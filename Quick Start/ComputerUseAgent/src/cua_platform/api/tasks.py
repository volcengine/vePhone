from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query, Request, Response, status
from sqlalchemy import select

from cua_platform.api.deps import CsrfSession, CurrentBusiness, CurrentUser, Database
from cua_platform.api.errors import api_error
from cua_platform.runners.universal_gateway import UniversalGateway
from cua_platform.settings.repository import SettingRepository
from cua_platform.settings.schemas import RunnerExecutionSettingsError
from cua_platform.settings.service import SettingsService
from cua_platform.tasks.models import Task, TaskEvent
from cua_platform.tasks.batches import TaskBatchService
from cua_platform.tasks.repository import SQLiteTaskRepository
from cua_platform.tasks.schemas import (
    TaskBatchCreateRequest,
    TaskBatchResponse,
    TaskExecutionConfig,
    TaskListResponse,
    TaskReviewRequest,
    TaskResponse,
)
from cua_platform.tasks.service import TaskService
from cua_platform.tasks.state_machine import ExecutionStatus
from cua_platform.tasks.worker import WorkerUnavailableError
from cua_platform.traces.repository import TraceRepository
from cua_platform.traces.service import TraceService

router = APIRouter(prefix="/api/v1")
testing_router = APIRouter(prefix="/api/v1/testing")


@router.post(
    "/task-batches",
    response_model=TaskBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task_batch(
    payload: TaskBatchCreateRequest,
    response: Response,
    request: Request,
    db: Database,
    user: CurrentUser,
    business: CurrentBusiness,
    _csrf_session: CsrfSession,
):
    if payload.selection_mode == "test_plan":
        raise api_error(
            422,
            "test_plan_selection_requires_plan_execution",
            "Test plan batches must be created through a plan execution",
        )
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
    snapshot["business_id"] = business.id
    snapshot["business_name_snapshot"] = business.name
    try:
        result = TaskBatchService(db).create(
            payload,
            created_by=user.username,
            business_id=business.id,
            runner_type=runner_config.mode,
            config_snapshot=snapshot,
            device_wait_timeout_seconds=(
                payload.device_wait_timeout_seconds
                or request.app.state.settings.device_wait_timeout_seconds
            ),
        )
    except ValueError as exc:
        if str(exc).startswith("batch_cases_not_found:"):
            missing = str(exc).partition(":")[2].split(",")
            raise api_error(
                404,
                "batch_cases_not_found",
                "One or more test cases were not found",
                {"case_ids": missing},
            ) from exc
        if str(exc).startswith("idempotency_conflict:"):
            raise api_error(
                409,
                "idempotency_conflict",
                "Idempotency key was already used for a different request",
            ) from exc
        raise
    if result.disposition == "existing":
        response.status_code = status.HTTP_200_OK
    else:
        schedule_batches = getattr(request.app.state, "schedule_batches", None)
        if schedule_batches is not None:
            await schedule_batches()
    return result.batch


@router.post(
    "/task-batches/{batch_id}/cancel",
    response_model=TaskBatchResponse,
)
async def cancel_task_batch(
    batch_id: str,
    request: Request,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
    _csrf_session: CsrfSession,
):
    try:
        result = TaskBatchService(db).cancel(
            batch_id,
            datetime.now(UTC),
            business_id=business.id,
        )
    except ValueError as exc:
        if str(exc).startswith("task_batch_not_found:"):
            raise api_error(
                404,
                "task_batch_not_found",
                "Task batch not found",
            ) from exc
        raise
    for task_id in result.running_task_ids:
        await request.app.state.task_worker.enqueue(task_id)
    return result.batch


@router.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    created_by: str | None = Query(None, alias="operator"),
    verdict: str | None = Query(None),
    review_result: str | None = Query(None),
    search: str | None = Query(None),
    created_after: datetime | None = Query(None),
) -> TaskListResponse:
    status_filter = _optional_filter(status_filter)
    created_by = _optional_filter(created_by)
    verdict = _optional_filter(verdict)
    review_result = _optional_filter(review_result)
    search = _optional_filter(search)
    if verdict == "stopped":
        status_filter = ExecutionStatus.CANCELLED.value
        verdict = None
    items, total = SQLiteTaskRepository(db).list_paginated(
        page=page,
        page_size=page_size,
        created_by=created_by,
        status=status_filter,
        verdict=verdict,
        review_result=review_result,
        search=search,
        created_after=created_after,
        business_id=business.id,
    )
    return TaskListResponse(
        items=[TaskResponse.model_validate(task) for task in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/tasks/stats")
def get_task_stats(
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
) -> dict[str, int]:
    return SQLiteTaskRepository(db).stats(business.id)


@router.get("/tasks/operators")
def list_task_operators(
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
) -> dict[str, list[str]]:
    return {"items": SQLiteTaskRepository(db).list_operators(business.id)}


@router.put("/tasks/{task_id}/review", response_model=TaskResponse)
def review_task(
    task_id: str,
    payload: TaskReviewRequest,
    db: Database,
    user: CurrentUser,
    business: CurrentBusiness,
    _csrf_session: CsrfSession,
) -> Task:
    existing = SQLiteTaskRepository(db).get(task_id, business.id)
    if existing is None:
        raise api_error(404, "task_not_found", "Task not found")
    try:
        return SQLiteTaskRepository(db).review_task(
            task_id,
            review_result=payload.review_result,
            reviewed_by=user.username,
            reviewed_at=datetime.now(UTC),
            review_note=payload.review_note,
        )
    except ValueError as exc:
        if str(exc).startswith("task_not_found:"):
            raise api_error(404, "task_not_found", "Task not found") from exc
        if str(exc).startswith("task_not_reviewable:"):
            raise api_error(
                409,
                "task_not_reviewable",
                "Task is not ready for manual review",
            ) from exc
        raise


@router.get("/tasks/{task_id}/runtime")
async def get_task_runtime(
    task_id: str,
    request: Request,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
) -> dict:
    task = _get_task(db, task_id, business.id)
    response = {
        "task": TaskResponse.model_validate(task).model_dump(mode="json"),
        "current_step": None,
        "thread_groups": [],
        "thread_steps": [],
        "trace": TraceService(TraceRepository(db))
        .get(task_id, "tree", True)
        .model_dump(mode="json"),
        "result": {
            "summary": task.result_summary,
            "evidence": task.result_evidence or [],
            "recording_url": task.recording_url,
            "assets": _filter_result_assets_for_run(
                task.result_assets or {},
                task.remote_run_id,
            ),
        },
        "execution_config": TaskExecutionConfig.model_validate(
            task.execution_config
        ).model_dump(mode="json"),
        "errors": {},
    }
    _merge_local_runtime_assets(response, task.result_assets or {})
    if task.runner_type != "mobile_use" or not task.remote_run_id:
        return response

    config = SettingsService(
        SettingRepository(
            db,
            request.app.state.setting_cipher,
            request.app.state.settings.runner_setting_defaults(),
        )
    ).get_runner_config(task.business_id).with_execution_snapshot(
        task.runner_config_snapshot
    )
    gateway = UniversalGateway()

    try:
        current = await gateway.list_current_step(config, task.remote_run_id)
        current_payload = _payload(current.payload)
        response["current_step"] = _current_step(current_payload)
    except Exception as exc:
        response["errors"]["current_step"] = type(exc).__name__

    try:
        remote_result = await gateway.get_result(config, task.remote_run_id)
        result_payload = _payload(remote_result.payload)
        _merge_remote_result(response["result"], result_payload, task.remote_run_id)
    except Exception as exc:
        response["errors"]["result"] = type(exc).__name__

    thread_id = task.remote_thread_id
    if response["current_step"] and not thread_id:
        thread_id = response["current_step"].get("thread_id")

    try:
        thread_tasks = await gateway.list_task_by_thread(
            config,
            thread_id=thread_id,
            run_id=task.remote_run_id,
        )
        response["thread_groups"] = _thread_groups(_payload(thread_tasks.payload))
    except Exception as exc:
        response["errors"]["thread_tasks"] = type(exc).__name__

    if task.execution_status in {ExecutionStatus.RESULT_READY, ExecutionStatus.CANCELLED}:
        try:
            thread_detail = await gateway.detail_task_by_thread(
                config,
                thread_id=thread_id,
                run_id=task.remote_run_id,
            )
            response["thread_steps"] = _thread_steps(_payload(thread_detail.payload))
        except Exception as exc:
            response["errors"]["thread_steps"] = type(exc).__name__

    return response


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: str,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
) -> Task:
    return _get_task(db, task_id, business.id)


@router.post("/tasks/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(
    task_id: str,
    request: Request,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
    _csrf_session: CsrfSession,
) -> Task:
    repository = SQLiteTaskRepository(db)
    existing = repository.get(task_id, business.id)
    if existing is None:
        raise api_error(404, "task_not_found", "Task not found")
    service = TaskService(
        repository,
        request.app.state.create_runner_for_task(existing, db),
        execution_timeout=timedelta(
            seconds=request.app.state.settings.task_execution_timeout_seconds
        ),
        cancel_confirm_timeout=timedelta(
            seconds=request.app.state.settings.cancel_confirm_timeout_seconds
        ),
    )
    try:
        task = await service.cancel(task_id)
    except ValueError as exc:
        if str(exc).startswith("task_not_cancellable:"):
            raise api_error(
                409,
                "task_not_cancellable",
                "Task cannot be cancelled",
            ) from exc
        raise
    if task.execution_status == ExecutionStatus.RUNNING:
        await request.app.state.task_worker.enqueue(task.id)
    return task


@router.get("/tasks/{task_id}/events")
def list_task_events(
    task_id: str,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
    after_sequence: int = Query(default=0, ge=0),
) -> dict:
    _get_task(db, task_id, business.id)
    events = db.scalars(
        select(TaskEvent)
        .where(
            TaskEvent.task_id == task_id,
            TaskEvent.sequence > after_sequence,
        )
        .order_by(TaskEvent.sequence)
    )
    return {
        "items": [
            {
                "sequence": event.sequence,
                "type": event.event_type,
                "payload": event.payload,
                "created_at": event.created_at,
            }
            for event in events
        ]
    }


@router.get("/tasks/{task_id}/report")
def get_task_report(
    task_id: str,
    db: Database,
    _user: CurrentUser,
    business: CurrentBusiness,
) -> dict:
    _get_task(db, task_id, business.id)
    service = TaskService(
        SQLiteTaskRepository(db),
        None,
    )
    try:
        return service.get_report(task_id)
    except ValueError as exc:
        if str(exc).startswith("task_not_found:"):
            raise api_error(404, "task_not_found", "Task not found") from exc
        if str(exc).startswith("report_not_ready:"):
            raise api_error(409, "report_not_ready", "Task report is not ready") from exc
        raise


@testing_router.post("/run-next", status_code=status.HTTP_204_NO_CONTENT)
async def wait_for_worker(
    request: Request,
    _user: CurrentUser,
    _csrf_session: CsrfSession,
) -> Response:
    try:
        await request.app.state.task_worker.wait_until_idle()
    except WorkerUnavailableError as exc:
        raise api_error(
            503,
            "worker_unavailable",
            "Task worker is unavailable",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _get_task(db: Database, task_id: str, business_id: str) -> Task:
    task = SQLiteTaskRepository(db).get(task_id, business_id)
    if task is None:
        raise api_error(404, "task_not_found", "Task not found")
    return task


def _optional_filter(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return None if not normalized or normalized == "all" else normalized


def _payload(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    result = value.get("Result")
    return result if isinstance(result, dict) else value


def _str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _tool_results(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _current_step(payload: dict) -> dict:
    return {
        "run_id": _str(payload.get("RunId")),
        "thread_id": _str(payload.get("ThreadId")),
        "status": _int(payload.get("Status")),
        "step_id": _str(payload.get("StepId")),
        "results": _tool_results(payload.get("Results")),
    }


def _thread_groups(payload: dict) -> list[dict]:
    groups = payload.get("ThreadGroups")
    if not isinstance(groups, list):
        return []
    normalized = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        tasks = []
        for item in _tool_results(group.get("Tasks")):
            artifact_count = item.get("ArtifactCount")
            tasks.append(
                {
                    "run_id": _str(item.get("RunId")),
                    "thread_id": _str(item.get("ThreadId")),
                    "run_name": _str(item.get("RunName")),
                    "status": _int(item.get("Status")),
                    "pod_id": _str(item.get("PodId")),
                    "product_id": _str(item.get("ProductId")),
                    "created_at": _str(item.get("CreatedAt")),
                    "started_at": _str(item.get("StartedAt")),
                    "updated_at": _str(item.get("UpdatedAt")),
                    "completed_at": _str(item.get("CompletedAt")),
                    "trace_id": _str(item.get("TraceId")),
                    "artifact_count": artifact_count if isinstance(artifact_count, dict) else None,
                }
            )
        normalized.append(
            {
                "thread_id": _str(group.get("ThreadId")),
                "tasks": tasks,
                "task_next_token": _str(group.get("TaskNextToken")),
            }
        )
    return normalized


def _thread_steps(payload: dict) -> list[dict]:
    steps = payload.get("RunSteps")
    if not isinstance(steps, list):
        return []
    normalized = []
    for item in steps:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "run_id": _str(item.get("RunId")),
                "thread_id": _str(item.get("ThreadId")),
                "status": _int(item.get("Status")),
                "step_id": _str(item.get("StepId")),
                "results": _tool_results(item.get("Results")),
            }
        )
    return normalized


def _merge_remote_result(
    target: dict,
    payload: dict,
    run_id: str | None = None,
) -> None:
    content = payload.get("Content")
    if isinstance(content, str) and content.strip() and not target.get("summary"):
        target["summary"] = content.strip()
    recording_url = payload.get("RecordingUrl")
    if isinstance(recording_url, str) and recording_url.strip():
        target["recording_url"] = recording_url.strip()
    assets = target.setdefault("assets", {})
    if not isinstance(assets, dict):
        assets = {}
        target["assets"] = assets
    screenshots = payload.get("ScreenShots")
    if isinstance(screenshots, dict):
        assets["screenshots"] = _filter_screenshots_for_run(screenshots, run_id)
    usage = payload.get("Usage")
    if isinstance(usage, dict):
        assets["usage"] = usage
    files = payload.get("Files")
    if isinstance(files, list):
        assets["files"] = [item for item in files if isinstance(item, str)]
    if isinstance(content, str) and content.strip():
        assets["content"] = content.strip()
    struct_output = payload.get("StructOutput")
    if isinstance(struct_output, dict):
        assets["struct_output"] = struct_output
    _merge_int_asset(assets, payload, "total_steps", "TotalSteps", "total_steps")
    _merge_int_asset(assets, payload, "duration_ms", "DurationMs", "duration_ms")
    _merge_string_asset(assets, payload, "duration_fmt", "DurationFmt", "duration_fmt")
    _merge_int_asset(
        assets,
        payload,
        "avg_step_duration_sec",
        "AvgStepDurationSec",
        "avg_step_duration_sec",
    )


def _merge_local_runtime_assets(response: dict, assets: dict) -> None:
    if not isinstance(assets, dict):
        return
    current_step = assets.get("current_step")
    if isinstance(current_step, dict):
        response["current_step"] = current_step
    thread_groups = assets.get("thread_groups")
    if isinstance(thread_groups, list):
        response["thread_groups"] = [
            item for item in thread_groups if isinstance(item, dict)
        ]
    thread_steps = assets.get("thread_steps")
    if isinstance(thread_steps, list):
        response["thread_steps"] = [
            item for item in thread_steps if isinstance(item, dict)
        ]


def _merge_int_asset(
    assets: dict,
    payload: dict,
    target: str,
    *keys: str,
) -> None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            assets[target] = value
            return


def _merge_string_asset(
    assets: dict,
    payload: dict,
    target: str,
    *keys: str,
) -> None:
    for key in keys:
        value = _str(payload.get(key))
        if value:
            assets[target] = value
            return


def _filter_result_assets_for_run(assets: object, run_id: str | None) -> dict:
    if not isinstance(assets, dict):
        return {}
    filtered = dict(assets)
    screenshots = filtered.get("screenshots")
    if isinstance(screenshots, dict):
        filtered["screenshots"] = _filter_screenshots_for_run(screenshots, run_id)
    return filtered


def _filter_screenshots_for_run(
    screenshots: dict,
    run_id: str | None,
) -> dict:
    if not run_id:
        return screenshots
    prefix = f"{run_id}-"
    return {
        key: value
        for key, value in screenshots.items()
        if isinstance(key, str) and key.startswith(prefix)
    }
