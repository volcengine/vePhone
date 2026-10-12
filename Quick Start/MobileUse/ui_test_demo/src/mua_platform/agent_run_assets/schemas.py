from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


class AgentRunScriptAsset(BaseModel):
    script_id: int
    name: str
    description: str | None = None
    resolution: str | None = None
    status: int
    created_at: int | str | None = None
    updated_at: int | str | None = None


class AgentRunScriptAssetDetail(AgentRunScriptAsset):
    script: str | None = None


class AgentRunChainAsset(BaseModel):
    chain_id: int
    name: str
    description: str | None = None
    status: int
    created_at: int | str | None = None
    updated_at: int | str | None = None


class AgentRunChainAssetDetail(AgentRunChainAsset):
    nodes: list[Any] | None = None


T = TypeVar("T")


class AgentRunAssetListResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int | None
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
