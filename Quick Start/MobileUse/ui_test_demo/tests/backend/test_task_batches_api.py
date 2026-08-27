from sqlalchemy import func, select

from mua_platform.tasks.models import (
    PodLease,
    Task,
    TaskBatch,
    TaskRunnerConfig,
)
from mua_platform.test_plans.models import PlanExecution


def _create_case(client, title: str) -> str:
    response = client.post(
        "/api/v1/cases",
        json={
            "title": title,
            "module": "批次",
            "content_markdown": f"## 执行任务\n- 验证 {title}",
            "tags": ["batch"],
            "automation_level": "auto",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _payload(case_ids: list[str]) -> dict:
    return {
        "name": "核心回归批次",
        "test_type": "regression",
        "selection_mode": "multi_cases",
        "case_ids": case_ids,
        "selection_snapshot": {"case_ids": case_ids},
        "device_strategy": "automatic",
        "pod_ids": [],
        "concurrency": 2,
        "agent_config_mode": "global",
        "idempotency_key": "batch-create-1",
    }


def _configure_runner(client) -> None:
    response = client.put(
        "/api/v1/settings/runner",
        json={
            "mode": "mobile_use",
            "mobile_use": {
                "access_key_id": "AKLT00000000BATCH",
                "secret_access_key": "batch-secret",
                "product_id": "product-batch",
                "tos_bucket": "batch-bucket",
                "tos_region": "cn-beijing",
            },
        },
    )
    assert response.status_code == 200


def test_create_batch_persists_children_without_preallocating_pods(
    authenticated_client,
):
    _configure_runner(authenticated_client)
    case_ids = [
        _create_case(authenticated_client, "登录"),
        _create_case(authenticated_client, "搜索"),
        _create_case(authenticated_client, "发布"),
    ]

    response = authenticated_client.post(
        "/api/v1/task-batches",
        json=_payload(case_ids),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "核心回归批次"
    assert body["device_wait_timeout_seconds"] == 300
    assert len(body["tasks"]) == 3
    assert [task["case_id"] for task in body["tasks"]] == case_ids
    assert [task["batch_position"] for task in body["tasks"]] == [0, 1, 2]
    assert {task["batch_id"] for task in body["tasks"]} == {body["id"]}
    assert {
        task["queue_reason"] for task in body["tasks"]
    } == {"waiting_for_any_device"}
    assert len({task["id"] for task in body["tasks"]}) == 3

    listed = authenticated_client.get(
        "/api/v1/tasks",
        params={"search": body["id"]},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 3
    assert {
        task["display_task_id"] for task in listed.json()["items"]
    } == {body["id"]}
    assert {
        task["source_type"] for task in listed.json()["items"]
    } == {"multi_cases"}
    runtime = authenticated_client.get(
        f"/api/v1/tasks/{body['tasks'][0]['id']}/runtime"
    )
    assert runtime.status_code == 200
    assert runtime.json()["execution_config"]["source"] == "global"
    assert runtime.json()["execution_config"]["product_id"] == "product-batch"

    with authenticated_client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(TaskBatch)) == 1
        assert db.scalar(select(func.count()).select_from(Task)) == 3
        assert db.scalar(select(func.count()).select_from(PodLease)) == 0


def test_create_batch_uses_payload_device_wait_timeout(authenticated_client):
    _configure_runner(authenticated_client)
    case_ids = [
        _create_case(authenticated_client, "等待超时一"),
        _create_case(authenticated_client, "等待超时二"),
    ]
    payload = _payload(case_ids)
    payload["device_wait_timeout_seconds"] = 45
    payload["idempotency_key"] = "batch-create-device-wait"

    response = authenticated_client.post("/api/v1/task-batches", json=payload)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["device_wait_timeout_seconds"] == 45
    runtime = authenticated_client.get(
        f"/api/v1/tasks/{body['tasks'][0]['id']}/runtime"
    )
    assert runtime.status_code == 200
    assert runtime.json()["execution_config"]["device_wait_timeout_seconds"] == 45
    with authenticated_client.app.state.session_factory() as db:
        batch = db.get(TaskBatch, body["id"])
        assert batch is not None
        assert batch.device_wait_timeout_seconds == 45


def test_create_batch_exposes_specified_pod_ids_in_runtime_config(
    authenticated_client,
):
    _configure_runner(authenticated_client)
    case_ids = [
        _create_case(authenticated_client, "指定设备一"),
        _create_case(authenticated_client, "指定设备二"),
    ]
    payload = _payload(case_ids)
    payload.update({
        "device_strategy": "specified",
        "pod_ids": ["pod-a", "pod-b"],
        "concurrency": 2,
        "idempotency_key": "batch-specified-pod-ids",
    })

    response = authenticated_client.post("/api/v1/task-batches", json=payload)

    assert response.status_code == 201, response.text
    body = response.json()
    runtime = authenticated_client.get(
        f"/api/v1/tasks/{body['tasks'][0]['id']}/runtime"
    )
    assert runtime.status_code == 200
    execution_config = runtime.json()["execution_config"]
    assert execution_config["device_strategy"] == "specified"
    assert execution_config["pod_ids"] == ["pod-a", "pod-b"]
    assert execution_config["pod_id"] is None
    with authenticated_client.app.state.session_factory() as db:
        batch = db.get(TaskBatch, body["id"])
        assert batch is not None
        assert batch.config_snapshot["device_strategy"] == "specified"
        assert batch.config_snapshot["pod_ids"] == ["pod-a", "pod-b"]
        task_config = db.get(TaskRunnerConfig, body["tasks"][0]["id"])
        assert task_config is not None
        assert task_config.config_snapshot["device_strategy"] == "specified"
        assert task_config.config_snapshot["pod_ids"] == ["pod-a", "pod-b"]


def test_create_batch_is_idempotent(authenticated_client):
    _configure_runner(authenticated_client)
    case_ids = [
        _create_case(authenticated_client, "用例一"),
        _create_case(authenticated_client, "用例二"),
    ]
    payload = _payload(case_ids)

    first = authenticated_client.post("/api/v1/task-batches", json=payload)
    second = authenticated_client.post("/api/v1/task-batches", json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert [item["id"] for item in second.json()["tasks"]] == [
        item["id"] for item in first.json()["tasks"]
    ]


def test_create_batch_rejects_invalid_specified_pod_count(authenticated_client):
    case_ids = [
        _create_case(authenticated_client, "设备一"),
        _create_case(authenticated_client, "设备二"),
    ]
    payload = _payload(case_ids)
    payload.update(
        {
            "device_strategy": "specified",
            "pod_ids": ["pod-a", "pod-b"],
            "concurrency": 1,
        }
    )

    response = authenticated_client.post("/api/v1/task-batches", json=payload)

    assert response.status_code == 422


def test_public_batch_api_rejects_test_plan_mode_without_orphan_records(
    authenticated_client,
):
    _configure_runner(authenticated_client)
    case_id = _create_case(authenticated_client, "单用例计划批次")
    payload = _payload([case_id])
    payload.update(
        {
            "selection_mode": "test_plan",
            "concurrency": 1,
            "idempotency_key": "single-plan-batch",
        }
    )

    response = authenticated_client.post(
        "/api/v1/task-batches",
        json=payload,
    )

    assert response.status_code == 422, response.text
    assert (
        response.json()["error"]["code"]
        == "test_plan_selection_requires_plan_execution"
    )
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


def test_cancel_batch_cancels_queued_children(authenticated_client):
    _configure_runner(authenticated_client)
    case_ids = [
        _create_case(authenticated_client, "取消一"),
        _create_case(authenticated_client, "取消二"),
    ]
    created = authenticated_client.post(
        "/api/v1/task-batches",
        json=_payload(case_ids),
    )
    assert created.status_code == 201

    response = authenticated_client.post(
        f"/api/v1/task-batches/{created.json()['id']}/cancel"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["execution_status"] == "cancelled"
    assert body["cancel_requested_at"] is not None
    assert {
        task["execution_status"] for task in body["tasks"]
    } == {"cancelled"}
    assert {task["verdict"] for task in body["tasks"]} == {None}
