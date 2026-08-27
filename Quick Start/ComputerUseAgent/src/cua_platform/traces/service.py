from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select

from cua_platform.runners.base import RunnerEvent
from cua_platform.runners.universal_gateway import GatewayTraceAttempt
from cua_platform.tasks.models import Task, TaskEvent
from cua_platform.traces.models import TaskTraceSpan
from cua_platform.traces.repository import TraceRepository
from cua_platform.traces.schemas import (
    TaskTraceResponse,
    TraceSpanDraft,
    TraceSpanResponse,
)


class TraceService:
    def __init__(self, repository: TraceRepository) -> None:
        self.repository = repository

    def upsert(
        self,
        task_id: str,
        stable_key: str,
        draft: TraceSpanDraft,
    ) -> TaskTraceSpan:
        if not stable_key or stable_key != draft.stable_key:
            raise ValueError("trace_stable_key_invalid")
        try:
            span = self.repository.upsert(task_id, stable_key, draft)
            self.repository.db.commit()
            return span
        except Exception:
            self.repository.db.rollback()
            raise

    def record_gateway_attempt(
        self,
        task_id: str,
        attempt: GatewayTraceAttempt,
    ) -> TaskTraceSpan:
        call_key, separator, _attempt_number = attempt.stable_key.rpartition(".attempt.")
        if not separator or not call_key:
            raise ValueError("trace_stable_key_invalid")
        try:
            existing_call = self.repository.get_by_stable_key(task_id, call_key)
            call_started_at = (
                existing_call.started_at
                if existing_call is not None
                else attempt.started_at
            )
            total_duration_ms = max(
                0,
                int((attempt.finished_at - call_started_at).total_seconds() * 1000),
            )
            self.repository.upsert(
                task_id,
                call_key,
                TraceSpanDraft(
                    stable_key=call_key,
                    parent_stable_key=None,
                    kind="call",
                    name=attempt.action,
                    status=attempt.status,
                    started_at=call_started_at,
                    finished_at=attempt.finished_at,
                    request_id=attempt.request_id,
                    step_index=None,
                    error_code=attempt.error_code,
                    attributes={
                        "action": attempt.action,
                        "method": attempt.method,
                        "duration_ms": total_duration_ms,
                    },
                ),
            )
            span = self.repository.upsert(
                task_id,
                attempt.stable_key,
                TraceSpanDraft(
                    stable_key=attempt.stable_key,
                    parent_stable_key=call_key,
                    kind="attempt",
                    name=attempt.action,
                    status=attempt.status,
                    started_at=attempt.started_at,
                    finished_at=attempt.finished_at,
                    request_id=attempt.request_id,
                    step_index=None,
                    error_code=attempt.error_code,
                    attributes={
                        "action": attempt.action,
                        "method": attempt.method,
                        "attempt": attempt.attempt,
                        "duration_ms": attempt.duration_ms,
                    },
                ),
            )
            self.repository.db.commit()
            return span
        except Exception:
            self.repository.db.rollback()
            raise

    def get(
        self,
        task_id: str,
        view: Literal["tree", "flat"],
        include_attempts: bool,
    ) -> TaskTraceResponse:
        task = self.repository.db.get(Task, task_id)
        if task is None:
            raise ValueError(f"task_not_found:{task_id}")
        persisted = self.repository.list_for_task(task_id)
        source: Literal["spans", "events"] = "spans" if persisted else "events"
        spans = (
            [_persisted_response(span) for span in persisted]
            if persisted
            else self._historical_responses(task_id)
        )
        if not include_attempts:
            spans = [span for span in spans if span.kind != "attempt"]
        if view == "tree":
            spans = _tree(spans)
        return TaskTraceResponse(
            task_id=task.id,
            source=source,
            view=view,
            execution_status=task.execution_status.value,
            verdict=task.verdict.value if task.verdict is not None else None,
            failure_type=task.failure_type,
            spans=spans,
        )

    def _historical_responses(self, task_id: str) -> list[TraceSpanResponse]:
        events = self.repository.db.scalars(
            select(TaskEvent)
            .where(TaskEvent.task_id == task_id)
            .order_by(TaskEvent.sequence)
        )
        return [
            TraceSpanResponse(
                id=f"historical.{event.sequence}",
                parent_span_id=None,
                sequence=event.sequence,
                kind=_historical_kind(event.event_type),
                name=event.event_type,
                status=_historical_status(event.event_type),
                started_at=_as_utc(event.created_at),
                finished_at=None,
                duration_ms=None,
                request_id=None,
                step_index=None,
                error_code=None,
                attributes={},
            )
            for event in events
        ]


def draft_for_runner_event(
    event: RunnerEvent,
    runner_type: str,
    occurred_at: datetime,
) -> TraceSpanDraft:
    trace_time = (
        occurred_at.replace(tzinfo=UTC)
        if occurred_at.tzinfo is None
        else occurred_at.astimezone(UTC)
    )
    kind = {
        "step_started": "step",
        "step_log": "step",
        "step_finished": "step",
        "task_finished": "result",
        "task_cancelled": "cancel",
        "task_start_outcome_unknown": "error",
        "runner_interrupted": "error",
        "runner_warning": "error",
    }.get(event.type, "lifecycle")
    status = (
        str(event.payload.get("status", "ok"))
        if kind == "step"
        else "error"
        if kind == "error"
        else "ok"
    )
    step_index = event.payload.get("index", event.payload.get("step_index"))
    return TraceSpanDraft(
        stable_key=f"event.{event.sequence}",
        parent_stable_key=None,
        kind=kind,
        name=event.type,
        status=status,
        started_at=trace_time,
        finished_at=trace_time,
        request_id=_safe_request_id(event.payload.get("request_id")),
        step_index=step_index if isinstance(step_index, int) else None,
        error_code=_safe_error_code(event.payload.get("error_code")),
        attributes={"runner_type": runner_type},
    )


def _safe_request_id(value: object) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 128:
        return None
    return value if all(character.isalnum() or character in "_.:-" for character in value) else None


def _safe_error_code(value: object) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 64:
        return None
    return value


def _persisted_response(span: TaskTraceSpan) -> TraceSpanResponse:
    started_at = _as_utc(span.started_at)
    finished_at = _as_utc(span.finished_at) if span.finished_at is not None else None
    duration_ms = (
        max(0, int((finished_at - started_at).total_seconds() * 1000))
        if finished_at is not None
        else None
    )
    return TraceSpanResponse(
        id=span.id,
        parent_span_id=span.parent_span_id,
        sequence=span.sequence,
        kind=span.kind,
        name=span.name,
        status=span.status,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        request_id=span.request_id,
        step_index=span.step_index,
        error_code=span.error_code,
        attributes=span.attributes,
    )


def _tree(spans: list[TraceSpanResponse]) -> list[TraceSpanResponse]:
    by_id = {span.id: span.model_copy(update={"children": []}) for span in spans}
    roots: list[TraceSpanResponse] = []
    for span in by_id.values():
        parent = by_id.get(span.parent_span_id or "")
        if parent is None:
            roots.append(span)
        else:
            parent.children.append(span)
    return roots


def _historical_kind(event_type: str) -> str:
    if event_type.startswith("step_"):
        return "step"
    if event_type == "task_finished":
        return "result"
    if event_type == "task_cancelled":
        return "cancel"
    if event_type in {"runner_interrupted", "runner_warning"}:
        return "error"
    return "lifecycle"


def _historical_status(event_type: str) -> str:
    return "error" if event_type in {"runner_interrupted", "runner_warning"} else "unknown"


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
