from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from mua_platform.api.deps import CsrfSession, CurrentBusiness, CurrentUser, Database
from mua_platform.api.errors import api_error
from mua_platform.pods.repository import PodRepository
from mua_platform.pods.service import PodDiscoveryError, PodPoolService
from mua_platform.runners.universal_gateway import UniversalGateway, UniversalRemoteError
from mua_platform.settings.repository import SettingRepository
from mua_platform.settings.service import SettingsService

router = APIRouter(prefix="/api/v1/pod-pool")


def _service(request: Request, db: Database) -> tuple[PodPoolService, SettingsService]:
    pool = PodPoolService(
        PodRepository(db),
        request.app.state.pod_gateway,
        request.app.state.pod_clock,
    )
    settings = SettingsService(
        SettingRepository(
            db,
            request.app.state.setting_cipher,
            request.app.state.settings.runner_setting_defaults(),
        )
    )
    return pool, settings


def _serialize(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_serialize(v) for v in value]
    if is_dataclass(value):
        return {f.name: _serialize(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    return value


def _missing_stream_settings(config) -> list[str]:
    missing = []
    if not config.access_key_id:
        missing.append("access_key_id")
    if not config.secret_access_key:
        missing.append("secret_access_key")
    if not config.product_id:
        missing.append("product_id")
    if not config.account_id:
        missing.append("account_id")
    if not config.sts_role_trn:
        missing.append("sts_role_trn")
    return missing


async def _ensure_pod_exists(pool: PodPoolService, repo: PodRepository, config, pod_id: str) -> None:
    if config.product_id is None:
        raise api_error(
            409,
            "runner_settings_incomplete",
            "Runner settings are incomplete",
        )
    if repo.get(config.product_id, pod_id) is not None:
        return
    try:
        await pool.refresh(config)
    except PodDiscoveryError as exc:
        raise api_error(
            502,
            exc.code,
            "Pod pool discovery failed",
            {"remote_request_id": exc.request_id} if exc.request_id else {},
        ) from exc
    if repo.get(config.product_id, pod_id) is None:
        raise HTTPException(status_code=404, detail="pod_not_found")


@router.get("")
def list_pod_pool(
    request: Request,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
) -> dict:
    pool, settings = _service(request, db)
    try:
        snapshot = pool.list_cached(settings.get_runner_config(business.id))
    except ValueError as exc:
        raise api_error(
            409,
            "runner_settings_incomplete",
            "Runner settings are incomplete",
        ) from exc
    return _serialize(snapshot)


@router.get("/{pod_id}")
async def get_pod_detail(
    pod_id: str,
    request: Request,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
) -> dict:
    pool, settings = _service(request, db)
    repo = PodRepository(db)
    try:
        config = settings.get_runner_config(business.id)
    except ValueError as exc:
        raise api_error(
            409,
            "runner_settings_incomplete",
            "Runner settings are incomplete",
        ) from exc
    existing = repo.get(config.product_id, pod_id)
    if existing is None:
        try:
            await pool.refresh(config)
        except PodDiscoveryError as exc:
            raise api_error(
                502,
                exc.code,
                "Pod pool discovery failed",
                {"remote_request_id": exc.request_id} if exc.request_id else {},
            ) from exc
        existing = repo.get(config.product_id, pod_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="pod_not_found")
    try:
        detail = await repo.fetch_detail(
            request.app.state.pod_gateway,
            config,
            config.product_id,
            pod_id,
        )
    except UniversalRemoteError as exc:
        cached = repo.get_detail(config.product_id, pod_id)
        if cached[1] is not None:
            return _serialize(cached[1])
        raise api_error(
            502,
            exc.code or "pod_detail_failed",
            "Pod detail request failed",
            {"remote_request_id": exc.request_id} if exc.request_id else {},
        ) from exc
    return _serialize(detail)


@router.post("/refresh")
async def refresh_pod_pool(
    request: Request,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
    _csrf_session: CsrfSession,
) -> dict:
    pool, settings = _service(request, db)
    try:
        snapshot = await pool.refresh(settings.get_runner_config(business.id))
    except ValueError as exc:
        raise api_error(
            409,
            "runner_settings_incomplete",
            "Runner settings are incomplete",
        ) from exc
    except PodDiscoveryError as exc:
        raise api_error(
            502,
            exc.code,
            "Pod pool discovery failed",
            {"remote_request_id": exc.request_id} if exc.request_id else {},
        ) from exc
    return _serialize(snapshot)


@router.post("/{pod_id}/stream-session")
async def create_pod_stream_session(
    pod_id: str,
    request: Request,
    db: Database,
    user: CurrentUser,
    business: CurrentBusiness,
    _csrf_session: CsrfSession,
) -> dict:
    pool, settings = _service(request, db)
    repo = PodRepository(db)
    try:
        config = settings.get_runner_config(business.id)
    except ValueError as exc:
        raise api_error(
            409,
            "runner_settings_incomplete",
            "Runner settings are incomplete",
        ) from exc

    missing_fields = _missing_stream_settings(config)
    if missing_fields:
        raise api_error(
            409,
            "stream_settings_incomplete",
            "Stream settings are incomplete",
            {"missing_fields": missing_fields},
        )

    await _ensure_pod_exists(pool, repo, config, pod_id)
    user_id = f"mua-{user.username}"
    try:
        token = await request.app.state.stream_token_gateway.assume_role(
            config,
            pod_id=pod_id,
            user_id=user_id,
        )
    except UniversalRemoteError as exc:
        raise api_error(
            502,
            exc.code or "stream_token_failed",
            "Stream token request failed",
            {"remote_request_id": exc.request_id} if exc.request_id else {},
        ) from exc

    return {
        "account_id": config.account_id,
        "product_id": config.product_id,
        "pod_id": pod_id,
        "user_id": user_id,
        "token": token,
    }


@router.post("/{pod_id}/reset")
async def reset_pod(
    pod_id: str,
    request: Request,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
    _csrf_session: CsrfSession,
) -> dict:
    return await _run_host_action(
        "reset",
        pod_id=pod_id,
        request=request,
        db=db,
        business_id=business.id,
    )


@router.post("/{pod_id}/reboot")
async def reboot_pod(
    pod_id: str,
    request: Request,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
    _csrf_session: CsrfSession,
) -> dict:
    return await _run_host_action(
        "reboot",
        pod_id=pod_id,
        request=request,
        db=db,
        business_id=business.id,
    )


@router.post("/{pod_id}/power-on")
async def power_on_pod(
    pod_id: str,
    request: Request,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
    _csrf_session: CsrfSession,
) -> dict:
    return await _run_host_action(
        "power_on",
        pod_id=pod_id,
        request=request,
        db=db,
        business_id=business.id,
    )


@router.post("/{pod_id}/power-off")
async def power_off_pod(
    pod_id: str,
    request: Request,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
    _csrf_session: CsrfSession,
) -> dict:
    return await _run_host_action(
        "power_off",
        pod_id=pod_id,
        request=request,
        db=db,
        business_id=business.id,
    )


@router.get("/{pod_id}/host-actions/{remote_task_id}")
async def get_pod_host_action(
    pod_id: str,
    remote_task_id: str,
    request: Request,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
) -> dict:
    pool, settings = _service(request, db)
    repo = PodRepository(db)
    try:
        config = settings.get_runner_config(business.id)
    except ValueError as exc:
        raise api_error(
            409,
            "runner_settings_incomplete",
            "Runner settings are incomplete",
        ) from exc
    if config.product_id is None:
        raise api_error(
            409,
            "runner_settings_incomplete",
            "Runner settings are incomplete",
        )
    await _ensure_pod_exists(pool, repo, config, pod_id)
    gateway = getattr(request.app.state, "host_action_gateway", None) or UniversalGateway()
    active = repo.get_active_host_action(config.product_id, pod_id)
    if (
        active is not None
        and active.remote_task_id == remote_task_id
        and active.action in _LIST_POD_TRACKED_ACTIONS
    ):
        return await _get_list_pod_action_status(
            gateway,
            repo,
            config,
            action=active.action,
            pod_id=pod_id,
            remote_task_id=remote_task_id,
        )
    try:
        remote = await gateway.get_task_info(
            config,
            product_id=config.product_id,
            task_id=remote_task_id,
        )
    except UniversalRemoteError as exc:
        raise api_error(
            502,
            exc.code,
            "Host action status request failed",
            {"remote_request_id": exc.request_id} if exc.request_id else {},
        ) from exc
    task_result = _remote_int(remote, "task_result")
    status = _host_task_status(task_result)
    repo.update_host_action_status(
        product_id=config.product_id,
        pod_id=pod_id,
        remote_task_id=remote_task_id,
        request_id=_remote_value(remote, "request_id"),
        status=status,
        task_result=task_result,
        task_message=_remote_value(remote, "task_message"),
    )
    return {
        "product_id": config.product_id,
        "pod_id": pod_id,
        "remote_task_id": remote_task_id,
        "request_id": _remote_value(remote, "request_id"),
        "task_action": _remote_value(remote, "task_action"),
        "task_result": task_result,
        "task_message": _remote_value(remote, "task_message"),
        "status": status,
        "jobs": _remote_jobs(remote),
    }


async def _run_host_action(
    action: str,
    *,
    pod_id: str,
    request: Request,
    db: Database,
    business_id: str,
) -> dict:
    pool, settings = _service(request, db)
    repo = PodRepository(db)
    try:
        config = settings.get_runner_config(business_id)
    except ValueError as exc:
        raise api_error(
            409,
            "runner_settings_incomplete",
            "Runner settings are incomplete",
        ) from exc
    if config.product_id is None:
        raise api_error(
            409,
            "runner_settings_incomplete",
            "Runner settings are incomplete",
        )
    await _ensure_pod_exists(pool, repo, config, pod_id)
    active = repo.get_active_host_action(config.product_id, pod_id)
    if active is not None:
        raise api_error(
            409,
            "host_action_in_progress",
            "Host action is already in progress",
            {
                "action": active.action,
                "remote_task_id": active.remote_task_id,
            },
        )
    gateway = getattr(request.app.state, "host_action_gateway", None) or UniversalGateway()
    try:
        pod_detail = await repo.fetch_detail(
            request.app.state.pod_gateway,
            config,
            config.product_id,
            pod_id,
        )
    except UniversalRemoteError as exc:
        raise api_error(
            502,
            exc.code,
            "Pod detail request failed",
            {"remote_request_id": exc.request_id} if exc.request_id else {},
        ) from exc
    if not _action_allowed(action, pod_detail.pod_status_code):
        raise api_error(
            409,
            "pod_not_running",
            "Pod is not running",
            {"pod_status_code": pod_detail.pod_status_code},
        )
    try:
        if action == "reset":
            remote = await gateway.reset_host(
                config,
                product_id=config.product_id,
                pod_id=pod_id,
            )
        elif action == "reboot":
            remote = await gateway.reboot_host(
                config,
                product_id=config.product_id,
                pod_id=pod_id,
            )
        elif action == "power_on":
            remote = await gateway.power_on_pod(
                config,
                product_id=config.product_id,
                pod_id=pod_id,
            )
        elif action == "power_off":
            remote = await gateway.power_off_pod(
                config,
                product_id=config.product_id,
                pod_id=pod_id,
            )
        else:
            raise ValueError(f"unsupported_host_action:{action}")
    except UniversalRemoteError as exc:
        raise api_error(
            502,
            exc.code,
            "Host action request failed",
            {"remote_request_id": exc.request_id} if exc.request_id else {},
        ) from exc
    request_id = _remote_value(remote, "request_id")
    remote_task_id = _remote_value(remote, "task_id")
    if remote_task_id is None and action in _LIST_POD_TRACKED_ACTIONS:
        remote_task_id = request_id or f"local_{action}_{pod_id}_{uuid4().hex}"
    if remote_task_id is None:
        raise api_error(
            502,
            "response_invalid",
            "Host action response is invalid",
        )
    repo.create_host_action(
        product_id=config.product_id,
        pod_id=pod_id,
        action=action,
        request_id=request_id,
        remote_task_id=remote_task_id,
    )

    return {
        "action": action,
        "product_id": config.product_id,
        "pod_id": pod_id,
        "request_id": request_id,
        "remote_task_id": remote_task_id,
    }


def _remote_value(remote: object, key: str) -> str | None:
    if isinstance(remote, dict):
        value = remote.get(key)
    else:
        value = getattr(remote, key, None)
    return value if isinstance(value, str) else None


def _remote_int(remote: object, key: str) -> int | None:
    if isinstance(remote, dict):
        value = remote.get(key)
    else:
        value = getattr(remote, key, None)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


_LIST_POD_TRACKED_ACTIONS = {"reboot", "power_on", "power_off"}


async def _get_list_pod_action_status(
    gateway: object,
    repo: PodRepository,
    config: object,
    *,
    action: str,
    pod_id: str,
    remote_task_id: str,
) -> dict:
    try:
        remote = await gateway.list_pod_status(
            config,
            product_id=config.product_id,
            pod_id=pod_id,
        )
    except UniversalRemoteError as exc:
        raise api_error(
            502,
            exc.code,
            "Host action status request failed",
            {"remote_request_id": exc.request_id} if exc.request_id else {},
        ) from exc
    online = _pod_online_or_error(remote)
    repo.update_pod_status(
        product_id=config.product_id,
        pod_id=pod_id,
        pod_status_code=online,
        request_id=_remote_value(remote, "request_id"),
        checked_at=datetime.now(UTC),
    )
    status = "succeeded" if _list_pod_action_done(action, online) else "running"
    task_result = 100 if status == "succeeded" else 10
    task_message = _pod_status_message(online)
    repo.update_host_action_status(
        product_id=config.product_id,
        pod_id=pod_id,
        remote_task_id=remote_task_id,
        request_id=_remote_value(remote, "request_id"),
        status=status,
        task_result=task_result,
        task_message=task_message,
    )
    return {
        "product_id": config.product_id,
        "pod_id": pod_id,
        "remote_task_id": remote_task_id,
        "request_id": _remote_value(remote, "request_id"),
        "task_action": _pod_action_name(action),
        "task_result": task_result,
        "task_message": task_message,
        "status": status,
        "jobs": [{"PodId": pod_id, "Online": online}],
    }


def _pod_online_or_error(remote: object) -> int:
    online = _remote_int(remote, "online")
    if online not in {0, 1, 2, 3, 4}:
        raise api_error(502, "response_invalid", "Pod status response is invalid")
    return online


def _action_allowed(action: str, pod_status_code: int) -> bool:
    if action == "reboot":
        return pod_status_code == 1
    if action == "power_off":
        return pod_status_code in {0, 1, 4}
    if action in {"power_on", "reset"}:
        return pod_status_code == 2
    return False


def _list_pod_action_done(action: str, online: int) -> bool:
    if action in {"reboot", "power_on"}:
        return online == 1
    if action == "power_off":
        return online == 2
    return False


def _pod_action_name(action: str) -> str:
    return {
        "reboot": "RebootPod",
        "power_on": "PowerOnPod",
        "power_off": "PowerOffPod",
    }.get(action, action)


def _pod_status_message(online: int) -> str:
    return {
        0: "开机中",
        1: "运行中",
        2: "已关机",
        3: "关机中",
        4: "重启中",
    }.get(online, "未知")


def _remote_jobs(remote: object) -> list[dict]:
    if isinstance(remote, dict):
        value = remote.get("jobs")
    else:
        value = getattr(remote, "jobs", None)
    return [dict(item) for item in value] if isinstance(value, list) else []


def _host_task_status(task_result: object) -> str:
    if isinstance(task_result, int) and not isinstance(task_result, bool):
        if task_result == 100:
            return "succeeded"
        if task_result < 0:
            return "failed"
    return "running"
