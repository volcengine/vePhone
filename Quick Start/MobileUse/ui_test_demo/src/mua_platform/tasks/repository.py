from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol
from uuid import uuid4

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mua_platform.business.models import DEFAULT_BUSINESS_ID
from mua_platform.cases.models import TestCase
from mua_platform.pods.models import DiscoveredPod
from mua_platform.pods.schemas import VerifiedPodAllocation
from mua_platform.runners.base import RunHandle, RunnerEvent
from mua_platform.tasks.models import (
    PodLease,
    Task,
    TaskEvent,
    TaskRunnerConfig,
    utc_now,
)
from mua_platform.tasks.state_machine import (
    CANCELLABLE_STATUSES,
    ExecutionStatus,
    StartState,
    Verdict,
    transition,
    validate_terminal_outcome,
)
from mua_platform.traces.repository import TraceRepository
from mua_platform.traces.service import draft_for_runner_event

DEFERRED_EVENT_TYPES = {
    "task_finished",
    "task_cancelled",
    "runner_interrupted",
}
LOGGER_NAME = "mua_platform.pod_leases"
RELEASE_REASONS = frozenset(
    {
        "terminal",
        "cancelled",
        "interrupted",
        "startup_cleanup",
        "startup_requeue",
        "orphan_cleanup",
        "explicit",
    }
)
logger = logging.getLogger(LOGGER_NAME)


def _log(level: int, event: str, **fields: object) -> None:
    try:
        logger.log(level, event, extra=fields)
    except Exception:
        pass


class PodLeaseConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class TaskCreationResult:
    task: Task
    disposition: Literal["created", "existing"]


@dataclass(frozen=True)
class _ReleasedLease:
    task_id: str
    resource_key: str
    worker_id: str
    lease_version: int
    reason: str


class TaskRepository(Protocol):
    def create_from_case(
        self,
        case: TestCase,
        scenario: str,
        *,
        idempotency_key: str,
        runner_type: str = "mock",
        created_by: str = "system",
        runner_config_snapshot: dict[str, Any] | None = None,
        verified_allocation: VerifiedPodAllocation | None = None,
    ) -> TaskCreationResult: ...

    def claim(
        self,
        task_id: str,
        worker_id: str,
        now: datetime,
        lease_ttl: timedelta,
        execution_timeout: timedelta = timedelta(seconds=600),
    ) -> Task | None: ...

    def claim_next(
        self,
        worker_id: str,
        now: datetime,
        lease_ttl: timedelta,
        execution_timeout: timedelta = timedelta(seconds=600),
    ) -> Task | None: ...

    def mark_start_dispatching(
        self,
        task_id: str,
        now: datetime,
    ) -> Task | None: ...

    def save_run_handle(self, task_id: str, handle: RunHandle) -> Task: ...

    def repair_start_attached(self, task_id: str) -> Task: ...

    def requeue_before_dispatch(self, task_id: str) -> Task: ...

    def finalize_start_outcome_unknown(
        self,
        task_id: str,
        quarantine_until: datetime,
    ) -> Task: ...

    def renew_lease(
        self,
        task_id: str,
        worker_id: str,
        now: datetime,
        lease_ttl: timedelta,
    ) -> bool: ...

    def ensure_attached_lease(
        self,
        task_id: str,
        worker_id: str,
        now: datetime,
        lease_ttl: timedelta,
    ) -> bool: ...

    def release_lease(
        self,
        task_id: str,
        worker_id: str | None = None,
        reason: str = "explicit",
    ) -> bool: ...

    def release_expired_leases(self, now: datetime) -> int: ...

    def recover_running_leases(
        self,
        worker_id: str,
        now: datetime,
        lease_ttl: timedelta,
    ) -> int: ...

    def list_recoverable(self) -> list[Task]: ...

    def last_event_sequence(self, task_id: str) -> int: ...

    def request_cancel(self, task_id: str, now: datetime | None = None) -> Task: ...

    def mark_cancel_dispatched(self, task_id: str, now: datetime) -> Task: ...

    def finalize_cancel(self, task_id: str) -> Task: ...

    def finalize_preclaim_failure(self, task_id: str) -> Task: ...

    def finalize_device_unavailable(self, task_id: str) -> Task: ...

    def finalize_queued_failure(
        self,
        task_id: str,
        failure_type: str,
    ) -> Task: ...

    def reserve_batch_pod(
        self,
        task_id: str,
        product_id: str,
        pod_id: str,
        now: datetime,
        lease_ttl: timedelta,
    ) -> bool: ...

    def finalize_interrupted(self, task_id: str, failure_type: str) -> Task: ...

    def record_cancel_warning(self, task_id: str, error_code: str) -> Task: ...

    def has_cancel_warning(self, task_id: str) -> bool: ...

    def end_transaction(self) -> None: ...

    def append_event(self, task_id: str, event: RunnerEvent) -> TaskEvent: ...

    def record_event(
        self,
        task_id: str,
        event: RunnerEvent,
        *,
        status: ExecutionStatus | None = None,
        verdict: Verdict | None = None,
        failure_type: str | None = None,
        release_lease_worker_id: str | None = None,
        result_summary: str | None = None,
        result_evidence: list[str] | None = None,
        recording_url: str | None = None,
        result_assets: dict[str, Any] | None = None,
        remote_status_code: int | None = None,
        remote_step_id: str | None = None,
        remote_thread_id: str | None = None,
    ) -> TaskEvent: ...

    def mark_running(self, task_id: str) -> Task: ...

    def finish(
        self,
        task_id: str,
        status: ExecutionStatus,
        verdict: Verdict | None,
        failure_type: str | None,
        *,
        result_summary: str | None = None,
        result_evidence: list[str] | None = None,
        recording_url: str | None = None,
        result_assets: dict[str, Any] | None = None,
        remote_status_code: int | None = None,
        remote_step_id: str | None = None,
        remote_thread_id: str | None = None,
    ) -> Task: ...

    def get(self, task_id: str) -> Task | None: ...

    def refresh(self, task_id: str) -> Task: ...

    def list(self) -> list[Task]: ...

    def list_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        case_id: str | None = None,
        created_by: str | None = None,
        status: str | None = None,
        verdict: str | None = None,
        review_result: str | None = None,
        search: str | None = None,
        business_id: str | None = None,
    ) -> tuple[list[Task], int]: ...

    def stats(self, business_id: str | None = None) -> dict[str, int]: ...

    def list_operators(self, business_id: str | None = None) -> list[str]: ...

    def get_case(self, case_id: str) -> TestCase | None: ...


class SQLiteTaskRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_from_case(
        self,
        case: TestCase,
        scenario: str,
        *,
        idempotency_key: str,
        runner_type: str = "mock",
        created_by: str = "system",
        runner_config_snapshot: dict[str, Any] | None = None,
        verified_allocation: VerifiedPodAllocation | None = None,
    ) -> TaskCreationResult:
        request_fingerprint = {
            "runner_type": runner_type,
            "case_id": case.id,
            "scenario": scenario,
        }
        fingerprint = _canonical_json(request_fingerprint)
        snapshot = (
            runner_config_snapshot
            if runner_config_snapshot is not None
            else {"pod_id": "mock:default"}
        )
        if verified_allocation is not None:
            snapshot = {
                **snapshot,
                "product_id": verified_allocation.product_id,
                "pod_id": verified_allocation.pod_id,
            }

        existing = self._find_idempotent_case(case.id, idempotency_key, fingerprint)
        if existing is not None:
            return TaskCreationResult(task=existing, disposition="existing")

        task = Task(
            id=f"task_{uuid4().hex}",
            business_id=case.business_id or DEFAULT_BUSINESS_ID,
            case_id=case.id,
            script_version_id=None,
            prompt_snapshot=case.content_markdown,
            runner_type=runner_type,
            scenario=scenario,
            created_by=created_by,
            execution_status=ExecutionStatus.QUEUED,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            version=1,
        )
        task.runner_config = TaskRunnerConfig(config_snapshot=snapshot)
        task.start_idempotency_key = f"start:{task.id}"
        try:
            self.db.add(task)
            if verified_allocation is not None:
                pod = self.db.scalar(
                    select(DiscoveredPod).where(
                        DiscoveredPod.product_id == verified_allocation.product_id,
                        DiscoveredPod.pod_id == verified_allocation.pod_id,
                    )
                )
                if pod is None:
                    raise ValueError("verified_pod_missing")
                pod.last_assigned_at = verified_allocation.checked_at
                self.db.add(
                    PodLease(
                        pod_id=verified_allocation.resource_key,
                        task_id=task.id,
                        worker_id="reserved",
                        expires_at=verified_allocation.checked_at + timedelta(days=365),
                        version=1,
                    )
                )
                self.db.flush()
                TraceRepository(self.db).insert_allocation_drafts(
                    task.id,
                    verified_allocation.trace_drafts,
                )
            self.db.commit()
            if verified_allocation is not None:
                _log(
                    logging.INFO,
                    "pod_lease_reserved",
                    task_id=task.id,
                    resource_key=verified_allocation.resource_key,
                    worker_id="reserved",
                    lease_version=1,
                )
            return TaskCreationResult(task=task, disposition="created")
        except IntegrityError:
            self.db.rollback()
            existing = self._find_idempotent_case(case.id, idempotency_key, fingerprint)
            if existing is not None:
                return TaskCreationResult(task=existing, disposition="existing")
            if verified_allocation is not None:
                raise PodLeaseConflict(verified_allocation.resource_key)
            raise
        except Exception:
            self.db.rollback()
            raise

    def _find_idempotent_case(
        self,
        case_id: str,
        idempotency_key: str,
        fingerprint: str,
    ) -> Task | None:
        existing = self.db.scalar(
            select(Task).where(
                Task.case_id == case_id,
                Task.idempotency_key == idempotency_key,
                Task.script_version_id.is_(None),
            )
        )
        if existing is not None and existing.request_fingerprint != fingerprint:
            raise ValueError(f"idempotency_conflict:{case_id}:{idempotency_key}")
        return existing

    def claim(
        self,
        task_id: str,
        worker_id: str,
        now: datetime,
        lease_ttl: timedelta,
        execution_timeout: timedelta = timedelta(seconds=600),
    ) -> Task | None:
        candidate = self.db.execute(
            select(
                Task.version,
                Task.execution_status,
                TaskRunnerConfig.config_snapshot,
            )
            .outerjoin(TaskRunnerConfig, TaskRunnerConfig.task_id == Task.id)
            .where(Task.id == task_id)
        ).one_or_none()
        self.db.rollback()
        if candidate is None or candidate.execution_status != ExecutionStatus.QUEUED:
            _log(
                logging.WARNING,
                "pod_lease_claim_rejected",
                task_id=task_id,
                worker_id=worker_id,
                reason="task_unavailable",
            )
            return None

        snapshot = (
            candidate.config_snapshot
            if candidate.config_snapshot is not None
            else {"pod_id": "mock:default"}
        )
        pod_id = snapshot.get("pod_id") if isinstance(snapshot, dict) else None
        if not isinstance(pod_id, str) or not pod_id:
            raise ValueError(f"runner_snapshot_invalid:{task_id}")

        try:
            claimed = self.db.execute(
                update(Task)
                .where(
                    Task.id == task_id,
                    Task.version == candidate.version,
                    Task.execution_status == ExecutionStatus.QUEUED,
                )
                .values(
                    execution_status=ExecutionStatus.RUNNING,
                    started_at=now,
                    deadline_at=None,
                    version=Task.version + 1,
                )
            )
            if claimed.rowcount != 1:
                self.db.rollback()
                _log(
                    logging.WARNING,
                    "pod_lease_claim_rejected",
                    task_id=task_id,
                    worker_id=worker_id,
                    reason="task_conflict",
                )
                return None

            reserved = self.db.scalar(
                select(PodLease).where(PodLease.task_id == task_id)
            )
            if reserved is None:
                product_id = snapshot.get("product_id")
                resource_key = (
                    f"{product_id}:{pod_id}"
                    if isinstance(product_id, str) and product_id
                    else pod_id
                )
                self.db.add(
                    PodLease(
                        pod_id=resource_key,
                        task_id=task_id,
                        worker_id=worker_id,
                        expires_at=now + lease_ttl,
                        version=1,
                    )
                )
                lease_version = 1
                claim_reason = "compatibility_created"
            else:
                if reserved.pod_id not in {
                    pod_id,
                    f"{snapshot.get('product_id')}:{pod_id}",
                }:
                    resource_key = reserved.pod_id
                    self.db.rollback()
                    _log(
                        logging.WARNING,
                        "pod_lease_claim_rejected",
                        task_id=task_id,
                        resource_key=resource_key,
                        worker_id=worker_id,
                        reason="resource_key_mismatch",
                    )
                    raise ValueError(f"runner_lease_invalid:{task_id}")
                reserved.worker_id = worker_id
                reserved.expires_at = now + lease_ttl
                reserved.version += 1
                resource_key = reserved.pod_id
                lease_version = reserved.version
                claim_reason = "reserved_takeover"
            self.db.flush()
            self.db.commit()
            _log(
                logging.INFO,
                "pod_lease_claimed",
                task_id=task_id,
                resource_key=resource_key,
                worker_id=worker_id,
                lease_version=lease_version,
                reason=claim_reason,
            )
            return self.db.get(Task, task_id)
        except IntegrityError:
            self.db.rollback()
            _log(
                logging.WARNING,
                "pod_lease_claim_rejected",
                task_id=task_id,
                worker_id=worker_id,
                reason="lease_conflict",
            )
            return None
        except Exception:
            self.db.rollback()
            raise

    def claim_next(
        self,
        worker_id: str,
        now: datetime,
        lease_ttl: timedelta,
        execution_timeout: timedelta = timedelta(seconds=600),
    ) -> Task | None:
        candidate_ids = list(
            self.db.scalars(
                select(Task.id)
                .where(Task.execution_status == ExecutionStatus.QUEUED)
                .order_by(Task.created_at, Task.id)
            )
        )
        self.db.rollback()

        for task_id in candidate_ids:
            claimed = self.claim(
                task_id,
                worker_id,
                now,
                lease_ttl,
                execution_timeout,
            )
            if claimed is not None:
                return claimed

        return None

    def mark_start_dispatching(
        self,
        task_id: str,
        now: datetime,
    ) -> Task | None:
        task = self._required(task_id)
        changed = self.db.execute(
            update(Task)
            .where(
                Task.id == task_id,
                Task.version == task.version,
                Task.execution_status == ExecutionStatus.RUNNING,
                Task.start_state == StartState.PENDING,
                Task.remote_run_id.is_(None),
            )
            .values(
                start_state=StartState.DISPATCHING,
                start_attempted_at=now,
                version=Task.version + 1,
            )
        )
        if changed.rowcount != 1:
            self.db.rollback()
            return None
        self.db.commit()
        return self._reload(task_id)

    def save_run_handle(self, task_id: str, handle: RunHandle) -> Task:
        try:
            task = self._required(task_id)
            if handle.task_id != task.id or handle.runner_type != task.runner_type:
                raise ValueError(f"invalid_run_handle:{task_id}")
            changed = self.db.execute(
                update(Task)
                .where(
                    Task.id == task_id,
                    Task.execution_status == ExecutionStatus.RUNNING,
                    Task.start_state == StartState.DISPATCHING,
                    Task.remote_run_id.is_(None),
                )
                .values(
                    remote_run_id=handle.run_id,
                    remote_thread_id=handle.thread_id or task.remote_thread_id,
                    start_state=StartState.ATTACHED,
                    version=Task.version + 1,
                )
            )
            if changed.rowcount != 1:
                self.db.rollback()
                raise ValueError(f"task_start_not_dispatching:{task_id}")
            self.db.commit()
            return self._reload(task_id)
        except Exception:
            self.db.rollback()
            raise

    def repair_start_attached(self, task_id: str) -> Task:
        task = self._required(task_id)
        if task.remote_run_id is None:
            raise ValueError(f"task_run_handle_missing:{task_id}")
        task.start_state = StartState.ATTACHED
        task.version += 1
        self.db.commit()
        return task

    def requeue_before_dispatch(self, task_id: str) -> Task:
        try:
            task = self._required(task_id)
            changed = self.db.execute(
                update(Task)
                .where(
                    Task.id == task_id,
                    Task.version == task.version,
                    Task.execution_status == ExecutionStatus.RUNNING,
                    Task.start_state == StartState.PENDING,
                    Task.remote_run_id.is_(None),
                )
                .values(
                    execution_status=ExecutionStatus.QUEUED,
                    started_at=None,
                    version=Task.version + 1,
                )
            )
            if changed.rowcount != 1:
                self.db.rollback()
                raise ValueError(f"task_requeue_conflict:{task_id}")
            released = self._release_lease(
                task_id,
                None,
                "startup_requeue",
            )
            self.db.commit()
            self._log_release_result(
                task_id,
                None,
                "startup_requeue",
                released,
            )
            return self._reload(task_id)
        except Exception:
            self.db.rollback()
            raise

    def renew_lease(
        self,
        task_id: str,
        worker_id: str,
        now: datetime,
        lease_ttl: timedelta,
    ) -> bool:
        try:
            renewed = self.db.execute(
                update(PodLease)
                .where(
                    PodLease.task_id == task_id,
                    PodLease.worker_id == worker_id,
                    PodLease.expires_at > now,
                )
                .values(
                    expires_at=now + lease_ttl,
                    version=PodLease.version + 1,
                )
                .execution_options(synchronize_session=False)
                .returning(PodLease.pod_id, PodLease.version)
            ).one_or_none()
            if renewed is None:
                lease_state = self.db.execute(
                    select(PodLease.worker_id).where(PodLease.task_id == task_id)
                ).one_or_none()
                if lease_state is None:
                    failure_reason = "missing"
                elif lease_state.worker_id != worker_id:
                    failure_reason = "worker_mismatch"
                else:
                    failure_reason = "expired"
            self.db.commit()
            if renewed is None:
                _log(
                    logging.WARNING,
                    "pod_lease_renew_failed",
                    task_id=task_id,
                    worker_id=worker_id,
                    reason=failure_reason,
                )
                return False
            _log(
                logging.DEBUG,
                "pod_lease_renewed",
                task_id=task_id,
                resource_key=renewed.pod_id,
                worker_id=worker_id,
                lease_version=renewed.version,
            )
            return True
        except Exception:
            self.db.rollback()
            raise

    def ensure_attached_lease(
        self,
        task_id: str,
        worker_id: str,
        now: datetime,
        lease_ttl: timedelta,
    ) -> bool:
        try:
            task = self._required(task_id)
            if (
                task.execution_status != ExecutionStatus.RUNNING
                or task.start_state != StartState.ATTACHED
                or task.remote_run_id is None
            ):
                self.db.rollback()
                return False
            resource_keys = _lease_resource_keys(task.runner_config_snapshot)
            expected_key = resource_keys[-1]
            lease = self.db.scalar(
                select(PodLease).where(PodLease.task_id == task_id)
            )
            conflict = self.db.scalar(
                select(PodLease).where(
                    PodLease.pod_id.in_(resource_keys),
                    PodLease.task_id != task_id,
                )
            )
            if (
                conflict is not None
                or lease is not None
                and (
                    lease.worker_id != worker_id
                    or lease.pod_id not in resource_keys
                )
            ):
                self.db.rollback()
                return False

            expires_at = _utc_naive(now + lease_ttl)
            if lease is None:
                inserted = self.db.execute(
                    sqlite_insert(PodLease)
                    .values(
                        pod_id=expected_key,
                        task_id=task_id,
                        worker_id=worker_id,
                        expires_at=expires_at,
                        version=1,
                    )
                    .on_conflict_do_nothing()
                )
                if inserted.rowcount != 1:
                    self.db.rollback()
                    return False
                resource_key = expected_key
                lease_version = 1
                reason = "recreated"
            else:
                reason = (
                    "renewed"
                    if _utc_naive(lease.expires_at) > _utc_naive(now)
                    else "recovered"
                )
                lease.expires_at = expires_at
                lease.version += 1
                resource_key = lease.pod_id
                lease_version = lease.version
            self.db.commit()
            _log(
                logging.INFO,
                "pod_lease_ownership_ensured",
                task_id=task_id,
                resource_key=resource_key,
                worker_id=worker_id,
                lease_version=lease_version,
                reason=reason,
            )
            return True
        except Exception:
            self.db.rollback()
            raise

    def release_lease(
        self,
        task_id: str,
        worker_id: str | None = None,
        reason: str = "explicit",
    ) -> bool:
        _validate_release_reason(reason)
        try:
            released = self._release_lease(task_id, worker_id, reason)
            self.db.commit()
            self._log_release_result(task_id, worker_id, reason, released)
            return released is not None
        except Exception:
            self.db.rollback()
            raise

    def release_expired_leases(self, now: datetime) -> int:
        try:
            running_task_ids = select(Task.id).where(
                Task.execution_status == ExecutionStatus.RUNNING
            )
            released = self.db.execute(
                delete(PodLease).where(
                    PodLease.expires_at <= now,
                    PodLease.task_id.not_in(running_task_ids),
                )
            )
            self.db.commit()
            _log(
                logging.INFO,
                "pod_lease_cleanup_completed",
                reason="startup_cleanup",
                released_count=released.rowcount,
            )
            return released.rowcount
        except Exception:
            self.db.rollback()
            raise

    def recover_running_leases(
        self,
        worker_id: str,
        now: datetime,
        lease_ttl: timedelta,
    ) -> int:
        try:
            running_task_ids = select(Task.id).where(
                Task.execution_status == ExecutionStatus.RUNNING
            )
            recovered = self.db.execute(
                update(PodLease)
                .where(PodLease.task_id.in_(running_task_ids))
                .values(
                    worker_id=worker_id,
                    expires_at=now + lease_ttl,
                    version=PodLease.version + 1,
                )
                .execution_options(synchronize_session=False)
            )
            self.db.commit()
            return recovered.rowcount
        except Exception:
            self.db.rollback()
            raise

    def list_recoverable(self) -> list[Task]:
        tasks = list(
            self.db.scalars(
                select(Task)
                .where(
                    Task.execution_status.in_(
                        [ExecutionStatus.QUEUED, ExecutionStatus.RUNNING]
                    )
                )
                .order_by(Task.created_at, Task.id)
            )
        )
        recoverable: list[Task] = []
        for task in tasks:
            if (
                task.execution_status == ExecutionStatus.QUEUED
                and task.batch_id is not None
                and task.cancel_requested_at is None
                and self.db.scalar(
                    select(PodLease.task_id).where(PodLease.task_id == task.id)
                )
                is None
            ):
                continue
            recoverable.append(task)
        return recoverable

    def last_event_sequence(self, task_id: str) -> int:
        current = self.db.scalar(
            select(func.max(TaskEvent.sequence)).where(TaskEvent.task_id == task_id)
        )
        return current or 0

    def request_cancel(self, task_id: str, now: datetime | None = None) -> Task:
        requested_at = now or utc_now()
        released_lease: _ReleasedLease | None = None
        release_attempted = False
        try:
            task = self._required(task_id)
            if task.execution_status == ExecutionStatus.CANCELLED:
                return task
            if task.execution_status not in CANCELLABLE_STATUSES:
                raise ValueError(f"task_not_cancellable:{task_id}")

            if task.execution_status == ExecutionStatus.QUEUED:
                cancelled = self.db.execute(
                    update(Task)
                    .where(
                        Task.id == task_id,
                        Task.version == task.version,
                        Task.execution_status == ExecutionStatus.QUEUED,
                    )
                    .values(
                        execution_status=ExecutionStatus.CANCELLED,
                        verdict=None,
                        failure_type=None,
                        finished_at=requested_at,
                        version=Task.version + 1,
                    )
                )
                if cancelled.rowcount != 1:
                    self.db.rollback()
                    return self.request_cancel(task_id)
                self._insert_event(
                    task_id,
                    RunnerEvent(
                        sequence=self._next_event_sequence(task_id),
                        type="task_cancelled",
                        payload={},
                    ),
                )
                released_lease = self._release_lease(task_id, None, "cancelled")
                release_attempted = True
            elif task.cancel_requested_at is None:
                requested = self.db.execute(
                    update(Task)
                    .where(
                        Task.id == task_id,
                        Task.version == task.version,
                        Task.execution_status == ExecutionStatus.RUNNING,
                        Task.cancel_requested_at.is_(None),
                    )
                    .values(
                        cancel_requested_at=requested_at,
                        last_polled_at=None,
                        version=Task.version + 1,
                    )
                )
                if requested.rowcount != 1:
                    self.db.rollback()
                    return self.request_cancel(task_id)

            self.db.commit()
            if release_attempted:
                self._log_release_result(
                    task_id,
                    None,
                    "cancelled",
                    released_lease,
                )
            return self._reload(task_id)
        except Exception:
            self.db.rollback()
            raise

    def mark_cancel_dispatched(self, task_id: str, now: datetime) -> Task:
        try:
            task = self._required(task_id)
            if task.execution_status != ExecutionStatus.RUNNING:
                return task
            task.last_polled_at = now
            task.version += 1
            self.db.commit()
            return self._reload(task_id)
        except Exception:
            self.db.rollback()
            raise

    def finalize_cancel(self, task_id: str) -> Task:
        released_lease: _ReleasedLease | None = None
        try:
            task = self._required(task_id)
            if task.execution_status == ExecutionStatus.CANCELLED:
                return task
            if (
                task.execution_status != ExecutionStatus.RUNNING
                or task.cancel_requested_at is None
            ):
                raise ValueError(f"task_not_cancellable:{task_id}")

            cancelled = self.db.execute(
                update(Task)
                .where(
                    Task.id == task_id,
                    Task.version == task.version,
                    Task.execution_status == ExecutionStatus.RUNNING,
                    Task.cancel_requested_at.is_not(None),
                )
                .values(
                    execution_status=ExecutionStatus.CANCELLED,
                    verdict=None,
                    failure_type=None,
                    finished_at=utc_now(),
                    version=Task.version + 1,
                )
            )
            if cancelled.rowcount != 1:
                self.db.rollback()
                current = self._required(task_id)
                if current.execution_status == ExecutionStatus.CANCELLED:
                    return current
                raise ValueError(f"task_cancel_conflict:{task_id}")

            self._insert_event(
                task_id,
                RunnerEvent(
                    sequence=self._next_event_sequence(task_id),
                    type="task_cancelled",
                    payload={},
                ),
            )
            released_lease = self._release_lease(task_id, None, "cancelled")
            self.db.commit()
            self._log_release_result(task_id, None, "cancelled", released_lease)
            return self._reload(task_id)
        except Exception:
            self.db.rollback()
            raise

    def finalize_start_outcome_unknown(
        self,
        task_id: str,
        quarantine_until: datetime,
    ) -> Task:
        quarantined_lease: PodLease | None = None
        try:
            task = self._required(task_id)
            if task.execution_status == ExecutionStatus.RESULT_READY:
                return task
            if (
                task.execution_status != ExecutionStatus.RUNNING
                or task.start_state != StartState.DISPATCHING
                or task.remote_run_id is not None
            ):
                raise ValueError(f"task_start_outcome_known:{task_id}")
            self._insert_event(
                task_id,
                RunnerEvent(
                    sequence=self._next_event_sequence(task_id),
                    type="task_start_outcome_unknown",
                    payload={"failure_type": "start_outcome_unknown"},
                ),
            )
            self._finish(
                task_id,
                ExecutionStatus.RESULT_READY,
                Verdict.FAIL,
                "start_outcome_unknown",
            )
            quarantined_lease = self.db.scalar(
                select(PodLease).where(PodLease.task_id == task_id)
            )
            if quarantined_lease is not None:
                if _utc_naive(quarantined_lease.expires_at) < _utc_naive(
                    quarantine_until
                ):
                    quarantined_lease.expires_at = quarantine_until
                quarantined_lease.version += 1
            self.db.commit()
            if quarantined_lease is None:
                _log(
                    logging.WARNING,
                    "pod_lease_quarantine_missed",
                    task_id=task_id,
                    reason="lease_missing",
                )
            else:
                _log(
                    logging.WARNING,
                    "pod_lease_quarantined",
                    task_id=task_id,
                    resource_key=quarantined_lease.pod_id,
                    worker_id=quarantined_lease.worker_id,
                    lease_version=quarantined_lease.version,
                    quarantine_until=_as_utc(quarantined_lease.expires_at).isoformat(),
                )
            return self._reload(task_id)
        except Exception:
            self.db.rollback()
            raise

    def finalize_interrupted(self, task_id: str, failure_type: str) -> Task:
        released_lease: _ReleasedLease | None = None
        try:
            task = self._required(task_id)
            if task.execution_status == ExecutionStatus.RESULT_READY:
                return task
            if task.execution_status != ExecutionStatus.RUNNING:
                raise ValueError(f"task_not_running:{task_id}")
            self._insert_event(
                task_id,
                RunnerEvent(
                    sequence=self._next_event_sequence(task_id),
                    type="runner_interrupted",
                    payload={"failure_type": failure_type},
                ),
            )
            self._finish(
                task_id,
                ExecutionStatus.RESULT_READY,
                Verdict.FAIL,
                failure_type,
            )
            released_lease = self._release_lease(task_id, None, "interrupted")
            self.db.commit()
            self._log_release_result(
                task_id,
                None,
                "interrupted",
                released_lease,
            )
            return self._reload(task_id)
        except Exception:
            self.db.rollback()
            raise

    def finalize_preclaim_failure(self, task_id: str) -> Task:
        released_lease: _ReleasedLease | None = None
        try:
            task = self._required(task_id)
            if task.execution_status == ExecutionStatus.RESULT_READY:
                return task
            if task.execution_status != ExecutionStatus.QUEUED:
                raise ValueError(f"task_not_queued:{task_id}")
            self._insert_event(
                task_id,
                RunnerEvent(
                    sequence=self._next_event_sequence(task_id),
                    type="runner_interrupted",
                    payload={"failure_type": "internal_error"},
                ),
            )
            self._finish(
                task_id,
                ExecutionStatus.RESULT_READY,
                Verdict.FAIL,
                "internal_error",
            )
            released_lease = self._release_lease(task_id, None, "interrupted")
            self.db.commit()
            self._log_release_result(
                task_id,
                None,
                "interrupted",
                released_lease,
            )
            return self._reload(task_id)
        except Exception:
            self.db.rollback()
            raise

    def finalize_device_unavailable(self, task_id: str) -> Task:
        return self.finalize_queued_failure(task_id, "device_unavailable")

    def finalize_queued_failure(
        self,
        task_id: str,
        failure_type: str,
    ) -> Task:
        released_lease: _ReleasedLease | None = None
        try:
            task = self._required(task_id)
            if task.execution_status == ExecutionStatus.RESULT_READY:
                return task
            if task.execution_status != ExecutionStatus.QUEUED:
                raise ValueError(f"task_not_queued:{task_id}")
            self._insert_event(
                task_id,
                RunnerEvent(
                    sequence=self._next_event_sequence(task_id),
                    type="runner_interrupted",
                    payload={"failure_type": failure_type},
                ),
            )
            self._finish(
                task_id,
                ExecutionStatus.RESULT_READY,
                Verdict.FAIL,
                failure_type,
            )
            released_lease = self._release_lease(task_id, None, "interrupted")
            self.db.commit()
            self._log_release_result(
                task_id,
                None,
                "interrupted",
                released_lease,
            )
            return self._reload(task_id)
        except Exception:
            self.db.rollback()
            raise

    def reserve_batch_pod(
        self,
        task_id: str,
        product_id: str,
        pod_id: str,
        now: datetime,
        lease_ttl: timedelta,
    ) -> bool:
        try:
            task = self._required(task_id)
            if (
                task.batch_id is None
                or task.execution_status != ExecutionStatus.QUEUED
            ):
                return False
            resource_key = f"{product_id}:{pod_id}"
            inserted = self.db.execute(
                sqlite_insert(PodLease)
                .values(
                    pod_id=resource_key,
                    task_id=task_id,
                    worker_id="reserved",
                    expires_at=now + lease_ttl,
                    version=1,
                )
                .on_conflict_do_nothing()
            )
            if inserted.rowcount != 1:
                self.db.rollback()
                return False
            config = self.db.get(TaskRunnerConfig, task_id)
            if config is None:
                raise ValueError(f"runner_snapshot_invalid:{task_id}")
            config.config_snapshot = {
                **config.config_snapshot,
                "product_id": product_id,
                "pod_id": pod_id,
            }
            task.queue_reason = None
            pod = self.db.scalar(
                select(DiscoveredPod).where(
                    DiscoveredPod.product_id == product_id,
                    DiscoveredPod.pod_id == pod_id,
                )
            )
            if pod is not None:
                pod.last_assigned_at = now
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise

    def record_cancel_warning(self, task_id: str, error_code: str) -> Task:
        try:
            task = self._required(task_id)
            if task.execution_status != ExecutionStatus.RUNNING:
                return task
            if self.has_cancel_warning(task_id):
                return task
            self._insert_event(
                task_id,
                RunnerEvent(
                    sequence=self._next_event_sequence(task_id),
                    type="runner_warning",
                    payload={"error_code": error_code},
                ),
            )
            self.db.commit()
            return self._reload(task_id)
        except Exception:
            self.db.rollback()
            raise

    def has_cancel_warning(self, task_id: str) -> bool:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(TaskEvent)
                .where(
                    TaskEvent.task_id == task_id,
                    TaskEvent.event_type == "runner_warning",
                )
            )
            or 0
        ) > 0

    def end_transaction(self) -> None:
        if self.db.in_transaction():
            self.db.commit()

    def append_event(self, task_id: str, event: RunnerEvent) -> TaskEvent:
        try:
            stored, _inserted = self._insert_event(task_id, event)
            if event.type in DEFERRED_EVENT_TYPES:
                self.db.flush()
            else:
                self.db.commit()
            return stored
        except Exception:
            self.db.rollback()
            raise

    def record_event(
        self,
        task_id: str,
        event: RunnerEvent,
        *,
        status: ExecutionStatus | None = None,
        verdict: Verdict | None = None,
        failure_type: str | None = None,
        release_lease_worker_id: str | None = None,
        result_summary: str | None = None,
        result_evidence: list[str] | None = None,
        recording_url: str | None = None,
        result_assets: dict[str, Any] | None = None,
        remote_status_code: int | None = None,
        remote_step_id: str | None = None,
        remote_thread_id: str | None = None,
    ) -> TaskEvent:
        released_lease: _ReleasedLease | None = None
        try:
            stored, inserted = self._insert_event(task_id, event)
            if inserted:
                if status == ExecutionStatus.RUNNING:
                    self._mark_running(task_id)
                elif status is not None:
                    self._finish(
                        task_id,
                        status,
                        verdict,
                        failure_type,
                        result_summary=result_summary,
                        result_evidence=result_evidence,
                        recording_url=recording_url,
                        result_assets=result_assets,
                        remote_status_code=remote_status_code,
                        remote_step_id=remote_step_id,
                        remote_thread_id=remote_thread_id,
                    )
            if release_lease_worker_id is not None:
                released_lease = self._release_lease(
                    task_id,
                    release_lease_worker_id,
                    "terminal",
                )
            self.db.commit()
            if release_lease_worker_id is not None:
                self._log_release_result(
                    task_id,
                    release_lease_worker_id,
                    "terminal",
                    released_lease,
                )
            return stored
        except Exception:
            self.db.rollback()
            raise

    def _insert_event(
        self,
        task_id: str,
        event: RunnerEvent,
    ) -> tuple[TaskEvent, bool]:
        event_id = f"event_{uuid4().hex}"
        statement = (
            sqlite_insert(TaskEvent)
            .values(
                id=event_id,
                task_id=task_id,
                sequence=event.sequence,
                event_type=event.type,
                payload=event.payload,
                created_at=utc_now(),
            )
            .on_conflict_do_nothing(index_elements=["task_id", "sequence"])
        )
        result = self.db.execute(statement)
        stored = self.db.scalar(
            select(TaskEvent).where(
                TaskEvent.task_id == task_id,
                TaskEvent.sequence == event.sequence,
            )
        )
        if stored is None:
            raise RuntimeError("event_insert_failed")
        inserted = result.rowcount == 1
        if inserted:
            runner_type = self.db.scalar(
                select(Task.runner_type).where(Task.id == task_id)
            )
            if runner_type is None:
                raise ValueError(f"task_not_found:{task_id}")
            TraceRepository(self.db).upsert(
                task_id,
                f"event.{event.sequence}",
                draft_for_runner_event(event, runner_type, stored.created_at),
            )
        return stored, inserted

    def mark_running(self, task_id: str) -> Task:
        task = self._mark_running(task_id)
        self.db.commit()
        return task

    def _mark_running(self, task_id: str) -> Task:
        task = self._required(task_id)
        task.execution_status = transition(
            task.execution_status,
            ExecutionStatus.RUNNING,
        )
        task.started_at = utc_now()
        task.version += 1
        return task

    def finish(
        self,
        task_id: str,
        status: ExecutionStatus,
        verdict: Verdict | None,
        failure_type: str | None,
        *,
        result_summary: str | None = None,
        result_evidence: list[str] | None = None,
        recording_url: str | None = None,
        result_assets: dict[str, Any] | None = None,
        remote_status_code: int | None = None,
        remote_step_id: str | None = None,
        remote_thread_id: str | None = None,
    ) -> Task:
        try:
            task = self._finish(
                task_id,
                status,
                verdict,
                failure_type,
                result_summary=result_summary,
                result_evidence=result_evidence,
                recording_url=recording_url,
                result_assets=result_assets,
                remote_status_code=remote_status_code,
                remote_step_id=remote_step_id,
                remote_thread_id=remote_thread_id,
            )
            self.db.commit()
            return task
        except Exception:
            self.db.rollback()
            raise

    def _finish(
        self,
        task_id: str,
        status: ExecutionStatus,
        verdict: Verdict | None,
        failure_type: str | None,
        *,
        result_summary: str | None = None,
        result_evidence: list[str] | None = None,
        recording_url: str | None = None,
        result_assets: dict[str, Any] | None = None,
        remote_status_code: int | None = None,
        remote_step_id: str | None = None,
        remote_thread_id: str | None = None,
    ) -> Task:
        validate_terminal_outcome(status, verdict)
        task = self._required(task_id)
        task.execution_status = transition(task.execution_status, status)
        task.verdict = verdict
        task.failure_type = failure_type
        task.finished_at = utc_now()
        if result_summary is not None:
            task.result_summary = result_summary
        if result_evidence is not None:
            task.result_evidence = result_evidence
        if recording_url is not None:
            task.recording_url = recording_url
        if result_assets is not None:
            task.result_assets = result_assets
        if remote_status_code is not None:
            task.remote_status_code = remote_status_code
        if remote_step_id is not None:
            task.remote_step_id = remote_step_id
        if remote_thread_id is not None:
            task.remote_thread_id = remote_thread_id
        task.version += 1
        return task

    def get(self, task_id: str, business_id: str | None = None) -> Task | None:
        task = self.db.get(Task, task_id)
        if task is None:
            return None
        if business_id is not None and task.business_id != business_id:
            return None
        return task

    def refresh(self, task_id: str) -> Task:
        self.db.expire_all()
        return self._required(task_id)

    def list(self) -> list[Task]:
        return list(self.db.scalars(select(Task).order_by(Task.created_at.desc())))

    def list_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        case_id: str | None = None,
        created_by: str | None = None,
        status: str | None = None,
        verdict: str | None = None,
        review_result: str | None = None,
        search: str | None = None,
        created_after: datetime | None = None,
        business_id: str | None = None,
    ) -> tuple[list[Task], int]:
        filters = []
        if business_id:
            filters.append(Task.business_id == business_id)
        if case_id:
            filters.append(Task.case_id == case_id)
        if created_by:
            filters.append(
                or_(
                    Task.created_by == created_by,
                    Task.reviewed_by == created_by,
                )
            )
        if status:
            filters.append(Task.execution_status == status)
        if verdict:
            filters.append(Task.verdict == verdict)
        if review_result == "unreviewed":
            filters.append(Task.execution_status == ExecutionStatus.RESULT_READY)
            filters.append(Task.review_result.is_(None))
        elif review_result:
            filters.append(Task.review_result == review_result)
        if created_after:
            filters.append(Task.created_at >= created_after)
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    Task.id.ilike(pattern),
                    Task.batch_id.ilike(pattern),
                    Task.case_id.ilike(pattern),
                    Task.scenario.ilike(pattern),
                    Task.created_by.ilike(pattern),
                )
            )

        count_query = select(func.count(Task.id))
        query = select(Task)
        if filters:
            count_query = count_query.where(*filters)
            query = query.where(*filters)

        total = self.db.scalar(count_query) or 0
        items = list(
            self.db.scalars(
                query.order_by(Task.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return items, total

    def stats(self, business_id: str | None = None) -> dict[str, int]:
        filters = [Task.business_id == business_id] if business_id else []
        (
            total,
            running,
            queued,
            passed,
            completed,
            manual_review_failed,
            manual_review_total,
        ) = self.db.execute(
            select(
                func.count(Task.id),
                func.count(Task.id).filter(
                    Task.execution_status == ExecutionStatus.RUNNING
                ),
                func.count(Task.id).filter(
                    Task.execution_status == ExecutionStatus.QUEUED
                ),
                func.count(Task.id).filter(
                    Task.execution_status == ExecutionStatus.RESULT_READY,
                    Task.verdict == Verdict.PASS,
                ),
                func.count(Task.id).filter(
                    Task.execution_status == ExecutionStatus.RESULT_READY,
                    Task.verdict.in_((Verdict.PASS, Verdict.FAIL)),
                ),
                func.count(Task.id).filter(Task.review_result == Verdict.FAIL),
                func.count(Task.id).filter(
                    Task.review_result.in_((Verdict.PASS, Verdict.FAIL)),
                ),
            )
            .where(*filters)
        ).one()
        pass_rate = round((passed / completed) * 100) if completed else 0
        manual_review_fail_rate = (
            round((manual_review_failed / manual_review_total) * 100)
            if manual_review_total
            else 0
        )
        return {
            "total": total,
            "running": running,
            "queued": queued,
            "pass_rate": pass_rate,
            "manual_review_fail_count": manual_review_failed,
            "manual_review_total": manual_review_total,
            "manual_review_fail_rate": manual_review_fail_rate,
        }

    def review_task(
        self,
        task_id: str,
        *,
        review_result: Verdict,
        reviewed_by: str,
        reviewed_at: datetime,
        review_note: str | None = None,
    ) -> Task:
        task = self._required(task_id)
        if task.execution_status != ExecutionStatus.RESULT_READY:
            raise ValueError(f"task_not_reviewable:{task_id}")
        task.review_result = review_result
        task.reviewed_by = reviewed_by
        task.reviewed_at = reviewed_at
        task.review_note = review_note.strip() if review_note and review_note.strip() else None
        task.version += 1
        self.db.commit()
        return task

    def list_operators(self, business_id: str | None = None) -> list[str]:
        filters = [Task.business_id == business_id] if business_id else []
        creators = self.db.scalars(
            select(Task.created_by)
            .where(Task.created_by.is_not(None), Task.created_by != "", *filters)
            .distinct()
        ).all()
        reviewers = self.db.scalars(
            select(Task.reviewed_by)
            .where(Task.reviewed_by.is_not(None), Task.reviewed_by != "", *filters)
            .distinct()
        ).all()
        return sorted(
            operator
            for operator in set(creators + reviewers)
            if isinstance(operator, str)
        )

    def get_case(self, case_id: str) -> TestCase | None:
        return self.db.get(TestCase, case_id)

    def _required(self, task_id: str) -> Task:
        task = self.get(task_id)
        if task is None:
            raise ValueError(f"task_not_found:{task_id}")
        return task

    def _reload(self, task_id: str) -> Task:
        self.db.expire_all()
        return self._required(task_id)

    def _next_event_sequence(self, task_id: str) -> int:
        return self.last_event_sequence(task_id) + 1

    def _release_lease(
        self,
        task_id: str,
        worker_id: str | None,
        reason: str,
    ) -> _ReleasedLease | None:
        lease = self.db.scalar(
            select(PodLease).where(PodLease.task_id == task_id)
        )
        if lease is None or (
            worker_id is not None and lease.worker_id != worker_id
        ):
            return None
        released = _ReleasedLease(
            task_id=task_id,
            resource_key=lease.pod_id,
            worker_id=lease.worker_id,
            lease_version=lease.version,
            reason=reason,
        )
        statement = delete(PodLease).where(PodLease.task_id == task_id)
        if worker_id is not None:
            statement = statement.where(PodLease.worker_id == worker_id)
        if self.db.execute(statement).rowcount != 1:
            return None
        return released

    def _log_release_result(
        self,
        task_id: str,
        worker_id: str | None,
        reason: str,
        released: _ReleasedLease | None,
    ) -> None:
        if released is not None:
            self._log_released(released)
            return
        _log(
            logging.DEBUG,
            "pod_lease_release_missed",
            task_id=task_id,
            worker_id=worker_id,
            reason=reason,
        )

    @staticmethod
    def _log_released(released: _ReleasedLease) -> None:
        _log(
            logging.INFO,
            "pod_lease_released",
            task_id=released.task_id,
            resource_key=released.resource_key,
            worker_id=released.worker_id,
            lease_version=released.lease_version,
            reason=released.reason,
        )


def _canonical_json(value: Any) -> str:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("request_fingerprint_must_be_json") from exc
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("request_fingerprint_must_be_json") from exc


def _validate_release_reason(reason: str) -> None:
    if reason not in RELEASE_REASONS:
        raise ValueError("lease_release_reason_invalid")


def _lease_resource_keys(snapshot: dict[str, Any]) -> tuple[str, ...]:
    pod_id = snapshot.get("pod_id") if isinstance(snapshot, dict) else None
    if not isinstance(pod_id, str) or not pod_id:
        raise ValueError("runner_snapshot_invalid")
    product_id = snapshot.get("product_id") if isinstance(snapshot, dict) else None
    if isinstance(product_id, str) and product_id:
        return (pod_id, f"{product_id}:{pod_id}")
    return (pod_id,)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _utc_naive(value: datetime) -> datetime:
    return _as_utc(value).replace(tzinfo=None)
