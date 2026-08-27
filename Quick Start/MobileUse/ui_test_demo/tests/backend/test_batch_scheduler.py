from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from mua_platform.business.models import BusinessSpace
from mua_platform.business.service import business_name_key
from mua_platform.cases.models import TestCase as CaseModel
from mua_platform.db import Base
from mua_platform.pods.models import DiscoveredPod
from mua_platform.tasks.models import PodLease, Task, TaskBatch, TaskRunnerConfig
from mua_platform.tasks.repository import SQLiteTaskRepository
from mua_platform.tasks.scheduler import BatchScheduler
from mua_platform.tasks.state_machine import ExecutionStatus, Verdict


def _seed_batch(
    db: Session,
    *,
    strategy: str,
    pod_ids: list[str],
    concurrency: int,
    task_count: int = 3,
    batch_id: str | None = None,
    business_id: str = "biz_default",
    product_id: str = "product-1",
    business_limit: int = 4,
) -> TaskBatch:
    suffix = batch_id or strategy
    if db.get(BusinessSpace, business_id) is None:
        business = BusinessSpace(
            id=business_id,
            name=business_id,
            name_key=business_name_key(business_id),
            is_default=business_id == "biz_default",
            task_concurrency_limit=business_limit,
            created_by="system",
        )
        db.add(business)
    batch = TaskBatch(
        id=f"batch_{suffix}",
        business_id=business_id,
        name="调度测试",
        test_type="regression",
        selection_mode="multi_cases",
        selection_snapshot={},
        device_strategy=strategy,
        pod_ids=pod_ids,
        concurrency=concurrency,
        device_wait_timeout_seconds=300,
        runner_type="mobile_use",
        config_snapshot={"product_id": product_id},
        execution_status=ExecutionStatus.QUEUED,
        idempotency_key=f"key-{suffix}",
        request_fingerprint="{}",
        created_by="admin",
    )
    for index in range(task_count):
        case = CaseModel(
            id=f"case_{suffix}_{index}",
            business_id=business_id,
            title=f"用例 {index}",
            module="调度",
            content_markdown="- 执行",
            tags=[],
            automation_level="auto",
            created_by="admin",
        )
        task = Task(
            id=f"task_{suffix}_{index}",
            business_id=business_id,
            case_id=case.id,
            batch_id=batch.id,
            batch_position=index,
            queue_reason="waiting_for_any_device",
            runner_type="mobile_use",
            scenario=case.title,
            created_by="admin",
            execution_status=ExecutionStatus.QUEUED,
            idempotency_key=f"task-key-{suffix}-{index}",
            request_fingerprint="{}",
            version=1,
        )
        task.runner_config = TaskRunnerConfig(
            config_snapshot={"product_id": product_id}
        )
        db.add(case)
        batch.tasks.append(task)
    db.add(batch)
    db.commit()
    return batch


def _seed_pod(
    db: Session,
    pod_id: str,
    now: datetime,
    *,
    status: int = 1,
    discovery_state: str = "active",
    product_id: str = "product-1",
) -> DiscoveredPod:
    pod = DiscoveredPod(
        id=f"row_{product_id}_{pod_id}",
        product_id=product_id,
        pod_id=pod_id,
        pod_name=pod_id,
        pod_status_code=status,
        discovery_state=discovery_state,
        last_seen_at=now,
    )
    db.add(pod)
    db.commit()
    return pod


def _schedule(
    db: Session,
    now: datetime,
    *,
    global_limit: int = 16,
    start_after_business_id: str | None = None,
    blocked_batch_ids: set[str] | None = None,
) -> list[str]:
    return BatchScheduler(db).schedule(
        now,
        global_limit=global_limit,
        start_after_business_id=start_after_business_id,
        blocked_batch_ids=blocked_batch_ids,
    ).task_ids


def test_automatic_scheduler_reserves_only_batch_concurrency():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)
    try:
        with Session(engine, expire_on_commit=False) as db:
            batch = _seed_batch(
                db,
                strategy="automatic",
                pod_ids=[],
                concurrency=2,
            )
            _seed_pod(db, "pod-a", now)
            _seed_pod(db, "pod-b", now)
            _seed_pod(db, "pod-c", now)

            assigned = _schedule(db, now)

            assert len(assigned) == 2
            leases = list(db.scalars(select(PodLease)))
            assert len(leases) == 2
            assert {lease.task_id for lease in leases} == set(assigned)
            remaining = next(task for task in batch.tasks if task.id not in assigned)
            assert remaining.queue_reason == "waiting_for_batch_capacity"
    finally:
        engine.dispose()


def test_scheduler_limits_single_business_to_configured_concurrency():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)
    try:
        with Session(engine, expire_on_commit=False) as db:
            _seed_batch(
                db,
                strategy="automatic",
                pod_ids=[],
                concurrency=8,
                task_count=6,
            )
            for index in range(6):
                _seed_pod(db, f"pod-{index}", now)

            assigned = _schedule(db, now)

            assert len(assigned) == 4
    finally:
        engine.dispose()


def test_scheduler_round_robins_businesses_within_global_capacity():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)
    try:
        with Session(engine, expire_on_commit=False) as db:
            first = _seed_batch(
                db,
                strategy="automatic",
                pod_ids=[],
                concurrency=4,
                task_count=4,
                batch_id="first",
                business_id="biz_first",
                product_id="product-first",
            )
            second = _seed_batch(
                db,
                strategy="automatic",
                pod_ids=[],
                concurrency=4,
                task_count=4,
                batch_id="second",
                business_id="biz_second",
                product_id="product-second",
            )
            for index in range(4):
                _seed_pod(
                    db,
                    f"first-{index}",
                    now,
                    product_id="product-first",
                )
                _seed_pod(
                    db,
                    f"second-{index}",
                    now,
                    product_id="product-second",
                )

            result = BatchScheduler(db).schedule(now, global_limit=4)

            assert len(result.task_ids) == 4
            assigned = set(result.task_ids)
            assert len(assigned & {task.id for task in first.tasks}) == 2
            assert len(assigned & {task.id for task in second.tasks}) == 2
            assert result.last_business_id == "biz_second"
    finally:
        engine.dispose()


def test_scheduler_counts_existing_leases_against_global_capacity():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)
    try:
        with Session(engine, expire_on_commit=False) as db:
            batch = _seed_batch(
                db,
                strategy="automatic",
                pod_ids=[],
                concurrency=4,
                task_count=4,
            )
            for index in range(4):
                _seed_pod(db, f"pod-{index}", now)
            leased_task = batch.tasks[0]
            db.add(
                PodLease(
                    pod_id="product-1:pod-0",
                    task_id=leased_task.id,
                    worker_id="worker:test",
                    expires_at=now + timedelta(minutes=5),
                    version=1,
                )
            )
            db.commit()

            assigned = _schedule(db, now, global_limit=2)

            assert len(assigned) == 1
            assert assigned[0] != leased_task.id
    finally:
        engine.dispose()


def test_released_capacity_assigns_next_batch_child():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)
    try:
        with Session(engine, expire_on_commit=False) as db:
            batch = _seed_batch(
                db,
                strategy="automatic",
                pod_ids=[],
                concurrency=2,
            )
            _seed_pod(db, "pod-a", now)
            _seed_pod(db, "pod-b", now)

            first_wave = _schedule(db, now)
            assert len(first_wave) == 2
            completed_id = first_wave[0]
            repository = SQLiteTaskRepository(db)
            repository.finish(
                completed_id,
                ExecutionStatus.RESULT_READY,
                Verdict.PASS,
                None,
            )
            assert repository.release_lease(
                completed_id,
                reason="terminal",
            )

            second_wave = _schedule(
                db,
                now + timedelta(seconds=1)
            )

            remaining_id = next(
                task.id
                for task in batch.tasks
                if task.id not in first_wave
            )
            assert second_wave == [remaining_id]
            active_task_ids = set(db.scalars(select(PodLease.task_id)))
            assert active_task_ids == {first_wave[1], remaining_id}
    finally:
        engine.dispose()


def test_specified_busy_pod_waits_without_unavailable_timer():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)
    try:
        with Session(engine, expire_on_commit=False) as db:
            batch = _seed_batch(
                db,
                strategy="specified",
                pod_ids=["pod-a"],
                concurrency=1,
                task_count=1,
            )
            _seed_pod(db, "pod-a", now)
            other_case = CaseModel(
                id="case_other",
                title="其他任务",
                module=None,
                content_markdown="- 执行",
                tags=[],
                automation_level="auto",
                created_by="admin",
            )
            other = Task(
                id="task_other",
                case_id=other_case.id,
                runner_type="mobile_use",
                scenario="其他任务",
                created_by="admin",
                execution_status=ExecutionStatus.RUNNING,
                idempotency_key="other",
                request_fingerprint="{}",
                version=1,
            )
            db.add_all(
                [
                    other_case,
                    other,
                    PodLease(
                        pod_id="product-1:pod-a",
                        task_id=other.id,
                        worker_id="worker:other",
                        expires_at=now + timedelta(minutes=5),
                        version=1,
                    ),
                ]
            )
            db.commit()

            assert _schedule(db, now) == []
            db.refresh(batch)
            db.refresh(batch.tasks[0])
            assert batch.unavailable_since is None
            assert batch.tasks[0].queue_reason == "waiting_for_specified_device"
    finally:
        engine.dispose()


def test_partial_specified_unavailability_uses_remaining_pod():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)
    try:
        with Session(engine, expire_on_commit=False) as db:
            batch = _seed_batch(
                db,
                strategy="specified",
                pod_ids=["pod-offline", "pod-online"],
                concurrency=2,
                task_count=2,
            )
            _seed_pod(db, "pod-offline", now, status=2)
            _seed_pod(db, "pod-online", now)

            assigned = _schedule(db, now)

            assert len(assigned) == 1
            lease = db.scalar(select(PodLease))
            assert lease is not None
            assert lease.pod_id == "product-1:pod-online"
            db.refresh(batch)
            assert batch.unavailable_since is None
    finally:
        engine.dispose()


def test_all_specified_pods_unavailable_fail_queued_children_after_timeout():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)
    try:
        with Session(engine, expire_on_commit=False) as db:
            batch = _seed_batch(
                db,
                strategy="specified",
                pod_ids=["pod-offline"],
                concurrency=1,
                task_count=2,
            )
            _seed_pod(db, "pod-offline", now, status=2)

            assert _schedule(db, now) == []
            db.refresh(batch)
            assert batch.unavailable_since is not None
            assert {task.queue_reason for task in batch.tasks} == {
                "device_temporarily_unavailable"
            }

            assert _schedule(db, now + timedelta(seconds=301)) == []
            for task in batch.tasks:
                db.refresh(task)
                assert task.execution_status == ExecutionStatus.RESULT_READY
                assert task.verdict == Verdict.FAIL
                assert task.failure_type == "device_unavailable"
    finally:
        engine.dispose()


def test_stale_by_last_seen_starts_specified_unavailable_timer():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)
    try:
        with Session(engine, expire_on_commit=False) as db:
            batch = _seed_batch(
                db,
                strategy="specified",
                pod_ids=["pod-stale"],
                concurrency=1,
                task_count=1,
            )
            _seed_pod(db, "pod-stale", now - timedelta(minutes=4))

            assert _schedule(db, now) == []

            db.refresh(batch)
            db.refresh(batch.tasks[0])
            assert batch.unavailable_since is not None
            assert (
                batch.tasks[0].queue_reason
                == "device_temporarily_unavailable"
            )
    finally:
        engine.dispose()


def test_refresh_blocked_batch_does_not_advance_device_unavailable_timer():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)
    try:
        with Session(engine, expire_on_commit=False) as db:
            batch = _seed_batch(
                db,
                strategy="specified",
                pod_ids=["pod-stale"],
                concurrency=1,
                task_count=1,
            )
            original_unavailable_since = now - timedelta(minutes=10)
            batch.unavailable_since = original_unavailable_since
            db.commit()

            assert _schedule(
                db,
                now,
                blocked_batch_ids={batch.id},
            ) == []

            db.refresh(batch)
            db.refresh(batch.tasks[0])
            assert batch.unavailable_since is not None
            assert batch.unavailable_since.replace(
                tzinfo=UTC
            ) == original_unavailable_since
            assert batch.tasks[0].execution_status == ExecutionStatus.QUEUED
            assert (
                batch.tasks[0].queue_reason
                == "waiting_for_pod_pool_refresh"
            )
    finally:
        engine.dispose()


def test_cancelled_batch_converges_after_last_running_child_finishes():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)
    try:
        with Session(engine, expire_on_commit=False) as db:
            batch = _seed_batch(
                db,
                strategy="automatic",
                pod_ids=[],
                concurrency=2,
                task_count=2,
            )
            batch.cancel_requested_at = now
            batch.execution_status = ExecutionStatus.RUNNING
            batch.tasks[0].execution_status = ExecutionStatus.RUNNING
            batch.tasks[1].execution_status = ExecutionStatus.CANCELLED
            db.commit()

            assert _schedule(db, now) == []
            db.refresh(batch)
            assert batch.execution_status == ExecutionStatus.RUNNING

            batch.tasks[0].execution_status = ExecutionStatus.CANCELLED
            db.commit()
            assert _schedule(
                db,
                now + timedelta(seconds=1)
            ) == []
            db.refresh(batch)
            assert batch.execution_status == ExecutionStatus.CANCELLED
            assert batch.verdict is None
    finally:
        engine.dispose()
