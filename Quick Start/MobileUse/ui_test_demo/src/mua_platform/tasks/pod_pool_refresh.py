from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from mua_platform.pods.models import PodPoolRefresh
from mua_platform.tasks.batches import aggregate_batch_status
from mua_platform.tasks.models import TaskBatch
from mua_platform.tasks.repository import SQLiteTaskRepository
from mua_platform.tasks.state_machine import ExecutionStatus


logger = logging.getLogger(__name__)

RefreshProduct = Callable[[str, str], Awaitable[None]]
SessionFactory = Callable[[], Session]


@dataclass(frozen=True)
class _RefreshTarget:
    business_id: str
    product_id: str
    batch_ids: frozenset[str]
    refreshed_at: datetime | None
    force: bool


class SchedulerPodPoolRefresher:
    def __init__(
        self,
        session_factory: SessionFactory,
        refresh_product: RefreshProduct,
        *,
        refresh_interval: timedelta = timedelta(seconds=60),
        failure_retry_interval: timedelta = timedelta(seconds=15),
    ) -> None:
        self.session_factory = session_factory
        self.refresh_product = refresh_product
        self.refresh_interval = refresh_interval
        self.failure_retry_interval = failure_retry_interval
        self._retry_after: dict[tuple[str, str], datetime] = {}
        self._lock = asyncio.Lock()

    async def refresh_due(self, now: datetime) -> set[str]:
        async with self._lock:
            return await self._refresh_due_locked(now)

    async def _refresh_due_locked(self, now: datetime) -> set[str]:
        blocked: set[str] = set()
        for target in self._targets(now):
            if not self._due(target, now):
                continue
            key = (target.business_id, target.product_id)
            retry_after = self._retry_after.get(key)
            if retry_after is not None and now < retry_after:
                blocked.update(self._record_failure(target, now))
                continue
            try:
                await self.refresh_product(
                    target.business_id,
                    target.product_id,
                )
            except Exception:
                logger.exception(
                    "scheduler_pod_pool_refresh_failed",
                    extra={
                        "business_id": target.business_id,
                        "product_id": target.product_id,
                        "batch_ids": sorted(target.batch_ids),
                    },
                )
                self._retry_after[key] = now + self.failure_retry_interval
                blocked.update(self._record_failure(target, now))
            else:
                self._retry_after.pop(key, None)
                self._clear_failure(target)
        return blocked

    def _targets(self, now: datetime) -> list[_RefreshTarget]:
        with self.session_factory() as db:
            batches = list(
                db.scalars(
                    select(TaskBatch)
                    .options(selectinload(TaskBatch.tasks))
                    .where(
                        TaskBatch.execution_status.in_(
                            [
                                ExecutionStatus.QUEUED,
                                ExecutionStatus.RUNNING,
                            ]
                        )
                    )
                    .order_by(TaskBatch.created_at, TaskBatch.id)
                )
            )
            grouped: dict[tuple[str, str], list[TaskBatch]] = defaultdict(list)
            for batch in batches:
                if batch.cancel_requested_at is not None:
                    continue
                if not any(
                    task.execution_status == ExecutionStatus.QUEUED
                    for task in batch.tasks
                ):
                    continue
                product_id = batch.config_snapshot.get("product_id")
                if not isinstance(product_id, str) or not product_id:
                    continue
                grouped[(batch.business_id, product_id)].append(batch)

            product_ids = {product_id for _, product_id in grouped}
            refreshed_by_product = {
                row.product_id: row.refreshed_at
                for row in db.scalars(
                    select(PodPoolRefresh).where(
                        PodPoolRefresh.product_id.in_(product_ids)
                    )
                )
            } if product_ids else {}

            return [
                _RefreshTarget(
                    business_id=business_id,
                    product_id=product_id,
                    batch_ids=frozenset(batch.id for batch in target_batches),
                    refreshed_at=refreshed_by_product.get(product_id),
                    force=any(
                        (
                            batch.unavailable_since is not None
                            and now - _aware(batch.unavailable_since)
                            >= timedelta(
                                seconds=batch.device_wait_timeout_seconds
                            )
                        )
                        or any(
                            task.execution_status == ExecutionStatus.QUEUED
                            and task.queue_reason
                            == "waiting_for_pod_pool_refresh"
                            for task in batch.tasks
                        )
                        for batch in target_batches
                    ),
                )
                for (business_id, product_id), target_batches in grouped.items()
            ]

    def _due(self, target: _RefreshTarget, now: datetime) -> bool:
        if target.force or target.refreshed_at is None:
            return True
        return now - _aware(target.refreshed_at) >= self.refresh_interval

    def _record_failure(
        self,
        target: _RefreshTarget,
        now: datetime,
    ) -> set[str]:
        blocked: set[str] = set()
        with self.session_factory() as db:
            batches = list(
                db.scalars(
                    select(TaskBatch)
                    .options(selectinload(TaskBatch.tasks))
                    .where(TaskBatch.id.in_(target.batch_ids))
                )
            )
            expired: list[tuple[TaskBatch, list[str]]] = []
            for batch in batches:
                queued = [
                    task
                    for task in batch.tasks
                    if task.execution_status == ExecutionStatus.QUEUED
                ]
                if not queued:
                    continue
                if batch.unavailable_since is None:
                    batch.unavailable_since = now
                for task in queued:
                    task.queue_reason = "waiting_for_pod_pool_refresh"
                if now - _aware(batch.unavailable_since) >= timedelta(
                    seconds=batch.device_wait_timeout_seconds
                ):
                    expired.append((batch, [task.id for task in queued]))
                else:
                    blocked.add(batch.id)
            db.commit()

            repository = SQLiteTaskRepository(db)
            for batch, task_ids in expired:
                for task_id in task_ids:
                    repository.finalize_queued_failure(
                        task_id,
                        "pod_pool_discovery_failed",
                    )
                db.refresh(batch)
                aggregate_batch_status(batch, now)
                db.commit()
        return blocked

    def _clear_failure(self, target: _RefreshTarget) -> None:
        with self.session_factory() as db:
            batches = list(
                db.scalars(
                    select(TaskBatch)
                    .options(selectinload(TaskBatch.tasks))
                    .where(TaskBatch.id.in_(target.batch_ids))
                )
            )
            changed = False
            for batch in batches:
                if not any(
                    task.execution_status == ExecutionStatus.QUEUED
                    and task.queue_reason == "waiting_for_pod_pool_refresh"
                    for task in batch.tasks
                ):
                    continue
                batch.unavailable_since = None
                changed = True
            if changed:
                db.commit()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
