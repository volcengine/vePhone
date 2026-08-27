import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from mua_platform.tasks.models import Task, TaskBatch, TaskRunnerConfig
from mua_platform.tasks.state_machine import ExecutionStatus
from mua_platform.test_plans.models import PlanExecution


def _configure_runner(client) -> None:
    response = client.put(
        "/api/v1/settings/runner",
        json={
            "mode": "mobile_use",
            "mobile_use": {
                "access_key_id": "AKLT00000000PLAN",
                "secret_access_key": "plan-secret",
                "product_id": "product-plan",
                "tos_bucket": "plan-bucket",
                "tos_region": "cn-beijing",
            },
        },
    )
    assert response.status_code == 200, response.text


def _create_case(
    client,
    title: str,
    *,
    default_agent_options: dict | None = None,
) -> str:
    payload = {
        "title": title,
        "module": "计划执行",
        "content_markdown": f"## 执行任务\n- 验证 {title}",
        "tags": ["plan-run"],
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


def _create_plan(client, name: str, case_ids: list[str]) -> dict:
    response = client.post(
        "/api/v1/test-plans",
        json={
            "name": name,
            "description": "计划执行测试",
            "tags": ["每日回归", "P0"],
            "case_ids": case_ids,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _run_payload(**overrides) -> dict:
    payload = {
        "test_type": "regression",
        "device_strategy": "automatic",
        "pod_ids": [],
        "concurrency": 1,
        "timeout_seconds": 600,
        "agent_config_mode": "global",
        "agent_options": None,
        "idempotency_key": "plan-run-1",
    }
    payload.update(overrides)
    return payload


def test_run_single_case_plan_creates_ordered_atomic_snapshot(
    authenticated_client,
):
    _configure_runner(authenticated_client)
    case_id = _create_case(authenticated_client, "单用例")
    plan = _create_plan(
        authenticated_client,
        "单用例计划",
        [case_id],
    )
    schedule_calls = 0

    async def schedule_batches():
        nonlocal schedule_calls
        schedule_calls += 1
        return []

    authenticated_client.app.state.schedule_batches = schedule_batches

    response = authenticated_client.post(
        f"/api/v1/test-plans/{plan['id']}/executions",
        json=_run_payload(),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["test_plan_id"] == plan["id"]
    assert body["plan_name_snapshot"] == plan["name"]
    assert body["plan_tags_snapshot"] == ["每日回归", "P0"]
    assert body["case_ids_snapshot"] == [case_id]
    assert body["device_strategy_snapshot"] == "automatic"
    assert body["pod_ids_snapshot"] == []
    assert body["concurrency_snapshot"] == 1
    assert body["runner_type_snapshot"] == "mobile_use"
    assert body["config_snapshot"]["source"] == "global"
    assert body["config_snapshot"]["product_id"] == "product-plan"
    assert body["config_snapshot"]["timeout_seconds"] == 600
    assert body["batch"]["id"] == body["task_batch_id"]
    assert body["batch"]["selection_mode"] == "test_plan"
    assert body["batch"]["selection_snapshot"] == {
        "test_plan_id": plan["id"],
        "case_ids": [case_id],
    }
    assert [task["case_id"] for task in body["batch"]["tasks"]] == [
        case_id
    ]
    assert schedule_calls == 1

    with authenticated_client.app.state.session_factory() as db:
        execution = db.get(PlanExecution, body["id"])
        batch = db.get(TaskBatch, body["task_batch_id"])
        assert execution is not None
        assert batch is not None
        assert execution.task_batch_id == batch.id
        assert execution.case_ids_snapshot == [case_id]
        assert execution.config_snapshot["config_source"] == "global"
        assert db.scalar(select(func.count()).select_from(Task)) == 1
        assert (
            db.scalar(select(func.count()).select_from(TaskRunnerConfig))
            == 1
        )


def test_run_plan_uses_payload_device_wait_timeout(authenticated_client):
    _configure_runner(authenticated_client)
    case_id = _create_case(authenticated_client, "等待超时计划用例")
    plan = _create_plan(authenticated_client, "等待超时计划", [case_id])

    response = authenticated_client.post(
        f"/api/v1/test-plans/{plan['id']}/executions",
        json=_run_payload(
            device_wait_timeout_seconds=75,
            idempotency_key="plan-run-device-wait",
        ),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["batch"]["device_wait_timeout_seconds"] == 75
    assert body["config_snapshot"]["device_wait_timeout_seconds"] == 75
    with authenticated_client.app.state.session_factory() as db:
        batch = db.get(TaskBatch, body["task_batch_id"])
        assert batch is not None
        assert batch.device_wait_timeout_seconds == 75


def test_run_plan_preserves_case_order_and_custom_specified_config(
    authenticated_client,
):
    _configure_runner(authenticated_client)
    case_ids = [
        _create_case(authenticated_client, f"顺序用例 {index}")
        for index in range(3)
    ]
    ordered_case_ids = [case_ids[2], case_ids[0], case_ids[1]]
    plan = _create_plan(
        authenticated_client,
        "指定设备计划",
        ordered_case_ids,
    )
    payload = _run_payload(
        device_strategy="specified",
        pod_ids=["pod-a", "pod-b"],
        concurrency=2,
        agent_config_mode="custom",
        agent_options={
            "timeout_seconds": 321,
            "callback_info": {
                "url": "https://callback.example.com",
                "authorization": "Bearer callback-secret",
            },
            "mcp_json": (
                '{"mcpServers":{"demo":{"url":"https://mcp.example.com",'
                '"headers":{"Authorization":"Bearer mcp-secret"}}}}'
            ),
        },
        idempotency_key="plan-run-custom",
    )

    response = authenticated_client.post(
        f"/api/v1/test-plans/{plan['id']}/executions",
        json=payload,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["case_ids_snapshot"] == ordered_case_ids
    assert body["pod_ids_snapshot"] == ["pod-a", "pod-b"]
    assert [task["case_id"] for task in body["batch"]["tasks"]] == (
        ordered_case_ids
    )
    assert {
        task["queue_reason"] for task in body["batch"]["tasks"]
    } == {"waiting_for_specified_device"}
    public_config = body["config_snapshot"]
    assert public_config["source"] == "custom"
    assert public_config["timeout_seconds"] == 321
    assert public_config["callback_info"]["authorization"] == "***"
    assert "callback-secret" not in response.text
    assert "mcp-secret" not in response.text

    with authenticated_client.app.state.session_factory() as db:
        execution = db.get(PlanExecution, body["id"])
        assert execution is not None
        assert execution.config_snapshot["callback_info"][
            "authorization"
        ] == "Bearer callback-secret"
        assert "mcp-secret" in execution.config_snapshot["mcp_json"]
        task_configs = list(
            db.scalars(
                select(TaskRunnerConfig).order_by(
                    TaskRunnerConfig.task_id
                )
            )
        )
        assert len(task_configs) == 3
        assert all(
            config.config_snapshot["callback_info"]["authorization"]
            == "Bearer callback-secret"
            for config in task_configs
        )


def test_run_plan_can_apply_case_default_agent_options_with_global_fallback(
    authenticated_client,
):
    _configure_runner(authenticated_client)
    configured_case = _create_case(
        authenticated_client,
        "带默认配置计划用例",
        default_agent_options={
            "thread_id": "thread-plan-case",
            "timeout_seconds": 222,
            "max_step": 111,
            "tos_bucket": "case-plan-bucket",
            "tos_region": "cn-beijing",
        },
    )
    fallback_case = _create_case(authenticated_client, "无默认配置计划用例")
    plan = _create_plan(
        authenticated_client,
        "用例默认配置计划",
        [configured_case, fallback_case],
    )

    response = authenticated_client.post(
        f"/api/v1/test-plans/{plan['id']}/executions",
        json=_run_payload(
            agent_config_mode="case_default",
            timeout_seconds=None,
            idempotency_key="plan-case-default",
        ),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["config_snapshot"]["source"] == "case_default"
    assert body["config_snapshot"]["timeout_seconds"] == 120
    with authenticated_client.app.state.session_factory() as db:
        task_configs = {
            config.task_id: config.config_snapshot
            for config in db.scalars(select(TaskRunnerConfig)).all()
        }
        tasks = list(db.scalars(select(Task)).all())
        config_by_case_id = {
            task.case_id: task_configs[task.id]
            for task in tasks
        }
        assert (
            config_by_case_id[configured_case]["config_source"]
            == "case_default"
        )
        assert (
            config_by_case_id[configured_case]["thread_id"]
            == "thread-plan-case"
        )
        assert config_by_case_id[configured_case]["max_step"] == 111
        assert (
            config_by_case_id[configured_case]["tos_bucket"]
            == "case-plan-bucket"
        )
        assert (
            config_by_case_id[fallback_case]["config_source"]
            == "case_default"
        )
        assert "thread_id" not in config_by_case_id[fallback_case]
        assert config_by_case_id[fallback_case]["tos_bucket"] == "plan-bucket"


def test_run_plan_idempotent_replay_reschedules_queued_batch(
    authenticated_client,
):
    _configure_runner(authenticated_client)
    case_id = _create_case(authenticated_client, "幂等用例")
    plan = _create_plan(authenticated_client, "幂等计划", [case_id])
    schedule_calls = 0

    async def schedule_batches():
        nonlocal schedule_calls
        schedule_calls += 1
        return []

    authenticated_client.app.state.schedule_batches = schedule_batches
    url = f"/api/v1/test-plans/{plan['id']}/executions"
    payload = _run_payload(idempotency_key="plan-idempotent")

    first = authenticated_client.post(url, json=payload)
    second = authenticated_client.post(url, json=payload)

    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["task_batch_id"] == first.json()["task_batch_id"]
    assert schedule_calls == 2
    with authenticated_client.app.state.session_factory() as db:
        assert (
            db.scalar(select(func.count()).select_from(PlanExecution))
            == 1
        )
        assert db.scalar(select(func.count()).select_from(TaskBatch)) == 1
        assert db.scalar(select(func.count()).select_from(Task)) == 1


def test_run_plan_replay_compensates_after_initial_scheduler_failure(
    authenticated_client,
):
    _configure_runner(authenticated_client)
    case_id = _create_case(authenticated_client, "调度补偿用例")
    plan = _create_plan(
        authenticated_client,
        "调度补偿计划",
        [case_id],
    )
    schedule_calls = 0

    async def schedule_batches():
        nonlocal schedule_calls
        schedule_calls += 1
        if schedule_calls == 1:
            raise RuntimeError("scheduler unavailable")
        return []

    authenticated_client.app.state.schedule_batches = schedule_batches
    url = f"/api/v1/test-plans/{plan['id']}/executions"
    payload = _run_payload(idempotency_key="plan-schedule-recovery")

    with pytest.raises(RuntimeError, match="scheduler unavailable"):
        authenticated_client.post(url, json=payload)

    with authenticated_client.app.state.session_factory() as db:
        assert (
            db.scalar(select(func.count()).select_from(PlanExecution))
            == 1
        )
        assert db.scalar(select(func.count()).select_from(TaskBatch)) == 1
        assert db.scalar(select(func.count()).select_from(Task)) == 1
        batch = db.scalar(select(TaskBatch))
        assert batch is not None
        assert batch.execution_status.value == "queued"

    replay = authenticated_client.post(url, json=payload)

    assert replay.status_code == 200, replay.text
    assert schedule_calls == 2
    with authenticated_client.app.state.session_factory() as db:
        assert (
            db.scalar(select(func.count()).select_from(PlanExecution))
            == 1
        )
        assert db.scalar(select(func.count()).select_from(TaskBatch)) == 1
        assert db.scalar(select(func.count()).select_from(Task)) == 1


def test_run_plan_replay_does_not_reschedule_running_batch(
    authenticated_client,
):
    _configure_runner(authenticated_client)
    case_id = _create_case(authenticated_client, "运行中重放用例")
    plan = _create_plan(
        authenticated_client,
        "运行中重放计划",
        [case_id],
    )
    schedule_calls = 0

    async def schedule_batches():
        nonlocal schedule_calls
        schedule_calls += 1
        return []

    authenticated_client.app.state.schedule_batches = schedule_batches
    url = f"/api/v1/test-plans/{plan['id']}/executions"
    payload = _run_payload(idempotency_key="plan-running-replay")

    first = authenticated_client.post(url, json=payload)
    assert first.status_code == 201, first.text
    with authenticated_client.app.state.session_factory() as db:
        batch = db.get(TaskBatch, first.json()["task_batch_id"])
        assert batch is not None
        batch.execution_status = ExecutionStatus.RUNNING
        db.commit()

    replay = authenticated_client.post(url, json=payload)

    assert replay.status_code == 200, replay.text
    assert schedule_calls == 1


def test_run_plan_rejects_idempotency_conflict(authenticated_client):
    _configure_runner(authenticated_client)
    case_id = _create_case(authenticated_client, "冲突用例")
    plan = _create_plan(authenticated_client, "冲突计划", [case_id])
    url = f"/api/v1/test-plans/{plan['id']}/executions"

    first = authenticated_client.post(
        url,
        json=_run_payload(idempotency_key="plan-conflict"),
    )
    conflict = authenticated_client.post(
        url,
        json=_run_payload(
            idempotency_key="plan-conflict",
            timeout_seconds=601,
        ),
    )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    with authenticated_client.app.state.session_factory() as db:
        assert (
            db.scalar(select(func.count()).select_from(PlanExecution))
            == 1
        )


def test_run_plan_rejects_concurrency_above_case_count(
    authenticated_client,
):
    _configure_runner(authenticated_client)
    case_id = _create_case(authenticated_client, "并发边界用例")
    plan = _create_plan(
        authenticated_client,
        "并发边界计划",
        [case_id],
    )

    response = authenticated_client.post(
        f"/api/v1/test-plans/{plan['id']}/executions",
        json=_run_payload(
            concurrency=2,
            idempotency_key="concurrency-overflow",
        ),
    )

    assert response.status_code == 422
    assert (
        response.json()["error"]["code"]
        == "concurrency_exceeds_case_count"
    )
    with authenticated_client.app.state.session_factory() as db:
        assert (
            db.scalar(select(func.count()).select_from(PlanExecution))
            == 0
        )
        assert db.scalar(select(func.count()).select_from(TaskBatch)) == 0


def test_run_plan_rejects_more_specified_pods_than_concurrency(
    authenticated_client,
):
    _configure_runner(authenticated_client)
    case_ids = [
        _create_case(authenticated_client, f"指定设备并发用例 {index}")
        for index in range(3)
    ]
    plan = _create_plan(
        authenticated_client,
        "指定设备并发计划",
        case_ids,
    )

    response = authenticated_client.post(
        f"/api/v1/test-plans/{plan['id']}/executions",
        json=_run_payload(
            device_strategy="specified",
            pod_ids=["pod-a", "pod-b"],
            concurrency=1,
            idempotency_key="pod-count-overflow",
        ),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == (
        "pod_count_exceeds_concurrency"
    )
    with authenticated_client.app.state.session_factory() as db:
        assert (
            db.scalar(select(func.count()).select_from(PlanExecution))
            == 0
        )
        assert db.scalar(select(func.count()).select_from(TaskBatch)) == 0


def test_plan_execution_insert_failure_rolls_back_batch_and_tasks(
    authenticated_client,
):
    _configure_runner(authenticated_client)
    case_id = _create_case(authenticated_client, "回滚用例")
    plan = _create_plan(authenticated_client, "回滚计划", [case_id])
    with authenticated_client.app.state.session_factory() as db:
        db.execute(
            text(
                "CREATE TRIGGER fail_plan_execution "
                "BEFORE INSERT ON plan_executions "
                "BEGIN "
                "SELECT RAISE(ABORT, 'forced plan execution failure'); "
                "END"
            )
        )
        db.commit()
    try:
        with pytest.raises(IntegrityError):
            authenticated_client.post(
                f"/api/v1/test-plans/{plan['id']}/executions",
                json=_run_payload(idempotency_key="plan-rollback"),
            )
    finally:
        with authenticated_client.app.state.session_factory() as db:
            db.execute(text("DROP TRIGGER fail_plan_execution"))
            db.commit()

    with authenticated_client.app.state.session_factory() as db:
        assert (
            db.scalar(select(func.count()).select_from(PlanExecution))
            == 0
        )
        assert db.scalar(select(func.count()).select_from(TaskBatch)) == 0
        assert db.scalar(select(func.count()).select_from(Task)) == 0
        assert (
            db.scalar(select(func.count()).select_from(TaskRunnerConfig))
            == 0
        )


def test_run_plan_rejects_unknown_and_soft_deleted_plan(
    authenticated_client,
):
    _configure_runner(authenticated_client)
    missing = authenticated_client.post(
        "/api/v1/test-plans/plan_missing/executions",
        json=_run_payload(idempotency_key="missing-plan"),
    )
    case_id = _create_case(authenticated_client, "软删除用例")
    plan = _create_plan(authenticated_client, "软删除计划", [case_id])
    deleted = authenticated_client.delete(
        f"/api/v1/test-plans/{plan['id']}"
    )
    soft_deleted = authenticated_client.post(
        f"/api/v1/test-plans/{plan['id']}/executions",
        json=_run_payload(idempotency_key="deleted-plan"),
    )

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "test_plan_not_found"
    assert deleted.status_code == 204
    assert soft_deleted.status_code == 404
    assert soft_deleted.json()["error"]["code"] == "test_plan_not_found"


def test_run_plan_supports_one_to_one_hundred_cases(
    authenticated_client,
):
    _configure_runner(authenticated_client)
    case_ids = [
        _create_case(authenticated_client, f"边界用例 {index:03d}")
        for index in range(100)
    ]
    plan = _create_plan(authenticated_client, "百用例计划", case_ids)

    response = authenticated_client.post(
        f"/api/v1/test-plans/{plan['id']}/executions",
        json=_run_payload(
            concurrency=20,
            idempotency_key="hundred-case-plan",
        ),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["case_ids_snapshot"] == case_ids
    assert len(body["batch"]["tasks"]) == 100
    assert [task["batch_position"] for task in body["batch"]["tasks"]] == (
        list(range(100))
    )

    overflow_case_id = _create_case(
        authenticated_client,
        "边界用例 101",
    )
    overflow_plan = authenticated_client.post(
        "/api/v1/test-plans",
        json={
            "name": "超限计划",
            "tags": [],
            "case_ids": [*case_ids, overflow_case_id],
        },
    )
    assert overflow_plan.status_code == 422
