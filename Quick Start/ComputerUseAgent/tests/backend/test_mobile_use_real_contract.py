import hashlib
import json
import logging
import re
import sys
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from cua_platform.runners.base import (
    CancelResult,
    PollResult,
    RunHandle,
    RunRequest,
    RunnerEvent,
)
from cua_platform.runners.mobile_use import MobileUseRunner
from cua_platform.runners.universal_gateway import (
    RemoteRun,
    UniversalGateway,
    UniversalRequest,
    call_universal,
)
from cua_platform.settings.schemas import RunnerConfig


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mobile_use"
FIXTURE_HASHES = {
    "cancel_accepted.json": (
        "10850bdfe386551e078e20b7beb3c64bffe71029c42fdd9566ec8af712e30314"
    ),
    "result_cancelled.json": (
        "dd8d39e8777dfdfd842afafae10ce2ad79fa98ab7fc094cb1a36b46513f02b44"
    ),
    "result_fail_content.json": (
        "ef6ee806cf20d0c712a265e21b9cf8885e800ef97050f66f585eaa9c2a9fefc9"
    ),
    "result_pass_struct.json": (
        "edd96e6a4f67492ec3f7aa164cfe5efbb89ae835ab2613b4846b8917b72da8b2"
    ),
    "result_pending.json": (
        "13a33d65e70689e2ee533cba57c73b5277d4064cdd65e885711e3e056ffb1ca5"
    ),
    "run_started.json": (
        "f75ab968d51033bb8e9f7e000b2b8402f4874aa82e0f741d163492d93560fa32"
    ),
    "step_finished.json": (
        "38547a67f14c21fea157b8981893dba29b50e0f840f0b0fc22c49974f69a71a2"
    ),
    "step_request_user.json": (
        "5131e4109805ef2b4dd1d070b23cdf018b67bb3f8b1a4a22cc0d5828783dff14"
    ),
}
SECRET_PATTERN = re.compile(
    r"AKLT[0-9A-Za-z]{8,}|VOLC_SECRETKEY|(?<!\d)\d{32,}(?!\d)|"
    r"https://[^\"\s]*volces\.com[^\"\s]*|https://[^\"\s?]+\?[^\"\s]*"
)


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def fixture_path(name: str) -> Path:
    return FIXTURE_DIR / name


def load_fixture(name: str) -> dict:
    return json.loads(
        fixture_path(name).read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"invalid JSON constant: {value}")
        ),
    )


def mobile_config() -> RunnerConfig:
    return RunnerConfig(
        mode="mobile_use",
        access_key_id="fixture-access-key",
        secret_access_key="fixture-secret-key",
        account_id="2103274899",
        product_id="product-sanitized",
        pod_id="pod-sanitized",
        tos_bucket="fixture-bucket",
        tos_region="cn-beijing",
    )


def run_request() -> RunRequest:
    return RunRequest(
        task_id="task-real-contract",
        scenario="success",
        title="打开首页",
        content_markdown=(
            "## 执行任务\n"
            "- 打开 fixture-app 首页\n\n"
            "## 断言\n"
            "- 首页"
        ),
        preconditions=[],
        steps=[{"index": 1, "instruction": "打开 fixture-app 首页"}],
        assertions=[
            {
                "type": "page_text_exists",
                "value": "首页",
                "priority": "must",
            }
        ],
    )


class FixtureCall:
    def __init__(self, responses: dict[str, list[dict]]) -> None:
        self.responses = {action: list(items) for action, items in responses.items()}
        self.requests: list[UniversalRequest] = []

    def __call__(
        self,
        _config: RunnerConfig,
        request: UniversalRequest,
    ) -> Mapping[str, object]:
        self.requests.append(request)
        if request.action == "ListAgentRunTaskByThread" and request.action not in self.responses:
            return {
                "ResponseMetadata": {
                    "RequestId": "req-list-task-empty",
                    "Action": "ListAgentRunTaskByThread",
                    "Version": "2023-08-01",
                    "Service": "ipaas",
                    "Region": "cn-north-1",
                },
                "Result": {"ThreadGroups": []},
            }
        return deepcopy(self.responses[request.action].pop(0))


def task_status_response(status: int, run_id: str = "run-sanitized") -> dict:
    return {
        "ResponseMetadata": {
            "RequestId": f"req-list-task-{status}",
            "Action": "ListAgentRunTaskByThread",
            "Version": "2023-08-01",
            "Service": "ipaas",
            "Region": "cn-north-1",
        },
        "Result": {
            "ThreadGroups": [
                {
                    "ThreadId": "thread-sanitized",
                    "Tasks": [
                        {
                            "RunId": run_id,
                            "ThreadId": "thread-sanitized",
                            "RunName": "task_task-real-contract",
                            "Status": status,
                        }
                    ],
                }
            ]
        },
    }


@pytest.mark.parametrize("fixture_name", FIXTURE_HASHES)
def test_real_contract_fixture_is_valid_and_secret_free(fixture_name):
    raw = fixture_path(fixture_name).read_text(encoding="utf-8")
    payload = load_fixture(fixture_name)

    assert payload["ResponseMetadata"]["Service"] == "ipaas"
    assert payload["ResponseMetadata"]["Version"] == "2023-08-01"
    assert not SECRET_PATTERN.search(raw)
    assert (
        hashlib.sha256(raw.encode()).hexdigest()
        == FIXTURE_HASHES[fixture_name]
    )


def test_real_contract_readme_pins_source_and_fixture_hashes():
    readme = fixture_path("README.md").read_text(encoding="utf-8")

    assert "e5f81dc5e86594a78759943ad88ca69d52367684" in readme
    for fixture_name, digest in FIXTURE_HASHES.items():
        assert f"`{fixture_name}`: `{digest}`" in readme


def test_real_contract_fixtures_preserve_universal_wrappers_and_enums():
    started = load_fixture("run_started.json")
    finished = load_fixture("step_finished.json")
    pending = load_fixture("result_pending.json")
    cancelled = load_fixture("result_cancelled.json")
    cancel_accepted = load_fixture("cancel_accepted.json")

    assert started["Result"] == {"RunId": "run-sanitized"}
    assert set(finished["Result"]["Results"][0]) == {
        "Action",
        "Param",
        "StepResult",
        "Timestamp",
    }
    assert pending["Result"]["IsSuccess"] == 0
    assert cancelled["Result"]["IsSuccess"] == 5
    assert cancel_accepted["Result"] is None


def test_real_contract_sdk_spy_preserves_start_action_and_body(monkeypatch):
    calls = []
    configurations = []
    clients = []

    class Configuration:
        def __init__(self) -> None:
            self.auto_retry = True
            configurations.append(self)

    class Flatten:
        def __init__(self, body) -> None:
            self.body = body

        def flat(self):
            return self.body

    class ApiClient:
        def __init__(self, configuration) -> None:
            self.configuration = configuration
            self.default_headers = {}
            clients.append(self)

        def set_default_header(self, name, value) -> None:
            self.default_headers[name] = value

    class UniversalApi:
        def __init__(self, _client) -> None:
            pass

        def do_call(self, info, body):
            calls.append((info, body))
            return load_fixture("run_started.json")

    fake_sdk = SimpleNamespace(
        Configuration=Configuration,
        ApiClient=ApiClient,
        UniversalApi=UniversalApi,
        UniversalInfo=lambda **kwargs: SimpleNamespace(**kwargs),
        Flatten=Flatten,
    )
    monkeypatch.setitem(sys.modules, "volcenginesdkcore", fake_sdk)
    body = {
        "SystemPrompt": "fixture system prompt",
        "UseBase64Screenshot": True,
        "IsScreenRecord": False,
    }

    response = call_universal(
        mobile_config().model_copy(
            update={"request_headers": {"X-Env": "test", "X-Source": "mua"}}
        ),
        UniversalRequest(
            service="ipaas",
            action="RunAgentTaskOneStep",
            version="2023-08-01",
            method="POST",
            body=body,
        ),
    )

    assert response == load_fixture("run_started.json")
    assert len(calls) == 1
    info, flattened_body = calls[0]
    assert vars(info) == {
        "method": "POST",
        "action": "RunAgentTaskOneStep",
        "service": "ipaas",
        "version": "2023-08-01",
        "content_type": "application/json",
    }
    assert flattened_body == body
    assert flattened_body["SystemPrompt"]
    assert flattened_body["UseBase64Screenshot"] is True
    assert flattened_body["IsScreenRecord"] is False
    assert configurations[0].auto_retry is False
    assert clients[0].default_headers == {"X-Env": "test", "X-Source": "mua"}


@pytest.mark.asyncio
async def test_real_contract_start_and_pass_lifecycle_use_raw_fixtures():
    finished = load_fixture("step_finished.json")
    running = deepcopy(finished)
    running["Result"]["Results"] = running["Result"]["Results"][:-1]
    call = FixtureCall(
        {
            "RunAgentTaskOneStep": [load_fixture("run_started.json")],
            "ListAgentRunCurrentStep": [running, finished, finished],
            "GetAgentResult": [
                load_fixture("result_pending.json"),
                load_fixture("result_pass_struct.json"),
            ],
        }
    )
    gateway = UniversalGateway(call=call)
    request = run_request()
    runner = MobileUseRunner(
        mobile_config(),
        gateway,
        request_loader=lambda task_id: request if task_id == request.task_id else None,
    )

    handle = await runner.start(request, "real-contract")
    running_page = await runner.poll(handle, after_sequence=0)
    pending_page = await runner.poll(handle, after_sequence=1)
    terminal_page = await runner.poll(handle, after_sequence=1)

    assert call.requests[0].body["Timeout"] == 120
    assert handle == RunHandle(
        "task-real-contract",
        "mobile_use",
        "run-sanitized",
    )
    assert running_page == PollResult(
        events=(
            RunnerEvent(
                1,
                "task_started",
                {"task_id": "task-real-contract"},
            ),
        ),
        terminal=False,
    )
    assert pending_page == PollResult(events=(), terminal=False)
    assert terminal_page.terminal is True
    assert len(terminal_page.events) == 1
    terminal_event = terminal_page.events[0]
    assert (terminal_event.sequence, terminal_event.type) == (2, "task_finished")
    assert terminal_event.payload["verdict"] == "pass"
    assert terminal_event.payload["evidence_complete"] is True
    assert terminal_event.payload["remote_state"] == "success"
    assert terminal_event.payload["failure_type"] is None
    assert terminal_event.payload["evidence"] == ["截图显示首页标题"]
    assert terminal_event.payload["remote_status_code"] == 1
    assert terminal_event.payload["result_assets"]["usage"] == {
        "in_tokens": 123,
        "out_tokens": "45",
    }
    assert call.requests[0].action == "RunAgentTaskOneStep"
    assert call.requests[0].body["SystemPrompt"]
    assert call.requests[0].body["AgentType"] == "cua"
    assert call.requests[0].body["Ecsid"] == "pod-sanitized"
    assert "UseBase64Screenshot" not in call.requests[0].body
    assert "IsScreenRecord" not in call.requests[0].body


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [1, 2, 4])
async def test_list_agent_run_task_active_statuses_keep_polling(
    status: int,
    caplog,
):
    call = FixtureCall(
        {
            "ListAgentRunTaskByThread": [task_status_response(status)],
            "ListAgentRunCurrentStep": [load_fixture("step_finished.json")],
            "GetAgentResult": [load_fixture("result_pass_struct.json")],
        }
    )
    request = run_request()
    runner = MobileUseRunner(
        mobile_config(),
        UniversalGateway(call=call),
        request_loader=lambda _task_id: request,
    )

    with caplog.at_level(logging.INFO, logger="cua_platform.mobile_use"):
        page = await runner.poll(
            RunHandle(request.task_id, "mobile_use", "run-sanitized"),
            after_sequence=0,
        )

    assert page == PollResult(
        events=(RunnerEvent(1, "task_started", {"task_id": request.task_id}),),
        terminal=False,
    )
    assert [request.action for request in call.requests] == [
        "ListAgentRunTaskByThread"
    ]
    status_log = next(
        record
        for record in caplog.records
        if record.message == "mobile_use_remote_task_status"
    )
    assert status_log.task_id == request.task_id
    assert status_log.run_id == "run-sanitized"
    assert status_log.remote_status_code == status
    assert status_log.decision == "running"


@pytest.mark.asyncio
async def test_list_agent_run_task_completed_status_fetches_result():
    call = FixtureCall(
        {
            "ListAgentRunTaskByThread": [task_status_response(3)],
            "ListAgentRunCurrentStep": [load_fixture("step_finished.json")],
            "GetAgentResult": [load_fixture("result_pass_struct.json")],
        }
    )
    request = run_request()
    runner = MobileUseRunner(
        mobile_config(),
        UniversalGateway(call=call),
        request_loader=lambda _task_id: request,
    )

    page = await runner.poll(
        RunHandle(request.task_id, "mobile_use", "run-sanitized"),
        after_sequence=1,
    )

    assert page.terminal is True
    assert page.events[-1].type == "task_finished"
    assert page.events[-1].payload["remote_status_code"] == 1
    assert [request.action for request in call.requests] == [
        "ListAgentRunTaskByThread",
        "GetAgentResult",
    ]


@pytest.mark.asyncio
async def test_list_agent_run_task_cancelled_status_finishes_cancelled():
    call = FixtureCall(
        {"ListAgentRunTaskByThread": [task_status_response(5)]}
    )
    request = run_request()
    runner = MobileUseRunner(
        mobile_config(),
        UniversalGateway(call=call),
        request_loader=lambda _task_id: request,
    )

    page = await runner.poll(
        RunHandle(request.task_id, "mobile_use", "run-sanitized"),
        after_sequence=1,
    )

    assert page == PollResult(
        events=(
            RunnerEvent(
                2,
                "task_cancelled",
                {"remote_status_code": 5, "remote_state": "cancelled"},
            ),
        ),
        terminal=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "remote_state"),
    [(6, "failed"), (7, "interrupted")],
)
async def test_list_agent_run_task_failure_statuses_finish_failed(
    status: int,
    remote_state: str,
):
    call = FixtureCall(
        {"ListAgentRunTaskByThread": [task_status_response(status)]}
    )
    request = run_request()
    runner = MobileUseRunner(
        mobile_config(),
        UniversalGateway(call=call),
        request_loader=lambda _task_id: request,
    )

    page = await runner.poll(
        RunHandle(request.task_id, "mobile_use", "run-sanitized"),
        after_sequence=1,
    )

    assert page == PollResult(
        events=(
            RunnerEvent(
                2,
                "runner_interrupted",
                {
                    "failure_type": "runner_interrupted",
                    "remote_status_code": status,
                    "remote_state": remote_state,
                },
            ),
        ),
        terminal=True,
    )


@pytest.mark.asyncio
async def test_runner_start_prefers_configured_thread_id():
    call = FixtureCall({"RunAgentTaskOneStep": [load_fixture("run_started.json")]})
    request = run_request()
    runner = MobileUseRunner(
        mobile_config().model_copy(update={"thread_id": "thread-configured"}),
        UniversalGateway(call=call),
        request_loader=lambda _task_id: request,
    )

    await runner.start(request, "thread-config-check")

    assert call.requests[0].body["ThreadId"] == "thread-configured"


@pytest.mark.asyncio
async def test_real_contract_content_fail_overrides_remote_success():
    call = FixtureCall(
        {
            "ListAgentRunCurrentStep": [load_fixture("step_finished.json")],
            "GetAgentResult": [load_fixture("result_fail_content.json")],
        }
    )
    request = run_request()
    runner = MobileUseRunner(
        mobile_config(),
        UniversalGateway(call=call),
        request_loader=lambda _task_id: request,
    )

    page = await runner.poll(
        RunHandle(request.task_id, "mobile_use", "run-sanitized"),
        after_sequence=1,
    )

    assert page.terminal is True
    assert page.events[-1].type == "task_finished"
    assert page.events[-1].payload["verdict"] == "fail"
    assert page.events[-1].payload["evidence_complete"] is True
    assert page.events[-1].payload["remote_state"] == "success"
    assert page.events[-1].payload["failure_type"] == "assertion_failed"
    assert page.events[-1].payload["summary"] == "首页断言失败"
    assert page.events[-1].payload["evidence"] == ["截图缺少首页标题"]
    assert page.events[-1].payload["remote_status_code"] == 1


@pytest.mark.asyncio
async def test_real_contract_terminal_step_status_checks_result_even_without_finished_action():
    timed_out_step = {
        "ResponseMetadata": {
            "RequestId": "req-step-timeout",
            "Action": "ListAgentRunCurrentStep",
            "Version": "2023-08-01",
            "Service": "ipaas",
            "Region": "cn-north-1",
        },
        "Result": {
            "RunId": "run-timeout",
            "ThreadId": "thread-timeout",
            "Results": [
                {
                    "Action": "wait",
                    "Param": {
                        "description": "继续等待下载完成",
                        "t": 10,
                    },
                    "StepResult": {"IsSuccess": False, "Result": ""},
                    "Timestamp": "2026-07-29T06:36:01.422000Z",
                }
            ],
            "Status": 6,
            "StepId": "step-timeout",
        },
    }
    timed_out_result = {
        "ResponseMetadata": {
            "RequestId": "req-result-timeout",
            "Action": "GetAgentResult",
            "Version": "2023-08-01",
            "Service": "ipaas",
            "Region": "cn-north-1",
        },
        "Result": {
            "IsSuccess": 2,
            "Content": "任务执行超时（timeout），已终止。可调大 timeout 或缩短任务后重试。",
            "Usage": {"in_tokens": 140359, "out_tokens": 738},
            "RecordingUrl": "https://example.invalid/recording.mp4",
        },
    }
    call = FixtureCall(
        {
            "ListAgentRunCurrentStep": [timed_out_step],
            "GetAgentResult": [timed_out_result],
        }
    )
    request = run_request()
    runner = MobileUseRunner(
        mobile_config(),
        UniversalGateway(call=call),
        request_loader=lambda _task_id: request,
    )

    page = await runner.poll(
        RunHandle(request.task_id, "mobile_use", "run-timeout"),
        after_sequence=1,
    )

    assert page.terminal is True
    assert len(page.events) == 1
    event = page.events[0]
    assert (event.sequence, event.type) == (2, "runner_interrupted")
    assert event.payload["failure_type"] == "runner_interrupted"
    assert event.payload["remote_state"] == "exec_failed"
    assert event.payload["summary"] == "任务执行超时（timeout），已终止。可调大 timeout 或缩短任务后重试。"
    assert event.payload["remote_status_code"] == 2
    assert event.payload["recording_url"] == "https://example.invalid/recording.mp4"
    assert event.payload["result_assets"]["usage"] == {
        "in_tokens": 140359,
        "out_tokens": 738,
    }


@pytest.mark.asyncio
async def test_real_contract_request_user_without_valid_output_fails_safely():
    no_output = deepcopy(load_fixture("result_pass_struct.json"))
    no_output["Result"]["StructOutput"] = None
    no_output["Result"]["Content"] = "需要用户确认，未生成结构化结论"
    call = FixtureCall(
        {
            "ListAgentRunCurrentStep": [load_fixture("step_request_user.json")],
            "GetAgentResult": [no_output],
        }
    )
    request = run_request()
    runner = MobileUseRunner(
        mobile_config(),
        UniversalGateway(call=call),
        request_loader=lambda _task_id: request,
    )

    page = await runner.poll(
        RunHandle(request.task_id, "mobile_use", "run-sanitized"),
        after_sequence=1,
    )

    assert page.terminal is True
    assert len(page.events) == 1
    event = page.events[0]
    assert (event.sequence, event.type) == (2, "task_finished")
    assert event.payload["verdict"] == "fail"
    assert event.payload["evidence_complete"] is False
    assert event.payload["remote_state"] == "success"
    assert event.payload["failure_type"] == "evidence_missing"
    assert event.payload["summary"] == "需要用户确认，未生成结构化结论"
    assert event.payload["remote_status_code"] == 1


@pytest.mark.asyncio
async def test_real_contract_cancel_acceptance_requires_terminal_result():
    call = FixtureCall(
        {
            "CancelTask": [load_fixture("cancel_accepted.json")],
            "ListAgentRunCurrentStep": [load_fixture("step_finished.json")],
            "GetAgentResult": [load_fixture("result_cancelled.json")],
        }
    )
    request = run_request()
    runner = MobileUseRunner(
        mobile_config(),
        UniversalGateway(call=call),
        request_loader=lambda _task_id: request,
    )
    handle = RunHandle(request.task_id, "mobile_use", "run-sanitized")

    accepted = await runner.cancel(handle)
    terminal = await runner.poll(handle, after_sequence=1)

    assert accepted == CancelResult(accepted=True, terminal=False)
    assert terminal.terminal is True
    assert len(terminal.events) == 1
    event = terminal.events[0]
    assert (event.sequence, event.type) == (2, "task_cancelled")
    assert event.payload == {
        "remote_state": "user_cancelled",
        "result_assets": {"content": "用户取消"},
        "remote_status_code": 5,
    }


@pytest.mark.asyncio
async def test_real_contract_gateway_extracts_start_request_id():
    gateway = UniversalGateway(
        call=FixtureCall(
            {"RunAgentTaskOneStep": [load_fixture("run_started.json")]}
        )
    )

    result = await gateway.start_one_step(mobile_config(), {"RunName": "fixture"})

    assert result == RemoteRun("run-sanitized", "req-run-started")
