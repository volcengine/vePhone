from types import SimpleNamespace

from cua_platform.tasks.models import Task, TaskRunnerConfig
from cua_platform.tasks.state_machine import ExecutionStatus


def _create_case(client, title: str) -> str:
    response = client.post(
        "/api/v1/cases",
        json={
            "title": title,
            "module": "执行轨迹",
            "content_markdown": "## 执行任务（必填）\n\n- 打开抖音APP",
            "tags": ["trace"],
            "automation_level": "auto",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


class RecordingRuntimeGateway:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def list_current_step(self, _config, _run_id):
        self.calls.append("ListAgentRunCurrentStep")
        return SimpleNamespace(
            payload={
                "Result": {
                    "RunId": "run-runtime",
                    "ThreadId": "thread-runtime",
                    "Status": 2,
                    "StepId": "step-current",
                    "Results": [],
                },
            },
        )

    async def get_result(self, _config, _run_id):
        self.calls.append("GetAgentResult")
        return SimpleNamespace(
            payload={
                "Result": {
                    "Content": "任务运行中",
                    "ScreenShots": {
                        "old-runtime-0": {
                            "screenshot": "https://example.invalid/old.png",
                        },
                        "run-runtime-0": {
                            "screenshot": "https://example.invalid/current.png",
                        },
                    },
                    "TotalSteps": 4,
                    "DurationMs": 72000,
                    "DurationFmt": "1m12s",
                    "AvgStepDurationSec": 18,
                },
            },
        )

    async def list_task_by_thread(self, _config, *, thread_id, run_id):
        self.calls.append("ListAgentRunTaskByThread")
        return SimpleNamespace(
            payload={
                "Result": {
                    "ThreadGroups": [
                        {
                            "ThreadId": thread_id,
                            "Tasks": [
                                {
                                    "RunId": run_id,
                                    "ThreadId": thread_id,
                                    "Status": 2,
                                },
                            ],
                        }
                    ],
                },
            },
        )

    async def detail_task_by_thread(self, _config, *, thread_id: str, run_id: str):
        _ = (thread_id, run_id)
        self.calls.append("DetailAgentRunTaskByThread")
        return SimpleNamespace(payload={"Result": {"RunSteps": []}})


def test_runtime_skips_thread_detail_while_task_is_running(
    authenticated_client,
    monkeypatch,
):
    case_id = _create_case(authenticated_client, "运行中轨迹")
    with authenticated_client.app.state.session_factory() as db:
        task = Task(
            id="task_runtime_running",
            case_id=case_id,
            runner_type="mobile_use",
            scenario="运行中轨迹",
            execution_status=ExecutionStatus.RUNNING,
            idempotency_key="runtime-running",
            request_fingerprint="{}",
            remote_run_id="run-runtime",
            remote_thread_id="thread-runtime",
            created_by="admin",
        )
        task.runner_config = TaskRunnerConfig(
            config_snapshot={
                "product_id": "prod-runtime",
                "tos_bucket": "mua-test",
                "tos_region": "cn-beijing",
                "request_headers": {
                    "X-Env": "runtime",
                    "X-Api-Key": "sk_live_1234567890abcdef",
                },
            },
        )
        db.add(task)
        db.commit()

    gateway = RecordingRuntimeGateway()
    monkeypatch.setattr(
        "cua_platform.api.tasks.UniversalGateway",
        lambda: gateway,
    )

    response = authenticated_client.get("/api/v1/tasks/task_runtime_running/runtime")

    assert response.status_code == 200
    body = response.json()
    assert body["current_step"]["step_id"] == "step-current"
    assert body["thread_steps"] == []
    assert body["result"]["assets"]["screenshots"] == {
        "run-runtime-0": {"screenshot": "https://example.invalid/current.png"}
    }
    assert body["result"]["assets"]["total_steps"] == 4
    assert body["result"]["assets"]["duration_ms"] == 72000
    assert body["result"]["assets"]["duration_fmt"] == "1m12s"
    assert body["result"]["assets"]["avg_step_duration_sec"] == 18
    assert body["execution_config"]["source"] == "legacy"
    assert body["execution_config"]["request_headers"] == {
        "configured": True,
        "names": ["X-Env", "X-Api-Key"],
        "items": [
            {"name": "X-Env", "value": "runtime"},
            {"name": "X-Api-Key", "value": "sk_l***cdef"},
        ],
    }
    assert "sk_live_1234567890abcdef" not in response.text
    assert gateway.calls == [
        "ListAgentRunCurrentStep",
        "GetAgentResult",
        "ListAgentRunTaskByThread",
    ]


def test_runtime_keeps_mua_trace_queries_with_current_step_only_param(
    authenticated_client,
    monkeypatch,
):
    case_id = _create_case(authenticated_client, "完整轨迹")
    with authenticated_client.app.state.session_factory() as db:
        task = Task(
            id="task_runtime_current_only",
            case_id=case_id,
            runner_type="mobile_use",
            scenario="完整轨迹",
            execution_status=ExecutionStatus.RUNNING,
            idempotency_key="runtime-current-only",
            request_fingerprint="{}",
            remote_run_id="run-runtime",
            remote_thread_id="thread-runtime",
            created_by="admin",
        )
        task.runner_config = TaskRunnerConfig(config_snapshot={})
        db.add(task)
        db.commit()

    gateway = RecordingRuntimeGateway()
    monkeypatch.setattr(
        "cua_platform.api.tasks.UniversalGateway",
        lambda: gateway,
    )

    response = authenticated_client.get(
        "/api/v1/tasks/task_runtime_current_only/runtime?current_step_only=true"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["current_step"]["step_id"] == "step-current"
    assert body["thread_groups"][0]["tasks"][0]["run_id"] == "run-runtime"
    assert body["thread_steps"] == []
    assert gateway.calls == [
        "ListAgentRunCurrentStep",
        "GetAgentResult",
        "ListAgentRunTaskByThread",
    ]


def test_runtime_uses_local_mock_trace_assets(authenticated_client):
    case_id = _create_case(authenticated_client, "本地 mock 轨迹")
    with authenticated_client.app.state.session_factory() as db:
        task = Task(
            id="task_mock_trace",
            case_id=case_id,
            runner_type="mobile_use",
            scenario="本地 mock 轨迹",
            execution_status=ExecutionStatus.RESULT_READY,
            idempotency_key="mock-trace",
            request_fingerprint="{}",
            result_assets={
                "current_step": {
                    "run_id": "run-mock-trace",
                    "thread_id": "thread-mock-trace",
                    "status": 3,
                    "step_id": "mock-finished",
                    "results": [],
                },
                "thread_groups": [
                    {
                        "thread_id": "thread-mock-trace",
                        "task_next_token": None,
                        "tasks": [
                            {
                                "run_id": "run-mock-trace",
                                "thread_id": "thread-mock-trace",
                                "run_name": "本地 mock 轨迹",
                                "status": 3,
                                "pod_id": "ecs-alpha",
                                "product_id": "prod-alpha",
                                "created_at": "2026-08-12 11:00:00 +0800 CST",
                                "started_at": "2026-08-12 11:00:02 +0800 CST",
                                "updated_at": "2026-08-12 11:01:00 +0800 CST",
                                "completed_at": "2026-08-12 11:01:00 +0800 CST",
                                "trace_id": "trace-mock",
                                "artifact_count": {"Screenshot": 4},
                            }
                        ],
                    }
                ],
                "thread_steps": [
                    {
                        "run_id": "run-mock-trace",
                        "thread_id": "thread-mock-trace",
                        "status": 3,
                        "step_id": "mock-step-1",
                        "results": [
                            {
                                "Action": "observe",
                                "Param": {"content": "观察页面是否加载"},
                                "StepResult": {"IsSuccess": True, "Result": "页面加载完成"},
                                "Timestamp": "2026-08-12T11:00:10+08:00",
                            }
                        ],
                    }
                ],
            },
            created_by="admin",
        )
        task.runner_config = TaskRunnerConfig(
            config_snapshot={"pod_id": "ecs-alpha", "product_id": "prod-alpha"}
        )
        db.add(task)
        db.commit()

    response = authenticated_client.get("/api/v1/tasks/task_mock_trace/runtime")

    assert response.status_code == 200
    body = response.json()
    assert body["current_step"]["step_id"] == "mock-finished"
    assert body["thread_groups"][0]["tasks"][0]["pod_id"] == "ecs-alpha"
    assert body["thread_steps"][0]["results"][0]["Action"] == "observe"


def test_runtime_does_not_fall_back_to_cached_screenshots(
    authenticated_client,
    monkeypatch,
):
    case_id = _create_case(authenticated_client, "实时截图优先")
    with authenticated_client.app.state.session_factory() as db:
        task = Task(
            id="task_runtime_no_cached_screenshots",
            case_id=case_id,
            runner_type="mobile_use",
            scenario="实时截图优先",
            execution_status=ExecutionStatus.RESULT_READY,
            idempotency_key="runtime-no-cached-screenshots",
            request_fingerprint="{}",
            remote_run_id="run-runtime",
            remote_thread_id="thread-runtime",
            result_assets={
                "screenshots": {
                    "run-runtime-0": {
                        "screenshot": "https://example.invalid/cached.png",
                    },
                },
                "files": ["/sdk_files/run-runtime/result.md"],
            },
            created_by="admin",
        )
        task.runner_config = TaskRunnerConfig(config_snapshot={})
        db.add(task)
        db.commit()

    class ResultFailureGateway(RecordingRuntimeGateway):
        async def get_result(self, _config, _run_id):
            self.calls.append("GetAgentResult")
            raise RuntimeError("remote result unavailable")

    gateway = ResultFailureGateway()
    monkeypatch.setattr(
        "cua_platform.api.tasks.UniversalGateway",
        lambda: gateway,
    )

    response = authenticated_client.get(
        "/api/v1/tasks/task_runtime_no_cached_screenshots/runtime"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["assets"]["screenshots"] == {
        "run-runtime-0": {"screenshot": "https://example.invalid/cached.png"}
    }
    assert body["result"]["assets"]["files"] == ["/sdk_files/run-runtime/result.md"]
    assert body["errors"]["result"] == "RuntimeError"


def test_runtime_parses_top_level_thread_detail_steps(
    authenticated_client,
    monkeypatch,
):
    case_id = _create_case(authenticated_client, "终态执行步骤详情")
    with authenticated_client.app.state.session_factory() as db:
        task = Task(
            id="task_runtime_thread_detail",
            case_id=case_id,
            runner_type="mobile_use",
            scenario="终态执行步骤详情",
            execution_status=ExecutionStatus.RESULT_READY,
            idempotency_key="runtime-thread-detail",
            request_fingerprint="{}",
            remote_run_id="run-runtime",
            remote_thread_id="thread-runtime",
            created_by="admin",
        )
        task.runner_config = TaskRunnerConfig(config_snapshot={})
        db.add(task)
        db.commit()

    class TopLevelThreadDetailGateway(RecordingRuntimeGateway):
        async def detail_task_by_thread(self, _config, *, thread_id: str, run_id: str):
            assert thread_id == "thread-runtime"
            assert run_id == "run-runtime"
            self.calls.append("DetailAgentRunTaskByThread")
            return SimpleNamespace(
                payload={
                    "RunSteps": [
                        {
                            "RunId": run_id,
                            "ThreadId": thread_id,
                            "Status": 3,
                            "StepId": "step-1",
                            "Results": [
                                {
                                    "Action": "observe",
                                    "Timestamp": "2026-07-28T11:35:20+08:00",
                                },
                            ],
                        }
                    ]
                }
            )

    gateway = TopLevelThreadDetailGateway()
    monkeypatch.setattr(
        "cua_platform.api.tasks.UniversalGateway",
        lambda: gateway,
    )

    response = authenticated_client.get("/api/v1/tasks/task_runtime_thread_detail/runtime")

    assert response.status_code == 200
    body = response.json()
    assert body["thread_steps"] == [
        {
            "run_id": "run-runtime",
            "thread_id": "thread-runtime",
            "status": 3,
            "step_id": "step-1",
            "results": [
                {
                    "Action": "observe",
                    "Timestamp": "2026-07-28T11:35:20+08:00",
                }
            ],
        }
    ]
    assert gateway.calls == [
        "ListAgentRunCurrentStep",
        "GetAgentResult",
        "ListAgentRunTaskByThread",
        "DetailAgentRunTaskByThread",
    ]
