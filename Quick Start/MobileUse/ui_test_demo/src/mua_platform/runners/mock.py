import base64
import binascii
import hashlib
import hmac
import json
import zlib
from collections.abc import AsyncIterator
from dataclasses import asdict

from mua_platform.diagnostics.schemas import (
    PodDiagnostic,
    ValidationCheck,
    ValidationResult,
)
from mua_platform.runners.base import (
    CancelResult,
    PollResult,
    RunHandle,
    RunRequest,
    RunnerEvent,
)
from mua_platform.settings.schemas import RunnerConfig

SUPPORTED_SCENARIOS = {
    "success",
    "assertion_failure",
    "runner_interrupted",
    "evidence_missing",
}
MAX_REQUEST_LIST_ITEMS = 100
MAX_HANDLE_LENGTH = 16_384
MAX_DECOMPRESSED_HANDLE_BYTES = 65_536


class MockRunner:
    runner_type = "mock"

    def __init__(self, hmac_key: str | bytes):
        self._hmac_key = hmac_key.encode() if isinstance(hmac_key, str) else hmac_key

    async def validate(self, _config: RunnerConfig) -> ValidationResult:
        return ValidationResult(
            runner_mode="mock",
            status="passed",
            checks=(
                ValidationCheck(
                    name="credentials",
                    status="passed",
                    code="credentials_valid",
                    message="Mock 凭证校验通过",
                    request_id=None,
                ),
                ValidationCheck(
                    name="runner_api",
                    status="passed",
                    code="runner_api_reachable",
                    message="Mock Runner API 可调用",
                    request_id=None,
                ),
                ValidationCheck(
                    name="pod",
                    status="passed",
                    code="pod_available",
                    message="Mock Pod 可用于执行",
                    request_id=None,
                ),
            ),
        )

    async def list_pods(self, _config: RunnerConfig) -> tuple[PodDiagnostic, ...]:
        return (
            PodDiagnostic(
                pod_id="mock:default",
                status="available",
                product_id="mock:default",
                code="pod_available",
                message="Mock Pod 可用于执行",
                request_id=None,
            ),
        )

    async def prepare_device(self, _request: RunRequest) -> dict[str, object] | None:
        return None

    async def start(
        self,
        request: RunRequest,
        idempotency_key: str,
    ) -> RunHandle:
        self._validate_request(request)
        payload = {
            "idempotency_key": idempotency_key,
            "request": asdict(request),
        }
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        if len(serialized) > MAX_DECOMPRESSED_HANDLE_BYTES:
            raise ValueError("mock_request_limit_exceeded")
        compressed = zlib.compress(serialized)
        payload_token = base64.urlsafe_b64encode(compressed).decode().rstrip("=")
        signature = hmac.new(
            self._hmac_key,
            compressed,
            hashlib.sha256,
        ).hexdigest()
        run_id = f"mock_{payload_token}.{signature}"
        if len(run_id) > MAX_HANDLE_LENGTH:
            raise ValueError("mock_request_limit_exceeded")
        return RunHandle(
            task_id=request.task_id,
            runner_type=self.runner_type,
            run_id=run_id,
        )

    async def poll(
        self,
        handle: RunHandle,
        after_sequence: int,
    ) -> PollResult:
        request = self._request_from_handle(handle)
        events = tuple(
            event
            for event in self._build_events(request)
            if event.sequence > after_sequence
        )
        return PollResult(events=events, terminal=True)

    async def cancel(self, handle: RunHandle) -> CancelResult:
        self._request_from_handle(handle)
        return CancelResult(accepted=True, terminal=True)

    async def run(self, request: RunRequest) -> AsyncIterator[RunnerEvent]:
        for runner_event in self._build_events(request):
            yield runner_event

    def _build_events(self, request: RunRequest) -> tuple[RunnerEvent, ...]:
        self._validate_request(request)
        events: list[RunnerEvent] = []
        sequence = 0

        def event(event_type: str, payload: dict) -> RunnerEvent:
            nonlocal sequence
            sequence += 1
            runner_event = RunnerEvent(
                sequence=sequence,
                type=event_type,
                payload=payload,
            )
            events.append(runner_event)
            return runner_event

        event("task_started", {"task_id": request.task_id})

        for position, step in enumerate(request.steps):
            index = step["index"]
            instruction = step["instruction"]
            event(
                "step_started",
                {"index": index, "instruction": instruction},
            )

            if request.scenario == "runner_interrupted":
                event(
                    "runner_interrupted",
                    {"failure_type": "runner_interrupted"},
                )
                return tuple(events)

            event(
                "step_log",
                {
                    "index": index,
                    "message": f"Mock Runner 开始执行步骤 {index}",
                },
            )
            is_assertion_failure = (
                request.scenario == "assertion_failure"
                and position == len(request.steps) - 1
            )
            assertion_result = "fail" if is_assertion_failure else "pass"
            step_payload = {
                "index": index,
                "instruction": instruction,
                "status": "failed" if assertion_result == "fail" else "passed",
                "assertion_result": assertion_result,
                "logs": [f"Mock Runner 开始执行步骤 {index}"],
            }
            if assertion_result == "fail":
                step_payload["failure_type"] = "assertion_failed"
            event("step_finished", step_payload)

        event(
            "task_finished",
            {"evidence_complete": request.scenario != "evidence_missing"},
        )
        return tuple(events)

    def _request_from_handle(self, handle: RunHandle) -> RunRequest:
        if (
            handle.runner_type != self.runner_type
            or not handle.run_id.startswith("mock_")
            or len(handle.run_id) > MAX_HANDLE_LENGTH
        ):
            raise ValueError("invalid_mock_run_handle")

        try:
            token, signature = handle.run_id.removeprefix("mock_").rsplit(".", 1)
            token += "=" * (-len(token) % 4)
            compressed = base64.b64decode(
                token,
                altchars=b"-_",
                validate=True,
            )
            expected = hmac.new(
                self._hmac_key,
                compressed,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError("invalid signature")
            decompressor = zlib.decompressobj()
            serialized = decompressor.decompress(
                compressed,
                MAX_DECOMPRESSED_HANDLE_BYTES + 1,
            )
            if (
                len(serialized) > MAX_DECOMPRESSED_HANDLE_BYTES
                or not decompressor.eof
                or decompressor.unused_data
            ):
                raise ValueError("invalid compressed payload")
            payload = json.loads(serialized)
            request = RunRequest(**payload["request"])
        except (
            binascii.Error,
            KeyError,
            TypeError,
            ValueError,
            zlib.error,
        ) as error:
            raise ValueError("invalid_mock_run_handle") from error

        if request.task_id != handle.task_id:
            raise ValueError("invalid_mock_run_handle")
        self._validate_request(request)
        return request

    @staticmethod
    def _validate_request(request: RunRequest) -> None:
        if request.scenario not in SUPPORTED_SCENARIOS:
            raise ValueError(f"unsupported_mock_scenario:{request.scenario}")
        if (
            len(request.steps) > MAX_REQUEST_LIST_ITEMS
            or len(request.assertions) > MAX_REQUEST_LIST_ITEMS
        ):
            raise ValueError("mock_request_limit_exceeded")
