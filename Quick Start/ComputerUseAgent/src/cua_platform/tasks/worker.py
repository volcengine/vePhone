import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from enum import StrEnum
from time import monotonic

logger = logging.getLogger("cua_platform.task_worker")


class WorkerState(StrEnum):
    RUNNING = "running"
    DRAINING = "draining"
    STOPPED = "stopped"


class WorkerFailureDisposition(StrEnum):
    COMPLETE = "complete"
    RETRY = "retry"
    DRAIN = "drain"


class WorkerUnavailableError(RuntimeError):
    pass


class TaskWorker:
    RETRY_DELAY_SECONDS = 1

    def __init__(
        self,
        execute: Callable[[str], Awaitable[None]],
        recover_startup: Callable[[], Awaitable[list[str]]] | None = None,
        converge_cancelled: (
            Callable[[str], Awaitable[WorkerFailureDisposition]] | None
        ) = None,
        *,
        max_concurrency: int = 1,
    ):
        if max_concurrency < 1:
            raise ValueError("max_concurrency_must_be_positive")
        self.execute = execute
        self.recover_startup = recover_startup
        self.converge_cancelled = converge_cancelled
        self.max_concurrency = max_concurrency
        self.queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._loop_task: asyncio.Task[None] | None = None
        self._stop_lock = asyncio.Lock()
        self._state = WorkerState.STOPPED
        self._active_task_ids: set[str] = set()
        self._drain_started_at: float | None = None

    @property
    def is_running(self) -> bool:
        return (
            self._state == WorkerState.RUNNING
            and self._loop_task is not None
            and not self._loop_task.done()
        )

    async def start(self) -> None:
        if self._loop_task is not None:
            return
        recovered = (
            await self.recover_startup()
            if self.recover_startup is not None
            else []
        )
        self._state = WorkerState.RUNNING
        self._loop_task = asyncio.create_task(self._run())
        for task_id in recovered:
            await self.queue.put(task_id)

    def begin_drain(self) -> None:
        if self._state != WorkerState.RUNNING:
            return
        self._state = WorkerState.DRAINING
        self._drain_started_at = monotonic()
        logger.info(
            "worker_drain_started",
            extra={"active_count": len(self._active_task_ids)},
        )
        for _index in range(self.max_concurrency):
            self.queue.put_nowait(None)

    async def stop(self, timeout_seconds: float = 0) -> None:
        async with self._stop_lock:
            await self._stop(timeout_seconds)

    async def _stop(self, timeout_seconds: float) -> None:
        loop_task = self._loop_task
        if loop_task is None:
            return
        if loop_task.done():
            self._state = WorkerState.STOPPED
            with suppress(asyncio.CancelledError, Exception):
                await loop_task
            return
        self.begin_drain()
        try:
            await asyncio.wait_for(
                asyncio.shield(loop_task),
                timeout=max(0, timeout_seconds),
            )
            logger.info(
                "worker_drain_completed",
                extra={"elapsed_ms": self._drain_elapsed_ms()},
            )
        except TimeoutError:
            handed_off = tuple(sorted(self._active_task_ids))
            logger.warning(
                "worker_drain_timeout",
                extra={
                    "active_count": len(handed_off),
                    "elapsed_ms": self._drain_elapsed_ms(),
                },
            )
            for task_id in handed_off:
                logger.info(
                    "task_handoff_preserved",
                    extra={"task_id": task_id},
                )
            loop_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await loop_task
        finally:
            self._state = WorkerState.STOPPED

    async def enqueue(self, task_id: str) -> None:
        self._ensure_available()
        await self.queue.put(task_id)

    async def wait_until_idle(self) -> None:
        loop_task = self._ensure_available()
        join_task = asyncio.create_task(self.queue.join())
        done, _pending = await asyncio.wait(
            {join_task, loop_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if loop_task in done:
            join_task.cancel()
            with suppress(asyncio.CancelledError):
                await join_task
            raise WorkerUnavailableError("task worker is not running")
        await join_task

    async def _run(self) -> None:
        consumers = [
            asyncio.create_task(self._consume())
            for _index in range(self.max_concurrency)
        ]
        try:
            await asyncio.gather(*consumers)
        finally:
            for consumer in consumers:
                consumer.cancel()
            for consumer in consumers:
                with suppress(asyncio.CancelledError, Exception):
                    await consumer

    async def _consume(self) -> None:
        while True:
            task_id = await self.queue.get()
            try:
                if task_id is None:
                    return
                if self._state != WorkerState.RUNNING:
                    self.queue.put_nowait(task_id)
                    return
                self._active_task_ids.add(task_id)
                try:
                    await self.execute(task_id)
                except asyncio.CancelledError:
                    if (
                        self._state != WorkerState.DRAINING
                        and self.converge_cancelled is not None
                    ):
                        await self.converge_cancelled(task_id)
                    raise
                except Exception:
                    disposition = WorkerFailureDisposition.COMPLETE
                    if self.converge_cancelled is not None:
                        disposition = await self.converge_cancelled(task_id)
                    if disposition == WorkerFailureDisposition.DRAIN:
                        self.begin_drain()
                    elif disposition == WorkerFailureDisposition.RETRY:
                        await asyncio.sleep(self.RETRY_DELAY_SECONDS)
                        if self._state == WorkerState.RUNNING:
                            self.queue.put_nowait(task_id)
                    continue
                finally:
                    self._active_task_ids.discard(task_id)
            finally:
                self.queue.task_done()

    def _ensure_available(self) -> asyncio.Task[None]:
        if not self.is_running:
            raise WorkerUnavailableError("task worker is not running")
        assert self._loop_task is not None
        return self._loop_task

    def _drain_elapsed_ms(self) -> int:
        if self._drain_started_at is None:
            return 0
        return round((monotonic() - self._drain_started_at) * 1000)
