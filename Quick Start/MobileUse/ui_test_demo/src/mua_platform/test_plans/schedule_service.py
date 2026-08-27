from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mua_platform.business.models import DEFAULT_BUSINESS_ID
from mua_platform.test_plans.models import (
    ScheduleEvent,
    TestPlan,
    TestPlanSchedule,
)
from mua_platform.test_plans.scheduling import compute_next_run
from mua_platform.test_plans.schemas import (
    TestPlanScheduleCreate,
    TestPlanScheduleUpdate,
)


class ScheduleNotFoundError(ValueError):
    pass


class ScheduleAlreadyExistsError(ValueError):
    pass


class ScheduleService:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        plan_id: str,
        payload: TestPlanScheduleCreate,
        *,
        created_by: str,
        now: datetime | None = None,
        business_id: str = DEFAULT_BUSINESS_ID,
    ) -> TestPlanSchedule:
        plan = self.db.scalar(
            select(TestPlan).where(
                TestPlan.id == plan_id,
                TestPlan.business_id == business_id,
            )
        )
        if plan is None:
            raise ScheduleNotFoundError("test_plan_not_found")

        existing = self.db.scalar(
            select(TestPlanSchedule).where(
                TestPlanSchedule.test_plan_id == plan_id
            )
        )
        if existing is not None:
            raise ScheduleAlreadyExistsError("schedule_already_exists")

        now = now or datetime.now(UTC)
        next_run = compute_next_run(payload.cron_expr, payload.timezone, now)

        schedule = TestPlanSchedule(
            id=f"schedule_{uuid4().hex}",
            business_id=business_id,
            test_plan_id=plan_id,
            cron_expr=payload.cron_expr,
            timezone=payload.timezone,
            enabled=payload.enabled,
            next_run_at=next_run,
            execution_config=payload.execution_config.model_dump(),
            created_by=created_by,
        )
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def get(self, plan_id: str) -> TestPlanSchedule | None:
        return self.db.scalar(
            select(TestPlanSchedule).where(
                TestPlanSchedule.test_plan_id == plan_id
            )
        )

    def get_by_id(self, schedule_id: str) -> TestPlanSchedule | None:
        return self.db.get(TestPlanSchedule, schedule_id)

    def update(
        self,
        plan_id: str,
        payload: TestPlanScheduleUpdate | None = None,
        **kwargs: Any,
    ) -> TestPlanSchedule:
        schedule = self.get(plan_id)
        if schedule is None:
            raise ScheduleNotFoundError("schedule_not_found")

        if payload is not None:
            fields = payload.model_dump(exclude_none=True)
        else:
            fields = kwargs

        needs_recalc = "cron_expr" in fields or "timezone" in fields

        if "execution_config" in fields:
            value = fields["execution_config"]
            if hasattr(value, "model_dump"):
                fields["execution_config"] = value.model_dump()

        for key, value in fields.items():
            setattr(schedule, key, value)

        if needs_recalc:
            schedule.next_run_at = compute_next_run(
                schedule.cron_expr,
                schedule.timezone,
                datetime.now(UTC),
            )

        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def set_enabled(
        self,
        plan_id: str,
        enabled: bool,
        *,
        now: datetime | None = None,
    ) -> TestPlanSchedule:
        schedule = self.get(plan_id)
        if schedule is None:
            raise ScheduleNotFoundError("schedule_not_found")
        schedule.enabled = enabled
        if enabled:
            schedule.next_run_at = compute_next_run(
                schedule.cron_expr,
                schedule.timezone,
                now or datetime.now(UTC),
            )
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def delete(self, plan_id: str) -> bool:
        schedule = self.get(plan_id)
        if schedule is None:
            return False
        self.db.delete(schedule)
        self.db.commit()
        return True

    def claim_due(self, now: datetime) -> list[TestPlanSchedule]:
        return list(
            self.db.scalars(
                select(TestPlanSchedule)
                .where(
                    TestPlanSchedule.enabled.is_(True),
                    TestPlanSchedule.next_run_at <= (now.replace(tzinfo=None) if now.tzinfo else now),
                )
                .order_by(TestPlanSchedule.next_run_at)
            )
        )

    def advance_next_run(
        self,
        schedule: TestPlanSchedule,
        now: datetime,
    ) -> TestPlanSchedule:
        schedule.next_run_at = compute_next_run(
            schedule.cron_expr,
            schedule.timezone,
            now,
        )
        schedule.last_run_at = now
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def record_event(
        self,
        schedule: TestPlanSchedule,
        *,
        event_type: str,
        trigger_type: str,
        scheduled_for: datetime,
        fired_at: datetime,
        plan_execution_id: str | None = None,
        skip_reason: str | None = None,
        error_message: str | None = None,
    ) -> ScheduleEvent:
        event = ScheduleEvent(
            id=f"event_{uuid4().hex}",
            schedule_id=schedule.id,
            business_id=schedule.business_id,
            event_type=event_type,
            trigger_type=trigger_type,
            scheduled_for=scheduled_for,
            fired_at=fired_at,
            plan_execution_id=plan_execution_id,
            skip_reason=skip_reason,
            error_message=error_message,
        )
        self.db.add(event)
        if skip_reason is not None:
            schedule.last_skip_reason = skip_reason
        self.db.commit()
        self.db.refresh(event)
        return event

    def list_events(
        self,
        plan_id: str,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ScheduleEvent], int]:
        schedule = self.get(plan_id)
        if schedule is None:
            return [], 0
        total = (
            self.db.scalar(
                select(func.count(ScheduleEvent.id)).where(
                    ScheduleEvent.schedule_id == schedule.id
                )
            )
            or 0
        )
        events = list(
            self.db.scalars(
                select(ScheduleEvent)
                .where(ScheduleEvent.schedule_id == schedule.id)
                .order_by(ScheduleEvent.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return events, total
