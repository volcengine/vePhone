import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from mua_platform.api.auth import router as auth_router
from mua_platform.api.body_limit import RequestBodyLimitMiddleware
from mua_platform.api.business import router as business_router
from mua_platform.api.cases import router as cases_router
from mua_platform.api.diagnostics import router as diagnostics_router
from mua_platform.api.errors import error_detail
from mua_platform.api.pods import router as pods_router
from mua_platform.api.settings import router as settings_router
from mua_platform.api.tasks import router as tasks_router
from mua_platform.api.tasks import testing_router
from mua_platform.api.test_plans import router as test_plans_router
from mua_platform.api.traces import router as traces_router
from mua_platform.auth.throttle import LoginThrottle
from mua_platform.business.models import BusinessSpace as _BusinessSpace  # noqa: F401
from mua_platform.config import Settings, get_settings
from mua_platform.db import (
    Base,
    create_engine_and_session,
    data_directory_is_writable,
    database_is_ready,
    ensure_auth_session_activity_column,
    ensure_schema_migrations,
)
from mua_platform.diagnostics.mobile_use import (
    CallableMobileUseDiagnosticGateway,
    DiagnosticCall,
    MobileUseDiagnosticAdapter,
    RemotePodResult,
    RemoteProbeResult,
)
from mua_platform.diagnostics.universal import UniversalMobileUseClient
from mua_platform.pods.gateway import PodGateway
from mua_platform.pods.models import DiscoveredPod as _DiscoveredPod  # noqa: F401
from mua_platform.pods.repository import PodRepository
from mua_platform.pods.service import PodDiscoveryGateway, PodPoolService
from mua_platform.pods.streaming import StreamTokenGateway, VolcengineStreamTokenGateway
from mua_platform.runners.base import RunRequest, RunnerAdapter
from mua_platform.runners.mobile_use import MobileUseRunner, RunRequestLoader
from mua_platform.runners.mock import MockRunner
from mua_platform.runners.universal_gateway import UniversalGateway
from mua_platform.settings.repository import SettingRepository
from mua_platform.settings.schemas import RunnerConfig
from mua_platform.settings.service import SettingsService
from mua_platform.settings.audit import AuditEvent as _AuditEvent  # noqa: F401
from mua_platform.settings.crypto import SettingCipher
from mua_platform.settings.models import Setting as _Setting  # noqa: F401
from mua_platform.tasks.repository import SQLiteTaskRepository
from mua_platform.tasks.pod_pool_refresh import SchedulerPodPoolRefresher
from mua_platform.tasks.scheduler import BatchScheduler
from mua_platform.tasks.service import AttachedLeaseUnavailable, TaskService
from mua_platform.tasks.state_machine import ExecutionStatus, StartState
from mua_platform.tasks.models import Task
from mua_platform.tasks.worker import TaskWorker, WorkerFailureDisposition
from mua_platform.test_plans.models import TestPlan as _TestPlan  # noqa: F401
from mua_platform.test_plans.schedule_runner import ScheduleTrigger
from mua_platform.test_plans.schedule_service import ScheduleService
from mua_platform.time import Clock, SystemClock
from mua_platform.traces.models import TaskTraceSpan as _TaskTraceSpan  # noqa: F401
from mua_platform.traces.repository import TraceRepository
from mua_platform.traces.service import TraceService

error_logger = logging.getLogger("mua_platform.errors")
RunnerFactory = Callable[[Task, RunnerConfig, RunRequestLoader], RunnerAdapter]

VALIDATION_BUSINESS_ERROR_CODES = {
    "automatic_strategy_rejects_pod_ids",
    "pod_count_exceeds_concurrency",
    "pod_ids_must_be_unique",
    "specified_strategy_requires_pod_ids",
}


def _business_validation_code(exc: RequestValidationError) -> str | None:
    for error in exc.errors():
        ctx = error.get("ctx")
        raw_error = ctx.get("error") if isinstance(ctx, dict) else None
        message = str(raw_error or error.get("msg", ""))
        for code in VALIDATION_BUSINESS_ERROR_CODES:
            if code in message:
                return code
    return None


def create_app(
    settings: Settings | None = None,
    *,
    runner_factory: RunnerFactory | None = None,
    diagnostics_runner_factory: Callable[[RunnerConfig], RunnerAdapter] | None = None,
    diagnostics_clock: Clock | None = None,
    diagnostics_timeout_seconds: float = 10.0,
    mobile_use_detail_pod: DiagnosticCall[RemotePodResult] | None = None,
    mobile_use_probe_api: DiagnosticCall[RemoteProbeResult] | None = None,
    pod_gateway: PodDiscoveryGateway | None = None,
    stream_token_gateway: StreamTokenGateway | None = None,
    readiness_database_check: Callable[[Engine], bool] | None = None,
) -> FastAPI:
    resolved = settings or get_settings()
    engine, session_factory = create_engine_and_session(resolved)
    Base.metadata.create_all(engine)
    ensure_auth_session_activity_column(engine)
    ensure_schema_migrations(engine)
    setting_cipher = SettingCipher.from_secret(resolved.app_secret_key)
    universal_mobile_use = UniversalMobileUseClient()
    resolved_pod_gateway = pod_gateway or PodGateway()
    resolved_stream_token_gateway = stream_token_gateway or VolcengineStreamTokenGateway()

    def load_run_request(task_id: str) -> RunRequest | None:
        with session_factory() as request_db:
            repository = SQLiteTaskRepository(request_db)
            task = repository.get(task_id)
            if task is None:
                return None
            case = repository.get_case(task.case_id)
            if case is None:
                return None
            content = task.prompt_snapshot or case.content_markdown
            return RunRequest(
                task_id=task.id,
                scenario=task.scenario,
                title=case.title,
                content_markdown=content,
            )

    def default_runner_factory(
        task: Task,
        config: RunnerConfig,
        request_loader: RunRequestLoader,
    ) -> RunnerAdapter:
        if task.runner_type == "mock":
            return MockRunner(resolved.app_secret_key)
        if task.runner_type == "mobile_use":
            return MobileUseRunner(
                config.with_execution_snapshot(task.runner_config_snapshot),
                UniversalGateway(),
                request_loader=request_loader,
            )
        raise ValueError(f"unsupported_runner_type:{task.runner_type}")

    resolved_runner_factory = runner_factory or default_runner_factory
    draining = False

    def create_runner_for_task(task: Task, db) -> RunnerAdapter:
        config = SettingsService(
            SettingRepository(db, setting_cipher, resolved.runner_setting_defaults())
        ).get_runner_config(task.business_id)
        if task.runner_type == "mobile_use":
            config = config.with_execution_snapshot(task.runner_config_snapshot)
        if runner_factory is None and task.runner_type == "mobile_use":
            trace_repository = TraceRepository(db)
            trace_service = TraceService(trace_repository)
            gateway = UniversalGateway(
                trace_sink=lambda attempt: trace_service.record_gateway_attempt(
                    task.id,
                    attempt,
                ),
                trace_call_counts=trace_repository.gateway_call_counts(task.id),
            )
            return MobileUseRunner(
                config,
                gateway,
                request_loader=load_run_request,
            )
        return resolved_runner_factory(task, config, load_run_request)

    def create_diagnostics_runner(config: RunnerConfig) -> RunnerAdapter:
        if diagnostics_runner_factory is not None:
            return diagnostics_runner_factory(config)
        if config.mode == "mock":
            return MockRunner(resolved.app_secret_key)
        gateway = CallableMobileUseDiagnosticGateway(
            mobile_use_detail_pod or universal_mobile_use.detail_pod,
            mobile_use_probe_api or universal_mobile_use.probe_api,
        )
        return MobileUseDiagnosticAdapter(gateway)

    async def execute_task(task_id: str) -> None:
        with session_factory() as db:
            repository = SQLiteTaskRepository(db)
            task = repository.get(task_id)
            if task is None:
                return
            service = TaskService(
                repository,
                create_runner_for_task(task, db),
                execution_timeout=timedelta(
                    seconds=resolved.task_execution_timeout_seconds
                ),
                cancel_confirm_timeout=timedelta(
                    seconds=resolved.cancel_confirm_timeout_seconds
                ),
            )
            if task.execution_status == ExecutionStatus.RUNNING:
                await service.execute_or_resume(task_id, worker_id="worker:default")
            elif task.execution_status == ExecutionStatus.QUEUED:
                await service.run_task(task_id, "worker:default")
        await schedule_batches()

    last_scheduled_business_id: str | None = None

    async def refresh_scheduler_product(
        business_id: str,
        product_id: str,
    ) -> None:
        with session_factory() as db:
            config = SettingsService(
                SettingRepository(
                    db,
                    setting_cipher,
                    resolved.runner_setting_defaults(),
                )
            ).get_runner_config(business_id)
            config = config.model_copy(update={"product_id": product_id})
            db.rollback()
            await PodPoolService(
                PodRepository(db),
                resolved_pod_gateway,
                SystemClock(),
            ).refresh(config)

    scheduler_pod_refresher = SchedulerPodPoolRefresher(
        session_factory,
        refresh_scheduler_product,
        refresh_interval=timedelta(
            seconds=resolved.pod_pool_refresh_interval_seconds
        ),
        failure_retry_interval=timedelta(
            seconds=resolved.pod_pool_refresh_failure_retry_seconds
        ),
    )

    async def schedule_batches() -> list[str]:
        nonlocal last_scheduled_business_id
        if draining:
            return []
        now = SystemClock().now()
        blocked_batch_ids = await scheduler_pod_refresher.refresh_due(now)
        if draining:
            return []
        with session_factory() as db:
            result = BatchScheduler(db).schedule(
                now,
                global_limit=resolved.task_worker_concurrency,
                start_after_business_id=last_scheduled_business_id,
                blocked_batch_ids=blocked_batch_ids,
            )
        last_scheduled_business_id = result.last_business_id
        worker = getattr(app.state, "task_worker", None)
        if worker is not None and worker.is_running:
            for task_id in result.task_ids:
                await worker.enqueue(task_id)
        return result.task_ids

    async def scan_due_schedules() -> None:
        if draining:
            return
        now = SystemClock().now()
        try:
            with session_factory() as db:
                trigger = ScheduleTrigger(db, resolved, setting_cipher)
                trigger.trigger_due(now)
        except Exception:
            error_logger.exception("schedule_scan_failed")

    async def scheduler_loop() -> None:
        while True:
            await scan_due_schedules()
            await schedule_batches()
            await asyncio.sleep(1)

    async def recover_startup() -> list[str]:
        with session_factory() as db:
            service = TaskService(
                SQLiteTaskRepository(db),
                None,
                execution_timeout=timedelta(
                    seconds=resolved.task_execution_timeout_seconds
                ),
                cancel_confirm_timeout=timedelta(
                    seconds=resolved.cancel_confirm_timeout_seconds
                ),
            )
            return await service.recover_startup()

    def drain_after_convergence_failure() -> WorkerFailureDisposition:
        nonlocal draining
        draining = True
        worker = getattr(app.state, "task_worker", None)
        if worker is not None:
            worker.begin_drain()
        return WorkerFailureDisposition.DRAIN

    async def converge_execute_failure(
        task_id: str,
    ) -> WorkerFailureDisposition:
        try:
            with session_factory() as db:
                repository = SQLiteTaskRepository(db)
                task = TaskService(
                    repository,
                    None,
                    execution_timeout=timedelta(
                        seconds=resolved.task_execution_timeout_seconds
                    ),
                    cancel_confirm_timeout=timedelta(
                        seconds=resolved.cancel_confirm_timeout_seconds
                    ),
                ).converge_worker_failure(
                    task_id,
                    worker_id="worker:default",
                )
        except AttachedLeaseUnavailable:
            return drain_after_convergence_failure()
        except Exception:
            error_logger.error(
                "task_worker_failure_convergence_failed",
                extra={"task_id": task_id},
            )
            return drain_after_convergence_failure()
        if (
            task is not None
            and task.execution_status == ExecutionStatus.RUNNING
            and task.start_state == StartState.ATTACHED
            and task.remote_run_id is not None
        ):
            return WorkerFailureDisposition.RETRY
        return WorkerFailureDisposition.COMPLETE

    def mount_spa(lifespan_app: FastAPI) -> None:
        dist = Path("dist")
        index = dist / "index.html"
        assets = dist / "assets"
        if not index.is_file() or getattr(lifespan_app.state, "spa_mounted", False):
            return
        if assets.is_dir():
            lifespan_app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @lifespan_app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            if path in {"api", "health"} or path.startswith(("api/", "health/")):
                raise StarletteHTTPException(status_code=404)
            return FileResponse(
                index,
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )

        lifespan_app.state.spa_mounted = True

    @asynccontextmanager
    async def lifespan(lifespan_app: FastAPI):
        nonlocal draining
        draining = False
        task_worker = TaskWorker(
            execute_task,
            recover_startup,
            converge_execute_failure,
            max_concurrency=resolved.task_worker_concurrency,
        )
        lifespan_app.state.task_worker = task_worker
        lifespan_app.state.schedule_batches = schedule_batches
        mount_spa(lifespan_app)
        await task_worker.start()
        try:
            with session_factory() as db:
                trigger = ScheduleTrigger(db, resolved, setting_cipher)
                trigger.trigger_due(
                    SystemClock().now(), trigger_type="catchup"
                )
        except Exception:
            error_logger.exception("schedule_startup_catchup_failed")
        scheduler_task = asyncio.create_task(scheduler_loop())
        try:
            yield
        finally:
            draining = True
            task_worker.begin_drain()
            scheduler_task.cancel()
            try:
                with suppress(asyncio.CancelledError):
                    await scheduler_task
            finally:
                await task_worker.stop(
                    timeout_seconds=resolved.task_worker_drain_timeout_seconds,
                )

    app = FastAPI(title="MUA Automation Platform", lifespan=lifespan)
    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_bytes=resolved.request_max_bytes,
    )
    app.state.settings = resolved
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.setting_cipher = setting_cipher
    app.state.create_runner_for_task = create_runner_for_task
    app.state.diagnostics_runner_factory = create_diagnostics_runner
    app.state.diagnostics_clock = diagnostics_clock or SystemClock()
    app.state.diagnostics_timeout_seconds = diagnostics_timeout_seconds
    app.state.auth_clock = SystemClock()
    app.state.login_throttle = LoginThrottle()
    app.state.runner_settings_lock = asyncio.Lock()
    app.state.pod_gateway = resolved_pod_gateway
    app.state.stream_token_gateway = resolved_stream_token_gateway
    app.state.pod_clock = SystemClock()
    app.include_router(auth_router)
    app.include_router(business_router)
    app.include_router(cases_router)
    app.include_router(diagnostics_router)
    app.include_router(pods_router)
    app.include_router(settings_router)
    app.include_router(tasks_router)
    app.include_router(test_plans_router)
    app.include_router(traces_router)
    if resolved.app_env == "test":
        app.include_router(testing_router)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else _http_error_detail(exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": detail},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        business_code = _business_validation_code(exc)
        if business_code is not None:
            detail = error_detail(
                business_code,
                "Request validation failed",
            )
            return JSONResponse(status_code=422, content={"error": detail})
        errors = [
            {key: value for key, value in error.items() if key not in {"input", "url"}}
            for error in exc.errors()
        ]
        detail = error_detail(
            "request_validation_failed",
            "Request validation failed",
            {"errors": jsonable_encoder(errors)},
        )
        return JSONResponse(status_code=422, content={"error": detail})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        detail = error_detail(
            "internal_server_error",
            "An unexpected error occurred",
        )
        error_logger.error(
            "Unhandled request exception",
            extra={
                "request_id": detail["request_id"],
                "method": request.method,
                "path": _route_template(request),
                "exception_type": type(exc).__name__,
            },
        )
        return JSONResponse(status_code=500, content={"error": detail})

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> JSONResponse:
        try:
            check_database_readiness = readiness_database_check or database_is_ready
            database_ready = check_database_readiness(engine)
        except SQLAlchemyError:
            database_ready = False
        checks = {
            "database": "ready" if database_ready else "not_ready",
            "data_directory": (
                "ready"
                if data_directory_is_writable(resolved.app_data_dir)
                else "not_ready"
            ),
            "worker": "ready" if app.state.task_worker.is_running else "not_ready",
        }
        failed_checks = [
            check_name
            for check_name, check_status in checks.items()
            if check_status == "not_ready"
        ]
        content = {
            "status": "not_ready" if failed_checks else "ready",
            "checks": checks,
            "failed_checks": failed_checks,
        }
        return JSONResponse(status_code=503 if failed_checks else 200, content=content)

    return app


def _http_error_detail(status_code: int) -> dict:
    if status_code == 404:
        return error_detail("not_found", "Resource not found")
    if status_code == 405:
        return error_detail("method_not_allowed", "Method not allowed")
    return error_detail("http_error", "Request failed")


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", "<unmatched>")

app = create_app()
