import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from mua_platform.cases.models import TestCase as CaseModel
from mua_platform.pods.repository import PodRepository
from mua_platform.pods.schemas import ListPodPage, PodDetail, PodSummary
from mua_platform.runners.base import (
    CancelResult,
    PollResult,
    RunHandle,
    RunRequest,
    RunnerEvent,
    RunnerFailure,
)
from mua_platform.runners.mock import MockRunner
from mua_platform.runners.mobile_use import MobileUseRunner
from mua_platform.runners.universal_gateway import UniversalGateway, UniversalRequest
from mua_platform.settings.repository import SettingRepository
from mua_platform.settings.service import SettingsService
from mua_platform.tasks.models import PodLease, Task, TaskEvent
from mua_platform.tasks.repository import SQLiteTaskRepository
from mua_platform.tasks.service import TaskService
from mua_platform.tasks.state_machine import ExecutionStatus, Verdict
from mua_platform.time import FakeClock
from mua_platform.test_plans.models import TagColorRegistry
from mua_platform.test_plans.service import (
    TagColorRegistryExhaustedError,
    TagColorService,
)


@pytest.fixture()
def authenticated_client(client, initialized_admin):
    return client


def _create_case(
    client,
    title: str,
    *,
    default_agent_options: dict | None = None,
) -> str:
    payload = {
        "title": title,
        "module": "登录",
        "content_markdown": "## 执行任务（必填）\n\n- 打开抖音APP",
        "tags": ["smoke"],
        "automation_level": "auto",
    }
    if default_agent_options is not None:
        payload["default_agent_options"] = default_agent_options
    response = client.post(
        "/api/v1/cases",
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_case_with_tags(client, title: str, tags: list[str]) -> str:
    response = client.post(
        "/api/v1/cases",
        json={
            "title": title,
            "module": "登录",
            "content_markdown": "## 执行任务（必填）\n\n- 打开抖音APP",
            "tags": tags,
            "automation_level": "auto",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _seed_task(
    client,
    case_id: str,
    idempotency_key: str,
    *,
    status: ExecutionStatus | None = None,
    verdict: Verdict | None = None,
) -> str:
    with client.app.state.session_factory() as db:
        repository = SQLiteTaskRepository(db)
        case = repository.get_case(case_id)
        assert case is not None
        result = repository.create_from_case(
            case,
            case.title,
            idempotency_key=idempotency_key,
            runner_type="mock",
        )
        task_id = result.task.id
        if status == ExecutionStatus.RUNNING:
            repository.mark_running(task_id)
        elif status not in {None, ExecutionStatus.QUEUED}:
            repository.mark_running(task_id)
            repository.finish(task_id, status, verdict, None)
        return task_id


def test_list_case_tasks_returns_only_that_case_newest_first(authenticated_client):
    case_id = _create_case(authenticated_client, "手机号登录成功")
    other_case_id = _create_case(authenticated_client, "无关用例")

    first_task = _seed_task(authenticated_client, case_id, "exec-1")
    second_task = _seed_task(authenticated_client, case_id, "exec-2")
    other_task = _seed_task(authenticated_client, other_case_id, "exec-3")

    response = authenticated_client.get(f"/api/v1/cases/{case_id}/tasks")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    items = body["items"]
    returned_ids = [item["id"] for item in items]
    assert other_task not in returned_ids
    assert set(returned_ids) == {first_task, second_task}
    # Newest task first.
    assert returned_ids[0] == second_task
    assert all(item["case_id"] == case_id for item in items)


def test_list_cases_tag_filter_matches_when_case_contains_tag(authenticated_client):
    matched = _create_case_with_tags(authenticated_client, "包含 smoke 标签", ["P0", "smoke"])
    _create_case_with_tags(authenticated_client, "不包含目标标签", ["P0"])

    response = authenticated_client.get("/api/v1/cases", params={"tag": "smoke"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [matched]


def test_list_case_creators_returns_distinct_active_creators(authenticated_client):
    with authenticated_client.app.state.session_factory() as db:
        from mua_platform.cases.models import TestCase

        db.add_all([
            TestCase(
                id="case_creator_admin",
                title="管理员创建",
                business_id="biz_default",
                module="登录",
                content_markdown="## 执行任务\n- 打开",
                tags=[],
                automation_level="auto",
                created_by="admin",
            ),
            TestCase(
                id="case_creator_alice",
                title="Alice 创建",
                business_id="biz_default",
                module="支付",
                content_markdown="## 执行任务\n- 打开",
                tags=[],
                automation_level="auto",
                created_by="alice",
            ),
            TestCase(
                id="case_creator_deleted",
                title="已删除",
                business_id="biz_default",
                module="支付",
                content_markdown="## 执行任务\n- 打开",
                tags=[],
                automation_level="auto",
                created_by="deleted-user",
                deleted_at=datetime.now(UTC),
            ),
        ])
        db.commit()

    response = authenticated_client.get("/api/v1/cases/creators")

    assert response.status_code == 200
    assert response.json() == {"items": ["admin", "alice"]}


def test_list_cases_includes_active_bound_plan_count(authenticated_client):
    bound = _create_case(authenticated_client, "有关联计划")
    unbound = _create_case(authenticated_client, "无关联计划")
    deleted_plan_case = _create_case(authenticated_client, "仅关联已删除计划")
    first_response = authenticated_client.post(
        "/api/v1/test-plans",
        json={
            "name": "关联计划一",
            "description": "",
            "tags": [],
            "case_ids": [bound],
        },
    )
    assert first_response.status_code == 201, first_response.text
    first_plan = first_response.json()
    second_response = authenticated_client.post(
        "/api/v1/test-plans",
        json={
            "name": "关联计划二",
            "description": "",
            "tags": [],
            "case_ids": [bound],
        },
    )
    assert second_response.status_code == 201, second_response.text
    deleted_response = authenticated_client.post(
        "/api/v1/test-plans",
        json={
            "name": "已删除关联计划",
            "description": "",
            "tags": [],
            "case_ids": [deleted_plan_case],
        },
    )
    assert deleted_response.status_code == 201, deleted_response.text
    deleted_plan = deleted_response.json()
    authenticated_client.delete(f"/api/v1/test-plans/{deleted_plan['id']}")

    response = authenticated_client.get("/api/v1/cases", params={"page_size": 100})

    assert response.status_code == 200
    by_id = {item["id"]: item for item in response.json()["items"]}
    assert by_id[bound]["bound_plan_count"] == 2
    assert by_id[unbound]["bound_plan_count"] == 0
    assert by_id[deleted_plan_case]["bound_plan_count"] == 0
    assert first_plan["case_count"] == 1


def test_list_cases_matches_repeated_tags_with_or_semantics(authenticated_client):
    first = _create_case_with_tags(authenticated_client, "A", ["P0"])
    second = _create_case_with_tags(authenticated_client, "B", ["smoke"])
    _create_case_with_tags(authenticated_client, "C", ["P2"])

    response = authenticated_client.get(
        "/api/v1/cases",
        params=[("tag", "P0"), ("tag", "smoke"), ("page_size", "10")],
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert {item["id"] for item in response.json()["items"]} == {
        first,
        second,
    }


def test_list_cases_combines_repeated_tags_with_search_and_module_using_and(
    authenticated_client,
):
    matched = _create_case_with_tags(
        authenticated_client,
        "登录核心链路",
        ["P0"],
    )
    _create_case_with_tags(
        authenticated_client,
        "支付核心链路",
        ["smoke"],
    )
    wrong_tag = _create_case_with_tags(
        authenticated_client,
        "登录非核心链路",
        ["P2"],
    )

    response = authenticated_client.get(
        "/api/v1/cases",
        params=[
            ("search", "登录核心"),
            ("module", "登录"),
            ("tag", "P0"),
            ("tag", "smoke"),
        ],
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["id"] for item in response.json()["items"]] == [matched]
    assert wrong_tag not in {
        item["id"] for item in response.json()["items"]
    }


def test_list_cases_search_uses_prefix_without_scanning_markdown_body(
    authenticated_client,
):
    matched = _create_case_with_tags(authenticated_client, "打开抖音 APP", ["P0"])
    _create_case_with_tags(authenticated_client, "完整链路验证", ["smoke"])

    response = authenticated_client.get("/api/v1/cases", params={"search": "打开"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [matched]


def test_case_create_update_and_copy_register_tags_on_write(
    authenticated_client,
):
    case_id = _create_case_with_tags(
        authenticated_client,
        "标签同步用例",
        ["创建标签"],
    )
    with authenticated_client.app.state.session_factory() as db:
        assert db.get(TagColorRegistry, "创建标签") is not None

    updated = authenticated_client.put(
        f"/api/v1/cases/{case_id}",
        json={"tags": ["更新标签"]},
    )
    assert updated.status_code == 200
    with authenticated_client.app.state.session_factory() as db:
        assert db.get(TagColorRegistry, "更新标签") is not None
        registry = db.get(TagColorRegistry, "更新标签")
        assert registry is not None
        db.delete(registry)
        db.commit()

    copied = authenticated_client.post(f"/api/v1/cases/{case_id}/copy")

    assert copied.status_code == 201
    assert copied.json()["tags"] == ["更新标签"]
    with authenticated_client.app.state.session_factory() as db:
        assert db.get(TagColorRegistry, "更新标签") is not None


def test_case_default_agent_options_are_saved_and_returned(
    authenticated_client,
):
    case_id = _create_case(
        authenticated_client,
        "带默认执行配置用例",
        default_agent_options={
            "thread_id": "thread-case-default",
            "max_step": 123,
            "timeout_seconds": 456,
            "retry_limit": 7,
            "screen_record": True,
            "tos_bucket": "case-bucket",
            "tos_region": "cn-beijing",
            "mcp_json": '{"mcpServers":{}}',
        },
    )

    fetched = authenticated_client.get(f"/api/v1/cases/{case_id}")

    assert fetched.status_code == 200
    assert fetched.json()["default_agent_options"] | {
        "thread_id": "thread-case-default",
        "max_step": 123,
        "timeout_seconds": 456,
        "retry_limit": 7,
        "screen_record": True,
        "tos_bucket": "case-bucket",
        "tos_region": "cn-beijing",
        "mcp_json": '{"mcpServers":{}}',
    } == fetched.json()["default_agent_options"]


def test_case_default_agent_options_can_be_enabled_by_update(
    authenticated_client,
):
    case_id = _create_case(authenticated_client, "后续启用默认配置")

    updated = authenticated_client.put(
        f"/api/v1/cases/{case_id}",
        json={
            "default_agent_options": {
                "thread_id": "thread-updated-default",
                "max_step": 88,
                "timeout_seconds": 222,
            },
        },
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["default_agent_options"]["thread_id"] == (
        "thread-updated-default"
    )
    with authenticated_client.app.state.session_factory() as db:
        case = db.get(CaseModel, case_id)
        assert case is not None
        assert case.default_agent_options["thread_id"] == (
            "thread-updated-default"
        )
        assert case.default_agent_options["max_step"] == 88


def test_case_writes_return_stable_error_and_roll_back_when_tag_registration_fails(
    authenticated_client,
    monkeypatch,
):
    case_id = _create_case_with_tags(
        authenticated_client,
        "标签注册原始用例",
        ["原始标签"],
    )

    def fail_registration(_service, _names):
        raise TagColorRegistryExhaustedError("tag color registry exhausted")

    monkeypatch.setattr(TagColorService, "ensure", fail_registration)

    created = authenticated_client.post(
        "/api/v1/cases",
        json={
            "title": "标签注册失败用例",
            "module": "登录",
            "content_markdown": "执行",
            "tags": ["无法注册"],
            "automation_level": "auto",
        },
    )
    updated = authenticated_client.put(
        f"/api/v1/cases/{case_id}",
        json={"title": "不应保存的新标题", "tags": ["无法更新"]},
    )
    copied = authenticated_client.post(f"/api/v1/cases/{case_id}/copy")

    for response in (created, updated, copied):
        assert response.status_code == 409
        assert response.json()["error"]["code"] == (
            "tag_color_registry_exhausted"
        )

    with authenticated_client.app.state.session_factory() as db:
        assert db.scalar(
            select(func.count(CaseModel.id)).where(
                CaseModel.title == "标签注册失败用例"
            )
        ) == 0
        assert db.get(TagColorRegistry, "无法注册") is None
        original = db.get(CaseModel, case_id)
        assert original is not None
        assert original.title == "标签注册原始用例"
        assert original.tags == ["原始标签"]
        assert db.scalar(
            select(func.count(CaseModel.id)).where(
                CaseModel.title.like("标签注册原始用例%副本")
            )
        ) == 0


def test_list_case_tasks_paginates(authenticated_client):
    case_id = _create_case(authenticated_client, "分页用例")
    task_ids = [_seed_task(authenticated_client, case_id, f"exec-{i}") for i in range(3)]

    first = authenticated_client.get(
        f"/api/v1/cases/{case_id}/tasks", params={"page": 1, "page_size": 2}
    )
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["total"] == 3
    assert first_body["page"] == 1
    assert first_body["page_size"] == 2
    assert len(first_body["items"]) == 2
    # Newest first: last seeded task leads.
    assert first_body["items"][0]["id"] == task_ids[-1]

    second = authenticated_client.get(
        f"/api/v1/cases/{case_id}/tasks", params={"page": 2, "page_size": 2}
    )
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["total"] == 3
    assert len(second_body["items"]) == 1
    assert second_body["items"][0]["id"] == task_ids[0]


def test_list_case_tasks_empty_for_case_without_runs(authenticated_client):
    case_id = _create_case(authenticated_client, "尚未执行的用例")

    response = authenticated_client.get(f"/api/v1/cases/{case_id}/tasks")

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_list_case_tasks_unknown_case_returns_404(authenticated_client):
    response = authenticated_client.get("/api/v1/cases/case_missing/tasks")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "case_not_found"


def test_case_stats_aggregate_all_cases(authenticated_client):
    first_case_id = _create_case(authenticated_client, "统计用例一")
    second_case_id = _create_case(authenticated_client, "统计用例二")
    first_pass_ids = []
    for index in range(2):
        first_pass_ids.append(_seed_task(
            authenticated_client,
            first_case_id,
            f"first-pass-{index}",
            status=ExecutionStatus.RESULT_READY,
            verdict=Verdict.PASS,
        ))
    first_fail_id = _seed_task(
        authenticated_client,
        first_case_id,
        "first-fail",
        status=ExecutionStatus.RESULT_READY,
        verdict=Verdict.FAIL,
    )
    second_pass_id = _seed_task(
        authenticated_client,
        second_case_id,
        "second-pass",
        status=ExecutionStatus.RESULT_READY,
        verdict=Verdict.PASS,
    )
    second_cancelled_id = _seed_task(
        authenticated_client,
        second_case_id,
        "second-cancelled",
        status=ExecutionStatus.CANCELLED,
    )
    _seed_task(authenticated_client, second_case_id, "second-queued")
    with authenticated_client.app.state.session_factory() as db:
        from mua_platform.cases.models import TestCase

        shanghai_now = datetime.now(ZoneInfo("Asia/Shanghai"))
        today_start = shanghai_now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        ).astimezone(UTC)
        first_case = db.get(TestCase, first_case_id)
        second_case = db.get(TestCase, second_case_id)
        assert first_case is not None
        assert second_case is not None
        first_case.execution_count = 99
        first_case.pass_count = 99
        first_case.fail_count = 0
        second_case.execution_count = 99
        second_case.pass_count = 99
        second_case.fail_count = 0
        second_case.automation_level = "manual_confirm"
        db.get(Task, first_pass_ids[0]).finished_at = today_start + timedelta(hours=1)
        db.get(Task, first_pass_ids[1]).finished_at = today_start + timedelta(hours=2)
        db.get(Task, first_fail_id).finished_at = today_start - timedelta(hours=1)
        db.get(Task, second_pass_id).finished_at = today_start + timedelta(hours=3)
        db.get(Task, second_cancelled_id).finished_at = today_start + timedelta(hours=4)
        db.commit()

    response = authenticated_client.get("/api/v1/cases/stats")

    assert response.status_code == 200
    assert response.json() == {
        "total": 2,
        "auto_count": 1,
        "today_executions": 3,
        "total_executions": 4,
        "pass_rate": 75,
    }


def test_case_statistics_are_derived_from_terminal_tasks(authenticated_client):
    case_id = _create_case(authenticated_client, "终态任务统计用例")
    passed_id = _seed_task(
        authenticated_client,
        case_id,
        "statistics-pass",
        status=ExecutionStatus.RESULT_READY,
        verdict=Verdict.PASS,
    )
    failed_id = _seed_task(
        authenticated_client,
        case_id,
        "statistics-fail",
        status=ExecutionStatus.RESULT_READY,
        verdict=Verdict.FAIL,
    )
    cancelled_id = _seed_task(
        authenticated_client,
        case_id,
        "statistics-cancelled",
        status=ExecutionStatus.CANCELLED,
    )
    running_id = _seed_task(
        authenticated_client,
        case_id,
        "statistics-running",
        status=ExecutionStatus.RUNNING,
    )
    expected_latest = datetime(2026, 1, 2, 12, tzinfo=UTC)
    with authenticated_client.app.state.session_factory() as db:
        from mua_platform.cases.models import TestCase

        case = db.get(TestCase, case_id)
        assert case is not None
        case.execution_count = 99
        case.pass_count = 99
        case.fail_count = 0
        db.get(Task, passed_id).finished_at = expected_latest - timedelta(days=1)
        db.get(Task, failed_id).finished_at = expected_latest
        db.get(Task, cancelled_id).finished_at = expected_latest + timedelta(days=1)
        db.get(Task, running_id).finished_at = expected_latest + timedelta(days=2)
        db.commit()

    expected_statistics = {
        "execution_count": 2,
        "pass_count": 1,
        "fail_count": 1,
        "last_executed_at": expected_latest.isoformat().replace("+00:00", "Z"),
    }

    list_response = authenticated_client.get("/api/v1/cases")
    detail_response = authenticated_client.get(f"/api/v1/cases/{case_id}")

    assert list_response.status_code == 200
    listed_case = next(
        item for item in list_response.json()["items"] if item["id"] == case_id
    )
    assert {
        key: listed_case[key] for key in expected_statistics
    } == expected_statistics
    assert detail_response.status_code == 200
    assert {
        key: detail_response.json()[key] for key in expected_statistics
    } == expected_statistics


@pytest.mark.asyncio
async def test_runner_task_cancelled_event_finishes_task_as_cancelled(
    authenticated_client,
    caplog,
):
    class CancellingRunner:
        async def start(self, request, idempotency_key):
            assert idempotency_key
            return RunHandle(
                task_id=request.task_id,
                runner_type="mock",
                run_id=f"cancelled:{request.task_id}",
            )

        async def poll(self, handle, after_sequence):
            assert after_sequence == 0
            return PollResult(
                events=(
                    RunnerEvent(
                        sequence=1,
                        type="task_started",
                        payload={"task_id": handle.task_id},
                    ),
                    RunnerEvent(
                        sequence=2,
                        type="task_cancelled",
                        payload={
                            "remote_status_code": 5,
                            "remote_state": "cancelled",
                        },
                    ),
                ),
                terminal=True,
            )

    case_id = _create_case(authenticated_client, "远端取消任务")
    with authenticated_client.app.state.session_factory() as db:
        repository = SQLiteTaskRepository(db)
        case = repository.get_case(case_id)
        assert case is not None
        task_id = repository.create_from_case(
            case,
            "远端取消任务",
            idempotency_key="remote-cancelled",
            runner_type="mock",
        ).task.id
        with caplog.at_level(logging.INFO, logger="mua_platform.tasks"):
            completed = await TaskService(
                repository,
                runner=CancellingRunner(),
            ).run_task(task_id, worker_id="worker:test")

        assert completed.execution_status == ExecutionStatus.CANCELLED
        assert completed.verdict is None
        assert completed.remote_status_code == 5
        terminal_log = next(
            record
            for record in caplog.records
            if record.message == "task_runner_event_recorded"
            and record.event_type == "task_cancelled"
        )
        assert terminal_log.task_id == task_id
        assert terminal_log.local_status == "cancelled"
        assert terminal_log.remote_status_code == 5


@pytest.mark.asyncio
async def test_device_prepare_failure_finishes_task_before_agent_start(
    authenticated_client,
):
    class PrepareFailingRunner:
        started = False

        async def prepare_device(self, request):
            raise RunnerFailure(
                "reset_pod_failed",
                "device_prepare_failed",
                "req-prepare-failed",
            )

        async def start(self, request, idempotency_key):
            self.started = True
            return RunHandle(
                task_id=request.task_id,
                runner_type="mock",
                run_id=f"started:{request.task_id}",
            )

        async def poll(self, handle, after_sequence):
            return PollResult(
                events=(
                    RunnerEvent(
                        sequence=1,
                        type="task_started",
                        payload={"task_id": handle.task_id},
                    ),
                    RunnerEvent(
                        sequence=2,
                        type="task_finished",
                        payload={
                            "verdict": "pass",
                            "summary": "should not run",
                        },
                    ),
                ),
                terminal=True,
            )

    case_id = _create_case(authenticated_client, "前置设备处理失败")
    runner = PrepareFailingRunner()
    with authenticated_client.app.state.session_factory() as db:
        repository = SQLiteTaskRepository(db)
        case = repository.get_case(case_id)
        assert case is not None
        task_id = repository.create_from_case(
            case,
            "前置设备处理失败",
            idempotency_key="device-prepare-failed",
            runner_type="mock",
            runner_config_snapshot={
                "pod_id": "pod_prepare",
                "device_prepare_action": "reset",
            },
        ).task.id

        completed = await TaskService(repository, runner=runner).run_task(
            task_id,
            worker_id="worker:test",
        )

        assert completed is not None
        assert completed.execution_status == ExecutionStatus.RESULT_READY
        assert completed.verdict == Verdict.FAIL
        assert completed.failure_type == "device_prepare_failed"
        assert completed.remote_run_id is None
        assert runner.started is False
        assert db.scalar(select(func.count()).select_from(PodLease)) == 0
        events = db.scalars(
            select(TaskEvent)
            .where(TaskEvent.task_id == task_id)
            .order_by(TaskEvent.sequence)
        ).all()
        assert [event.event_type for event in events] == [
            "device_prepare_started",
            "device_prepare_failed",
        ]
        assert events[0].payload == {
            "action": "reset",
            "pod_id": "pod_prepare",
            "product_id": None,
        }
        assert events[-1].payload == {
            "failure_type": "device_prepare_failed",
            "error_code": "reset_pod_failed",
            "request_id": "req-prepare-failed",
        }


def test_completed_task_does_not_write_case_stat_cache(
    authenticated_client,
    monkeypatch,
):
    async def start_passing_task(_runner, request, idempotency_key):
        assert idempotency_key
        return RunHandle(
            task_id=request.task_id,
            runner_type="mock",
            run_id=f"passing:{request.task_id}",
        )

    async def poll_passing_task(_runner, handle, after_sequence):
        assert after_sequence == 0
        return PollResult(
            events=(
                RunnerEvent(
                    sequence=1,
                    type="task_started",
                    payload={"task_id": handle.task_id},
                ),
                RunnerEvent(
                    sequence=2,
                    type="task_finished",
                    payload={"verdict": "pass", "evidence_complete": True},
                ),
            ),
            terminal=True,
        )

    monkeypatch.setattr(MockRunner, "start", start_passing_task)
    monkeypatch.setattr(MockRunner, "poll", poll_passing_task)
    configured = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mock"},
    )
    assert configured.status_code == 200
    case_id = _create_case(authenticated_client, "success")

    executed = authenticated_client.post(
        f"/api/v1/cases/{case_id}/execute",
        json={},
    )
    assert executed.status_code == 201
    authenticated_client.portal.call(
        authenticated_client.app.state.task_worker.wait_until_idle
    )

    task = authenticated_client.get(f"/api/v1/tasks/{executed.json()['id']}")
    assert task.status_code == 200
    task_body = task.json()
    assert task_body["execution_status"] == "result_ready", task_body
    assert task_body["verdict"] == "pass", {
        key: task_body[key]
        for key in ("execution_status", "verdict", "failure_type", "result_summary")
    }

    with authenticated_client.app.state.session_factory() as db:
        from mua_platform.cases.models import TestCase

        case = db.get(TestCase, case_id)
        assert case is not None
        assert case.execution_count == 0
        assert case.pass_count == 0
        assert case.fail_count == 0
        assert case.last_executed_at is None

    detail = authenticated_client.get(f"/api/v1/cases/{case_id}")
    assert detail.status_code == 200
    assert {
        key: detail.json()[key]
        for key in ("execution_count", "pass_count", "fail_count")
    } == {
        "execution_count": 1,
        "pass_count": 1,
        "fail_count": 0,
    }


def test_copy_case_creates_independent_reset_copy_for_current_user(
    authenticated_client,
):
    case_id = _create_case(authenticated_client, "登录核心链路")
    with authenticated_client.app.state.session_factory() as db:
        from mua_platform.cases.models import TestCase

        source = db.get(TestCase, case_id)
        assert source is not None
        source.execution_count = 4
        source.pass_count = 3
        source.fail_count = 1
        db.commit()

    response = authenticated_client.post(f"/api/v1/cases/{case_id}/copy")

    assert response.status_code == 201
    copied = response.json()
    assert copied["id"] != case_id
    assert copied["title"] == "登录核心链路 副本"
    assert copied["module"] == "登录"
    assert copied["content_markdown"] == "## 执行任务（必填）\n\n- 打开抖音APP"
    assert copied["tags"] == ["smoke"]
    assert copied["automation_level"] == "auto"
    assert copied["execution_count"] == 0
    assert copied["pass_count"] == 0
    assert copied["fail_count"] == 0
    assert copied["last_executed_at"] is None
    assert copied["created_by"] == "admin"

    original = authenticated_client.get(f"/api/v1/cases/{case_id}").json()
    assert original["title"] == "登录核心链路"
    assert original["execution_count"] == 0
    assert original["pass_count"] == 0
    assert original["fail_count"] == 0
    assert original["last_executed_at"] is None


def test_copy_unknown_case_returns_404(authenticated_client):
    response = authenticated_client.post("/api/v1/cases/case_missing/copy")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "case_not_found"


def test_delete_case_with_task_history_returns_conflict(authenticated_client):
    case_id = _create_case(authenticated_client, "保留执行历史")
    _seed_task(authenticated_client, case_id, "history-task")

    response = authenticated_client.delete(f"/api/v1/cases/{case_id}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "case_has_tasks"
    assert authenticated_client.get(f"/api/v1/cases/{case_id}").status_code == 200


def test_delete_case_with_completed_task_soft_deletes(authenticated_client):
    case_id = _create_case(authenticated_client, "已有完成记录可软删")
    task_id = _seed_task(
        authenticated_client,
        case_id,
        "soft-delete-completed",
        status=ExecutionStatus.RESULT_READY,
        verdict=Verdict.PASS,
    )

    response = authenticated_client.delete(f"/api/v1/cases/{case_id}")

    assert response.status_code == 204, response.text
    assert authenticated_client.get(f"/api/v1/cases/{case_id}").status_code == 404
    list_response = authenticated_client.get("/api/v1/cases")
    assert case_id not in [item["id"] for item in list_response.json()["items"]]
    with authenticated_client.app.state.session_factory() as db:
        case = db.get(CaseModel, case_id)
        assert case is not None
        assert case.deleted_at is not None
        assert db.get(Task, task_id) is not None


def test_delete_case_with_cancelled_task_soft_deletes(authenticated_client):
    case_id = _create_case(authenticated_client, "已取消记录可软删")
    _seed_task(
        authenticated_client,
        case_id,
        "soft-delete-cancelled",
        status=ExecutionStatus.CANCELLED,
    )

    response = authenticated_client.delete(f"/api/v1/cases/{case_id}")

    assert response.status_code == 204, response.text
    with authenticated_client.app.state.session_factory() as db:
        case = db.get(CaseModel, case_id)
        assert case is not None
        assert case.deleted_at is not None


def test_batch_delete_cases_returns_per_case_results(authenticated_client):
    removable_id = _create_case(authenticated_client, "可批量删除")
    with_task_id = _create_case(authenticated_client, "已有执行记录")
    bound_id = _create_case(authenticated_client, "已绑定计划")
    _seed_task(authenticated_client, with_task_id, "batch-delete-task")
    with authenticated_client.app.state.session_factory() as db:
        from mua_platform.test_plans.models import TestPlan, TestPlanCase

        plan = TestPlan(
            id="plan_batch_delete",
            name="批量删除保护计划",
            name_key="批量删除保护计划",
            test_type="regression",
            tags=[],
            created_by="admin",
        )
        db.add(plan)
        db.add(TestPlanCase(plan_id=plan.id, case_id=bound_id, position=0))
        db.commit()

    response = authenticated_client.post(
        "/api/v1/cases/batch-delete",
        json={
            "case_ids": [
                removable_id,
                with_task_id,
                bound_id,
                "case_missing",
            ],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["deleted_count"] == 1
    assert body["failed_count"] == 3
    by_id = {item["case_id"]: item for item in body["items"]}
    assert by_id[removable_id] == {
        "case_id": removable_id,
        "status": "deleted",
        "code": None,
        "message": None,
    }
    assert by_id[with_task_id]["status"] == "failed"
    assert by_id[with_task_id]["code"] == "case_has_tasks"
    assert by_id[bound_id]["status"] == "failed"
    assert by_id[bound_id]["code"] == "case_has_test_plans"
    assert by_id["case_missing"]["status"] == "failed"
    assert by_id["case_missing"]["code"] == "case_not_found"
    with authenticated_client.app.state.session_factory() as db:
        removable = db.get(CaseModel, removable_id)
        assert removable is not None
        assert removable.deleted_at is not None
        assert db.get(CaseModel, with_task_id) is not None
        assert db.get(CaseModel, bound_id) is not None


def test_create_from_case_reuses_same_idempotent_request(authenticated_client):
    case_id = _create_case(authenticated_client, "幂等执行用例")
    with authenticated_client.app.state.session_factory() as db:
        repository = SQLiteTaskRepository(db)
        case = repository.get_case(case_id)
        assert case is not None

        first = repository.create_from_case(
            case,
            case.title,
            idempotency_key="same-request",
            runner_type="mock",
        )
        second = repository.create_from_case(
            case,
            case.title,
            idempotency_key="same-request",
            runner_type="mock",
        )

        assert first.disposition == "created"
        assert second.disposition == "existing"
        assert second.task.id == first.task.id


def test_create_from_case_rejects_key_reused_for_different_request(
    authenticated_client,
):
    case_id = _create_case(authenticated_client, "幂等冲突用例")
    with authenticated_client.app.state.session_factory() as db:
        repository = SQLiteTaskRepository(db)
        case = repository.get_case(case_id)
        assert case is not None
        repository.create_from_case(
            case,
            "首次执行",
            idempotency_key="conflicting-request",
            runner_type="mock",
        )

        with pytest.raises(ValueError, match="idempotency_conflict"):
            repository.create_from_case(
                case,
                "不同执行",
                idempotency_key="conflicting-request",
                runner_type="mock",
            )


def test_cancel_queued_case_task_records_terminal_event(authenticated_client):
    case_id = _create_case(authenticated_client, "取消排队任务")
    task_id = _seed_task(authenticated_client, case_id, "cancel-queued")

    response = authenticated_client.post(f"/api/v1/tasks/{task_id}/cancel")

    assert response.status_code == 200
    assert response.json()["execution_status"] == "cancelled"
    assert response.json()["verdict"] is None
    with authenticated_client.app.state.session_factory() as db:
        events = list(
            db.scalars(
                select(TaskEvent)
                .where(TaskEvent.task_id == task_id)
                .order_by(TaskEvent.sequence)
            )
        )
        assert [(event.sequence, event.event_type) for event in events] == [
            (1, "task_cancelled")
        ]


@pytest.mark.asyncio
async def test_cancel_rejected_running_task_still_finishes_as_cancelled(
    authenticated_client,
):
    class RejectingCancelRunner:
        async def cancel(self, _handle):
            return CancelResult(accepted=False, terminal=False)

        async def poll(self, _handle, _after_sequence):
            return PollResult(events=(), terminal=False)

    case_id = _create_case(authenticated_client, "取消运行中任务")
    task_id = _seed_task(
        authenticated_client,
        case_id,
        "cancel-running-rejected",
        status=ExecutionStatus.RUNNING,
    )
    now = datetime(2026, 7, 30, 10, 0, tzinfo=UTC)
    with authenticated_client.app.state.session_factory() as db:
        task = db.get(Task, task_id)
        assert task is not None
        task.remote_run_id = "run-cancel-rejected"
        db.commit()
        repository = SQLiteTaskRepository(db)
        service = TaskService(
            repository,
            RejectingCancelRunner(),
            clock=FakeClock(now),
        )

        await service.cancel(task_id)
        cancelled = await service.execute_or_resume(task_id)

        assert cancelled.execution_status == ExecutionStatus.CANCELLED
        assert cancelled.verdict is None
        assert cancelled.failure_type is None
        events = list(
            db.scalars(
                select(TaskEvent)
                .where(TaskEvent.task_id == task_id)
                .order_by(TaskEvent.sequence)
            )
        )
        assert events[-1].event_type == "task_cancelled"


def test_execute_case_persists_custom_agent_runtime_options(
    authenticated_client,
    monkeypatch,
):
    authenticated_client.app.state.pod_gateway = DetailGateway()
    configured = authenticated_client.put(
        "/api/v1/settings/runner",
        json={
            "mode": "mobile_use",
            "mobile_use": {
                "access_key_id": "AKLT00000000WXYZ",
                "secret_access_key": "secret-value",
                "product_id": "prod_123",
                "tos_bucket": "mua-test",
                "tos_region": "cn-beijing",
            },
        },
    )
    assert configured.status_code == 200
    with authenticated_client.app.state.session_factory() as db:
        PodRepository(db).sync(
            "prod_123",
            ListPodPage(
                items=(
                    PodSummary(
                        product_id="prod_123",
                        pod_id="pod_custom",
                        pod_name="自定义云机",
                        pod_status_code=1,
                        stream_status=None,
                        image_id=None,
                        image_name=None,
                        aosp_version=None,
                        display_layout_id=None,
                        dc_id=None,
                        dc_name=None,
                        isp_code=None,
                        region=None,
                        zone_id=None,
                        config_code=None,
                        config_name=None,
                        config_type=None,
                        server_type_code=None,
                        intranet_ip=None,
                        adb_address=None,
                        adb_status=None,
                        data_size=None,
                        data_size_used=None,
                        pod_created_at=None,
                    ),
                ),
                next_token=None,
                request_id="req-custom-pool",
            ),
        )
    monkeypatch.setattr(
        authenticated_client.app.state.task_worker,
        "enqueue",
        _ignore_enqueue,
    )
    case_id = _create_case(authenticated_client, "自定义执行配置用例")

    response = authenticated_client.post(
        f"/api/v1/cases/{case_id}/execute",
        json={
            "idempotency_key": "custom-agent-options",
            "pod_id": "pod_custom",
            "agent_config_mode": "custom",
            "agent_options": {
                "use_base64_screenshot": False,
                "max_step": 123,
                "timeout_seconds": 456,
                "callback_info": {
                    "url": "https://callback.example.com",
                    "authorization": "Bearer callback-secret",
                },
                "output_schema": '{"type":"object"}',
                "retry_limit": 7,
                "system_prompt": "custom system prompt",
                "tos_bucket": "custom-bucket",
                "tos_endpoint": "tos-s3-cn-beijing.volces.com",
                "tos_region": "cn-beijing",
                "screen_record": True,
                "mcp_json": (
                    '{"mcpServers":{"amap":{"url":"https://mcp.example.com",'
                    '"headers":{"Authorization":"Bearer mcp-secret"}}}}'
                ),
                "max_output_tokens": 2048,
                "gps_info": "116.397128,39.916527,50,0,0,10",
                "device_prepare_action": "reboot",
            },
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created_by"] == "admin"
    runtime = authenticated_client.get(f"/api/v1/tasks/{body['id']}/runtime")
    assert runtime.status_code == 200
    execution_config = runtime.json()["execution_config"]
    assert execution_config["source"] == "custom"
    assert execution_config["device_prepare_action"] == "reboot"
    assert execution_config["timeout_seconds"] == 456
    assert execution_config["callback_info"] == {
        "url": "https://callback.example.com",
        "authorization": "***",
    }
    assert "mcp-secret" not in execution_config["mcp_json"]
    assert "***" in execution_config["mcp_json"]
    with authenticated_client.app.state.session_factory() as db:
        task = db.get(Task, body["id"])
        assert task is not None
        assert task.runner_config_snapshot["config_source"] == "custom"
        assert task.runner_config_snapshot["device_prepare_action"] == "reboot"
        assert task.runner_config_snapshot["pod_id"] == "pod_custom"
        assert task.runner_config_snapshot["use_base64_screenshot"] is False
        assert task.runner_config_snapshot["max_step"] == 123
        assert task.runner_config_snapshot["timeout_seconds"] == 456
        assert task.runner_config_snapshot["callback_info"] == {
            "url": "https://callback.example.com",
            "authorization": "Bearer callback-secret",
        }
        assert task.runner_config_snapshot["output_schema"] == '{"type":"object"}'
        assert task.runner_config_snapshot["retry_limit"] == 7
        assert task.runner_config_snapshot["system_prompt"] == "custom system prompt"
        assert task.runner_config_snapshot["tos_bucket"] == "custom-bucket"
        assert task.runner_config_snapshot["tos_endpoint"] == "tos-s3-cn-beijing.volces.com"
        assert task.runner_config_snapshot["tos_region"] == "cn-beijing"
        assert task.runner_config_snapshot["screen_record"] is True
        assert "mcp-secret" in task.runner_config_snapshot["mcp_json"]
        assert task.runner_config_snapshot["max_output_tokens"] == 2048
        assert task.runner_config_snapshot["gps_info"] == "116.397128,39.916527,50,0,0,10"


def test_execute_case_uses_case_default_agent_options(
    authenticated_client,
    monkeypatch,
):
    response = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mock"},
    )
    assert response.status_code == 200, response.text
    monkeypatch.setattr(
        authenticated_client.app.state.task_worker,
        "enqueue",
        _ignore_enqueue,
    )
    case_id = _create_case(
        authenticated_client,
        "默认执行配置用例",
        default_agent_options={
            "thread_id": "thread-from-case",
            "timeout_seconds": 456,
            "max_step": 123,
            "tos_bucket": "case-bucket",
            "tos_region": "cn-beijing",
            "screen_record": True,
        },
    )

    execute = authenticated_client.post(
        f"/api/v1/cases/{case_id}/execute",
        json={
            "idempotency_key": "case-default-options",
            "pod_id": "pod_default",
            "agent_config_mode": "case_default",
        },
    )

    assert execute.status_code == 201, execute.text
    body = execute.json()
    runtime = authenticated_client.get(f"/api/v1/tasks/{body['id']}/runtime")
    assert runtime.status_code == 200
    public_config = runtime.json()["execution_config"]
    assert public_config["source"] == "case_default"
    assert public_config["thread_id"] == "thread-from-case"
    assert public_config["timeout_seconds"] == 456
    with authenticated_client.app.state.session_factory() as db:
        task = db.get(Task, body["id"])
        assert task is not None
        assert task.runner_config_snapshot["config_source"] == "case_default"
        assert task.runner_config_snapshot["thread_id"] == "thread-from-case"
        assert task.runner_config_snapshot["max_step"] == 123
        assert task.runner_config_snapshot["tos_bucket"] == "case-bucket"
        assert task.runner_config_snapshot["screen_record"] is True


@pytest.mark.asyncio
async def test_case_default_device_prepare_flows_to_remote_before_agent_start(
    authenticated_client,
    monkeypatch,
):
    class PreparePodGateway:
        async def list_all(self, _config):
            return ListPodPage(
                items=(
                    PodSummary(
                        product_id="prod_prepare",
                        pod_id="host_prepare_1",
                        pod_name="前置处理云机",
                        pod_status_code=1,
                        stream_status=None,
                        image_id=None,
                        image_name=None,
                        aosp_version=None,
                        display_layout_id=None,
                        dc_id=None,
                        dc_name=None,
                        isp_code=None,
                        region=None,
                        zone_id=None,
                        config_code=None,
                        config_name=None,
                        config_type=None,
                        server_type_code=None,
                        intranet_ip=None,
                        adb_address=None,
                        adb_status=None,
                        data_size=None,
                        data_size_used=None,
                        pod_created_at=None,
                    ),
                ),
                next_token=None,
                request_id="req-prepare-pool",
            )

        async def detail(self, _config, pod_id: str):
            return PodDetail(
                product_id="prod_prepare",
                pod_id=pod_id,
                pod_name="前置处理云机",
                pod_status_code=1,
                stream_status=None,
                image_id=None,
                image_name=None,
                aosp_version=None,
                display_layout_id=None,
                dc_id=None,
                dc_name=None,
                isp_code=None,
                region=None,
                zone_id=None,
                config_code=None,
                config_name=None,
                config_type=None,
                server_type_code=None,
                intranet_ip=None,
                adb_address=None,
                adb_status=None,
                data_size=None,
                data_size_used=None,
                pod_created_at=None,
                request_id="req-prepare-detail",
            )

    configured = authenticated_client.put(
        "/api/v1/settings/runner",
        json={
            "mode": "mobile_use",
            "mobile_use": {
                "access_key_id": "AKLT00000000WXYZ",
                "secret_access_key": "secret-value",
                "product_id": "prod_prepare",
                "tos_bucket": "mua-test",
                "tos_region": "cn-beijing",
            },
        },
    )
    assert configured.status_code == 200, configured.text
    authenticated_client.app.state.pod_gateway = PreparePodGateway()
    with authenticated_client.app.state.session_factory() as db:
        PodRepository(db).sync(
            "prod_prepare",
            ListPodPage(
                items=(
                    PodSummary(
                        product_id="prod_prepare",
                        pod_id="host_prepare_1",
                        pod_name="前置处理云机",
                        pod_status_code=1,
                        stream_status=None,
                        image_id=None,
                        image_name=None,
                        aosp_version=None,
                        display_layout_id=None,
                        dc_id=None,
                        dc_name=None,
                        isp_code=None,
                        region=None,
                        zone_id=None,
                        config_code=None,
                        config_name=None,
                        config_type=None,
                        server_type_code=None,
                        intranet_ip=None,
                        adb_address=None,
                        adb_status=None,
                        data_size=None,
                        data_size_used=None,
                        pod_created_at=None,
                    ),
                ),
                next_token=None,
                request_id="req-prepare-pool",
            ),
        )
    monkeypatch.setattr(
        authenticated_client.app.state.task_worker,
        "enqueue",
        _ignore_enqueue,
    )
    case_id = _create_case(
        authenticated_client,
        "前置处理链路用例",
        default_agent_options={
            "device_prepare_action": "reset",
            "timeout_seconds": 321,
            "tos_bucket": "mua-test",
            "tos_region": "cn-beijing",
        },
    )

    created = authenticated_client.post(
        f"/api/v1/cases/{case_id}/execute",
        json={
            "idempotency_key": "case-default-device-prepare",
            "pod_id": "host_prepare_1",
            "agent_config_mode": "case_default",
        },
    )

    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    calls: list[UniversalRequest] = []
    detail_statuses = [1, 2, 0, 1]

    def invoke(_config, request: UniversalRequest):
        calls.append(request)
        if request.action == "DetailPod":
            online = detail_statuses.pop(0)
            return {
                "ResponseMetadata": {"RequestId": f"req-detail-{online}"},
                "Result": {
                    "ProductId": "prod_prepare",
                    "PodId": "host_prepare_1",
                    "PodName": "前置处理云机",
                    "Online": online,
                },
            }
        if request.action == "PowerOffPod":
            return {
                "ResponseMetadata": {"RequestId": "req-power-off"},
                "Result": {
                    "Details": [
                        {
                            "PodId": "host_prepare_1",
                            "Success": True,
                            "ErrMsg": "",
                        }
                    ]
                },
            }
        if request.action == "ResetPod":
            return {
                "TaskId": "prepare-task-1",
                "TaskAction": "ResetPod",
                "Jobs": [
                    {
                        "PodId": "host_prepare_1",
                        "JobId": "job-reset-pod",
                        "Status": 10,
                    }
                ],
            }
        if request.action == "GetTaskInfo":
            return {
                "TaskId": request.body["TaskId"],
                "TaskAction": "ResetPod",
                "TaskResult": 100,
                "TaskMessage": "reset done",
                "Jobs": [
                    {
                        "PodId": "host_prepare_1",
                        "JobId": "job-reset-pod",
                        "Status": 100,
                    }
                ],
            }
        if request.action == "PowerOnPod":
            return {
                "Details": [
                    {
                        "PodId": "host_prepare_1",
                        "Success": True,
                        "ErrMsg": "",
                    }
                ],
            }
        if request.action == "RunAgentTaskOneStep":
            return {
                "ResponseMetadata": {"RequestId": "req-run-agent"},
                "Result": {"RunId": "run-prepare", "ThreadId": "thread-prepare"},
            }
        if request.action == "ListAgentRunTaskByThread":
            return {
                "ResponseMetadata": {"RequestId": "req-task-status"},
                "Result": {
                    "ThreadGroups": [
                        {
                            "ThreadId": "thread-prepare",
                            "Tasks": [{"RunId": "run-prepare", "Status": 3}],
                        }
                    ]
                },
            }
        if request.action == "GetAgentResult":
            return {
                "ResponseMetadata": {"RequestId": "req-agent-result"},
                "Result": {
                    "IsSuccess": 1,
                    "Content": "prepared and passed",
                    "StructOutput": {
                        "status": "pass",
                        "reason": "",
                        "assertions": [
                            {
                                "index": 1,
                                "result": "pass",
                                "evidence": ["prepared"],
                            }
                        ],
                        "evidence": ["prepared"],
                    },
                },
            }
        raise AssertionError(f"unexpected action: {request.action}")

    with authenticated_client.app.state.session_factory() as db:
        repository = SQLiteTaskRepository(db)
        task = repository.get(task_id)
        assert task is not None
        config = SettingsService(
            SettingRepository(
                db,
                authenticated_client.app.state.setting_cipher,
                authenticated_client.app.state.settings.runner_setting_defaults(),
            )
        ).get_runner_config(task.business_id).with_execution_snapshot(
            task.runner_config_snapshot
        )

        def load_request(_task_id: str):
            return RunRequest(
                task_id=task.id,
                scenario=task.scenario,
                title="前置处理链路用例",
                content_markdown=task.prompt_snapshot or "",
            )

        completed = await TaskService(
            repository,
            MobileUseRunner(
                config,
                UniversalGateway(call=invoke),
                request_loader=load_request,
                poll_interval=0,
            ),
        ).run_task(task_id, worker_id="worker:test")

        assert completed is not None
        assert completed.execution_status == ExecutionStatus.RESULT_READY
        assert completed.verdict == Verdict.PASS
        assert completed.failure_type is None
        assert completed.remote_run_id == "run-prepare"

    assert [request.action for request in calls] == [
        "DetailPod",
        "PowerOffPod",
        "DetailPod",
        "ResetPod",
        "GetTaskInfo",
        "PowerOnPod",
        "DetailPod",
        "DetailPod",
        "RunAgentTaskOneStep",
        "ListAgentRunTaskByThread",
        "GetAgentResult",
    ]
    assert calls[3].body == {
        "ProductId": "prod_prepare",
        "PodIdList": ["host_prepare_1"],
    }
    assert calls[4].body == {
        "ProductId": "prod_prepare",
        "TaskId": "prepare-task-1",
    }
    assert calls[5].body == {
        "ProductId": "prod_prepare",
        "PodId": "host_prepare_1",
    }
    assert calls[8].body["PodId"] == "host_prepare_1"
    assert calls[8].body["ProductId"] == "prod_prepare"
    assert calls[8].body["Timeout"] == 321
    with authenticated_client.app.state.session_factory() as db:
        events = db.scalars(
            select(TaskEvent)
            .where(TaskEvent.task_id == task_id)
            .order_by(TaskEvent.sequence)
        ).all()
        assert [event.event_type for event in events[:3]] == [
            "device_prepare_started",
            "device_prepare_succeeded",
            "task_started",
        ]
        assert events[0].payload == {
            "action": "reset",
            "pod_id": "host_prepare_1",
            "product_id": "prod_prepare",
        }
        assert events[1].payload == {
            "action": "reset",
            "remote_task_id": "prepare-task-1",
        }


@pytest.mark.asyncio
async def test_case_default_reboot_prepare_waits_until_pod_running_before_agent_start(
    authenticated_client,
    monkeypatch,
):
    class RebootPreparePodGateway:
        async def list_all(self, _config):
            return ListPodPage(
                items=(
                    PodSummary(
                        product_id="prod_prepare",
                        pod_id="host_prepare_reboot",
                        pod_name="重启前置云机",
                        pod_status_code=1,
                        stream_status=None,
                        image_id=None,
                        image_name=None,
                        aosp_version=None,
                        display_layout_id=None,
                        dc_id=None,
                        dc_name=None,
                        isp_code=None,
                        region=None,
                        zone_id=None,
                        config_code=None,
                        config_name=None,
                        config_type=None,
                        server_type_code=None,
                        intranet_ip=None,
                        adb_address=None,
                        adb_status=None,
                        data_size=None,
                        data_size_used=None,
                        pod_created_at=None,
                    ),
                ),
                next_token=None,
                request_id="req-prepare-pool",
            )

        async def detail(self, _config, pod_id: str):
            return PodDetail(
                product_id="prod_prepare",
                pod_id=pod_id,
                pod_name="重启前置云机",
                pod_status_code=1,
                stream_status=None,
                image_id=None,
                image_name=None,
                aosp_version=None,
                display_layout_id=None,
                dc_id=None,
                dc_name=None,
                isp_code=None,
                region=None,
                zone_id=None,
                config_code=None,
                config_name=None,
                config_type=None,
                server_type_code=None,
                intranet_ip=None,
                adb_address=None,
                adb_status=None,
                data_size=None,
                data_size_used=None,
                pod_created_at=None,
                request_id="req-prepare-detail",
            )

    configured = authenticated_client.put(
        "/api/v1/settings/runner",
        json={
            "mode": "mobile_use",
            "mobile_use": {
                "access_key_id": "AKLT00000000WXYZ",
                "secret_access_key": "secret-value",
                "product_id": "prod_prepare",
                "tos_bucket": "mua-test",
                "tos_region": "cn-beijing",
            },
        },
    )
    assert configured.status_code == 200, configured.text
    authenticated_client.app.state.pod_gateway = RebootPreparePodGateway()
    with authenticated_client.app.state.session_factory() as db:
        PodRepository(db).sync(
            "prod_prepare",
            ListPodPage(
                items=(
                    PodSummary(
                        product_id="prod_prepare",
                        pod_id="host_prepare_reboot",
                        pod_name="重启前置云机",
                        pod_status_code=1,
                        stream_status=None,
                        image_id=None,
                        image_name=None,
                        aosp_version=None,
                        display_layout_id=None,
                        dc_id=None,
                        dc_name=None,
                        isp_code=None,
                        region=None,
                        zone_id=None,
                        config_code=None,
                        config_name=None,
                        config_type=None,
                        server_type_code=None,
                        intranet_ip=None,
                        adb_address=None,
                        adb_status=None,
                        data_size=None,
                        data_size_used=None,
                        pod_created_at=None,
                    ),
                ),
                next_token=None,
                request_id="req-prepare-pool",
            ),
        )
    monkeypatch.setattr(
        authenticated_client.app.state.task_worker,
        "enqueue",
        _ignore_enqueue,
    )
    case_id = _create_case(
        authenticated_client,
        "重启前置处理链路用例",
        default_agent_options={
            "device_prepare_action": "reboot",
            "timeout_seconds": 321,
            "tos_bucket": "mua-test",
            "tos_region": "cn-beijing",
        },
    )
    created = authenticated_client.post(
        f"/api/v1/cases/{case_id}/execute",
        json={
            "idempotency_key": "case-default-reboot-prepare",
            "pod_id": "host_prepare_reboot",
            "agent_config_mode": "case_default",
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    calls: list[UniversalRequest] = []
    detail_statuses = [1, 4, 1]

    def invoke(_config, request: UniversalRequest):
        calls.append(request)
        if request.action == "DetailPod":
            online = detail_statuses.pop(0)
            return {
                "ResponseMetadata": {"RequestId": f"req-detail-{online}"},
                "Result": {
                    "ProductId": "prod_prepare",
                    "PodId": "host_prepare_reboot",
                    "PodName": "重启前置云机",
                    "Online": online,
                },
            }
        if request.action == "RebootPod":
            return None
        if request.action == "RunAgentTaskOneStep":
            return {
                "ResponseMetadata": {"RequestId": "req-run-agent"},
                "Result": {"RunId": "run-reboot-prepare", "ThreadId": "thread-prepare"},
            }
        if request.action == "ListAgentRunTaskByThread":
            return {
                "ResponseMetadata": {"RequestId": "req-task-status"},
                "Result": {
                    "ThreadGroups": [
                        {
                            "ThreadId": "thread-prepare",
                            "Tasks": [{"RunId": "run-reboot-prepare", "Status": 3}],
                        }
                    ]
                },
            }
        if request.action == "GetAgentResult":
            return {
                "ResponseMetadata": {"RequestId": "req-agent-result"},
                "Result": {
                    "IsSuccess": 1,
                    "Content": "reboot prepared and passed",
                    "StructOutput": {
                        "status": "pass",
                        "reason": "",
                        "assertions": [
                            {
                                "index": 1,
                                "result": "pass",
                                "evidence": ["reboot prepared"],
                            }
                        ],
                        "evidence": ["reboot prepared"],
                    },
                },
            }
        raise AssertionError(f"unexpected action: {request.action}")

    with authenticated_client.app.state.session_factory() as db:
        repository = SQLiteTaskRepository(db)
        task = repository.get(task_id)
        assert task is not None
        config = SettingsService(
            SettingRepository(
                db,
                authenticated_client.app.state.setting_cipher,
                authenticated_client.app.state.settings.runner_setting_defaults(),
            )
        ).get_runner_config(task.business_id).with_execution_snapshot(
            task.runner_config_snapshot
        )

        completed = await TaskService(
            repository,
            MobileUseRunner(
                config,
                UniversalGateway(call=invoke),
                request_loader=lambda _task_id: RunRequest(
                    task_id=task.id,
                    scenario=task.scenario,
                    title="重启前置处理链路用例",
                    content_markdown=task.prompt_snapshot or "",
                ),
                poll_interval=0,
            ),
        ).run_task(task_id, worker_id="worker:test")

        assert completed is not None
        assert completed.execution_status == ExecutionStatus.RESULT_READY
        assert completed.verdict == Verdict.PASS
        assert completed.failure_type is None
        assert completed.remote_run_id == "run-reboot-prepare"

    assert [request.action for request in calls] == [
        "DetailPod",
        "RebootPod",
        "DetailPod",
        "DetailPod",
        "RunAgentTaskOneStep",
        "ListAgentRunTaskByThread",
        "GetAgentResult",
    ]


async def _ignore_enqueue(_task_id: str) -> None:
    return None


class DetailGateway:
    async def list_all(self, _config):
        return ListPodPage(items=(), next_token=None, request_id="req-list")

    async def detail(self, _config, pod_id: str):
        return PodDetail(
            product_id="prod_123",
            pod_id=pod_id,
            pod_name="自定义云机",
            pod_status_code=1,
            stream_status=None,
            image_id=None,
            image_name=None,
            aosp_version=None,
            display_layout_id=None,
            dc_id=None,
            dc_name=None,
            isp_code=None,
            region=None,
            zone_id=None,
            config_code=None,
            config_name=None,
            config_type=None,
            server_type_code=None,
            intranet_ip=None,
            adb_address=None,
            adb_status=None,
            data_size=None,
            data_size_used=None,
            pod_created_at=None,
            request_id="req-detail",
        )
