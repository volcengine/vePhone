#!/usr/bin/env python3
"""
geo.py - 多来源统一 GPS 获取模块 (GpsInfo 注入)

火山引擎 Mobile Use Agent 的 GpsInfo 参数格式 (英文逗号分隔):
    "经度,纬度,海拔,速度,方位角,定位精度"
    示例: "116.397128,39.916527,50,0,0,10"
    - 经度/纬度: WGS-84 坐标系 (必填)
    - 海拔: 单位米 (m)
    - 速度: 单位米/秒 (m/s)
    - 方位角: 相对正北顺时针角度 (deg), 0~360
    - 定位精度: 水平误差半径 (m), 越小越精准

获取来源 (统一抽象, 按降级链自动尝试, 上层无需关心来源):

    ┌ parse    文本坐标解析     prompt 中直接含坐标 (十进制/DMS), 零成本、高精度
    ├ exif     图片 EXIF        prompt 指向含 GPS 元数据的图片 (Pillow, 软依赖)
    ├ system   macOS 系统定位    CoreLocation, 米级 (含海拔/速度/方位角), 需终端定位权限
    ├ ip       IP 定位          ip-api.com / ipinfo.io / ipapi.co, 城市级 (±10km)
    ├ geocode  地理编码          Nominatim (OpenStreetMap), 地名/地址 → 坐标
    └ manual   手动输入          兜底: 用户输入坐标或地址 (交互式)

架构:
    - `GpsSource` 抽象基类: 统一 acquire() 接口 + name/label/priority 元信息
    - 具体来源注册到 `SOURCES` 注册表, 按 priority 升序组成降级链
    - `acquire_gps()` facade: 按链依次尝试, 失败自动降级, 可回退手动输入
    - 扩展新来源: 继承 GpsSource + register_source(), 上层代码零改动

隐私设计:
    本模块只提供"获取"能力; 是否获取由调用方 (CLI) 在每次发起任务前
    向用户征求同意, 获取结果 (来源/坐标/精度) 会明确告知用户。
    需权限的来源 (system) 与无需权限的来源 (parse/exif/geocode/manual) 分离,
    用户拒绝自动获取时仍可走"手动输入"或"文本解析"等无隐私来源。

坐标系:
    全部使用 WGS-84 (火山引擎要求), 刻意避开国内地图服务的
    GCJ-02/BD-09 偏移坐标系导致注入位置偏移。
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

# IP 定位水平误差半径 (城市级, 约 10 km)
IP_LOCATION_ACCURACY = 10000.0

# 地理编码精度 (Nominatim 返回街道级, 保守记为 2km)
GEOCODE_ACCURACY = 2000.0

# EXIF 精度 (GPS 标签通常精确到米级)
EXIF_ACCURACY = 50.0


@dataclass
class LocationInfo:
    """统一的位置信息 (WGS-84)"""

    latitude: float          # 纬度 (WGS-84)
    longitude: float         # 经度 (WGS-84)
    altitude: float = 0.0    # 海拔 (m)
    speed: float = 0.0       # 速度 (m/s)
    course: float = 0.0      # 方位角 (deg, 相对正北顺时针)
    accuracy: float = 0.0    # 水平精度 (m)
    source: str = ""         # 来源描述
    address: str = ""        # 地址描述 (IP 定位时为城市名, 地理编码时为地址)


# ========================
# 格式化
# ========================


def format_gps_info(loc: LocationInfo) -> str:
    """转换为火山引擎 GpsInfo 格式: "经度,纬度,海拔,速度,方位角,定位精度" """
    return (
        f"{loc.longitude:.6f},{loc.latitude:.6f},"
        f"{loc.altitude:.0f},{loc.speed:.1f},{loc.course:.0f},{loc.accuracy:.0f}"
    )


def describe_location(loc: LocationInfo) -> str:
    """生成人类可读的位置描述"""
    lat_str = (
        f"北纬 {loc.latitude:.6f}" if loc.latitude >= 0 else f"南纬 {abs(loc.latitude):.6f}"
    )
    lon_str = (
        f"东经 {loc.longitude:.6f}" if loc.longitude >= 0 else f"西经 {abs(loc.longitude):.6f}"
    )
    desc = f"{loc.address}, " if loc.address else ""
    desc += f"{lat_str}, {lon_str}"
    acc = f", 精度 ±{loc.accuracy:.0f}m" if loc.accuracy > 0 else ""
    return f"{desc} (来源: {loc.source}{acc})"


# ========================
# 来源抽象与上下文
# ========================


@dataclass
class GpsContext:
    """一次 GPS 获取的上下文 (各来源按需读取)"""

    prompt: str = ""                # 用户提示词 (文本解析/EXIF/地名提取的输入)
    allow_permission: bool = False  # 用户是否允许系统定位 (system 来源)
    allow_ip: bool = True           # 是否允许 IP 定位 (ip 来源)
    allow_manual: bool = True       # 全链失败后是否允许交互式手动输入 (manual)
    verbose: bool = True            # 是否打印过程信息
    timeout: float = 15.0           # 网络/系统定位超时 (秒)


class GpsSource(ABC):
    """GPS 来源抽象基类: 统一接口, 新来源只需继承并注册"""

    #: 唯一标识 (小写英文)
    name: str = ""
    #: 人类可读名称
    label: str = ""
    #: 是否需要用户授权 (system 需要; 文本/图片/地名解析不需要)
    requires_permission: bool = False
    #: 降级顺序, 越小越优先
    priority: int = 100

    @abstractmethod
    def acquire(self, ctx: GpsContext) -> Optional[LocationInfo]:
        """尝试从本来源获取位置; 失败返回 None"""

    def failure_hint(self, err: Optional[Exception]) -> str:
        """失败时的简要说明 (verbose 模式下打印)"""
        return f"{self.label} 不可用" + (f": {err}" if err else "")


# ---- 来源注册表 ----
SOURCES: list[GpsSource] = []


def register_source(src: GpsSource) -> GpsSource:
    """注册 GPS 来源并按 priority 升序插入降级链 (自动实例化)

    用法: 定义 GpsSource 子类后加 @register_source 装饰器即可。
    """
    SOURCES.append(src())  # 类 → 实例 (无参构造)
    SOURCES.sort(key=lambda s: s.priority)
    return src


def iter_sources(ctx: GpsContext):
    """按降级链顺序产出可用的来源 (过滤权限不允许的)"""
    for src in SOURCES:
        if src.requires_permission and not ctx.allow_permission:
            continue
        yield src


# ========================
# 来源 1: 文本坐标解析 (十进制 / 度分秒)
# ========================

# 十进制坐标对: "39.916527,116.397128" / "39.916527, 116.397128" / "39.916527 116.397128"
_RE_DECIMAL = re.compile(
    r"(-?\d{1,3}(?:\.\d+)?)\s*[,，\s]\s*(-?\d{1,3}(?:\.\d+)?)"
)
# 度分秒 (DMS): "39°54'26\"N 116°23'29\"E" / "39°54′26″N 116°23′29″E"
_RE_DMS = re.compile(
    r"(\d{1,3})°\s*(\d{1,2}(?:\.\d+)?)[′'‘]?\s*(\d{1,2}(?:\.\d+)?)?[″\"”]?\s*([NSEWnsew])"
)


def _dms_to_decimal(deg: float, minutes: float, seconds: float, ref: str) -> float:
    """度分秒 → 十进制; ref 为 S/W 时取负"""
    value = deg + minutes / 60.0 + (seconds or 0.0) / 3600.0
    return -value if ref.upper() in ("S", "W") else value


def _validate_latlon(lat: float, lon: float) -> bool:
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def parse_coordinate_pair(text: str) -> Optional[tuple[float, float]]:
    """从文本中解析出 (纬度, 经度); 支持十进制与度分秒, 自动判断顺序

    - "39.916527,116.397128"     → 纬度,经度 (常见顺序)
    - "116.397128,39.916527"     → 经度,纬度 (自动识别)
    - "39°54'26\"N 116°23'29\"E" → DMS 格式
    - 文本中混有无关数字时不误判 (需落在合法经纬度范围)

    Returns:
        (lat, lon) 或 None
    """
    if not text:
        return None

    # 优先 DMS (语义明确, 带 N/S/E/W 指示)
    matches = _RE_DMS.findall(text)
    if len(matches) >= 2:
        # 找到两组 DMS: 通常 纬度在前 经度在后 (N/S 开头的在前)
        groups = sorted(matches, key=lambda m: 0 if m[3].upper() in ("N", "S") else 1)
        lat = _dms_to_decimal(float(groups[0][0]), float(groups[0][1]),
                              float(groups[0][2] or 0), groups[0][3])
        lon = _dms_to_decimal(float(groups[1][0]), float(groups[1][1]),
                              float(groups[1][2] or 0), groups[1][3])
        if _validate_latlon(lat, lon):
            return (lat, lon)

    # 十进制对: 遍历候选, 取第一个合法组合
    for a, b in _RE_DECIMAL.findall(text):
        x, y = float(a), float(b)
        # 常见顺序: 纬度在前 (39,116); 若 x 明显超出纬度范围则按 经度,纬度
        if _validate_latlon(x, y):
            return (x, y)
        if _validate_latlon(y, x):
            return (y, x)
    return None


@register_source
class ParseSource(GpsSource):
    name = "parse"
    label = "文本坐标解析"
    priority = 10

    def acquire(self, ctx: GpsContext) -> Optional[LocationInfo]:
        pair = parse_coordinate_pair(ctx.prompt)
        if pair is None:
            return None
        lat, lon = pair
        return LocationInfo(
            latitude=lat, longitude=lon, accuracy=5.0,
            source="文本坐标解析", address="提示词中解析出的坐标",
        )


# ========================
# 来源 2: 图片 EXIF 元数据
# ========================

_RE_IMAGE_PATH = re.compile(
    r"([\w./\\ -]+\.(?:jpe?g|png|tiff?|heic|heif))", re.IGNORECASE
)


def extract_exif_gps(image_path: str) -> Optional[LocationInfo]:
    """从图片 EXIF GPS 元数据中解析位置 (需要 Pillow)

    图片由手机/相机拍摄时, EXIF 常含 GPSInfo 标签 (度分秒格式)。
    GPS IFD 数字标签: 1=LatitudeRef 2=Latitude(DMS) 3=LongitudeRef 4=Longitude(DMS) 6=Altitude
    """
    try:
        from PIL import Image
    except ImportError:
        return None

    try:
        img = Image.open(image_path)
        # Pillow 10+: getexif() 返回 Exif 对象 (get_ifd 解析 GPS); 老版本: _getexif() 返回 dict
        if hasattr(img, "getexif"):
            gps = img.getexif().get_ifd(0x8825)
        else:
            exif = img._getexif() or {}
            gps = exif.get(0x8825)
        if not gps:
            return None
    except Exception:
        return None

    try:
        lat = _dms_to_decimal(float(gps[2][0]), float(gps[2][1]),
                              float(gps[2][2]), str(gps.get(1) or "N"))
        lon = _dms_to_decimal(float(gps[4][0]), float(gps[4][1]),
                              float(gps[4][2]), str(gps.get(3) or "E"))
        if not _validate_latlon(lat, lon):
            return None
        alt = float(gps[6]) if gps.get(6) else 0.0
        return LocationInfo(
            latitude=lat, longitude=lon, altitude=alt, accuracy=EXIF_ACCURACY,
            source="图片 EXIF 元数据", address=os.path.basename(image_path),
        )
    except Exception:
        return None


@register_source
class ExifSource(GpsSource):
    name = "exif"
    label = "图片 EXIF 元数据"
    priority = 20

    def acquire(self, ctx: GpsContext) -> Optional[LocationInfo]:
        # 从提示词中找图片路径 (或提示词本身就是一个存在的图片文件)
        candidates = []
        stripped = ctx.prompt.strip().strip("'\"")
        if os.path.isfile(stripped):
            candidates.append(stripped)
        for m in _RE_IMAGE_PATH.findall(ctx.prompt):
            if os.path.isfile(m):
                candidates.append(m)
        for path in candidates:
            loc = extract_exif_gps(path)
            if loc is not None:
                return loc
        return None


# ========================
# 来源 3: macOS CoreLocation 系统定位 (需权限)
# ========================


@register_source
class SystemLocationSource(GpsSource):
    name = "system"
    label = "macOS 系统定位 (CoreLocation)"
    requires_permission = True
    priority = 30

    def acquire(self, ctx: GpsContext) -> Optional[LocationInfo]:
        return get_location_corelocation(timeout=ctx.timeout, verbose=ctx.verbose)


def get_location_corelocation(
    timeout: float = 15.0, verbose: bool = True
) -> Optional[LocationInfo]:
    """通过 macOS CoreLocation 获取精确位置

    无权限 / 超时 / 非 macOS / 依赖缺失时返回 None,
    由上层降级到下一个来源。
    """
    if sys.platform != "darwin":
        return None

    try:
        import objc
        from Foundation import NSObject, NSRunLoop, NSDate, NSDefaultRunLoopMode
        from CoreLocation import (
            CLLocationManager,
            kCLAuthorizationStatusNotDetermined,
            kCLAuthorizationStatusDenied,
            kCLAuthorizationStatusRestricted,
        )
    except ImportError:
        if verbose:
            print("[定位] 未安装 pyobjc-framework-CoreLocation, 跳过系统定位")
        return None

    # 定位服务总开关
    if not CLLocationManager.locationServicesEnabled():
        if verbose:
            print("[定位] 系统定位服务未开启")
        return None

    status = CLLocationManager.authorizationStatus()
    if status in (kCLAuthorizationStatusDenied, kCLAuthorizationStatusRestricted):
        if verbose:
            print(
                "[定位] 终端未获得定位权限 "
                "(系统设置 > 隐私与安全性 > 定位服务)"
            )
        return None

    class LocationDelegate(NSObject):
        # 注意: 不重写 init (函数内定义的类无法使用 objc.super() 零参数形式,
        # pyobjc 会为实例提供 Python 属性存储), 状态在 alloc().init() 后设置。

        def locationManager_didUpdateLocations_(self, manager, locations):
            if locations:
                self.location = locations[-1]

        def locationManager_didFailWithError_(self, manager, error):
            self.error = error

        def locationManager_didChangeAuthorization_(self, manager, status):
            # 授权被明确拒绝时提前终止等待, 不傻等到超时
            if status in (kCLAuthorizationStatusDenied, kCLAuthorizationStatusRestricted):
                self.error = "定位权限被拒绝"

    manager = CLLocationManager.alloc().init()
    delegate = LocationDelegate.alloc().init()
    delegate.location = None  # CLLocation 对象
    delegate.error = None
    manager.setDelegate_(delegate)

    if status == kCLAuthorizationStatusNotDetermined:
        # 触发系统授权弹窗 (由终端 App 承接)
        manager.requestWhenInUseAuthorization()

    manager.startUpdatingLocation()

    # 驱动 runloop 等待回调 (定位回调经由 runloop 投递)
    deadline = time.time() + timeout
    while time.time() < deadline:
        NSRunLoop.currentRunLoop().runMode_beforeDate_(
            NSDefaultRunLoopMode, NSDate.dateWithTimeIntervalSinceNow_(0.3)
        )
        if delegate.location is not None or delegate.error is not None:
            break

    manager.stopUpdatingLocation()

    if delegate.error is not None or delegate.location is None:
        return None

    loc = delegate.location
    coord = loc.coordinate()
    speed = loc.speed()               # 无效时为 -1.0
    course = loc.course()             # 无效时为 -1.0
    h_acc = loc.horizontalAccuracy()  # 无效时为 -1.0
    v_acc = loc.verticalAccuracy()    # 无效时为 -1.0

    return LocationInfo(
        latitude=float(coord.latitude),
        longitude=float(coord.longitude),
        altitude=float(loc.altitude()) if v_acc >= 0 else 0.0,
        speed=float(speed) if speed >= 0 else 0.0,
        course=float(course) if course >= 0 else 0.0,
        accuracy=float(h_acc) if h_acc >= 0 else 0.0,
        source="macOS 系统定位 (CoreLocation)",
    )


# ========================
# 来源 4: IP 定位 (城市级, 无需权限)
# ========================


def _http_get_json(url: str, timeout: float) -> Optional[dict]:
    req = urllib.request.Request(
        url, headers={"User-Agent": "mobile-use-agent-cli/1.0"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_location_ip(timeout: float = 8.0) -> Optional[LocationInfo]:
    """通过 IP 定位获取大致位置 (城市级, WGS-84)

    依次尝试多个公共 IP 定位服务, 全部失败返回 None。
    """
    errors = []

    # --- 1) ip-api.com (支持中文城市名) ---
    try:
        data = _http_get_json(
            "http://ip-api.com/json/?lang=zh-CN"
            "&fields=status,message,lat,lon,city,regionName,country",
            timeout,
        )
        if data.get("status") == "success":
            addr = " ".join(
                filter(None, [data.get("country"), data.get("regionName"), data.get("city")])
            )
            return LocationInfo(
                latitude=float(data["lat"]),
                longitude=float(data["lon"]),
                accuracy=IP_LOCATION_ACCURACY,
                source="IP 定位 (ip-api.com, 城市级)",
                address=addr,
            )
        errors.append(f"ip-api: {data.get('message', 'unknown')}")
    except Exception as e:
        errors.append(f"ip-api: {e}")

    # --- 2) ipinfo.io ---
    try:
        data = _http_get_json("https://ipinfo.io/json", timeout)
        loc = data.get("loc", "")
        if "," in loc:
            lat, lon = loc.split(",", 1)
            addr = " ".join(
                filter(None, [data.get("country"), data.get("region"), data.get("city")])
            )
            return LocationInfo(
                latitude=float(lat),
                longitude=float(lon),
                accuracy=IP_LOCATION_ACCURACY,
                source="IP 定位 (ipinfo.io, 城市级)",
                address=addr,
            )
        errors.append("ipinfo: missing loc field")
    except Exception as e:
        errors.append(f"ipinfo: {e}")

    # --- 3) ipapi.co ---
    try:
        data = _http_get_json("https://ipapi.co/json/", timeout)
        if data.get("latitude") is not None and data.get("longitude") is not None:
            addr = " ".join(
                filter(None, [data.get("country_name"), data.get("region"), data.get("city")])
            )
            return LocationInfo(
                latitude=float(data["latitude"]),
                longitude=float(data["longitude"]),
                accuracy=IP_LOCATION_ACCURACY,
                source="IP 定位 (ipapi.co, 城市级)",
                address=addr,
            )
        errors.append("ipapi: missing coordinates")
    except Exception as e:
        errors.append(f"ipapi: {e}")

    for err in errors:
        print(f"  [IP定位] {err}")
    return None


@register_source
class IpLocationSource(GpsSource):
    name = "ip"
    label = "IP 定位 (城市级)"
    priority = 40

    def acquire(self, ctx: GpsContext) -> Optional[LocationInfo]:
        if not ctx.allow_ip:
            return None
        if ctx.verbose:
            print("[定位] 系统定位不可用, 降级为 IP 定位 (城市级精度)...")
        return get_location_ip(timeout=min(8.0, max(2.0, ctx.timeout * 0.6)))


# ========================
# 来源 5: 地理编码 (地名/地址 → 坐标)
# ========================


def geocode_address(address: str, timeout: float = 10.0) -> Optional[LocationInfo]:
    """把地址/地名/城市名地理编码为坐标 (Nominatim / OpenStreetMap, 免费无 key)

    依赖网络; 失败返回 None。可替换为高德/腾讯等国内地理编码服务
    (注意其 GCJ-02 坐标系需转换, 本项目统一使用 WGS-84)。
    """
    if not address or not address.strip():
        return None
    query = urllib.parse.quote(address.strip())
    url = (
        f"https://nominatim.openstreetmap.org/search?format=json&limit=1"
        f"&accept-language=zh&q={query}"
    )
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "mobile-use-agent-cli/1.0 (contact: github.com/chenjie1129/mobile-use-agent)"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not data:
            return None
        item = data[0]
        return LocationInfo(
            latitude=float(item["lat"]),
            longitude=float(item["lon"]),
            accuracy=GEOCODE_ACCURACY,
            source="地理编码 (Nominatim)",
            address=item.get("display_name", address),
        )
    except Exception:
        return None


@register_source
class GeocodeSource(GpsSource):
    name = "geocode"
    label = "地理编码 (地址/地名 → 坐标)"
    priority = 50

    def acquire(self, ctx: GpsContext) -> Optional[LocationInfo]:
        addr = extract_place_name(ctx.prompt)
        if not addr:
            return None
        if ctx.verbose:
            print(f"[定位] 尝试把「{addr}」地理编码为坐标...")
        return geocode_address(addr)


#: 地名/地址触发词: 提示词含这些词且不包含坐标时, 提取后续内容作为地址
_PLACE_TRIGGERS = ("在", "位于", "去", "到", "地址", "定位到")


def extract_place_name(prompt: str) -> str:
    """从提示词中尽力提取地名/地址 (用于地理编码)

    规则 (简单启发式, 失败返回空串):
    1. 若提示词本身就是地址 (不含触发词且较短) → 原样返回
    2. 含触发词时, 取触发词之后、标点之前的一段文本
    """
    if not prompt:
        return ""
    text = prompt.strip().strip("，。！？,.!?")

    # 已含坐标的文本不再当地址处理
    if parse_coordinate_pair(text):
        return ""

    # 太长且无明显触发词的, 无法安全提取
    for trigger in _PLACE_TRIGGERS:
        idx = text.find(trigger)
        if idx >= 0:
            tail = text[idx + len(trigger):]
            # 截断到标点/空格
            cut = re.split(r"[，。；、,.!?！？\s]", tail, maxsplit=1)[0]
            cut = cut.strip()
            if 1 <= len(cut) <= 40:
                return cut
    # 无触发词: 文本整体较短(≤12字)且无操作动词, 视为纯地名
    if len(text) <= 12 and not re.search(r"打开|搜索|查|找|看|买|发|回复", text):
        return text
    return ""


# ========================
# 来源 6: 手动输入 (交互兜底)
# ========================


@register_source
class ManualSource(GpsSource):
    name = "manual"
    label = "手动输入"
    priority = 90

    def acquire(self, ctx: GpsContext) -> Optional[LocationInfo]:
        if not ctx.allow_manual or not sys.stdin.isatty():
            return None
        return manual_input(verbose=ctx.verbose)


def manual_input(verbose: bool = True) -> Optional[LocationInfo]:
    """交互式兜底: 用户输入坐标或地址 → 位置信息

    支持: "39.916527,116.397128" (坐标) / "上海市" (地址→地理编码) / 空回车跳过
    """
    if verbose:
        print("[定位] 自动获取未成功。可手动输入位置 (直接回车跳过):")
    for _ in range(3):
        try:
            raw = input("  坐标或地址 (如 39.916527,116.397128 或 上海市) [q=退出]: ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if not raw:
            return None
        if raw.lower() in ("q", "quit", "exit"):
            return None

        pair = parse_coordinate_pair(raw)
        if pair is not None:
            return LocationInfo(
                latitude=pair[0], longitude=pair[1], accuracy=5.0,
                source="手动输入坐标",
            )
        loc = geocode_address(raw)
        if loc is not None:
            return loc
        if verbose:
            print("  无法解析, 请重新输入坐标或地址")
    return None


# ========================
# 统一入口
# ========================


def get_location(
    verbose: bool = True, timeout: float = 15.0, prompt: str = ""
) -> Optional[LocationInfo]:
    """获取当前位置 (自动来源链, 不含手动输入)

    优先级: 文本坐标 → 图片 EXIF → 系统定位 → IP 定位 → 地理编码。
    全部失败返回 None。
    """
    ctx = GpsContext(
        prompt=prompt,
        allow_permission=True,  # 调用方已获用户同意才走到这里
        allow_ip=True,
        allow_manual=False,
        verbose=verbose,
        timeout=timeout,
    )
    return _acquire_chain(ctx)


def _acquire_chain(ctx: GpsContext) -> Optional[LocationInfo]:
    """按降级链依次尝试各来源, 返回第一个成功的结果"""
    for src in iter_sources(ctx):
        try:
            loc = src.acquire(ctx)
        except Exception as e:  # 任何异常都不中断降级链
            if ctx.verbose:
                print(f"[定位] {src.failure_hint(e)}")
            continue
        if loc is not None:
            return loc
    return None


def acquire_gps(
    verbose: bool = True,
    prompt: str = "",
    allow_permission: bool = True,
    allow_ip: bool = True,
    allow_manual: bool = True,
    timeout: float = 15.0,
) -> Optional[str]:
    """获取位置并告知用户结果, 返回 GpsInfo 字符串

    按降级链尝试: 文本坐标 → 图片 EXIF → 系统定位 (需权限) →
    IP 定位 → 地理编码 → 手动输入 (兜底)。

    Args:
        prompt: 用户提示词; 供文本坐标/EXIF/地名解析
        allow_permission: 用户是否允许系统定位 (True = 已授权)
        allow_ip: 是否允许 IP 定位 (用户拒绝自动获取时可关闭)
        allow_manual: 全链失败后是否允许交互式手动输入
        timeout: 系统定位超时 (秒)

    Returns:
        GpsInfo 字符串 (如 "116.397128,39.916527,50,0,0,10"); 失败返回 None
    """
    ctx = GpsContext(
        prompt=prompt,
        allow_permission=allow_permission,
        allow_ip=allow_ip,
        allow_manual=allow_manual,
        verbose=verbose,
        timeout=timeout,
    )
    loc = _acquire_chain(ctx)
    if loc is None:
        if verbose:
            print("[定位] 获取失败, 本次任务不注入 GpsInfo")
        return None

    gps_str = format_gps_info(loc)
    if verbose:
        print(f"[定位] 已获取: {describe_location(loc)}")
        print(f'[定位] GpsInfo 注入值: "{gps_str}"')
    return gps_str


# ========================
# 位置意图判断 (智能询问)
# ========================

# 强信号触发词: 命中任一即认为任务与位置相关, 才询问定位授权
# 设计原则: 宁缺毋滥 —— 只覆盖明确需要位置的场景, 避免无关任务被打扰
LOCATION_KEYWORDS = [
    # 位置/空间词
    "附近", "周边", "地图", "导航", "位置", "定位", "距离",
    "路线", "坐标", "地址", "在哪", "哪里", "方向",
    # 场景词
    "外卖", "打车", "滴滴", "共享单车", "公交", "地铁",
    "餐厅", "美食", "酒店", "民宿", "景点", "探店", "逛街",
    "加油站", "停车场", "医院", "药店", "银行", "超市",
    # 英文/混合
    "gps", "location", "nearby", "map", "navigate",
]

# 明显与位置无关的语境 (避免误报)
LOCATION_NEGATIVE_HINTS = [
    "定位服务", "关闭定位", "设置里", "检查定位", "定位权限",
]


def needs_location(prompt: str) -> bool:
    """判断用户提示词是否与位置相关 (决定是否询问定位授权)

    Args:
        prompt: 用户提示词

    Returns:
        True = 任务可能依赖位置, 值得询问; False = 无关, 跳过询问
    """
    if not prompt:
        return False

    text = prompt.lower()

    # 负向语境优先: 提到的是定位设置本身, 而非需要定位的任务
    for hint in LOCATION_NEGATIVE_HINTS:
        if hint in text:
            return False

    for kw in LOCATION_KEYWORDS:
        if kw in text:
            return True

    return False


def ask_location_permission(prompt: str = "") -> bool:
    """询问用户是否允许获取当前位置

    Args:
        prompt: 用户提示词; 传入时用于判断任务是否与位置相关,
                不相关则直接返回 False (不打扰用户)

    Returns:
        True = 允许; False = 拒绝或无需定位
    """
    # 智能判断: 任务与位置无关时, 跳过询问
    if prompt and not needs_location(prompt):
        return False

    try:
        ans = input("是否允许获取当前位置并注入云手机 GPS? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return ans in ("y", "yes")


if __name__ == "__main__":
    # 独立测试: python geo.py [提示词]
    print("=" * 50)
    print("  多来源 GPS 获取测试")
    print("=" * 50)
    prompt = " ".join(sys.argv[1:])
    gps = acquire_gps(prompt=prompt or "帮我看看附近有什么好吃的")
    if gps:
        print(f"\nGpsInfo: {gps}")
    else:
        print("\n未获取到位置")
