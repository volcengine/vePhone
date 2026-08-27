from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from mua_platform.business.models import BusinessSpace
from mua_platform.pods.models import POD_STATUS_RUNNING, DiscoveredPod
from mua_platform.tasks.batches import aggregate_batch_status
from mua_platform.tasks.models import PodLease, Task, TaskBatch
from mua_platform.tasks.repository import SQLiteTaskRepository
from mua_platform.tasks.state_machine import ExecutionStatus

POD_FRESHNESS_WINDOW = timedelta(seconds=180)


@dataclass(frozen=True)
class ScheduleResult:
    task_ids: list[str]
    last_business_id: str | None


class BatchScheduler:
    def __init__(
        self,
        db: Session,
        *,
        reservation_ttl: timedelta = timedelta(minutes=5),
    ):
        self.db = db
        self.reservation_ttl = reservation_ttl

    def schedule(
        self,
        now: datetime,
        *,
        global_limit: int,
        start_after_business_id: str | None = None,
        blocked_batch_ids: set[str] | None = None,
    ) -> ScheduleResult:
        if global_limit < 1:
            raise ValueError("global_limit_must_be_positive")
        blocked_batch_ids = blocked_batch_ids or set()
        repository = SQLiteTaskRepository(self.db)
        repository.release_expired_leases(now)
        batches = list(
            self.db.scalars(
                select(TaskBatch)
                .options(selectinload(TaskBatch.tasks))
                .where(
                    TaskBatch.execution_status.in_(
                        [ExecutionStatus.QUEUED, ExecutionStatus.RUNNING]
                    ),
                )
                .order_by(TaskBatch.created_at, TaskBatch.id)
            )
        )
        eligible_batches: list[TaskBatch] = []
        for batch in batches:
            if batch.cancel_requested_at is not None:
                aggregate_batch_status(batch, now)
                continue
            if not any(
                task.execution_status == ExecutionStatus.QUEUED
                for task in batch.tasks
            ):
                aggregate_batch_status(batch, now)
                continue
            if batch.id in blocked_batch_ids:
                self._set_reason(
                    [
                        task
                        for task in batch.tasks
                        if task.execution_status == ExecutionStatus.QUEUED
                    ],
                    "waiting_for_pod_pool_refresh",
                )
                continue
            eligible_batches.append(batch)
        self.db.commit()

        active_leases = list(
            self.db.scalars(select(PodLease).where(PodLease.expires_at > now))
        )
        leased_task_ids = {lease.task_id for lease in active_leases}
        occupied_tasks = list(
            self.db.scalars(
                select(Task).where(
                    or_(
                        Task.execution_status == ExecutionStatus.RUNNING,
                        Task.id.in_(leased_task_ids),
                    )
                )
            )
        )
        occupied_by_id = {task.id: task for task in occupied_tasks}
        business_occupied = Counter(
            task.business_id for task in occupied_by_id.values()
        )
        global_remaining = max(0, global_limit - len(occupied_by_id))

        batches_by_business: dict[str, list[TaskBatch]] = defaultdict(list)
        for batch in eligible_batches:
            batches_by_business[batch.business_id].append(batch)
        business_ids = list(batches_by_business)
        business_limits = {
            business.id: business.task_concurrency_limit
            for business in self.db.scalars(
                select(BusinessSpace).where(BusinessSpace.id.in_(business_ids))
            )
        }

        if global_remaining == 0:
            self._set_capacity_reason(
                eligible_batches,
                leased_task_ids,
                "waiting_for_global_capacity",
            )
            self.db.commit()
            return ScheduleResult([], start_after_business_id)

        ordered_business_ids = self._rotate_businesses(
            business_ids,
            start_after_business_id,
        )
        assigned: list[str] = []
        last_business_id = start_after_business_id
        while global_remaining > 0:
            assigned_in_round = False
            for business_id in ordered_business_ids:
                limit = business_limits.get(business_id, 4)
                if business_occupied[business_id] >= limit:
                    self._set_capacity_reason(
                        batches_by_business[business_id],
                        leased_task_ids | set(assigned),
                        "waiting_for_business_capacity",
                    )
                    continue
                for batch in batches_by_business[business_id]:
                    newly_assigned = self._schedule_batch(
                        batch,
                        now,
                        repository,
                        max_assignments=1,
                    )
                    if not newly_assigned:
                        continue
                    task_id = newly_assigned[0]
                    assigned.append(task_id)
                    business_occupied[business_id] += 1
                    global_remaining -= 1
                    last_business_id = business_id
                    assigned_in_round = True
                    break
                if global_remaining == 0:
                    break
            if not assigned_in_round:
                break

        if global_remaining == 0:
            self._set_capacity_reason(
                eligible_batches,
                leased_task_ids | set(assigned),
                "waiting_for_global_capacity",
            )
        self.db.commit()
        return ScheduleResult(assigned, last_business_id)

    def _schedule_batch(
        self,
        batch: TaskBatch,
        now: datetime,
        repository: SQLiteTaskRepository,
        *,
        max_assignments: int,
    ) -> list[str]:
        if batch.cancel_requested_at is not None:
            aggregate_batch_status(batch, now)
            self.db.commit()
            return []
        queued = [
            task
            for task in batch.tasks
            if task.execution_status == ExecutionStatus.QUEUED
        ]
        if not queued:
            aggregate_batch_status(batch, now)
            self.db.commit()
            return []

        product_id = batch.config_snapshot.get("product_id")
        if not isinstance(product_id, str) or not product_id:
            self._set_reason(queued, "waiting_for_any_device")
            self.db.commit()
            return []

        active_leases = list(
            self.db.scalars(select(PodLease).where(PodLease.expires_at > now))
        )
        lease_by_task = {lease.task_id: lease for lease in active_leases}
        leased_keys = {lease.pod_id for lease in active_leases}
        occupied = sum(
            task.execution_status == ExecutionStatus.RUNNING
            or task.id in lease_by_task
            for task in batch.tasks
        )
        slots = min(
            max_assignments,
            max(0, batch.concurrency - occupied),
        )
        unreserved = [task for task in queued if task.id not in lease_by_task]
        if slots == 0:
            self._set_reason(unreserved, "waiting_for_batch_capacity")
            self.db.commit()
            return []

        rows = list(
            self.db.scalars(
                select(DiscoveredPod)
                .where(DiscoveredPod.product_id == product_id)
                .order_by(DiscoveredPod.last_assigned_at.asc().nullsfirst())
            )
        )
        row_by_id = {row.pod_id: row for row in rows}
        requested_ids = (
            list(batch.pod_ids)
            if batch.device_strategy == "specified"
            else [row.pod_id for row in rows]
        )
        hard_unavailable = {
            pod_id
            for pod_id in requested_ids
            if self._hard_unavailable(row_by_id.get(pod_id), now)
        }
        available = [
            row_by_id[pod_id]
            for pod_id in requested_ids
            if pod_id in row_by_id
            and pod_id not in hard_unavailable
            and f"{product_id}:{pod_id}" not in leased_keys
            and pod_id not in leased_keys
        ]

        if batch.device_strategy == "specified":
            all_hard_unavailable = bool(requested_ids) and len(
                hard_unavailable
            ) == len(requested_ids)
            if all_hard_unavailable:
                return self._handle_all_unavailable(
                    batch,
                    queued,
                    now,
                    repository,
                )
            if batch.unavailable_since is not None:
                batch.unavailable_since = None

        newly_assigned: list[str] = []
        for task, pod in zip(unreserved[:slots], available[:slots], strict=False):
            if repository.reserve_batch_pod(
                task.id,
                product_id,
                pod.pod_id,
                now,
                self.reservation_ttl,
            ):
                newly_assigned.append(task.id)
                leased_keys.add(f"{product_id}:{pod.pod_id}")

        remaining = [
            task for task in unreserved if task.id not in set(newly_assigned)
        ]
        if remaining:
            if len(newly_assigned) >= slots:
                reason = "waiting_for_capacity"
            elif batch.device_strategy == "specified":
                reason = "waiting_for_specified_device"
            else:
                reason = "waiting_for_any_device"
            self._set_reason(remaining, reason)
            self.db.commit()
        return newly_assigned

    @staticmethod
    def _rotate_businesses(
        business_ids: list[str],
        start_after_business_id: str | None,
    ) -> list[str]:
        if start_after_business_id not in business_ids:
            return business_ids
        start = business_ids.index(start_after_business_id) + 1
        return business_ids[start:] + business_ids[:start]

    @staticmethod
    def _set_capacity_reason(
        batches: list[TaskBatch],
        occupied_task_ids: set[str],
        reason: str,
    ) -> None:
        for batch in batches:
            BatchScheduler._set_reason(
                [
                    task
                    for task in batch.tasks
                    if task.execution_status == ExecutionStatus.QUEUED
                    and task.id not in occupied_task_ids
                ],
                reason,
            )

    def _handle_all_unavailable(
        self,
        batch: TaskBatch,
        queued: list[Task],
        now: datetime,
        repository: SQLiteTaskRepository,
    ) -> list[str]:
        self._set_reason(queued, "device_temporarily_unavailable")
        if batch.unavailable_since is None:
            batch.unavailable_since = now
            self.db.commit()
            return []
        unavailable_since = _aware(batch.unavailable_since)
        if now - unavailable_since < timedelta(
            seconds=batch.device_wait_timeout_seconds
        ):
            self.db.commit()
            return []
        task_ids = [task.id for task in queued]
        self.db.commit()
        for task_id in task_ids:
            repository.finalize_device_unavailable(task_id)
        self.db.expire_all()
        refreshed = self.db.scalar(
            select(TaskBatch)
            .options(selectinload(TaskBatch.tasks))
            .where(TaskBatch.id == batch.id)
        )
        if refreshed is not None:
            aggregate_batch_status(refreshed, now)
            self.db.commit()
        return []

    @staticmethod
    def _set_reason(tasks: list[Task], reason: str) -> None:
        for task in tasks:
            task.queue_reason = reason

    @staticmethod
    def _hard_unavailable(
        pod: DiscoveredPod | None,
        now: datetime,
    ) -> bool:
        if pod is None:
            return True
        if pod.discovery_state != "active":
            return True
        if pod.pod_status_code != POD_STATUS_RUNNING:
            return True
        if now - _aware(pod.last_seen_at) > POD_FRESHNESS_WINDOW:
            return True
        return pod.cooldown_until is not None and _aware(pod.cooldown_until) > now


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
