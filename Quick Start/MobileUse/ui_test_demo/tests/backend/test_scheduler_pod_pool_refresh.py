from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from mua_platform.business.models import BusinessSpace
from mua_platform.business.service import business_name_key
from mua_platform.cases.models import TestCase as CaseModel
from mua_platform.db import Base
from mua_platform.pods.models import PodPoolRefresh
from mua_platform.tasks.models import Task, TaskBatch
from mua_platform.tasks.pod_pool_refresh import SchedulerPodPoolRefresher
from mua_platform.tasks.state_machine import ExecutionStatus


def _session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)


def _seed_batch(
    factory,
    *,
    batch_id: str = "batch-refresh",
    unavailable_since: datetime | None = None,
    wait_seconds: int = 300,
) -> None:
    with factory() as db:
        business = BusinessSpace(
            id="biz-refresh",
            name="刷新业务",
            name_key=business_name_key("刷新业务"),
            is_default=False,
            task_concurrency_limit=4,
            created_by="system",
        )
        case = CaseModel(
            id=f"case-{batch_id}",
            business_id=business.id,
            title="刷新用例",
            module="调度",
            content_markdown="- 执行",
            tags=[],
            automation_level="auto",
            created_by="admin",
        )
        batch = TaskBatch(
            id=batch_id,
            business_id=business.id,
            name="刷新批次",
            test_type="regression",
            selection_mode="multi_cases",
            selection_snapshot={},
            device_strategy="specified",
            pod_ids=["pod-refresh"],
            concurrency=1,
            device_wait_timeout_seconds=wait_seconds,
            runner_type="mobile_use",
            config_snapshot={"product_id": "product-refresh"},
            execution_status=ExecutionStatus.QUEUED,
            idempotency_key=f"key-{batch_id}",
            request_fingerprint="{}",
            created_by="admin",
            unavailable_since=unavailable_since,
        )
        task = Task(
            id=f"task-{batch_id}",
            business_id=business.id,
            case_id=case.id,
            batch_id=batch.id,
            batch_position=0,
            queue_reason="waiting_for_specified_device",
            runner_type="mobile_use",
            scenario=case.title,
            created_by="admin",
            execution_status=ExecutionStatus.QUEUED,
            idempotency_key=f"task-key-{batch_id}",
            request_fingerprint="{}",
            version=1,
        )
        db.add_all([business, case])
        batch.tasks.append(task)
        db.add(batch)
        db.commit()


@pytest.mark.asyncio
async def test_refreshes_due_target_and_throttles_recent_success():
    engine, factory = _session_factory()
    now = datetime(2026, 8, 17, 8, 0, tzinfo=UTC)
    _seed_batch(factory)
    calls: list[tuple[str, str]] = []

    async def refresh(business_id: str, product_id: str) -> None:
        calls.append((business_id, product_id))
        with factory() as db:
            db.add(
                PodPoolRefresh(
                    product_id=product_id,
                    refreshed_at=now,
                )
            )
            db.commit()

    try:
        refresher = SchedulerPodPoolRefresher(factory, refresh)

        assert await refresher.refresh_due(now) == set()
        assert calls == [("biz-refresh", "product-refresh")]
        assert await refresher.refresh_due(now + timedelta(seconds=30)) == set()
        assert calls == [("biz-refresh", "product-refresh")]
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_failed_refresh_blocks_batches_and_retries_after_backoff():
    engine, factory = _session_factory()
    now = datetime(2026, 8, 17, 8, 0, tzinfo=UTC)
    _seed_batch(factory)
    calls = 0

    async def refresh(_business_id: str, _product_id: str) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("refresh failed")

    try:
        refresher = SchedulerPodPoolRefresher(factory, refresh)

        assert await refresher.refresh_due(now) == {"batch-refresh"}
        assert calls == 1
        assert await refresher.refresh_due(
            now + timedelta(seconds=10)
        ) == {"batch-refresh"}
        assert calls == 1
        assert await refresher.refresh_due(
            now + timedelta(seconds=16)
        ) == {"batch-refresh"}
        assert calls == 2
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_successful_retry_clears_refresh_failure_timer():
    engine, factory = _session_factory()
    now = datetime(2026, 8, 17, 8, 0, tzinfo=UTC)
    _seed_batch(factory)
    should_fail = True

    async def refresh(_business_id: str, _product_id: str) -> None:
        if should_fail:
            raise RuntimeError("refresh failed")

    try:
        refresher = SchedulerPodPoolRefresher(factory, refresh)
        assert await refresher.refresh_due(now) == {"batch-refresh"}

        should_fail = False
        assert await refresher.refresh_due(
            now + timedelta(seconds=16)
        ) == set()

        with factory() as db:
            batch = db.get(TaskBatch, "batch-refresh")
            assert batch is not None
            assert batch.unavailable_since is None
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_continuous_refresh_failure_finishes_as_discovery_failure():
    engine, factory = _session_factory()
    now = datetime(2026, 8, 17, 8, 0, tzinfo=UTC)
    _seed_batch(factory, wait_seconds=30)

    async def refresh(_business_id: str, _product_id: str) -> None:
        raise RuntimeError("refresh failed")

    try:
        refresher = SchedulerPodPoolRefresher(factory, refresh)

        assert await refresher.refresh_due(now) == {"batch-refresh"}
        assert await refresher.refresh_due(
            now + timedelta(seconds=31)
        ) == set()

        with factory() as db:
            batch = db.get(TaskBatch, "batch-refresh")
            assert batch is not None
            assert batch.execution_status == ExecutionStatus.RESULT_READY
            assert {
                task.failure_type for task in batch.tasks
            } == {"pod_pool_discovery_failed"}
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_forces_refresh_before_device_unavailable_timeout():
    engine, factory = _session_factory()
    now = datetime(2026, 8, 17, 8, 0, tzinfo=UTC)
    _seed_batch(
        factory,
        unavailable_since=now - timedelta(seconds=300),
        wait_seconds=300,
    )
    with factory() as db:
        db.add(
            PodPoolRefresh(
                product_id="product-refresh",
                refreshed_at=now - timedelta(seconds=10),
            )
        )
        db.commit()
    calls: list[tuple[str, str]] = []

    async def refresh(business_id: str, product_id: str) -> None:
        calls.append((business_id, product_id))

    try:
        refresher = SchedulerPodPoolRefresher(factory, refresh)

        assert await refresher.refresh_due(now) == set()
        assert calls == [("biz-refresh", "product-refresh")]
    finally:
        engine.dispose()
