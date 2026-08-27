from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cua_platform.cases.models import TestCase as CaseModel
from cua_platform.db import Base
from cua_platform.pods.models import DiscoveredPod
from cua_platform.pods.repository import PodRepository
from cua_platform.pods.schemas import ListPodPage, PodSummary
from cua_platform.runners.base import PollResult, RunHandle, RunnerEvent
from cua_platform.tasks.models import PodLease, Task, TaskRunnerConfig
from cua_platform.tasks.repository import SQLiteTaskRepository
from cua_platform.tasks.service import TaskService
from cua_platform.tasks.state_machine import ExecutionStatus, StartState
from cua_platform.time import FakeClock


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


def _pod_summary(pod_id: str, pod_name: str) -> PodSummary:
    return PodSummary(
        product_id="2103274899",
        pod_id=pod_id,
        pod_name=pod_name,
        pod_status_code=2,
        stream_status=None,
        image_id=None,
        image_name=None,
        aosp_version=None,
        display_layout_id=None,
        dc_id=None,
        dc_name=None,
        isp_code=None,
        region=None,
        zone_id=None,
        config_code=None,
        config_name=None,
        config_type=None,
        server_type_code=None,
        intranet_ip=None,
        adb_address=None,
        adb_status=None,
        data_size=None,
        data_size_used=None,
        pod_created_at=None,
    )


def test_pool_snapshot_treats_unexpired_lease_as_authoritative():
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
                pod_status_code=2,
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
            assert after_cancel.items[0].local_state == "leased"
            assert after_cancel.items[0].task_id == task.id

            lease.expires_at = now - timedelta(seconds=1)
            db.commit()
            after_expiry = PodRepository(db).list_snapshot("product_sync", now=now)
            assert after_expiry.items[0].local_state == "available"
            assert after_expiry.items[0].task_id is None
    finally:
        engine.dispose()


def test_pool_snapshot_preserves_cua_node_fields():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    try:
        with Session(engine, expire_on_commit=False) as db:
            PodRepository(db).sync(
                "2103274899",
                ListPodPage(
                    items=(
                        PodSummary(
                            product_id="2103274899",
                            pod_id="i-yemj9hi22oxjd1yy592l",
                            pod_name="grafana",
                            pod_status_code=6,
                            stream_status=None,
                            image_id="image-yd6lmly69fgqeeqfvixc",
                            image_name="veLinux 2.0 CentOS Compatible 64 bit",
                            aosp_version=None,
                            display_layout_id=None,
                            dc_id=None,
                            dc_name=None,
                            isp_code=None,
                            region="cn-beijing",
                            zone_id="cn-beijing-d",
                            config_code="ecs.g4i.2xlarge",
                            config_name="ecs.g4i.2xlarge 8vCPU 32GiB",
                            config_type=None,
                            server_type_code="ecs.g4i.2xlarge",
                            intranet_ip="10.1.3.3",
                            adb_address=None,
                            adb_status=None,
                            data_size=None,
                            data_size_used=None,
                            pod_created_at=None,
                            eip_address="124.174.97.147",
                            node_id=144,
                            provider="volc_ecs",
                            project_name="default",
                            public_ip="124.174.97.147",
                            os_type="linux",
                            os_name="veLinux 2.0 CentOS Compatible 64 bit",
                            instance_type="ecs.g4i.2xlarge",
                            vcpu=8,
                            memory_gib=32,
                            specification="ecs.g4i.2xlarge 8vCPU 32GiB",
                            agent_endpoint="http://124.174.97.147:8910",
                            plugin_version="0.0.5",
                            script_version="0.0.5",
                            status_name="升级失败",
                            status_message="upgrade failed",
                            last_heartbeat_at=None,
                            node_updated_at=None,
                        ),
                    ),
                    next_token=None,
                    request_id="req-cua-cache",
                ),
                seen_at=now,
            )

            item = PodRepository(db).list_snapshot("2103274899", now=now).items[0]

            assert item.public_ip == "124.174.97.147"
            assert item.eip_address == "124.174.97.147"
            assert item.provider == "volc_ecs"
            assert item.plugin_version == "0.0.5"
            assert item.script_version == "0.0.5"
            assert item.project_name == "default"
            assert item.agent_endpoint == "http://124.174.97.147:8910"
            assert item.status_name == "升级失败"
    finally:
        engine.dispose()


def test_pod_sync_removes_nodes_missing_from_latest_cua_snapshot():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    try:
        with Session(engine, expire_on_commit=False) as db:
            repository = PodRepository(db)
            repository.sync(
                "2103274899",
                ListPodPage(
                    items=(
                        _pod_summary("i-old", "old node"),
                        _pod_summary("i-current", "current node"),
                    ),
                    next_token=None,
                    request_id="req-first",
                ),
                seen_at=now,
            )

            repository.sync(
                "2103274899",
                ListPodPage(
                    items=(
                        _pod_summary("i-current", "current node"),
                    ),
                    next_token=None,
                    request_id="req-second",
                ),
                seen_at=now + timedelta(minutes=1),
            )

            snapshot = repository.list_snapshot("2103274899", now=now + timedelta(minutes=1))

            assert [item.pod_id for item in snapshot.items] == ["i-current"]
            assert repository.get("2103274899", "i-old") is None
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
                    "account_id": "account_timeout",
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
                start_state=StartState.ATTACHED,
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
