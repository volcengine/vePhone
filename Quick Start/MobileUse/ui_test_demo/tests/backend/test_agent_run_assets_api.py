from collections.abc import Mapping

from mua_platform.runners.universal_gateway import (
    UniversalRemoteError,
    UniversalRequest,
)
from mua_platform.settings.schemas import RunnerConfig


class RecordingAssetGateway:
    def __init__(self, response: Mapping[str, object]) -> None:
        self.response = response
        self.requests: list[UniversalRequest] = []
        self.configs: list[RunnerConfig] = []

    async def invoke_read(
        self,
        config: RunnerConfig,
        request: UniversalRequest,
        *,
        _trace_key: str | None = None,
    ) -> Mapping[str, object]:
        self.configs.append(config)
        self.requests.append(request)
        return self.response


class FailingAssetGateway:
    async def invoke_read(
        self,
        _config: RunnerConfig,
        _request: UniversalRequest,
        *,
        _trace_key: str | None = None,
    ) -> Mapping[str, object]:
        raise UniversalRemoteError(
            "permission_denied",
            "req-denied",
            retryable=False,
            response_received=True,
        )


def _configure_mobile_runner(authenticated_client) -> None:
    response = authenticated_client.put(
        "/api/v1/settings/runner",
        json={
            "mode": "mobile_use",
            "mobile_use": {
                "access_key_id": "AKLT00000000WXYZ",
                "secret_access_key": "secret-value",
                "product_id": "product-assets",
                "tos_bucket": "assets-bucket",
                "tos_region": "cn-beijing",
            },
        },
    )
    assert response.status_code == 200, response.text


def test_list_agent_run_scripts_calls_remote_contract(authenticated_client):
    _configure_mobile_runner(authenticated_client)
    gateway = RecordingAssetGateway(
        {
            "ResponseMetadata": {"RequestId": "req-list-script"},
            "Result": {
                "Total": 1,
                "List": [
                    {
                        "ScriptId": 1001,
                        "AgentType": "mua",
                        "Name": "open-app",
                        "Description": "打开应用",
                        "Script": "tap(500,800)",
                        "Resolution": "1920x1080",
                        "Status": 1,
                        "CreatedAt": 1785738000,
                        "UpdatedAt": 1785738600,
                    }
                ],
            },
        }
    )
    authenticated_client.app.state.agent_run_asset_gateway = gateway

    response = authenticated_client.get(
        "/api/v1/agent-run-scripts?search=open&search_field=name&page=2&page_size=10"
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "items": [
            {
                "script_id": 1001,
                "name": "open-app",
                "description": "打开应用",
                "resolution": "1920x1080",
                "status": 1,
                "created_at": 1785738000,
                "updated_at": 1785738600,
            }
        ],
        "total": 1,
        "page": 2,
        "page_size": 10,
    }
    request = gateway.requests[0]
    assert (request.method, request.action, request.service, request.version) == (
        "GET",
        "ListAgentRunScript",
        "ipaas",
        "2023-08-01",
    )
    assert request.body == {
        "AgentType": "mua",
        "Status": 1,
        "SearchField": "name",
        "Keyword": "open",
        "Limit": 10,
        "Offset": 2,
    }


def test_list_agent_run_scripts_accepts_top_level_remote_list(authenticated_client):
    _configure_mobile_runner(authenticated_client)
    gateway = RecordingAssetGateway(
        {
            "Total": 1,
            "List": [
                {
                    "ScriptId": 1001,
                    "AgentType": "mua",
                    "Name": "open-app",
                    "Description": "打开应用",
                    "Script": "tap(500,800)",
                    "Resolution": "1920x1080",
                    "Status": 1,
                    "CreatedAt": 1785738000,
                    "UpdatedAt": 1785738600,
                }
            ],
        }
    )
    authenticated_client.app.state.agent_run_asset_gateway = gateway

    response = authenticated_client.get("/api/v1/agent-run-scripts")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["script_id"] == 1001


def test_get_agent_run_script_accepts_top_level_remote_detail(authenticated_client):
    _configure_mobile_runner(authenticated_client)
    gateway = RecordingAssetGateway(
        {
            "ScriptId": 1001,
            "AgentType": "mua",
            "Name": "open-app",
            "Description": "打开应用",
            "Script": "tap(500,800)",
            "Resolution": "1920x1080",
            "Status": 1,
            "CreatedAt": 1785738000,
            "UpdatedAt": 1785738600,
        }
    )
    authenticated_client.app.state.agent_run_asset_gateway = gateway

    response = authenticated_client.get("/api/v1/agent-run-scripts/1001")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["script_id"] == 1001
    assert body["script"] == "tap(500,800)"
    assert gateway.requests[0].body == {"AgentType": "mua", "ScriptId": 1001}


def test_get_agent_run_chain_returns_nodes(authenticated_client):
    _configure_mobile_runner(authenticated_client)
    gateway = RecordingAssetGateway(
        {
            "ResponseMetadata": {"RequestId": "req-get-chain"},
            "Result": {
                "ChainId": 2001,
                "AgentType": "mua",
                "Name": "login-check",
                "Description": "登录检查",
                "Nodes": [{"Id": "open", "Type": "ScriptRun"}],
                "Status": 1,
                "CreatedAt": 1785738000,
                "UpdatedAt": 1785738600,
            },
        }
    )
    authenticated_client.app.state.agent_run_asset_gateway = gateway

    response = authenticated_client.get("/api/v1/agent-run-chains/2001")

    assert response.status_code == 200, response.text
    assert response.json()["chain_id"] == 2001
    assert response.json()["nodes"] == [{"Id": "open", "Type": "ScriptRun"}]
    assert gateway.requests[0].action == "GetAgentRunChain"
    assert gateway.requests[0].body == {"AgentType": "mua", "ChainId": 2001}


def test_list_agent_run_scripts_maps_malformed_result_to_remote_error(
    authenticated_client,
):
    _configure_mobile_runner(authenticated_client)
    gateway = RecordingAssetGateway(
        {
            "ResponseMetadata": {"RequestId": "req-bad-list"},
            "Result": {"Total": 1, "List": {"ScriptId": 1001}},
        }
    )
    authenticated_client.app.state.agent_run_asset_gateway = gateway

    response = authenticated_client.get("/api/v1/agent-run-scripts")

    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "response_invalid"
    assert body["error"]["details"]["request_id"] == "req-bad-list"


def test_get_agent_run_script_maps_malformed_id_to_remote_error(
    authenticated_client,
):
    _configure_mobile_runner(authenticated_client)
    gateway = RecordingAssetGateway(
        {
            "ResponseMetadata": {"RequestId": "req-bad-detail"},
            "Result": {"Name": "missing id", "Status": 1},
        }
    )
    authenticated_client.app.state.agent_run_asset_gateway = gateway

    response = authenticated_client.get("/api/v1/agent-run-scripts/1001")

    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "response_invalid"
    assert body["error"]["details"]["request_id"] == "req-bad-detail"


def test_get_agent_run_script_rejects_non_positive_id_without_gateway_call(
    authenticated_client,
):
    _configure_mobile_runner(authenticated_client)
    gateway = RecordingAssetGateway(
        {
            "ResponseMetadata": {"RequestId": "req-should-not-call"},
            "Result": {"ScriptId": 1, "Name": "unused", "Status": 1},
        }
    )
    authenticated_client.app.state.agent_run_asset_gateway = gateway

    response = authenticated_client.get("/api/v1/agent-run-scripts/0")

    assert response.status_code == 422
    assert gateway.requests == []


def test_get_agent_run_chain_rejects_non_positive_id_without_gateway_call(
    authenticated_client,
):
    _configure_mobile_runner(authenticated_client)
    gateway = RecordingAssetGateway(
        {
            "ResponseMetadata": {"RequestId": "req-should-not-call"},
            "Result": {"ChainId": 1, "Name": "unused", "Status": 1},
        }
    )
    authenticated_client.app.state.agent_run_asset_gateway = gateway

    response = authenticated_client.get("/api/v1/agent-run-chains/-1")

    assert response.status_code == 422
    assert gateway.requests == []


def test_agent_run_asset_api_maps_remote_error(authenticated_client):
    _configure_mobile_runner(authenticated_client)
    authenticated_client.app.state.agent_run_asset_gateway = FailingAssetGateway()

    response = authenticated_client.get("/api/v1/agent-run-scripts")

    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "permission_denied"
    assert body["error"]["details"]["request_id"] == "req-denied"
