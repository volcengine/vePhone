import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from mua_platform.cases.models import TestCase as CaseModel
from mua_platform.tasks.models import PodLease, Task
from mua_platform.tasks.repository import SQLiteTaskRepository
from mua_platform.tasks.state_machine import ExecutionStatus, Verdict
from mua_platform.tasks.worker import (
    TaskWorker,
    WorkerFailureDisposition,
    WorkerUnavailableError,
)


@pytest.mark.asyncio
async def test_worker_reports_running_only_while_loop_is_available():
    async def execute(_task_id: str) -> None:
        return None

    worker = TaskWorker(execute)
    assert worker.is_running is False

    await worker.start()
    assert worker.is_running is True

    await worker.stop()
    assert worker.is_running is False


@pytest.mark.asyncio
async def test_worker_isolates_task_failure_and_processes_next_task():
    processed = []

    async def execute(task_id: str) -> None:
        processed.append(task_id)
        if task_id == "task_1":
            raise RuntimeError("task failed")

    worker = TaskWorker(execute)
    await worker.start()
    await worker.enqueue("task_1")
    await worker.enqueue("task_2")

    await worker.wait_until_idle()
    await worker.stop()

    assert processed == ["task_1", "task_2"]


@pytest.mark.asyncio
async def test_worker_processes_tasks_up_to_configured_concurrency():
    both_started = asyncio.Event()
    release = asyncio.Event()
    started: set[str] = set()

    async def execute(task_id: str) -> None:
        started.add(task_id)
        if len(started) == 2:
            both_started.set()
        await release.wait()

    worker = TaskWorker(execute, max_concurrency=2)
    await worker.start()
    try:
        await worker.enqueue("task_1")
        await worker.enqueue("task_2")
        await asyncio.wait_for(both_started.wait(), timeout=0.5)
        assert started == {"task_1", "task_2"}
    finally:
        release.set()
        await worker.wait_until_idle()
        await worker.stop()


@pytest.mark.asyncio
async def test_worker_converges_execute_failure_before_processing_next_task():
    converged = set()
    second_processed = asyncio.Event()
    second_saw_convergence = False

    async def execute(task_id: str) -> None:
        nonlocal second_saw_convergence
        if task_id == "task_1":
            raise RuntimeError("task failed")
        second_saw_convergence = "task_1" in converged
        second_processed.set()

    async def converge_failed(task_id: str) -> None:
        converged.add(task_id)

    worker = TaskWorker(execute, converge_cancelled=converge_failed)
    await worker.start()
    try:
        await worker.enqueue("task_1")
        await worker.enqueue("task_2")
        await asyncio.wait_for(second_processed.wait(), timeout=0.5)

        assert converged == {"task_1"}
        assert second_saw_convergence is True
    finally:
        await worker.stop()


@pytest.mark.asyncio
async def test_execute_failure_releases_lease_before_next_task_and_before_stop(
    authenticated_client,
    create_script,
):
    with authenticated_client.app.state.session_factory() as db:
        repository = SQLiteTaskRepository(db)
        case = db.get(CaseModel, create_script())
        assert case is not None
        failed_task_id = repository.create_from_case(
            case,
            "success",
            idempotency_key="worker-execute-failure",
            runner_type="mock",
        ).task.id

    second_processed = asyncio.Event()
    second_observation = {}

    async def execute(task_id: str) -> None:
        if task_id == failed_task_id:
            with authenticated_client.app.state.session_factory() as db:
                claimed = SQLiteTaskRepository(db).claim(
                    task_id,
                    "worker:test",
                    datetime.now(UTC),
                    timedelta(seconds=30),
                )
                assert claimed is not None
            raise RuntimeError("execute failed outside task service")
        with authenticated_client.app.state.session_factory() as db:
            failed = db.get(Task, failed_task_id)
            second_observation["status"] = failed.execution_status
            second_observation["lease_count"] = db.scalar(
                select(func.count()).select_from(PodLease)
            )
        second_processed.set()

    async def converge_failed(task_id: str) -> None:
        with authenticated_client.app.state.session_factory() as db:
            SQLiteTaskRepository(db).finalize_interrupted(
                task_id,
                "runner_interrupted",
            )

    worker = TaskWorker(execute, converge_cancelled=converge_failed)
    await worker.start()
    try:
        await worker.enqueue(failed_task_id)
        await worker.enqueue("task_2")
        await asyncio.wait_for(second_processed.wait(), timeout=0.5)

        assert second_observation == {
            "status": ExecutionStatus.RESULT_READY,
            "lease_count": 0,
        }
        with authenticated_client.app.state.session_factory() as db:
            failed = db.get(Task, failed_task_id)
            assert failed.verdict == Verdict.FAIL
            assert failed.failure_type == "runner_interrupted"
    finally:
        await worker.stop()


@pytest.mark.asyncio
async def test_worker_stop_is_idempotent():
    async def execute(_task_id: str) -> None:
        return None

    worker = TaskWorker(execute)
    await worker.start()

    await worker.stop()
    await worker.stop()

    assert worker._loop_task is not None
    assert worker._loop_task.done()


@pytest.mark.asyncio
async def test_worker_stop_tolerates_cancelled_loop():
    async def execute(_task_id: str) -> None:
        return None

    worker = TaskWorker(execute)
    await worker.start()
    assert worker._loop_task is not None
    worker._loop_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker._loop_task

    assert worker.is_running is False
    await worker.stop()


@pytest.mark.asyncio
async def test_worker_stop_cancels_in_flight_execution():
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def execute(_task_id: str) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    worker = TaskWorker(execute)
    await worker.start()
    await worker.enqueue("task_1")
    await asyncio.wait_for(started.wait(), timeout=0.5)

    stop_task = asyncio.create_task(worker.stop())
    await asyncio.sleep(0.05)
    try:
        assert stop_task.done()
        await stop_task
    finally:
        if not stop_task.done():
            stop_task.cancel()
            with suppress(asyncio.CancelledError):
                await stop_task

    assert cancelled.is_set()
    assert worker.is_running is False


@pytest.mark.asyncio
async def test_worker_drain_rejects_enqueue_and_does_not_start_queued_work():
    processed = []
    started = asyncio.Event()
    release = asyncio.Event()

    async def execute(task_id: str) -> None:
        processed.append(task_id)
        started.set()
        await release.wait()

    worker = TaskWorker(execute)
    await worker.start()
    await worker.enqueue("active")
    await worker.enqueue("queued")
    await asyncio.wait_for(started.wait(), timeout=0.5)

    worker.begin_drain()
    with pytest.raises(WorkerUnavailableError):
        await worker.enqueue("late")
    release.set()
    await worker.stop(timeout_seconds=0.5)

    assert processed == ["active"]
    assert list(worker.queue._queue).count("queued") == 1


@pytest.mark.asyncio
async def test_worker_drain_timeout_cancels_without_failure_convergence():
    started = asyncio.Event()
    converged = []

    async def execute(_task_id: str) -> None:
        started.set()
        await asyncio.Event().wait()

    async def converge(task_id: str) -> WorkerFailureDisposition:
        converged.append(task_id)
        return WorkerFailureDisposition.COMPLETE

    worker = TaskWorker(execute, converge_cancelled=converge)
    await worker.start()
    await worker.enqueue("remote-running")
    await asyncio.wait_for(started.wait(), timeout=0.5)

    await worker.stop(timeout_seconds=0.01)

    assert converged == []
    assert worker.is_running is False


@pytest.mark.asyncio
async def test_worker_retries_attached_task_after_execute_failure(monkeypatch):
    monkeypatch.setattr(TaskWorker, "RETRY_DELAY_SECONDS", 0)
    calls = []

    async def execute(task_id: str) -> None:
        calls.append(task_id)
        if len(calls) == 1:
            raise RuntimeError("poll failed")

    async def converge(_task_id: str) -> WorkerFailureDisposition:
        return WorkerFailureDisposition.RETRY

    worker = TaskWorker(execute, converge_cancelled=converge)
    await worker.start()
    await worker.enqueue("attached")
    await worker.wait_until_idle()
    await worker.stop()

    assert calls == ["attached", "attached"]


@pytest.mark.asyncio
async def test_worker_drain_disposition_enters_draining():
    async def execute(_task_id: str) -> None:
        raise RuntimeError("lease unavailable")

    async def converge(_task_id: str) -> WorkerFailureDisposition:
        return WorkerFailureDisposition.DRAIN

    worker = TaskWorker(execute, converge_cancelled=converge)
    await worker.start()
    await worker.enqueue("attached")
    with pytest.raises(WorkerUnavailableError):
        await worker.wait_until_idle()

    assert worker.is_running is False
