from datetime import UTC, datetime

from cua_platform.pods.models import DiscoveredPod


COMPUTER_USE_STREAM_CONFIG = {
    "access_key_id": "AKLT00000000WXYZ",
    "secret_access_key": "long-term-secret-value",
    "account_id": "2100000000000000000",
}


class FakeStreamTokenGateway:
    def __init__(self):
        self.calls = []

    async def create_session(self, config, *, ecsid: str):
        self.calls.append(
            {
                "account_id": config.account_id,
                "ecsid": ecsid,
            }
        )
        return {
            "ViewerUrl": "https://agent.example.com:8911/novnc/view?sid=sid-1",
            "WebsocketUrl": "wss://agent.example.com:8911/novnc/ws?sid=sid-1",
            "HttpViewerUrl": "http://agent.example.com:8910/novnc/view?sid=sid-1",
            "WsWebsocketUrl": "ws://agent.example.com:8910/novnc/ws?sid=sid-1",
            "ExpiresAt": 1781599999,
        }


def _add_pod(
    client,
    *,
    account_id: str = "2100000000000000000",
    ecsid: str = "i-node123",
    status_code: int = 2,
    status_name: str = "已在线",
) -> None:
    with client.app.state.session_factory() as db:
        db.add(
            DiscoveredPod(
                id=f"{account_id}:{ecsid}",
                product_id=account_id,
                pod_id=ecsid,
                pod_name="测试节点",
                pod_status_code=status_code,
                stream_status=2,
                status_name=status_name,
                discovery_state="active",
                last_seen_at=datetime.now(UTC),
            )
        )
        db.commit()


def test_pod_stream_session_returns_novnc_session(authenticated_client):
    gateway = FakeStreamTokenGateway()
    authenticated_client.app.state.stream_token_gateway = gateway
    configured = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mobile_use", "mobile_use": COMPUTER_USE_STREAM_CONFIG},
    )
    assert configured.status_code == 200
    _add_pod(authenticated_client)

    response = authenticated_client.post("/api/v1/pod-pool/i-node123/stream-session")

    assert response.status_code == 200
    body = response.json()
    assert body.pop("proxy_viewer_url").startswith("/novnc/view?sid=")
    assert body == {
        "account_id": "2100000000000000000",
        "ecsid": "i-node123",
        "viewer_url": "https://agent.example.com:8911/novnc/view?sid=sid-1",
        "websocket_url": "wss://agent.example.com:8911/novnc/ws?sid=sid-1",
        "http_viewer_url": "http://agent.example.com:8910/novnc/view?sid=sid-1",
        "ws_websocket_url": "ws://agent.example.com:8910/novnc/ws?sid=sid-1",
        "expires_at": 1781599999,
    }
    assert gateway.calls == [
        {
            "account_id": "2100000000000000000",
            "ecsid": "i-node123",
        }
    ]
    assert "long-term-secret-value" not in response.text


def test_runner_settings_requires_account_id(authenticated_client):
    response = authenticated_client.put(
        "/api/v1/settings/runner",
        json={
            "mode": "mobile_use",
            "mobile_use": {
                "access_key_id": "AKLT00000000WXYZ",
                "secret_access_key": "long-term-secret-value",
            },
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "runner_settings_incomplete"
    assert response.json()["error"]["details"] == {
        "missing_fields": ["account_id"]
    }


def test_pod_stream_session_rejects_unknown_pod(authenticated_client):
    authenticated_client.app.state.stream_token_gateway = FakeStreamTokenGateway()
    configured = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mobile_use", "mobile_use": COMPUTER_USE_STREAM_CONFIG},
    )
    assert configured.status_code == 200

    response = authenticated_client.post("/api/v1/pod-pool/missing_pod/stream-session")

    assert response.status_code == 404


def test_pod_stream_session_rejects_unstreamable_node_before_remote_call(authenticated_client):
    gateway = FakeStreamTokenGateway()
    authenticated_client.app.state.stream_token_gateway = gateway
    configured = authenticated_client.put(
        "/api/v1/settings/runner",
        json={"mode": "mobile_use", "mobile_use": COMPUTER_USE_STREAM_CONFIG},
    )
    assert configured.status_code == 200
    _add_pod(
        authenticated_client,
        ecsid="i-upgrade-failed",
        status_code=6,
        status_name="升级失败",
    )

    response = authenticated_client.post("/api/v1/pod-pool/i-upgrade-failed/stream-session")

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "pod_unavailable"
    assert body["error"]["message"] == "Pod is not available for streaming"
    assert body["error"]["details"] == {
        "pod_status_code": 6,
        "status_name": "升级失败",
    }
    assert gateway.calls == []
