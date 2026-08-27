from datetime import UTC, datetime

from mua_platform.pods.models import DiscoveredPod
from mua_platform.pods.repository import PodRepository
from mua_platform.pods.schemas import PodDetail


MOBILE_USE_STREAM_CONFIG = {
    "access_key_id": "AKLT00000000WXYZ",
    "secret_access_key": "long-term-secret-value",
    "product_id": "prod_123",
    "account_id": "2100000000000000000",
    "sts_role_trn": "trn:iam::2100000000000000000:role/mua-stream-viewer",
}


class FakeStreamTokenGateway:
    def __init__(self):
        self.calls = []

    async def assume_role(self, config, *, pod_id: str, user_id: str):
        self.calls.append(
            {
                "account_id": config.account_id,
                "product_id": config.product_id,
                "pod_id": pod_id,
                "role_trn": config.sts_role_trn,
                "ttl": config.stream_token_ttl_seconds,
                "user_id": user_id,
            }
        )
        return {
            "AccessKeyID": "AKTP_TEMP",
            "SecretAccessKey": "temporary-secret",
            "SessionToken": "session-token",
            "CurrentTime": "2026-08-03T10:00:00+08:00",
            "ExpiredTime": "2026-08-03T10:10:00+08:00",
        }


class FakeHostActionGateway:
    def __init__(self):
        self.calls = []
        self.task_results = {
            "task-reset-pod": 10,
        }
        self.pod_online = 4
        self.omit_power_on_request_id = False

    async def reset_host(self, config, *, product_id: str, pod_id: str):
        self.calls.append(
            {
                "action": "reset",
                "product_id": product_id,
                "pod_id": pod_id,
                "config_product_id": config.product_id,
            }
        )
        return {"request_id": "req-reset-pod", "task_id": "task-reset-pod"}

    async def reboot_host(self, config, *, product_id: str, pod_id: str):
        self.calls.append(
            {
                "action": "reboot",
                "product_id": product_id,
                "pod_id": pod_id,
                "config_product_id": config.product_id,
            }
        )
        return {"request_id": f"req-reboot-pod-{pod_id}", "task_id": None}

    async def power_on_pod(self, config, *, product_id: str, pod_id: str):
        self.calls.append(
            {
                "action": "power_on",
                "product_id": product_id,
                "pod_id": pod_id,
                "config_product_id": config.product_id,
            }
        )
        return {
            "request_id": None if self.omit_power_on_request_id else f"req-power-on-{pod_id}",
            "task_id": None,
        }

    async def power_off_pod(self, config, *, product_id: str, pod_id: str):
        self.calls.append(
            {
                "action": "power_off",
                "product_id": product_id,
                "pod_id": pod_id,
                "config_product_id": config.product_id,
            }
        )
        return {"request_id": f"req-power-off-{pod_id}", "task_id": None}

    async def get_task_info(self, config, *, product_id: str, task_id: str):
        self.calls.append(
            {
                "action": "get_task_info",
                "product_id": product_id,
                "task_id": task_id,
                "config_product_id": config.product_id,
            }
        )
        result = self.task_results[task_id]
        return {
            "request_id": "req-task-info",
            "task_id": task_id,
            "task_action": "ResetPod",
            "task_result": result,
            "task_message": "done" if result == 100 else "running",
            "jobs": [{"PodId": "pod_123", "Status": result}],
        }

    async def list_pod_status(self, config, *, product_id: str, pod_id: str):
        self.calls.append(
            {
                "action": "list_pod_status",
                "product_id": product_id,
                "pod_id": pod_id,
                "config_product_id": config.product_id,
            }
        )
        return {
            "request_id": "req-list-pod",
            "pod_id": pod_id,
            "online": self.pod_online,
        }


class FakePodDetailGateway:
    def __init__(self, *, online: int | dict[str, int]):
        self.online = online
        self.calls = []

    async def list_all(self, _config):
        raise AssertionError("list_all should not be called")

    async def detail(self, config, pod_id: str):
        self.calls.append(
            {
                "product_id": config.product_id,
                "pod_id": pod_id,
            }
        )
        return PodDetail(
            product_id=config.product_id,
            pod_id=pod_id,
            pod_name=pod_id,
            pod_status_code=self.online[pod_id] if isinstance(self.online, dict) else self.online,
            stream_status=2,
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
            request_id="req-detail-pod",
        )


def _add_pod(
    client,
    *,
    product_id: str = "prod_123",
    pod_id: str = "pod_123",
    pod_status_code: int = 1,
) -> None:
    with client.app.state.session_factory() as db:
        db.add(
            DiscoveredPod(
                id=f"{product_id}:{pod_id}",
                product_id=product_id,
                pod_id=pod_id,
                pod_name="测试云机",
                pod_status_code=pod_status_code,
                stream_status=2,
                discovery_state="active",
                last_seen_at=datetime.now(UTC),
            )
        )
        db.commit()


def test_pod_stream_session_returns_web_sdk_start_config(authenticated_client):
    gateway = FakeStreamTokenGateway()
    authenticated_client.app.state.stream_token_gateway = gateway
    _add_pod(authenticated_client)
    configured = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mobile_use", "mobile_use": MOBILE_USE_STREAM_CONFIG},
    )
    assert configured.status_code == 200

    response = authenticated_client.post("/api/v1/pod-pool/pod_123/stream-session")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "account_id": "2100000000000000000",
        "product_id": "prod_123",
        "pod_id": "pod_123",
        "user_id": "mua-admin",
        "token": {
            "AccessKeyID": "AKTP_TEMP",
            "SecretAccessKey": "temporary-secret",
            "SessionToken": "session-token",
            "CurrentTime": "2026-08-03T10:00:00+08:00",
            "ExpiredTime": "2026-08-03T10:10:00+08:00",
        },
    }
    assert gateway.calls == [
        {
            "account_id": "2100000000000000000",
            "product_id": "prod_123",
            "pod_id": "pod_123",
            "role_trn": "trn:iam::2100000000000000000:role/mua-stream-viewer",
            "ttl": 600,
            "user_id": "mua-admin",
        }
    ]

    assert "long-term-secret-value" not in response.text


def test_pod_stream_session_requires_stream_settings(authenticated_client):
    _add_pod(authenticated_client)
    configured = authenticated_client.put(
        "/api/v1/settings/runner",
        json={
            "mode": "mobile_use",
            "mobile_use": {
                "access_key_id": "AKLT00000000WXYZ",
                "secret_access_key": "long-term-secret-value",
                "product_id": "prod_123",
            },
        },
    )
    assert configured.status_code == 200

    response = authenticated_client.post("/api/v1/pod-pool/pod_123/stream-session")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "stream_settings_incomplete"
    assert response.json()["error"]["details"] == {
        "missing_fields": ["account_id", "sts_role_trn"]
    }


def test_pod_stream_session_rejects_unknown_pod(authenticated_client):
    authenticated_client.app.state.stream_token_gateway = FakeStreamTokenGateway()
    configured = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mobile_use", "mobile_use": MOBILE_USE_STREAM_CONFIG},
    )
    assert configured.status_code == 200

    response = authenticated_client.post("/api/v1/pod-pool/missing_pod/stream-session")

    assert response.status_code == 404


def test_pod_host_actions_call_reset_reboot_power_on_and_power_off(authenticated_client):
    gateway = FakeHostActionGateway()
    detail_gateway = FakePodDetailGateway(online=2)
    authenticated_client.app.state.host_action_gateway = gateway
    _add_pod(authenticated_client, pod_status_code=2)
    configured = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mobile_use", "mobile_use": MOBILE_USE_STREAM_CONFIG},
    )
    assert configured.status_code == 200
    authenticated_client.app.state.pod_gateway = detail_gateway

    reset = authenticated_client.post("/api/v1/pod-pool/pod_123/reset")

    assert reset.status_code == 200
    assert reset.json() == {
        "action": "reset",
        "product_id": "prod_123",
        "pod_id": "pod_123",
        "request_id": "req-reset-pod",
        "remote_task_id": "task-reset-pod",
    }
    pool = authenticated_client.get("/api/v1/pod-pool")
    assert pool.status_code == 200
    assert pool.json()["items"][0]["active_host_action"] == {
        "action": "reset",
        "request_id": "req-reset-pod",
        "remote_task_id": "task-reset-pod",
        "status": "running",
        "task_result": None,
        "task_message": None,
    }

    rejected = authenticated_client.post("/api/v1/pod-pool/pod_123/reboot")
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "host_action_in_progress"

    gateway.task_results["task-reset-pod"] = 100
    reset_status = authenticated_client.get(
        "/api/v1/pod-pool/pod_123/host-actions/task-reset-pod"
    )
    assert reset_status.status_code == 200
    assert reset_status.json()["status"] == "succeeded"
    pool = authenticated_client.get("/api/v1/pod-pool")
    assert pool.status_code == 200
    assert pool.json()["items"][0]["active_host_action"] is None

    with authenticated_client.app.state.session_factory() as db:
        pod = db.get(DiscoveredPod, "prod_123:pod_123")
        assert pod is not None
        pod.pod_status_code = 1
        db.commit()
    detail_gateway.online = 1

    reboot = authenticated_client.post("/api/v1/pod-pool/pod_123/reboot")
    assert reboot.status_code == 200
    assert reboot.json() == {
        "action": "reboot",
        "product_id": "prod_123",
        "pod_id": "pod_123",
        "request_id": "req-reboot-pod-pod_123",
        "remote_task_id": "req-reboot-pod-pod_123",
    }
    assert gateway.calls == [
        {
            "action": "reset",
            "product_id": "prod_123",
            "pod_id": "pod_123",
            "config_product_id": "prod_123",
        },
        {
            "action": "get_task_info",
            "product_id": "prod_123",
            "task_id": "task-reset-pod",
            "config_product_id": "prod_123",
        },
        {
            "action": "reboot",
            "product_id": "prod_123",
            "pod_id": "pod_123",
            "config_product_id": "prod_123",
        },
    ]

    status = authenticated_client.get(
        "/api/v1/pod-pool/pod_123/host-actions/req-reboot-pod-pod_123"
    )
    assert status.status_code == 200
    assert status.json()["status"] == "running"
    assert status.json()["task_result"] == 10
    gateway.pod_online = 1
    status = authenticated_client.get(
        "/api/v1/pod-pool/pod_123/host-actions/req-reboot-pod-pod_123"
    )
    assert status.status_code == 200
    assert status.json() == {
        "product_id": "prod_123",
        "pod_id": "pod_123",
        "remote_task_id": "req-reboot-pod-pod_123",
        "request_id": "req-list-pod",
        "task_action": "RebootPod",
        "task_result": 100,
        "task_message": "运行中",
        "status": "succeeded",
        "jobs": [{"PodId": "pod_123", "Online": 1}],
    }
    pool = authenticated_client.get("/api/v1/pod-pool")
    assert pool.status_code == 200
    assert pool.json()["items"][0]["active_host_action"] is None

    with authenticated_client.app.state.session_factory() as db:
        pod = db.get(DiscoveredPod, "prod_123:pod_123")
        assert pod is not None
        pod.pod_status_code = 2
        db.commit()
    detail_gateway.online = 2
    gateway.pod_online = 0
    power_on = authenticated_client.post("/api/v1/pod-pool/pod_123/power-on")
    assert power_on.status_code == 200
    assert power_on.json() == {
        "action": "power_on",
        "product_id": "prod_123",
        "pod_id": "pod_123",
        "request_id": "req-power-on-pod_123",
        "remote_task_id": "req-power-on-pod_123",
    }
    power_on_status = authenticated_client.get(
        "/api/v1/pod-pool/pod_123/host-actions/req-power-on-pod_123"
    )
    assert power_on_status.status_code == 200
    assert power_on_status.json()["status"] == "running"
    gateway.pod_online = 1
    power_on_status = authenticated_client.get(
        "/api/v1/pod-pool/pod_123/host-actions/req-power-on-pod_123"
    )
    assert power_on_status.status_code == 200
    assert power_on_status.json()["status"] == "succeeded"

    gateway.pod_online = 3
    detail_gateway.online = 1
    power_off = authenticated_client.post("/api/v1/pod-pool/pod_123/power-off")
    assert power_off.status_code == 200
    assert power_off.json() == {
        "action": "power_off",
        "product_id": "prod_123",
        "pod_id": "pod_123",
        "request_id": "req-power-off-pod_123",
        "remote_task_id": "req-power-off-pod_123",
    }
    power_off_status = authenticated_client.get(
        "/api/v1/pod-pool/pod_123/host-actions/req-power-off-pod_123"
    )
    assert power_off_status.status_code == 200
    assert power_off_status.json()["status"] == "running"
    gateway.pod_online = 2
    power_off_status = authenticated_client.get(
        "/api/v1/pod-pool/pod_123/host-actions/req-power-off-pod_123"
    )
    assert power_off_status.status_code == 200
    assert power_off_status.json()["status"] == "succeeded"


def test_pod_host_actions_reject_non_running_instance(authenticated_client):
    gateway = FakeHostActionGateway()
    detail_gateway = FakePodDetailGateway(online=4)
    authenticated_client.app.state.host_action_gateway = gateway
    _add_pod(authenticated_client, pod_status_code=4)
    configured = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mobile_use", "mobile_use": MOBILE_USE_STREAM_CONFIG},
    )
    assert configured.status_code == 200
    authenticated_client.app.state.pod_gateway = detail_gateway

    reset = authenticated_client.post("/api/v1/pod-pool/pod_123/reset")
    reboot = authenticated_client.post("/api/v1/pod-pool/pod_123/reboot")

    assert reset.status_code == 409
    assert reset.json()["error"]["code"] == "pod_not_running"
    assert reboot.status_code == 409
    assert reboot.json()["error"]["code"] == "pod_not_running"
    assert gateway.calls == []


def test_pod_host_actions_enforce_action_specific_instance_status(authenticated_client):
    gateway = FakeHostActionGateway()
    detail_gateway = FakePodDetailGateway(
        online={
            "reboot-running": 1,
            "reboot-offline": 2,
            "reset-offline": 2,
            "reset-running": 1,
            "power-on-offline": 2,
            "power-on-running": 1,
            "power-off-running": 1,
            "power-off-booting": 0,
            "power-off-rebooting": 4,
            "power-off-offline": 2,
        }
    )
    authenticated_client.app.state.host_action_gateway = gateway
    configured = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mobile_use", "mobile_use": MOBILE_USE_STREAM_CONFIG},
    )
    assert configured.status_code == 200
    authenticated_client.app.state.pod_gateway = detail_gateway

    _add_pod(authenticated_client, pod_id="reboot-running", pod_status_code=1)
    _add_pod(authenticated_client, pod_id="reboot-offline", pod_status_code=2)
    _add_pod(authenticated_client, pod_id="reset-offline", pod_status_code=2)
    _add_pod(authenticated_client, pod_id="reset-running", pod_status_code=1)
    _add_pod(authenticated_client, pod_id="power-on-offline", pod_status_code=2)
    _add_pod(authenticated_client, pod_id="power-on-running", pod_status_code=1)
    _add_pod(authenticated_client, pod_id="power-off-running", pod_status_code=1)
    _add_pod(authenticated_client, pod_id="power-off-booting", pod_status_code=0)
    _add_pod(authenticated_client, pod_id="power-off-rebooting", pod_status_code=4)
    _add_pod(authenticated_client, pod_id="power-off-offline", pod_status_code=2)

    assert authenticated_client.post("/api/v1/pod-pool/reboot-running/reboot").status_code == 200
    assert authenticated_client.post("/api/v1/pod-pool/reboot-offline/reboot").status_code == 409
    assert authenticated_client.post("/api/v1/pod-pool/reset-offline/reset").status_code == 200
    assert authenticated_client.post("/api/v1/pod-pool/reset-running/reset").status_code == 409
    assert authenticated_client.post("/api/v1/pod-pool/power-on-offline/power-on").status_code == 200
    assert authenticated_client.post("/api/v1/pod-pool/power-on-running/power-on").status_code == 409
    assert authenticated_client.post("/api/v1/pod-pool/power-off-running/power-off").status_code == 200
    assert authenticated_client.post("/api/v1/pod-pool/power-off-booting/power-off").status_code == 200
    assert authenticated_client.post("/api/v1/pod-pool/power-off-rebooting/power-off").status_code == 200
    assert authenticated_client.post("/api/v1/pod-pool/power-off-offline/power-off").status_code == 409


def test_pod_host_action_generates_local_tracking_id_without_remote_request_id(
    authenticated_client,
):
    gateway = FakeHostActionGateway()
    gateway.omit_power_on_request_id = True
    detail_gateway = FakePodDetailGateway(online=2)
    authenticated_client.app.state.host_action_gateway = gateway
    _add_pod(authenticated_client, pod_status_code=2)
    configured = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mobile_use", "mobile_use": MOBILE_USE_STREAM_CONFIG},
    )
    assert configured.status_code == 200
    authenticated_client.app.state.pod_gateway = detail_gateway

    response = authenticated_client.post("/api/v1/pod-pool/pod_123/power-on")

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] is None
    assert body["remote_task_id"].startswith("local_power_on_pod_123_")


def test_pod_pool_list_clears_completed_power_on_action(authenticated_client):
    _add_pod(authenticated_client, pod_status_code=1)
    configured = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mobile_use", "mobile_use": MOBILE_USE_STREAM_CONFIG},
    )
    assert configured.status_code == 200
    with authenticated_client.app.state.session_factory() as db:
        PodRepository(db).create_host_action(
            product_id="prod_123",
            pod_id="pod_123",
            action="power_on",
            request_id=None,
            remote_task_id="local_power_on_pod_123",
        )

    pool = authenticated_client.get("/api/v1/pod-pool")

    assert pool.status_code == 200
    assert pool.json()["items"][0]["active_host_action"] is None
    with authenticated_client.app.state.session_factory() as db:
        active = PodRepository(db).get_active_host_action("prod_123", "pod_123")
        assert active is None


def test_pod_host_actions_use_detail_pod_for_submit_status(authenticated_client):
    gateway = FakeHostActionGateway()
    gateway.omit_power_on_request_id = True
    detail_gateway = FakePodDetailGateway(online=2)
    authenticated_client.app.state.host_action_gateway = gateway
    _add_pod(authenticated_client, pod_status_code=1)
    configured = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mobile_use", "mobile_use": MOBILE_USE_STREAM_CONFIG},
    )
    assert configured.status_code == 200
    authenticated_client.app.state.pod_gateway = detail_gateway

    response = authenticated_client.post("/api/v1/pod-pool/pod_123/power-on")

    assert response.status_code == 200
    assert detail_gateway.calls == [{"product_id": "prod_123", "pod_id": "pod_123"}]
    assert gateway.calls == [
        {
            "action": "power_on",
            "product_id": "prod_123",
            "pod_id": "pod_123",
            "config_product_id": "prod_123",
        }
    ]
    with authenticated_client.app.state.session_factory() as db:
        pod = db.get(DiscoveredPod, "prod_123:pod_123")
        assert pod is not None
        assert pod.pod_status_code == 2


def test_pod_host_actions_reject_using_detail_pod_status(authenticated_client):
    gateway = FakeHostActionGateway()
    detail_gateway = FakePodDetailGateway(online=1)
    authenticated_client.app.state.host_action_gateway = gateway
    _add_pod(authenticated_client, pod_status_code=2)
    configured = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mobile_use", "mobile_use": MOBILE_USE_STREAM_CONFIG},
    )
    assert configured.status_code == 200
    authenticated_client.app.state.pod_gateway = detail_gateway

    response = authenticated_client.post("/api/v1/pod-pool/pod_123/power-on")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "pod_not_running"
    assert gateway.calls == []
    with authenticated_client.app.state.session_factory() as db:
        pod = db.get(DiscoveredPod, "prod_123:pod_123")
        assert pod is not None
        assert pod.pod_status_code == 1
