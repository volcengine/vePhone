from fastapi import APIRouter, Query, Request, status

from mua_platform.api.deps import CsrfSession, CurrentBusiness, CurrentUser, Database
from mua_platform.api.errors import api_error
from mua_platform.business.schemas import (
    BusinessSpaceCreate,
    BusinessSpaceListResponse,
    BusinessSpaceResponse,
    BusinessSpaceUpdate,
)
from mua_platform.business.service import BusinessSpaceService
from mua_platform.pods.repository import PodRepository
from mua_platform.pods.service import PodDiscoveryError, PodPoolService
from mua_platform.settings.repository import SettingRepository
from mua_platform.settings.service import RunnerSettingsValidationError, SettingsService

router = APIRouter(prefix="/api/v1/business-spaces")
_POD_POOL_IDENTITY_FIELDS = {"access_key_id", "secret_access_key", "product_id"}


@router.get("", response_model=BusinessSpaceListResponse)
def list_business_spaces(
    _user: CurrentUser,
    db: Database,
) -> BusinessSpaceListResponse:
    return BusinessSpaceListResponse(
        items=[
            BusinessSpaceResponse.model_validate(business)
            for business in BusinessSpaceService(db).list_active()
        ]
    )


@router.post(
    "",
    response_model=BusinessSpaceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_business_space(
    payload: BusinessSpaceCreate,
    request: Request,
    user: CurrentUser,
    _csrf_session: CsrfSession,
    db: Database,
) -> BusinessSpaceResponse:
    try:
        business = BusinessSpaceService(db).create(payload, created_by=user.username)
        if payload.runner_settings is not None:
            await _save_runner_settings_for_created_business(
                payload,
                request,
                db,
                user.id,
                business.id,
            )
        db.commit()
        db.refresh(business)
    except RunnerSettingsValidationError as exc:
        db.rollback()
        raise api_error(
            422,
            exc.code,
            "Runner settings are invalid",
            exc.details,
        ) from exc
    except ValueError as exc:
        db.rollback()
        if str(exc) == "business_name_exists":
            raise api_error(409, "business_name_exists", "Business name already exists") from exc
        raise
    except PodDiscoveryError as exc:
        db.rollback()
        raise api_error(
            502,
            exc.code,
            "Pod pool discovery failed",
            {"remote_request_id": exc.request_id} if exc.request_id else {},
        ) from exc
    return BusinessSpaceResponse.model_validate(business)


async def _save_runner_settings_for_created_business(
    payload: BusinessSpaceCreate,
    request: Request,
    db: Database,
    actor_user_id: int,
    business_id: str,
) -> None:
    if payload.runner_settings is None:
        return
    service = SettingsService(
        SettingRepository(
            db,
            request.app.state.setting_cipher,
            request.app.state.settings.runner_setting_defaults(),
        )
    )
    config = service.validate_runner(payload.runner_settings, business_id)
    submitted_fields = (
        payload.runner_settings.mobile_use.model_fields_set
        if payload.runner_settings.mobile_use is not None
        else set()
    )
    if config.mode == "mobile_use" and submitted_fields & _POD_POOL_IDENTITY_FIELDS:
        pool = PodPoolService(
            PodRepository(db),
            request.app.state.pod_gateway,
            request.app.state.pod_clock,
        )
        await pool.refresh(
            config,
            before_sync=lambda: service.update_runner(
                payload.runner_settings,
                actor_user_id,
                business_id,
            ),
        )
        return
    service.update_runner(payload.runner_settings, actor_user_id, business_id)


@router.get("/current", response_model=BusinessSpaceResponse)
def get_current_business_space(
    _user: CurrentUser,
    business: CurrentBusiness,
) -> BusinessSpaceResponse:
    return BusinessSpaceResponse.model_validate(business)


@router.get("/product-id-available")
def product_id_available(
    request: Request,
    db: Database,
    _user: CurrentUser,
    product_id: str = Query(min_length=1),
    business_id: str | None = Query(default=None),
) -> dict[str, bool]:
    service = SettingsService(
        SettingRepository(
            db,
            request.app.state.setting_cipher,
            request.app.state.settings.runner_setting_defaults(),
        )
    )
    return {"available": service.product_id_available(product_id, business_id)}


@router.patch("/{business_id}", response_model=BusinessSpaceResponse)
def update_business_space(
    business_id: str,
    payload: BusinessSpaceUpdate,
    _user: CurrentUser,
    _csrf_session: CsrfSession,
    db: Database,
) -> BusinessSpaceResponse:
    try:
        business = BusinessSpaceService(db).update(business_id, payload)
    except ValueError as exc:
        if str(exc) == "business_name_exists":
            raise api_error(409, "business_name_exists", "Business name already exists") from exc
        raise
    if business is None:
        raise api_error(404, "business_not_found", "Business space not found")
    return BusinessSpaceResponse.model_validate(business)


@router.post("/{business_id}/archive", response_model=BusinessSpaceResponse)
def archive_business_space(
    business_id: str,
    _user: CurrentUser,
    _csrf_session: CsrfSession,
    db: Database,
) -> BusinessSpaceResponse:
    try:
        business = BusinessSpaceService(db).archive(business_id)
    except ValueError as exc:
        if str(exc) == "default_business_cannot_archive":
            raise api_error(
                409,
                "default_business_cannot_archive",
                "Default business cannot be archived",
            ) from exc
        raise
    if business is None:
        raise api_error(404, "business_not_found", "Business space not found")
    return BusinessSpaceResponse.model_validate(business)
