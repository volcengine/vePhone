from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cua_platform.cases.schemas import TestCaseResponse
from cua_platform.tasks.schemas import TaskExecutionConfig

TestType = Literal["new_feature", "regression"]


class TestPlanWrite(BaseModel):
    name: str
    description: str | None = Field(default=None, max_length=2000)
    test_type: TestType = "regression"
    tags: list[str] = Field(default_factory=list)
    case_ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("test_plan_name_required")
        if len(normalized) > 100:
            raise ValueError("test_plan_name_too_long")
        try:
            normalized.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("test_plan_name_invalid_unicode") from exc
        return normalized

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            tag = value.strip()
            if not tag or len(tag) > 32:
                raise ValueError("test_plan_tag_length")
            try:
                tag.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise ValueError("test_plan_tag_invalid_unicode") from exc
            if tag not in seen:
                seen.add(tag)
                normalized.append(tag)
        return normalized

    @field_validator("case_ids")
    @classmethod
    def require_unique_case_ids(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("test_plan_case_ids_must_be_unique")
        return values


class TagResponse(BaseModel):
    name: str
    foreground_color: str
    background_color: str
    case_count: int | None = None


class LatestPlanExecutionResponse(BaseModel):
    execution_id: str
    task_batch_id: str
    report_status: str
    pass_rate: float
    created_at: datetime


class ScheduleSummaryResponse(BaseModel):
    enabled: bool
    cron_expr: str
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None


class TestPlanResponse(BaseModel):
    id: str
    name: str
    description: str | None
    test_type: TestType
    tags: list[TagResponse]
    case_ids: list[str]
    case_count: int
    execution_count: int
    latest_execution: LatestPlanExecutionResponse | None
    schedule: ScheduleSummaryResponse | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime


class TestPlanListResponse(BaseModel):
    items: list[TestPlanResponse]
    total: int
    page: int
    page_size: int


class TestPlanStatsResponse(BaseModel):
    active_plan_count: int
    distinct_case_count: int
    execution_count: int
    latest_completed_pass_rate: float


class CreatorListResponse(BaseModel):
    items: list[str]


class TagListResponse(BaseModel):
    items: list[TagResponse]
    total: int
    page: int
    page_size: int


class TestPlanCaseListResponse(BaseModel):
    items: list[TestCaseResponse]
    total: int
    page: int
    page_size: int


ReportStatus = Literal[
    "queued",
    "running",
    "success",
    "failure",
    "exception",
    "cancelled",
]


class PlanReportSummary(BaseModel):
    execution_id: str
    task_batch_id: str
    test_plan_id: str | None
    plan_name_snapshot: str
    report_status: ReportStatus
    pass_rate: float
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: int | None


class PlanReportStats(BaseModel):
    report_count: int
    success_count: int
    failure_count: int
    average_pass_rate: float


ReportTaskExecutionStatus = Literal[
    "script_pending",
    "queued",
    "running",
    "result_ready",
    "cancelled",
    "unknown",
]
ReportTaskVerdict = Literal["pass", "fail", "unknown"]


class PlanReportTask(BaseModel):
    task_id: str
    remote_run_id: str | None = None
    case_id: str
    case_title: str
    case_deleted: bool = False
    execution_status: ReportTaskExecutionStatus
    verdict: ReportTaskVerdict | None
    failure_type: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: int | None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_steps: int | None = None


class PlanReportDetail(PlanReportSummary):
    plan_tags_snapshot: list[str]
    case_ids_snapshot: list[str]
    device_strategy_snapshot: str
    pod_ids_snapshot: list[str]
    concurrency_snapshot: int
    runner_type_snapshot: str
    config_snapshot: TaskExecutionConfig
    pass_count: int
    fail_count: int
    exception_count: int
    cancelled_count: int
    queued_count: int
    running_count: int
    tasks: list[PlanReportTask]
    tasks_total: int
    page: int
    page_size: int


class PlanReportListResponse(BaseModel):
    items: list[PlanReportSummary]
    total: int
    page: int
    page_size: int


class ScheduleExecutionConfig(BaseModel):
    test_type: TestType = "regression"
    device_strategy: Literal["automatic", "specified"] = "automatic"
    pod_ids: list[str] = Field(default_factory=list, max_length=20)
    concurrency: int = Field(ge=1, le=20)
    device_wait_timeout_seconds: int | None = Field(
        default=None, ge=1, le=86400
    )
    timeout_seconds: int | None = Field(default=None, ge=1, le=86400)
    agent_config_mode: Literal["global", "custom", "case_default"] = "global"
    agent_options: dict | None = None


class TestPlanScheduleCreate(BaseModel):
    __test__ = False

    cron_expr: str = Field(min_length=1, max_length=100)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    execution_config: ScheduleExecutionConfig
    enabled: bool = True

    @field_validator("cron_expr")
    @classmethod
    def validate_cron_expr(cls, value: str) -> str:
        from cua_platform.test_plans.scheduling import validate_cron

        validate_cron(value.strip())
        return value.strip()

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        from cua_platform.test_plans.scheduling import _zone

        _zone(value)
        return value


class TestPlanScheduleUpdate(BaseModel):
    __test__ = False

    cron_expr: str | None = Field(default=None, min_length=1, max_length=100)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    execution_config: ScheduleExecutionConfig | None = None
    enabled: bool | None = None

    @field_validator("cron_expr")
    @classmethod
    def validate_cron_expr(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from cua_platform.test_plans.scheduling import validate_cron

        validate_cron(value.strip())
        return value.strip()

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from cua_platform.test_plans.scheduling import _zone

        _zone(value)
        return value


class TestPlanScheduleResponse(BaseModel):
    __test__ = False

    model_config = ConfigDict(from_attributes=True)

    id: str
    test_plan_id: str
    cron_expr: str
    timezone: str
    enabled: bool
    next_run_at: datetime
    last_run_at: datetime | None
    last_skip_reason: str | None
    execution_config: dict
    created_by: str
    created_at: datetime
    updated_at: datetime


class ScheduleEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    schedule_id: str
    event_type: str
    trigger_type: str
    scheduled_for: datetime
    fired_at: datetime
    plan_execution_id: str | None
    skip_reason: str | None
    error_message: str | None
    created_at: datetime


class ScheduleEventListResponse(BaseModel):
    items: list[ScheduleEventResponse]
    total: int
    page: int
    page_size: int


class CronPreviewResponse(BaseModel):
    next_runs: list[datetime]
    human_description: str | None = None
