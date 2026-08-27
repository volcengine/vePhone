import hashlib
import logging
import re
from collections.abc import Callable, Mapping
from typing import Any

from cua_platform.runners.base import (
    CancelResult,
    PollResult,
    RunHandle,
    RunRequest,
    RunnerEvent,
    RunnerFailure,
)
from cua_platform.runners.mobile_use_parser import (
    ParsedResult,
    parse_agent_result,
    parse_step_signal,
    step_status_is_terminal,
)
from cua_platform.runners.mobile_use_prompt import (
    MAX_USER_PROMPT_LENGTH,
    SYSTEM_PROMPT,
    render_user_prompt,
)
from cua_platform.runners.universal_gateway import (
    UniversalGateway,
    UniversalRemoteError,
)
from cua_platform.settings.schemas import RunnerConfig
from cua_platform.time import Clock, SystemClock

RunRequestLoader = Callable[[str], RunRequest | None]

_TOS_REGION = re.compile(r"^[a-z]{2}-[a-z]+(?:-\d+)?$")
_DEVICE_ERROR_CODES = frozenset({"pod_not_found", "pod_unavailable"})
_REMOTE_TASK_ACTIVE_STATUSES = frozenset({1, 2, 4})
_REMOTE_TASK_COMPLETED_STATUS = 3
_REMOTE_TASK_CANCELLED_STATUS = 5
_REMOTE_TASK_FAILED_STATES = {
    6: "failed",
    7: "interrupted",
}
logger = logging.getLogger("cua_platform.mobile_use")


def _log(level: int, event: str, **fields: object) -> None:
    try:
        logger.log(level, event, extra=fields)
    except Exception:
        pass


class MobileUseRunner:
    runner_type = "mobile_use"

    def __init__(
        self,
        config: RunnerConfig,
        gateway: UniversalGateway,
        *,
        request_loader: RunRequestLoader,
        clock: Clock | None = None,
        poll_interval: float = 1.0,
    ) -> None:
        self._config = config
        self._gateway = gateway
        self._request_loader = request_loader
        self._clock = clock or SystemClock()
        self._poll_interval = poll_interval

    async def start(
        self,
        request: RunRequest,
        idempotency_key: str,
    ) -> RunHandle:
        self._validate_config()
        prompt = render_user_prompt(request)
        if len(prompt) > MAX_USER_PROMPT_LENGTH:
            raise RunnerFailure(
                "mobile_use_prompt_too_long",
                "runner_interrupted",
            )
        payload = {
            "RunName": f"task_{request.task_id}"[:127],
            "ThreadId": self._config.thread_id
            or "cua-"
            + hashlib.sha256(idempotency_key.encode()).hexdigest()[:48],
            "AgentType": "cua",
            "Ecsid": self._config.pod_id,
            "UserPrompt": prompt,
            "SystemPrompt": self._config.system_prompt or SYSTEM_PROMPT,
            "MaxStep": self._config.max_step,
            "Timeout": self._config.timeout_seconds,
            "RetryLimit": self._config.retry_limit,
        }
        _set_if_present(payload, "TosBucket", self._config.tos_bucket)
        if self._config.tos_endpoint:
            _set_if_present(payload, "TosEndpoint", self._config.tos_endpoint)
        elif self._config.tos_region:
            _set_if_present(payload, "TosEndpoint", f"tos-{self._config.tos_region}.volces.com")
        _set_if_present(payload, "TosRegion", self._config.tos_region)
        _set_if_present(payload, "CallbackInfo", self._config.callback_info)
        _set_if_present(payload, "OutputSchema", self._config.output_schema)
        _set_if_present(payload, "McpJson", self._config.mcp_json)
        _set_if_present(payload, "MaxOutputTokens", self._config.max_output_tokens)
        try:
            remote = await self._gateway.start_one_step(self._config, payload)
        except UniversalRemoteError as exc:
            raise _runner_failure(exc) from None
        if not remote.run_id:
            raise RunnerFailure(
                "response_invalid",
                "runner_interrupted",
                remote.request_id,
                start_outcome_unknown=True,
            )
        _log(
            logging.INFO,
            "mobile_use_task_started_remote",
            task_id=request.task_id,
            run_id=remote.run_id,
            thread_id=remote.thread_id,
            request_id=remote.request_id,
        )
        return RunHandle(request.task_id, self.runner_type, remote.run_id, remote.thread_id)

    async def poll(
        self,
        handle: RunHandle,
        after_sequence: int,
    ) -> PollResult:
        self._validate_handle(handle)
        self._validate_config()
        request = self._request_loader(handle.task_id)
        if request is None or request.task_id != handle.task_id:
            raise RunnerFailure(
                "mobile_use_request_unavailable",
                "runner_interrupted",
            )
        try:
            task_status = await self._remote_task_status(handle)
            if task_status is not None:
                _log(
                    logging.INFO,
                    "mobile_use_remote_task_status",
                    task_id=handle.task_id,
                    run_id=handle.run_id,
                    thread_id=handle.thread_id,
                    remote_status_code=task_status,
                    decision=_task_status_decision(task_status),
                )
            if task_status in _REMOTE_TASK_ACTIVE_STATUSES:
                events = (
                    RunnerEvent(1, "task_started", {"task_id": handle.task_id}),
                )
                return PollResult(
                    events=_after(events, after_sequence),
                    terminal=False,
                )
            if task_status == _REMOTE_TASK_CANCELLED_STATUS:
                events = (
                    RunnerEvent(1, "task_started", {"task_id": handle.task_id}),
                    RunnerEvent(
                        2,
                        "task_cancelled",
                        {
                            "remote_status_code": task_status,
                            "remote_state": "cancelled",
                        },
                    ),
                )
                return PollResult(
                    events=_after(events, after_sequence),
                    terminal=True,
                )
            if task_status in _REMOTE_TASK_FAILED_STATES:
                events = (
                    RunnerEvent(1, "task_started", {"task_id": handle.task_id}),
                    RunnerEvent(
                        2,
                        "runner_interrupted",
                        {
                            "failure_type": "runner_interrupted",
                            "remote_status_code": task_status,
                            "remote_state": _REMOTE_TASK_FAILED_STATES[task_status],
                        },
                    ),
                )
                return PollResult(
                    events=_after(events, after_sequence),
                    terminal=True,
                )
            if task_status != _REMOTE_TASK_COMPLETED_STATUS:
                current = await self._gateway.list_current_step(
                    self._config,
                    handle.run_id,
                )
                signal = parse_step_signal(current.payload)
                _log(
                    logging.DEBUG,
                    "mobile_use_current_step_status",
                    task_id=handle.task_id,
                    run_id=handle.run_id,
                    step_status=_current_step_status(current.payload),
                    step_terminal=step_status_is_terminal(current.payload),
                    signal=signal.signal,
                    request_id=current.request_id,
                )
                if not signal.done and not step_status_is_terminal(current.payload):
                    events = (
                        RunnerEvent(1, "task_started", {"task_id": handle.task_id}),
                    )
                    return PollResult(
                        events=_after(events, after_sequence),
                        terminal=False,
                    )

            remote = await self._gateway.get_result(self._config, handle.run_id)
        except UniversalRemoteError as exc:
            raise _runner_failure(exc) from None
        parsed = parse_agent_result(remote.payload)
        _log(
            logging.INFO,
            "mobile_use_result_status",
            task_id=handle.task_id,
            run_id=handle.run_id,
            remote_terminal=parsed.remote_terminal,
            remote_state=parsed.remote_state,
            remote_status_code=parsed.remote_status_code,
            verdict=parsed.verdict,
            failure_type=parsed.failure_type,
            request_id=remote.request_id,
        )
        if not parsed.remote_terminal:
            return PollResult(events=(), terminal=False)
        events = self._terminal_events(request, parsed)
        return PollResult(
            events=_after(events, after_sequence),
            terminal=True,
        )

    async def _remote_task_status(self, handle: RunHandle) -> int | None:
        try:
            remote = await self._gateway.list_task_by_thread(
                self._config,
                thread_id=handle.thread_id,
                run_id=handle.run_id,
            )
        except UniversalRemoteError:
            _log(
                logging.WARNING,
                "mobile_use_remote_task_status_failed",
                task_id=handle.task_id,
                run_id=handle.run_id,
                thread_id=handle.thread_id,
            )
            return None
        return _task_status(remote.payload, handle.run_id)

    async def cancel(self, handle: RunHandle) -> CancelResult:
        self._validate_handle(handle)
        self._validate_config()
        try:
            result = await self._gateway.cancel(self._config, handle.run_id)
        except UniversalRemoteError as exc:
            return CancelResult(
                accepted=False,
                terminal=False,
                error_code=exc.code,
            )
        return CancelResult(accepted=result.accepted, terminal=False)

    @staticmethod
    def _terminal_events(
        request: RunRequest,
        parsed: ParsedResult,
    ) -> tuple[RunnerEvent, ...]:
        events = [
            RunnerEvent(1, "task_started", {"task_id": request.task_id}),
        ]
        if parsed.remote_state == "user_cancelled":
            payload = {
                "remote_state": parsed.remote_state,
            }
            if parsed.recording_url:
                payload["recording_url"] = parsed.recording_url
            if parsed.result_assets:
                payload["result_assets"] = dict(parsed.result_assets)
            if parsed.remote_status_code is not None:
                payload["remote_status_code"] = parsed.remote_status_code
            if parsed.remote_step_id:
                payload["remote_step_id"] = parsed.remote_step_id
            if parsed.remote_thread_id:
                payload["remote_thread_id"] = parsed.remote_thread_id
            events.append(
                RunnerEvent(
                    2,
                    "task_cancelled",
                    payload,
                )
            )
            return tuple(events)

        if parsed.failure_type == "runner_interrupted":
            payload = {
                "failure_type": "runner_interrupted",
                "remote_state": parsed.remote_state,
            }
            if parsed.summary:
                payload["summary"] = parsed.summary
            if parsed.evidence:
                payload["evidence"] = list(parsed.evidence)
            if parsed.recording_url:
                payload["recording_url"] = parsed.recording_url
            if parsed.result_assets:
                payload["result_assets"] = dict(parsed.result_assets)
            if parsed.remote_status_code is not None:
                payload["remote_status_code"] = parsed.remote_status_code
            if parsed.remote_step_id:
                payload["remote_step_id"] = parsed.remote_step_id
            if parsed.remote_thread_id:
                payload["remote_thread_id"] = parsed.remote_thread_id
            events.append(
                RunnerEvent(
                    2,
                    "runner_interrupted",
                    payload,
                )
            )
            return tuple(events)

        events.append(
            RunnerEvent(
                2,
                "task_finished",
                {
                    "verdict": parsed.verdict,
                    "summary": parsed.summary,
                    "evidence": list(parsed.evidence),
                    "evidence_complete": parsed.evidence_complete,
                    "remote_state": parsed.remote_state,
                    "failure_type": parsed.failure_type,
                    "reason": parsed.reason,
                    "recording_url": parsed.recording_url,
                    "result_assets": dict(parsed.result_assets),
                    "remote_status_code": parsed.remote_status_code,
                    "remote_step_id": parsed.remote_step_id,
                    "remote_thread_id": parsed.remote_thread_id,
                },
            )
        )
        return tuple(events)

    def _validate_config(self) -> None:
        values = (
            self._config.access_key_id,
            self._config.secret_access_key,
            self._config.account_id,
            self._config.pod_id,
        )
        if (
            self._config.mode != self.runner_type
            or any(not isinstance(value, str) or not value for value in values)
            or (
                self._config.tos_region is not None
                and _TOS_REGION.fullmatch(self._config.tos_region) is None
            )
        ):
            raise RunnerFailure(
                "mobile_use_config_invalid",
                "runner_interrupted",
            )

    def _validate_handle(self, handle: RunHandle) -> None:
        if (
            handle.runner_type != self.runner_type
            or not handle.task_id
            or not handle.run_id
        ):
            raise RunnerFailure(
                "mobile_use_handle_invalid",
                "runner_interrupted",
            )


def _runner_failure(exc: UniversalRemoteError) -> RunnerFailure:
    failure_type = (
        "device_unavailable"
        if exc.code in _DEVICE_ERROR_CODES
        else "runner_interrupted"
    )
    return RunnerFailure(
        exc.code,
        failure_type,
        exc.request_id,
        start_outcome_unknown=(
            not exc.response_received or exc.code == "response_invalid"
        ),
    )


def _task_status(payload: object, run_id: str) -> int | None:
    data = _result_mapping(payload)
    if data is None:
        return None
    for task in _task_items(data):
        if _string_value(task.get("RunId")) != run_id:
            continue
        return _int_value(task.get("Status"))
    return None


def _task_status_decision(status: int) -> str:
    if status in _REMOTE_TASK_ACTIVE_STATUSES:
        return "running"
    if status == _REMOTE_TASK_COMPLETED_STATUS:
        return "fetch_result"
    if status == _REMOTE_TASK_CANCELLED_STATUS:
        return "cancelled"
    if status in _REMOTE_TASK_FAILED_STATES:
        return "failed"
    return "fallback"


def _current_step_status(payload: object) -> int | None:
    data = _result_mapping(payload)
    if data is None:
        return None
    return _int_value(data.get("Status"))


def _result_mapping(payload: object) -> Mapping[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    result = payload.get("Result")
    if isinstance(result, Mapping):
        return result
    return payload


def _task_items(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    items: list[Mapping[str, Any]] = []
    for key in ("Tasks", "TaskList", "Items"):
        value = payload.get(key)
        if isinstance(value, list):
            items.extend(item for item in value if isinstance(item, Mapping))
    groups = payload.get("ThreadGroups")
    if isinstance(groups, list):
        for group in groups:
            if not isinstance(group, Mapping):
                continue
            tasks = group.get("Tasks")
            if isinstance(tasks, list):
                items.extend(item for item in tasks if isinstance(item, Mapping))
    return tuple(items)


def _string_value(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _int_value(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isascii() and stripped.isdecimal():
            return int(stripped)
    return None


def _set_if_present(payload: dict, key: str, value: object | None) -> None:
    if value is not None:
        payload[key] = value


def _after(
    events: tuple[RunnerEvent, ...],
    sequence: int,
) -> tuple[RunnerEvent, ...]:
    return tuple(event for event in events if event.sequence > sequence)
