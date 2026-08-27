import asyncio
from collections.abc import Mapping
from typing import Protocol

from cua_platform.runners.universal_gateway import UniversalRemoteError, safe_universal_error
from cua_platform.settings.schemas import RunnerConfig

_NOVNC_SESSION_KEYS = frozenset(
    {
        "ViewerUrl",
        "WebsocketUrl",
        "HttpViewerUrl",
        "WsWebsocketUrl",
    }
)

class StreamTokenGateway(Protocol):
    async def create_session(
        self,
        config: RunnerConfig,
        *,
        ecsid: str,
    ) -> dict[str, object]: ...


class VolcengineStreamTokenGateway:
    async def create_session(
        self,
        config: RunnerConfig,
        *,
        ecsid: str,
    ) -> dict[str, object]:
        return await asyncio.to_thread(self._create_session, config, ecsid)

    def _create_session(
        self,
        config: RunnerConfig,
        ecsid: str,
    ) -> dict[str, object]:
        if not config.access_key_id or not config.secret_access_key:
            raise ValueError("stream_settings_incomplete")
        try:
            import volcenginesdkcore

            configuration = volcenginesdkcore.Configuration()
            configuration.ak = config.access_key_id
            configuration.sk = config.secret_access_key
            configuration.region = "cn-north-1"
            configuration.auto_retry = False
            api_client = volcenginesdkcore.ApiClient(configuration)
            for name, value in (config.request_headers or {}).items():
                api_client.set_default_header(name, value)
            api = volcenginesdkcore.UniversalApi(api_client)
            response = api.do_call(
                volcenginesdkcore.UniversalInfo(
                    method="POST",
                    action="CreateCuaNodeNoVNCSession",
                    service="ipaas",
                    version="2023-08-01",
                    content_type="application/json",
                ),
                volcenginesdkcore.Flatten({"Ecsid": ecsid}).flat(),
            )
        except UniversalRemoteError:
            raise
        except Exception as exc:
            raise safe_universal_error(exc) from None

        return _session_result(response)


def _session_result(response: object) -> dict[str, object]:
    if not isinstance(response, Mapping):
        raise _invalid_session_response()
    result = response.get("Result")
    if isinstance(result, Mapping):
        return dict(result)
    if any(key in response for key in _NOVNC_SESSION_KEYS):
        return dict(response)
    raise _invalid_session_response()


def _invalid_session_response() -> UniversalRemoteError:
    return UniversalRemoteError(
        "response_invalid",
        None,
        retryable=False,
        response_received=True,
    )
