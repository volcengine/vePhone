from datetime import timedelta
from urllib.parse import unquote

from fastapi import APIRouter, Query, Request, status

from mua_platform.api.deps import CsrfSession, CurrentBusiness, CurrentUser, Database
from mua_platform.api.errors import api_error
from mua_platform.cases.models import CASE_TEMPLATE, TestCase
from mua_platform.cases.schemas import (
    CaseBatchDeleteItem,
    CaseBatchDeleteRequest,
    CaseBatchDeleteResponse,
    CaseBoundTestPlanItem,
    CaseBoundTestPlanListResponse,
    CaseImportConfirmRequest,
    CaseImportConfirmResponse,
    CaseImportPreviewRequest,
    CaseImportPreviewResponse,
    CaseStatsResponse,
    CaseExecuteRequest,
    CreatorListResponse,
    ModuleListResponse,
    TagListResponse,
    TestCaseCreate,
    TestCaseListResponse,
    TestCaseResponse,
    TestCaseUpdate,
)
from mua_platform.cases.service import CaseService
from mua_platform.pods.repository import PodRepository
from mua_platform.pods.service import PodAllocationError, PodPoolService
from mua_platform.settings.repository import SettingRepository
from mua_platform.settings.schemas import RunnerExecutionSettingsError
from mua_platform.settings.service import SettingsService
from mua_platform.tasks.repository import SQLiteTaskRepository
from mua_platform.tasks.schemas import TaskResponse
from mua_platform.tasks.service import TaskService
from mua_platform.test_plans.service import (
    TagColorRegistryExhaustedError,
    TestPlanService,
)

router = APIRouter(prefix="/api/v1/cases")


@router.get("", response_model=TestCaseListResponse)
def list_cases(
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = Query(None),
    module: str | None = Query(None),
    tag: list[str] = Query(default_factory=list),
    automation_level: str | None = Query(None),
    created_by: str | None = Query(None),
) -> TestCaseListResponse:
    service = CaseService(db)
    items, total = service.list_cases(
        page=page,
        page_size=page_size,
        business_id=business.id,
        search=search,
        module=module,
        tags=tag,
        automation_level=automation_level,
        created_by=created_by,
    )
    return TestCaseListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TestCaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: TestCaseCreate,
    db: Database,
    user: CurrentUser,
    business: CurrentBusiness,
    _csrf_session: CsrfSession,
) -> TestCaseResponse:
    service = CaseService(db)
    try:
        case = service.create_case(
            payload,
            created_by=user.username,
            business_id=business.id,
        )
    except TagColorRegistryExhaustedError as exc:
        raise _tag_color_registry_exhausted() from exc
    return service.case_response(case)


@router.post("/import/preview", response_model=CaseImportPreviewResponse)
def preview_case_import(
    payload: CaseImportPreviewRequest,
    db: Database,
    _user: CurrentUser,
    _csrf_session: CsrfSession,
) -> CaseImportPreviewResponse:
    try:
        return CaseService(db).preview_import(payload.format, payload.content)
    except ValueError as exc:
        if str(exc) == "case_import_too_many_rows":
            raise api_error(
                400,
                "case_import_too_many_rows",
                "Case import supports at most 100 rows",
            ) from exc
        if str(exc) == "case_import_invalid_csv_header":
            raise api_error(
                400,
                "case_import_invalid_csv_header",
                "CSV header must include title, module, tags and content_markdown",
            ) from exc
        raise


@router.post("/import/file/preview", response_model=CaseImportPreviewResponse)
async def preview_case_file_import(
    request: Request,
    db: Database,
    _user: CurrentUser,
    _csrf_session: CsrfSession,
    format: str = Query("auto", pattern="^(auto|csv|markdown|excel)$"),
) -> CaseImportPreviewResponse:
    filename = unquote(request.headers.get("x-file-name", "").strip())
    if not filename:
        raise api_error(
            400,
            "case_import_file_name_required",
            "File name is required",
        )
    content = await request.body()
    try:
        return CaseService(db).preview_import_file(
            filename=filename,
            content=content,
            import_format=format,
        )
    except ValueError as exc:
        if str(exc) == "case_import_file_too_large":
            raise api_error(
                400,
                "case_import_file_too_large",
                "Import file is too large",
            ) from exc
        if str(exc) == "case_import_unsupported_format":
            raise api_error(
                400,
                "case_import_unsupported_format",
                "Unsupported import file format",
            ) from exc
        if str(exc) == "case_import_invalid_encoding":
            raise api_error(
                400,
                "case_import_invalid_encoding",
                "Import file must be UTF-8 encoded",
            ) from exc
        if str(exc) == "case_import_too_many_rows":
            raise api_error(
                400,
                "case_import_too_many_rows",
                "Case import supports at most 100 rows",
            ) from exc
        if str(exc) == "case_import_invalid_csv_header":
            raise api_error(
                400,
                "case_import_invalid_header",
                "Import file header must include title, module, tags and content_markdown",
            ) from exc
        if str(exc) in {"case_import_empty_file", "case_import_parse_failed"}:
            raise api_error(
                400,
                str(exc),
                "Import file could not be parsed",
            ) from exc
        raise


@router.post(
    "/import",
    response_model=CaseImportConfirmResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_cases(
    payload: CaseImportConfirmRequest,
    db: Database,
    user: CurrentUser,
    business: CurrentBusiness,
    _csrf_session: CsrfSession,
) -> CaseImportConfirmResponse:
    service = CaseService(db)
    try:
        imported = service.import_cases(
            payload.items,
            created_by=user.username,
            business_id=business.id,
        )
    except TagColorRegistryExhaustedError as exc:
        raise _tag_color_registry_exhausted() from exc
    return CaseImportConfirmResponse(
        created_count=len(imported),
        items=imported,
    )


@router.post("/batch-delete", response_model=CaseBatchDeleteResponse)
def batch_delete_cases(
    payload: CaseBatchDeleteRequest,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
    _csrf_session: CsrfSession,
) -> CaseBatchDeleteResponse:
    service = CaseService(db)
    items: list[CaseBatchDeleteItem] = []
    seen: set[str] = set()
    for case_id in payload.case_ids:
        if case_id in seen:
            continue
        seen.add(case_id)
        try:
            deleted = service.delete_case(case_id, business.id)
        except ValueError as exc:
            code = str(exc)
            items.append(
                CaseBatchDeleteItem(
                    case_id=case_id,
                    status="failed",
                    code=code,
                    message=_case_delete_error_message(code),
                )
            )
            continue
        if deleted:
            items.append(CaseBatchDeleteItem(case_id=case_id, status="deleted"))
        else:
            items.append(
                CaseBatchDeleteItem(
                    case_id=case_id,
                    status="failed",
                    code="case_not_found",
                    message="Test case not found",
                )
            )
    deleted_count = sum(item.status == "deleted" for item in items)
    return CaseBatchDeleteResponse(
        deleted_count=deleted_count,
        failed_count=len(items) - deleted_count,
        items=items,
    )


@router.get("/template")
def get_case_template() -> dict[str, str]:
    return {"template": CASE_TEMPLATE}


@router.get("/tags", response_model=TagListResponse)
def list_tags(
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
) -> TagListResponse:
    return TagListResponse(items=CaseService(db).list_tags(business.id))


@router.get("/modules", response_model=ModuleListResponse)
def list_modules(
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
) -> ModuleListResponse:
    return ModuleListResponse(items=CaseService(db).list_modules(business.id))


@router.get("/creators", response_model=CreatorListResponse)
def list_creators(
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
) -> CreatorListResponse:
    return CreatorListResponse(items=CaseService(db).list_creators(business.id))


@router.get("/stats", response_model=CaseStatsResponse)
def get_case_stats(
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
) -> CaseStatsResponse:
    return CaseStatsResponse(**CaseService(db).stats(business.id))


@router.get("/{case_id}", response_model=TestCaseResponse)
def get_case(
    case_id: str,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
) -> TestCaseResponse:
    service = CaseService(db)
    return service.case_response(_get_case(db, case_id, business.id))


@router.get("/{case_id}/tasks")
def list_case_tasks(
    case_id: str,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
    page: int = Query(1, ge=1),
    page_size: int = Query(5, ge=1, le=100),
) -> dict:
    _get_case(db, case_id, business.id)
    items, total = SQLiteTaskRepository(db).list_paginated(
        page=page,
        page_size=page_size,
        case_id=case_id,
        business_id=business.id,
    )
    return {
        "items": [TaskResponse.model_validate(task) for task in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/{case_id}/test-plans",
    response_model=CaseBoundTestPlanListResponse,
)
def list_case_test_plans(
    case_id: str,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
    page: int = Query(1, ge=1),
    page_size: int = Query(5, ge=1, le=20),
) -> CaseBoundTestPlanListResponse:
    _get_case(db, case_id, business.id)
    items, total = TestPlanService(db).list_bound_plans_for_case(
        case_id,
        page,
        page_size,
    )
    return CaseBoundTestPlanListResponse(
        items=[CaseBoundTestPlanItem(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/{case_id}/copy",
    response_model=TestCaseResponse,
    status_code=status.HTTP_201_CREATED,
)
def copy_case(
    case_id: str,
    db: Database,
    user: CurrentUser,
    business: CurrentBusiness,
    _csrf_session: CsrfSession,
) -> TestCaseResponse:
    service = CaseService(db)
    try:
        copied = service.copy_case(
            case_id,
            created_by=user.username,
            business_id=business.id,
        )
    except TagColorRegistryExhaustedError as exc:
        raise _tag_color_registry_exhausted() from exc
    if copied is None:
        raise api_error(404, "case_not_found", "Test case not found")
    return service.case_response(copied)


@router.put("/{case_id}", response_model=TestCaseResponse)
def update_case(
    case_id: str,
    payload: TestCaseUpdate,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
    _csrf_session: CsrfSession,
) -> TestCaseResponse:
    service = CaseService(db)
    try:
        case = service.update_case(case_id, payload, business.id)
    except TagColorRegistryExhaustedError as exc:
        raise _tag_color_registry_exhausted() from exc
    if case is None:
        raise api_error(404, "case_not_found", "Test case not found")
    return service.case_response(case)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    case_id: str,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
    _csrf_session: CsrfSession,
) -> None:
    try:
        deleted = CaseService(db).delete_case(case_id, business.id)
    except ValueError as exc:
        if str(exc) == "case_has_test_plans":
            raise api_error(
                409,
                "case_has_test_plans",
                "Test case is bound to an active test plan",
            ) from exc
        if str(exc) == "case_has_tasks":
            raise api_error(
                409,
                "case_has_tasks",
                "Test case has queued or running tasks",
            ) from exc
        raise
    if not deleted:
        raise api_error(404, "case_not_found", "Test case not found")


def _tag_color_registry_exhausted():
    return api_error(
        409,
        "tag_color_registry_exhausted",
        "No readable tag color is available",
    )


def _case_delete_error_message(code: str) -> str:
    if code == "case_has_test_plans":
        return "Test case is bound to an active test plan"
    if code == "case_has_tasks":
        return "Test case has queued or running tasks"
    return "Test case could not be deleted"


@router.post(
    "/{case_id}/execute",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def execute_case(
    case_id: str,
    payload: CaseExecuteRequest,
    request: Request,
    db: Database,
    user: CurrentUser,
    business: CurrentBusiness,
    _csrf_session: CsrfSession,
):
    case = _get_case(db, case_id, business.id)
    runner_config = SettingsService(
        SettingRepository(
            db,
            request.app.state.setting_cipher,
            request.app.state.settings.runner_setting_defaults(),
        )
    ).get_runner_config(business.id)
    try:
        snapshot = runner_config.execution_snapshot()
    except RunnerExecutionSettingsError as exc:
        db.rollback()
        raise api_error(
            409,
            "runner_execution_settings_incomplete",
            "Runner execution settings are incomplete",
            {"missing_fields": exc.missing_fields},
        ) from exc

    import uuid
    idempotency_key = payload.idempotency_key or f"exec-{uuid.uuid4().hex}"

    if payload.pod_id:
        snapshot["pod_id"] = payload.pod_id
    if payload.timeout_seconds:
        snapshot["timeout_seconds"] = payload.timeout_seconds
    snapshot["config_source"] = payload.agent_config_mode
    if payload.agent_config_mode == "custom" and payload.agent_options is not None:
        snapshot.update(
            payload.agent_options.model_dump(exclude_none=True)
        )
    if payload.agent_config_mode == "case_default" and case.default_agent_options:
        snapshot.update(case.default_agent_options)
    snapshot["business_id"] = business.id
    snapshot["business_name_snapshot"] = business.name

    pod_pool = (
        PodPoolService(
            PodRepository(db),
            request.app.state.pod_gateway,
            request.app.state.pod_clock,
            config=runner_config,
        )
        if runner_config.mode == "mobile_use"
        else None
    )
    task_service = TaskService(
        SQLiteTaskRepository(db),
        None,
        execution_timeout=timedelta(
            seconds=request.app.state.settings.task_execution_timeout_seconds
        ),
        cancel_confirm_timeout=timedelta(
            seconds=request.app.state.settings.cancel_confirm_timeout_seconds
        ),
    )
    try:
        task = await task_service.execute_case(
            case,
            case.title,
            idempotency_key,
            runner_config.mode,
            user.username,
            snapshot,
            pod_pool,
        )
    except PodAllocationError as exc:
        if exc.code == "pod_pool_discovery_failed":
            status_code = 502
            message = "Pod pool discovery failed"
        elif exc.code == "pod_not_found":
            status_code = 400
            message = "Specified pod not found"
        elif exc.code == "pod_busy":
            status_code = 409
            message = "Specified pod is busy or unavailable"
        else:
            status_code = 409
            message = "Pod allocation failed"
        raise api_error(
            status_code,
            exc.code,
            message,
            {"request_id": exc.request_id} if exc.request_id else None,
        ) from exc
    except ValueError as exc:
        if str(exc).startswith("idempotency_conflict:"):
            raise api_error(
                409,
                "idempotency_conflict",
                "Idempotency key was already used for a different request",
            ) from exc
        raise
    await request.app.state.task_worker.enqueue(task.id)
    return task


def _get_case(db: Database, case_id: str, business_id: str) -> TestCase:
    case = CaseService(db).get_case(case_id, business_id)
    if case is None:
        raise api_error(404, "case_not_found", "Test case not found")
    return case
