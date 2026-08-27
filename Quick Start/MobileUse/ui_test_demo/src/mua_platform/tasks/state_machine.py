from enum import StrEnum


class ExecutionStatus(StrEnum):
    SCRIPT_PENDING = "script_pending"
    QUEUED = "queued"
    RUNNING = "running"
    RESULT_READY = "result_ready"
    CANCELLED = "cancelled"


class StartState(StrEnum):
    PENDING = "pending"
    DISPATCHING = "dispatching"
    ATTACHED = "attached"


class Verdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"


TERMINAL_STATUSES = {
    ExecutionStatus.RESULT_READY,
    ExecutionStatus.CANCELLED,
}

TERMINAL_OUTCOMES = {
    ExecutionStatus.RESULT_READY: {Verdict.PASS, Verdict.FAIL},
    ExecutionStatus.CANCELLED: {None},
}
CANCELLABLE_STATUSES = {
    ExecutionStatus.QUEUED,
    ExecutionStatus.RUNNING,
}


ALLOWED_TRANSITIONS = {
    ExecutionStatus.SCRIPT_PENDING: {ExecutionStatus.QUEUED},
    ExecutionStatus.QUEUED: {
        ExecutionStatus.RUNNING,
        ExecutionStatus.RESULT_READY,
        ExecutionStatus.CANCELLED,
    },
    ExecutionStatus.RUNNING: {
        ExecutionStatus.RESULT_READY,
        ExecutionStatus.CANCELLED,
    },
}


def transition(
    current: ExecutionStatus,
    target: ExecutionStatus,
) -> ExecutionStatus:
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"invalid_transition:{current.value}->{target.value}")
    return target


def derive_verdict(
    must_results: list[str],
    evidence_complete: bool,
) -> Verdict:
    if (
        not evidence_complete
        or not must_results
        or any(result not in {"pass", "fail"} for result in must_results)
    ):
        return Verdict.FAIL
    if any(result == "fail" for result in must_results):
        return Verdict.FAIL
    return Verdict.PASS


def validate_terminal_outcome(
    status: ExecutionStatus,
    verdict: Verdict | None,
) -> None:
    if verdict not in TERMINAL_OUTCOMES.get(status, set()):
        verdict_value = verdict.value if verdict is not None else "none"
        raise ValueError(
            f"invalid_terminal_outcome:{status.value}+{verdict_value}"
        )
