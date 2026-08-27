from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mua_platform.traces.schemas import TraceSpanDraft


@dataclass(frozen=True, slots=True)
class PodSummary:
    product_id: str
    pod_id: str
    pod_name: str
    pod_status_code: int
    stream_status: int | None
    image_id: str | None
    image_name: str | None
    aosp_version: str | None
    display_layout_id: str | None
    dc_id: str | None
    dc_name: str | None
    isp_code: int | None
    region: str | None
    zone_id: str | None
    config_code: str | None
    config_name: str | None
    config_type: int | None
    server_type_code: str | None
    intranet_ip: str | None
    adb_address: str | None
    adb_status: int | None
    data_size: str | None
    data_size_used: str | None
    pod_created_at: datetime | None
    eip_address: str | None = None

    @property
    def online(self) -> bool:
        return self.pod_status_code == 1

    @property
    def remote_status(self) -> str:
        return _POD_STATUS_LABELS.get(self.pod_status_code, "unknown")


@dataclass(frozen=True, slots=True)
class ListPodPage:
    items: tuple[PodSummary, ...]
    next_token: str | None
    request_id: str | None


@dataclass(frozen=True, slots=True)
class PodDetail:
    product_id: str
    pod_id: str
    pod_name: str
    pod_status_code: int
    stream_status: int | None
    image_id: str | None
    image_name: str | None
    aosp_version: str | None
    display_layout_id: str | None
    dc_id: str | None
    dc_name: str | None
    isp_code: int | None
    region: str | None
    zone_id: str | None
    config_code: str | None
    config_name: str | None
    config_type: int | None
    server_type_code: str | None
    intranet_ip: str | None
    adb_address: str | None
    adb_status: int | None
    data_size: str | None
    data_size_used: str | None
    pod_created_at: datetime | None
    request_id: str | None
    eip_address: str | None = None

    @property
    def online(self) -> bool:
        return self.pod_status_code == 1

    @property
    def remote_status(self) -> str:
        return _POD_STATUS_LABELS.get(self.pod_status_code, "unknown")


@dataclass(frozen=True, slots=True)
class PodHostAction:
    action: str
    request_id: str | None
    remote_task_id: str
    status: str
    task_result: int | None
    task_message: str | None


@dataclass(frozen=True, slots=True)
class PodPoolItem:
    product_id: str
    pod_id: str
    pod_name: str
    pod_status_code: int
    stream_status: int | None
    discovery_state: str
    local_state: str
    image_id: str | None
    image_name: str | None
    aosp_version: str | None
    display_layout_id: str | None
    dc_id: str | None
    dc_name: str | None
    isp_code: int | None
    region: str | None
    zone_id: str | None
    config_code: str | None
    config_name: str | None
    config_type: int | None
    server_type_code: str | None
    intranet_ip: str | None
    adb_address: str | None
    adb_status: int | None
    data_size: str | None
    data_size_used: str | None
    pod_created_at: datetime | None
    last_seen_at: datetime
    last_checked_at: datetime | None
    request_id: str | None
    task_id: str | None
    task_status: str | None
    task_scenario: str | None
    active_host_action: PodHostAction | None = None
    eip_address: str | None = None

    @property
    def online(self) -> bool:
        return self.pod_status_code == 1

    @property
    def remote_status(self) -> str:
        return _POD_STATUS_LABELS.get(self.pod_status_code, "unknown")


@dataclass(frozen=True, slots=True)
class PodPoolSnapshot:
    items: tuple[PodPoolItem, ...]
    refreshed_at: datetime | None

    @property
    def active_ids(self) -> tuple[str, ...]:
        return tuple(
            item.pod_id for item in self.items if item.discovery_state == "active"
        )


@dataclass(frozen=True, slots=True)
class VerifiedPodAllocation:
    product_id: str
    pod_id: str
    pod_name: str
    resource_key: str
    checked_at: datetime
    request_id: str | None
    trace_drafts: tuple["TraceSpanDraft", ...] = ()


_POD_STATUS_LABELS: dict[int, str] = {
    0: "booting",
    1: "running",
    2: "offline",
    3: "shutting_down",
    4: "rebooting",
}

DISPLAY_LAYOUT_LABELS: dict[str, str] = {
    "single-display-landscape": "1080p 横屏 (1920×1080)",
    "single-display-portrait": "1080p 竖屏 (1080×1920)",
    "single-display-portrait-720p": "高清竖屏 (720×1080)",
}

AOSP_VERSION_LABELS: dict[str, str] = {
    "10": "AOSP 10",
    "11": "AOSP 11",
    "13": "AOSP 13",
}

STREAM_STATUS_LABELS: dict[int, str] = {
    0: "空闲",
    1: "推流中",
    2: "就绪",
}

POD_STATUS_LABELS_CN: dict[int, str] = {
    0: "开机中",
    1: "运行中",
    2: "已关机",
    3: "关机中",
    4: "重启中",
}

REGION_LABELS: dict[str, str] = {
    "cn-north": "华北",
    "cn-south": "华南",
    "cn-east": "华东",
    "cn-middle": "华中",
    "cn-southwest": "西南",
    "cn-northwest": "西北",
    "cn-hongkong-pop": "中国香港",
}

ISP_LABELS: dict[int, str] = {
    1: "中国移动",
    2: "中国联通",
    4: "中国电信",
    7: "三线",
    8: "BGP",
}

CONFIG_TYPE_LABELS: dict[int, str] = {
    1: "正式",
    2: "试用",
}
