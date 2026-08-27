import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from cua_platform.cases.models import TestCase as CaseModel
from cua_platform.db import Base
from cua_platform.runners.base import (
    CancelResult,
    PollResult,
    RunHandle,
    RunnerEvent,
    RunnerFailure,
)
from cua_platform.tasks.models import (
    PodLease,
    Task,
    TaskBatch,
    TaskEvent,
    TaskRunnerConfig,
)
from cua_platform.tasks.pod_pool_refresh import SchedulerPodPoolRefresher
from cua_platform.tasks.repository import SQLiteTaskRepository
from cua_platform.tasks.scheduler import BatchScheduler
from cua_platform.tasks.service import TaskService
from cua_platform.tasks.state_machine import ExecutionStatus, StartState, Verdict
from cua_platform.tasks.worker import WorkerFailureDisposition
from cua_platform.time import FakeClock
from cua_platform.traces.repository import TraceRepository


class CountingRunner:
    def __init__(self):
        self.start_calls = 0

    async def start(self, request, idempotency_key):
        self.start_calls += 1
        return RunHandle(request.task_id, "mock", f"run:{request.task_id}")

    async def poll(self, handle, after_sequence):
        return PollResult(
            events=(
                RunnerEvent(1, "task_started", {"task_id": handle.task_id}),
                RunnerEvent(
                    2,
                    "task_finished",
                    {"verdict": "pass", "evidence_complete": True},
                ),
            ),
            terminal=True,
        )


class AwaitingStartRunner:
    def __init__(self):
        self.start_calls = 0
        self.start_waiting = asyncio.Event()
        self.finish_start = asyncio.Event()

    async def start(self, request, idempotency_key):
        self.start_calls += 1
        self.start_waiting.set()
        await self.finish_start.wait()
        return RunHandle(request.task_id, "mock", f"run:{request.task_id}")

    async def cancel(self, handle):
        return CancelResult(accepted=True, terminal=True)


class FailingStartRunner:
    def __init__(self, error: Exception):
        self.error = error

    async def start(self, request, idempotency_key):
        raise self.error


class TerminalCancelRunner:
    def __init__(self):
        self.cancelled_run_ids = []

    async def cancel(self, handle):
        self.cancelled_run_ids.append(handle.run_id)
        return CancelResult(accepted=True, terminal=True)

    async def poll(self, handle, after_sequence):
        raise AssertionError("terminal cancel must not poll again")


@pytest.fixture
def task_repository():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        yield SQLiteTaskRepository(db)
    engine.dispose()


def seed_running_task(
    db,
    *,
    start_state: StartState,
    remote_run_id: str | None,
    cancel_requested_at: datetime | None = None,
    batch_id: str | None = None,
    with_lease: bool = True,
) -> str:
    suffix = uuid4().hex
    now = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)
    case = CaseModel(
        id=f"case_{suffix}",
        title="恢复任务",
        module=None,
        content_markdown="## 执行任务\n验证恢复",
        tags=[],
        automation_level="auto",
        created_by="admin",
    )
    task = Task(
        id=f"task_{suffix}",
        case_id=case.id,
        batch_id=batch_id,
        batch_position=0 if batch_id is not None else None,
        prompt_snapshot=case.content_markdown,
        runner_type="mock",
        scenario="success",
        created_by="admin",
        execution_status=ExecutionStatus.RUNNING,
        idempotency_key=f"recover-{suffix}",
        request_fingerprint="{}",
        start_idempotency_key=f"start:task_{suffix}",
        start_state=start_state,
        start_attempted_at=now,
        remote_run_id=remote_run_id,
        cancel_requested_at=cancel_requested_at,
        version=1,
    )
    config = TaskRunnerConfig(
        task_id=task.id,
        config_snapshot={"pod_id": f"pod_{suffix}"},
    )
    lease = PodLease(
        pod_id=f"pod_{suffix}",
        task_id=task.id,
        worker_id="worker:old",
        expires_at=now - timedelta(seconds=1),
        version=1,
    )
    rows = [case, task, config]
    if batch_id is not None:
        rows.append(
            TaskBatch(
                id=batch_id,
                name="恢复批次",
                test_type="regression",
                selection_mode="multi_cases",
                selection_snapshot={},
                device_strategy="automatic",
                pod_ids=[],
                concurrency=1,
                runner_type="mock",
                config_snapshot={},
                execution_status=ExecutionStatus.QUEUED,
                idempotency_key=f"batch-{suffix}",
                request_fingerprint="{}",
                created_by="admin",
            )
        )
    if with_lease:
        rows.append(lease)
    db.add_all(rows)
    db.commit()
    return task.id


@pytest.fixture
def running_task(task_repository):
    now = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)
    case = CaseModel(
        id="case_start_guard",
        title="提交保护",
        module=None,
        content_markdown="## 执行任务\n验证提交保护",
        tags=[],
        automation_level="auto",
        created_by="admin",
    )
    task = Task(
        id="task_start_guard",
        case_id=case.id,
        prompt_snapshot=case.content_markdown,
        runner_type="mock",
        scenario="success",
        created_by="admin",
        execution_status=ExecutionStatus.RUNNING,
        idempotency_key="start-guard",
        request_fingerprint="{}",
        start_idempotency_key="start:task_start_guard",
        start_state=StartState.PENDING,
        version=1,
    )
    config = TaskRunnerConfig(
        task_id=task.id,
        config_snapshot={"pod_id": "mock:default"},
    )
    lease = PodLease(
        pod_id="mock:default",
        task_id=task.id,
        worker_id="worker:test",
        expires_at=now + timedelta(seconds=30),
        version=1,
    )
    task_repository.db.add_all([case, task, config, lease])
    task_repository.db.commit()
    return task


@pytest.fixture
def queued_task(task_repository, running_task):
    running_task.execution_status = ExecutionStatus.QUEUED
    running_task.started_at = None
    lease = task_repository.db.scalar(
        select(PodLease).where(PodLease.task_id == running_task.id)
    )
    assert lease is not None
    lease.worker_id = "reserved"
    task_repository.db.commit()
    return running_task


def test_remote_start_can_be_dispatched_only_once(task_repository, running_task):
    now = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)

    first = task_repository.mark_start_dispatching(running_task.id, now)
    second = task_repository.mark_start_dispatching(running_task.id, now)

    assert first is not None
    assert first.start_state == StartState.DISPATCHING
    assert first.start_attempted_at is not None
    assert first.start_attempted_at.replace(tzinfo=UTC) == now
    assert second is None


def test_run_handle_can_only_attach_to_dispatching_task(
    task_repository,
    running_task,
):
    handle = RunHandle(running_task.id, "mock", "run-once", "thread-once")

    with pytest.raises(ValueError, match="task_start_not_dispatching"):
        task_repository.save_run_handle(running_task.id, handle)

    task_repository.mark_start_dispatching(
        running_task.id,
        datetime(2026, 8, 24, 9, 0, tzinfo=UTC),
    )
    attached = task_repository.save_run_handle(running_task.id, handle)

    assert attached.start_state == StartState.ATTACHED
    assert attached.remote_run_id == "run-once"
    assert attached.remote_thread_id == "thread-once"

    with pytest.raises(ValueError, match="task_start_not_dispatching"):
        task_repository.save_run_handle(
            running_task.id,
            RunHandle(running_task.id, "mock", "run-replacement"),
        )
    assert task_repository.refresh(running_task.id).remote_run_id == "run-once"


def test_run_handle_cannot_attach_to_non_running_task(
    task_repository,
    running_task,
):
    task_repository.mark_start_dispatching(
        running_task.id,
        datetime(2026, 8, 24, 9, 0, tzinfo=UTC),
    )
    running_task.execution_status = ExecutionStatus.RESULT_READY
    task_repository.db.commit()

    with pytest.raises(ValueError, match="task_start_not_dispatching"):
        task_repository.save_run_handle(
            running_task.id,
            RunHandle(running_task.id, "mock", "run-ineligible"),
        )

    assert task_repository.refresh(running_task.id).remote_run_id is None


def test_start_state_repair_requires_run_handle(task_repository, running_task):
    with pytest.raises(ValueError, match="task_run_handle_missing"):
        task_repository.repair_start_attached(running_task.id)


def test_start_state_repair_marks_task_with_run_handle_attached(
    task_repository,
    running_task,
):
    running_task.remote_run_id = "run-existing"
    task_repository.db.commit()

    repaired = task_repository.repair_start_attached(running_task.id)

    assert repaired.start_state == StartState.ATTACHED
    assert repaired.version == 2


@pytest.mark.asyncio
async def test_task_service_marks_dispatching_before_remote_start(
    task_repository,
    queued_task,
):
    runner = CountingRunner()
    seen_states = []
    original_start = runner.start

    async def start(request, idempotency_key):
        seen_states.append(task_repository.refresh(request.task_id).start_state)
        return await original_start(request, idempotency_key)

    runner.start = start
    completed = await TaskService(task_repository, runner).run_task(
        queued_task.id,
        "worker:test",
    )

    assert seen_states == [StartState.DISPATCHING]
    assert runner.start_calls == 1
    assert completed.start_state == StartState.ATTACHED


@pytest.mark.asyncio
async def test_task_service_attaches_run_id_after_concurrent_cancel(
    task_repository,
    queued_task,
):
    runner = AwaitingStartRunner()
    execution = asyncio.create_task(
        TaskService(task_repository, runner).run_task(
            queued_task.id,
            "worker:test",
        )
    )
    await asyncio.wait_for(runner.start_waiting.wait(), timeout=1)

    dispatching = task_repository.refresh(queued_task.id)
    with Session(task_repository.db.get_bind(), expire_on_commit=False) as db:
        cancelled = SQLiteTaskRepository(db).request_cancel(
            queued_task.id,
            datetime(2026, 8, 24, 9, 0, 1, tzinfo=UTC),
        )
    assert cancelled.version == dispatching.version + 1

    runner.finish_start.set()
    completed = await execution

    assert runner.start_calls == 1
    assert completed.remote_run_id == f"run:{queued_task.id}"
    assert completed.start_state == StartState.ATTACHED


@pytest.mark.asyncio
async def test_unknown_runner_start_failure_uses_dedicated_terminal_path(
    task_repository,
    queued_task,
    caplog,
):
    now = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)
    queued_task.runner_config.config_snapshot = {
        "pod_id": "mock:default",
        "timeout_seconds": 900,
    }
    task_repository.db.commit()
    runner = FailingStartRunner(
        RunnerFailure(
            "remote_timeout",
            "runner_interrupted",
            start_outcome_unknown=True,
        )
    )

    with caplog.at_level(logging.INFO, logger="cua_platform.pod_leases"):
        completed = await TaskService(
            task_repository,
            runner,
            clock=FakeClock(now),
            execution_timeout=timedelta(seconds=600),
        ).run_task(
            queued_task.id,
            "worker:test",
        )

    assert completed.execution_status == ExecutionStatus.RESULT_READY
    assert completed.failure_type == "start_outcome_unknown"
    assert list(
        task_repository.db.scalars(
            select(TaskEvent.event_type).where(TaskEvent.task_id == queued_task.id)
        )
    ) == ["task_start_outcome_unknown"]
    lease = task_repository.db.scalar(
        select(PodLease).where(PodLease.task_id == queued_task.id)
    )
    assert lease is not None
    assert lease.expires_at.replace(tzinfo=UTC) == now + timedelta(seconds=930)
    quarantined = next(
        record
        for record in caplog.records
        if record.getMessage() == "pod_lease_quarantined"
    )
    assert quarantined.task_id == queued_task.id
    assert quarantined.resource_key == "mock:default"
    assert quarantined.worker_id == "worker:test"
    assert quarantined.lease_version == 3
    assert quarantined.quarantine_until == (
        now + timedelta(seconds=930)
    ).isoformat()


@pytest.mark.parametrize(
    "snapshot",
    [
        [],
        {"timeout_seconds": float("nan")},
        {"timeout_seconds": float("inf")},
        {"timeout_seconds": float("-inf")},
        {"timeout_seconds": True},
        {"timeout_seconds": 0},
        {"timeout_seconds": -1},
        {"timeout_seconds": 86401},
        {"timeout_seconds": 10**400},
    ],
    ids=[
        "non-mapping",
        "nan",
        "positive-infinity",
        "negative-infinity",
        "bool",
        "zero",
        "negative",
        "above-api-bound",
        "huge-integer",
    ],
)
def test_live_unknown_start_uses_service_timeout_for_invalid_snapshot(
    task_repository,
    queued_task,
    snapshot,
):
    now = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)
    task_id = queued_task.id
    queued_task.execution_status = ExecutionStatus.RUNNING
    queued_task.start_state = StartState.DISPATCHING
    queued_task.start_attempted_at = now
    queued_task.runner_config.config_snapshot = snapshot
    task_repository.db.commit()

    completed = TaskService(
        task_repository,
        None,
        clock=FakeClock(now),
        execution_timeout=timedelta(seconds=600),
    ).converge_worker_failure(task_id)

    assert completed is not None
    assert completed.execution_status == ExecutionStatus.RESULT_READY
    assert completed.failure_type == "start_outcome_unknown"
    lease = task_repository.db.scalar(
        select(PodLease).where(PodLease.task_id == task_id)
    )
    assert lease is not None
    assert lease.expires_at.replace(tzinfo=UTC) == now + timedelta(seconds=630)


@pytest.mark.asyncio
async def test_generic_exception_after_dispatch_uses_unknown_terminal_path(
    task_repository,
    queued_task,
):
    completed = await TaskService(
        task_repository,
        FailingStartRunner(RuntimeError("unexpected start failure")),
    ).run_task(
        queued_task.id,
        "worker:test",
    )

    assert completed.failure_type == "start_outcome_unknown"
    assert list(
        task_repository.db.scalars(
            select(TaskEvent.event_type).where(TaskEvent.task_id == queued_task.id)
        )
    ) == ["task_start_outcome_unknown"]


@pytest.mark.asyncio
async def test_known_runner_start_failure_uses_existing_failure_path(
    task_repository,
    queued_task,
):
    runner = FailingStartRunner(
        RunnerFailure(
            "invalid_parameter",
            "runner_interrupted",
            start_outcome_unknown=False,
        )
    )

    completed = await TaskService(task_repository, runner).run_task(
        queued_task.id,
        "worker:test",
    )

    assert completed.failure_type == "runner_interrupted"
    assert list(
        task_repository.db.scalars(
            select(TaskEvent.event_type).where(TaskEvent.task_id == queued_task.id)
        )
    ) == ["task_started", "runner_interrupted"]


@pytest.mark.asyncio
async def test_run_handle_persistence_failure_uses_unknown_terminal_path(
    task_repository,
    queued_task,
    monkeypatch,
):
    runner = CountingRunner()

    def fail_save(_task_id, _handle):
        raise RuntimeError("database write failed")

    monkeypatch.setattr(task_repository, "save_run_handle", fail_save)

    completed = await TaskService(task_repository, runner).run_task(
        queued_task.id,
        "worker:test",
    )

    assert completed.failure_type == "start_outcome_unknown"
    assert list(
        task_repository.db.scalars(
            select(TaskEvent.event_type).where(TaskEvent.task_id == queued_task.id)
        )
    ) == ["task_start_outcome_unknown"]


def test_worker_failure_renews_attached_remote_task_on_every_retry(
    task_repository,
    running_task,
):
    now = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)
    clock = FakeClock(now)
    running_task.start_state = StartState.ATTACHED
    running_task.remote_run_id = "run-preserved"
    task_repository.db.commit()
    service = TaskService(task_repository, None, clock=clock)

    first = service.converge_worker_failure(
        running_task.id,
        worker_id="worker:test",
    )
    lease = task_repository.db.scalar(
        select(PodLease).where(PodLease.task_id == running_task.id)
    )
    assert lease is not None
    assert lease.expires_at.replace(tzinfo=UTC) == now + timedelta(seconds=30)
    assert lease.version == 2

    clock.advance(seconds=10)
    second = service.converge_worker_failure(
        running_task.id,
        worker_id="worker:test",
    )

    assert first is not None
    assert first.execution_status == ExecutionStatus.RUNNING
    assert first.start_state == StartState.ATTACHED
    assert first.remote_run_id == "run-preserved"
    assert second is not None
    assert second.execution_status == ExecutionStatus.RUNNING
    assert second.start_state == StartState.ATTACHED
    assert second.remote_run_id == "run-preserved"
    task_repository.db.refresh(lease)
    assert lease.expires_at.replace(tzinfo=UTC) == now + timedelta(seconds=40)
    assert lease.version == 3


def test_worker_failure_repairs_attached_state_before_renewal(
    task_repository,
    running_task,
):
    now = datetime(2026, 8, 24, 9, 0, 10, tzinfo=UTC)
    running_task.start_state = StartState.DISPATCHING
    running_task.remote_run_id = "run-repaired"
    task_repository.db.commit()

    result = TaskService(
        task_repository,
        None,
        clock=FakeClock(now),
    ).converge_worker_failure(
        running_task.id,
        worker_id="worker:test",
    )

    assert result is not None
    assert result.start_state == StartState.ATTACHED
    lease = task_repository.db.scalar(
        select(PodLease).where(PodLease.task_id == running_task.id)
    )
    assert lease is not None
    assert lease.expires_at.replace(tzinfo=UTC) == now + timedelta(seconds=30)


def test_worker_failure_recreates_missing_free_attached_lease(
    task_repository,
    running_task,
):
    now = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)
    running_task.start_state = StartState.ATTACHED
    running_task.remote_run_id = "run-recreated"
    lease = task_repository.db.scalar(
        select(PodLease).where(PodLease.task_id == running_task.id)
    )
    assert lease is not None
    task_repository.db.delete(lease)
    task_repository.db.commit()

    result = TaskService(
        task_repository,
        None,
        clock=FakeClock(now),
    ).converge_worker_failure(
        running_task.id,
        worker_id="worker:test",
    )

    assert result is not None
    recreated = task_repository.db.scalar(
        select(PodLease).where(PodLease.task_id == running_task.id)
    )
    assert recreated is not None
    assert recreated.pod_id == "mock:default"
    assert recreated.worker_id == "worker:test"
    assert recreated.expires_at.replace(tzinfo=UTC) == now + timedelta(seconds=30)
    assert recreated.version == 1


def test_worker_failure_recovers_expired_same_owner_attached_lease(
    task_repository,
    running_task,
):
    now = datetime(2026, 8, 24, 9, 1, tzinfo=UTC)
    running_task.start_state = StartState.ATTACHED
    running_task.remote_run_id = "run-recovered"
    lease = task_repository.db.scalar(
        select(PodLease).where(PodLease.task_id == running_task.id)
    )
    assert lease is not None
    lease.expires_at = now - timedelta(seconds=1)
    task_repository.db.commit()

    result = TaskService(
        task_repository,
        None,
        clock=FakeClock(now),
    ).converge_worker_failure(
        running_task.id,
        worker_id="worker:test",
    )

    assert result is not None
    task_repository.db.refresh(lease)
    assert lease.worker_id == "worker:test"
    assert lease.expires_at.replace(tzinfo=UTC) == now + timedelta(seconds=30)
    assert lease.version == 2


def test_worker_failure_refuses_conflicting_attached_lease(
    task_repository,
    running_task,
):
    now = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)
    running_task.start_state = StartState.ATTACHED
    running_task.remote_run_id = "run-conflict"
    original_lease = task_repository.db.scalar(
        select(PodLease).where(PodLease.task_id == running_task.id)
    )
    assert original_lease is not None
    case = task_repository.db.get(CaseModel, running_task.case_id)
    assert case is not None
    task_repository.db.delete(original_lease)
    conflicting_task = task_repository.create_from_case(
        case,
        "success",
        idempotency_key="attached-lease-conflict",
        runner_type="mock",
    ).task
    conflicting_lease = PodLease(
        pod_id="mock:default",
        task_id=conflicting_task.id,
        worker_id="worker:other",
        expires_at=now + timedelta(seconds=30),
        version=4,
    )
    task_repository.db.add(conflicting_lease)
    task_repository.db.commit()

    with pytest.raises(RuntimeError, match="attached_lease_unavailable"):
        TaskService(
            task_repository,
            None,
            clock=FakeClock(now),
        ).converge_worker_failure(
            running_task.id,
            worker_id="worker:test",
        )

    assert task_repository.db.scalar(
        select(PodLease).where(PodLease.task_id == running_task.id)
    ) is None
    task_repository.db.refresh(conflicting_lease)
    assert conflicting_lease.task_id == conflicting_task.id
    assert conflicting_lease.worker_id == "worker:other"
    assert conflicting_lease.expires_at == datetime(2026, 8, 24, 9, 0, 30)
    assert conflicting_lease.version == 4


@pytest.mark.parametrize(
    ("start_state", "expected_status", "expected_failure"),
    [
        (StartState.PENDING, ExecutionStatus.QUEUED, None),
        (
            StartState.DISPATCHING,
            ExecutionStatus.RESULT_READY,
            "start_outcome_unknown",
        ),
    ],
)
def test_worker_failure_converges_unattached_task_by_phase(
    task_repository,
    running_task,
    start_state,
    expected_status,
    expected_failure,
    monkeypatch,
):
    renewals = []

    def track_renewal(*args):
        renewals.append(args)
        return True

    monkeypatch.setattr(task_repository, "renew_lease", track_renewal)
    running_task.start_state = start_state
    task_repository.db.commit()

    result = TaskService(task_repository, None).converge_worker_failure(
        running_task.id,
        worker_id="worker:test",
    )

    assert result is not None
    assert result.execution_status == expected_status
    assert result.failure_type == expected_failure
    assert renewals == []


@pytest.mark.asyncio
async def test_app_worker_failure_callback_preserves_attached_remote_task(
    authenticated_client,
    create_script,
):
    with authenticated_client.app.state.session_factory() as db:
        repository = SQLiteTaskRepository(db)
        case = db.get(CaseModel, create_script())
        assert case is not None
        task = repository.create_from_case(
            case,
            "success",
            idempotency_key="worker-callback-run-id",
            runner_type="mock",
        ).task
        claimed = repository.claim(
            task.id,
            "worker:default",
            datetime.now(UTC),
            timedelta(seconds=30),
        )
        assert claimed is not None
        repository.mark_start_dispatching(task.id, datetime.now(UTC))
        repository.save_run_handle(
            task.id,
            RunHandle(task.id, "mock", "run-preserved"),
        )

    callback = authenticated_client.app.state.task_worker.converge_cancelled
    assert callback is not None
    assert await callback(task.id) == WorkerFailureDisposition.RETRY

    with authenticated_client.app.state.session_factory() as db:
        preserved = db.get(Task, task.id)
        assert preserved is not None
        assert preserved.execution_status == ExecutionStatus.RUNNING
        assert preserved.remote_run_id == "run-preserved"
        lease = db.scalar(
            select(PodLease).where(PodLease.task_id == task.id)
        )
        assert lease is not None
        assert lease.worker_id == "worker:default"
        assert lease.version == 2


@pytest.mark.asyncio
async def test_app_worker_failure_repository_error_returns_drain_action(
    authenticated_client,
    create_script,
    monkeypatch,
):
    with authenticated_client.app.state.session_factory() as db:
        repository = SQLiteTaskRepository(db)
        case = db.get(CaseModel, create_script())
        assert case is not None
        task = repository.create_from_case(
            case,
            "success",
            idempotency_key="worker-callback-repository-error",
            runner_type="mock",
        ).task
        now = datetime.now(UTC)
        assert repository.claim(
            task.id,
            "worker:default",
            now,
            timedelta(seconds=30),
        )
        repository.mark_start_dispatching(task.id, now)
        repository.save_run_handle(
            task.id,
            RunHandle(task.id, "mock", "run-repository-error"),
        )

    def fail_lease_recovery(*_args, **_kwargs):
        raise RuntimeError("database write failed")

    monkeypatch.setattr(
        SQLiteTaskRepository,
        "ensure_attached_lease",
        fail_lease_recovery,
        raising=False,
    )
    callback = authenticated_client.app.state.task_worker.converge_cancelled
    assert callback is not None

    assert await callback(task.id) == WorkerFailureDisposition.DRAIN


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("branch", "repository_method"),
    [
        ("queued", "finalize_preclaim_failure"),
        ("pending", "requeue_before_dispatch"),
        ("unknown", "finalize_start_outcome_unknown"),
    ],
)
async def test_convergence_repository_failure_drains_and_fences_scheduler(
    authenticated_client,
    create_script,
    monkeypatch,
    caplog,
    branch,
    repository_method,
):
    with authenticated_client.app.state.session_factory() as db:
        repository = SQLiteTaskRepository(db)
        case = db.get(CaseModel, create_script())
        assert case is not None
        task = repository.create_from_case(
            case,
            "success",
            idempotency_key=f"worker-callback-{branch}-repository-error",
            runner_type="mock",
        ).task
        if branch != "queued":
            now = datetime.now(UTC)
            assert repository.claim(
                task.id,
                "worker:default",
                now,
                timedelta(seconds=30),
            )
            if branch == "unknown":
                repository.mark_start_dispatching(task.id, now)

    def fail_convergence(*_args, **_kwargs):
        raise RuntimeError("secret repository failure")

    monkeypatch.setattr(
        SQLiteTaskRepository,
        repository_method,
        fail_convergence,
    )
    callback = authenticated_client.app.state.task_worker.converge_cancelled
    assert callback is not None

    with caplog.at_level(logging.ERROR, logger="cua_platform.errors"):
        disposition = await callback(task.id)

    assert disposition == WorkerFailureDisposition.DRAIN
    assert authenticated_client.app.state.task_worker.is_running is False
    assert authenticated_client.get("/health/ready").status_code == 503
    assert "task_worker_failure_convergence_failed" in caplog.text
    assert "secret repository failure" not in caplog.text

    scheduler_calls = []

    async def track_refresh(*_args, **_kwargs):
        scheduler_calls.append("refresh")
        return set()

    def track_reservation(*_args, **_kwargs):
        scheduler_calls.append("reservation")

    monkeypatch.setattr(SchedulerPodPoolRefresher, "refresh_due", track_refresh)
    monkeypatch.setattr(BatchScheduler, "schedule", track_reservation)

    assert await authenticated_client.app.state.schedule_batches() == []
    assert scheduler_calls == []


@pytest.mark.asyncio
async def test_attached_lease_conflict_drains_app_and_suppresses_scheduling(
    authenticated_client,
    create_script,
    monkeypatch,
):
    with authenticated_client.app.state.session_factory() as db:
        repository = SQLiteTaskRepository(db)
        case = db.get(CaseModel, create_script())
        assert case is not None
        task = repository.create_from_case(
            case,
            "success",
            idempotency_key="worker-callback-lease-conflict",
            runner_type="mock",
        ).task
        now = datetime.now(UTC)
        assert repository.claim(
            task.id,
            "worker:default",
            now,
            timedelta(seconds=30),
        )
        repository.mark_start_dispatching(task.id, now)
        repository.save_run_handle(
            task.id,
            RunHandle(task.id, "mock", "run-lease-conflict"),
        )
        lease = db.scalar(select(PodLease).where(PodLease.task_id == task.id))
        assert lease is not None
        lease.worker_id = "worker:other"
        db.commit()

    callback = authenticated_client.app.state.task_worker.converge_cancelled
    assert callback is not None
    assert await callback(task.id) == WorkerFailureDisposition.DRAIN
    assert authenticated_client.get("/health/ready").status_code == 503

    def fail_if_scheduled(*_args, **_kwargs):
        raise AssertionError("draining app must not schedule")

    monkeypatch.setattr(BatchScheduler, "schedule", fail_if_scheduled)
    assert await authenticated_client.app.state.schedule_batches() == []

    with authenticated_client.app.state.session_factory() as db:
        preserved = db.get(Task, task.id)
        lease = db.scalar(select(PodLease).where(PodLease.task_id == task.id))
        assert preserved is not None
        assert preserved.execution_status == ExecutionStatus.RUNNING
        assert preserved.start_state == StartState.ATTACHED
        assert preserved.remote_run_id == "run-lease-conflict"
        assert lease is not None
        assert lease.worker_id == "worker:other"


@pytest.mark.asyncio
async def test_app_worker_failure_callback_retries_only_attached_run_id(
    authenticated_client,
    create_script,
):
    callback = authenticated_client.app.state.task_worker.converge_cancelled
    assert callback is not None

    with authenticated_client.app.state.session_factory() as db:
        repository = SQLiteTaskRepository(db)
        case = db.get(CaseModel, create_script())
        assert case is not None

        def create_task(suffix: str) -> Task:
            return repository.create_from_case(
                case,
                "success",
                idempotency_key=f"worker-callback-{suffix}",
                runner_type="mock",
            ).task

        queued = create_task("queued")
    queued_disposition = await callback(queued.id)

    with authenticated_client.app.state.session_factory() as db:
        repository = SQLiteTaskRepository(db)
        case = db.get(CaseModel, create_script())
        assert case is not None
        pending = repository.create_from_case(
            case,
            "success",
            idempotency_key="worker-callback-pending",
            runner_type="mock",
        ).task
        now = datetime.now(UTC)
        assert repository.claim(
            pending.id,
            "worker:test",
            now,
            timedelta(seconds=30),
        )
    pending_disposition = await callback(pending.id)

    with authenticated_client.app.state.session_factory() as db:
        repository = SQLiteTaskRepository(db)
        case = db.get(CaseModel, create_script())
        assert case is not None
        terminal = repository.create_from_case(
            case,
            "success",
            idempotency_key="worker-callback-terminal",
            runner_type="mock",
        ).task
        repository.finalize_preclaim_failure(terminal.id)
    terminal_disposition = await callback(terminal.id)

    with authenticated_client.app.state.session_factory() as db:
        repository = SQLiteTaskRepository(db)
        case = db.get(CaseModel, create_script())
        assert case is not None
        dispatching = repository.create_from_case(
            case,
            "success",
            idempotency_key="worker-callback-dispatching",
            runner_type="mock",
        ).task
        now = datetime.now(UTC)
        assert repository.claim(
            dispatching.id,
            "worker:test",
            now,
            timedelta(seconds=30),
        )
        repository.mark_start_dispatching(dispatching.id, now)
    dispatching_disposition = await callback(dispatching.id)

    assert [
        queued_disposition,
        pending_disposition,
        dispatching_disposition,
        terminal_disposition,
    ] == [WorkerFailureDisposition.COMPLETE] * 4


def test_app_worker_failure_finalizes_queued_task_before_claim(
    authenticated_client,
    create_script,
    monkeypatch,
):
    with authenticated_client.app.state.session_factory() as db:
        repository = SQLiteTaskRepository(db)
        case = db.get(CaseModel, create_script())
        assert case is not None
        task = repository.create_from_case(
            case,
            "success",
            idempotency_key="worker-callback-preclaim",
            runner_type="mock",
        ).task
        db.add(
            PodLease(
                pod_id="mock:preclaim",
                task_id=task.id,
                worker_id="reserved",
                expires_at=datetime.now(UTC) + timedelta(seconds=30),
                version=1,
            )
        )
        db.commit()

    async def fail_before_claim(_task_id):
        raise RuntimeError("runner construction failed")

    worker = authenticated_client.app.state.task_worker
    monkeypatch.setattr(worker, "execute", fail_before_claim)
    authenticated_client.portal.call(worker.enqueue, task.id)
    authenticated_client.portal.call(worker.wait_until_idle)

    with authenticated_client.app.state.session_factory() as db:
        failed = db.get(Task, task.id)
        assert failed is not None
        assert failed.execution_status == ExecutionStatus.RESULT_READY
        assert failed.verdict == Verdict.FAIL
        assert failed.failure_type == "internal_error"
        assert list(
            db.execute(
                select(TaskEvent.event_type, TaskEvent.payload)
                .where(TaskEvent.task_id == task.id)
                .order_by(TaskEvent.sequence)
            )
        ) == [
            (
                "runner_interrupted",
                {"failure_type": "internal_error"},
            )
        ]
        assert db.scalar(
            select(PodLease).where(PodLease.task_id == task.id)
        ) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("start_state", "run_id", "expected_status", "expected_failure", "enqueued"),
    [
        (StartState.PENDING, None, ExecutionStatus.QUEUED, None, True),
        (
            StartState.DISPATCHING,
            None,
            ExecutionStatus.RESULT_READY,
            "start_outcome_unknown",
            False,
        ),
        (
            StartState.ATTACHED,
            None,
            ExecutionStatus.RESULT_READY,
            "internal_error",
            False,
        ),
        (StartState.ATTACHED, "run-existing", ExecutionStatus.RUNNING, None, True),
    ],
)
async def test_startup_recovery_uses_submission_state(
    task_repository,
    start_state,
    run_id,
    expected_status,
    expected_failure,
    enqueued,
    caplog,
):
    task_id = seed_running_task(
        task_repository.db,
        start_state=start_state,
        remote_run_id=run_id,
    )

    with caplog.at_level(logging.INFO, logger="cua_platform.tasks"):
        recovered = await TaskService(
            task_repository,
            None,
            clock=FakeClock(datetime(2026, 8, 24, 10, 0, tzinfo=UTC)),
        ).recover_startup()
    task = task_repository.refresh(task_id)

    assert (task_id in recovered) is enqueued
    assert task.execution_status == expected_status
    assert task.failure_type == expected_failure
    event_types = list(
        task_repository.db.scalars(
            select(TaskEvent.event_type).where(TaskEvent.task_id == task_id)
        )
    )
    if expected_failure == "start_outcome_unknown":
        assert event_types == ["task_start_outcome_unknown"]
        trace = TraceRepository(task_repository.db).list_for_task(task_id)
        assert [(span.name, span.kind, span.status) for span in trace] == [
            ("task_start_outcome_unknown", "error", "error")
        ]
    elif start_state == StartState.ATTACHED and run_id is None:
        assert event_types == ["runner_interrupted"]
    else:
        assert "runner_interrupted" not in event_types
    if start_state == StartState.PENDING:
        assert (
            task_repository.db.scalar(
                select(PodLease).where(PodLease.task_id == task_id)
            )
            is None
        )

    completed = next(
        record
        for record in caplog.records
        if record.getMessage() == "task_recovery_completed"
    )
    assert completed.resumed_count == int(run_id is not None)
    assert completed.requeued_count == int(start_state == StartState.PENDING)
    assert completed.unknown_count == int(start_state == StartState.DISPATCHING)
    assert completed.failed_count == int(
        start_state == StartState.ATTACHED and run_id is None
    )
    branch_logs = {
        record.getMessage(): record
        for record in caplog.records
        if record.getMessage() != "task_recovery_completed"
    }
    if run_id is not None:
        branch = branch_logs["task_recovery_resumed"]
        assert branch.remote_run_id == run_id
    elif start_state == StartState.PENDING:
        branch = branch_logs["task_recovery_requeued"]
    elif start_state == StartState.DISPATCHING:
        branch = branch_logs["task_start_outcome_unknown"]
    else:
        branch = None
    if branch is not None:
        assert branch.task_id == task_id
        assert branch.start_state == start_state.value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "snapshot",
    [
        "invalid",
        {"timeout_seconds": float("nan")},
        {"timeout_seconds": float("inf")},
        {"timeout_seconds": float("-inf")},
        {"timeout_seconds": False},
        {"timeout_seconds": 0},
        {"timeout_seconds": -1},
        {"timeout_seconds": 86401},
        {"timeout_seconds": 10**400},
    ],
    ids=[
        "non-mapping",
        "nan",
        "positive-infinity",
        "negative-infinity",
        "bool",
        "zero",
        "negative",
        "above-api-bound",
        "huge-integer",
    ],
)
async def test_startup_unknown_start_uses_service_timeout_for_invalid_snapshot(
    task_repository,
    snapshot,
):
    started_at = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)
    now = started_at + timedelta(minutes=1)
    task_id = seed_running_task(
        task_repository.db,
        start_state=StartState.DISPATCHING,
        remote_run_id=None,
    )
    task = task_repository.refresh(task_id)
    task.runner_config.config_snapshot = snapshot
    lease = task_repository.db.scalar(
        select(PodLease).where(PodLease.task_id == task_id)
    )
    assert lease is not None
    lease.expires_at = now + timedelta(seconds=30)
    task_repository.db.commit()

    recovered = await TaskService(
        task_repository,
        None,
        clock=FakeClock(now),
        execution_timeout=timedelta(seconds=600),
    ).recover_startup()

    assert recovered == []
    completed = task_repository.refresh(task_id)
    assert completed.execution_status == ExecutionStatus.RESULT_READY
    assert completed.failure_type == "start_outcome_unknown"
    lease = task_repository.db.scalar(
        select(PodLease).where(PodLease.task_id == task_id)
    )
    assert lease is not None
    assert lease.expires_at.replace(tzinfo=UTC) == now + timedelta(seconds=630)


@pytest.mark.asyncio
async def test_startup_recovery_repairs_run_id_to_attached(task_repository):
    task_id = seed_running_task(
        task_repository.db,
        start_state=StartState.DISPATCHING,
        remote_run_id="run-repair",
    )

    recovered = await TaskService(task_repository, None).recover_startup()

    assert recovered == [task_id]
    assert task_repository.refresh(task_id).start_state == StartState.ATTACHED


@pytest.mark.asyncio
async def test_startup_recovery_cancels_pending_task_before_requeue(task_repository):
    now = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)
    task_id = seed_running_task(
        task_repository.db,
        start_state=StartState.PENDING,
        remote_run_id=None,
        cancel_requested_at=now,
    )

    recovered = await TaskService(
        task_repository,
        None,
        clock=FakeClock(now),
    ).recover_startup()

    task = task_repository.refresh(task_id)
    assert recovered == []
    assert task.execution_status == ExecutionStatus.CANCELLED
    assert task.cancel_requested_at.replace(tzinfo=UTC) == now
    assert list(
        task_repository.db.scalars(
            select(TaskEvent.event_type).where(TaskEvent.task_id == task_id)
        )
    ) == ["task_cancelled"]
    assert (
        task_repository.db.scalar(
            select(PodLease).where(PodLease.task_id == task_id)
        )
        is None
    )


@pytest.mark.asyncio
async def test_startup_recovery_cancels_legacy_queued_task_before_enqueue(
    task_repository,
):
    now = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)
    task_id = seed_running_task(
        task_repository.db,
        start_state=StartState.PENDING,
        remote_run_id=None,
        cancel_requested_at=now,
        batch_id=f"batch_{uuid4().hex}",
        with_lease=False,
    )
    task = task_repository.refresh(task_id)
    task.execution_status = ExecutionStatus.QUEUED
    task.started_at = None
    task_repository.db.commit()

    recovered = await TaskService(
        task_repository,
        None,
        clock=FakeClock(now),
    ).recover_startup()

    task = task_repository.refresh(task_id)
    assert recovered == []
    assert task.execution_status == ExecutionStatus.CANCELLED
    assert task.cancel_requested_at.replace(tzinfo=UTC) == now
    assert list(
        task_repository.db.scalars(
            select(TaskEvent.event_type).where(TaskEvent.task_id == task_id)
        )
    ) == ["task_cancelled"]
    assert (
        task_repository.db.scalar(
            select(PodLease).where(PodLease.task_id == task_id)
        )
        is None
    )


def test_startup_recovery_excludes_unleased_queued_batch_task(task_repository):
    task_id = seed_running_task(
        task_repository.db,
        start_state=StartState.PENDING,
        remote_run_id=None,
        batch_id=f"batch_{uuid4().hex}",
        with_lease=False,
    )
    task = task_repository.refresh(task_id)
    task.execution_status = ExecutionStatus.QUEUED
    task.started_at = None
    task_repository.db.commit()

    assert task_repository.list_recoverable() == []


@pytest.mark.asyncio
async def test_recovered_cancel_request_uses_existing_run_id(task_repository):
    now = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)
    task_id = seed_running_task(
        task_repository.db,
        start_state=StartState.ATTACHED,
        remote_run_id="run-cancel-existing",
        cancel_requested_at=now,
    )
    runner = TerminalCancelRunner()

    recovered = await TaskService(
        task_repository,
        None,
        clock=FakeClock(now),
    ).recover_startup()
    assert recovered == [task_id]

    completed = await TaskService(
        task_repository,
        runner,
        clock=FakeClock(now),
    ).execute_or_resume(task_id)

    assert runner.cancelled_run_ids == ["run-cancel-existing"]
    assert completed.execution_status == ExecutionStatus.CANCELLED
