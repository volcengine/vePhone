from datetime import datetime

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mua_platform.db import Base
from mua_platform.settings.models import UTCDateTime
from mua_platform.tasks.models import utc_now


class PodPoolRefresh(Base):
    __tablename__ = "pod_pool_refreshes"

    product_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    refreshed_at: Mapped[datetime] = mapped_column(UTCDateTime())


POD_STATUS_BOOTING = 0
POD_STATUS_RUNNING = 1
POD_STATUS_SHUTDOWN = 2
POD_STATUS_SHUTTING_DOWN = 3
POD_STATUS_REBOOTING = 4

STREAM_STATUS_IDLE = 0
STREAM_STATUS_STREAMING = 1
STREAM_STATUS_READY = 2


class DiscoveredPod(Base):
    __tablename__ = "discovered_pods"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "pod_id",
            name="unique_discovered_product_pod",
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(255), index=True)
    pod_id: Mapped[str] = mapped_column(String(255))
    pod_name: Mapped[str] = mapped_column(String(255))
    pod_status_code: Mapped[int] = mapped_column(Integer, default=POD_STATUS_RUNNING)
    stream_status: Mapped[int | None] = mapped_column(Integer)
    discovery_state: Mapped[str] = mapped_column(String(16), default="active")
    image_id: Mapped[str | None] = mapped_column(String(255))
    image_name: Mapped[str | None] = mapped_column(String(255))
    aosp_version: Mapped[str | None] = mapped_column(String(32))
    display_layout_id: Mapped[str | None] = mapped_column(String(64))
    dc_id: Mapped[str | None] = mapped_column(String(64))
    dc_name: Mapped[str | None] = mapped_column(String(128))
    isp_code: Mapped[int | None] = mapped_column(Integer)
    region: Mapped[str | None] = mapped_column(String(32))
    zone_id: Mapped[str | None] = mapped_column(String(64))
    config_code: Mapped[str | None] = mapped_column(String(64))
    config_name: Mapped[str | None] = mapped_column(String(64))
    config_type: Mapped[int | None] = mapped_column(Integer)
    server_type_code: Mapped[str | None] = mapped_column(String(64))
    intranet_ip: Mapped[str | None] = mapped_column(String(64))
    adb_address: Mapped[str | None] = mapped_column(String(128))
    adb_status: Mapped[int | None] = mapped_column(Integer)
    data_size: Mapped[str | None] = mapped_column(String(32))
    data_size_used: Mapped[str | None] = mapped_column(String(32))
    pod_created_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_request_id: Mapped[str | None] = mapped_column(String(128))
    last_assigned_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    cooldown_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=utc_now,
        onupdate=utc_now,
    )

    @property
    def online(self) -> bool:
        return self.pod_status_code == POD_STATUS_RUNNING

    @property
    def remote_status(self) -> str:
        return _REMOTE_STATUS_LABELS.get(self.pod_status_code, "unknown")


class PodHostAction(Base):
    __tablename__ = "pod_host_actions"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "remote_task_id",
            name="unique_pod_host_action_remote_task",
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(255), index=True)
    pod_id: Mapped[str] = mapped_column(String(255), index=True)
    action: Mapped[str] = mapped_column(String(16))
    request_id: Mapped[str | None] = mapped_column(String(128))
    remote_task_id: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="running")
    task_result: Mapped[int | None] = mapped_column(Integer)
    task_message: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=utc_now,
        onupdate=utc_now,
    )
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


_REMOTE_STATUS_LABELS: dict[int, str] = {
    POD_STATUS_BOOTING: "booting",
    POD_STATUS_RUNNING: "running",
    POD_STATUS_SHUTDOWN: "offline",
    POD_STATUS_SHUTTING_DOWN: "shutting_down",
    POD_STATUS_REBOOTING: "rebooting",
}
