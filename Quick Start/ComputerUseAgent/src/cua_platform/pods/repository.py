import logging
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from cua_platform.pods.models import (
    POD_STATUS_ABNORMAL,
    POD_STATUS_RUNNING,
    DiscoveredPod,
    PodPoolRefresh,
)
from cua_platform.pods.schemas import PodDetail, PodPoolItem, PodPoolSnapshot, PodSummary
from cua_platform.tasks.models import PodLease, Task

logger = logging.getLogger(__name__)

_FRESH_WINDOW_SECONDS = 180
_FAILURE_LIMIT = 3
_FAILURE_COOLDOWN_SECONDS = 300

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _lease_keys(product_id: str, pod_id: str) -> tuple[str, str]:
    return (pod_id, f"{product_id}:{pod_id}")


def _active_task_for_pod_stmt(product_id: str, pod_id: str) -> Any:
    return (
        select(Task)
        .join(PodLease, PodLease.task_id == Task.id)
        .where(
            PodLease.pod_id.in_(_lease_keys(product_id, pod_id)),
            PodLease.expires_at > utc_now(),
        )
        .limit(1)
    )


def _active_tasks_for_pods_stmt(lease_keys: list[str]) -> Any:
    return (
        select(Task, PodLease.pod_id)
        .join(PodLease, PodLease.task_id == Task.id)
        .where(
            PodLease.pod_id.in_(lease_keys),
            PodLease.expires_at > utc_now(),
        )
    )


class PodRepository:
    def __init__(self, db: "Session") -> None:
        self.db = db

    def get(self, product_id: str, pod_id: str) -> DiscoveredPod | None:
        return self.db.scalar(
            select(DiscoveredPod).where(
                DiscoveredPod.product_id == product_id,
                DiscoveredPod.pod_id == pod_id,
            )
        )

    def get_by_db_id(self, pod_db_id: str) -> DiscoveredPod | None:
        return self.db.scalar(select(DiscoveredPod).where(DiscoveredPod.id == pod_db_id))

    def find_available(self, product_id: str) -> DiscoveredPod | None:
        now = utc_now()
        candidates = list(
            self.db.scalars(
                select(DiscoveredPod)
                .where(
                    DiscoveredPod.product_id == product_id,
                    DiscoveredPod.discovery_state == "active",
                    DiscoveredPod.pod_status_code == POD_STATUS_RUNNING,
                )
                .order_by(DiscoveredPod.last_assigned_at.asc().nullsfirst())
            )
        )
        for row in candidates:
            if row.cooldown_until is not None and row.cooldown_until > now:
                continue
            active_task = self.db.scalar(
                _active_task_for_pod_stmt(row.product_id, row.pod_id)
            )
            if active_task is not None:
                continue
            return row
        return None

    def list_allocation_candidates(self, product_id: str, *, now: datetime | None = None) -> list[DiscoveredPod]:
        now = now or utc_now()
        rows = list(
            self.db.scalars(
                select(DiscoveredPod)
                .where(
                    DiscoveredPod.product_id == product_id,
                    DiscoveredPod.discovery_state == "active",
                    DiscoveredPod.pod_status_code == POD_STATUS_RUNNING,
                )
                .order_by(DiscoveredPod.last_assigned_at.asc().nullsfirst())
            )
        )
        available: list[DiscoveredPod] = []
        for row in rows:
            if row.cooldown_until is not None and row.cooldown_until > now:
                continue
            if self.db.scalar(
                _active_task_for_pod_stmt(row.product_id, row.pod_id)
            ) is not None:
                continue
            available.append(row)
        return available

    def list_pool(self, product_id: str) -> PodPoolSnapshot:
        now = utc_now()
        return self._list_pool_at(product_id, now)

    def list_snapshot(self, product_id: str, *, now: datetime | None = None) -> PodPoolSnapshot:
        return self._list_pool_at(product_id, now or utc_now())

    def _list_pool_at(self, product_id: str, now: datetime) -> PodPoolSnapshot:
        refresh = self.db.scalar(
            select(PodPoolRefresh).where(PodPoolRefresh.product_id == product_id)
        )
        refreshed_at = refresh.refreshed_at if refresh is not None else None
        rows = list(
            self.db.scalars(
                select(DiscoveredPod)
                .where(DiscoveredPod.product_id == product_id)
                .order_by(
                    DiscoveredPod.pod_status_code.asc(),
                    DiscoveredPod.pod_name.asc(),
                )
            )
        )
        pod_by_lease_key = {
            lease_key: row.pod_id
            for row in rows
            for lease_key in _lease_keys(row.product_id, row.pod_id)
        }
        task_by_pod: dict[str, Task] = {}
        if pod_by_lease_key:
            task_rows = self.db.execute(
                _active_tasks_for_pods_stmt(list(pod_by_lease_key))
            ).all()
            for task, lease_key in task_rows:
                pod_id = pod_by_lease_key.get(lease_key)
                if pod_id is not None:
                    task_by_pod[pod_id] = task
        items = tuple(
            self._to_pool_item(row, task_by_pod.get(row.pod_id), now)
            for row in rows
        )
        return PodPoolSnapshot(items=items, refreshed_at=refreshed_at)

    def get_pool_item(self, pod_db_id: str) -> PodPoolItem | None:
        row = self.get_by_db_id(pod_db_id)
        if row is None:
            return None
        now = utc_now()
        task = self.db.scalar(_active_task_for_pod_stmt(row.product_id, row.pod_id))
        return self._to_pool_item(row, task, now)

    def get_detail(self, product_id: str, pod_id: str) -> tuple[DiscoveredPod | None, PodDetail | None]:
        row = self.get(product_id, pod_id)
        if row is None:
            return None, None
        detail = PodDetail(
            product_id=row.product_id,
            pod_id=row.pod_id,
            pod_name=row.pod_name,
            pod_status_code=row.pod_status_code,
            stream_status=row.stream_status,
            image_id=row.image_id,
            image_name=row.image_name,
            aosp_version=row.aosp_version,
            display_layout_id=row.display_layout_id,
            dc_id=row.dc_id,
            dc_name=row.dc_name,
            isp_code=row.isp_code,
            region=row.region,
            zone_id=row.zone_id,
            config_code=row.config_code,
            config_name=row.config_name,
            config_type=row.config_type,
            server_type_code=row.server_type_code,
            intranet_ip=row.intranet_ip,
            adb_address=row.adb_address,
            adb_status=row.adb_status,
            data_size=row.data_size,
            data_size_used=row.data_size_used,
            pod_created_at=row.pod_created_at,
            request_id=row.last_request_id,
            eip_address=row.public_ip,
            node_id=row.node_id,
            provider=row.provider,
            project_name=row.project_name,
            public_ip=row.public_ip,
            os_type=row.os_type,
            os_name=row.os_name,
            instance_type=row.instance_type,
            vcpu=row.vcpu,
            memory_gib=row.memory_gib,
            specification=row.specification,
            agent_endpoint=row.agent_endpoint,
            plugin_version=row.plugin_version,
            script_version=row.script_version,
            status_name=row.status_name,
            status_message=row.status_message,
            last_heartbeat_at=row.last_heartbeat_at,
            node_updated_at=row.node_updated_at,
        )
        return row, detail

    def mark_checked(
        self,
        row: DiscoveredPod,
        *,
        ok: bool,
        checked_at: datetime,
        request_id: str | None,
    ) -> None:
        row.last_checked_at = checked_at
        row.last_request_id = request_id
        if ok:
            row.consecutive_failures = 0
            row.cooldown_until = None
        else:
            row.consecutive_failures += 1
            if row.consecutive_failures >= _FAILURE_LIMIT:
                row.cooldown_until = datetime.fromtimestamp(
                    checked_at.timestamp() + _FAILURE_COOLDOWN_SECONDS,
                    tz=timezone.utc,
                )
        self.db.add(row)

    def mark_assigned(self, row: DiscoveredPod, assigned_at: datetime) -> None:
        row.last_assigned_at = assigned_at
        self.db.add(row)

    def record_temporary_failure(
        self,
        row: DiscoveredPod,
        *,
        checked_at: datetime,
        request_id: str | None,
    ) -> None:
        self.mark_checked(row, ok=False, checked_at=checked_at, request_id=request_id)

    def record_detail(
        self,
        row: DiscoveredPod,
        *,
        checked_at: datetime,
        online: bool,
        remote_status: str,
        request_id: str | None,
    ) -> None:
        _ = remote_status
        if online:
            row.pod_status_code = POD_STATUS_RUNNING
        else:
            row.pod_status_code = POD_STATUS_ABNORMAL
        row.last_checked_at = checked_at
        row.last_request_id = request_id
        row.consecutive_failures = 0
        row.cooldown_until = None
        self.db.add(row)

    async def fetch_detail(self, gateway: Any, config: Any, product_id: str, pod_id: str) -> PodDetail:
        detail = await gateway.detail(config, pod_id)
        db_row = self.get(product_id, pod_id)
        if db_row is not None:
            self.record_detail(
                db_row,
                checked_at=utc_now(),
                online=detail.online,
                remote_status=detail.remote_status,
                request_id=detail.request_id,
            )
            self._apply_detail_fields(db_row, detail)
            self.db.commit()
        return detail

    def _apply_detail_fields(self, row: DiscoveredPod, detail: PodDetail) -> None:
        _update_opt(row, "image_id", detail.image_id)
        _update_opt(row, "image_name", detail.image_name)
        _update_opt(row, "aosp_version", detail.aosp_version)
        _update_opt(row, "display_layout_id", detail.display_layout_id)
        _update_opt(row, "dc_id", detail.dc_id)
        _update_opt(row, "dc_name", detail.dc_name)
        _update_opt(row, "isp_code", detail.isp_code)
        _update_opt(row, "region", detail.region)
        _update_opt(row, "zone_id", detail.zone_id)
        _update_opt(row, "config_code", detail.config_code)
        _update_opt(row, "config_name", detail.config_name)
        _update_opt(row, "config_type", detail.config_type)
        _update_opt(row, "server_type_code", detail.server_type_code)
        _update_opt(row, "intranet_ip", detail.intranet_ip)
        _update_opt(row, "adb_address", detail.adb_address)
        _update_opt(row, "adb_status", detail.adb_status)
        _update_opt(row, "data_size", detail.data_size)
        _update_opt(row, "data_size_used", detail.data_size_used)
        _update_opt(row, "pod_created_at", detail.pod_created_at)
        _apply_cua_fields(row, detail)

    def sync(
        self,
        product_id: str,
        page: Any,
        *,
        seen_at: datetime | None = None,
    ) -> None:
        seen_at = seen_at or utc_now()
        items: Iterable[PodSummary]
        request_id: str | None
        if hasattr(page, "items"):
            items = page.items
            request_id = getattr(page, "request_id", None)
        else:
            items = page
            request_id = None
        seen_ids: set[str] = set()
        changed = False
        for item in items:
            seen_ids.add(item.pod_id)
            self._upsert(item, request_id, seen_at)
            changed = True
        missing = self.db.execute(
            delete(DiscoveredPod)
            .where(
                DiscoveredPod.product_id == product_id,
                DiscoveredPod.pod_id.not_in(seen_ids),
            )
            .execution_options(synchronize_session=False)
        )
        missing_count = missing.rowcount or 0
        if missing_count:
            changed = True
            logger.warning(
                "pod_pool_missing_pods",
                extra={"count": missing_count, "request_id": request_id},
            )
        refresh = self.db.scalar(
            select(PodPoolRefresh).where(
                PodPoolRefresh.product_id == product_id
            )
        )
        if refresh is None:
            refresh = PodPoolRefresh(
                product_id=product_id, refreshed_at=seen_at
            )
        else:
            refresh.refreshed_at = seen_at
        self.db.add(refresh)
        if changed:
            self.db.commit()

    def _product_id(self, items: Iterable[PodSummary]) -> str:
        for item in items:
            return item.product_id
        raise ValueError("items_empty")

    def _upsert(
        self,
        item: PodSummary,
        request_id: str | None,
        seen_at: datetime,
    ) -> DiscoveredPod:
        row = self.get(item.product_id, item.pod_id)
        if row is None:
            row = DiscoveredPod(
                id=f"pod_{uuid4().hex}",
                product_id=item.product_id,
                pod_id=item.pod_id,
                pod_name=item.pod_name,
                pod_status_code=item.pod_status_code,
                stream_status=item.stream_status,
                discovery_state="active",
                image_id=item.image_id,
                image_name=item.image_name,
                aosp_version=item.aosp_version,
                display_layout_id=item.display_layout_id,
                dc_id=item.dc_id,
                dc_name=item.dc_name,
                isp_code=item.isp_code,
                region=item.region,
                zone_id=item.zone_id,
                config_code=item.config_code,
                config_name=item.config_name,
                config_type=item.config_type,
                server_type_code=item.server_type_code,
                intranet_ip=item.intranet_ip,
                adb_address=item.adb_address,
                adb_status=item.adb_status,
                data_size=item.data_size,
                data_size_used=item.data_size_used,
                pod_created_at=item.pod_created_at,
                node_id=item.node_id,
                provider=item.provider,
                project_name=item.project_name,
                public_ip=item.public_ip or item.eip_address,
                os_type=item.os_type,
                os_name=item.os_name,
                instance_type=item.instance_type,
                vcpu=item.vcpu,
                memory_gib=item.memory_gib,
                specification=item.specification,
                agent_endpoint=item.agent_endpoint,
                plugin_version=item.plugin_version,
                script_version=item.script_version,
                status_name=item.status_name,
                status_message=item.status_message,
                last_heartbeat_at=item.last_heartbeat_at,
                node_updated_at=item.node_updated_at,
                last_seen_at=seen_at,
                last_checked_at=None,
                last_request_id=request_id,
                last_assigned_at=None,
                consecutive_failures=0,
                cooldown_until=None,
                created_at=seen_at,
                updated_at=seen_at,
            )
            self.db.add(row)
            return row
        row.pod_name = item.pod_name
        row.pod_status_code = item.pod_status_code
        row.stream_status = item.stream_status
        row.discovery_state = "active"
        _update_opt(row, "image_id", item.image_id)
        _update_opt(row, "image_name", item.image_name)
        _update_opt(row, "aosp_version", item.aosp_version)
        _update_opt(row, "display_layout_id", item.display_layout_id)
        _update_opt(row, "dc_id", item.dc_id)
        _update_opt(row, "dc_name", item.dc_name)
        _update_opt(row, "isp_code", item.isp_code)
        _update_opt(row, "region", item.region)
        _update_opt(row, "zone_id", item.zone_id)
        _update_opt(row, "config_code", item.config_code)
        _update_opt(row, "config_name", item.config_name)
        _update_opt(row, "config_type", item.config_type)
        _update_opt(row, "server_type_code", item.server_type_code)
        _update_opt(row, "intranet_ip", item.intranet_ip)
        _update_opt(row, "adb_address", item.adb_address)
        _update_opt(row, "adb_status", item.adb_status)
        _update_opt(row, "data_size", item.data_size)
        _update_opt(row, "data_size_used", item.data_size_used)
        _update_opt(row, "pod_created_at", item.pod_created_at)
        _apply_cua_fields(row, item)
        row.last_seen_at = seen_at
        row.last_request_id = request_id
        row.updated_at = seen_at
        return row

    def _local_state(self, row: DiscoveredPod, now: datetime) -> str:
        if row.discovery_state == "stale":
            return "stale"
        if row.cooldown_until is not None and row.cooldown_until > now:
            return "cooldown"
        if row.pod_status_code != POD_STATUS_RUNNING:
            return "unavailable"
        if (now - row.last_seen_at).total_seconds() > _FRESH_WINDOW_SECONDS:
            return "stale"
        return "available"

    def _to_pool_item(
        self,
        row: DiscoveredPod,
        task: Task | None,
        now: datetime,
    ) -> PodPoolItem:
        local_state = self._local_state(row, now)
        if local_state == "available" and task is not None:
            local_state = "leased"
        return PodPoolItem(
            product_id=row.product_id,
            pod_id=row.pod_id,
            pod_name=row.pod_name,
            pod_status_code=row.pod_status_code,
            stream_status=row.stream_status,
            discovery_state=row.discovery_state,
            local_state=local_state,
            image_id=row.image_id,
            image_name=row.image_name,
            aosp_version=row.aosp_version,
            display_layout_id=row.display_layout_id,
            dc_id=row.dc_id,
            dc_name=row.dc_name,
            isp_code=row.isp_code,
            region=row.region,
            zone_id=row.zone_id,
            config_code=row.config_code,
            config_name=row.config_name,
            config_type=row.config_type,
            server_type_code=row.server_type_code,
            intranet_ip=row.intranet_ip,
            adb_address=row.adb_address,
            adb_status=row.adb_status,
            data_size=row.data_size,
            data_size_used=row.data_size_used,
            pod_created_at=row.pod_created_at,
            last_seen_at=row.last_seen_at,
            last_checked_at=row.last_checked_at,
            request_id=row.last_request_id,
            task_id=task.id if task is not None else None,
            task_status=task.execution_status.value if task is not None else None,
            task_scenario=task.scenario if task is not None else None,
            eip_address=row.public_ip,
            node_id=row.node_id,
            provider=row.provider,
            project_name=row.project_name,
            public_ip=row.public_ip,
            os_type=row.os_type,
            os_name=row.os_name,
            instance_type=row.instance_type,
            vcpu=row.vcpu,
            memory_gib=row.memory_gib,
            specification=row.specification,
            agent_endpoint=row.agent_endpoint,
            plugin_version=row.plugin_version,
            script_version=row.script_version,
            status_name=row.status_name,
            status_message=row.status_message,
            last_heartbeat_at=row.last_heartbeat_at,
            node_updated_at=row.node_updated_at,
        )


def _update_opt(row: Any, field: str, value: Any) -> None:
    if value is not None:
        setattr(row, field, value)


def _apply_cua_fields(row: DiscoveredPod, item: Any) -> None:
    _update_opt(row, "node_id", item.node_id)
    _update_opt(row, "provider", item.provider)
    _update_opt(row, "project_name", item.project_name)
    _update_opt(row, "public_ip", item.public_ip or item.eip_address)
    _update_opt(row, "os_type", item.os_type)
    _update_opt(row, "os_name", item.os_name)
    _update_opt(row, "instance_type", item.instance_type)
    _update_opt(row, "vcpu", item.vcpu)
    _update_opt(row, "memory_gib", item.memory_gib)
    _update_opt(row, "specification", item.specification)
    _update_opt(row, "agent_endpoint", item.agent_endpoint)
    _update_opt(row, "plugin_version", item.plugin_version)
    _update_opt(row, "script_version", item.script_version)
    _update_opt(row, "status_name", item.status_name)
    _update_opt(row, "status_message", item.status_message)
    _update_opt(row, "last_heartbeat_at", item.last_heartbeat_at)
    _update_opt(row, "node_updated_at", item.node_updated_at)
