import asyncio

import pytest

from cua_platform.main import create_app
from cua_platform.tasks.pod_pool_refresh import SchedulerPodPoolRefresher
from cua_platform.tasks.scheduler import BatchScheduler, ScheduleResult
from cua_platform.tasks.worker import TaskWorker


@pytest.mark.asyncio
async def test_scheduler_failure_still_stops_worker_with_configured_timeout(
    settings,
    monkeypatch,
):
    events = []
    scheduler_failed = asyncio.Event()

    async def start(_worker):
        events.append("start")

    def begin_drain(_worker):
        events.append("begin_drain")

    async def stop(_worker, timeout_seconds=0):
        events.append(("stop", timeout_seconds))

    def fail_schedule(_scheduler, *_args, **_kwargs):
        events.append("scheduler_failed")
        scheduler_failed.set()
        raise RuntimeError("scheduler failed")

    monkeypatch.setattr(TaskWorker, "start", start)
    monkeypatch.setattr(TaskWorker, "begin_drain", begin_drain)
    monkeypatch.setattr(TaskWorker, "stop", stop)
    monkeypatch.setattr(BatchScheduler, "schedule", fail_schedule)
    app = create_app(
        settings.model_copy(update={"task_worker_drain_timeout_seconds": 7})
    )

    with pytest.raises(RuntimeError, match="scheduler failed"):
        async with app.router.lifespan_context(app):
            await scheduler_failed.wait()

    assert events == [
        "start",
        "scheduler_failed",
        "begin_drain",
        ("stop", 7),
    ]


@pytest.mark.asyncio
async def test_trailing_schedule_is_skipped_after_drain_begins(
    settings,
    monkeypatch,
):
    initial_schedule_done = asyncio.Event()
    drain_started = asyncio.Event()
    stop_release = asyncio.Event()
    refresh_calls = 0
    schedule_calls = 0

    async def start(_worker):
        pass

    def begin_drain(_worker):
        drain_started.set()

    async def stop(_worker, timeout_seconds=0):
        await stop_release.wait()

    async def refresh_due(_refresher, _now):
        nonlocal refresh_calls
        refresh_calls += 1
        return set()

    def schedule(_scheduler, *_args, **_kwargs):
        nonlocal schedule_calls
        schedule_calls += 1
        initial_schedule_done.set()
        return ScheduleResult([], None)

    monkeypatch.setattr(TaskWorker, "start", start)
    monkeypatch.setattr(TaskWorker, "begin_drain", begin_drain)
    monkeypatch.setattr(TaskWorker, "stop", stop)
    monkeypatch.setattr(SchedulerPodPoolRefresher, "refresh_due", refresh_due)
    monkeypatch.setattr(BatchScheduler, "schedule", schedule)
    app = create_app(settings)
    lifespan = app.router.lifespan_context(app)
    await lifespan.__aenter__()
    await asyncio.wait_for(initial_schedule_done.wait(), timeout=1)

    shutdown = asyncio.create_task(lifespan.__aexit__(None, None, None))
    await asyncio.wait_for(drain_started.wait(), timeout=1)
    baseline = (refresh_calls, schedule_calls)

    assert await app.state.schedule_batches() == []
    assert (refresh_calls, schedule_calls) == baseline

    stop_release.set()
    await shutdown


@pytest.mark.asyncio
async def test_schedule_in_refresh_does_not_reserve_after_drain_begins(
    settings,
    monkeypatch,
):
    initial_schedule_done = asyncio.Event()
    refresh_started = asyncio.Event()
    refresh_release = asyncio.Event()
    drain_started = asyncio.Event()
    refresh_calls = 0
    schedule_calls = 0

    async def start(_worker):
        pass

    def begin_drain(_worker):
        drain_started.set()

    async def stop(_worker, timeout_seconds=0):
        pass

    async def refresh_due(_refresher, _now):
        nonlocal refresh_calls
        refresh_calls += 1
        if refresh_calls > 1:
            refresh_started.set()
            await refresh_release.wait()
        return set()

    def schedule(_scheduler, *_args, **_kwargs):
        nonlocal schedule_calls
        schedule_calls += 1
        initial_schedule_done.set()
        return ScheduleResult([], None)

    monkeypatch.setattr(TaskWorker, "start", start)
    monkeypatch.setattr(TaskWorker, "begin_drain", begin_drain)
    monkeypatch.setattr(TaskWorker, "stop", stop)
    monkeypatch.setattr(SchedulerPodPoolRefresher, "refresh_due", refresh_due)
    monkeypatch.setattr(BatchScheduler, "schedule", schedule)
    app = create_app(settings)
    lifespan = app.router.lifespan_context(app)
    await lifespan.__aenter__()
    await asyncio.wait_for(initial_schedule_done.wait(), timeout=1)

    trailing_schedule = asyncio.create_task(app.state.schedule_batches())
    await asyncio.wait_for(refresh_started.wait(), timeout=1)
    shutdown = asyncio.create_task(lifespan.__aexit__(None, None, None))
    await asyncio.wait_for(drain_started.wait(), timeout=1)
    refresh_release.set()

    assert await trailing_schedule == []
    assert schedule_calls == 1
    await shutdown
