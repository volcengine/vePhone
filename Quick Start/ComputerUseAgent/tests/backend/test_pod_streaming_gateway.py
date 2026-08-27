import sys
from types import SimpleNamespace

import pytest

from cua_platform.pods.streaming import VolcengineStreamTokenGateway, _session_result
from cua_platform.settings.schemas import RunnerConfig


def test_stream_session_accepts_top_level_novnc_response():
    response = {
        "ViewerUrl": "https://agent.example.com/novnc/view",
        "WebsocketUrl": "wss://agent.example.com/novnc/ws",
        "HttpViewerUrl": "http://agent.example.com/novnc/view",
        "WsWebsocketUrl": "ws://agent.example.com/novnc/ws",
        "ExpiresAt": 1786537700,
    }

    assert _session_result(response) == response


def test_stream_session_accepts_result_wrapped_novnc_response():
    result = {
        "ViewerUrl": "https://agent.example.com/novnc/view",
        "ExpiresAt": 1786537700,
    }

    assert _session_result({"Result": result}) == result


@pytest.mark.asyncio
async def test_stream_session_forwards_configured_request_headers(monkeypatch):
    captured_headers: dict[str, str] = {}

    class FakeConfiguration:
        ak = ""
        sk = ""
        region = ""
        auto_retry = True

    class FakeApiClient:
        def __init__(self, _configuration):
            pass

        def set_default_header(self, name: str, value: str) -> None:
            captured_headers[name] = value

    class FakeUniversalApi:
        def __init__(self, _api_client):
            pass

        def do_call(self, _info, body):
            assert body == {"Ecsid": "i-node"}
            return {
                "ViewerUrl": "https://agent.example.com/novnc/view",
                "ExpiresAt": 1786537700,
            }

    class FakeFlatten:
        def __init__(self, body):
            self.body = body

        def flat(self):
            return self.body

    monkeypatch.setitem(
        sys.modules,
        "volcenginesdkcore",
        SimpleNamespace(
            ApiClient=FakeApiClient,
            Configuration=FakeConfiguration,
            Flatten=FakeFlatten,
            UniversalApi=FakeUniversalApi,
            UniversalInfo=lambda **kwargs: kwargs,
        ),
    )
    config = RunnerConfig(
        mode="mobile_use",
        access_key_id="ak",
        secret_access_key="sk",
        account_id="2107192146",
        request_headers={"x-mua-test": "mua_test"},
    )

    await VolcengineStreamTokenGateway().create_session(config, ecsid="i-node")

    assert captured_headers == {"x-mua-test": "mua_test"}
