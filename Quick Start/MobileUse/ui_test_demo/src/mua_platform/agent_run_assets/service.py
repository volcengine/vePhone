from collections.abc import Mapping
from typing import Any, Literal

from mua_platform.agent_run_assets.schemas import (
    AgentRunAssetListResponse,
    AgentRunChainAsset,
    AgentRunChainAssetDetail,
    AgentRunScriptAsset,
    AgentRunScriptAssetDetail,
)
from mua_platform.runners.universal_gateway import (
    UniversalGateway,
    UniversalRemoteError,
    UniversalRequest,
    safe_request_id,
)
from mua_platform.settings.schemas import RunnerConfig

_SERVICE = "ipaas"
_VERSION = "2023-08-01"
_AGENT_TYPE = "mua"
ScriptSearchField = Literal["name", "description", "script"]
ChainSearchField = Literal["name", "description", "nodes"]


class AgentRunAssetService:
    def __init__(self, gateway: UniversalGateway) -> None:
        self._gateway = gateway

    async def list_scripts(
        self,
        config: RunnerConfig,
        *,
        page: int,
        page_size: int,
        search: str | None,
        search_field: ScriptSearchField,
    ) -> AgentRunAssetListResponse[AgentRunScriptAsset]:
        body = _list_body(page, page_size, search, search_field)
        response = await self._gateway.invoke_read(
            config,
            UniversalRequest(_SERVICE, "ListAgentRunScript", _VERSION, "GET", body),
        )
        return AgentRunAssetListResponse[AgentRunScriptAsset](
            items=[_script_summary(item, response) for item in _result_list(response)],
            total=_result_total(response),
            page=page,
            page_size=page_size,
        )

    async def get_script(
        self,
        config: RunnerConfig,
        script_id: int,
    ) -> AgentRunScriptAssetDetail:
        response = await self._gateway.invoke_read(
            config,
            UniversalRequest(
                _SERVICE,
                "GetAgentRunScript",
                _VERSION,
                "GET",
                {"AgentType": _AGENT_TYPE, "ScriptId": script_id},
            ),
        )
        return _script_detail(response)

    async def list_chains(
        self,
        config: RunnerConfig,
        *,
        page: int,
        page_size: int,
        search: str | None,
        search_field: ChainSearchField,
    ) -> AgentRunAssetListResponse[AgentRunChainAsset]:
        body = _list_body(page, page_size, search, search_field)
        response = await self._gateway.invoke_read(
            config,
            UniversalRequest(_SERVICE, "ListAgentRunChain", _VERSION, "GET", body),
        )
        return AgentRunAssetListResponse[AgentRunChainAsset](
            items=[_chain_summary(item, response) for item in _result_list(response)],
            total=_result_total(response),
            page=page,
            page_size=page_size,
        )

    async def get_chain(
        self,
        config: RunnerConfig,
        chain_id: int,
    ) -> AgentRunChainAssetDetail:
        response = await self._gateway.invoke_read(
            config,
            UniversalRequest(
                _SERVICE,
                "GetAgentRunChain",
                _VERSION,
                "GET",
                {"AgentType": _AGENT_TYPE, "ChainId": chain_id},
            ),
        )
        return _chain_detail(response)


def _list_body(
    page: int,
    page_size: int,
    search: str | None,
    search_field: str,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "AgentType": _AGENT_TYPE,
        "Status": 1,
        "Limit": page_size,
        "Offset": page,
    }
    keyword = search.strip() if search else ""
    if keyword:
        body["SearchField"] = search_field
        body["Keyword"] = keyword
    return body


def _result_object(response: Mapping[str, Any]) -> Mapping[str, Any]:
    if "Result" not in response:
        return response
    result = response.get("Result")
    if not isinstance(result, Mapping):
        raise _invalid_response(response)
    return result


def _result_list(response: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    result = _result_object(response)
    items = result.get("List")
    if not isinstance(items, list):
        raise _invalid_response(response)
    if any(not isinstance(item, Mapping) for item in items):
        raise _invalid_response(response)
    return items


def _result_total(response: Mapping[str, Any]) -> int | None:
    total = _result_object(response).get("Total")
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise _invalid_response(response)
    return total


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _positive_int(value: Any, response: Mapping[str, Any]) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise _invalid_response(response)
    return value


def _script_summary(
    item: Mapping[str, Any],
    response: Mapping[str, Any],
) -> AgentRunScriptAsset:
    script_id = _positive_int(item.get("ScriptId"), response)
    return AgentRunScriptAsset(
        script_id=script_id,
        name=_text(item.get("Name")) or str(script_id),
        description=_text(item.get("Description")),
        resolution=_text(item.get("Resolution")),
        status=_int(item.get("Status")) or 0,
        created_at=item.get("CreatedAt"),
        updated_at=item.get("UpdatedAt"),
    )


def _script_detail(response: Mapping[str, Any]) -> AgentRunScriptAssetDetail:
    item = _result_object(response)
    return AgentRunScriptAssetDetail(
        **_script_summary(item, response).model_dump(),
        script=_text(item.get("Script")),
    )


def _chain_summary(
    item: Mapping[str, Any],
    response: Mapping[str, Any],
) -> AgentRunChainAsset:
    chain_id = _positive_int(item.get("ChainId"), response)
    return AgentRunChainAsset(
        chain_id=chain_id,
        name=_text(item.get("Name")) or str(chain_id),
        description=_text(item.get("Description")),
        status=_int(item.get("Status")) or 0,
        created_at=item.get("CreatedAt"),
        updated_at=item.get("UpdatedAt"),
    )


def _chain_detail(response: Mapping[str, Any]) -> AgentRunChainAssetDetail:
    item = _result_object(response)
    nodes = item.get("Nodes")
    return AgentRunChainAssetDetail(
        **_chain_summary(item, response).model_dump(),
        nodes=nodes if isinstance(nodes, list) else None,
    )


def _invalid_response(response: Mapping[str, Any]) -> UniversalRemoteError:
    metadata = response.get("ResponseMetadata")
    request_id = (
        safe_request_id(metadata.get("RequestId"))
        if isinstance(metadata, Mapping)
        else None
    )
    return UniversalRemoteError(
        "response_invalid",
        request_id,
        retryable=False,
        response_received=True,
    )
