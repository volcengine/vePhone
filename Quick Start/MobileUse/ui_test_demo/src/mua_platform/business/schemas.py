from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mua_platform.settings.schemas import RunnerSettingsUpdate


class BusinessSpaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    task_concurrency_limit: int = Field(default=4, ge=1, le=8)
    runner_settings: RunnerSettingsUpdate | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("business_name_required")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class BusinessSpaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    task_concurrency_limit: int | None = Field(default=None, ge=1, le=8)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("business_name_required")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class BusinessSpaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    is_default: bool
    task_concurrency_limit: int
    archived_at: datetime | None
    created_by: str


class BusinessSpaceListResponse(BaseModel):
    items: list[BusinessSpaceResponse]
