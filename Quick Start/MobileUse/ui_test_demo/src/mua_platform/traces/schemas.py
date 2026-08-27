from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


TraceAttribute = str | int | bool | None
TRACE_ATTRIBUTE_KEYS = frozenset(
    {
        "action",
        "method",
        "attempt",
        "duration_ms",
        "result_category",
        "runner_type",
        "pod_id",
        "product_id",
        "remote_task_id",
    }
)
MAX_TRACE_ATTRIBUTE_STRING_LENGTH = 256
MAX_TRACE_ATTRIBUTE_INTEGER = 2**53 - 1


@dataclass(frozen=True, slots=True)
class TraceSpanDraft:
    stable_key: str
    parent_stable_key: str | None
    kind: str
    name: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    request_id: str | None
    step_index: int | None
    error_code: str | None
    attributes: Mapping[str, TraceAttribute]


class TraceSpanResponse(BaseModel):
    id: str
    parent_span_id: str | None
    sequence: int
    kind: str
    name: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    request_id: str | None
    step_index: int | None
    error_code: str | None
    attributes: dict[str, TraceAttribute]
    children: list["TraceSpanResponse"] | None = None


class TaskTraceResponse(BaseModel):
    task_id: str
    source: Literal["spans", "events"]
    view: Literal["tree", "flat"]
    execution_status: str
    verdict: str | None
    failure_type: str | None
    spans: list[TraceSpanResponse]


def validate_trace_attributes(
    attributes: Mapping[str, TraceAttribute],
) -> dict[str, TraceAttribute]:
    safe: dict[str, TraceAttribute] = {}
    for key, value in attributes.items():
        if key not in TRACE_ATTRIBUTE_KEYS or not _bounded_scalar(value):
            raise ValueError("trace_attributes_unsafe")
        safe[key] = value
    return safe


def _bounded_scalar(value: object) -> bool:
    if value is None or isinstance(value, bool):
        return True
    if isinstance(value, int):
        return abs(value) <= MAX_TRACE_ATTRIBUTE_INTEGER
    return isinstance(value, str) and len(value) <= MAX_TRACE_ATTRIBUTE_STRING_LENGTH
