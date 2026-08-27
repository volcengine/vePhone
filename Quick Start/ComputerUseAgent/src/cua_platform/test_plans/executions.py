from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from cua_platform.business.models import DEFAULT_BUSINESS_ID
from cua_platform.settings.schemas import AgentRuntimeOptions
from cua_platform.tasks.batches import TaskBatchService
from cua_platform.tasks.execution_config import public_execution_config
from cua_platform.tasks.models import TaskBatch
from cua_platform.tasks.schemas import (
    TaskBatchCreateRequest,
    TaskBatchResponse,
    TaskExecutionConfig,
)
from cua_platform.test_plans.models import PlanExecution
from cua_platform.test_plans.service import TestPlanService


class PlanExecutionNotFoundError(ValueError):
    pass


class PlanExecutionConcurrencyError(ValueError):
    pass


class PlanExecutionCreate(BaseModel):
    test_type: Literal["new_feature", "regression"]
    device_strategy: Literal["automatic", "specified"]
    pod_ids: list[str] = Field(default_factory=list, max_length=20)
    concurrency: int = Field(ge=1, le=20)
    device_wait_timeout_seconds: int | None = Field(
        default=None,
        ge=1,
        le=86400,
    )
    timeout_seconds: int | None = Field(
        default=None,
        ge=1,
        le=86400,
    )
    agent_config_mode: Literal["global", "custom", "case_default"] = "global"
    agent_options: AgentRuntimeOptions | None = None
    idempotency_key: str = Field(min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_execution_shape(self) -> "PlanExecutionCreate":
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

    def to_batch(
        self,
        *,
        name: str,
        case_ids: list[str],
        plan_id: str,
    ) -> TaskBatchCreateRequest:
        return TaskBatchCreateRequest(
            name=name,
            test_type=self.test_type,
            selection_mode="test_plan",
            case_ids=case_ids,
            selection_snapshot={"test_plan_id": plan_id},
            device_strategy=self.device_strategy,
            pod_ids=list(self.pod_ids),
            concurrency=self.concurrency,
            device_wait_timeout_seconds=self.device_wait_timeout_seconds,
            timeout_seconds=self.timeout_seconds,
            agent_config_mode=self.agent_config_mode,
            agent_options=(
                self.agent_options.model_dump(exclude_none=True)
                if self.agent_options is not None
                else None
            ),
            idempotency_key=self.idempotency_key,
        )


class PlanExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    test_plan_id: str | None
    task_batch_id: str
    plan_name_snapshot: str
    plan_tags_snapshot: list[str]
    case_ids_snapshot: list[str]
    device_strategy_snapshot: str
    pod_ids_snapshot: list[str]
    concurrency_snapshot: int
    runner_type_snapshot: str
    config_snapshot: TaskExecutionConfig
    created_by: str
    created_at: datetime
    batch: TaskBatchResponse


@dataclass(frozen=True)
class PlanExecutionCreationResult:
    execution: PlanExecution
    batch: TaskBatch
    disposition: Literal["created", "existing"]


class PlanExecutionService:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        plan_id: str,
        payload: PlanExecutionCreate,
        *,
        created_by: str,
        runner_type: str,
        config_snapshot: dict[str, Any],
        device_wait_timeout_seconds: int,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> PlanExecutionCreationResult:
        plan = TestPlanService(self.db).get(plan_id, business_id)
        if plan is None:
            raise PlanExecutionNotFoundError("test_plan_not_found")

        case_ids = [item.case_id for item in plan.cases]
        if payload.concurrency > len(case_ids):
            raise PlanExecutionConcurrencyError(
                "concurrency_exceeds_case_count"
            )
        batch_payload = payload.to_batch(
            name=plan.name,
            case_ids=case_ids,
            plan_id=plan.id,
        )
        try:
            batch_result = TaskBatchService(self.db).create(
                batch_payload,
                created_by=created_by,
                runner_type=runner_type,
                config_snapshot=config_snapshot,
                device_wait_timeout_seconds=device_wait_timeout_seconds,
                business_id=business_id,
                commit=False,
            )
            if batch_result.disposition == "existing":
                execution = self.db.scalar(
                    select(PlanExecution).where(
                        PlanExecution.task_batch_id
                        == batch_result.batch.id
                    )
                )
                if execution is None:
                    raise ValueError(
                        f"idempotency_conflict:{payload.idempotency_key}"
                    )
                return PlanExecutionCreationResult(
                    execution,
                    batch_result.batch,
                    "existing",
                )

            execution = PlanExecution(
                id=f"execution_{uuid4().hex}",
                business_id=business_id,
                test_plan_id=plan.id,
                task_batch_id=batch_result.batch.id,
                plan_name_snapshot=plan.name,
                plan_tags_snapshot=list(plan.tags),
                case_ids_snapshot=case_ids,
                device_strategy_snapshot=payload.device_strategy,
                pod_ids_snapshot=list(payload.pod_ids),
                concurrency_snapshot=payload.concurrency,
                runner_type_snapshot=runner_type,
                config_snapshot=dict(
                    batch_result.batch.config_snapshot
                ),
                created_by=created_by,
            )
            self.db.add(execution)
            self.db.commit()
            self.db.refresh(execution)
            return PlanExecutionCreationResult(
                execution,
                batch_result.batch,
                "created",
            )
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def response(
        result: PlanExecutionCreationResult,
    ) -> PlanExecutionResponse:
        execution = result.execution
        return PlanExecutionResponse(
            id=execution.id,
            test_plan_id=execution.test_plan_id,
            task_batch_id=execution.task_batch_id,
            plan_name_snapshot=execution.plan_name_snapshot,
            plan_tags_snapshot=list(execution.plan_tags_snapshot),
            case_ids_snapshot=list(execution.case_ids_snapshot),
            device_strategy_snapshot=(
                execution.device_strategy_snapshot
            ),
            pod_ids_snapshot=list(execution.pod_ids_snapshot),
            concurrency_snapshot=execution.concurrency_snapshot,
            runner_type_snapshot=execution.runner_type_snapshot,
            config_snapshot=TaskExecutionConfig.model_validate(
                public_execution_config(execution.config_snapshot)
            ),
            created_by=execution.created_by,
            created_at=execution.created_at,
            batch=TaskBatchResponse.model_validate(result.batch),
        )
