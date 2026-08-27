import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

StepSignalName = Literal["finished", "request_user"]
_TERMINAL_STEP_STATUSES = frozenset({3, 6})
RemoteState = Literal[
    "not_completed",
    "success",
    "completed_no_message",
    "exec_failed",
    "user_interrupt",
    "user_cancelled",
    "unknown_error",
]
Verdict = Literal["pass", "fail"]


@dataclass(frozen=True)
class StepSignal:
    done: bool
    signal: StepSignalName | None
    hint: str | None


@dataclass(frozen=True)
class ParsedResult:
    remote_terminal: bool
    remote_state: RemoteState
    remote_status_code: int | None
    remote_step_id: str | None
    remote_thread_id: str | None
    verdict: Verdict | None
    failure_type: str | None
    reason: str | None
    summary: str | None
    evidence: tuple[str, ...]
    evidence_complete: bool
    recording_url: str | None
    result_assets: Mapping[str, Any]


_REMOTE_STATES: dict[int, RemoteState] = {
    0: "not_completed",
    1: "success",
    2: "exec_failed",
    3: "completed_no_message",
    4: "user_interrupt",
    5: "user_cancelled",
    6: "unknown_error",
}
_INTERRUPTED_STATES = frozenset({2, 4, 6})
_INVALID_RESULT = ParsedResult(
    remote_terminal=False,
    remote_state="not_completed",
    remote_status_code=0,
    remote_step_id=None,
    remote_thread_id=None,
    verdict=None,
    failure_type=None,
    reason=None,
    summary=None,
    evidence=(),
    evidence_complete=False,
    recording_url=None,
    result_assets={},
)
_MISSING = object()


def parse_step_signal(payload: object) -> StepSignal:
    data = _step_payload(payload)
    if data is None:
        return StepSignal(False, None, None)
    results = data.get("Results")
    if not isinstance(results, list):
        return StepSignal(False, None, None)
    for item in results:
        if not isinstance(item, Mapping):
            continue
        request_hint = _find_request_user(item.get("Param"))
        if request_hint is None:
            request_hint = _find_request_user(item.get("StepResult"))
        if item.get("Action") == "request_user" or request_hint is not None:
            hint = request_hint or _hint_from_param(item.get("Param"))
            return StepSignal(True, "request_user", hint)
        if item.get("Action") == "finished":
            return StepSignal(True, "finished", _hint_from_param(item.get("Param")))
    return StepSignal(False, None, None)


def step_status_is_terminal(payload: object) -> bool:
    data = _step_payload(payload)
    if data is None:
        return False
    status = data.get("Status")
    if isinstance(status, bool):
        return False
    if isinstance(status, int):
        return status in _TERMINAL_STEP_STATUSES
    if isinstance(status, str):
        stripped = status.strip()
        return (
            stripped.isascii()
            and stripped.isdecimal()
            and int(stripped) in _TERMINAL_STEP_STATUSES
        )
    return False


def parse_agent_result(payload: object) -> ParsedResult:
    data = _result_payload(payload)
    if data is None:
        return _INVALID_RESULT
    is_success = _coerce_is_success(data.get("IsSuccess"))
    if is_success is None:
        return _INVALID_RESULT

    remote_state = _REMOTE_STATES[is_success]
    remote_status_code = is_success
    remote_step_id = _safe_string(data.get("StepId"))
    remote_thread_id = _safe_string(data.get("ThreadId"))
    if is_success == 0:
        return _INVALID_RESULT
    if is_success in _INTERRUPTED_STATES:
        summary = _content_summary(data)
        evidence = (summary,) if summary else ()
        return ParsedResult(
            remote_terminal=True,
            remote_state=remote_state,
            remote_status_code=remote_status_code,
            remote_step_id=remote_step_id,
            remote_thread_id=remote_thread_id,
            verdict="fail",
            failure_type="runner_interrupted",
            reason=summary,
            summary=summary,
            evidence=evidence,
            evidence_complete=bool(evidence),
            recording_url=_safe_string(data.get("RecordingUrl")),
            result_assets=_result_assets(data),
        )
    if is_success == 5:
        return ParsedResult(
            remote_terminal=True,
            remote_state=remote_state,
            remote_status_code=remote_status_code,
            remote_step_id=remote_step_id,
            remote_thread_id=remote_thread_id,
            verdict=None,
            failure_type=None,
            reason=None,
            summary=None,
            evidence=(),
            evidence_complete=False,
            recording_url=_safe_string(data.get("RecordingUrl")),
            result_assets=_result_assets(data),
        )

    output = _structured_output(data)
    if output is None and is_success == 1:
        output = _relaxed_structured_output(data)
    if output is None:
        return _evidence_missing(remote_state, data)

    verdict_raw = output.get("verdict")
    if verdict_raw is None:
        verdict_raw = _verdict_from_status(output.get("status") or output.get("Status"))
    if verdict_raw not in {"pass", "fail", "inconclusive"}:
        return _evidence_missing(remote_state, data)

    verdict: Verdict = "fail" if verdict_raw == "inconclusive" else verdict_raw
    summary = output.get("summary")
    if summary is None:
        summary = output.get("reason") or output.get("Reason")
    safe_summary = summary if isinstance(summary, str) else None
    evidence = _string_tuple(output.get("evidence"))
    reason = output.get("reason")
    safe_reason = reason if isinstance(reason, str) else None
    evidence_complete = bool(evidence)

    failure_type = None if verdict == "pass" else "assertion_failed"

    return ParsedResult(
        remote_terminal=True,
        remote_state=remote_state,
        remote_status_code=remote_status_code,
        remote_step_id=remote_step_id,
        remote_thread_id=remote_thread_id,
        verdict=verdict,
        failure_type=failure_type,
        reason=safe_reason,
        summary=safe_summary,
        evidence=evidence,
        evidence_complete=evidence_complete,
        recording_url=_safe_string(data.get("RecordingUrl")),
        result_assets=_result_assets(data),
    )


def _step_payload(payload: object) -> Mapping[str, Any] | None:
    if not isinstance(payload, Mapping) or "Error" in payload:
        return None
    if "Result" in payload:
        result = payload.get("Result")
        if not isinstance(result, Mapping) or "Error" in result:
            return None
        return result
    return payload if "Results" in payload else None


def _result_payload(payload: object) -> Mapping[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    if "Result" in payload:
        result = payload.get("Result")
        if not isinstance(result, Mapping):
            return None
        payload = result
    if not any(key in payload for key in ("IsSuccess", "Content", "StructOutput")):
        return None
    return payload


def _coerce_is_success(value: object) -> int | None:
    if isinstance(value, bool):
        parsed = int(value)
    elif isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped.isascii() or not stripped.isdecimal():
            return None
        parsed = int(stripped)
    else:
        return None
    return parsed if parsed in _REMOTE_STATES else None


def _structured_output(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    struct_output = payload.get("StructOutput", _MISSING)
    if struct_output is not _MISSING:
        parsed = _json_object(struct_output)
        if parsed is not None:
            return parsed
    content = payload.get("Content")
    if not isinstance(content, str):
        return None
    fenced = _last_fenced_json_object(content)
    if fenced is not None:
        return fenced
    return _last_json_object(content)


def _last_fenced_json_object(content: str) -> Mapping[str, Any] | None:
    text = _last_fenced_json_text(content)
    return _json_object(text.strip()) if text is not None else None


def _last_fenced_json_text(content: str) -> str | None:
    stripped = content.strip()
    fence_end = stripped.rfind("```")
    if fence_end <= 0:
        return None
    fence_start = stripped.rfind("```", 0, fence_end)
    if fence_start < 0:
        return None
    header_end = stripped.find("\n", fence_start, fence_end)
    if header_end < 0:
        return None
    language = stripped[fence_start + 3 : header_end].strip().lower()
    if language not in {"", "json"}:
        return None
    return stripped[header_end + 1 : fence_end]


def _relaxed_structured_output(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    content = payload.get("Content")
    if not isinstance(content, str):
        return None
    text = _last_fenced_json_text(content) or _last_json_like_text(content)
    if text is None:
        return None
    verdict = _relaxed_verdict(text)
    evidence = _relaxed_evidence(text)
    if verdict is None or not evidence:
        return None
    output: dict[str, Any] = {
        "verdict": verdict,
        "evidence": evidence,
    }
    summary = _relaxed_string_field(text, "summary")
    if summary:
        output["summary"] = summary
    reason = _relaxed_string_field(text, "reason")
    if reason:
        output["reason"] = reason
    return output


def _last_json_like_text(content: str) -> str | None:
    stripped = content.strip()
    if not stripped.endswith("}"):
        return None
    verdict_index = stripped.rfind('"verdict"')
    if verdict_index < 0:
        verdict_index = stripped.rfind('"status"')
    if verdict_index < 0:
        return None
    start = stripped.rfind("{", 0, verdict_index)
    return stripped[start:] if start >= 0 else None


def _relaxed_verdict(text: str) -> str | None:
    for key in ("verdict", "status", "Status"):
        match = re.search(
            rf'(?m)^\s*"{re.escape(key)}"\s*:\s*"(pass|fail|inconclusive)"\s*,?\s*$',
            text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).lower()
    return None


def _relaxed_string_field(text: str, key: str) -> str | None:
    prefix = f'"{key}"'
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith(prefix):
            continue
        separator = stripped.find(":")
        if separator < 0:
            continue
        raw_value = stripped[separator + 1 :].strip()
        if raw_value.endswith(","):
            raw_value = raw_value[:-1].rstrip()
        try:
            value = json.loads(raw_value)
        except (json.JSONDecodeError, ValueError):
            value = None
        if isinstance(value, str) and value.strip():
            return value.strip()
        if len(raw_value) >= 2 and raw_value[0] == '"' and raw_value[-1] == '"':
            value = raw_value[1:-1].strip()
            if value:
                return value
    return None


def _relaxed_evidence(text: str) -> list[str]:
    lines = text.splitlines()
    collecting = False
    evidence: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not collecting:
            if re.match(r'^"evidence"\s*:\s*\[', stripped):
                collecting = True
            continue
        if stripped.startswith("]"):
            break
        if not stripped:
            continue
        if stripped.endswith(","):
            stripped = stripped[:-1].rstrip()
        if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
            item = stripped[1:-1].strip()
            if item:
                evidence.append(item)
    return evidence


def _verdict_from_status(value: object) -> Verdict | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized == "pass":
        return "pass"
    if normalized == "fail":
        return "fail"
    if normalized in {"skip", "inconclusive"}:
        return "fail"
    return None


def _content_summary(payload: Mapping[str, Any]) -> str | None:
    content = payload.get("Content")
    if not isinstance(content, str):
        return None
    summary = _sanitize_hint(content)
    return summary.strip() if summary else None


def _safe_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _result_assets(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    assets: dict[str, Any] = {}
    screenshots = payload.get("ScreenShots")
    if isinstance(screenshots, Mapping):
        assets["screenshots"] = dict(screenshots)
    usage = payload.get("Usage")
    if isinstance(usage, Mapping):
        assets["usage"] = dict(usage)
    files = payload.get("Files")
    if isinstance(files, list):
        assets["files"] = [item for item in files if isinstance(item, str)]
    content = payload.get("Content")
    if isinstance(content, str) and content.strip():
        assets["content"] = content.strip()
    struct_output = payload.get("StructOutput")
    if isinstance(struct_output, Mapping):
        assets["struct_output"] = dict(struct_output)
    _copy_int_asset(assets, payload, "total_steps", "TotalSteps", "total_steps")
    _copy_int_asset(assets, payload, "duration_ms", "DurationMs", "duration_ms")
    _copy_string_asset(assets, payload, "duration_fmt", "DurationFmt", "duration_fmt")
    _copy_int_asset(
        assets,
        payload,
        "avg_step_duration_sec",
        "AvgStepDurationSec",
        "avg_step_duration_sec",
    )
    return assets


def _copy_int_asset(
    assets: dict[str, Any],
    payload: Mapping[str, Any],
    target: str,
    *keys: str,
) -> None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            assets[target] = value
            return


def _copy_string_asset(
    assets: dict[str, Any],
    payload: Mapping[str, Any],
    target: str,
    *keys: str,
) -> None:
    for key in keys:
        value = _safe_string(payload.get(key))
        if value:
            assets[target] = value
            return


def _json_object(value: object) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    if not isinstance(value, str):
        return None
    try:
        decoded = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return None
    return decoded if isinstance(decoded, Mapping) else None


def _last_json_object(content: str) -> Mapping[str, Any] | None:
    end = len(content.rstrip()) - 1
    if end < 0 or content[end] != "}":
        return None
    depth = 0
    in_string = False
    for start in range(end, -1, -1):
        character = content[start]
        if character == '"' and not _is_escaped(content, start):
            in_string = not in_string
            continue
        if in_string:
            continue
        if character == "}":
            depth += 1
            continue
        if character != "{":
            continue
        depth -= 1
        if depth < 0:
            return None
        if depth != 0:
            continue
        try:
            decoded = json.loads(content[start : end + 1])
        except (json.JSONDecodeError, ValueError):
            return None
        return decoded if isinstance(decoded, Mapping) else None
    return None


def _is_escaped(content: str, index: int) -> bool:
    backslashes = 0
    index -= 1
    while index >= 0 and content[index] == "\\":
        backslashes += 1
        index -= 1
    return backslashes % 2 == 1


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    result = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
    return tuple(result)


def _evidence_missing(
    remote_state: RemoteState,
    payload: Mapping[str, Any],
) -> ParsedResult:
    summary = _content_summary(payload)
    failure_type = "evidence_missing"
    if remote_state == "completed_no_message":
        summary = summary or "执行成功，但未返回 Content。"
        failure_type = "completed_but_no_message"
    return ParsedResult(
        remote_terminal=True,
        remote_state=remote_state,
        remote_status_code=_status_code_for_state(remote_state),
        remote_step_id=_safe_string(payload.get("StepId")),
        remote_thread_id=_safe_string(payload.get("ThreadId")),
        verdict="fail",
        failure_type=failure_type,
        reason=None,
        summary=summary,
        evidence=(),
        evidence_complete=False,
        recording_url=_safe_string(payload.get("RecordingUrl")),
        result_assets=_result_assets(payload),
    )


def _status_code_for_state(remote_state: RemoteState) -> int | None:
    for code, state in _REMOTE_STATES.items():
        if state == remote_state:
            return code
    return None


def _find_request_user(value: object, depth: int = 0) -> str | None:
    if depth > 8:
        return None
    if isinstance(value, Mapping):
        direct = value.get("request_user")
        if isinstance(direct, str):
            return _sanitize_hint(direct)
        for nested in value.values():
            hint = _find_request_user(nested, depth + 1)
            if hint is not None:
                return hint
        return None
    if isinstance(value, list):
        for nested in value:
            hint = _find_request_user(nested, depth + 1)
            if hint is not None:
                return hint
        return None
    if not isinstance(value, str):
        return None
    try:
        decoded = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return None
    return _find_request_user(decoded, depth + 1)


def _hint_from_param(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    for key in ("request_user", "content"):
        hint = value.get(key)
        if isinstance(hint, str):
            return _sanitize_hint(hint)
    return None


def _sanitize_hint(value: str) -> str | None:
    sanitized = "".join(
        character for character in value if unicodedata.category(character)[0] != "C"
    )[:500]
    return sanitized or None
