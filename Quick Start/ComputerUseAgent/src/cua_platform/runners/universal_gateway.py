import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Literal

from cua_platform.settings.schemas import RunnerConfig

logger = logging.getLogger(__name__)

RemoteErrorCode = Literal[
    "credentials_invalid",
    "permission_denied",
    "pod_not_found",
    "pod_unavailable",
    "invalid_parameter",
    "rate_limited",
    "remote_timeout",
    "remote_unavailable",
    "request_rejected",
    "response_invalid",
]
HttpMethod = Literal["GET", "POST"]


class _SafeSummary(Mapping[str, Any]):
    __slots__ = ()

    def _summary_items(self) -> tuple[tuple[str, Any], ...]:
        raise NotImplementedError

    def _value_tuple(self) -> tuple[Any, ...]:
        raise NotImplementedError

    def __getitem__(self, key: str) -> Any:
        for item_key, value in self._summary_items():
            if item_key == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _value in self._summary_items())

    def __len__(self) -> int:
        return len(self._summary_items())

    def __setattr__(self, _name: str, _value: Any) -> None:
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __delattr__(self, _name: str) -> None:
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __eq__(self, other: object) -> bool:
        return type(other) is type(self) and self._value_tuple() == other._value_tuple()

    def __repr__(self) -> str:
        values = ", ".join(f"{key}={value!r}" for key, value in self._summary_items())
        return f"{type(self).__name__}({values})"


class UniversalRequest(_SafeSummary):
    __slots__ = ("_action", "_body", "_method", "_service", "_version")

    def __init__(
        self,
        service: str,
        action: str,
        version: str,
        method: HttpMethod,
        body: Mapping[str, Any],
    ) -> None:
        object.__setattr__(self, "_service", service)
        object.__setattr__(self, "_action", action)
        object.__setattr__(self, "_version", version)
        object.__setattr__(self, "_method", method)
        object.__setattr__(self, "_body", body)

    @property
    def service(self) -> str:
        return self._service

    @property
    def action(self) -> str:
        return self._action

    @property
    def version(self) -> str:
        return self._version

    @property
    def method(self) -> HttpMethod:
        return self._method

    @property
    def body(self) -> Mapping[str, Any]:
        return self._body

    def _summary_items(self) -> tuple[tuple[str, Any], ...]:
        return (
            ("service", self.service),
            ("action", self.action),
            ("version", self.version),
            ("method", self.method),
        )

    def _value_tuple(self) -> tuple[Any, ...]:
        return (self.service, self.action, self.version, self.method, self.body)


@dataclass(frozen=True)
class RemoteRun:
    run_id: str
    request_id: str | None
    thread_id: str | None = None


class _RemotePayloadResponse(_SafeSummary):
    __slots__ = ("_payload", "_request_id")

    def __init__(
        self,
        payload: Mapping[str, Any],
        request_id: str | None,
    ) -> None:
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_request_id", request_id)

    @property
    def payload(self) -> Mapping[str, Any]:
        return self._payload

    @property
    def request_id(self) -> str | None:
        return self._request_id

    def _summary_items(self) -> tuple[tuple[str, Any], ...]:
        return (("request_id", self.request_id),)

    def _value_tuple(self) -> tuple[Any, ...]:
        return (self.payload, self.request_id)


class RemoteStepResponse(_RemotePayloadResponse):
    __slots__ = ()


class RemoteResultResponse(_RemotePayloadResponse):
    __slots__ = ()


@dataclass(frozen=True)
class RemoteCancel:
    accepted: bool
    request_id: str | None


@dataclass(frozen=True, slots=True)
class GatewayTraceAttempt:
    stable_key: str
    action: str
    method: HttpMethod
    attempt: int
    status: Literal["ok", "error"]
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    request_id: str | None
    error_code: RemoteErrorCode | None


class UniversalRemoteError(RuntimeError):
    def __init__(
        self,
        code: RemoteErrorCode,
        request_id: str | None,
        *,
        retryable: bool,
        response_received: bool,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.request_id = safe_request_id(request_id)
        self.retryable = retryable
        self.response_received = response_received


UniversalCall = Callable[[RunnerConfig, UniversalRequest], Mapping[str, Any]]
Sleep = Callable[[float], Awaitable[None]]
GatewayTraceSink = Callable[[GatewayTraceAttempt], None]
ResponseValidator = Callable[[Mapping[str, Any]], None]

_SERVICE = "ipaas"
_VERSION = "2023-08-01"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_RETRYABLE_CODES: frozenset[RemoteErrorCode] = frozenset(
    {"rate_limited", "remote_timeout", "remote_unavailable"}
)


class UniversalGateway:
    def __init__(
        self,
        call: UniversalCall | None = None,
        sleep: Sleep = asyncio.sleep,
        trace_sink: GatewayTraceSink | None = None,
        trace_call_counts: Mapping[str, int] | None = None,
    ) -> None:
        self._call = call or call_universal
        self._sleep = sleep
        self._trace_sink = trace_sink
        self._trace_call_counts = dict(trace_call_counts or {})

    async def invoke_read(
        self,
        config: RunnerConfig,
        request: UniversalRequest,
        *,
        trace_key: str | None = None,
    ) -> Mapping[str, Any]:
        if request.method != "GET":
            raise ValueError("universal_read_requires_get")
        return await self._invoke(
            config,
            request,
            retry_get=True,
            trace_key=trace_key,
        )

    async def start_one_step(
        self,
        config: RunnerConfig,
        payload: Mapping[str, Any],
        *,
        trace_key: str | None = None,
    ) -> RemoteRun:
        response = await self._invoke(
            config,
            UniversalRequest(
                service=_SERVICE,
                action="RunAgentTaskOneStep",
                version=_VERSION,
                method="POST",
                body=payload,
            ),
            retry_get=False,
            trace_key=trace_key,
            validate_response=_validate_start_response,
        )
        request_id = _response_request_id(response)
        result = _start_result(response)
        run_id = result.get("RunId")
        if not isinstance(run_id, str) or not run_id:
            raise _invalid_response(request_id)
        thread_id = result.get("ThreadId")
        return RemoteRun(run_id, request_id, thread_id if isinstance(thread_id, str) else None)

    async def list_current_step(
        self,
        config: RunnerConfig,
        run_id: str,
        *,
        trace_key: str | None = None,
    ) -> RemoteStepResponse:
        response = await self._invoke(
            config,
            UniversalRequest(
                service=_SERVICE,
                action="ListAgentRunCurrentStep",
                version=_VERSION,
                method="GET",
                body={"RunId": run_id},
            ),
            retry_get=True,
            trace_key=trace_key,
        )
        return RemoteStepResponse(response, _response_request_id(response))

    async def get_result(
        self,
        config: RunnerConfig,
        run_id: str,
        *,
        trace_key: str | None = None,
    ) -> RemoteResultResponse:
        response = await self._invoke(
            config,
            UniversalRequest(
                service=_SERVICE,
                action="GetAgentResult",
                version=_VERSION,
                method="GET",
                body={"RunId": run_id, "IsDetail": True},
            ),
            retry_get=True,
            trace_key=trace_key,
        )
        return RemoteResultResponse(response, _response_request_id(response))

    async def list_task_by_thread(
        self,
        config: RunnerConfig,
        *,
        thread_id: str | None = None,
        run_id: str | None = None,
        trace_key: str | None = None,
    ) -> RemoteResultResponse:
        body: dict[str, Any] = {"AgentType": "cua"}
        if config.product_id:
            body["ProductId"] = config.product_id
        if thread_id:
            body["ThreadId"] = thread_id
        if run_id:
            body["RunId"] = run_id
        response = await self._invoke(
            config,
            UniversalRequest(
                service=_SERVICE,
                action="ListAgentRunTaskByThread",
                version=_VERSION,
                method="GET",
                body=body,
            ),
            retry_get=True,
            trace_key=trace_key,
        )
        return RemoteResultResponse(response, _response_request_id(response))

    async def detail_task_by_thread(
        self,
        config: RunnerConfig,
        *,
        thread_id: str | None = None,
        run_id: str | None = None,
        trace_key: str | None = None,
    ) -> RemoteResultResponse:
        body: dict[str, Any] = {"AgentType": "cua"}
        if thread_id:
            body["ThreadId"] = thread_id
        if run_id:
            body["RunId"] = run_id
        response = await self._invoke(
            config,
            UniversalRequest(
                service=_SERVICE,
                action="DetailAgentRunTaskByThread",
                version=_VERSION,
                method="GET",
                body=body,
            ),
            retry_get=True,
            trace_key=trace_key,
        )
        return RemoteResultResponse(response, _response_request_id(response))

    async def cancel(
        self,
        config: RunnerConfig,
        run_id: str,
        *,
        trace_key: str | None = None,
    ) -> RemoteCancel:
        response = await self._invoke(
            config,
            UniversalRequest(
                service=_SERVICE,
                action="CancelTask",
                version=_VERSION,
                method="POST",
                body={"RunId": run_id},
            ),
            retry_get=False,
            trace_key=trace_key,
        )
        return RemoteCancel(True, _response_request_id(response))

    async def _invoke(
        self,
        config: RunnerConfig,
        request: UniversalRequest,
        *,
        retry_get: bool,
        trace_key: str | None,
        validate_response: ResponseValidator | None = None,
    ) -> Mapping[str, Any]:
        delays = (0.25, 0.5) if retry_get else ()
        resolved_trace_key = self._resolved_trace_key(request.action, trace_key)
        for attempt in range(len(delays) + 1):
            started = monotonic()
            started_at = datetime.now(UTC)
            try:
                raw_response = await asyncio.to_thread(self._call, config, request)
                response = _normalize_response(raw_response, request.action)
                if validate_response is not None:
                    validate_response(response)
                self._trace_attempt(
                    resolved_trace_key,
                    request,
                    attempt + 1,
                    started,
                    started_at,
                    status="ok",
                    request_id=_response_request_id(response),
                    error_code=None,
                )
                return response
            except UniversalRemoteError as exc:
                self._trace_attempt(
                    resolved_trace_key,
                    request,
                    attempt + 1,
                    started,
                    started_at,
                    status="error",
                    request_id=exc.request_id,
                    error_code=exc.code,
                )
                if not exc.retryable or attempt == len(delays):
                    raise
                await self._sleep(delays[attempt])
        raise AssertionError("bounded retry loop exhausted")

    def _trace_attempt(
        self,
        trace_key: str | None,
        request: UniversalRequest,
        attempt: int,
        started: float,
        started_at: datetime,
        *,
        status: Literal["ok", "error"],
        request_id: str | None,
        error_code: RemoteErrorCode | None,
    ) -> None:
        if self._trace_sink is None or trace_key is None:
            return
        finished_at = datetime.now(UTC)
        try:
            self._trace_sink(
                GatewayTraceAttempt(
                    stable_key=f"{trace_key}.attempt.{attempt}",
                    action=request.action,
                    method=request.method,
                    attempt=attempt,
                    status=status,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=max(0, int((monotonic() - started) * 1000)),
                    request_id=request_id,
                    error_code=error_code,
                )
            )
        except Exception:
            logger.warning(
                "gateway_trace_persist_failed",
                extra={"action": request.action, "method": request.method},
            )

    def _resolved_trace_key(
        self,
        action: str,
        trace_key: str | None,
    ) -> str | None:
        if self._trace_sink is None:
            return None
        if trace_key is not None:
            return trace_key
        prefix = {
            "RunAgentTaskOneStep": "mobile.start",
            "ListAgentRunCurrentStep": "mobile.step",
            "GetAgentResult": "mobile.result",
            "CancelTask": "mobile.cancel",
        }.get(action, "mobile.call")
        call_number = self._trace_call_counts.get(action, 0) + 1
        self._trace_call_counts[action] = call_number
        return f"{prefix}.{call_number}"


def _validate_start_response(response: Mapping[str, Any]) -> None:
    result = _start_result(response)
    run_id = result.get("RunId")
    if not isinstance(run_id, str) or not run_id:
        raise _invalid_response(_response_request_id(response))


def call_universal(
    config: RunnerConfig,
    request: UniversalRequest,
) -> Mapping[str, Any]:
    if not config.access_key_id or not config.secret_access_key:
        raise ValueError("mobile_use_credentials_incomplete")
    try:
        import volcenginesdkcore

        configuration = volcenginesdkcore.Configuration()
        configuration.ak = config.access_key_id
        configuration.sk = config.secret_access_key
        configuration.region = "cn-north-1"
        configuration.auto_retry = False
        api_client = volcenginesdkcore.ApiClient(configuration)
        for name, value in (config.request_headers or {}).items():
            api_client.set_default_header(name, value)
        api = volcenginesdkcore.UniversalApi(api_client)
        response = api.do_call(
            volcenginesdkcore.UniversalInfo(
                method=request.method,
                action=request.action,
                service=request.service,
                version=request.version,
                content_type="application/json",
            ),
            volcenginesdkcore.Flatten(request.body).flat(),
        )
    except UniversalRemoteError:
        raise
    except Exception as exc:
        raise safe_universal_error(exc) from None
    return _normalize_response(response, request.action)


def safe_universal_error(exc: Exception) -> UniversalRemoteError:
    if isinstance(exc, UniversalRemoteError):
        return exc
    payload, decoded_body = _exception_payload(exc)
    metadata = _mapping(payload.get("ResponseMetadata"))
    error = _mapping(metadata.get("Error"))
    raw_code = error.get("Code") or getattr(exc, "code", None)
    status = getattr(exc, "status", None)
    request_id = safe_request_id(
        metadata.get("RequestId") or getattr(exc, "request_id", None)
    )
    response_received = decoded_body or (
        isinstance(status, int) and not isinstance(status, bool) and status > 0
    )
    code = _normalize_error_code(
        raw_code,
        exc,
        status=status,
        response_received=response_received,
    )
    return UniversalRemoteError(
        code,
        request_id,
        retryable=code in _RETRYABLE_CODES,
        response_received=response_received,
    )


def safe_request_id(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if _SAFE_REQUEST_ID.fullmatch(value) is None:
        return None
    return value


def _invalid_response(request_id: str | None) -> UniversalRemoteError:
    return UniversalRemoteError(
        "response_invalid",
        request_id,
        retryable=False,
        response_received=True,
    )


def _normalize_response(
    response: object,
    action: str,
) -> Mapping[str, Any]:
    if isinstance(response, Mapping):
        return response
    if action == "CancelTask" and response is None:
        return {}
    raise _invalid_response(None)


def _response_request_id(response: Mapping[str, Any]) -> str | None:
    metadata = _mapping(response.get("ResponseMetadata"))
    return safe_request_id(metadata.get("RequestId") or metadata.get("request_id"))


def _exception_payload(exc: Exception) -> tuple[Mapping[str, Any], bool]:
    body = getattr(exc, "body", None)
    if isinstance(body, bytes):
        try:
            body = body.decode("utf-8")
        except UnicodeDecodeError:
            return {}, False
    if not isinstance(body, str):
        return {}, False
    try:
        decoded = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return {}, False
    if not isinstance(decoded, Mapping):
        return {}, False
    return decoded, True


def _normalize_error_code(
    value: Any,
    exc: Exception,
    *,
    status: Any,
    response_received: bool,
) -> RemoteErrorCode:
    code = re.sub(r"[^a-z0-9]", "", str(value or "").lower())
    if status == 0:
        return "remote_unavailable"
    if "pod" in code and ("notfound" in code or "notexist" in code):
        return "pod_not_found"
    if "pod" in code and ("unavailable" in code or "offline" in code):
        return "pod_unavailable"
    if (
        "invalidaccesskey" in code
        or "signaturedoesnotmatch" in code
        or "authfailure" in code
    ):
        return "credentials_invalid"
    if "permission" in code or "forbidden" in code or "accessdenied" in code:
        return "permission_denied"
    if "invalidparameter" in code or "missingparameter" in code:
        return "invalid_parameter"
    if (
        "throttl" in code
        or "ratelimit" in code
        or "toomanyrequest" in code
        or status == 429
    ):
        return "rate_limited"
    if "timeout" in code or isinstance(exc, TimeoutError) or status in {408, 504}:
        return "remote_timeout"
    if (
        "internalerror" in code
        or "serviceunavailable" in code
        or "servererror" in code
        or isinstance(status, int)
        and 500 <= status <= 599
        or (not response_received and isinstance(exc, (ConnectionError, OSError)))
    ):
        return "remote_unavailable"
    if status == 401:
        return "credentials_invalid"
    if status == 403:
        return "permission_denied"
    return "request_rejected"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _start_result(response: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = _mapping(response.get("Result"))
    return nested if nested else response
