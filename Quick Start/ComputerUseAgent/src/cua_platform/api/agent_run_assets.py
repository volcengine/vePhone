from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query, Request
from sqlalchemy.orm import Session

from cua_platform.agent_run_assets.schemas import (
    AgentRunAssetListResponse,
    AgentRunChainAsset,
    AgentRunChainAssetDetail,
    AgentRunScriptAsset,
    AgentRunScriptAssetDetail,
)
from cua_platform.agent_run_assets.service import AgentRunAssetService
from cua_platform.api.deps import CurrentBusiness, CurrentUser, Database
from cua_platform.api.errors import api_error
from cua_platform.runners.universal_gateway import UniversalRemoteError
from cua_platform.settings.repository import SettingRepository
from cua_platform.settings.schemas import RunnerExecutionSettingsError
from cua_platform.settings.service import SettingsService

router = APIRouter(prefix="/api/v1")


@router.get(
    "/agent-run-scripts",
    response_model=AgentRunAssetListResponse[AgentRunScriptAsset],
)
async def list_agent_run_scripts(
    request: Request,
    db: Database,
    business: CurrentBusiness,
    _user: CurrentUser,
    search: str | None = Query(default=None, max_length=200),
    search_field: Literal["name", "description", "script"] = "name",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    config = _runner_config(request, db, business.id)
    try:
        _ensure_remote_config(config)
        return await _service(request).list_scripts(
            config,
            page=page,
            page_size=page_size,
            search=search,
            search_field=search_field,
        )
    except RunnerExecutionSettingsError as exc:
        raise _settings_error(exc) from exc
    except UniversalRemoteError as exc:
        raise _remote_error(exc) from exc


@router.get(
    "/agent-run-scripts/{script_id}",
    response_model=AgentRunScriptAssetDetail,
)
async def get_agent_run_script(
    script_id: Annotated[int, Path(ge=1)],
    request: Request,
    db: Database,
    business: CurrentBusiness,
    _user: CurrentUser,
):
    config = _runner_config(request, db, business.id)
    try:
        _ensure_remote_config(config)
        return await _service(request).get_script(config, script_id)
    except RunnerExecutionSettingsError as exc:
        raise _settings_error(exc) from exc
    except UniversalRemoteError as exc:
        raise _remote_error(exc) from exc


@router.get(
    "/agent-run-chains",
    response_model=AgentRunAssetListResponse[AgentRunChainAsset],
)
async def list_agent_run_chains(
    request: Request,
    db: Database,
    business: CurrentBusiness,
    _user: CurrentUser,
    search: str | None = Query(default=None, max_length=200),
    search_field: Literal["name", "description", "nodes"] = "name",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    config = _runner_config(request, db, business.id)
    try:
        _ensure_remote_config(config)
        return await _service(request).list_chains(
            config,
            page=page,
            page_size=page_size,
            search=search,
            search_field=search_field,
        )
    except RunnerExecutionSettingsError as exc:
        raise _settings_error(exc) from exc
    except UniversalRemoteError as exc:
        raise _remote_error(exc) from exc


@router.get(
    "/agent-run-chains/{chain_id}",
    response_model=AgentRunChainAssetDetail,
)
async def get_agent_run_chain(
    chain_id: Annotated[int, Path(ge=1)],
    request: Request,
    db: Database,
    business: CurrentBusiness,
    _user: CurrentUser,
):
    config = _runner_config(request, db, business.id)
    try:
        _ensure_remote_config(config)
        return await _service(request).get_chain(config, chain_id)
    except RunnerExecutionSettingsError as exc:
        raise _settings_error(exc) from exc
    except UniversalRemoteError as exc:
        raise _remote_error(exc) from exc


def _runner_config(request: Request, db: Session, business_id: str):
    return SettingsService(
        SettingRepository(
            db,
            request.app.state.setting_cipher,
            request.app.state.settings.runner_setting_defaults(),
        )
    ).get_runner_config(business_id)


def _service(request: Request) -> AgentRunAssetService:
    return AgentRunAssetService(request.app.state.agent_run_asset_gateway)


def _ensure_remote_config(config) -> None:
    if config.mode != "mobile_use":
        raise RunnerExecutionSettingsError(["mode"])
    config.execution_snapshot()


def _settings_error(exc: RunnerExecutionSettingsError):
    return api_error(
        409,
        "runner_execution_settings_incomplete",
        "Runner execution settings are incomplete",
        {"missing_fields": exc.missing_fields},
    )


def _remote_error(exc: UniversalRemoteError):
    status_by_code = {
        "credentials_invalid": 401,
        "permission_denied": 403,
        "invalid_parameter": 400,
        "rate_limited": 429,
        "remote_timeout": 504,
        "remote_unavailable": 502,
        "pod_not_found": 404,
        "pod_unavailable": 409,
        "request_rejected": 409,
        "response_invalid": 502,
    }
    return api_error(
        status_by_code.get(exc.code, 502),
        exc.code,
        "Agent run asset request failed",
        {"request_id": exc.request_id} if exc.request_id else None,
    )
