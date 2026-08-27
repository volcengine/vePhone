from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cua_platform.db import Base
from cua_platform.tasks.execution_config import public_execution_config
from cua_platform.tasks.state_machine import ExecutionStatus, StartState, Verdict


def utc_now() -> datetime:
    return datetime.now(UTC)


class TaskBatch(Base):
    __tablename__ = "task_batches"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    business_id: Mapped[str] = mapped_column(
        String(40),
        default="biz_default",
        server_default="biz_default",
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200))
    test_type: Mapped[str] = mapped_column(String(32))
    selection_mode: Mapped[str] = mapped_column(String(32))
    selection_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    device_strategy: Mapped[str] = mapped_column(String(32))
    pod_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    concurrency: Mapped[int] = mapped_column(Integer)
    device_wait_timeout_seconds: Mapped[int] = mapped_column(Integer, default=300)
    runner_type: Mapped[str] = mapped_column(String(32), default="mobile_use")
    config_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    execution_status: Mapped[ExecutionStatus] = mapped_column(
        Enum(
            ExecutionStatus,
            native_enum=False,
            values_callable=lambda values: [value.value for value in values],
        ),
        default=ExecutionStatus.QUEUED,
    )
    verdict: Mapped[Verdict | None] = mapped_column(
        Enum(
            Verdict,
            native_enum=False,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True)
    request_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), default="system")
    unavailable_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="batch",
        order_by="Task.batch_position",
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    business_id: Mapped[str] = mapped_column(
        String(40),
        default="biz_default",
        server_default="biz_default",
        index=True,
    )
    case_id: Mapped[str] = mapped_column(ForeignKey("test_cases.id"), index=True)
    batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("task_batches.id"),
        index=True,
        nullable=True,
    )
    batch_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queue_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    script_version_id: Mapped[str | None] = mapped_column(
        String(40),
        index=True,
        nullable=True,
    )
    prompt_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_evidence: Mapped[list[str]] = mapped_column(JSON, default=list)
    runner_type: Mapped[str] = mapped_column(String(32), default="mock")
    scenario: Mapped[str] = mapped_column(String(32))
    created_by: Mapped[str] = mapped_column(String(100), default="system")
    execution_status: Mapped[ExecutionStatus] = mapped_column(
        Enum(
            ExecutionStatus,
            native_enum=False,
            values_callable=lambda values: [value.value for value in values],
        ),
        default=ExecutionStatus.QUEUED,
    )
    verdict: Mapped[Verdict | None] = mapped_column(
        Enum(
            Verdict,
            native_enum=False,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=True,
    )
    review_result: Mapped[Verdict | None] = mapped_column(
        Enum(
            Verdict,
            native_enum=False,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=True,
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    request_fingerprint: Mapped[str] = mapped_column(String)
    remote_run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    remote_thread_id: Mapped[str | None] = mapped_column(String, nullable=True)
    remote_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remote_step_id: Mapped[str | None] = mapped_column(String, nullable=True)
    recording_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_assets: Mapped[dict] = mapped_column(JSON, default=dict)
    start_idempotency_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    start_state: Mapped[StartState] = mapped_column(
        Enum(
            StartState,
            native_enum=False,
            values_callable=lambda values: [value.value for value in values],
        ),
        default=StartState.PENDING,
        server_default=StartState.PENDING.value,
    )
    start_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_polled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    events: Mapped[list["TaskEvent"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskEvent.sequence",
    )
    steps: Mapped[list["TaskStep"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskStep.step_index",
    )
    runner_config: Mapped["TaskRunnerConfig | None"] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        uselist=False,
    )
    batch: Mapped[TaskBatch | None] = relationship(back_populates="tasks")

    @property
    def runner_config_snapshot(self) -> dict:
        if self.runner_config is None:
            return {"pod_id": "mock:default"}
        return self.runner_config.config_snapshot

    @property
    def execution_config(self) -> dict:
        return public_execution_config(self.runner_config_snapshot)

    @property
    def display_task_id(self) -> str:
        return self.batch_id or self.id

    @property
    def source_type(self) -> str:
        return "multi_cases" if self.batch_id else "single_case"


class TaskRunnerConfig(Base):
    __tablename__ = "task_runner_configs"

    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id"),
        primary_key=True,
    )
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)

    task: Mapped[Task] = relationship(back_populates="runner_config")


class PodLease(Base):
    __tablename__ = "pod_leases"
    __table_args__ = (
        UniqueConstraint("task_id", name="unique_pod_lease_task"),
    )

    pod_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))
    worker_id: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)


class TaskEvent(Base):
    __tablename__ = "task_events"
    __table_args__ = (
        UniqueConstraint("task_id", "sequence", name="unique_task_event_sequence"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )

    task: Mapped[Task] = relationship(back_populates="events")


class TaskStep(Base):
    __tablename__ = "task_steps"
    __table_args__ = (
        UniqueConstraint("task_id", "step_index", name="unique_task_step_index"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    step_index: Mapped[int] = mapped_column(Integer)
    instruction: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(32))
    assertion_result: Mapped[str | None] = mapped_column(String(32), nullable=True)
    logs: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    task: Mapped[Task] = relationship(back_populates="steps")
