import asyncio
import logging
import math
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from numbers import Real
from typing import Any

from mua_platform.cases.models import TestCase
from mua_platform.pods.service import PodPoolService
from mua_platform.runners.base import (
    RunHandle,
    RunRequest,
    RunnerAdapter,
    RunnerEvent,
    RunnerFailure,
)
from mua_platform.tasks.models import Task
from mua_platform.tasks.repository import TaskRepository
from mua_platform.tasks.state_machine import ExecutionStatus, StartState, Verdict
from mua_platform.time import Clock, SystemClock

logger = logging.getLogger("mua_platform.tasks")
LEASE_SAFETY_INTERVAL = timedelta(seconds=30)
RUNNER_TIMEOUT_MAX_SECONDS = 86400


class AttachedLeaseUnavailable(RuntimeError):
    pass


def _log(level: int, event: str, **fields: object) -> None:
    try:
        logger.log(level, event, extra=fields)
    except Exception:
        pass


def _snapshot_execution_timeout(
    snapshot: object,
    fallback: timedelta,
) -> timedelta:
    if not isinstance(snapshot, Mapping):
        return fallback
    timeout = snapshot.get("timeout_seconds")
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, Real)
        or not 0 < timeout <= RUNNER_TIMEOUT_MAX_SECONDS
        or not math.isfinite(timeout)
    ):
        return fallback
    return timedelta(seconds=timeout)


class TaskService:
    def __init__(
        self,
        repository: TaskRepository,
        runner: RunnerAdapter | None,
        *,
        clock: Clock | None = None,
        execution_timeout: timedelta = timedelta(seconds=600),
        cancel_confirm_timeout: timedelta = timedelta(seconds=30),
    ):
        self.repository = repository
        self.runner = runner
        self.clock = clock or SystemClock()
        self.execution_timeout = execution_timeout
        self.cancel_confirm_timeout = cancel_confirm_timeout

    async def execute_case(
        self,
        case: TestCase,
        scenario: str,
        idempotency_key: str,
        runner_type: str = "mobile_use",
        created_by: str = "system",
        runner_config_snapshot: dict[str, Any] | None = None,
        pod_pool: PodPoolService | None = None,
    ) -> Task:
        snapshot = (
            runner_config_snapshot
            if runner_config_snapshot is not None
            else {"pod_id": "mock:default"}
        )
        if runner_type == "mobile_use":
            if pod_pool is None:
                raise RuntimeError("pod_pool_not_configured")
            return await pod_pool.allocate_for_case(
                case,
                scenario,
                idempotency_key,
                runner_type,
                created_by=created_by,
                runner_config_snapshot=snapshot,
            )
        result = self.repository.create_from_case(
            case,
            scenario,
            idempotency_key=idempotency_key,
            runner_type=runner_type,
            created_by=created_by,
            runner_config_snapshot=snapshot,
        )
        return result.task

    async def cancel(self, task_id: str) -> Task:
        return self.repository.request_cancel(task_id, self.clock.now())

    async def process_cancellation(self, task_id: str) -> Task:
        return await self.execute_or_resume(task_id)

    async def recover_startup(self, now: datetime | None = None) -> list[str]:
        current_time = now or self.clock.now()
        released_count = self.repository.release_expired_leases(current_time)
        recovered_lease_count = self.repository.recover_running_leases(
            "worker:default",
            current_time,
            timedelta(seconds=30),
        )
        recoverable = self.repository.list_recoverable()
        recoverable_ids: list[str] = []
        resumed_count = 0
        requeued_count = 0
        unknown_count = 0
        failed_count = 0
        for task in recoverable:
            if (
                task.execution_status == ExecutionStatus.QUEUED
                and task.cancel_requested_at is not None
            ):
                self.repository.request_cancel(task.id, current_time)
                continue
            if (
                task.execution_status == ExecutionStatus.RUNNING
                and task.start_state == StartState.PENDING
                and task.remote_run_id is None
                and task.cancel_requested_at is not None
            ):
                self.repository.finalize_cancel(task.id)
                continue
            if task.execution_status == ExecutionStatus.QUEUED:
                recoverable_ids.append(task.id)
                continue
            if task.remote_run_id is not None:
                if task.start_state != StartState.ATTACHED:
                    task = self.repository.repair_start_attached(task.id)
                recoverable_ids.append(task.id)
                resumed_count += 1
                _log(
                    logging.INFO,
                    "task_recovery_resumed",
                    task_id=task.id,
                    remote_run_id=task.remote_run_id,
                    start_state=task.start_state.value,
                )
                continue
            if task.start_state == StartState.PENDING:
                self.repository.requeue_before_dispatch(task.id)
                recoverable_ids.append(task.id)
                requeued_count += 1
                _log(
                    logging.INFO,
                    "task_recovery_requeued",
                    task_id=task.id,
                    start_state=task.start_state.value,
                )
                continue
            if task.start_state == StartState.DISPATCHING:
                self._finalize_start_outcome_unknown(task.id)
                unknown_count += 1
                continue
            self.repository.finalize_interrupted(task.id, "internal_error")
            failed_count += 1
        _log(
            logging.INFO,
            "task_recovery_completed",
            released_count=released_count,
            recovered_lease_count=recovered_lease_count,
            recoverable_count=len(recoverable),
            finalized_count=unknown_count + failed_count,
            resumed_count=resumed_count,
            requeued_count=requeued_count,
            unknown_count=unknown_count,
            failed_count=failed_count,
        )
        return recoverable_ids

    def converge_worker_failure(
        self,
        task_id: str,
        *,
        worker_id: str = "worker:default",
    ) -> Task | None:
        task = self.repository.get(task_id)
        if task is None:
            return None
        if task.execution_status == ExecutionStatus.QUEUED:
            return self.repository.finalize_preclaim_failure(task_id)
        if task.execution_status != ExecutionStatus.RUNNING:
            return task
        if task.remote_run_id is not None:
            try:
                if task.start_state != StartState.ATTACHED:
                    task = self.repository.repair_start_attached(task_id)
                ensured = self.repository.ensure_attached_lease(
                    task_id,
                    worker_id,
                    self.clock.now(),
                    timedelta(seconds=30),
                )
            except Exception as exc:
                _log(
                    logging.WARNING,
                    "task_worker_failure_lease_ensure_failed",
                    task_id=task_id,
                    worker_id=worker_id,
                    reason="repository_error",
                )
                raise AttachedLeaseUnavailable(
                    f"attached_lease_unavailable:{task_id}"
                ) from exc
            if not ensured:
                _log(
                    logging.WARNING,
                    "task_worker_failure_lease_ensure_failed",
                    task_id=task_id,
                    worker_id=worker_id,
                    reason="ownership_conflict",
                )
                raise AttachedLeaseUnavailable(
                    f"attached_lease_unavailable:{task_id}"
                )
            return task
        if task.start_state == StartState.PENDING:
            return self.repository.requeue_before_dispatch(task_id)
        if task.start_state == StartState.DISPATCHING:
            return self._finalize_start_outcome_unknown(task_id)
        return self.repository.finalize_interrupted(task_id, "internal_error")

    async def execute_or_resume(
        self,
        task_id: str,
        *,
        worker_id: str = "worker:default",
    ) -> Task:
        task = self.repository.get(task_id)
        if task is None:
            raise ValueError(f"task_not_found:{task_id}")
        if task.execution_status in {
            ExecutionStatus.CANCELLED,
            ExecutionStatus.RESULT_READY,
        }:
            return task
        if task.execution_status != ExecutionStatus.RUNNING:
            return task

        if task.remote_run_id is None:
            return task

        handle = RunHandle(
            task_id=task.id,
            runner_type=task.runner_type,
            run_id=task.remote_run_id,
        )
        if task.cancel_requested_at is None:
            return await self._poll_running(task, handle, worker_id)

        now = self.clock.now()
        cancel_deadline = task.cancel_requested_at + self.cancel_confirm_timeout
        if task.last_polled_at is not None and _deadline_reached(now, cancel_deadline):
            return self.repository.finalize_cancel(task_id)

        self.repository.end_transaction()
        try:
            outcome = await self._cancel_remote(
                handle,
                after_sequence=self.repository.last_event_sequence(task_id),
                dispatched=task.last_polled_at is not None,
                now=now,
                deadline=cancel_deadline,
            )
        except Exception:
            return self.repository.finalize_cancel(task_id)
        if outcome == "terminal":
            return self.repository.finalize_cancel(task_id)
        if outcome in {"rejected", "timeout"}:
            return self.repository.finalize_cancel(task_id)
        current = self.repository.get(task_id)
        if current is None:
            raise ValueError(f"task_not_found:{task_id}")
        return current

    async def run_next(
        self,
        *,
        worker_id: str,
        now: datetime | None = None,
        lease_ttl: timedelta = timedelta(seconds=30),
    ) -> Task | None:
        current_time = now or self.clock.now()
        task = self.repository.claim_next(
            worker_id,
            current_time,
            lease_ttl,
            execution_timeout=self.execution_timeout,
        )
        if task is None:
            return None
        return await self._execute_claimed(task, worker_id)

    async def run_task(
        self,
        task_id: str,
        worker_id: str,
        *,
        now: datetime | None = None,
        lease_ttl: timedelta = timedelta(seconds=30),
    ) -> Task | None:
        task = self.repository.claim(
            task_id,
            worker_id,
            now or self.clock.now(),
            lease_ttl,
            execution_timeout=self.execution_timeout,
        )
        if task is None:
            return None
        return await self._execute_claimed(task, worker_id)

    async def _execute_claimed(self, task: Task, worker_id: str) -> Task:
        runner = self._required_runner()
        sequence_offset = 0
        dispatch_started = False
        try:
            case = self._execution_case(task)
            content = task.prompt_snapshot or case.content_markdown
            request = RunRequest(
                task_id=task.id,
                scenario=task.scenario,
                title=case.title,
                content_markdown=content,
            )
            prepare_action = _device_prepare_action(task.runner_config_snapshot)
            if prepare_action != "none":
                prepare_device = getattr(runner, "prepare_device", None)
                if prepare_device is None:
                    return self._record_device_prepare_failure(
                        task.id,
                        error_code="device_prepare_unsupported",
                        request_id=None,
                    )
                self._record_device_prepare_started(
                    task.id,
                    action=prepare_action,
                    snapshot=task.runner_config_snapshot,
                )
                self.repository.end_transaction()
                try:
                    prepare_result = await prepare_device(request)
                except RunnerFailure as exc:
                    return self._record_device_prepare_failure(
                        task.id,
                        error_code=exc.code,
                        request_id=exc.request_id,
                    )
                except Exception:
                    return self._record_device_prepare_failure(
                        task.id,
                        error_code="device_prepare_error",
                        request_id=None,
                    )
                self._record_device_prepare_succeeded(
                    task.id,
                    action=prepare_action,
                    result=prepare_result,
                )
                sequence_offset = self.repository.last_event_sequence(task.id)
            dispatching = self.repository.mark_start_dispatching(
                task.id,
                self.clock.now(),
            )
            if dispatching is None:
                return self.repository.refresh(task.id)
            dispatch_started = True
            self.repository.end_transaction()
            handle = await runner.start(
                request,
                idempotency_key=(
                    dispatching.start_idempotency_key or f"start:{dispatching.id}"
                ),
            )
            self.repository.save_run_handle(task.id, handle)
            _log(
                logging.INFO,
                "task_remote_run_started",
                task_id=task.id,
                runner_type=handle.runner_type,
                run_id=handle.run_id,
                thread_id=handle.thread_id,
            )
        except asyncio.CancelledError:
            raise
        except RunnerFailure as exc:
            if dispatch_started and exc.start_outcome_unknown:
                return self._finalize_start_outcome_unknown(task.id)
            return self._record_runner_failure(
                task.id,
                failure_type=exc.failure_type,
                error_code=exc.code,
                request_id=exc.request_id,
            )
        except Exception:
            if dispatch_started:
                return self._finalize_start_outcome_unknown(task.id)
            return self._record_runner_interrupted(task.id)

        return await self._poll_running(
            self.repository.refresh(task.id),
            handle,
            worker_id,
            sequence_offset=sequence_offset,
        )

    def _finalize_start_outcome_unknown(self, task_id: str) -> Task:
        task = self.repository.refresh(task_id)
        now = self.clock.now()
        started_at = task.start_attempted_at or now
        quarantine_duration = max(
            self.execution_timeout,
            _snapshot_execution_timeout(
                task.runner_config_snapshot,
                self.execution_timeout,
            ),
        )
        quarantine_until = (
            max(_utc_naive(started_at), _utc_naive(now))
            + quarantine_duration
            + LEASE_SAFETY_INTERVAL
        ).replace(tzinfo=UTC)
        completed = self.repository.finalize_start_outcome_unknown(
            task_id,
            quarantine_until,
        )
        _log(
            logging.WARNING,
            "task_start_outcome_unknown",
            task_id=task_id,
            start_state=StartState.DISPATCHING.value,
            quarantine_until=quarantine_until.isoformat(),
        )
        return completed

    async def _poll_running(
        self,
        task: Task,
        handle: RunHandle,
        worker_id: str,
        *,
        sequence_offset: int | None = None,
    ) -> Task:
        resolved_offset = (
            _runner_sequence_offset(task)
            if sequence_offset is None
            else sequence_offset
        )
        last_sequence = max(0, self.repository.last_event_sequence(task.id) - resolved_offset)
        started = any(event.event_type == "task_started" for event in task.events)

        try:
            terminal = False
            while not terminal:
                current = self.repository.refresh(task.id)
                if current.cancel_requested_at is not None:
                    return await self.execute_or_resume(
                        task.id,
                        worker_id=worker_id,
                    )

                if not self.repository.renew_lease(
                    task.id,
                    worker_id,
                    self.clock.now(),
                    timedelta(seconds=30),
                ):
                    return self._record_runner_interrupted(task.id, started=started)

                self.repository.end_transaction()
                page = await self._required_runner().poll(
                    handle,
                    after_sequence=last_sequence,
                )
                current = self.repository.refresh(task.id)

                terminal = page.terminal
                for event in page.events:
                    local_event = RunnerEvent(
                        sequence=resolved_offset + event.sequence,
                        type=event.type,
                        payload=event.payload,
                    )
                    outcome = _terminal_outcome(event)
                    result_summary = None
                    result_evidence = None
                    recording_url = None
                    result_assets = None
                    remote_status_code = None
                    remote_step_id = None
                    remote_thread_id = None
                    if outcome:
                        result_summary = event.payload.get("summary")
                        if isinstance(result_summary, str):
                            result_summary = result_summary
                        else:
                            result_summary = None
                        ev = event.payload.get("evidence")
                        if isinstance(ev, list):
                            result_evidence = [e for e in ev if isinstance(e, str)]
                        raw_recording_url = event.payload.get("recording_url")
                        if isinstance(raw_recording_url, str) and raw_recording_url.strip():
                            recording_url = raw_recording_url.strip()
                        raw_assets = event.payload.get("result_assets")
                        if isinstance(raw_assets, dict):
                            result_assets = raw_assets
                        raw_status_code = event.payload.get("remote_status_code")
                        if isinstance(raw_status_code, int) and not isinstance(raw_status_code, bool):
                            remote_status_code = raw_status_code
                        raw_step_id = event.payload.get("remote_step_id")
                        if isinstance(raw_step_id, str) and raw_step_id.strip():
                            remote_step_id = raw_step_id.strip()
                        raw_thread_id = event.payload.get("remote_thread_id")
                        if isinstance(raw_thread_id, str) and raw_thread_id.strip():
                            remote_thread_id = raw_thread_id.strip()

                    self.repository.record_event(
                        task.id,
                        local_event,
                        status=outcome["status"] if outcome else None,
                        verdict=outcome["verdict"] if outcome else None,
                        failure_type=outcome["failure_type"] if outcome else None,
                        release_lease_worker_id=worker_id if outcome else None,
                        result_summary=result_summary,
                        result_evidence=result_evidence,
                        recording_url=recording_url,
                        result_assets=result_assets,
                        remote_status_code=remote_status_code,
                        remote_step_id=remote_step_id,
                        remote_thread_id=remote_thread_id,
                    )
                    _log(
                        logging.INFO if outcome else logging.DEBUG,
                        "task_runner_event_recorded",
                        task_id=task.id,
                        event_type=event.type,
                        event_sequence=local_event.sequence,
                        local_status=(
                            outcome["status"].value
                            if outcome and outcome.get("status") is not None
                            else None
                        ),
                        verdict=(
                            outcome["verdict"].value
                            if outcome and outcome.get("verdict") is not None
                            else None
                        ),
                        failure_type=outcome["failure_type"] if outcome else None,
                        remote_status_code=remote_status_code,
                    )

                    last_sequence = event.sequence
                    started = started or event.type == "task_started"

                if not page.events and not terminal:
                    await self.clock.sleep(1)
                    continue
        except RunnerFailure as exc:
            return self._record_runner_failure(
                task.id,
                failure_type=exc.failure_type,
                error_code=exc.code,
                request_id=exc.request_id,
                started=started,
            )
        except Exception:
            return self._record_runner_interrupted(
                task.id,
                started=started,
            )

        completed = self.repository.get(task.id)
        if completed is None:
            raise ValueError(f"task_not_found:{task.id}")
        if completed.execution_status == ExecutionStatus.RUNNING:
            return self._record_runner_interrupted(task.id, started=started)
        return completed

    def _record_runner_interrupted(
        self,
        task_id: str,
        *,
        started: bool = False,
    ) -> Task:
        last_sequence = self.repository.last_event_sequence(task_id)
        if not started:
            last_sequence += 1
            self.repository.record_event(
                task_id,
                RunnerEvent(
                    sequence=last_sequence,
                    type="task_started",
                    payload={"task_id": task_id},
                ),
            )
        last_sequence += 1
        self.repository.record_event(
            task_id,
            RunnerEvent(
                sequence=last_sequence,
                type="runner_interrupted",
                payload={"failure_type": "runner_interrupted"},
            ),
            status=ExecutionStatus.RESULT_READY,
            verdict=Verdict.FAIL,
            failure_type="runner_interrupted",
        )
        self.repository.release_lease(task_id, reason="interrupted")
        completed = self.repository.get(task_id)
        if completed is None:
            raise ValueError(f"task_not_found:{task_id}")
        return completed

    def _record_runner_failure(
        self,
        task_id: str,
        *,
        failure_type: str,
        error_code: str,
        request_id: str | None,
        started: bool = False,
    ) -> Task:
        safe_failure_type = (
            failure_type
            if failure_type in {"device_unavailable", "runner_interrupted"}
            else "runner_interrupted"
        )
        last_sequence = self.repository.last_event_sequence(task_id)
        if not started:
            last_sequence += 1
            self.repository.record_event(
                task_id,
                RunnerEvent(
                    sequence=last_sequence,
                    type="task_started",
                    payload={"task_id": task_id},
                ),
            )
        self.repository.record_event(
            task_id,
            RunnerEvent(
                sequence=last_sequence + 1,
                type="runner_interrupted",
                payload={
                    "failure_type": safe_failure_type,
                    "error_code": error_code,
                    "request_id": request_id,
                },
            ),
            status=ExecutionStatus.RESULT_READY,
            verdict=Verdict.FAIL,
            failure_type=safe_failure_type,
        )
        self.repository.release_lease(task_id, reason="interrupted")
        completed = self.repository.get(task_id)
        if completed is None:
            raise ValueError(f"task_not_found:{task_id}")
        return completed

    def _record_device_prepare_started(
        self,
        task_id: str,
        *,
        action: str,
        snapshot: dict[str, Any],
    ) -> None:
        self.repository.record_event(
            task_id,
            RunnerEvent(
                sequence=self.repository.last_event_sequence(task_id) + 1,
                type="device_prepare_started",
                payload={
                    "action": action,
                    "pod_id": snapshot.get("pod_id"),
                    "product_id": snapshot.get("product_id"),
                },
            ),
        )

    def _record_device_prepare_succeeded(
        self,
        task_id: str,
        *,
        action: str,
        result: dict[str, Any] | None,
    ) -> None:
        payload = {"action": action}
        if result:
            for key in ("request_id", "remote_task_id"):
                value = result.get(key)
                if isinstance(value, str):
                    payload[key] = value
        self.repository.record_event(
            task_id,
            RunnerEvent(
                sequence=self.repository.last_event_sequence(task_id) + 1,
                type="device_prepare_succeeded",
                payload=payload,
            ),
        )

    def _record_device_prepare_failure(
        self,
        task_id: str,
        *,
        error_code: str,
        request_id: str | None,
    ) -> Task:
        self.repository.record_event(
            task_id,
            RunnerEvent(
                sequence=self.repository.last_event_sequence(task_id) + 1,
                type="device_prepare_failed",
                payload={
                    "failure_type": "device_prepare_failed",
                    "error_code": error_code,
                    "request_id": request_id,
                },
            ),
            status=ExecutionStatus.RESULT_READY,
            verdict=Verdict.FAIL,
            failure_type="device_prepare_failed",
        )
        self.repository.release_lease(task_id, reason="interrupted")
        completed = self.repository.get(task_id)
        if completed is None:
            raise ValueError(f"task_not_found:{task_id}")
        return completed

    async def _cancel_remote(
        self,
        handle: RunHandle,
        *,
        after_sequence: int,
        dispatched: bool,
        now: datetime,
        deadline: datetime,
    ) -> str:
        if not dispatched:
            self.repository.mark_cancel_dispatched(handle.task_id, now)
            result = await self._required_runner().cancel(handle)
            if not result.accepted:
                return "rejected"
            if result.terminal:
                return "terminal"

        while not _deadline_reached(self.clock.now(), deadline):
            page = await self._required_runner().poll(
                handle,
                after_sequence=after_sequence,
            )
            polled_at = self.clock.now()
            self.repository.mark_cancel_dispatched(handle.task_id, polled_at)
            if page.terminal:
                return "terminal"
            if page.events:
                after_sequence = max(event.sequence for event in page.events)
            await self.clock.sleep(1)
        return "timeout"

    def get_report(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get(task_id)
        if task is None:
            raise ValueError(f"task_not_found:{task_id}")
        if task.execution_status != ExecutionStatus.RESULT_READY:
            raise ValueError(f"report_not_ready:{task_id}")

        case = self._execution_case(task)
        return {
            "task_id": task.id,
            "title": case.title,
            "case_id": case.id,
            "execution_status": task.execution_status,
            "verdict": task.verdict,
            "failure_type": task.failure_type,
            "summary": task.result_summary,
            "evidence": task.result_evidence or [],
            "recording_url": task.recording_url,
            "assets": task.result_assets or {},
        }

    def _execution_case(self, task: Task) -> TestCase:
        case = self.repository.get_case(task.case_id)
        if case is None:
            raise ValueError(f"task_case_not_found:{task.id}")
        return case

    def _required_runner(self) -> RunnerAdapter:
        if self.runner is None:
            raise RuntimeError("runner_not_configured")
        return self.runner


def _terminal_outcome(
    event: RunnerEvent,
) -> dict[str, Any] | None:
    if event.type == "runner_interrupted":
        failure_type = event.payload.get("failure_type")
        if failure_type not in {"device_unavailable", "runner_interrupted"}:
            failure_type = "runner_interrupted"
        return {
            "status": ExecutionStatus.RESULT_READY,
            "verdict": Verdict.FAIL,
            "failure_type": failure_type,
        }
    if event.type == "task_cancelled":
        return {
            "status": ExecutionStatus.CANCELLED,
            "verdict": None,
            "failure_type": None,
        }
    if event.type != "task_finished":
        return None

    verdict = event.payload.get("verdict")
    evidence_complete = bool(event.payload.get("evidence_complete"))
    if verdict == "pass" and evidence_complete:
        return {
            "status": ExecutionStatus.RESULT_READY,
            "verdict": Verdict.PASS,
            "failure_type": None,
        }
    return {
        "status": ExecutionStatus.RESULT_READY,
        "verdict": Verdict.FAIL,
        "failure_type": event.payload.get("failure_type") or "assertion_failed",
    }


def _deadline_reached(now: datetime, deadline: datetime | None) -> bool:
    if deadline is None:
        return False
    return _utc_naive(now) >= _utc_naive(deadline)


def _device_prepare_action(snapshot: dict[str, Any]) -> str:
    action = snapshot.get("device_prepare_action")
    return action if action in {"reset", "reboot"} else "none"


def _runner_sequence_offset(task: Task) -> int:
    return sum(
        1
        for event in task.events
        if event.event_type in {
            "device_prepare_started",
            "device_prepare_succeeded",
        }
    )


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)
