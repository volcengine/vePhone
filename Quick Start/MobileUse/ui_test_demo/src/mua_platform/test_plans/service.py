from datetime import datetime
from uuid import uuid4

from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from mua_platform.business.models import DEFAULT_BUSINESS_ID
from mua_platform.cases.models import TestCase
from mua_platform.db import _unused_tag_color
from mua_platform.tasks.models import Task, TaskBatch
from mua_platform.tasks.state_machine import ExecutionStatus, Verdict
from mua_platform.test_plans.models import (
    PlanExecution,
    TagColorRegistry,
    TestPlan,
    TestPlanCase,
    TestPlanSchedule,
)
from mua_platform.test_plans.schemas import (
    LatestPlanExecutionResponse,
    ScheduleSummaryResponse,
    TagResponse,
    TestPlanResponse,
    TestPlanWrite,
)
from mua_platform.test_plans.reports import effective_report_status


class TestPlanNameConflictError(ValueError):
    pass


class TestPlanCasesNotFoundError(ValueError):
    def __init__(self, case_ids: list[str]):
        super().__init__("test_plan_cases_not_found")
        self.case_ids = case_ids


class TestPlanCaseNotFoundError(ValueError):
    pass


class TestPlanExecutionActiveError(ValueError):
    pass


class TestPlanRequiresOneCaseError(ValueError):
    pass


class TagColorRegistryExhaustedError(RuntimeError):
    pass


class TagColorService:
    def __init__(self, db: Session):
        self.db = db

    def ensure(
        self,
        names: list[str],
    ) -> dict[str, TagColorRegistry]:
        unique_names = list(dict.fromkeys(names))
        if not unique_names:
            return {}

        existing = self.get_registered(unique_names)
        for tag_name in sorted(set(unique_names) - existing.keys()):
            registered = self._register(tag_name)
            existing[tag_name] = registered
        return {name: existing[name] for name in unique_names}

    def get_registered(
        self,
        names: list[str],
    ) -> dict[str, TagColorRegistry]:
        unique_names = list(dict.fromkeys(names))
        if not unique_names:
            return {}
        return {
            row.tag_name: row
            for row in self.db.scalars(
                select(TagColorRegistry).where(
                    TagColorRegistry.tag_name.in_(unique_names)
                )
            )
        }

    def list_paginated(
        self,
        search: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[TagColorRegistry], int]:
        query = select(TagColorRegistry)
        count_query = select(func.count(TagColorRegistry.tag_name))
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            query = query.where(TagColorRegistry.tag_name.ilike(pattern))
            count_query = count_query.where(
                TagColorRegistry.tag_name.ilike(pattern)
            )
        total = self.db.scalar(count_query) or 0
        items = list(
            self.db.scalars(
                query.order_by(TagColorRegistry.tag_name)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        counts = self._case_counts([item.tag_name for item in items])
        for item in items:
            item.case_count = counts.get(item.tag_name, 0)
        return items, total

    def _register(self, tag_name: str) -> TagColorRegistry:
        for _attempt in range(8):
            current = self.db.get(TagColorRegistry, tag_name)
            if current is not None:
                return current
            used_colors = set(
                self.db.scalars(
                    select(TagColorRegistry.foreground_color)
                )
            )
            try:
                foreground = _unused_tag_color(tag_name, used_colors)
            except RuntimeError as exc:
                raise TagColorRegistryExhaustedError(
                    "tag color registry exhausted"
                ) from exc
            candidate = TagColorRegistry(
                tag_name=tag_name,
                foreground_color=foreground,
                background_color=f"{foreground}1A",
            )
            try:
                with self.db.begin_nested():
                    self.db.add(candidate)
                    self.db.flush()
                return candidate
            except IntegrityError:
                self.db.expire_all()
        raise TagColorRegistryExhaustedError(
            "tag color registry allocation failed"
        )

    def _case_counts(self, names: list[str]) -> dict[str, int]:
        counts = dict.fromkeys(names, 0)
        if not counts:
            return counts
        for tags in self.db.scalars(select(TestCase.tags)):
            if not isinstance(tags, list):
                continue
            for tag in set(tags):
                if tag in counts:
                    counts[tag] += 1
        return counts


class TestPlanService:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        payload: TestPlanWrite,
        created_by: str,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> TestPlan:
        cases = self._require_cases(payload.case_ids, business_id)
        self._require_available_name(payload.name, business_id=business_id)
        plan = TestPlan(
            id=f"plan_{uuid4().hex}",
            business_id=business_id,
            name=payload.name,
            name_key=payload.name.casefold(),
            description=payload.description,
            test_type=payload.test_type,
            tags=list(payload.tags),
            created_by=created_by,
        )
        plan.cases = [
            TestPlanCase(
                case_id=case.id,
                position=position,
            )
            for position, case in enumerate(cases)
        ]
        try:
            TagColorService(self.db).ensure(payload.tags)
            self.db.add(plan)
            self.db.commit()
            return self._required(plan.id, business_id)
        except IntegrityError as exc:
            self.db.rollback()
            raise TestPlanNameConflictError(
                "test_plan_name_conflict"
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def update(
        self,
        plan_id: str,
        payload: TestPlanWrite,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> TestPlan | None:
        plan = self.get(plan_id, business_id)
        if plan is None:
            return None
        cases = self._require_cases(payload.case_ids, business_id)
        self._require_available_name(
            payload.name,
            exclude_plan_id=plan_id,
            business_id=business_id,
        )
        try:
            TagColorService(self.db).ensure(payload.tags)
            plan.name = payload.name
            plan.name_key = payload.name.casefold()
            plan.description = payload.description
            plan.test_type = payload.test_type
            plan.tags = list(payload.tags)
            plan.cases.clear()
            self.db.flush()
            plan.cases = [
                TestPlanCase(
                    case_id=case.id,
                    position=position,
                )
                for position, case in enumerate(cases)
            ]
            self.db.commit()
            return self._required(plan.id, business_id)
        except IntegrityError as exc:
            self.db.rollback()
            raise TestPlanNameConflictError(
                "test_plan_name_conflict"
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def get(
        self,
        plan_id: str,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> TestPlan | None:
        return self.db.scalar(
            select(TestPlan)
            .options(selectinload(TestPlan.cases))
            .where(
                TestPlan.id == plan_id,
                TestPlan.business_id == business_id,
                TestPlan.deleted_at.is_(None),
            )
        )

    def exists_active(
        self,
        plan_id: str,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> bool:
        return self.db.scalar(
            select(TestPlan.id)
            .where(
                TestPlan.id == plan_id,
                TestPlan.business_id == business_id,
                TestPlan.deleted_at.is_(None),
            )
            .limit(1)
        ) is not None

    def list_paginated(
        self,
        page: int,
        page_size: int,
        search: str | None,
        tag: str | None = None,
        test_type: str | None = None,
        business_id: str = DEFAULT_BUSINESS_ID,
        created_by: str | None = None,
    ) -> tuple[list[TestPlan], int]:
        query = (
            select(TestPlan)
            .options(selectinload(TestPlan.cases))
            .where(
                TestPlan.deleted_at.is_(None),
                TestPlan.business_id == business_id,
            )
        )
        count_query = select(func.count(TestPlan.id)).where(
            TestPlan.deleted_at.is_(None),
            TestPlan.business_id == business_id,
        )
        if search and search.strip():
            pattern = f"{search.strip().casefold()}%"
            query = query.where(TestPlan.name_key.ilike(pattern))
            count_query = count_query.where(
                TestPlan.name_key.ilike(pattern)
            )
        if tag and tag.strip():
            tag_values = (
                func.json_each(TestPlan.tags)
                .table_valued("value")
                .alias("plan_tag")
            )
            tag_filter = exists(
                select(1)
                .select_from(tag_values)
                .where(tag_values.c.value == tag.strip())
            )
            query = query.where(tag_filter)
            count_query = count_query.where(tag_filter)
        if test_type and test_type.strip():
            test_type_filter = self._test_type_filter(test_type.strip())
            query = query.where(test_type_filter)
            count_query = count_query.where(test_type_filter)
        if created_by and created_by.strip():
            creator_filter = TestPlan.created_by == created_by.strip()
            query = query.where(creator_filter)
            count_query = count_query.where(creator_filter)
        total = self.db.scalar(count_query) or 0
        plans = list(
            self.db.scalars(
                query.order_by(TestPlan.created_at.desc(), TestPlan.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return plans, total

    def list_creators(
        self,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> list[str]:
        rows = self.db.scalars(
            select(TestPlan.created_by)
            .where(
                TestPlan.deleted_at.is_(None),
                TestPlan.business_id == business_id,
                TestPlan.created_by.is_not(None),
                TestPlan.created_by != "",
            )
            .distinct()
            .order_by(TestPlan.created_by)
        ).all()
        return [creator for creator in rows if isinstance(creator, str)]

    def list_plan_tags(
        self,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> list[TagResponse]:
        tag_names = list(
            dict.fromkeys(
                tag_name
                for tags in self.db.scalars(
                    select(TestPlan.tags)
                    .where(
                        TestPlan.deleted_at.is_(None),
                        TestPlan.business_id == business_id,
                    )
                    .order_by(TestPlan.created_at.desc(), TestPlan.id.desc())
                )
                if isinstance(tags, list)
                for tag_name in tags
            )
        )
        colors = TagColorService(self.db).ensure(tag_names)
        self.db.commit()
        return [
            TagResponse(
                name=tag_name,
                foreground_color=colors[tag_name].foreground_color,
                background_color=colors[tag_name].background_color,
                case_count=None,
            )
            for tag_name in sorted(tag_names)
        ]

    def delete(
        self,
        plan_id: str,
        now: datetime,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> bool:
        plan = self.get(plan_id, business_id)
        if plan is None:
            return False
        plan.deleted_at = now
        plan.cases.clear()
        self.db.commit()
        return True

    def stats(
        self,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> dict[str, int | float]:
        active_plan_ids = list(
            self.db.scalars(
                select(TestPlan.id).where(TestPlan.deleted_at.is_(None))
                .where(TestPlan.business_id == business_id)
            )
        )
        if not active_plan_ids:
            return {
                "active_plan_count": 0,
                "distinct_case_count": 0,
                "execution_count": 0,
                "latest_completed_pass_rate": 0.0,
            }
        distinct_case_count = self.db.scalar(
            select(func.count(func.distinct(TestPlanCase.case_id))).where(
                TestPlanCase.plan_id.in_(active_plan_ids)
            )
        ) or 0
        execution_count = self.db.scalar(
            select(func.count(PlanExecution.id)).where(
                PlanExecution.test_plan_id.in_(active_plan_ids)
            )
        ) or 0
        completed = self.db.execute(
            select(PlanExecution.test_plan_id, TaskBatch.verdict)
            .join(
                TaskBatch,
                TaskBatch.id == PlanExecution.task_batch_id,
            )
            .where(
                PlanExecution.test_plan_id.in_(active_plan_ids),
                TaskBatch.execution_status
                == ExecutionStatus.RESULT_READY,
            )
            .order_by(
                PlanExecution.test_plan_id,
                PlanExecution.created_at.desc(),
                PlanExecution.id.desc(),
            )
        )
        latest_by_plan: dict[str, Verdict | None] = {}
        for plan_id, verdict in completed:
            latest_by_plan.setdefault(plan_id, verdict)
        passing = sum(
            verdict == Verdict.PASS
            for verdict in latest_by_plan.values()
        )
        latest_rate = (
            round(passing / len(latest_by_plan) * 100, 2)
            if latest_by_plan
            else 0.0
        )
        return {
            "active_plan_count": len(active_plan_ids),
            "distinct_case_count": distinct_case_count,
            "execution_count": execution_count,
            "latest_completed_pass_rate": latest_rate,
        }

    def list_cases(
        self,
        plan_id: str,
        page: int,
        page_size: int,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> tuple[list[TestCase], int]:
        if not self.exists_active(plan_id, business_id):
            return [], 0
        total = self.db.scalar(
            select(func.count(TestPlanCase.case_id)).where(
                TestPlanCase.plan_id == plan_id
            )
        ) or 0
        cases = list(
            self.db.scalars(
                select(TestCase)
                .join(
                    TestPlanCase,
                    TestPlanCase.case_id == TestCase.id,
                )
                .where(TestPlanCase.plan_id == plan_id)
                .order_by(TestPlanCase.position)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return cases, total

    def list_bound_plans_for_case(
        self,
        case_id: str,
        page: int,
        page_size: int,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> tuple[list[dict], int]:
        plan_ids = (
            select(TestPlanCase.plan_id).where(
                TestPlanCase.case_id == case_id
            )
        )
        total = self.db.scalar(
            select(func.count(TestPlan.id)).where(
                TestPlan.deleted_at.is_(None),
                TestPlan.business_id == business_id,
                TestPlan.id.in_(plan_ids),
            )
        ) or 0
        rows = self.db.execute(
            select(
                TestPlan,
                func.count(TestPlanCase.case_id).label("case_count"),
            )
            .join(TestPlanCase, TestPlanCase.plan_id == TestPlan.id)
            .where(
                TestPlan.deleted_at.is_(None),
                TestPlan.business_id == business_id,
                TestPlan.id.in_(plan_ids),
            )
            .group_by(TestPlan.id)
            .order_by(TestPlan.updated_at.desc(), TestPlan.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return (
            [
                {
                    "id": plan.id,
                    "name": plan.name,
                    "test_type": self._normalized_test_type(plan.test_type),
                    "case_count": case_count,
                    "has_active_execution": self._has_active_execution(plan.id),
                    "created_by": plan.created_by,
                    "updated_at": plan.updated_at,
                }
                for plan, case_count in rows
            ],
            total,
        )

    def remove_case(
        self,
        plan_id: str,
        case_id: str,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> bool:
        plan = self.get(plan_id, business_id)
        if plan is None:
            return False
        association = next(
            (item for item in plan.cases if item.case_id == case_id),
            None,
        )
        if association is None:
            raise TestPlanCaseNotFoundError("case_not_in_test_plan")
        if len(plan.cases) <= 1:
            raise TestPlanRequiresOneCaseError("test_plan_requires_one_case")
        if self._has_active_execution(plan_id):
            raise TestPlanExecutionActiveError("test_plan_execution_active")

        remaining = [
            item
            for item in sorted(plan.cases, key=lambda item: item.position)
            if item.case_id != case_id
        ]
        plan.cases.remove(association)
        self.db.flush()
        offset = len(remaining) + 1
        for item in remaining:
            item.position += offset
        self.db.flush()
        for position, item in enumerate(remaining):
            item.position = position
        self.db.commit()
        return True

    def response(self, plan: TestPlan) -> TestPlanResponse:
        return self.responses([plan])[0]

    def responses(
        self,
        plans: list[TestPlan],
    ) -> list[TestPlanResponse]:
        if not plans:
            return []

        plan_ids = [plan.id for plan in plans]
        tag_names = list(
            dict.fromkeys(
                tag_name
                for plan in plans
                for tag_name in plan.tags or []
            )
        )
        colors = TagColorService(self.db).get_registered(tag_names)
        execution_counts = dict(
            self.db.execute(
                select(
                    PlanExecution.test_plan_id,
                    func.count(PlanExecution.id),
                )
                .where(PlanExecution.test_plan_id.in_(plan_ids))
                .group_by(PlanExecution.test_plan_id)
            ).all()
        )

        latest_ranked = (
            select(
                PlanExecution.id.label("execution_id"),
                func.row_number()
                .over(
                    partition_by=PlanExecution.test_plan_id,
                    order_by=(
                        PlanExecution.created_at.desc(),
                        PlanExecution.id.desc(),
                    ),
                )
                .label("execution_rank"),
            )
            .where(PlanExecution.test_plan_id.in_(plan_ids))
            .subquery()
        )
        latest_by_plan = {
            execution.test_plan_id: (execution, batch)
            for execution, batch in self.db.execute(
                select(PlanExecution, TaskBatch)
                .join(
                    TaskBatch,
                    TaskBatch.id == PlanExecution.task_batch_id,
                )
                .join(
                    latest_ranked,
                    latest_ranked.c.execution_id == PlanExecution.id,
                )
                .where(latest_ranked.c.execution_rank == 1)
            )
        }

        latest_batch_ids = [
            batch.id for _execution, batch in latest_by_plan.values()
        ]
        schedules_by_plan = {
            row.test_plan_id: row
            for row in self.db.execute(
                select(TestPlanSchedule).where(
                    TestPlanSchedule.test_plan_id.in_(plan_ids)
                )
            ).scalars()
        }
        task_aggregates = {
            batch_id: (passed, failed, exceptional, cancelled, queued, running)
            for (
                batch_id,
                passed,
                failed,
                exceptional,
                cancelled,
                queued,
                running,
            ) in self.db.execute(
                select(
                    Task.batch_id,
                    func.count(Task.id).filter(
                        Task.execution_status == ExecutionStatus.RESULT_READY,
                        Task.verdict == Verdict.PASS
                    ),
                    func.count(Task.id).filter(
                        Task.execution_status == ExecutionStatus.RESULT_READY,
                        Task.verdict == Verdict.FAIL,
                        (
                            Task.failure_type.is_(None)
                            | (Task.failure_type == "assertion_failed")
                        ),
                    ),
                    func.count(Task.id).filter(
                        Task.execution_status == ExecutionStatus.RESULT_READY,
                        Task.verdict == Verdict.FAIL,
                        Task.failure_type.is_not(None),
                        Task.failure_type != "assertion_failed",
                    ),
                    func.count(Task.id).filter(
                        Task.execution_status == ExecutionStatus.CANCELLED
                    ),
                    func.count(Task.id).filter(
                        Task.execution_status == ExecutionStatus.QUEUED
                    ),
                    func.count(Task.id).filter(
                        Task.execution_status == ExecutionStatus.RUNNING
                    ),
                )
                .where(Task.batch_id.in_(latest_batch_ids))
                .group_by(Task.batch_id)
            )
        }

        responses = []
        for plan in plans:
            latest_row = latest_by_plan.get(plan.id)
            latest = None
            if latest_row is not None:
                execution, batch = latest_row
                (
                    passed,
                    failed,
                    exceptional,
                    cancelled,
                    queued,
                    running,
                ) = task_aggregates.get(
                    batch.id,
                    (0, 0, 0, 0, 0, 0),
                )
                latest = self._latest_execution_response(
                    execution,
                    batch,
                    passed=passed,
                    failed=failed,
                    exceptional=exceptional,
                    cancelled=cancelled,
                    queued=queued,
                    running=running,
                )
            schedule_row = schedules_by_plan.get(plan.id)
            schedule = None
            if schedule_row is not None:
                schedule = ScheduleSummaryResponse(
                    enabled=schedule_row.enabled,
                    cron_expr=schedule_row.cron_expr,
                    next_run_at=schedule_row.next_run_at,
                    last_run_at=schedule_row.last_run_at,
                )
            responses.append(
                TestPlanResponse(
                    id=plan.id,
                    name=plan.name,
                    description=plan.description,
                    test_type=self._normalized_test_type(plan.test_type),
                    tags=[
                        TagResponse(
                            name=tag_name,
                            foreground_color=colors[
                                tag_name
                            ].foreground_color,
                            background_color=colors[
                                tag_name
                            ].background_color,
                        )
                        for tag_name in plan.tags or []
                    ],
                    case_ids=[
                        association.case_id
                        for association in plan.cases
                    ],
                    case_count=len(plan.cases),
                    execution_count=execution_counts.get(plan.id, 0),
                    latest_execution=latest,
                    schedule=schedule,
                    created_by=plan.created_by,
                    created_at=plan.created_at,
                    updated_at=plan.updated_at,
                )
            )
        return responses

    def _normalized_test_type(self, value: str | None) -> str:
        return "new_feature" if value == "new_feature" else "regression"

    def _test_type_filter(self, value: str):
        if value == "new_feature":
            return TestPlan.test_type == "new_feature"
        return or_(
            TestPlan.test_type == "regression",
            TestPlan.test_type.is_(None),
            TestPlan.test_type == "",
        )

    def _has_active_execution(self, plan_id: str) -> bool:
        return self.db.scalar(
            select(PlanExecution.id)
            .join(TaskBatch, TaskBatch.id == PlanExecution.task_batch_id)
            .where(
                PlanExecution.test_plan_id == plan_id,
                TaskBatch.execution_status.in_(
                    (
                        ExecutionStatus.SCRIPT_PENDING,
                        ExecutionStatus.QUEUED,
                        ExecutionStatus.RUNNING,
                    )
                ),
            )
            .limit(1)
        ) is not None

    def _required(
        self,
        plan_id: str,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> TestPlan:
        self.db.expire_all()
        plan = self.get(plan_id, business_id)
        if plan is None:
            raise RuntimeError(f"test plan disappeared: {plan_id}")
        return plan

    def _require_cases(
        self,
        case_ids: list[str],
        business_id: str,
    ) -> list[TestCase]:
        cases = list(
            self.db.scalars(
                select(TestCase).where(
                    TestCase.id.in_(case_ids),
                    TestCase.business_id == business_id,
                    TestCase.deleted_at.is_(None),
                )
            )
        )
        case_by_id = {case.id: case for case in cases}
        missing = [
            case_id for case_id in case_ids if case_id not in case_by_id
        ]
        if missing:
            raise TestPlanCasesNotFoundError(missing)
        return [case_by_id[case_id] for case_id in case_ids]

    def _require_available_name(
        self,
        name: str,
        *,
        exclude_plan_id: str | None = None,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> None:
        query = select(TestPlan.id).where(
            TestPlan.name_key == name.casefold(),
            TestPlan.business_id == business_id,
            TestPlan.deleted_at.is_(None),
        )
        if exclude_plan_id is not None:
            query = query.where(TestPlan.id != exclude_plan_id)
        if self.db.scalar(query.limit(1)) is not None:
            raise TestPlanNameConflictError(
                "test_plan_name_conflict"
            )

    def _latest_execution_response(
        self,
        execution: PlanExecution,
        batch: TaskBatch,
        *,
        passed: int,
        failed: int,
        exceptional: int,
        cancelled: int,
        queued: int,
        running: int,
    ) -> LatestPlanExecutionResponse:
        denominator = len(execution.case_ids_snapshot)
        pass_rate = (
            round(passed / denominator * 100, 2)
            if denominator
            else 0.0
        )
        return LatestPlanExecutionResponse(
            execution_id=execution.id,
            task_batch_id=batch.id,
            report_status=self._report_status(
                batch,
                passed=passed,
                failed=failed,
                exceptional=exceptional,
                cancelled=cancelled,
                queued=queued,
                running=running,
                total=denominator,
            ),
            pass_rate=pass_rate,
            created_at=execution.created_at,
        )

    def _report_status(
        self,
        batch: TaskBatch,
        *,
        passed: int = 0,
        failed: int = 0,
        exceptional: int = 0,
        cancelled: int = 0,
        queued: int = 0,
        running: int = 0,
        total: int = 0,
    ) -> str:
        effective = effective_report_status(
            batch.execution_status.value,
            batch.verdict.value if batch.verdict is not None else None,
            pass_count=passed,
            fail_count=failed,
            exception_count=exceptional,
            cancelled_count=cancelled,
            queued_count=queued,
            running_count=running,
            total_count=total,
        )
        if effective is not None:
            return effective
        if batch.execution_status == ExecutionStatus.QUEUED:
            return "queued"
        if batch.execution_status == ExecutionStatus.RUNNING:
            return "running"
        if batch.execution_status == ExecutionStatus.CANCELLED:
            return "cancelled"
        if batch.verdict == Verdict.PASS:
            return "success"
        return "exception" if exceptional else "failure"
