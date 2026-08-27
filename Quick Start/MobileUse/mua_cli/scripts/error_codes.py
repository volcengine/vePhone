"""
Mobile Use Agent - 错误码定义与解析

数据来源: 火山引擎官方文档 (错误码)
https://docs.volcengine.com/docs/6394/1956026?lang=zh

包含:
  1. 公共错误码   - 火山引擎平台通用 (HTTP 层: 网关/参数/资源/认证/授权)
  2. 业务特定错误码 - Mobile Use Agent 任务执行层
     (参数/资源/环境/Agent 执行/HITL 人工介入/模型/工具/安全/平台)
  3. 平台通用认证错误 - 文档未列但实际高频出现 (InvalidAccessKey 等)

设计:
  - MobileUseError:       统一错误异常, 携带错误码/中文描述/操作建议/分类
  - parse_api_error():    从 ApiException 或响应 dict 中解析出 MobileUseError
  - scan_error_in_response(): 递归扫描响应中嵌套的业务错误码
  - format_error():       将错误格式化为可读文本
"""

import json
from typing import Any, Dict, Optional


# ========================
# 错误分类 (供 CLI 差异化引导)
# ========================
CATEGORY_AUTH = "auth"           # 认证/授权
CATEGORY_PARAM = "param"         # 请求参数
CATEGORY_RESOURCE = "resource"   # 资源 (云手机产品/Pod/设备)
CATEGORY_TASK = "task"           # 任务状态
CATEGORY_HITL = "hitl"           # 需要人工介入 (Human-in-the-loop)
CATEGORY_MODEL = "model"         # 大模型
CATEGORY_TOOL = "tool"           # 工具/环境
CATEGORY_SECURITY = "security"   # 安全风控
CATEGORY_PLATFORM = "platform"   # 平台服务
CATEGORY_SYSTEM = "system"       # 系统内部
CATEGORY_UNKNOWN = "unknown"     # 未识别

CATEGORY_LABELS = {
    CATEGORY_AUTH: "认证/授权",
    CATEGORY_PARAM: "请求参数",
    CATEGORY_RESOURCE: "资源",
    CATEGORY_TASK: "任务状态",
    CATEGORY_HITL: "人工介入",
    CATEGORY_MODEL: "模型",
    CATEGORY_TOOL: "工具/环境",
    CATEGORY_SECURITY: "安全风控",
    CATEGORY_PLATFORM: "平台",
    CATEGORY_SYSTEM: "系统",
    CATEGORY_UNKNOWN: "未知",
}


# ========================
# 错误码表
# 每条: (code_n, code, message, desc, advice, category, retryable)
#   code_n    数字错误码
#   code      错误标识 (常量名)
#   message   官方原始错误信息
#   desc      中文描述
#   advice    操作建议
#   category  错误分类
#   retryable 是否建议重试
# ========================

# --- 公共错误码 (HTTP 层, 火山引擎平台通用) ---
_PUBLIC_ERRORS = [
    (500100, "ErrInternalServer", "server internal error",
     "服务内部错误", "请稍后重试", CATEGORY_SYSTEM, True),
    (400100, "ErrParsingParams", "parsing params error",
     "解析请求参数失败", "请检查传入的请求参数是否正确", CATEGORY_PARAM, False),
    (400101, "ErrParamInvalid", "validation fail",
     "参数校验失败", "根据实际报错结果定位报错原因", CATEGORY_PARAM, False),
    (400102, "ErrDBDuplicated", "duplicated",
     "资源重复", "根据实际报错结果定位报错原因", CATEGORY_PARAM, False),
    (400103, "ErrDbMissing", "record not found",
     "资源未找到", "根据实际报错结果定位报错原因", CATEGORY_RESOURCE, False),
    (400105, "ErrCanNotBeEmpty", "can't be empty",
     "参数不能为空", "根据实际报错结果定位报错原因", CATEGORY_PARAM, False),
    (400201, "ErrTaskStillExecuting", "task still being executed",
     "任务仍在执行流程中", "请等待任务执行完成, 或更换 thread_id 重试", CATEGORY_TASK, True),
    (400202, "ErrTaskStatusInvalid", "status err",
     "任务状态不正确", "根据实际报错结果定位报错原因", CATEGORY_TASK, False),
    (400205, "ErrCloudPhoneProductUnavailable",
     "cloud phone product is unavailable or not found",
     "云手机产品不存在、无权限访问或不可用", "请检查 ProductId", CATEGORY_RESOURCE, False),
    (400206, "ErrCloudPhonePodUnavailable",
     "cloud phone pod is unavailable or not found",
     "云手机实例不存在、无权限访问或不可用",
     "请检查 ProductId、PodId 和实例状态", CATEGORY_RESOURCE, False),
    (400207, "ErrCloudPhoneGPSInjectFailed", "GPS inject failed",
     "GPS 注入失败", "请检查 GPS 相关参数配置后重试", CATEGORY_PARAM, False),
    (401100, "ErrAssumeRoleFailed", "AssumeRole failed",
     "跨服务调用未授权",
     "调用前必须先访问跨服务访问请求页面为账号授权 "
     "(https://console.volcengine.com/iam/service/attach_role/?ServiceName=ipaas)",
     CATEGORY_AUTH, False),
]

# --- 业务特定错误码 (Mobile Use Agent 任务执行层) ---
_BIZ_ERRORS = [
    (1000001, "REQUEST_INVALID_ARGS", "参数缺失或参数格式非法",
     "请求参数或参数调用方式问题", "检查 API 入参是否完整且符合规范", CATEGORY_PARAM, False),
    (1000002, "REQUEST_DUPLICATE", "重复提交任务",
     "任务被重复提交", "检查任务是否重复使用", CATEGORY_TASK, False),
    (1000003, "REQUEST_CANCEL_FAILED", "取消执行操作失败",
     "目标任务当前状态不支持取消",
     "先检查该任务的最新执行状态 (是否已完成或已失败); "
     "若状态正常仍报错, 稍后重试或检查业务侧是否重复提交",
     CATEGORY_TASK, False),
    (2000001, "RESOURCE_CLOUDPHONE_UNREACHABLE", "无法连接到云手机",
     "资源不足或调度失败",
     "检查云手机状态; 系统会自动重试, 若长时间未恢复可手动重连或稍后重试",
     CATEGORY_RESOURCE, True),
    (3000001, "ENV_APP_NOT_INSTALLED", "应用 App 未安装",
     "设备/账号/网络环境异常", "在目标实例中安装对应 App 或检查镜像配置",
     CATEGORY_TOOL, False),
    (3000002, "ENV_APP_LAUNCH_FAILED", "应用 App 启动失败",
     "应用运行环境异常", "检查 App 包名、版本是否兼容, 或尝试清理环境后重试",
     CATEGORY_TOOL, True),
    (4000001, "AGENT_MAX_STEP_REACHED", "任务执行步数超过限制",
     "任务执行链路过长", "拆分任务或简化操作流程", CATEGORY_TASK, False),
    (4000002, "AGENT_TOKEN_BUDGET_EXCEEDED", "执行 Token 数超过限制",
     "Token 数消耗超限", "减少不必要的输入或分段执行任务", CATEGORY_MODEL, False),
    (4000003, "AGENT_TIMEOUT", "执行时长超过限制",
     "任务运行超时", "检查任务是否因复杂环境卡顿, 必要时手动介入",
     CATEGORY_TASK, False),
    (4000004, "AGENT_STUCK_LOOP", "陷入循环或重复操作",
     "任务规划陷入死循环", "终止任务并分析可观测链路, 调整提示词或任务目标",
     CATEGORY_TASK, False),
    (4000005, "AGENT_NO_STATE_CHANGE", "执行多次操作无状态变化",
     "操作未生效或 UI 反馈异常",
     "检查当前页面布局及操作是否准确; 系统会自动重试, 若长时间未恢复可手动重试",
     CATEGORY_TASK, True),
    (5000001, "HITL_MORE_INFO", "任务需要人工补充信息",
     "任务执行需要更多信息", "进行 HITL 流程, 由用户补充必要信息",
     CATEGORY_HITL, False),
    (5000002, "HITL_APPROVE", "任务需要人工审批信息",
     "任务执行需要人工审批", "进行 HITL 流程, 由管理人员或用户完成审批",
     CATEGORY_HITL, False),
    (5000003, "HITL_HUMAN_HELP", "任务需要人工协助操作",
     "任务执行需要人工协助", "进行 HITL 流程, 由用户完成手动操作",
     CATEGORY_HITL, False),
    (6000001, "MODEL_CALL_FAILED", "模型调用失败",
     "底层大模型推理服务响应异常", "系统会自动重试; 若多次失败检查模型额度",
     CATEGORY_MODEL, True),
    (6000002, "MODEL_TOKEN_EXCEEDED", "Token 超限/上下文超长",
     "输入内容超过模型最大上下文长度", "精简上下文信息", CATEGORY_MODEL, False),
    (6000003, "MODEL_SAFETY_BLOCK", "模型安全策略拦截",
     "输入或输出内容触碰安全合规红线", "调整任务内容", CATEGORY_SECURITY, False),
    (7000001, "TOOL_CALL_FAILED", "工具调用失败",
     "外部插件或 API 工具响应超时/返回错误", "检查工具", CATEGORY_TOOL, False),
    (7000002, "TOOL_SKILL_FAILED", "技能执行失败",
     "技能执行异常", "检查技能文件路径及配置", CATEGORY_TOOL, False),
    (7000003, "TOOL_SCREENSHOT_FAILED", "截图失败",
     "无法获取当前云手机的屏幕画面", "稍后重试", CATEGORY_TOOL, True),
    (7000004, "TOOL_GUIDE_FETCH_FAILED", "应用操作指南读取失败",
     "操作指南读取异常", "检查操作指南路径及配置", CATEGORY_TOOL, False),
    (7000005, "DEVICE_NOT_AVAILABLE", "设备或节点当前不可用",
     "设备或节点不可用", "检查设备状态, 稍后重试", CATEGORY_RESOURCE, True),
    (7000006, "DEVICE_PERMISSION_DENIED", "设备权限不足或操作被拒绝",
     "设备权限不足", "检查设备权限配置, 稍后重试", CATEGORY_RESOURCE, False),
    (7000007, "DEVICE_CONFIG_ERROR", "设备配置异常或运行环境不满足要求",
     "设备配置异常", "检查设备及运行环境配置, 稍后重试", CATEGORY_RESOURCE, False),
    (8000001, "RESULT_NOT_ACHIEVED", "任务执行失败",
     "任务未能达成目标", "检查任务, 提供更清晰、完整的指令信息",
     CATEGORY_TASK, False),
    (9000001, "SECURITY_BLOCKED", "禁止高风险操作",
     "权限/风控/安全策略拦截高风险操作",
     "调整任务目标, 避免系统级修改或高危敏感操作", CATEGORY_SECURITY, False),
    (9000002, "SECURITY_RISK_CONTROL", "触发安全风控策略",
     "任务内容或执行环节触发平台安全风控",
     "检查输入的指令、数据或操作目标是否含敏感/违规/高风险特征, 调整后重新提交",
     CATEGORY_SECURITY, False),
    (10000001, "PLATFORM_UNKNOWN", "未知错误",
     "平台未知错误", "提交工单联系火山引擎技术支持", CATEGORY_PLATFORM, False),
    (10000002, "PLATFORM_UNAVAILABLE", "服务暂不可用",
     "平台服务暂不可用", "系统会自动重试; 若多次失败提交工单",
     CATEGORY_PLATFORM, True),
    (10000003, "PLATFORM_INCOMPATIBLE", "版本不兼容",
     "API 版本不兼容", "将 API 升级至官方最新版本后重新发起请求",
     CATEGORY_PLATFORM, False),
]

# --- 平台通用认证错误 (文档未列但实际高频出现) ---
_EXTRA_ERRORS = [
    (401, "RequestExpired", "request expired",
     "请求签名已过期", "检查本机系统时间是否准确", CATEGORY_AUTH, False),
    (401, "Unauthorized", "unauthorized",
     "请求未授权", "运行 python cli.py setup 重新配置凭证", CATEGORY_AUTH, False),
    (403, "SignatureDoesNotMatch", "signature does not match",
     "请求签名不匹配", "检查 AK/SK 是否配置正确, 重新运行 python cli.py setup",
     CATEGORY_AUTH, False),
    (403, "AccessDenied", "access denied",
     "无权限访问该资源",
     "检查账号是否开通云手机 Mobile Use Agent 服务, 以及子账号权限配置",
     CATEGORY_AUTH, False),
    (401, "InvalidAccessKey", "invalid access key",
     "AK/SK 无效或已被禁用", "运行 python cli.py setup 重新配置凭证",
     CATEGORY_AUTH, False),
]

# 构建索引: CodeN -> 定义, Code 字符串 -> 定义
_ERROR_INDEX_N: Dict[int, Dict[str, Any]] = {}
_ERROR_INDEX_CODE: Dict[str, Dict[str, Any]] = {}


def _build_index() -> None:
    for code_n, code, message, desc, advice, category, retryable in (
        _PUBLIC_ERRORS + _BIZ_ERRORS + _EXTRA_ERRORS
    ):
        item = {
            "code_n": code_n,
            "code": code,
            "message": message,
            "desc": desc,
            "advice": advice,
            "category": category,
            "retryable": retryable,
        }
        _ERROR_INDEX_N[code_n] = item
        _ERROR_INDEX_CODE[code] = item


_build_index()


def lookup_error(
    code_n: Optional[int] = None,
    code: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """按 CodeN 或 Code 字符串查错误定义

    Args:
        code_n: 数字错误码 (如 400206)
        code:   错误标识 (如 ErrCloudPhonePodUnavailable)

    Returns:
        错误定义 dict 或 None
    """
    # Code 字符串精确唯一, 优先匹配 (CodeN 可能重复, 如 401 有多个认证错误)
    if code:
        item = _ERROR_INDEX_CODE.get(str(code))
        if item:
            return item
    if code_n is not None:
        try:
            item = _ERROR_INDEX_N.get(int(code_n))
        except (TypeError, ValueError):
            item = None
        if item:
            return item
    return None


# ========================
# 统一错误异常
# ========================

class MobileUseError(Exception):
    """带错误码与操作建议的统一异常

    Attributes:
        code_n:      数字错误码 (如 400206)
        code:        错误标识 (如 ErrCloudPhonePodUnavailable)
        message:     原始错误信息
        desc:        中文描述
        advice:      操作建议
        category:    错误分类 (见 CATEGORY_*)
        retryable:   是否可重试
        http_status: HTTP 状态码
    """

    def __init__(
        self,
        code_n: Optional[int] = None,
        code: str = "",
        message: str = "",
        desc: str = "",
        advice: str = "",
        category: str = CATEGORY_UNKNOWN,
        retryable: bool = False,
        http_status: Optional[int] = None,
    ):
        self.code_n = code_n
        self.code = code
        self.message = message
        self.desc = desc
        self.advice = advice
        self.category = category
        self.retryable = retryable
        self.http_status = http_status
        super().__init__(self.__str__())

    def __str__(self) -> str:
        parts = []
        if self.code_n is not None:
            parts.append(f"[{self.code_n}]")
        if self.code:
            parts.append(self.code)
        label = CATEGORY_LABELS.get(self.category, self.category)
        parts.append(f"({label})")
        parts.append(self.desc or self.message or "未知错误")
        return " ".join(parts)


# ========================
# 解析器
# ========================

def parse_api_error(source: Any) -> Optional[MobileUseError]:
    """从 API 响应或 ApiException 中解析错误

    覆盖两种通道:
      1. HTTP 200 但业务错误 -> do_call 返回的响应 dict 中带 ResponseMetadata.Error
      2. HTTP 非 2xx -> ApiException, 从 body JSON 中解析, 或按状态码兜底

    Args:
        source: ApiException | dict (响应体) | str (JSON 文本)

    Returns:
        MobileUseError 或 None (无错误)
    """
    http_status = None
    body = None

    if isinstance(source, dict):
        body = source
        http_status = _extract_http_status(source)
    elif isinstance(source, str):
        try:
            body = json.loads(source)
        except Exception:
            body = None
    else:
        # ApiException 及其它异常对象
        http_status = getattr(source, "status", None)
        raw = getattr(source, "body", None)
        if raw is None:
            raw = getattr(source, "reason", None)
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8", errors="replace")
        if isinstance(raw, str):
            stripped = raw.strip()
            if stripped.startswith("{"):
                try:
                    body = json.loads(stripped)
                except Exception:
                    body = None
            elif stripped and http_status in (401, 403):
                # 无 body 的认证错误: 直接按状态码兜底
                return _build_http_fallback(http_status, stripped)

    # 1. 从 body 中找 ResponseMetadata.Error
    if isinstance(body, dict):
        err_obj = None
        meta = body.get("ResponseMetadata")
        if isinstance(meta, dict) and isinstance(meta.get("Error"), dict):
            err_obj = meta["Error"]
        elif isinstance(body.get("Error"), dict):
            err_obj = body["Error"]

        if isinstance(err_obj, dict):
            code_n = err_obj.get("CodeN")
            code = err_obj.get("Code")
            message = str(err_obj.get("Message") or "")
            # 火山引擎标准错误对象必须含 Code/CodeN/Message 至少一个,
            # 否则不是错误对象 (避免误判嵌套的业务字段如 {'ErrorCode': ...})
            if code_n is None and not code and not message:
                err_obj = None

        if isinstance(err_obj, dict):
            code_n = err_obj.get("CodeN")
            code = err_obj.get("Code")
            message = str(err_obj.get("Message") or "")
            item = lookup_error(code_n=code_n, code=code)
            if item:
                return MobileUseError(
                    # 优先保留响应中的真实 CodeN/Code, 查表值仅作兜底
                    code_n=code_n if code_n is not None else item["code_n"],
                    code=code or item["code"],
                    message=message,
                    desc=item["desc"],
                    advice=item["advice"],
                    category=item["category"],
                    retryable=item["retryable"],
                    http_status=http_status,
                )
            # 未知错误码: 保留原始信息
            return MobileUseError(
                code_n=code_n,
                code=code or "",
                message=message,
                desc=f"未知错误码 ({code_n or code or '?'})",
                advice="请提交工单联系火山引擎技术支持",
                category=CATEGORY_UNKNOWN,
                retryable=False,
                http_status=http_status,
            )

    # 2. HTTP 层错误且无 body: 按状态码兜底
    if http_status in (401, 403):
        return _build_http_fallback(http_status, "")

    return None


def _extract_http_status(body: Dict[str, Any]) -> Optional[int]:
    """从响应 dict 中尽力提取 HTTP 状态码"""
    meta = body.get("ResponseMetadata")
    if isinstance(meta, dict):
        for key in ("HTTPCode", "HttpCode", "StatusCode", "Status"):
            val = meta.get(key)
            if val is not None:
                try:
                    return int(val)
                except (TypeError, ValueError):
                    pass
    return None


def _build_http_fallback(http_status: int, message: str) -> MobileUseError:
    """HTTP 401/403 无 body 时按状态码生成兜底错误"""
    item = lookup_error(code_n=http_status)
    if item:
        return MobileUseError(
            code_n=item["code_n"],
            code=item["code"],
            message=message,
            desc=item["desc"],
            advice=item["advice"],
            category=item["category"],
            retryable=item["retryable"],
            http_status=http_status,
        )
    return MobileUseError(
        code_n=http_status,
        code="",
        message=message,
        desc=f"HTTP {http_status} 请求失败",
        advice="请稍后重试",
        category=CATEGORY_UNKNOWN,
        retryable=True,
        http_status=http_status,
    )


def scan_error_in_response(data: Any, max_depth: int = 5) -> Optional[MobileUseError]:
    """递归扫描响应中嵌套的业务错误码

    GetAgentResult 任务失败时, 失败原因可能嵌套在 Result 或步骤结果中,
    用本函数递归查找已知错误码并返回对应定义。

    Args:
        data: 响应 dict / list / 任意值
        max_depth: 最大递归深度, 防止环形结构

    Returns:
        MobileUseError 或 None
    """
    if max_depth < 0:
        return None
    if isinstance(data, dict):
        # 直接解析 (ResponseMetadata.Error / 顶层 Error)
        err = parse_api_error(data)
        if err:
            return err
        # 检查常见错误码字段
        for key in ("ErrorCodeN", "CodeN", "ErrorCode", "Code"):
            val = data.get(key)
            if val is None:
                continue
            item = None
            if isinstance(val, (int, float)):
                item = lookup_error(code_n=int(val))
            elif isinstance(val, str) and val.strip().isdigit():
                item = lookup_error(code_n=int(val.strip()))
            elif isinstance(val, str):
                item = lookup_error(code=val)
            if item:
                # 保留响应中的真实错误码, 查表值仅提供描述/建议
                real_code_n = None
                if isinstance(val, (int, float)):
                    real_code_n = int(val)
                elif isinstance(val, str) and val.strip().isdigit():
                    real_code_n = int(val.strip())
                return MobileUseError(
                    code_n=real_code_n if real_code_n is not None else item["code_n"],
                    code=item["code"],
                    message=str(data.get("ErrorMsg") or data.get("Message") or ""),
                    desc=item["desc"],
                    advice=item["advice"],
                    category=item["category"],
                    retryable=item["retryable"],
                )
        for v in data.values():
            err = scan_error_in_response(v, max_depth - 1)
            if err:
                return err
    elif isinstance(data, list):
        for v in data:
            err = scan_error_in_response(v, max_depth - 1)
            if err:
                return err
    return None


def format_error(err: MobileUseError) -> str:
    """将 MobileUseError 格式化为 CLI 可读文本"""
    label = CATEGORY_LABELS.get(err.category, err.category)
    lines = []
    head = []
    if err.code_n is not None:
        head.append(str(err.code_n))
    if err.code:
        head.append(err.code)
    head.append(f"[{label}]")
    lines.append(" ".join(head))
    if err.desc:
        lines.append(f"  描述: {err.desc}")
    if err.advice:
        lines.append(f"  建议: {err.advice}")
    lines.append(f"  {'可重试' if err.retryable else '不可重试, 需人工处理'}")
    return "\n".join(lines)


# ========================
# 人话版错误 (面向 0 基础用户)
# 按错误标识映射: (发生了什么, 你该怎么办)
# 覆盖小白最可能遇到的场景; 未命中的走分类兜底
# ========================
FRIENDLY_ACTIONS = {
    "ErrAssumeRoleFailed": (
        "还没有给云手机服务开授权",
        "打开下面的链接，点「一键授权」即可：\n"
        "   https://console.volcengine.com/iam/service/attach_role/?ServiceName=ipaas",
    ),
    "InvalidAccessKey": (
        "填写的密钥不对，或者密钥已被停用",
        "运行 mua setup 重新填写 AK/SK；还不行就去火山引擎控制台确认密钥状态",
    ),
    "SignatureDoesNotMatch": (
        "密钥好像复制得不完整，或前后带了空格",
        "运行 mua setup 重新粘贴 AK/SK，注意前后不要留空格",
    ),
    "AccessDenied": (
        "这个账号没有使用云手机服务的权限",
        "检查是否已开通「云手机 Mobile Use Agent」服务；子账号需要在主账号下获得授权",
    ),
    "Unauthorized": (
        "登录凭证有问题",
        "运行 mua setup 重新配置 AK/SK",
    ),
    "RequestExpired": (
        "请求签名过期了，通常是电脑系统时间不准",
        "打开系统设置开启「自动设置时间」，然后重试",
    ),
    "ErrCloudPhoneProductUnavailable": (
        "云手机业务（ProductId）不存在、没开通或填错了",
        "到云手机控制台确认 ProductId 正确，且该业务已开通 Mobile Use Agent",
    ),
    "ErrCloudPhonePodUnavailable": (
        "云手机实例（PodId）不存在、没开机或填错了",
        "到云手机控制台确认 PodId 正确，且实例处于运行状态",
    ),
    "ErrCloudPhoneGPSInjectFailed": (
        "位置信息没能注入到云手机",
        "重新试一次；如果一直失败，可以跳过定位继续做任务",
    ),
    "RESOURCE_CLOUDPHONE_UNREACHABLE": (
        "云手机暂时连不上",
        "稍等片刻会自动重试；很久没恢复的话，去控制台重启一下实例",
    ),
    "ENV_APP_NOT_INSTALLED": (
        "云手机上没有安装要用到的 App",
        "先到云手机里安装这个 App，再重新发起任务",
    ),
    "ENV_APP_LAUNCH_FAILED": (
        "App 打不开或运行异常",
        "确认云手机里的 App 版本正常，重启一次再试",
    ),
    "AGENT_MAX_STEP_REACHED": (
        "任务步骤太多，超过了限制",
        "把大任务拆成几个小任务，一次只做一件事",
    ),
    "AGENT_TOKEN_BUDGET_EXCEEDED": (
        "任务内容太长，超过了模型的处理上限",
        "简化任务描述，去掉不必要的细节",
    ),
    "AGENT_TIMEOUT": (
        "任务运行超时了",
        "把任务拆小一点，或换成更直接的说法再试",
    ),
    "AGENT_STUCK_LOOP": (
        "Agent 在原地打转，陷入重复操作",
        "换个说法重新描述任务，或取消后重新发起",
    ),
    "RESULT_NOT_ACHIEVED": (
        "任务没有成功完成",
        "换个更清楚、更具体的说法再试一次，比如把目标拆成一步步的操作",
    ),
    "MODEL_SAFETY_BLOCK": (
        "内容触碰了安全限制，被模型拦下了",
        "换个说法或换一个目标再试",
    ),
    "SECURITY_BLOCKED": (
        "这个操作被安全策略判定为高风险，被拦下了",
        "调整任务目标，避免系统级修改、绕过限制等高风险操作",
    ),
    "SECURITY_RISK_CONTROL": (
        "任务内容触发了平台安全风控",
        "检查指令里有没有敏感、违规的内容，调整后再试",
    ),
    "HITL_MORE_INFO": (
        "任务需要你补充一些信息",
        "按提示补上缺失的信息，然后重新发起任务",
    ),
    "HITL_APPROVE": (
        "任务需要有人审批确认",
        "联系管理员或主账号完成审批",
    ),
    "HITL_HUMAN_HELP": (
        "任务需要人工协助操作",
        "在云手机里完成需要的手动操作，然后重试",
    ),
    "MODEL_CALL_FAILED": (
        "AI 模型服务暂时不稳定",
        "稍等片刻再重试",
    ),
    "TOOL_SCREENSHOT_FAILED": (
        "截取云手机屏幕画面失败了",
        "稍后重试",
    ),
    "PLATFORM_UNAVAILABLE": (
        "平台服务暂时不稳定",
        "稍等片刻再重试",
    ),
    "PLATFORM_INCOMPATIBLE": (
        "接口版本不兼容",
        "将项目更新到最新版本后重试",
    ),
    "ErrParsingParams": (
        "填写的参数格式有问题",
        "检查输入内容，或重新跑一次向导 (mua run)",
    ),
    "ErrParamInvalid": (
        "填写的参数校验没通过",
        "检查输入内容，或重新跑一次向导 (mua run)",
    ),
    "ErrDbMissing": (
        "找不到对应的记录",
        "检查填写的 ID 是否复制完整",
    ),
}

_CATEGORY_FRIENDLY = {
    CATEGORY_AUTH: (
        "登录或权限方面出了问题",
        "按提示检查密钥和授权；可以用 mua setup 重新配置",
    ),
    CATEGORY_RESOURCE: (
        "云手机资源方面出了问题",
        "到云手机控制台确认 ProductId、PodId 正确，实例已开通且处于运行状态",
    ),
    CATEGORY_PARAM: (
        "填写的参数有问题",
        "检查输入有没有拼写或格式错误，再试一次",
    ),
    CATEGORY_TASK: (
        "任务没有按预期完成",
        "换个更清晰、更具体的说法再试一次",
    ),
    CATEGORY_HITL: (
        "任务需要你参与一下",
        "按提示补充信息或完成确认",
    ),
    CATEGORY_MODEL: (
        "AI 模型那边出了点问题",
        "稍等片刻重试一次",
    ),
    CATEGORY_TOOL: (
        "云手机上的应用或工具出了问题",
        "检查云手机里相关的 App 是否已安装、是否正常",
    ),
    CATEGORY_SECURITY: (
        "操作被安全策略拦下了",
        "换个说法或换个操作目标再试",
    ),
    CATEGORY_PLATFORM: (
        "平台服务暂时不稳定",
        "稍等片刻再试；反复失败可联系火山引擎技术支持",
    ),
    CATEGORY_SYSTEM: (
        "遇到一个少见的问题",
        "记下上面的错误信息，稍后重试，或联系火山引擎技术支持",
    ),
    CATEGORY_UNKNOWN: (
        "遇到一个没见过的问题",
        "记下错误信息，稍后重试，或联系火山引擎技术支持",
    ),
}


def format_friendly_error(err: MobileUseError, context: str = "") -> str:
    """将错误翻译成 0 基础用户看得懂的话

    输出两行核心信息:
      - 发生了什么 (人话解释)
      - 你该怎么办 (具体动作)
    技术细节 (错误码/分类/是否可重试) 折叠成一行小字附后。

    Args:
        err: MobileUseError
        context: 可选的上下文前缀 (如 "第 2 步出错了")

    Returns:
        人话版错误文本
    """
    what, how = FRIENDLY_ACTIONS.get(err.code) or _CATEGORY_FRIENDLY.get(
        err.category, _CATEGORY_FRIENDLY[CATEGORY_UNKNOWN]
    )

    lines = []
    if context:
        lines.append(f"[{context}]")
    else:
        lines.append("[出错了]")
    lines.append(f"  发生了什么：{what}")
    lines.append(f"  你该怎么办：{how}")

    # 技术细节折叠成一行 (给愿意深究的用户)
    tech = []
    if err.code_n is not None:
        tech.append(str(err.code_n))
    if err.code:
        tech.append(err.code)
    label = CATEGORY_LABELS.get(err.category, err.category)
    tech.append(f"[{label}]")
    tech.append("可重试" if err.retryable else "不可自动恢复")
    lines.append(f"  (技术信息: {' '.join(tech)})")
    return "\n".join(lines)
