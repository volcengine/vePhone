import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


RunnerMode = Literal["mock", "mobile_use"]
DevicePrepareAction = Literal["none", "reset", "reboot"]
_TOS_REGION = re.compile(r"^[a-z]{2}-[a-z]+(?:-\d+)?$")
_RESERVED_REQUEST_HEADERS = {
    "accept",
    "authorization",
    "content-length",
    "content-type",
    "host",
    "user-agent",
    "x-content-sha256",
    "x-date",
}


class RunnerExecutionSettingsError(ValueError):
    def __init__(self, missing_fields: list[str]) -> None:
        super().__init__("runner_execution_settings_incomplete")
        self.missing_fields = missing_fields


class MobileUseSettingsUpdate(BaseModel):
    access_key_id: str | None = None
    secret_access_key: str | None = None
    product_id: str | None = None
    account_id: str | None = None
    sts_role_trn: str | None = None
    stream_token_ttl_seconds: int | None = Field(default=None, ge=60, le=3600)
    pod_id: str | None = None
    ark_api_key: str | None = None
    tos_bucket: str | None = None
    tos_endpoint: str | None = None
    tos_region: str | None = None
    use_base64_screenshot: bool | None = None
    max_step: int | None = Field(default=None, ge=1, le=500)
    timeout_seconds: int | None = Field(default=None, ge=1, le=86400)
    callback_info: dict[str, Any] | None = None
    output_schema: str | None = None
    retry_limit: int | None = Field(default=None, ge=1, le=10)
    system_prompt: str | None = None
    screen_record: bool | None = None
    mcp_json: str | None = None
    max_output_tokens: int | None = Field(default=None, ge=1)
    gps_info: str | None = None
    request_headers: dict[str, str] | None = None
    device_prepare_action: DevicePrepareAction | None = None

    @field_validator("output_schema", "mcp_json")
    @classmethod
    def validate_json_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        json.loads(value)
        return value


class RunnerSettingsUpdate(BaseModel):
    mode: RunnerMode
    mobile_use: MobileUseSettingsUpdate | None = None


class AgentRuntimeOptions(BaseModel):
    thread_id: str | None = Field(default=None, min_length=1, max_length=63)
    use_base64_screenshot: bool | None = None
    max_step: int | None = Field(default=None, ge=1, le=500)
    timeout_seconds: int | None = Field(default=None, ge=1, le=86400)
    callback_info: dict[str, Any] | None = None
    output_schema: str | None = None
    retry_limit: int | None = Field(default=None, ge=1, le=10)
    system_prompt: str | None = None
    tos_bucket: str | None = None
    tos_endpoint: str | None = None
    tos_region: str | None = None
    screen_record: bool | None = None
    mcp_json: str | None = None
    max_output_tokens: int | None = Field(default=None, ge=1)
    gps_info: str | None = None
    request_headers: dict[str, str] | None = None
    device_prepare_action: DevicePrepareAction | None = None

    @field_validator("output_schema", "mcp_json")
    @classmethod
    def validate_json_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        json.loads(value)
        return value

    @field_validator("request_headers")
    @classmethod
    def validate_request_headers_field(
        cls,
        value: dict[str, str] | None,
    ) -> dict[str, str] | None:
        return validate_request_headers(value)


class RunnerConfig(BaseModel):
    mode: RunnerMode
    access_key_id: str | None = None
    secret_access_key: str | None = None
    thread_id: str | None = Field(default=None, min_length=1, max_length=63)
    product_id: str | None = None
    account_id: str | None = None
    sts_role_trn: str | None = None
    stream_token_ttl_seconds: int = Field(default=600, ge=60, le=3600)
    pod_id: str | None = None
    ark_api_key: str | None = None
    tos_bucket: str | None = None
    tos_endpoint: str | None = None
    tos_region: str | None = None
    use_base64_screenshot: bool = False
    max_step: int = Field(default=100, ge=1, le=500)
    timeout_seconds: int = Field(default=120, ge=1, le=86400)
    callback_info: dict[str, Any] | None = None
    output_schema: str | None = None
    retry_limit: int = Field(default=3, ge=1, le=10)
    system_prompt: str | None = None
    screen_record: bool = False
    mcp_json: str | None = None
    max_output_tokens: int | None = Field(default=None, ge=1)
    gps_info: str | None = None
    request_headers: dict[str, str] | None = None
    device_prepare_action: DevicePrepareAction = "none"

    @classmethod
    def mock(cls) -> "RunnerConfig":
        return cls(mode="mock")

    def execution_snapshot(self) -> dict[str, str | int | bool]:
        if self.mode == "mock":
            return {"pod_id": "mock:default"}

        missing_fields = []
        if not self.tos_bucket:
            missing_fields.append("tos_bucket")
        if not self.tos_region or _TOS_REGION.fullmatch(self.tos_region) is None:
            missing_fields.append("tos_region")
        if missing_fields:
            raise RunnerExecutionSettingsError(missing_fields)
        if not self.product_id:
            raise RunnerExecutionSettingsError(["product_id"])
        return _without_none({
            "thread_id": self.thread_id,
            "product_id": self.product_id,
            "account_id": self.account_id,
            "sts_role_trn": self.sts_role_trn,
            "stream_token_ttl_seconds": self.stream_token_ttl_seconds,
            "tos_bucket": self.tos_bucket,
            "tos_endpoint": self.tos_endpoint,
            "tos_region": self.tos_region,
            "timeout_seconds": self.timeout_seconds,
            "use_base64_screenshot": self.use_base64_screenshot,
            "max_step": self.max_step,
            "callback_info": self.callback_info,
            "output_schema": self.output_schema,
            "retry_limit": self.retry_limit,
            "system_prompt": self.system_prompt,
            "screen_record": self.screen_record,
            "mcp_json": self.mcp_json,
            "max_output_tokens": self.max_output_tokens,
            "gps_info": self.gps_info,
            "request_headers": self.request_headers,
            "device_prepare_action": self.device_prepare_action,
        })

    def with_execution_snapshot(self, snapshot: dict[str, Any]) -> "RunnerConfig":
        fields = {
            field: snapshot.get(field)
            for field in (
                "product_id",
                "account_id",
                "sts_role_trn",
                "stream_token_ttl_seconds",
                "thread_id",
                "pod_id",
                "tos_bucket",
                "tos_endpoint",
                "tos_region",
                "timeout_seconds",
                "use_base64_screenshot",
                "max_step",
                "callback_info",
                "output_schema",
                "retry_limit",
                "system_prompt",
                "screen_record",
                "mcp_json",
                "max_output_tokens",
                "gps_info",
                "request_headers",
                "device_prepare_action",
            )
        }
        return self.model_copy(
            update={
                "mode": "mobile_use",
                **{key: value for key, value in fields.items() if value is not None},
            }
        )


def _without_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def validate_request_headers(
    value: dict[str, str] | None,
) -> dict[str, str] | None:
    if value is None:
        return None
    normalized: dict[str, str] = {}
    for raw_name, raw_value in value.items():
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise ValueError("request_header_name_invalid")
        if not isinstance(raw_value, str):
            raise ValueError("request_header_value_invalid")
        name = raw_name.strip()
        if name.lower() in _RESERVED_REQUEST_HEADERS:
            raise ValueError("request_header_reserved")
        normalized[name] = raw_value
    return normalized
