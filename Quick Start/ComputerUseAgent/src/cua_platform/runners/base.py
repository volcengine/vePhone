from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

from cua_platform.diagnostics.schemas import PodDiagnostic, ValidationResult
from cua_platform.settings.schemas import RunnerConfig


@dataclass(frozen=True)
class RunRequest:
    task_id: str
    scenario: str
    title: str
    content_markdown: str
    preconditions: list[str] | None = None
    steps: list[dict[str, Any]] | None = None
    assertions: list[dict[str, Any]] | None = None


class RunnerFailure(RuntimeError):
    def __init__(
        self,
        code: str,
        failure_type: str,
        request_id: str | None = None,
        *,
        start_outcome_unknown: bool = False,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.failure_type = failure_type
        self.request_id = request_id
        self.start_outcome_unknown = start_outcome_unknown


@dataclass(frozen=True)
class RunnerEvent:
    sequence: int
    type: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class RunHandle:
    task_id: str
    runner_type: str
    run_id: str
    thread_id: str | None = None


@dataclass(frozen=True)
class PollResult:
    events: tuple[RunnerEvent, ...]
    terminal: bool


@dataclass(frozen=True)
class CancelResult:
    accepted: bool
    terminal: bool
    error_code: str | None = None


class RunnerAdapter(Protocol):
    async def validate(self, config: RunnerConfig) -> ValidationResult: ...

    async def list_pods(self, config: RunnerConfig) -> tuple[PodDiagnostic, ...]: ...

    async def start(
        self,
        request: RunRequest,
        idempotency_key: str,
    ) -> RunHandle: ...

    async def poll(
        self,
        handle: RunHandle,
        after_sequence: int,
    ) -> PollResult: ...

    async def cancel(self, handle: RunHandle) -> CancelResult: ...

    def run(self, request: RunRequest) -> AsyncIterator[RunnerEvent]: ...
