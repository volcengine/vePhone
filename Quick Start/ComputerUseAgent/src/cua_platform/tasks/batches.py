from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from cua_platform.business.models import DEFAULT_BUSINESS_ID
from cua_platform.cases.models import TestCase
from cua_platform.tasks.models import Task, TaskBatch, TaskRunnerConfig
from cua_platform.tasks.repository import SQLiteTaskRepository
from cua_platform.tasks.schemas import TaskBatchCreateRequest
from cua_platform.tasks.state_machine import ExecutionStatus


@dataclass(frozen=True)
class TaskBatchCreationResult:
    batch: TaskBatch
    disposition: Literal["created", "existing"]


@dataclass(frozen=True)
class TaskBatchCancelResult:
    batch: TaskBatch
    running_task_ids: tuple[str, ...]


class TaskBatchService:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        payload: TaskBatchCreateRequest,
        *,
        created_by: str,
        runner_type: str,
        config_snapshot: dict[str, Any],
        device_wait_timeout_seconds: int,
        business_id: str = DEFAULT_BUSINESS_ID,
        commit: bool = True,
    ) -> TaskBatchCreationResult:
        fingerprint = _canonical_json(
            payload.model_dump(exclude={"idempotency_key"})
        )
        existing = self._find_idempotent(payload.idempotency_key, fingerprint)
        if existing is not None:
            return TaskBatchCreationResult(existing, "existing")

        cases = list(
            self.db.scalars(
                select(TestCase).where(
                    TestCase.id.in_(payload.case_ids),
                    TestCase.business_id == business_id,
                    TestCase.deleted_at.is_(None),
                )
            )
        )
        case_by_id = {case.id: case for case in cases}
        missing = [case_id for case_id in payload.case_ids if case_id not in case_by_id]
        if missing:
            raise ValueError(f"batch_cases_not_found:{','.join(missing)}")

        batch_id = f"batch_{uuid4().hex}"
        snapshot = dict(config_snapshot)
        snapshot.pop("pod_id", None)
        snapshot["config_source"] = payload.agent_config_mode
        snapshot["device_strategy"] = payload.device_strategy
        snapshot["pod_ids"] = list(payload.pod_ids)
        snapshot["device_wait_timeout_seconds"] = device_wait_timeout_seconds
        if payload.timeout_seconds is not None:
            snapshot["timeout_seconds"] = payload.timeout_seconds
        if payload.agent_config_mode == "custom" and payload.agent_options:
            snapshot.update(payload.agent_options)

        batch = TaskBatch(
            id=batch_id,
            business_id=business_id,
            name=payload.name.strip(),
            test_type=payload.test_type,
            selection_mode=payload.selection_mode,
            selection_snapshot={
                **payload.selection_snapshot,
                "case_ids": list(payload.case_ids),
            },
            device_strategy=payload.device_strategy,
            pod_ids=list(payload.pod_ids),
            concurrency=payload.concurrency,
            device_wait_timeout_seconds=device_wait_timeout_seconds,
            runner_type=runner_type,
            config_snapshot=snapshot,
            execution_status=ExecutionStatus.QUEUED,
            idempotency_key=payload.idempotency_key,
            request_fingerprint=fingerprint,
            created_by=created_by,
        )
        queue_reason = (
            "waiting_for_any_device"
            if payload.device_strategy == "automatic"
            else "waiting_for_specified_device"
        )
        for position, case_id in enumerate(payload.case_ids):
            case = case_by_id[case_id]
            task_snapshot = dict(snapshot)
            if (
                payload.agent_config_mode == "case_default"
                and case.default_agent_options
            ):
                task_snapshot.update(case.default_agent_options)
            task = Task(
                id=f"task_{uuid4().hex}",
                business_id=business_id,
                case_id=case.id,
                batch_id=batch.id,
                batch_position=position,
                queue_reason=queue_reason,
                script_version_id=None,
                prompt_snapshot=case.content_markdown,
                runner_type=runner_type,
                scenario=case.title,
                created_by=created_by,
                execution_status=ExecutionStatus.QUEUED,
                idempotency_key=f"{payload.idempotency_key}:{position}",
                request_fingerprint=_canonical_json(
                    {"batch_id": batch.id, "case_id": case.id, "position": position}
                ),
                version=1,
            )
            task.start_idempotency_key = f"start:{task.id}"
            task.runner_config = TaskRunnerConfig(config_snapshot=task_snapshot)
            batch.tasks.append(task)

        try:
            self.db.add(batch)
            if not commit:
                self.db.flush()
                return TaskBatchCreationResult(batch, "created")
            self.db.commit()
            return TaskBatchCreationResult(
                self._required(batch.id),
                "created",
            )
        except IntegrityError:
            self.db.rollback()
            existing = self._find_idempotent(
                payload.idempotency_key,
                fingerprint,
            )
            if existing is not None:
                return TaskBatchCreationResult(existing, "existing")
            raise
        except Exception:
            self.db.rollback()
            raise

    def get(
        self,
        batch_id: str,
        business_id: str | None = None,
    ) -> TaskBatch | None:
        filters = [TaskBatch.id == batch_id]
        if business_id is not None:
            filters.append(TaskBatch.business_id == business_id)
        return self.db.scalar(
            select(TaskBatch)
            .options(selectinload(TaskBatch.tasks))
            .where(*filters)
        )

    def cancel(
        self,
        batch_id: str,
        now: datetime,
        business_id: str | None = None,
    ) -> TaskBatchCancelResult:
        batch = self.get(batch_id, business_id)
        if batch is None:
            raise ValueError(f"task_batch_not_found:{batch_id}")
        if batch.execution_status in {
            ExecutionStatus.RESULT_READY,
            ExecutionStatus.CANCELLED,
        }:
            return TaskBatchCancelResult(batch, ())
        batch.cancel_requested_at = batch.cancel_requested_at or now
        self.db.commit()
        repository = SQLiteTaskRepository(self.db)
        running_ids: list[str] = []
        for task in list(batch.tasks):
            if task.execution_status == ExecutionStatus.QUEUED:
                repository.request_cancel(task.id, now)
            elif task.execution_status == ExecutionStatus.RUNNING:
                repository.request_cancel(task.id, now)
                running_ids.append(task.id)
        refreshed = self._required(batch_id)
        aggregate_batch_status(refreshed, now)
        self.db.commit()
        return TaskBatchCancelResult(
            self._required(batch_id),
            tuple(running_ids),
        )

    def _required(self, batch_id: str) -> TaskBatch:
        self.db.expire_all()
        batch = self.get(batch_id)
        if batch is None:
            raise ValueError(f"task_batch_not_found:{batch_id}")
        return batch

    def _find_idempotent(
        self,
        idempotency_key: str,
        fingerprint: str,
    ) -> TaskBatch | None:
        existing = self.db.scalar(
            select(TaskBatch)
            .options(selectinload(TaskBatch.tasks))
            .where(TaskBatch.idempotency_key == idempotency_key)
        )
        if existing is not None and existing.request_fingerprint != fingerprint:
            raise ValueError(f"idempotency_conflict:{idempotency_key}")
        return existing


def aggregate_batch_status(batch: TaskBatch, now: datetime) -> None:
    tasks = list(batch.tasks)
    if not tasks:
        return
    statuses = {task.execution_status for task in tasks}
    if any(status == ExecutionStatus.RUNNING for status in statuses):
        batch.execution_status = ExecutionStatus.RUNNING
        batch.started_at = batch.started_at or now
        return
    if all(status == ExecutionStatus.QUEUED for status in statuses):
        batch.execution_status = ExecutionStatus.QUEUED
        return
    if any(status == ExecutionStatus.QUEUED for status in statuses):
        batch.execution_status = ExecutionStatus.RUNNING
        batch.started_at = batch.started_at or now
        return
    batch.finished_at = now
    if batch.cancel_requested_at is not None or any(
        status == ExecutionStatus.CANCELLED for status in statuses
    ):
        batch.execution_status = ExecutionStatus.CANCELLED
        batch.verdict = None
        return
    batch.execution_status = ExecutionStatus.RESULT_READY
    batch.verdict = (
        "pass" if all(task.verdict == "pass" for task in tasks) else "fail"
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
