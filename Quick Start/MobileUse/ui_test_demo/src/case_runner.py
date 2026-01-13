from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from queue import Queue, Empty
from threading import Lock, Thread, Event
from typing import Any, Callable, Dict, List, Optional, Tuple
import atexit
import json
import logging
import os
import re
import signal
import time

from .env_utils import load_env_from_root
from .mobile_use import MobileUseClient, ResultItem


@dataclass(frozen=True)
class CaseFile:
    index: int
    path: Path
    content: str


@dataclass(frozen=True)
class RunnerConfig:
    timeout_s: int = 600
    poll_interval_s: float = 2.0
    run_api: str = "one_step"  # one_step | task
    use_status_api: bool = True  # 兼容保留：当前实现以 ListAgentRunCurrentStep 为主
    use_base64_screenshot: bool = True
    screen_record: bool = False
    exec_mode: str = "auto"  # serial | parallel | auto


def parse_pod_id_list(value: str) -> List[str]:
    return [s.strip() for s in (value or "").split(",") if s.strip()]


def discover_cases(cases_dir: Path) -> List[CaseFile]:
    patterns = ("*.md", "*.case")
    files: List[Path] = []
    for p in patterns:
        files.extend(cases_dir.rglob(p))

    files = sorted(f for f in files if f.is_file())

    raw_filter = os.environ.get("CASE_FILTER", "").strip()
    filters: List[str] = [s.strip() for s in raw_filter.split(",") if s.strip()] if raw_filter else []

    filtered: List[Path] = []
    for f in files:
        if f.name.startswith("."):
            continue
        if f.stem.lower() == "template":
            continue
        if filters:
            rel = str(f.relative_to(cases_dir))
            if not any(token in rel for token in filters):
                continue
        filtered.append(f)

    cases: List[CaseFile] = []
    for idx, path in enumerate(filtered):
        cases.append(CaseFile(index=idx, path=path, content=path.read_text(encoding="utf-8")))
    return cases


def _iso_now() -> str:
    bj_tz = timezone(timedelta(hours=8))
    return datetime.now(bj_tz).strftime("%Y-%m-%d %H:%M:%S")


def _coerce_is_success_code(val: Any) -> Optional[int]:
    if val is None:
        return None
    if isinstance(val, bool):
        return 1 if val else 0
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        s = val.strip()
        if s.isdigit():
            try:
                return int(s)
            except Exception:
                return None
    return None


def _extract_request_user_from_text(text: str) -> Optional[str]:
    if not isinstance(text, str) or not text:
        return None
    if "request_user" not in text:
        return None

    # 常见：err_msg: {'request_user': '...'} 或 {"request_user": "..."}
    m = re.search(r"request_user['\"]?\s*[:：]\s*['\"]([^'\"]+)['\"]", text)
    if m:
        return m.group(1).strip() or None

    # 找不到结构化字段时，直接返回截断文本
    return text.strip()[:500] or None


def _find_request_user_in_obj(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, str):
        return _extract_request_user_from_text(obj)
    if isinstance(obj, dict):
        if "request_user" in obj:
            v = obj.get("request_user")
            if isinstance(v, str) and v.strip():
                return v.strip()
            if v is not None:
                return str(v)
        for _k, v in obj.items():
            hit = _find_request_user_in_obj(v)
            if hit:
                return hit
        return None
    if isinstance(obj, list):
        for v in obj:
            hit = _find_request_user_in_obj(v)
            if hit:
                return hit
        return None
    return None


def _extract_current_step_signal(resp: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str]]:
    """基于 ListAgentRunCurrentStep 判断是否结束。

    结束条件（按你描述）：
    - Results[*].Action == "finished"
    - 或 Results[*].Action == "request_user"
    - 或任意位置出现 request_user（常见于 Param / content / StepResult.Result 等）
    返回：(done, signal, hint)
    signal: "finished" | "request_user" | None
    hint: 可读提示（content/request_user 文本）
    """
    if not isinstance(resp, dict) or not resp:
        return False, None, None

    if resp.get("Error"):
        return False, None, None

    payload: Any = resp.get("Result") if isinstance(resp.get("Result"), dict) else resp
    if not isinstance(payload, dict):
        return False, None, None

    results = payload.get("Results") or payload.get("results")
    if not isinstance(results, list) or not results:
        hit = _find_request_user_in_obj(payload)
        if hit:
            return True, "request_user", hit
        return False, None, None

    for it in results:
        if not isinstance(it, dict):
            continue

        action = str(it.get("Action") or "").strip().lower()

        def _extract_hint_from_step(step: Dict[str, Any]) -> Optional[str]:
            param = step.get("Param")
            step_result = step.get("StepResult")

            if isinstance(param, dict):
                c = param.get("content")
                if isinstance(c, str) and c.strip():
                    return c.strip()

            if isinstance(step_result, dict):
                r = step_result.get("Result")
                if isinstance(r, str) and r.strip():
                    return r.strip()

            return None

        if action == "finished":
            return True, "finished", _extract_hint_from_step(it)

        if action == "request_user":
            # 明确动作是 request_user：立即进入“拉取最终结果”阶段
            hit = _find_request_user_in_obj(it)
            return True, "request_user", hit or _extract_hint_from_step(it)

        # 动作不是 request_user，但任意位置出现 request_user，也认为结束
        hit = _find_request_user_in_obj(it)
        if hit:
            return True, "request_user", hit

    return False, None, None


_active_run_ids_lock = Lock()
_active_run_ids: set[str] = set()

_cancel_task_resp_lock = Lock()
_cancel_task_resp_by_run_id: Dict[str, Dict[str, Any]] = {}

_shutdown_event = Event()
_exit_handlers_installed = False


def _register_active_run_id(run_id: str) -> None:
    rid = (run_id or "").strip()
    if not rid:
        return
    with _active_run_ids_lock:
        _active_run_ids.add(rid)


def _unregister_active_run_id(run_id: str) -> None:
    rid = (run_id or "").strip()
    if not rid:
        return
    with _active_run_ids_lock:
        _active_run_ids.discard(rid)


def _remember_cancel_task_resp(run_id: str, resp: Optional[Dict[str, Any]]) -> None:
    rid = (run_id or "").strip()
    if not rid or not isinstance(resp, dict):
        return
    with _cancel_task_resp_lock:
        _cancel_task_resp_by_run_id[rid] = resp


def _get_cancel_task_resp(run_id: str) -> Optional[Dict[str, Any]]:
    rid = (run_id or "").strip()
    if not rid:
        return None
    with _cancel_task_resp_lock:
        return _cancel_task_resp_by_run_id.get(rid)


def _cancel_task_best_effort(*, client: Optional[MobileUseClient], run_id: str, reason: str) -> Optional[Dict[str, Any]]:
    rid = (run_id or "").strip()
    if not rid:
        return None

    cached = _get_cancel_task_resp(rid)
    if isinstance(cached, dict):
        return cached

    try:
        c = client or MobileUseClient()
        cancel_fn = getattr(c, "cancel_task_raw", None)
        if not callable(cancel_fn):
            logging.warning("CancelTask 不可用：MobileUseClient.cancel_task_raw 不存在")
            return None

        resp = cancel_fn(rid)
        if isinstance(resp, dict):
            _remember_cancel_task_resp(rid, resp)
            logging.info(f"CancelTask 已触发 run_id={rid} reason={reason}")
            return resp

        logging.warning(f"CancelTask 返回非 JSON 对象 run_id={rid} reason={reason}")
        return None
    except Exception as e:
        logging.warning(f"CancelTask 异常 run_id={rid} reason={reason} err={type(e).__name__}: {e}")
        return None


def _extract_cancel_summary(resp: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
    if not isinstance(resp, dict):
        return False, "CancelTask 未返回响应"

    if "Result" not in resp:
        return False, "CancelTask 响应缺少 Result"

    if resp.get("Result") is None:
        return False, "CancelTask Result 为空"

    return True, None


def _attach_cancel_summary(out: Dict[str, Any], resp: Optional[Dict[str, Any]]) -> None:
    ok, msg = _extract_cancel_summary(resp)
    out["cancel_ok"] = bool(ok)
    out["cancel_error_message"] = msg


def _cancel_all_active_runs(reason: str) -> None:
    try:
        with _active_run_ids_lock:
            run_ids = list(_active_run_ids)

        if not run_ids:
            return

        logging.warning(f"{reason}：尝试取消未结束任务，共 {len(run_ids)} 个")
        shared_client = MobileUseClient()
        for rid in run_ids:
            _cancel_task_best_effort(client=shared_client, run_id=rid, reason=reason)
    except Exception as e:
        logging.warning(f"批量 CancelTask 异常 reason={reason} err={type(e).__name__}: {e}")


def _install_exit_handlers_once() -> None:
    global _exit_handlers_installed
    if _exit_handlers_installed:
        return
    _exit_handlers_installed = True

    def _atexit_handler() -> None:
        try:
            _shutdown_event.set()
            _cancel_all_active_runs("进程退出（atexit）")
        except Exception:
            return

    atexit.register(_atexit_handler)

    def _signal_handler(sig: int, _frame: Any) -> None:
        try:
            if _shutdown_event.is_set():
                return
            _shutdown_event.set()
            Thread(target=_cancel_all_active_runs, name="cancel-all", args=(f"收到信号 {sig}",), daemon=True).start()
            if sig == getattr(signal, "SIGINT", None):
                raise KeyboardInterrupt
        except Exception:
            return

    for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
        if isinstance(sig, int):
            try:
                signal.signal(sig, _signal_handler)
            except Exception:
                continue


def _list_agent_run_current_step_raw(*, client: MobileUseClient, run_id: str) -> Dict[str, Any]:
    fn = getattr(client, "list_agent_run_current_step_raw", None)
    if callable(fn):
        try:
            return fn(run_id=run_id)
        except TypeError:
            # 兼容未来签名变化
            return fn(run_id)

    # fallback：如果 mobile_use.py 还没合并该 wrapper
    do_call = getattr(client, "_do_call_universal", None)
    if callable(do_call):
        return do_call(method="GET", action="ListAgentRunCurrentStep", body={"RunId": run_id})

    return {}


def _is_done_by_get_result(resp: Dict[str, Any]) -> bool:
    """GetAgentResult 是否已产生终态结果（按 IsSuccess 枚举）。"""
    if not isinstance(resp, dict) or not resp:
        return False

    if resp.get("Error"):
        return True

    payload: Any
    if "Result" in resp:
        payload = resp.get("Result")
        if payload is None:
            return True
    else:
        payload = resp

    if not isinstance(payload, dict):
        return False

    code = _coerce_is_success_code(payload.get("IsSuccess"))
    if code is None:
        return False

    # 0=NOT_COMPLETED：未完成
    return code != 0


def _coerce_case_status(val: Any) -> Optional[str]:
    if not isinstance(val, str):
        return None
    v = val.strip().lower()
    if v in {"pass", "fail", "skip"}:
        return v
    return None


def _extract_json_object(text: str, start_idx: int) -> Optional[str]:
    if not isinstance(text, str):
        return None
    if start_idx < 0 or start_idx >= len(text) or text[start_idx] != "{":
        return None

    depth = 0
    in_string = False
    escaped = False

    for i in range(start_idx, len(text)):
        ch = text[i]

        if in_string:
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                return text[start_idx : i + 1]
            continue

    return None


def _try_parse_json_obj(text: str) -> Optional[Dict[str, Any]]:
    if not isinstance(text, str) or not text.strip():
        return None

    s = text.strip()

    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    if '\\"' in s or "\\n" in s:
        s2 = s.replace('\\"', '"').replace("\\\\", "\\")
        try:
            obj = json.loads(s2)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    return None


def _infer_case_status_reason_from_struct_output(struct_output: Any) -> Tuple[Optional[str], Optional[str]]:
    if isinstance(struct_output, dict):
        st = _coerce_case_status(struct_output.get("status") or struct_output.get("Status"))
        rs = struct_output.get("reason") or struct_output.get("Reason")
        reason = rs.strip() if isinstance(rs, str) and rs.strip() else None
        return st, reason

    if isinstance(struct_output, str) and struct_output.strip():
        obj = _try_parse_json_obj(struct_output)
        if isinstance(obj, dict):
            st = _coerce_case_status(obj.get("status") or obj.get("Status"))
            rs = obj.get("reason") or obj.get("Reason")
            reason = rs.strip() if isinstance(rs, str) and rs.strip() else None
            return st, reason

    return None, None


def _infer_case_status_reason_from_content(content: Any) -> Tuple[Optional[str], Optional[str]]:
    if not isinstance(content, str) or not content.strip():
        return None, None

    text = content.strip()

    m = re.search(r"最终状态\s*[:：]\s*(pass|fail|skip)\b", text, flags=re.IGNORECASE)
    if m:
        return _coerce_case_status(m.group(1)), None

    start = text.rfind('{"status"')
    if start < 0:
        start = text.rfind('{\\"status\\"')

    if start >= 0:
        json_blob = _extract_json_object(text, start)
        if isinstance(json_blob, str) and json_blob.strip():
            obj = _try_parse_json_obj(json_blob)
            if isinstance(obj, dict):
                st = _coerce_case_status(obj.get("status") or obj.get("Status"))
                rs = obj.get("reason") or obj.get("Reason")
                reason = rs.strip() if isinstance(rs, str) and rs.strip() else None
                return st, reason

    m2 = re.search(r"失败原因\s*[:：]\s*(.+)", text)
    if m2:
        return "fail", m2.group(1).strip() or None

    return None, None


def _infer_case_status_reason_from_result_payload(result_payload: Any) -> Tuple[Optional[str], Optional[str]]:
    if not isinstance(result_payload, dict):
        return None, None

    st, reason = _infer_case_status_reason_from_struct_output(result_payload.get("StructOutput"))
    if st:
        return st, reason

    return _infer_case_status_reason_from_content(result_payload.get("Content"))


def _result_from_resp(
    *,
    client: MobileUseClient,
    case_name: str,
    run_id: str,
    pod_id: Optional[str],
    started_at_ms: int,
    resp: Dict[str, Any],
    timeout: bool,
) -> Dict[str, Any]:
    finished_at_ms = int(time.time() * 1000)
    duration_ms = max(0, finished_at_ms - started_at_ms)

    status = "pass"
    reason = ""

    # 兼容：{"Result": {...}} 或 顶层 payload
    result_payload: Any = None
    if isinstance(resp, dict):
        if "Result" in resp:
            result_payload = resp.get("Result")
        elif any(k in resp for k in ("IsSuccess", "Content", "StructOutput", "ScreenShots", "Usage")):
            result_payload = resp

    if timeout:
        status = "fail"
        reason = "等待任务完成超时"
    else:
        top_err = (resp or {}).get("Error")
        if top_err:
            status = "fail"
            if isinstance(top_err, dict):
                reason = str(top_err.get("Message") or top_err)
            else:
                reason = str(top_err)

        if result_payload is None:
            if status == "pass":
                status = "fail"
                reason = "GetAgentResult 返回为空"
        elif isinstance(result_payload, dict):
            code = _coerce_is_success_code(result_payload.get("IsSuccess"))
            content = result_payload.get("Content")
            content_msg = str(content) if isinstance(content, str) else ""

            # 0 NOT_COMPLETED -> 未完成
            # 1 SUCCESS -> pass
            # 2 EXEC_FAILED -> fail
            # 3 COMPLETED_BUT_NO_MESSAGE -> pass
            # 4 USER_INTERRUPT -> fail
            # 5 USER_CANCELLED -> skip
            # 6 UNKNOWN_ERROR -> fail
            if code is None:
                if status == "pass":
                    status = "fail"
                if not reason:
                    reason = "GetAgentResult IsSuccess 缺失/类型异常"
            elif code == 0:
                if status == "pass":
                    status = "fail"
                if not reason:
                    reason = "任务未完成（NOT_COMPLETED）"
            elif code in (1, 3):
                pass
            elif code == 5:
                status = "skip"
                if not reason:
                    reason = content_msg or "用户取消（USER_CANCELLED）"
            else:
                status = "fail"
                if not reason:
                    if content_msg:
                        reason = content_msg
                    elif code == 2:
                        reason = "任务执行失败（EXEC_FAILED）"
                    elif code == 4:
                        reason = "用户中断（USER_INTERRUPT）"
                    elif code == 6:
                        reason = "未知错误（UNKNOWN_ERROR）"
                    else:
                        reason = f"任务失败（IsSuccess={code}）"
        else:
            status = "fail"
            if not reason:
                reason = "GetAgentResult Result 类型异常"

    inferred_status, inferred_reason = _infer_case_status_reason_from_result_payload(result_payload)
    if status == "pass" and inferred_status in {"fail", "skip"}:
        status = inferred_status
        if inferred_reason:
            reason = inferred_reason
    elif status in {"fail", "skip"} and inferred_reason and not reason:
        reason = inferred_reason

    in_tokens: Optional[int] = None
    out_tokens: Optional[int] = None

    if isinstance(result_payload, dict):
        usage = result_payload.get("Usage")
        if isinstance(usage, dict):
            it = usage.get("in_tokens")
            ot = usage.get("out_tokens")
            if isinstance(it, int):
                in_tokens = it
            elif isinstance(it, str) and it.isdigit():
                in_tokens = int(it)
            if isinstance(ot, int):
                out_tokens = ot
            elif isinstance(ot, str) and ot.isdigit():
                out_tokens = int(ot)

    screenshot_urls: List[str] = []
    original_dimensions: Optional[List[int]] = None
    screenshot_dimensions: Optional[List[int]] = None

    def _dims_to_list(val: Any) -> Optional[List[int]]:
        if isinstance(val, (list, tuple)) and len(val) == 2:
            a, b = val
            try:
                return [int(a), int(b)]
            except Exception:
                return None
        return None

    if isinstance(result_payload, dict):
        screenshots = result_payload.get("ScreenShots")
        if isinstance(screenshots, dict) and screenshots:
            first_item: Optional[Dict[str, Any]] = None
            seen: set[str] = set()

            for _k, it in screenshots.items():
                if not isinstance(it, dict):
                    continue

                if first_item is None:
                    first_item = it

                v = it.get("screenshot") or it.get("original_screenshot")
                if isinstance(v, str) and v.strip():
                    url = v.strip()
                    if url not in seen:
                        seen.add(url)
                        screenshot_urls.append(url)

            if first_item is not None:
                tmp = _dims_to_list(first_item.get("original_dimensions"))
                if tmp is not None:
                    original_dimensions = tmp

                tmp = _dims_to_list(first_item.get("screenshot_dimensions"))
                if tmp is not None:
                    screenshot_dimensions = tmp

    aosp_version: Optional[str] = None
    image_name: Optional[str] = None
    image_id: Optional[str] = None
    try:
        helper = getattr(client, "_get_pod_image_info", None)
        effective_pod_id = pod_id or getattr(client, "pod_id", None)
        if callable(helper):
            pod_info = helper(effective_pod_id)
            if isinstance(pod_info, dict):
                aosp_version = pod_info.get("aosp_version")
                image_name = pod_info.get("image_name")
                image_id = pod_info.get("image_id")
    except Exception:
        pass

    item = ResultItem(
        case=case_name,
        status=status,
        timestamp=_iso_now(),
        duration_ms=duration_ms,
        reason=reason,
        screenshot=screenshot_urls,
        in_tokens=in_tokens,
        out_tokens=out_tokens,
        original_dimensions=original_dimensions,
        screenshot_dimensions=screenshot_dimensions,
        aosp_version=aosp_version,
        image_name=image_name,
        image_id=image_id,
        pod_id=pod_id,
        run_id=run_id,
    )
    data = item.to_dict()

    if isinstance(result_payload, dict):
        content = result_payload.get("Content")
        if isinstance(content, str) and content.strip():
            data["content"] = content
        struct_output = result_payload.get("StructOutput")
        if struct_output not in (None, {}, []):
            data["struct_output"] = struct_output

    return data


def run_one_case(
    *,
    client: MobileUseClient,
    case: CaseFile,
    root: Path,
    system_prompt: str,
    pod_id: str,
    product_id: str,
    cfg: RunnerConfig,
) -> Dict[str, Any]:
    started_at_ms = int(time.time() * 1000)
    case_name = str(case.path.relative_to(root))

    if _shutdown_event.is_set():
        item = ResultItem(
            case=case_name,
            status="skip",
            timestamp=_iso_now(),
            duration_ms=0,
            reason="本地中断，未执行",
            screenshot=[],
            pod_id=pod_id,
            run_id=None,
        )
        return item.to_dict()

    user_prompt = case.content.strip()
    if not user_prompt:
        aosp_version = None
        image_name = None
        image_id = None
        try:
            helper = getattr(client, "_get_pod_image_info", None)
            if callable(helper):
                pod_info = helper(pod_id)
                if isinstance(pod_info, dict):
                    aosp_version = pod_info.get("aosp_version")
                    image_name = pod_info.get("image_name")
                    image_id = pod_info.get("image_id")
        except Exception:
            pass

        item = ResultItem(
            case=case_name,
            status="skip",
            timestamp=_iso_now(),
            duration_ms=0,
            reason="用例内容为空",
            screenshot=[],
            aosp_version=aosp_version,
            image_name=image_name,
            image_id=image_id,
            pod_id=pod_id,
            run_id=None,
        )
        return item.to_dict()

    params: Dict[str, Any] = {
        "RunName": case.path.stem,
        "PodId": pod_id,
        "ProductId": product_id,
        "UserPrompt": user_prompt,
        "SystemPrompt": system_prompt,
        "TosBucket": client.tos_bucket,
        "TosEndpoint": client.tos_endpoint,
        "TosRegion": client.tos_region,
        "UseBase64Screenshot": cfg.use_base64_screenshot,
        "IsScreenRecord": cfg.screen_record,
        "Timeout": cfg.timeout_s,
    }

    try:
        if cfg.run_api == "task":
            run_id = client.run_agent_task(params)
        else:
            run_id = client.run_agent_task_one_step(params)
    except Exception as e:
        item = ResultItem(
            case=case_name,
            status="fail",
            timestamp=_iso_now(),
            duration_ms=max(0, int(time.time() * 1000) - started_at_ms),
            reason=f"RunAgentTask 调用异常: {type(e).__name__}: {e}",
            screenshot=[],
            pod_id=pod_id,
            run_id=None,
        )
        return item.to_dict()
    except BaseException:
        _shutdown_event.set()
        item = ResultItem(
            case=case_name,
            status="skip",
            timestamp=_iso_now(),
            duration_ms=max(0, int(time.time() * 1000) - started_at_ms),
            reason="本地退出：RunAgentTask 调用被中断",
            screenshot=[],
            pod_id=pod_id,
            run_id=None,
        )
        return item.to_dict()

    if run_id:
        logging.info(f"[pod={pod_id or 'N/A'}] 运行用例: {case_name} run_id={run_id}")
    else:
        logging.info(f"[pod={pod_id or 'N/A'}] 运行用例: {case_name} 未获取到 RunId（RunAgentTask 调用失败）")
        aosp_version = None
        image_name = None
        image_id = None
        try:
            helper = getattr(client, "_get_pod_image_info", None)
            if callable(helper):
                pod_info = helper(pod_id)
                if isinstance(pod_info, dict):
                    aosp_version = pod_info.get("aosp_version")
                    image_name = pod_info.get("image_name")
                    image_id = pod_info.get("image_id")
        except Exception:
            pass

        item = ResultItem(
            case=case_name,
            status="fail",
            timestamp=_iso_now(),
            duration_ms=max(0, int(time.time() * 1000) - started_at_ms),
            reason="未获取到 RunId（RunAgentTask 调用失败）",
            screenshot=[],
            aosp_version=aosp_version,
            image_name=image_name,
            image_id=image_id,
            pod_id=pod_id,
            run_id=None,
        )
        return item.to_dict()

    _register_active_run_id(run_id)

    last_resp: Dict[str, Any] = {}
    last_step_signal: Optional[str] = None
    last_step_hint: Optional[str] = None
    probe_polls = 0

    try:
        deadline = time.monotonic() + max(1, int(cfg.timeout_s))
        poll_interval = max(0.5, float(cfg.poll_interval_s))

        while True:
            if _shutdown_event.is_set():
                cancel_resp = _cancel_task_best_effort(client=client, run_id=run_id, reason="本地中断")

                out = _result_from_resp(
                    client=client,
                    case_name=case_name,
                    run_id=run_id,
                    pod_id=pod_id,
                    started_at_ms=started_at_ms,
                    resp=last_resp,
                    timeout=False,
                )
                out["status"] = "skip"
                out["reason"] = "本地中断，已触发 CancelTask"
                if last_step_signal:
                    out["task_status"] = last_step_signal
                if isinstance(cancel_resp, dict):
                    out["cancel_task"] = cancel_resp.get("Result")
                _attach_cancel_summary(out, cancel_resp)
                return out

            # 轮询 ListAgentRunCurrentStep：finished/request_user 作为“结束信号”
            step_resp = _list_agent_run_current_step_raw(client=client, run_id=run_id)
            done_by_step, signal, hint = _extract_current_step_signal(step_resp)
            if signal:
                last_step_signal = signal
            if hint:
                last_step_hint = hint

            if done_by_step:
                # 结束后：调用 GetAgentResult 获取最终结果
                final_resp = client.get_agent_result_raw(run_id)
                if final_resp:
                    last_resp = final_resp

                # 如果 GetAgentResult 仍是 IsSuccess=0，则继续轮询直到终态或超时
                if _is_done_by_get_result(final_resp):
                    out = _result_from_resp(
                        client=client,
                        case_name=case_name,
                        run_id=run_id,
                        pod_id=pod_id,
                        started_at_ms=started_at_ms,
                        resp=final_resp or last_resp,
                        timeout=False,
                    )
                    if last_step_signal:
                        out["task_status"] = last_step_signal
                    if last_step_hint and not out.get("reason"):
                        out["reason"] = last_step_hint
                    return out

            # 兜底：不依赖 step 信号时，定期探测一次 GetAgentResult 防卡死
            probe_polls += 1
            if probe_polls % 5 == 0:
                probe = client.get_agent_result_raw(run_id)
                if probe:
                    last_resp = probe
                if _is_done_by_get_result(probe):
                    out = _result_from_resp(
                        client=client,
                        case_name=case_name,
                        run_id=run_id,
                        pod_id=pod_id,
                        started_at_ms=started_at_ms,
                        resp=probe,
                        timeout=False,
                    )
                    if last_step_signal:
                        out["task_status"] = last_step_signal
                    if last_step_hint and not out.get("reason"):
                        out["reason"] = last_step_hint
                    return out

            if time.monotonic() >= deadline:
                cancel_resp = _cancel_task_best_effort(client=client, run_id=run_id, reason="单用例超时")

                out = _result_from_resp(
                    client=client,
                    case_name=case_name,
                    run_id=run_id,
                    pod_id=pod_id,
                    started_at_ms=started_at_ms,
                    resp=last_resp,
                    timeout=True,
                )
                if last_step_signal:
                    out["task_status"] = last_step_signal
                if isinstance(cancel_resp, dict):
                    out["cancel_task"] = cancel_resp.get("Result")
                _attach_cancel_summary(out, cancel_resp)
                return out

            time.sleep(poll_interval)

    except Exception as e:
        cancel_resp = _cancel_task_best_effort(client=client, run_id=run_id, reason=f"本地异常: {type(e).__name__}")

        duration_ms = max(0, int(time.time() * 1000) - started_at_ms)
        item = ResultItem(
            case=case_name,
            status="fail",
            timestamp=_iso_now(),
            duration_ms=duration_ms,
            reason=f"本地异常: {type(e).__name__}: {e}",
            screenshot=[],
            pod_id=pod_id,
            run_id=run_id,
        )
        out = item.to_dict()
        if last_step_signal:
            out["task_status"] = last_step_signal
        if isinstance(cancel_resp, dict):
            out["cancel_task"] = cancel_resp.get("Result")
        _attach_cancel_summary(out, cancel_resp)
        return out

    except BaseException as e:
        _shutdown_event.set()
        cancel_resp = _cancel_task_best_effort(client=client, run_id=run_id, reason=f"本地退出: {type(e).__name__}")

        duration_ms = max(0, int(time.time() * 1000) - started_at_ms)
        item = ResultItem(
            case=case_name,
            status="skip",
            timestamp=_iso_now(),
            duration_ms=duration_ms,
            reason=f"本地退出: {type(e).__name__}",
            screenshot=[],
            pod_id=pod_id,
            run_id=run_id,
        )
        out = item.to_dict()
        if last_step_signal:
            out["task_status"] = last_step_signal
        if isinstance(cancel_resp, dict):
            out["cancel_task"] = cancel_resp.get("Result")
        _attach_cancel_summary(out, cancel_resp)
        return out

    finally:
        _unregister_active_run_id(run_id)


def run_suite(
    *,
    root: Path,
    cases_dir: Path,
    system_prompt: str,
    cfg: RunnerConfig,
    on_result: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> List[Dict[str, Any]]:
    _install_exit_handlers_once()
    load_env_from_root(root)

    pod_ids = parse_pod_id_list(os.environ.get("POD_ID_LIST", ""))
    cases = discover_cases(cases_dir)

    if not cases:
        logging.warning("未发现任何用例（*.md / *.case）")
        return []

    mode = (cfg.exec_mode or "auto").strip().lower()
    if mode not in {"auto", "serial", "parallel"}:
        logging.warning(f"EXEC_MODE={cfg.exec_mode} 不合法，回退到 auto")
        mode = "auto"

    if mode == "auto":
        mode = "parallel" if len(pod_ids) > 1 else "serial"

    total_cases = len(cases)
    progress_every_env = (os.environ.get("PROGRESS_LOG_EVERY") or "1").strip()
    try:
        progress_every = max(1, int(float(progress_every_env)))
    except Exception:
        progress_every = 1

    progress_lock = Lock()
    progress_done = 0
    progress_pass = 0
    progress_fail = 0
    progress_skip = 0

    def _emit_result(res: Dict[str, Any]) -> None:
        nonlocal progress_done, progress_pass, progress_fail, progress_skip

        if on_result is not None:
            try:
                on_result(res)
            except Exception as e:
                logging.warning(f"增量落盘回调失败: {type(e).__name__}: {e}")

        with progress_lock:
            progress_done += 1
            st = res.get("status")
            if st == "pass":
                progress_pass += 1
            elif st == "fail":
                progress_fail += 1
            elif st == "skip":
                progress_skip += 1

            if progress_done % progress_every == 0 or progress_done >= total_cases:
                pct = (progress_done / total_cases * 100.0) if total_cases > 0 else 100.0
                case_name = str(res.get("case") or "")
                logging.info(
                    f"PROGRESS {progress_done}/{total_cases} ({pct:.0f}%) "
                    f"pass={progress_pass} fail={progress_fail} skip={progress_skip} "
                    f"last={case_name} status={st}"
                )

    def _run_case_safe(*, client: MobileUseClient, pod: str, c: CaseFile) -> Dict[str, Any]:
        try:
            return run_one_case(
                client=client,
                case=c,
                root=root,
                system_prompt=system_prompt,
                pod_id=pod,
                product_id=client.product_id,
                cfg=cfg,
            )
        except Exception as e:
            aosp_version = None
            image_name = None
            image_id = None
            try:
                helper = getattr(client, "_get_pod_image_info", None)
                effective_pod_id = pod or getattr(client, "pod_id", None)
                if callable(helper):
                    pod_info = helper(effective_pod_id)
                    if isinstance(pod_info, dict):
                        aosp_version = pod_info.get("aosp_version")
                        image_name = pod_info.get("image_name")
                        image_id = pod_info.get("image_id")
            except Exception:
                pass

            item = ResultItem(
                case=str(c.path.relative_to(root)),
                status="fail",
                timestamp=_iso_now(),
                duration_ms=0,
                reason=f"执行异常: {type(e).__name__}: {e}",
                screenshot=[],
                aosp_version=aosp_version,
                image_name=image_name,
                image_id=image_id,
                pod_id=pod or None,
                run_id=None,
            )
            return item.to_dict()

    if mode == "serial":
        pod_id = pod_ids[0] if pod_ids else None
        logging.info(f"EXEC_MODE=serial，串行执行；pod={pod_id or 'N/A'}")
        client = MobileUseClient(pod_id=pod_id)

        results: List[Tuple[int, Dict[str, Any]]] = []
        try:
            for c in cases:
                if _shutdown_event.is_set():
                    break
                r = _run_case_safe(client=client, pod=client.pod_id, c=c)
                results.append((c.index, r))
                _emit_result(r)
        except KeyboardInterrupt:
            _shutdown_event.set()
            _cancel_all_active_runs("本地中断（KeyboardInterrupt）")

        if _shutdown_event.is_set():
            done = {idx for idx, _ in results}
            for c in cases:
                if c.index in done:
                    continue
                item = ResultItem(
                    case=str(c.path.relative_to(root)),
                    status="skip",
                    timestamp=_iso_now(),
                    duration_ms=0,
                    reason="本地中断，未执行",
                    screenshot=[],
                    pod_id=None,
                    run_id=None,
                )
                r2 = item.to_dict()
                results.append((c.index, r2))
                _emit_result(r2)

        results.sort(key=lambda x: x[0])
        return [r for _, r in results]

    if len(pod_ids) <= 1:
        logging.warning("EXEC_MODE=parallel 但 POD_ID_LIST<=1，回退到串行")
        pod_id = pod_ids[0] if pod_ids else None
        client = MobileUseClient(pod_id=pod_id)

        results: List[Tuple[int, Dict[str, Any]]] = []
        try:
            for c in cases:
                if _shutdown_event.is_set():
                    break
                r = _run_case_safe(client=client, pod=client.pod_id, c=c)
                results.append((c.index, r))
                _emit_result(r)
        except KeyboardInterrupt:
            _shutdown_event.set()
            _cancel_all_active_runs("本地中断（KeyboardInterrupt）")

        if _shutdown_event.is_set():
            done = {idx for idx, _ in results}
            for c in cases:
                if c.index in done:
                    continue
                item = ResultItem(
                    case=str(c.path.relative_to(root)),
                    status="skip",
                    timestamp=_iso_now(),
                    duration_ms=0,
                    reason="本地中断，未执行",
                    screenshot=[],
                    pod_id=None,
                    run_id=None,
                )
                r2 = item.to_dict()
                results.append((c.index, r2))
                _emit_result(r2)

        results.sort(key=lambda x: x[0])
        return [r for _, r in results]

    logging.info(f"EXEC_MODE=parallel，POD_ID_LIST={len(pod_ids)}，并发执行；pods={pod_ids}")

    q: Queue[Optional[CaseFile]] = Queue()
    for c in cases:
        q.put(c)
    for _ in pod_ids:
        q.put(None)

    lock = Lock()
    results2: List[Tuple[int, Dict[str, Any]]] = []

    def worker(pod: str) -> None:
        client = MobileUseClient(pod_id=pod)
        while True:
            if _shutdown_event.is_set():
                return
            try:
                c = q.get(timeout=0.5)
            except Empty:
                continue
            if c is None:
                return

            r = _run_case_safe(client=client, pod=client.pod_id, c=c)
            with lock:
                results2.append((c.index, r))
            _emit_result(r)

    threads = [Thread(target=worker, name=f"pod-worker-{pid}", args=(pid,), daemon=True) for pid in pod_ids]
    for t in threads:
        t.start()

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        _shutdown_event.set()
        _cancel_all_active_runs("本地中断（KeyboardInterrupt）")
        for t in threads:
            t.join(timeout=1.0)

    results2.sort(key=lambda x: x[0])

    if _shutdown_event.is_set():
        done = {idx for idx, _ in results2}
        for c in cases:
            if c.index in done:
                continue
            item = ResultItem(
                case=str(c.path.relative_to(root)),
                status="skip",
                timestamp=_iso_now(),
                duration_ms=0,
                reason="本地中断，未执行",
                screenshot=[],
                pod_id=None,
                run_id=None,
            )
            r2 = item.to_dict()
            results2.append((c.index, r2))
            _emit_result(r2)

        results2.sort(key=lambda x: x[0])

    return [r for _, r in results2]
