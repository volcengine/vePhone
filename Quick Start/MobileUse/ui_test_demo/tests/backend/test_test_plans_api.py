from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import event, select

from mua_platform.cases.models import TestCase as CaseModel
from mua_platform.db import _TAG_COLOR_CANDIDATES
from mua_platform.tasks.models import Task, TaskBatch
from mua_platform.tasks.state_machine import ExecutionStatus, Verdict
from mua_platform.test_plans import models as plan_models
from mua_platform.test_plans.models import (
    PlanExecution,
    TagColorRegistry,
)
from mua_platform.test_plans.schemas import TestPlanWrite as PlanWrite


@pytest.fixture()
def authenticated_client(client, initialized_admin):
    return client


def _create_case(client, title: str, *, tags: list[str] | None = None) -> str:
    response = client.post(
        "/api/v1/cases",
        json={
            "title": title,
            "module": "登录",
            "content_markdown": "## 执行任务（必填）\n\n- 打开抖音APP",
            "tags": tags or ["smoke"],
            "automation_level": "auto",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_plan_response(
    client,
    name: str,
    *,
    case_ids: list[str] | None = None,
    tags: list[str] | None = None,
    test_type: str = "regression",
):
    resolved_case_ids = case_ids or [_create_case(client, f"{name} 用例")]
    return client.post(
        "/api/v1/test-plans",
        json={
            "name": name,
            "description": "每日回归",
            "test_type": test_type,
            "tags": tags or ["核心链路"],
            "case_ids": resolved_case_ids,
        },
    )


def _create_plan(
    client,
    name: str,
    *,
    case_ids: list[str] | None = None,
    tags: list[str] | None = None,
    test_type: str = "regression",
) -> dict:
    response = _create_plan_response(
        client,
        name,
        case_ids=case_ids,
        tags=tags,
        test_type=test_type,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _seed_execution(
    client,
    plan: dict,
    verdicts: list[Verdict],
    *,
    created_at: datetime,
) -> str:
    execution_id = f"execution_{uuid4().hex}"
    batch_id = f"batch_{uuid4().hex}"
    batch_verdict = (
        Verdict.PASS
        if all(verdict == Verdict.PASS for verdict in verdicts)
        else Verdict.FAIL
    )
    with client.app.state.session_factory() as db:
        batch = TaskBatch(
            id=batch_id,
            name=plan["name"],
            test_type="regression",
            selection_mode="test_plan",
            selection_snapshot={"case_ids": list(plan["case_ids"])},
            device_strategy="automatic",
            pod_ids=[],
            concurrency=1,
            device_wait_timeout_seconds=300,
            runner_type="mock",
            config_snapshot={},
            execution_status=ExecutionStatus.RESULT_READY,
            verdict=batch_verdict,
            idempotency_key=f"batch-{uuid4().hex}",
            request_fingerprint="{}",
            created_by="admin",
            created_at=created_at,
            started_at=created_at,
            finished_at=created_at + timedelta(minutes=1),
        )
        for position, (case_id, verdict) in enumerate(
            zip(plan["case_ids"], verdicts, strict=True)
        ):
            batch.tasks.append(
                Task(
                    id=f"task_{uuid4().hex}",
                    case_id=case_id,
                    batch_position=position,
                    prompt_snapshot="run",
                    runner_type="mock",
                    scenario="plan",
                    created_by="admin",
                    execution_status=ExecutionStatus.RESULT_READY,
                    verdict=verdict,
                    idempotency_key=f"task-{uuid4().hex}",
                    request_fingerprint="{}",
                    version=1,
                    created_at=created_at,
                    started_at=created_at,
                    finished_at=created_at + timedelta(minutes=1),
                )
            )
        db.add(batch)
        db.add(
            PlanExecution(
                id=execution_id,
                test_plan_id=plan["id"],
                task_batch_id=batch_id,
                plan_name_snapshot=plan["name"],
                plan_tags_snapshot=[
                    tag["name"] for tag in plan["tags"]
                ],
                case_ids_snapshot=list(plan["case_ids"]),
                device_strategy_snapshot="automatic",
                pod_ids_snapshot=[],
                concurrency_snapshot=1,
                runner_type_snapshot="mock",
                config_snapshot={},
                created_by="admin",
                created_at=created_at,
            )
        )
        db.commit()
    return execution_id


def _get_with_statement_count(client, url: str, *, params=None):
    statements: list[str] = []

    def capture_statement(
        _connection,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ):
        statements.append(statement)

    event.listen(
        client.app.state.engine,
        "before_cursor_execute",
        capture_statement,
    )
    try:
        response = client.get(url, params=params)
    finally:
        event.remove(
            client.app.state.engine,
            "before_cursor_execute",
            capture_statement,
        )
    return response, statements


def test_create_and_update_plan_preserves_case_order(authenticated_client):
    case_ids = [
        _create_case(authenticated_client, f"用例 {index}")
        for index in range(3)
    ]
    created = authenticated_client.post(
        "/api/v1/test-plans",
        json={
            "name": " 核心回归 ",
            "description": "每日回归",
            "tags": ["核心链路", "P0", "核心链路"],
            "case_ids": [case_ids[2], case_ids[0], case_ids[1]],
        },
    )

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "核心回归"
    assert body["test_type"] == "regression"
    assert body["case_ids"] == [case_ids[2], case_ids[0], case_ids[1]]
    assert body["case_count"] == 3
    assert [tag["name"] for tag in body["tags"]] == ["核心链路", "P0"]
    assert all(tag["foreground_color"].startswith("#") for tag in body["tags"])
    assert all(tag["background_color"].endswith("1A") for tag in body["tags"])

    updated = authenticated_client.put(
        f"/api/v1/test-plans/{body['id']}",
        json={
            "name": "核心回归",
            "description": "更新",
            "test_type": "new_feature",
            "tags": ["P0"],
            "case_ids": [case_ids[1], case_ids[2]],
        },
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["test_type"] == "new_feature"
    assert updated.json()["case_ids"] == [case_ids[1], case_ids[2]]
    assert updated.json()["description"] == "更新"
    detail = authenticated_client.get(f"/api/v1/test-plans/{body['id']}")
    assert detail.status_code == 200
    assert detail.json() == updated.json()


def test_plan_list_uses_backend_pagination_and_name_prefix(
    authenticated_client,
):
    case_id = _create_case(authenticated_client, "分页公共用例")
    for index in range(12):
        _create_plan(
            authenticated_client,
            f"回归-{index:02d}",
            case_ids=[case_id],
        )
    _create_plan(authenticated_client, "冒烟-00", case_ids=[case_id])

    response = authenticated_client.get(
        "/api/v1/test-plans",
        params={"page": 2, "page_size": 10, "search": "回归-"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 12
    assert len(response.json()["items"]) == 2
    assert response.json()["page"] == 2
    assert response.json()["page_size"] == 10


def test_plan_list_filters_by_plan_tag(authenticated_client):
    case_id = _create_case(authenticated_client, "标签筛选公共用例")
    matched = _create_plan(
        authenticated_client,
        "P0 回归计划",
        case_ids=[case_id],
        tags=["P0", "核心链路"],
    )
    _create_plan(
        authenticated_client,
        "冒烟计划",
        case_ids=[case_id],
        tags=["smoke"],
    )

    response = authenticated_client.get(
        "/api/v1/test-plans",
        params={"tag": "P0"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["id"] for item in response.json()["items"]] == [
        matched["id"]
    ]


def test_plan_tag_options_are_based_on_active_test_plans(
    authenticated_client,
):
    case_id = _create_case(
        authenticated_client,
        "计划标签选项公共用例",
        tags=["case-only"],
    )
    _create_plan(
        authenticated_client,
        "计划标签 A",
        case_ids=[case_id],
        tags=["计划标签", "P0"],
    )
    deleted = _create_plan(
        authenticated_client,
        "已删除计划标签",
        case_ids=[case_id],
        tags=["已删除标签"],
    )
    delete_response = authenticated_client.delete(
        f"/api/v1/test-plans/{deleted['id']}",
    )
    assert delete_response.status_code == 204

    response = authenticated_client.get("/api/v1/test-plans/tags")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()["items"]]
    assert names == ["P0", "计划标签"]
    assert "case-only" not in names
    assert "已删除标签" not in names


def test_plan_list_filters_by_test_type(authenticated_client):
    case_id = _create_case(authenticated_client, "测试类型筛选公共用例")
    matched = _create_plan(
        authenticated_client,
        "新功能计划",
        case_ids=[case_id],
        test_type="new_feature",
    )
    _create_plan(
        authenticated_client,
        "回归计划",
        case_ids=[case_id],
        test_type="regression",
    )

    response = authenticated_client.get(
        "/api/v1/test-plans",
        params={"test_type": "new_feature"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == matched["id"]
    assert response.json()["items"][0]["test_type"] == "new_feature"


def test_plan_list_filters_and_lists_creators(authenticated_client):
    case_id = _create_case(authenticated_client, "创建人筛选公共用例")
    admin_plan = _create_plan(
        authenticated_client,
        "管理员计划",
        case_ids=[case_id],
    )
    alice_plan = _create_plan(
        authenticated_client,
        "Alice 计划",
        case_ids=[case_id],
    )
    deleted_plan = _create_plan(
        authenticated_client,
        "已删除计划",
        case_ids=[case_id],
    )
    with authenticated_client.app.state.session_factory() as db:
        from mua_platform.test_plans.models import TestPlan

        alice = db.get(TestPlan, alice_plan["id"])
        deleted = db.get(TestPlan, deleted_plan["id"])
        assert alice is not None
        assert deleted is not None
        alice.created_by = "alice"
        deleted.created_by = "deleted-user"
        deleted.deleted_at = datetime.now(UTC)
        db.commit()

    filtered = authenticated_client.get(
        "/api/v1/test-plans",
        params={"created_by": "alice"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["id"] == alice_plan["id"]
    assert filtered.json()["items"][0]["created_by"] == "alice"

    creators = authenticated_client.get("/api/v1/test-plans/creators")
    assert creators.status_code == 200
    assert creators.json() == {"items": ["admin", "alice"]}
    assert admin_plan["created_by"] == "admin"


def test_plan_list_treats_blank_test_type_as_regression(authenticated_client):
    case_id = _create_case(authenticated_client, "旧测试类型公共用例")
    matched = _create_plan(
        authenticated_client,
        "旧回归计划",
        case_ids=[case_id],
        test_type="regression",
    )
    with authenticated_client.app.state.session_factory() as db:
        from mua_platform.test_plans.models import TestPlan

        plan = db.get(TestPlan, matched["id"])
        assert plan is not None
        plan.test_type = ""
        db.commit()

    response = authenticated_client.get(
        "/api/v1/test-plans",
        params={"test_type": "regression"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == matched["id"]
    assert response.json()["items"][0]["test_type"] == "regression"


def test_plan_list_query_count_does_not_grow_with_page_size(
    authenticated_client,
):
    plans = [
        _create_plan(authenticated_client, f"批量聚合计划 {index}")
        for index in range(4)
    ]
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    _seed_execution(
        authenticated_client,
        plans[0],
        [Verdict.PASS],
        created_at=created_at,
    )
    _seed_execution(
        authenticated_client,
        plans[1],
        [Verdict.FAIL],
        created_at=created_at + timedelta(minutes=1),
    )
    exceptional_execution_id = _seed_execution(
        authenticated_client,
        plans[2],
        [Verdict.FAIL],
        created_at=created_at + timedelta(minutes=2),
    )
    with authenticated_client.app.state.session_factory() as db:
        exceptional_execution = db.get(
            PlanExecution,
            exceptional_execution_id,
        )
        assert exceptional_execution is not None
        failed_task = db.scalar(
            select(Task).where(
                Task.batch_id == exceptional_execution.task_batch_id
            )
        )
        assert failed_task is not None
        failed_task.failure_type = "runner_interrupted"
        db.commit()

    single, single_statements = _get_with_statement_count(
        authenticated_client,
        "/api/v1/test-plans",
        params={"page": 1, "page_size": 1},
    )
    multiple, multiple_statements = _get_with_statement_count(
        authenticated_client,
        "/api/v1/test-plans",
        params={"page": 1, "page_size": 4},
    )

    assert single.status_code == 200
    assert multiple.status_code == 200
    assert len(multiple.json()["items"]) == 4
    by_id = {item["id"]: item for item in multiple.json()["items"]}
    assert by_id[plans[0]["id"]]["execution_count"] == 1
    assert by_id[plans[0]["id"]]["latest_execution"]["pass_rate"] == 100.0
    assert by_id[plans[0]["id"]]["latest_execution"]["report_status"] == "success"
    assert by_id[plans[1]["id"]]["latest_execution"]["report_status"] == "failure"
    assert by_id[plans[2]["id"]]["latest_execution"]["report_status"] == "exception"
    assert by_id[plans[3]["id"]]["latest_execution"] is None
    assert len(multiple_statements) == len(single_statements)


def test_plan_list_treats_assertion_failure_as_failure(
    authenticated_client,
):
    plan = _create_plan(authenticated_client, "断言失败计划")
    execution_id = _seed_execution(
        authenticated_client,
        plan,
        [Verdict.FAIL],
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    with authenticated_client.app.state.session_factory() as db:
        execution = db.get(PlanExecution, execution_id)
        assert execution is not None
        failed_task = db.scalar(
            select(Task).where(
                Task.batch_id == execution.task_batch_id
            )
        )
        assert failed_task is not None
        failed_task.failure_type = "assertion_failed"
        db.commit()

    response = authenticated_client.get("/api/v1/test-plans")

    assert response.status_code == 200
    item = next(
        item
        for item in response.json()["items"]
        if item["id"] == plan["id"]
    )
    assert item["latest_execution"]["report_status"] == "failure"


def test_plan_list_latest_execution_running_when_some_children_finished_and_queued(
    authenticated_client,
):
    case_ids = [
        _create_case(authenticated_client, "部分完成用例 1"),
        _create_case(authenticated_client, "部分完成用例 2"),
    ]
    plan = _create_plan(
        authenticated_client,
        "部分完成仍排队计划",
        case_ids=case_ids,
    )
    execution_id = _seed_execution(
        authenticated_client,
        plan,
        [Verdict.PASS, Verdict.PASS],
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    with authenticated_client.app.state.session_factory() as db:
        execution = db.get(PlanExecution, execution_id)
        assert execution is not None
        batch = db.get(TaskBatch, execution.task_batch_id)
        assert batch is not None
        batch.execution_status = ExecutionStatus.QUEUED
        batch.verdict = None
        queued_task = db.scalar(
            select(Task)
            .where(Task.batch_id == batch.id)
            .order_by(Task.batch_position.desc())
        )
        assert queued_task is not None
        queued_task.execution_status = ExecutionStatus.QUEUED
        queued_task.verdict = None
        queued_task.started_at = None
        queued_task.finished_at = None
        db.commit()

    response = authenticated_client.get("/api/v1/test-plans")

    assert response.status_code == 200, response.text
    item = next(
        item
        for item in response.json()["items"]
        if item["id"] == plan["id"]
    )
    assert item["latest_execution"]["report_status"] == "running"


def test_plan_cases_use_backend_pagination_and_preserve_order(
    authenticated_client,
):
    case_ids = [
        _create_case(authenticated_client, f"绑定用例 {index:02d}")
        for index in range(11)
    ]
    ordered_ids = list(reversed(case_ids))
    plan = _create_plan(
        authenticated_client,
        "分页绑定计划",
        case_ids=ordered_ids,
    )

    first = authenticated_client.get(
        f"/api/v1/test-plans/{plan['id']}/cases",
        params={"page": 1, "page_size": 10},
    )
    second = authenticated_client.get(
        f"/api/v1/test-plans/{plan['id']}/cases",
        params={"page": 2, "page_size": 10},
    )

    assert first.status_code == 200
    assert first.json()["total"] == 11
    assert [item["id"] for item in first.json()["items"]] == ordered_ids[:10]
    assert second.status_code == 200
    assert [item["id"] for item in second.json()["items"]] == ordered_ids[10:]


def test_plan_cases_query_count_is_constant_and_statistics_are_batched(
    authenticated_client,
):
    case_ids = [
        _create_case(authenticated_client, f"批量统计用例 {index}")
        for index in range(4)
    ]
    plan = _create_plan(
        authenticated_client,
        "批量统计计划",
        case_ids=case_ids,
    )
    _seed_execution(
        authenticated_client,
        plan,
        [Verdict.PASS, Verdict.FAIL, Verdict.PASS, Verdict.FAIL],
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    single, single_statements = _get_with_statement_count(
        authenticated_client,
        f"/api/v1/test-plans/{plan['id']}/cases",
        params={"page": 1, "page_size": 1},
    )
    multiple, multiple_statements = _get_with_statement_count(
        authenticated_client,
        f"/api/v1/test-plans/{plan['id']}/cases",
        params={"page": 1, "page_size": 4},
    )

    assert single.status_code == 200
    assert multiple.status_code == 200
    assert [item["id"] for item in multiple.json()["items"]] == case_ids
    assert [
        (
            item["execution_count"],
            item["pass_count"],
            item["fail_count"],
        )
        for item in multiple.json()["items"]
    ] == [
        (1, 1, 0),
        (1, 0, 1),
        (1, 1, 0),
        (1, 0, 1),
    ]
    assert len(multiple_statements) == len(single_statements)
    assert not any(
        "test_plan_cases.plan_id IN" in statement
        for statement in multiple_statements
    )


def test_tag_registry_is_unique_searchable_and_paginated(
    authenticated_client,
):
    case_id = _create_case(
        authenticated_client,
        "标签计数用例",
        tags=["标签-00", "标签-01"],
    )
    _create_plan(
        authenticated_client,
        "计划 A",
        case_ids=[case_id],
        tags=[f"标签-{index:02d}" for index in range(20)],
    )

    first = authenticated_client.get(
        "/api/v1/tags",
        params={"page": 1, "page_size": 10, "search": "标签-"},
    )
    second = authenticated_client.get(
        "/api/v1/tags",
        params={"page": 2, "page_size": 10, "search": "标签-"},
    )

    assert first.status_code == 200
    assert first.json()["total"] == 20
    assert len(first.json()["items"]) == 10
    assert len(second.json()["items"]) == 10
    tags = first.json()["items"] + second.json()["items"]
    assert len({item["foreground_color"] for item in tags}) == len(tags)
    assert {
        item["foreground_color"] for item in tags
    } <= set(_TAG_COLOR_CANDIDATES)
    assert next(item for item in tags if item["name"] == "标签-00")[
        "case_count"
    ] == 1
    assert all(item["background_color"].endswith("1A") for item in tags)


def test_tag_list_does_not_register_legacy_case_tags_during_get(
    authenticated_client,
):
    with authenticated_client.app.state.session_factory() as db:
        db.add(
            CaseModel(
                id="case_legacy_tag",
                title="遗留标签用例",
                module="登录",
                content_markdown="执行",
                tags=["未注册遗留标签"],
                automation_level="auto",
                created_by="admin",
            )
        )
        db.commit()

    response, statements = _get_with_statement_count(
        authenticated_client,
        "/api/v1/tags",
        params={"search": "未注册遗留标签"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert not any(
        statement.lstrip().upper().startswith(
            ("INSERT", "UPDATE", "DELETE")
        )
        for statement in statements
    )
    with authenticated_client.app.state.session_factory() as db:
        assert db.get(TagColorRegistry, "未注册遗留标签") is None


def test_active_plan_name_is_unique_but_reusable_after_soft_delete(
    authenticated_client,
):
    case_id = _create_case(authenticated_client, "名称冲突用例")
    first = _create_plan(
        authenticated_client,
        "核心回归",
        case_ids=[case_id],
    )

    duplicate = _create_plan_response(
        authenticated_client,
        " 核心回归 ",
        case_ids=[case_id],
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "test_plan_name_conflict"

    deleted = authenticated_client.delete(
        f"/api/v1/test-plans/{first['id']}"
    )
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert "content-type" not in deleted.headers
    assert (
        authenticated_client.get(
            f"/api/v1/test-plans/{first['id']}"
        ).status_code
        == 404
    )
    recreated = _create_plan_response(
        authenticated_client,
        "核心回归",
        case_ids=[case_id],
    )
    assert recreated.status_code == 201


def test_active_plan_name_conflict_uses_unicode_casefold(
    authenticated_client,
):
    case_id = _create_case(authenticated_client, "Casefold 用例")
    _create_plan(
        authenticated_client,
        "CORE REGRESSION",
        case_ids=[case_id],
    )

    duplicate = _create_plan_response(
        authenticated_client,
        " core regression ",
        case_ids=[case_id],
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "test_plan_name_conflict"


def test_plan_name_length_is_validated_after_trimming(authenticated_client):
    case_id = _create_case(authenticated_client, "名称长度用例")
    name = "A" * 100

    response = _create_plan_response(
        authenticated_client,
        f" {name} ",
        case_ids=[case_id],
    )

    assert response.status_code == 201, response.text
    assert response.json()["name"] == name


def test_plan_write_rejects_non_utf8_tag_before_color_allocation():
    with pytest.raises(ValidationError):
        PlanWrite(
            name="非法标签计划",
            tags=["\ud800"],
            case_ids=["case_1"],
        )


def test_plan_write_rejects_non_utf8_name_before_database_write():
    with pytest.raises(ValidationError):
        PlanWrite(
            name="\ud800",
            tags=[],
            case_ids=["case_1"],
        )


@pytest.mark.parametrize(
    ("name", "case_ids"),
    [
        ("   ", ["case_placeholder"]),
        ("无用例计划", []),
        ("过量用例计划", [f"case_{index}" for index in range(101)]),
    ],
)
def test_plan_write_rejects_invalid_name_or_case_count(
    authenticated_client,
    name,
    case_ids,
):
    response = authenticated_client.post(
        "/api/v1/test-plans",
        json={
            "name": name,
            "description": None,
            "tags": [],
            "case_ids": case_ids,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_failed"


def test_plan_write_rejects_missing_cases_without_partial_update(
    authenticated_client,
):
    case_id = _create_case(authenticated_client, "原子更新用例")
    plan = _create_plan(
        authenticated_client,
        "原始计划",
        case_ids=[case_id],
        tags=["原始标签"],
    )

    response = authenticated_client.put(
        f"/api/v1/test-plans/{plan['id']}",
        json={
            "name": "被拒绝的新名称",
            "description": "不应保存",
            "tags": ["不应注册"],
            "case_ids": [case_id, "case_missing"],
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "test_plan_cases_not_found"
    assert response.json()["error"]["details"]["case_ids"] == ["case_missing"]
    unchanged = authenticated_client.get(
        f"/api/v1/test-plans/{plan['id']}"
    ).json()
    assert unchanged["name"] == "原始计划"
    assert [tag["name"] for tag in unchanged["tags"]] == ["原始标签"]
    tags = authenticated_client.get(
        "/api/v1/tags",
        params={"search": "不应注册"},
    ).json()
    assert tags["total"] == 0


def test_create_plan_rejects_soft_deleted_case(authenticated_client):
    case_id = _create_case(authenticated_client, "已软删除候选用例")
    with authenticated_client.app.state.session_factory() as db:
        case = db.get(CaseModel, case_id)
        assert case is not None
        case.deleted_at = datetime.now(UTC)
        db.commit()

    response = _create_plan_response(
        authenticated_client,
        "不能引用软删除用例",
        case_ids=[case_id],
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "test_plan_cases_not_found"
    assert response.json()["error"]["details"]["case_ids"] == [case_id]


def test_soft_delete_preserves_execution_snapshot(authenticated_client):
    case_id = _create_case(authenticated_client, "快照用例")
    plan = _create_plan(
        authenticated_client,
        "历史快照计划",
        case_ids=[case_id],
        tags=["历史标签"],
    )
    execution_id = _seed_execution(
        authenticated_client,
        plan,
        [Verdict.PASS],
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    response = authenticated_client.delete(
        f"/api/v1/test-plans/{plan['id']}"
    )

    assert response.status_code == 204
    with authenticated_client.app.state.session_factory() as db:
        execution = db.get(PlanExecution, execution_id)
        assert execution is not None
        assert execution.test_plan_id == plan["id"]
        assert execution.plan_name_snapshot == "历史快照计划"
        assert execution.plan_tags_snapshot == ["历史标签"]
        assert execution.case_ids_snapshot == [case_id]


def test_plan_stats_use_each_active_plans_latest_completed_execution(
    authenticated_client,
):
    first_cases = [
        _create_case(authenticated_client, "统计用例 A"),
        _create_case(authenticated_client, "统计用例 B"),
    ]
    third_case = _create_case(authenticated_client, "统计用例 C")
    first = _create_plan(
        authenticated_client,
        "统计计划一",
        case_ids=first_cases,
    )
    second = _create_plan(
        authenticated_client,
        "统计计划二",
        case_ids=[first_cases[1], third_case],
    )
    deleted = _create_plan(
        authenticated_client,
        "已删除统计计划",
        case_ids=[first_cases[0]],
    )
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    _seed_execution(
        authenticated_client,
        first,
        [Verdict.PASS, Verdict.PASS],
        created_at=base_time,
    )
    latest_first = _seed_execution(
        authenticated_client,
        first,
        [Verdict.PASS, Verdict.FAIL],
        created_at=base_time + timedelta(days=1),
    )
    _seed_execution(
        authenticated_client,
        second,
        [Verdict.PASS, Verdict.PASS],
        created_at=base_time + timedelta(days=2),
    )
    _seed_execution(
        authenticated_client,
        deleted,
        [Verdict.PASS],
        created_at=base_time + timedelta(days=3),
    )
    authenticated_client.delete(f"/api/v1/test-plans/{deleted['id']}")

    response = authenticated_client.get("/api/v1/test-plans/stats")

    assert response.status_code == 200
    assert response.json() == {
        "active_plan_count": 2,
        "distinct_case_count": 3,
        "execution_count": 3,
        "latest_completed_pass_rate": 50.0,
    }
    detail = authenticated_client.get(
        f"/api/v1/test-plans/{first['id']}"
    ).json()
    assert detail["execution_count"] == 2
    assert detail["latest_execution"]["execution_id"] == latest_first
    assert detail["latest_execution"]["report_status"] == "failure"
    assert detail["latest_execution"]["pass_rate"] == 50.0


def test_delete_case_bound_to_active_plan_returns_stable_conflict(
    authenticated_client,
):
    case_id = _create_case(authenticated_client, "计划绑定用例")
    plan = _create_plan(
        authenticated_client,
        "删除保护计划",
        case_ids=[case_id],
    )

    response = authenticated_client.delete(f"/api/v1/cases/{case_id}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "case_has_test_plans"
    authenticated_client.delete(f"/api/v1/test-plans/{plan['id']}")
    assert (
        authenticated_client.delete(f"/api/v1/cases/{case_id}").status_code
        == 204
    )


def test_case_bound_plans_and_remove_case_update_plan_count(authenticated_client):
    case_id = _create_case(authenticated_client, "待解除绑定用例")
    other_id = _create_case(authenticated_client, "保留绑定用例")
    plan = _create_plan(
        authenticated_client,
        "解除绑定计划",
        case_ids=[case_id, other_id],
    )

    bound = authenticated_client.get(f"/api/v1/cases/{case_id}/test-plans")
    removed = authenticated_client.delete(
        f"/api/v1/test-plans/{plan['id']}/cases/{case_id}"
    )
    rebound = authenticated_client.get(f"/api/v1/cases/{case_id}/test-plans")
    detail = authenticated_client.get(f"/api/v1/test-plans/{plan['id']}")

    assert bound.status_code == 200
    assert bound.json()["total"] == 1
    assert bound.json()["items"][0]["id"] == plan["id"]
    assert bound.json()["items"][0]["case_count"] == 2
    assert removed.status_code == 204
    assert rebound.status_code == 200
    assert rebound.json()["total"] == 0
    assert detail.json()["case_count"] == 1
    assert detail.json()["case_ids"] == [other_id]


def test_case_bound_plans_are_paginated(authenticated_client):
    case_id = _create_case(authenticated_client, "分页绑定用例")
    [
        _create_plan(
            authenticated_client,
            f"分页绑定计划 {index}",
            case_ids=[case_id],
        )["id"]
        for index in range(7)
    ]

    response = authenticated_client.get(
        f"/api/v1/cases/{case_id}/test-plans",
        params={"page": 2, "page_size": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 7
    assert body["page"] == 2
    assert body["page_size"] == 5
    assert len(body["items"]) == 2


def test_remove_case_from_plan_rejects_active_execution(authenticated_client):
    case_id = _create_case(authenticated_client, "执行中禁止移除")
    other_id = _create_case(authenticated_client, "执行中保留用例")
    plan = _create_plan(
        authenticated_client,
        "执行中计划",
        case_ids=[case_id, other_id],
    )
    execution_id = _seed_execution(
        authenticated_client,
        plan,
        [Verdict.PASS, Verdict.PASS],
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    with authenticated_client.app.state.session_factory() as db:
        execution = db.get(PlanExecution, execution_id)
        assert execution is not None
        batch = db.get(TaskBatch, execution.task_batch_id)
        assert batch is not None
        batch.execution_status = ExecutionStatus.RUNNING
        db.commit()

    response = authenticated_client.delete(
        f"/api/v1/test-plans/{plan['id']}/cases/{case_id}"
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "test_plan_execution_active"


def test_remove_case_from_plan_rejects_last_case(authenticated_client):
    case_id = _create_case(authenticated_client, "最后一个用例")
    plan = _create_plan(
        authenticated_client,
        "单用例计划",
        case_ids=[case_id],
    )

    response = authenticated_client.delete(
        f"/api/v1/test-plans/{plan['id']}/cases/{case_id}"
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "test_plan_requires_one_case"


def test_remove_middle_case_from_plan_reorders_positions(authenticated_client):
    case_ids = [
        _create_case(authenticated_client, f"重排用例 {index}")
        for index in range(6)
    ]
    plan = _create_plan(
        authenticated_client,
        "重排计划",
        case_ids=case_ids,
    )

    response = authenticated_client.delete(
        f"/api/v1/test-plans/{plan['id']}/cases/{case_ids[2]}"
    )

    assert response.status_code == 204, response.text
    expected_case_ids = case_ids[:2] + case_ids[3:]
    detail = authenticated_client.get(f"/api/v1/test-plans/{plan['id']}")
    assert detail.status_code == 200
    assert detail.json()["case_ids"] == expected_case_ids
    with authenticated_client.app.state.session_factory() as db:
        rows = db.execute(
            select(plan_models.TestPlanCase.case_id, plan_models.TestPlanCase.position)
            .where(plan_models.TestPlanCase.plan_id == plan["id"])
            .order_by(plan_models.TestPlanCase.position)
        ).all()
    assert [case_id for case_id, _position in rows] == expected_case_ids
    assert [position for _case_id, position in rows] == list(
        range(len(expected_case_ids))
    )


def test_unknown_plan_routes_return_stable_not_found(authenticated_client):
    detail = authenticated_client.get(
        "/api/v1/test-plans/plan_missing"
    )
    cases = authenticated_client.get(
        "/api/v1/test-plans/plan_missing/cases"
    )
    deleted = authenticated_client.delete(
        "/api/v1/test-plans/plan_missing"
    )

    for response in (detail, cases, deleted):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "test_plan_not_found"


def test_plan_update_name_conflict_rolls_back_all_fields(
    authenticated_client,
):
    case_ids = [
        _create_case(authenticated_client, "冲突更新用例一"),
        _create_case(authenticated_client, "冲突更新用例二"),
    ]
    _create_plan(
        authenticated_client,
        "保留名称",
        case_ids=[case_ids[0]],
    )
    target = _create_plan(
        authenticated_client,
        "待更新计划",
        case_ids=[case_ids[1]],
        tags=["更新前"],
    )

    response = authenticated_client.put(
        f"/api/v1/test-plans/{target['id']}",
        json={
            "name": " 保留名称 ",
            "description": "不应保存",
            "tags": ["更新后"],
            "case_ids": case_ids,
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "test_plan_name_conflict"
    unchanged = authenticated_client.get(
        f"/api/v1/test-plans/{target['id']}"
    ).json()
    assert unchanged["name"] == "待更新计划"
    assert unchanged["case_ids"] == [case_ids[1]]
    assert [tag["name"] for tag in unchanged["tags"]] == ["更新前"]
    registered = authenticated_client.get(
        "/api/v1/tags",
        params={"search": "更新后"},
    ).json()
    assert registered["total"] == 0


def test_plan_records_are_soft_deleted_in_database(authenticated_client):
    case_id = _create_case(authenticated_client, "软删数据库用例")
    plan = _create_plan(
        authenticated_client,
        "软删数据库计划",
        case_ids=[case_id],
    )

    authenticated_client.delete(f"/api/v1/test-plans/{plan['id']}")

    with authenticated_client.app.state.session_factory() as db:
        from mua_platform.test_plans.models import TestPlan

        stored = db.scalar(
            select(TestPlan).where(TestPlan.id == plan["id"])
        )
        assert stored is not None
        assert stored.deleted_at is not None
