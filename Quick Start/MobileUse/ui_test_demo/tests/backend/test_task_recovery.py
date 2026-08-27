import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from mua_platform.cases.models import TestCase as CaseModel
from mua_platform.db import Base
from mua_platform.runners.base import (
    CancelResult,
    PollResult,
    RunHandle,
    RunnerEvent,
    RunnerFailure,
)
from mua_platform.tasks.models import PodLease, Task, TaskEvent, TaskRunnerConfig
from mua_platform.tasks.repository import SQLiteTaskRepository
from mua_platform.tasks.service import AttachedLeaseUnavailable, TaskService
from mua_platform.tasks.state_machine import ExecutionStatus, StartState
from mua_platform.time import FakeClock


class CountingRunner:
    def __init__(self, run_id: str = "run-once") -> None:
        self.start_calls = 0
        self.run_id = run_id

    async def start(self, request, idempotency_key):
        self.start_calls += 1
        return RunHandle(request.task_id, "mock", self.run_id, "thread-once")

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
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def start(self, request, idempotency_key):
        self.started.set()
        await self.release.wait()
        return RunHandle(request.task_id, "mock", "run-after-cancel")

    async def cancel(self, handle):
        return CancelResult(accepted=True, terminal=True)


class FailingStartRunner:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def start(self, request, idempotency_key):
        raise self.error


@pytest.fixture
def task_repository():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        yield SQLiteTaskRepository(db)
    engine.dispose()


@pytest.fixture
def running_task(task_repository):
    now = datetime(2026, 8, 25, 9, 0, tzinfo=UTC)
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
    task.runner_config = TaskRunnerConfig(
        config_snapshot={"product_id": "product_a", "pod_id": "pod_a"},
    )
    lease = PodLease(
        pod_id="product_a:pod_a",
        task_id=task.id,
        worker_id="worker:test",
        expires_at=now + timedelta(seconds=30),
        version=1,
    )
    task_repository.db.add_all([case, task, lease])
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


def seed_running_task(
    db: Session,
    *,
    start_state: StartState,
    remote_run_id: str | None,
    cancel_requested_at: datetime | None = None,
    with_lease: bool = True,
) -> str:
    suffix = uuid4().hex
    now = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)
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
    task.runner_config = TaskRunnerConfig(
        config_snapshot={"product_id": "product_a", "pod_id": f"pod_{suffix}"},
    )
    rows = [case, task]
    if with_lease:
        rows.append(
            PodLease(
                pod_id=f"product_a:pod_{suffix}",
                task_id=task.id,
                worker_id="worker:old",
                expires_at=now - timedelta(seconds=1),
                version=1,
            )
        )
    db.add_all(rows)
    db.commit()
    return task.id


def test_remote_start_can_be_dispatched_only_once(task_repository, running_task):
    now = datetime(2026, 8, 25, 9, 0, tzinfo=UTC)

    first = task_repository.mark_start_dispatching(running_task.id, now)
    second = task_repository.mark_start_dispatching(running_task.id, now)

    assert first is not None
    assert first.start_state == StartState.DISPATCHING
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
        datetime(2026, 8, 25, 9, 0, tzinfo=UTC),
    )
    attached = task_repository.save_run_handle(running_task.id, handle)

    assert attached.start_state == StartState.ATTACHED
    assert attached.remote_run_id == "run-once"
    assert attached.remote_thread_id == "thread-once"


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
    await asyncio.wait_for(runner.started.wait(), timeout=1)

    task_repository.request_cancel(
        queued_task.id,
        datetime(2026, 8, 25, 9, 0, 1, tzinfo=UTC),
    )

    runner.release.set()
    completed = await execution

    assert completed.remote_run_id == "run-after-cancel"
    assert completed.start_state == StartState.ATTACHED
    assert completed.cancel_requested_at is not None


@pytest.mark.asyncio
async def test_unknown_runner_start_failure_uses_dedicated_terminal_path(
    task_repository,
    queued_task,
):
    now = datetime(2026, 8, 25, 9, 0, tzinfo=UTC)
    runner = FailingStartRunner(
        RunnerFailure(
            "remote_timeout",
            "runner_interrupted",
            start_outcome_unknown=True,
        )
    )

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
    events = list(
        task_repository.db.scalars(
            select(TaskEvent.event_type).where(TaskEvent.task_id == queued_task.id)
        )
    )
    assert events == ["task_start_outcome_unknown"]
    lease = task_repository.db.scalar(
        select(PodLease).where(PodLease.task_id == queued_task.id)
    )
    assert lease is not None
    assert lease.expires_at.replace(tzinfo=UTC) == now + timedelta(seconds=630)


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
        (StartState.ATTACHED, None, ExecutionStatus.RESULT_READY, "internal_error", False),
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
):
    now = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)
    task_id = seed_running_task(
        task_repository.db,
        start_state=start_state,
        remote_run_id=run_id,
    )

    recovered = await TaskService(
        task_repository,
        None,
        clock=FakeClock(now),
    ).recover_startup(now)
    task = task_repository.refresh(task_id)

    assert (task_id in recovered) is enqueued
    assert task.execution_status == expected_status
    assert task.failure_type == expected_failure


def test_worker_failure_preserves_attached_remote_task_and_renews_lease(
    task_repository,
    running_task,
):
    now = datetime(2026, 8, 25, 9, 0, tzinfo=UTC)
    running_task.start_state = StartState.ATTACHED
    running_task.remote_run_id = "run-preserved"
    task_repository.db.commit()

    task = TaskService(
        task_repository,
        None,
        clock=FakeClock(now),
    ).converge_worker_failure(
        running_task.id,
        worker_id="worker:test",
    )

    lease = task_repository.db.scalar(
        select(PodLease).where(PodLease.task_id == running_task.id)
    )
    assert task.execution_status == ExecutionStatus.RUNNING
    assert task.remote_run_id == "run-preserved"
    assert lease.expires_at.replace(tzinfo=UTC) == now + timedelta(seconds=30)
    assert lease.version == 2


def test_worker_failure_attached_lease_conflict_raises_unavailable(
    task_repository,
    running_task,
):
    running_task.start_state = StartState.ATTACHED
    running_task.remote_run_id = "run-conflict"
    lease = task_repository.db.scalar(
        select(PodLease).where(PodLease.task_id == running_task.id)
    )
    assert lease is not None
    lease.worker_id = "worker:other"
    task_repository.db.commit()

    with pytest.raises(AttachedLeaseUnavailable):
        TaskService(task_repository, None).converge_worker_failure(
            running_task.id,
            worker_id="worker:test",
        )
