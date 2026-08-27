from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from mua_platform.cases.models import TestCase as CaseModel
from mua_platform.db import Base
from mua_platform.pods.models import DiscoveredPod
from mua_platform.pods.repository import PodRepository
from mua_platform.runners.base import PollResult, RunHandle, RunnerEvent
from mua_platform.tasks.models import PodLease, Task, TaskRunnerConfig
from mua_platform.tasks.repository import SQLiteTaskRepository
from mua_platform.tasks.service import TaskService
from mua_platform.tasks.state_machine import ExecutionStatus
from mua_platform.time import FakeClock


class TerminalRunner:
    async def poll(self, handle: RunHandle, after_sequence: int) -> PollResult:
        return PollResult(
            events=(
                RunnerEvent(1, "task_started", {"task_id": handle.task_id}),
                RunnerEvent(
                    2,
                    "task_finished",
                    {"verdict": "pass", "evidence_complete": True},
                ),
            ),
            terminal=True,
        )


def test_pool_snapshot_maps_queued_task_from_product_scoped_lease_key():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    try:
        with Session(engine, expire_on_commit=False) as db:
            case = CaseModel(
                id="case_sync",
                title="设备同步用例",
                module=None,
                content_markdown="## 执行任务\n验证设备状态",
                tags=[],
                automation_level="auto",
                created_by="admin",
            )
            pod = DiscoveredPod(
                id="pod_row_sync",
                product_id="product_sync",
                pod_id="pod_sync",
                pod_name="同步云机",
                pod_status_code=1,
                discovery_state="active",
                last_seen_at=now,
            )
            task = Task(
                id="task_sync",
                case_id=case.id,
                script_version_id=None,
                prompt_snapshot=case.content_markdown,
                runner_type="mobile_use",
                scenario="验证设备同步",
                created_by="admin",
                execution_status=ExecutionStatus.QUEUED,
                idempotency_key="sync-key",
                request_fingerprint="{}",
                version=1,
            )
            lease = PodLease(
                pod_id="product_sync:pod_sync",
                task_id=task.id,
                worker_id="reserved",
                expires_at=now + timedelta(minutes=5),
                version=1,
            )
            db.add_all([case, pod, task, lease])
            db.commit()

            snapshot = PodRepository(db).list_snapshot("product_sync", now=now)

            item = snapshot.items[0]
            assert item.local_state == "leased"
            assert item.task_id == task.id
            assert item.task_status == "queued"
            assert item.task_scenario == "验证设备同步"

            task.execution_status = ExecutionStatus.CANCELLED
            db.commit()

            after_cancel = PodRepository(db).list_snapshot("product_sync", now=now)
            assert after_cancel.items[0].local_state == "available"
            assert after_cancel.items[0].task_id is None
    finally:
        engine.dispose()


def test_claim_does_not_set_local_execution_deadline():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 28, 3, 0, tzinfo=UTC)
    try:
        with Session(engine, expire_on_commit=False) as db:
            case = CaseModel(
                id="case_timeout",
                title="超时用例",
                module=None,
                content_markdown="## 执行任务\n验证超时",
                tags=[],
                automation_level="auto",
                created_by="admin",
            )
            task = Task(
                id="task_timeout",
                case_id=case.id,
                script_version_id=None,
                prompt_snapshot=case.content_markdown,
                runner_type="mobile_use",
                scenario="验证超时",
                created_by="admin",
                execution_status=ExecutionStatus.QUEUED,
                idempotency_key="timeout-key",
                request_fingerprint="{}",
                version=1,
            )
            config = TaskRunnerConfig(
                task_id=task.id,
                config_snapshot={
                    "pod_id": "pod_timeout",
                    "product_id": "product_timeout",
                    "timeout_seconds": 1800,
                },
            )
            db.add_all([case, task, config])
            db.commit()

            claimed = SQLiteTaskRepository(db).claim(
                task.id,
                "worker:default",
                now,
                timedelta(seconds=30),
                execution_timeout=timedelta(seconds=600),
            )

            assert claimed is not None
            assert claimed.deadline_at is None
            assert claimed.runner_config_snapshot["timeout_seconds"] == 1800
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_running_task_renews_its_pod_lease_before_remote_poll(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 28, 3, 0, tzinfo=UTC)
    try:
        with Session(engine, expire_on_commit=False) as db:
            case = CaseModel(
                id="case_renew",
                title="租约续期用例",
                module=None,
                content_markdown="## 执行任务\n验证租约续期",
                tags=[],
                automation_level="auto",
                created_by="admin",
            )
            task = Task(
                id="task_renew",
                case_id=case.id,
                script_version_id=None,
                prompt_snapshot=case.content_markdown,
                runner_type="mobile_use",
                scenario="验证租约续期",
                created_by="admin",
                execution_status=ExecutionStatus.RUNNING,
                idempotency_key="renew-key",
                request_fingerprint="{}",
                remote_run_id="run_renew",
                deadline_at=now - timedelta(seconds=1),
                version=1,
            )
            lease = PodLease(
                pod_id="product_sync:pod_sync",
                task_id=task.id,
                worker_id="worker:default",
                expires_at=now + timedelta(seconds=30),
                version=1,
            )
            db.add_all([case, task, lease])
            db.commit()

            repository = SQLiteTaskRepository(db)
            original_renew_lease = repository.renew_lease
            renewed_task_ids: list[str] = []

            def renew_lease(task_id, worker_id, renewed_at, lease_ttl):
                renewed_task_ids.append(task_id)
                return original_renew_lease(task_id, worker_id, renewed_at, lease_ttl)

            monkeypatch.setattr(repository, "renew_lease", renew_lease)
            completed = await TaskService(
                repository,
                TerminalRunner(),
                clock=FakeClock(now),
            ).execute_or_resume(task.id, worker_id="worker:default")

            assert renewed_task_ids == [task.id]
            assert completed.execution_status == ExecutionStatus.RESULT_READY
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_startup_recovery_takes_over_expired_running_lease():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 29, 4, 0, tzinfo=UTC)
    try:
        with Session(engine, expire_on_commit=False) as db:
            case = CaseModel(
                id="case_recover_lease",
                title="恢复租约用例",
                module=None,
                content_markdown="## 执行任务\n验证恢复",
                tags=[],
                automation_level="auto",
                created_by="admin",
            )
            task = Task(
                id="task_recover_lease",
                case_id=case.id,
                runner_type="mobile_use",
                scenario="恢复租约",
                created_by="admin",
                execution_status=ExecutionStatus.RUNNING,
                idempotency_key="recover-lease",
                request_fingerprint="{}",
                remote_run_id="run_recover",
                deadline_at=now + timedelta(minutes=10),
                version=1,
            )
            lease = PodLease(
                pod_id="product_sync:pod_sync",
                task_id=task.id,
                worker_id="worker:old",
                expires_at=now - timedelta(seconds=1),
                version=1,
            )
            db.add_all([case, task, lease])
            db.commit()

            recovered = await TaskService(
                SQLiteTaskRepository(db),
                None,
                clock=FakeClock(now),
            ).recover_startup(now)

            db.refresh(lease)
            assert recovered == [task.id]
            assert lease.worker_id == "worker:default"
            assert lease.expires_at.replace(tzinfo=UTC) > now
            assert lease.version == 2
    finally:
        engine.dispose()
