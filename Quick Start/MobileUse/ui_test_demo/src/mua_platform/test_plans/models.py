from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mua_platform.db import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class TestPlan(Base):
    __tablename__ = "test_plans"
    __table_args__ = (
        Index(
            "uq_active_test_plan_name_key",
            "name_key",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    business_id: Mapped[str] = mapped_column(
        String(40),
        default="biz_default",
        server_default="biz_default",
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100))
    name_key: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_type: Mapped[str] = mapped_column(String(32), default="regression")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    cases: Mapped[list["TestPlanCase"]] = relationship(
        cascade="all, delete-orphan",
        order_by="TestPlanCase.position",
    )


class TestPlanCase(Base):
    __tablename__ = "test_plan_cases"
    __table_args__ = (
        UniqueConstraint("plan_id", "case_id"),
        UniqueConstraint("plan_id", "position"),
    )

    plan_id: Mapped[str] = mapped_column(
        ForeignKey("test_plans.id"),
        primary_key=True,
    )
    case_id: Mapped[str] = mapped_column(
        ForeignKey("test_cases.id"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer)


class PlanExecution(Base):
    __tablename__ = "plan_executions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    business_id: Mapped[str] = mapped_column(
        String(40),
        default="biz_default",
        server_default="biz_default",
        index=True,
    )
    test_plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("test_plans.id"),
        nullable=True,
        index=True,
    )
    task_batch_id: Mapped[str] = mapped_column(
        ForeignKey("task_batches.id"),
        unique=True,
        index=True,
    )
    plan_name_snapshot: Mapped[str] = mapped_column(String(100))
    plan_tags_snapshot: Mapped[list[str]] = mapped_column(JSON, default=list)
    case_ids_snapshot: Mapped[list[str]] = mapped_column(JSON)
    device_strategy_snapshot: Mapped[str] = mapped_column(String(32))
    pod_ids_snapshot: Mapped[list[str]] = mapped_column(JSON, default=list)
    concurrency_snapshot: Mapped[int] = mapped_column(Integer)
    runner_type_snapshot: Mapped[str] = mapped_column(String(32))
    config_snapshot: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )


class TagColorRegistry(Base):
    __tablename__ = "tag_color_registry"

    tag_name: Mapped[str] = mapped_column(String(32), primary_key=True)
    foreground_color: Mapped[str] = mapped_column(String(7), unique=True)
    background_color: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )


class TestPlanSchedule(Base):
    __tablename__ = "test_plan_schedules"
    __table_args__ = (
        Index("ix_schedule_enabled_next_run", "enabled", "next_run_at"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    business_id: Mapped[str] = mapped_column(
        String(40),
        default="biz_default",
        server_default="biz_default",
        index=True,
    )
    test_plan_id: Mapped[str] = mapped_column(
        ForeignKey("test_plans.id"),
        unique=True,
        index=True,
    )
    cron_expr: Mapped[str] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="1",
    )
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_skip_reason: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    execution_config: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class ScheduleEvent(Base):
    __tablename__ = "schedule_events"
    __table_args__ = (
        Index("ix_schedule_events_schedule_created", "schedule_id", "created_at"),
        Index("ix_schedule_events_business_created", "business_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    schedule_id: Mapped[str] = mapped_column(
        ForeignKey("test_plan_schedules.id", ondelete="CASCADE"),
        index=True,
    )
    business_id: Mapped[str] = mapped_column(
        String(40),
        default="biz_default",
        server_default="biz_default",
    )
    event_type: Mapped[str] = mapped_column(String(20))
    trigger_type: Mapped[str] = mapped_column(String(20))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    plan_execution_id: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )
    skip_reason: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
