import json
import logging
import threading
from collections.abc import Mapping
from dataclasses import asdict
from unittest.mock import AsyncMock, call

import pytest
from fastapi.encoders import jsonable_encoder

from mua_platform.runners.universal_gateway import (
    GatewayTraceAttempt,
    RemoteCancel,
    RemoteResultResponse,
    RemoteRun,
    RemoteStepResponse,
    UniversalGateway,
    UniversalRemoteError,
    UniversalRequest,
    call_universal,
    safe_universal_error,
)
from mua_platform.settings.schemas import RunnerConfig


ACCESS_KEY = "AKLT-test-sensitive"
SECRET_KEY = "secret-key-sensitive"
USER_PROMPT = "# 测试用例\n敏感用户输入"
STRUCT_OUTPUT = {"status": "pass", "evidence": ["sensitive evidence"]}


def mobile_config() -> RunnerConfig:
    return RunnerConfig(
        mode="mobile_use",
        access_key_id=ACCESS_KEY,
        secret_access_key=SECRET_KEY,
        product_id="product-1",
        pod_id="pod-1",
        tos_bucket="mua-test",
        tos_region="cn-beijing",
    )


def one_step_payload() -> dict[str, object]:
    return {
        "RunName": "task_task_1",
        "ThreadId": "mua-0123456789abcdef0123456789abcdef0123456789abcdef",
        "PodId": "pod-1",
        "ProductId": "product-1",
        "UserPrompt": "# 测试用例\n...",
        "SystemPrompt": "你是移动端 UI 自动化测试 Agent。...",
        "TosBucket": "mua-test",
        "TosEndpoint": "tos-cn-beijing.volces.com",
        "TosRegion": "cn-beijing",
        "UseBase64Screenshot": True,
        "IsScreenRecord": False,
        "Timeout": 600,
    }


class ApiException(Exception):
    def __init__(
        self,
        remote_code: str,
        request_id: str,
        *,
        status: int | None = None,
    ) -> None:
        super().__init__("unsafe remote exception")
        self.status = status
        self.body = json.dumps(
            {
                "ResponseMetadata": {
                    "RequestId": request_id,
                    "Error": {
                        "Code": remote_code,
                        "Message": f"{SECRET_KEY} {USER_PROMPT}",
                    },
                },
                "Result": {"StructOutput": STRUCT_OUTPUT},
            }
        )


def api_exception(remote_code: str, request_id: str = "req-safe") -> ApiException:
    return ApiException(remote_code, request_id)


@pytest.mark.asyncio
async def test_gateway_uses_ui_test_demo_execution_contract():
    calls: list[UniversalRequest] = []

    def invoke(_config: RunnerConfig, request: UniversalRequest) -> Mapping[str, object]:
        calls.append(request)
        result: object = {"RunId": "run-123"} if request.action == "RunAgentTaskOneStep" else None
        return {
            "ResponseMetadata": {"RequestId": f"req_{request.action}"},
            "Result": result,
        }

    gateway = UniversalGateway(call=invoke, sleep=AsyncMock())
    payload = one_step_payload()
    run = await gateway.start_one_step(mobile_config(), payload)
    step = await gateway.list_current_step(mobile_config(), run.run_id)
    result = await gateway.get_result(mobile_config(), run.run_id)
    cancelled = await gateway.cancel(mobile_config(), run.run_id)

    assert payload == one_step_payload()
    assert run == RemoteRun("run-123", "req_RunAgentTaskOneStep")
    assert step == RemoteStepResponse(
        {
            "ResponseMetadata": {"RequestId": "req_ListAgentRunCurrentStep"},
            "Result": None,
        },
        "req_ListAgentRunCurrentStep",
    )
    assert result == RemoteResultResponse(
        {
            "ResponseMetadata": {"RequestId": "req_GetAgentResult"},
            "Result": None,
        },
        "req_GetAgentResult",
    )
    assert cancelled == RemoteCancel(True, "req_CancelTask")
    assert [(item.method, item.action, item.service, item.version) for item in calls] == [
        ("POST", "RunAgentTaskOneStep", "ipaas", "2023-08-01"),
        ("GET", "ListAgentRunCurrentStep", "ipaas", "2023-08-01"),
        ("GET", "GetAgentResult", "ipaas", "2023-08-01"),
        ("POST", "CancelTask", "ipaas", "2023-08-01"),
    ]
    assert calls[0].body == payload
    assert calls[1].body == {"RunId": "run-123"}
    assert calls[2].body == {"RunId": "run-123", "IsDetail": True}
    assert calls[3].body == {"RunId": "run-123"}


@pytest.mark.asyncio
async def test_gateway_calls_pod_prepare_actions():
    calls: list[UniversalRequest] = []

    def invoke(_config: RunnerConfig, request: UniversalRequest) -> Mapping[str, object]:
        calls.append(request)
        if request.action == "GetTaskInfo":
            return {
                "ResponseMetadata": {"RequestId": f"req_{request.action}"},
                "Result": {
                    "TaskId": request.body["TaskId"],
                    "TaskAction": "ResetPod",
                    "TaskResult": 100,
                    "Jobs": [
                        {
                            "PodId": "pod-1",
                            "JobId": f"job_{request.action}",
                            "Status": 100,
                        }
                    ],
                },
            }
        response = {
            "ResponseMetadata": {"RequestId": f"req_{request.action}"},
        }
        if request.action in {"PowerOnPod", "PowerOffPod"}:
            response["Result"] = {
                "Details": [{"PodId": "pod-1", "Success": True, "ErrMsg": ""}],
            }
        elif request.action != "RebootPod":
            response["Result"] = {
                    "TaskId": f"task_{request.action}",
                    "TaskAction": request.action,
                    "Jobs": [
                        {
                            "PodId": "pod-1",
                            "JobId": f"job_{request.action}",
                            "Status": 10,
                        }
                    ],
                }
        return response

    gateway = UniversalGateway(call=invoke, sleep=AsyncMock())

    reset = await gateway.reset_host(mobile_config(), product_id="product-1", pod_id="pod-1")
    reboot = await gateway.reboot_host(mobile_config(), product_id="product-1", pod_id="pod-1")
    power_on = await gateway.power_on_pod(mobile_config(), product_id="product-1", pod_id="pod-1")
    power_off = await gateway.power_off_pod(mobile_config(), product_id="product-1", pod_id="pod-1")
    info = await gateway.get_task_info(
        mobile_config(),
        product_id="product-1",
        task_id="task_ResetPod",
    )

    assert reset.request_id == "req_ResetPod"
    assert reset.task_id == "task_ResetPod"
    assert reboot.request_id == "req_RebootPod"
    assert reboot.task_id is None
    assert power_on.request_id == "req_PowerOnPod"
    assert power_on.task_id is None
    assert power_off.request_id == "req_PowerOffPod"
    assert power_off.task_id is None
    assert info.request_id == "req_GetTaskInfo"
    assert info.task_result == 100
    assert info.jobs == [{"PodId": "pod-1", "JobId": "job_GetTaskInfo", "Status": 100}]
    assert [(item.method, item.action, item.service, item.version) for item in calls] == [
        ("POST", "ResetPod", "ACEP", "2025-05-01"),
        ("POST", "RebootPod", "ACEP", "2025-05-01"),
        ("POST", "PowerOnPod", "ACEP", "2025-05-01"),
        ("POST", "PowerOffPod", "ACEP", "2025-05-01"),
        ("GET", "GetTaskInfo", "ACEP", "2025-05-01"),
    ]
    assert calls[0].body == {
        "ProductId": "product-1",
        "PodIdList": ["pod-1"],
    }
    assert calls[1].body == {
        "ProductId": "product-1",
        "PodId": "pod-1",
        "ResourcePolicy": "Persist",
    }
    assert calls[2].body == {
        "ProductId": "product-1",
        "PodId": "pod-1",
    }
    assert calls[3].body == {
        "ProductId": "product-1",
        "PodId": "pod-1",
    }
    assert calls[4].body == {
        "ProductId": "product-1",
        "TaskId": "task_ResetPod",
    }


@pytest.mark.asyncio
async def test_gateway_accepts_top_level_power_action_details_without_request_id():
    def invoke(_config: RunnerConfig, request: UniversalRequest) -> Mapping[str, object]:
        assert request.action == "PowerOnPod"
        return {
            "AccountId": "account-1",
            "ProductId": request.body["ProductId"],
            "Details": [
                {
                    "PodId": request.body["PodId"],
                    "Success": True,
                    "ErrMsg": "",
                }
            ],
        }

    gateway = UniversalGateway(call=invoke, sleep=AsyncMock())

    result = await gateway.power_on_pod(
        mobile_config(),
        product_id="product-1",
        pod_id="pod-1",
    )

    assert result.request_id is None
    assert result.task_id is None


@pytest.mark.asyncio
async def test_gateway_accepts_top_level_reset_task_returned_by_sdk():
    def invoke(_config: RunnerConfig, request: UniversalRequest) -> Mapping[str, object]:
        assert request.action == "ResetPod"
        return {
            "TaskId": "task-reset-top-level",
            "TaskAction": "ResetPod",
            "Jobs": [
                {
                    "PodId": request.body["PodIdList"][0],
                    "JobId": "job-reset-top-level",
                    "Status": 10,
                }
            ],
        }

    gateway = UniversalGateway(call=invoke, sleep=AsyncMock())

    result = await gateway.reset_host(
        mobile_config(),
        product_id="product-1",
        pod_id="pod-1",
    )

    assert result.request_id is None
    assert result.task_id == "task-reset-top-level"


@pytest.mark.asyncio
async def test_gateway_accepts_empty_reboot_response_from_sdk():
    def invoke(_config: RunnerConfig, request: UniversalRequest) -> Mapping[str, object] | None:
        assert request.action == "RebootPod"
        return None

    gateway = UniversalGateway(call=invoke, sleep=AsyncMock())

    result = await gateway.reboot_host(
        mobile_config(),
        product_id="product-1",
        pod_id="pod-1",
    )

    assert result.request_id is None
    assert result.task_id is None


@pytest.mark.asyncio
async def test_gateway_list_pod_status_selects_requested_pod_from_page():
    def invoke(_config: RunnerConfig, request: UniversalRequest) -> Mapping[str, object]:
        assert request.action == "ListPod"
        return {
            "Row": [
                {"ProductId": "product-1", "PodId": "other-pod", "Online": 1},
                {"ProductId": "product-1", "PodId": request.body["PodIdList"][0], "Online": 2},
            ]
        }

    gateway = UniversalGateway(call=invoke, sleep=AsyncMock())

    status = await gateway.list_pod_status(
        mobile_config(),
        product_id="product-1",
        pod_id="pod-1",
    )

    assert status.pod_id == "pod-1"
    assert status.online == 2


@pytest.mark.asyncio
async def test_gateway_rejects_failed_host_prepare_job():
    def invoke(_config: RunnerConfig, request: UniversalRequest) -> Mapping[str, object]:
        return {
            "ResponseMetadata": {"RequestId": "req_prepare_failed"},
            "Result": {
                "TaskId": "task_ResetPod",
                "TaskAction": request.action,
                "Jobs": [{"PodId": "pod-1", "Status": -1}],
            },
        }

    gateway = UniversalGateway(call=invoke, sleep=AsyncMock())

    with pytest.raises(UniversalRemoteError) as exc:
        await gateway.reset_host(
            mobile_config(),
            product_id="product-1",
            pod_id="pod-1",
        )

    assert exc.value.code == "request_rejected"
    assert exc.value.request_id == "req_prepare_failed"


@pytest.mark.asyncio
async def test_gateway_accepts_top_level_start_payload_returned_by_sdk():
    def invoke(
        _config: RunnerConfig,
        _request: UniversalRequest,
    ) -> Mapping[str, object]:
        return {
            "RunId": "run-top-level",
            "RunName": "task-task-1",
            "ThreadId": "thread-top-level",
        }

    run = await UniversalGateway(call=invoke).start_one_step(
        mobile_config(),
        one_step_payload(),
    )

    assert run == RemoteRun(
        "run-top-level",
        None,
        "thread-top-level",
    )


@pytest.mark.asyncio
async def test_gateway_accepts_empty_cancel_response_from_sdk():
    def invoke(
        _config: RunnerConfig,
        request: UniversalRequest,
    ) -> Mapping[str, object] | None:
        assert request.action == "CancelTask"
        return None

    cancelled = await UniversalGateway(call=invoke).cancel(
        mobile_config(),
        "run-empty-cancel",
    )

    assert cancelled == RemoteCancel(True, None)


@pytest.mark.asyncio
async def test_gateway_runs_synchronous_call_outside_event_loop_thread():
    caller_thread = threading.get_ident()
    worker_threads: list[int] = []

    def invoke(_config: RunnerConfig, _request: UniversalRequest) -> Mapping[str, object]:
        worker_threads.append(threading.get_ident())
        return {
            "ResponseMetadata": {"RequestId": "req-thread"},
            "Result": {"RunId": "run-thread"},
        }

    run = await UniversalGateway(call=invoke).start_one_step(
        mobile_config(), one_step_payload()
    )

    assert run.run_id == "run-thread"
    assert worker_threads and worker_threads[0] != caller_thread


@pytest.mark.parametrize(
    ("remote_code", "safe_code", "retryable"),
    [
        ("InvalidAccessKey", "credentials_invalid", False),
        ("SignatureDoesNotMatch", "credentials_invalid", False),
        ("Forbidden", "permission_denied", False),
        ("InvalidParameter", "invalid_parameter", False),
        ("PodNotFound", "pod_not_found", False),
        ("PodUnavailable", "pod_unavailable", False),
        ("Throttling.User", "rate_limited", True),
        ("InternalError", "remote_unavailable", True),
    ],
)
def test_gateway_classifies_remote_errors(remote_code, safe_code, retryable):
    error = safe_universal_error(api_exception(remote_code))

    assert (error.code, error.retryable, error.request_id) == (
        safe_code,
        retryable,
        "req-safe",
    )
    assert error.response_received is True


@pytest.mark.parametrize(
    ("exception", "safe_code"),
    [
        (TimeoutError("unsafe timeout"), "remote_timeout"),
        (ConnectionError("unsafe connection"), "remote_unavailable"),
    ],
)
def test_gateway_classifies_network_errors_without_response(exception, safe_code):
    error = safe_universal_error(exception)

    assert error.code == safe_code
    assert error.retryable is True
    assert error.response_received is False
    assert error.request_id is None


def test_gateway_extracts_safe_error_fields_from_sdk_bytes_body():
    exception = api_exception("InvalidParameter", "req-bytes")
    exception.body = exception.body.encode()

    error = safe_universal_error(exception)

    assert error.code == "invalid_parameter"
    assert error.request_id == "req-bytes"
    assert error.retryable is False
    assert error.response_received is True


def test_gateway_treats_sdk_status_zero_as_transport_failure():
    exception = ApiException("", "unsafe request id", status=0)
    exception.body = None

    error = safe_universal_error(exception)

    assert error.code == "remote_unavailable"
    assert error.request_id is None
    assert error.retryable is True
    assert error.response_received is False


def test_gateway_classifies_http_5xx_without_error_body_as_received_and_retryable():
    exception = ApiException("", "req-server", status=503)
    exception.body = "{}"

    error = safe_universal_error(exception)

    assert error.code == "remote_unavailable"
    assert error.retryable is True
    assert error.response_received is True
    assert error.request_id is None


@pytest.mark.asyncio
async def test_gateway_retries_get_twice_with_bounded_backoff():
    attempts = 0
    sleep = AsyncMock()

    def invoke(_config: RunnerConfig, _request: UniversalRequest) -> Mapping[str, object]:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise UniversalRemoteError(
                "remote_unavailable",
                "req-retry",
                retryable=True,
                response_received=False,
            )
        return {
            "ResponseMetadata": {"RequestId": "req-success"},
            "Result": {"Results": []},
        }

    response = await UniversalGateway(call=invoke, sleep=sleep).list_current_step(
        mobile_config(), "run-123"
    )

    assert response.request_id == "req-success"
    assert attempts == 3
    assert sleep.await_args_list == [call(0.25), call(0.5)]


@pytest.mark.asyncio
async def test_gateway_traces_each_get_attempt_without_request_body():
    attempts = 0
    traces: list[GatewayTraceAttempt] = []

    def invoke(_config: RunnerConfig, _request: UniversalRequest) -> Mapping[str, object]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise UniversalRemoteError(
                "remote_unavailable",
                "req-retry",
                retryable=True,
                response_received=False,
            )
        return {
            "ResponseMetadata": {"RequestId": "req-success"},
            "Result": {"Results": []},
        }

    gateway = UniversalGateway(call=invoke, sleep=AsyncMock(), trace_sink=traces.append)
    await gateway.list_current_step(
        mobile_config(),
        "run-sensitive",
        trace_key="mobile.poll.1",
    )

    assert [
        (
            trace.stable_key,
            trace.action,
            trace.method,
            trace.attempt,
            trace.status,
            trace.request_id,
            trace.error_code,
        )
        for trace in traces
    ] == [
        (
            "mobile.poll.1.attempt.1",
            "ListAgentRunCurrentStep",
            "GET",
            1,
            "error",
            "req-retry",
            "remote_unavailable",
        ),
        (
            "mobile.poll.1.attempt.2",
            "ListAgentRunCurrentStep",
            "GET",
            2,
            "ok",
            "req-success",
            None,
        ),
    ]
    assert all(trace.duration_ms >= 0 for trace in traces)
    assert all(not hasattr(trace, "body") for trace in traces)
    assert "run-sensitive" not in repr(traces)


@pytest.mark.asyncio
async def test_action_response_parse_failure_overwrites_attempt_as_response_invalid():
    traces: dict[str, GatewayTraceAttempt] = {}

    def invoke(_config: RunnerConfig, _request: UniversalRequest) -> Mapping[str, object]:
        return {
            "ResponseMetadata": {"RequestId": "req-invalid"},
            "Result": {},
        }

    gateway = UniversalGateway(
        call=invoke,
        trace_sink=lambda attempt: traces.__setitem__(attempt.stable_key, attempt),
    )

    with pytest.raises(UniversalRemoteError) as caught:
        await gateway.start_one_step(
            mobile_config(),
            one_step_payload(),
            trace_key="mobile.start.1",
        )

    assert caught.value.code == "response_invalid"
    assert list(traces) == ["mobile.start.1.attempt.1"]
    assert traces["mobile.start.1.attempt.1"].status == "error"
    assert traces["mobile.start.1.attempt.1"].error_code == "response_invalid"
    assert traces["mobile.start.1.attempt.1"].request_id == "req-invalid"


@pytest.mark.asyncio
async def test_gateway_continues_trace_call_number_after_resume():
    traces: list[GatewayTraceAttempt] = []

    def invoke(_config: RunnerConfig, _request: UniversalRequest) -> Mapping[str, object]:
        return {
            "ResponseMetadata": {"RequestId": "req-resumed"},
            "Result": {"Results": []},
        }

    gateway = UniversalGateway(
        call=invoke,
        trace_sink=traces.append,
        trace_call_counts={"ListAgentRunCurrentStep": 3},
    )
    await gateway.list_current_step(mobile_config(), "run-resumed")

    assert traces[0].stable_key == "mobile.step.4.attempt.1"


@pytest.mark.asyncio
async def test_trace_sink_failure_does_not_change_remote_call_result(caplog):
    caplog.set_level(logging.WARNING)

    def invoke(_config: RunnerConfig, _request: UniversalRequest) -> Mapping[str, object]:
        return {
            "ResponseMetadata": {"RequestId": "req-success"},
            "Result": {"RunId": "run-success"},
        }

    def fail_trace(_attempt: GatewayTraceAttempt) -> None:
        raise RuntimeError(f"unsafe trace failure {SECRET_KEY}")

    run = await UniversalGateway(call=invoke, trace_sink=fail_trace).start_one_step(
        mobile_config(),
        one_step_payload(),
    )

    assert run == RemoteRun("run-success", "req-success")
    assert "gateway_trace_persist_failed" in caplog.text
    assert SECRET_KEY not in caplog.text


@pytest.mark.asyncio
async def test_gateway_never_performs_a_fourth_get_attempt():
    attempts = 0

    def invoke(_config: RunnerConfig, _request: UniversalRequest) -> Mapping[str, object]:
        nonlocal attempts
        attempts += 1
        raise UniversalRemoteError(
            "rate_limited",
            "req-limited",
            retryable=True,
            response_received=True,
        )

    with pytest.raises(UniversalRemoteError) as caught:
        await UniversalGateway(call=invoke, sleep=AsyncMock()).get_result(
            mobile_config(), "run-123"
        )

    assert caught.value.code == "rate_limited"
    assert attempts == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["start", "cancel"])
async def test_gateway_does_not_retry_post_after_network_error(operation):
    attempts = 0

    def invoke(_config: RunnerConfig, _request: UniversalRequest) -> Mapping[str, object]:
        nonlocal attempts
        attempts += 1
        raise UniversalRemoteError(
            "remote_unavailable",
            None,
            retryable=True,
            response_received=False,
        )

    gateway = UniversalGateway(call=invoke, sleep=AsyncMock())
    with pytest.raises(UniversalRemoteError):
        if operation == "start":
            await gateway.start_one_step(mobile_config(), one_step_payload())
        else:
            await gateway.cancel(mobile_config(), "run-123")

    assert attempts == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["invalid_parameter", "permission_denied"])
async def test_gateway_does_not_retry_non_retryable_get_errors(code):
    attempts = 0

    def invoke(_config: RunnerConfig, _request: UniversalRequest) -> Mapping[str, object]:
        nonlocal attempts
        attempts += 1
        raise UniversalRemoteError(
            code,
            "req-fast-fail",
            retryable=False,
            response_received=True,
        )

    with pytest.raises(UniversalRemoteError):
        await UniversalGateway(call=invoke, sleep=AsyncMock()).get_result(
            mobile_config(), "run-123"
        )

    assert attempts == 1


def test_gateway_filters_unsafe_request_id_and_redacts_exception_data(caplog):
    caplog.set_level(logging.DEBUG)

    error = safe_universal_error(
        api_exception("InternalError", f"unsafe request id {ACCESS_KEY}")
    )
    serialized = repr(error) + str(error) + json.dumps(vars(error), default=str)
    captured = caplog.text + serialized

    assert error.request_id is None
    for secret in (ACCESS_KEY, SECRET_KEY, USER_PROMPT, "StructOutput"):
        assert secret not in captured


def test_gateway_dto_repr_omits_request_and_response_payloads():
    request = UniversalRequest(
        "ipaas",
        "RunAgentTaskOneStep",
        "2023-08-01",
        "POST",
        {"UserPrompt": USER_PROMPT, "AccessKey": ACCESS_KEY},
    )
    response = RemoteResultResponse(
        {"Result": {"StructOutput": STRUCT_OUTPUT, "SecretAccessKey": SECRET_KEY}},
        "req-safe",
    )

    serialized = repr(request) + repr(response)
    for secret in (ACCESS_KEY, SECRET_KEY, USER_PROMPT, "StructOutput"):
        assert secret not in serialized


def sensitive_dtos() -> list[tuple[object, dict[str, object], str]]:
    return [
        (
            UniversalRequest(
                "ipaas",
                "RunAgentTaskOneStep",
                "2023-08-01",
                "POST",
                {"UserPrompt": USER_PROMPT, "AccessKey": ACCESS_KEY},
            ),
            {
                "service": "ipaas",
                "action": "RunAgentTaskOneStep",
                "version": "2023-08-01",
                "method": "POST",
            },
            ACCESS_KEY,
        ),
        (
            RemoteStepResponse(
                {"Result": {"UserPrompt": USER_PROMPT}},
                "req-step-safe",
            ),
            {"request_id": "req-step-safe"},
            USER_PROMPT,
        ),
        (
            RemoteResultResponse(
                {"Result": {"StructOutput": STRUCT_OUTPUT, "SecretAccessKey": SECRET_KEY}},
                "req-result-safe",
            ),
            {"request_id": "req-result-safe"},
            SECRET_KEY,
        ),
    ]


@pytest.mark.parametrize(("value", "_summary", "_secret"), sensitive_dtos())
def test_sensitive_gateway_dtos_reject_asdict(value, _summary, _secret):
    with pytest.raises(TypeError):
        asdict(value)


@pytest.mark.parametrize(("value", "_summary", "_secret"), sensitive_dtos())
def test_sensitive_gateway_dtos_reject_vars(value, _summary, _secret):
    with pytest.raises(TypeError):
        vars(value)


@pytest.mark.parametrize(("value", "summary", "secret"), sensitive_dtos())
def test_sensitive_gateway_dtos_expose_only_safe_jsonable_summary(
    value,
    summary,
    secret,
):
    encoded = jsonable_encoder(value)

    assert encoded == summary
    assert secret not in json.dumps(encoded)
    assert "body" not in encoded
    assert "payload" not in encoded


def test_sensitive_gateway_dtos_keep_readonly_internal_mappings():
    body = {"UserPrompt": USER_PROMPT}
    payload = {"Result": {"StructOutput": STRUCT_OUTPUT}}
    request = UniversalRequest(
        "ipaas",
        "RunAgentTaskOneStep",
        "2023-08-01",
        "POST",
        body,
    )
    step = RemoteStepResponse(payload, "req-step-safe")
    result = RemoteResultResponse(payload, "req-result-safe")

    assert request.body is body
    assert step.payload is payload
    assert result.payload is payload
    with pytest.raises(AttributeError):
        request.body = {}
    with pytest.raises(AttributeError):
        step.payload = {}
    with pytest.raises(AttributeError):
        result.payload = {}


def test_call_universal_rejects_non_mapping_response(monkeypatch):
    class Configuration:
        pass

    class UniversalApi:
        def __init__(self, _client: object) -> None:
            pass

        def do_call(self, _info: object, _body: object) -> list[object]:
            return []

    fake_sdk = type(
        "FakeSdk",
        (),
        {
            "Configuration": Configuration,
            "ApiClient": staticmethod(lambda configuration: configuration),
            "UniversalApi": UniversalApi,
            "UniversalInfo": staticmethod(lambda **kwargs: kwargs),
            "Flatten": staticmethod(lambda body: type("Flat", (), {"flat": lambda self: body})()),
        },
    )
    monkeypatch.setitem(__import__("sys").modules, "volcenginesdkcore", fake_sdk)
    request = UniversalRequest("ACEP", "DetailPod", "2023-10-30", "GET", {})

    with pytest.raises(UniversalRemoteError) as caught:
        call_universal(mobile_config(), request)

    assert caught.value.code == "response_invalid"
    assert caught.value.retryable is False
    assert caught.value.response_received is True


def test_call_universal_preserves_post_json_arrays(monkeypatch):
    calls = []

    class Configuration:
        pass

    class UniversalApi:
        def __init__(self, _client: object) -> None:
            pass

        def do_call(self, _info: object, body: object) -> dict:
            calls.append(body)
            return {"ResponseMetadata": {"RequestId": "req-post"}}

    class Flatten:
        def __init__(self, body: object) -> None:
            self.body = body

        def flat(self) -> dict:
            return {"PodIdList.1": "pod-1"}

    fake_sdk = type(
        "FakeSdk",
        (),
        {
            "Configuration": Configuration,
            "ApiClient": staticmethod(lambda configuration: configuration),
            "UniversalApi": UniversalApi,
            "UniversalInfo": staticmethod(lambda **kwargs: kwargs),
            "Flatten": Flatten,
        },
    )
    monkeypatch.setitem(__import__("sys").modules, "volcenginesdkcore", fake_sdk)
    body = {"ProductId": "product-1", "PodIdList": ["pod-1"]}

    call_universal(
        mobile_config(),
        UniversalRequest("ACEP", "ResetPod", "2025-05-01", "POST", body),
    )

    assert calls == [body]


@pytest.mark.asyncio
async def test_gateway_rejects_missing_or_invalid_response_fields():
    gateway = UniversalGateway(
        call=lambda _config, _request: {
            "ResponseMetadata": {"RequestId": "req-invalid"},
            "Result": {},
        }
    )

    with pytest.raises(UniversalRemoteError) as caught:
        await gateway.start_one_step(mobile_config(), one_step_payload())

    assert caught.value.code == "response_invalid"
    assert caught.value.request_id == "req-invalid"
    assert caught.value.retryable is False
    assert caught.value.response_received is True
