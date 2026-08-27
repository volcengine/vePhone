from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mua_platform.settings.schemas import validate_request_headers
from mua_platform.tasks.state_machine import ExecutionStatus, Verdict


class TaskEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sequence: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


class TaskStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_index: int
    instruction: str
    status: str
    assertion_result: str | None
    logs: list[str]
    error_code: str | None


class TaskExecutionConfig(BaseModel):
    source: Literal["global", "custom", "case_default", "legacy"]
    business_id: str | None = None
    business_name_snapshot: str | None = None
    thread_id: str | None = None
    product_id: str | None = None
    pod_id: str | None = None
    device_strategy: str | None = None
    pod_ids: list[str] | None = None
    tos_bucket: str | None = None
    tos_endpoint: str | None = None
    tos_region: str | None = None
    timeout_seconds: int | None = None
    device_wait_timeout_seconds: int | None = None
    use_base64_screenshot: bool | None = None
    max_step: int | None = None
    callback_info: dict[str, Any] | None = None
    output_schema: str | None = None
    retry_limit: int | None = None
    system_prompt: str | None = None
    screen_record: bool | None = None
    mcp_json: str | None = None
    max_output_tokens: int | None = None
    gps_info: str | None = None
    device_prepare_action: Literal["none", "reset", "reboot"] = "none"
    request_headers: dict[str, Any] = Field(
        default_factory=lambda: {"configured": False, "names": []}
    )


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    batch_id: str | None = None
    batch_position: int | None = None
    display_task_id: str
    source_type: str
    queue_reason: str | None = None
    script_version_id: str | None
    prompt_snapshot: str | None = None
    result_summary: str | None = None
    result_evidence: list[str] = Field(default_factory=list)
    remote_run_id: str | None = None
    remote_thread_id: str | None = None
    remote_status_code: int | None = None
    remote_step_id: str | None = None
    recording_url: str | None = None
    result_assets: dict[str, Any] = Field(default_factory=dict)
    runner_type: str
    scenario: str
    created_by: str
    execution_status: ExecutionStatus
    verdict: Verdict | None
    review_result: Verdict | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    failure_type: str | None
    version: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @field_validator("result_evidence", mode="before")
    @classmethod
    def _default_result_evidence(cls, value: object) -> object:
        return [] if value is None else value

    @field_validator("result_assets", mode="before")
    @classmethod
    def _default_result_assets(cls, value: object) -> object:
        return {} if value is None else value


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
    page: int
    page_size: int


class TaskReviewRequest(BaseModel):
    review_result: Verdict
    review_note: str | None = Field(default=None, max_length=2000)


class TaskBatchCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    test_type: Literal["new_feature", "regression"]
    selection_mode: Literal["multi_cases", "tags", "test_plan"]
    case_ids: list[str] = Field(min_length=1, max_length=100)
    selection_snapshot: dict[str, Any] = Field(default_factory=dict)
    device_strategy: Literal["automatic", "specified"]
    pod_ids: list[str] = Field(default_factory=list, max_length=20)
    concurrency: int = Field(ge=1, le=20)
    device_wait_timeout_seconds: int | None = Field(
        default=None,
        ge=1,
        le=86400,
    )
    timeout_seconds: int | None = Field(default=None, ge=1, le=86400)
    agent_config_mode: Literal["global", "custom", "case_default"] = "global"
    agent_options: dict[str, Any] | None = None
    idempotency_key: str = Field(min_length=1, max_length=255)

    @field_validator("agent_options")
    @classmethod
    def validate_agent_options(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if value is None:
            return value
        if (
            "device_prepare_action" in value
            and value["device_prepare_action"] not in {"none", "reset", "reboot"}
        ):
            raise ValueError("device_prepare_action_invalid")
        if "request_headers" not in value:
            return value
        try:
            value = dict(value)
            value["request_headers"] = validate_request_headers(
                value.get("request_headers")
            )
        except ValueError as exc:
            raise ValueError("request_headers_invalid") from exc
        return value

    @model_validator(mode="after")
    def validate_batch_shape(self) -> "TaskBatchCreateRequest":
        if len(set(self.case_ids)) != len(self.case_ids):
            raise ValueError("case_ids_must_be_unique")
        if self.selection_mode == "multi_cases" and len(self.case_ids) < 2:
            raise ValueError("multi_cases_requires_two_cases")
        if self.concurrency > len(self.case_ids):
            raise ValueError("concurrency_exceeds_case_count")
        if len(set(self.pod_ids)) != len(self.pod_ids):
            raise ValueError("pod_ids_must_be_unique")
        if self.device_strategy == "automatic" and self.pod_ids:
            raise ValueError("automatic_strategy_rejects_pod_ids")
        if self.device_strategy == "specified":
            if not self.pod_ids:
                raise ValueError("specified_strategy_requires_pod_ids")
            if len(self.pod_ids) > self.concurrency:
                raise ValueError("pod_count_exceeds_concurrency")
        return self


class TaskBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    test_type: str
    selection_mode: str
    selection_snapshot: dict[str, Any]
    device_strategy: str
    pod_ids: list[str]
    concurrency: int
    device_wait_timeout_seconds: int
    execution_status: ExecutionStatus
    verdict: Verdict | None
    created_by: str
    unavailable_since: datetime | None
    cancel_requested_at: datetime | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    tasks: list[TaskResponse]
