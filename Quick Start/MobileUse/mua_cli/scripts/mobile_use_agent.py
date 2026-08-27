"""
Mobile Use Agent - 火山引擎云手机 Agent OpenAPI 封装客户端

支持以下操作:
  1. CreateAgentRunConfig  - 创建代理运行配置
  2. UpdateAgentRunConfig  - 更新代理运行配置
  3. DeleteAgentRunConfig  - 删除代理运行配置
  4. ListAgentRunConfig    - 查询代理运行配置列表
  5. RunAgentTask          - 运行代理任务 (需先创建配置)
  6. RunAgentTaskOneStep   - 一键运行代理任务 (无需创建配置)
  7. CancelTask            - 取消代理任务
  8. ListAgentRunCurrentStep - 查询任务当前步骤
  9. ListAgentRunTask      - 查询代理任务列表
 10. GetAgentResult        - 获取任务运行结果

认证: 火山引擎 AK/SK
服务: ipaas
版本: 2023-08-01
端点: open.volcengineapi.com
区域: cn-north-1
"""

import uuid
import time
import json
import logging
from typing import Optional, Dict, Any, List

try:
    import volcenginesdkcore
    from volcenginesdkcore.rest import ApiException
except ImportError:
    raise ImportError(
        "volcenginesdkcore is required. Install it with: pip install volcenginesdkcore"
    )

# 同目录导入错误码模块
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from error_codes import (
    MobileUseError,
    parse_api_error,
    scan_error_in_response,
    CATEGORY_AUTH,
    CATEGORY_TASK,
)

logger = logging.getLogger(__name__)

# 常量
SERVICE = "ipaas"
VERSION = "2023-08-01"
REGION = "cn-north-1"


# ========================
# 响应解析工具函数
# ========================

def extract_results(step_resp: Any) -> List[Dict[str, Any]]:
    """从 ListAgentRunCurrentStep 响应中提取步骤列表

    官方返回结构 (Result 嵌套兼容两种形式):
        {"Results": [{"Action": ..., "Param": ..., "StepResult": ..., "Timestamp": ...}]}
        {"Result": {"RunId": ..., "Results": [...]}}
    """
    if not isinstance(step_resp, dict):
        return []
    results = step_resp.get("Results")
    if results is None:
        inner = step_resp.get("Result")
        if isinstance(inner, dict):
            results = inner.get("Results")
    if not isinstance(results, list):
        return []
    return [r for r in results if isinstance(r, dict)]


def format_step(step: Dict[str, Any], index: int = 0) -> str:
    """格式化单步执行记录为可读文本

    Step 结构:
        Action     (str)  当前执行动作, 如 "finished"
        Param      (dict) 执行参数, 如 {"content": "打开小红书"}
        StepResult (dict) {IsSuccess: bool, Result: str} 步骤阶段性结果
        Timestamp  (str)  步骤完成时间, 如 "2025-10-30T13:17:12+08:00"
    """
    action = step.get("Action", "") or ""
    param = step.get("Param")
    content = ""
    if isinstance(param, dict):
        content = param.get("content", "") or ""
    step_result = step.get("StepResult")
    is_success, result_text = None, ""
    if isinstance(step_result, dict):
        is_success = step_result.get("IsSuccess")
        result_text = step_result.get("Result", "") or ""
    ts = step.get("Timestamp", "") or ""
    try:
        ts_short = ts[11:19] if len(ts) >= 19 else ts
    except Exception:
        ts_short = ts

    if is_success is True or is_success == 1:
        mark = "OK"
    elif is_success is False or is_success == 0:
        mark = "FAIL"
    else:
        mark = "..."

    lines = [f"  -- Step {index} [{mark}] {ts_short} --"]
    if action:
        lines.append(f"     [action] {action}")
    if content:
        lines.append(f"     [content] {content}")
    if result_text:
        lines.append(f"     [result] {result_text}")
    return "\n".join(lines)


def format_steps(step_resp: Any) -> str:
    """格式化 ListAgentRunCurrentStep 响应的全部步骤"""
    results = extract_results(step_resp)
    if not results:
        return "  (暂无步骤记录)"
    parts = [format_step(s, i + 1) for i, s in enumerate(results)]
    return "\n".join(parts)


def format_result(result_resp: Any) -> str:
    """格式化 GetAgentResult 响应为可读文本

    Result 结构:
        IsSuccess    (int)    1 表示任务成功结束
        Content      (str)    任务运行结果的内容
        StructOutput (str)   结构化输出 (配置 OutputSchema 时)
        ScreenShots  (dict)  截屏 TOS URL 集合 (IsDetail=true 时)
        Usage        (dict)  任务用量信息
    """
    if not isinstance(result_resp, dict):
        return f"  (无结果: {result_resp})"
    inner = result_resp.get("Result")
    src = result_resp
    if isinstance(inner, dict):
        src = inner

    is_success = src.get("IsSuccess")
    content = src.get("Content", "") or ""
    struct_output = src.get("StructOutput") or ""
    screenshots = src.get("ScreenShots")
    usage = src.get("Usage")

    lines = []
    if is_success is not None:
        ok = is_success == 1 or is_success is True
        lines.append(f"  状态: {'成功' if ok else '失败/未成功'} (IsSuccess={is_success})")
        # 任务失败时, 扫描响应中的业务错误码, 给出失败原因与操作建议
        if not ok:
            err = scan_error_in_response(result_resp)
            if err:
                lines.append(f"  失败原因: {err.desc}")
                lines.append(f"  操作建议: {err.advice}")
                if err.code_n is not None:
                    lines.append(f"  错误码:   {err.code_n} {err.code or ''}".rstrip())
    if content:
        lines.append(f"  内容: {content}")
    if struct_output:
        lines.append(f"  结构化输出: {struct_output}")
    if screenshots:
        if isinstance(screenshots, dict):
            for k, v in screenshots.items():
                lines.append(f"  截图[{k}]: {v}")
        else:
            lines.append(f"  截图: {screenshots}")
    if usage:
        lines.append(f"  用量: {usage}")
    if not lines:
        lines.append(f"  (响应无业务字段: {result_resp})")
    return "\n".join(lines)


class MobileUseAgentClient:
    """火山引擎 Mobile Use Agent OpenAPI 客户端

    在实例化时传入 AK/SK，每次发起任务时传入 ProductId/PodId。
    """

    def __init__(self, ak: str, sk: str, region: str = REGION):
        """初始化客户端

        Args:
            ak: 火山引擎 Access Key ID
            sk: 火山引擎 Secret Access Key
            region: 区域，默认 cn-north-1
        """
        if not ak or not sk:
            raise ValueError("AK and SK are required")

        self.ak = ak
        self.sk = sk
        self.region = region

        # 配置 SDK
        self.configuration = volcenginesdkcore.Configuration()
        self.configuration.ak = ak
        self.configuration.sk = sk
        self.configuration.region = region

        # 创建 API 客户端
        self.api_instance = volcenginesdkcore.UniversalApi(
            volcenginesdkcore.ApiClient(self.configuration)
        )
        logger.info(f"MobileUseAgentClient initialized (region={region})")

    def _do_call(
        self,
        method: str,
        action: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """统一调用 API

        Args:
            method: HTTP 方法 (GET/POST)
            action: 接口名称
            body: 请求参数

        Returns:
            API 响应 (dict)
        """
        if body is None:
            body = {}

        flat_body = volcenginesdkcore.Flatten(body).flat()

        info = volcenginesdkcore.UniversalInfo(
            method=method,
            action=action,
            service=SERVICE,
            version=VERSION,
            content_type="application/json",
        )

        try:
            resp = self.api_instance.do_call(info, flat_body)
            logger.debug(f"{action} response: {resp}")
            # HTTP 200 但业务层错误: SDK 不抛异常, 错误码藏在响应体
            # ResponseMetadata.Error 中 (如 400205/400206 Pod 不存在), 需自行检查
            err = parse_api_error(resp)
            if err:
                logger.error(f"{action} business error: {err}")
                raise err
            return resp
        except MobileUseError:
            raise
        except ApiException as e:
            logger.error(f"API Exception in {action}: {e}")
            err = parse_api_error(e)
            if err:
                raise err
            raise
        except Exception as e:
            logger.error(f"Exception in {action}: {e}")
            raise

    # ========================
    # 代理运行配置管理
    # ========================

    def create_agent_run_config(
        self,
        max_step: int = 55,
        timeout: int = 300,
        tos_bucket: str = "",
        tos_endpoint: str = "",
        tos_region: str = "",
        callback_url: str = "",
    ) -> str:
        """创建代理运行配置

        Args:
            max_step: 最大运行步数, 默认 55
            timeout: 超时时间 (秒), 默认 300
            tos_bucket: TOS 存储桶名称
            tos_endpoint: TOS 端点地址
            tos_region: TOS 区域
            callback_url: 状态回调 URL

        Returns:
            config_id: 代理运行配置的唯一标识
        """
        body = {
            "MaxStep": max_step,
            "Timeout": timeout,
        }
        if tos_bucket:
            body["TosBucket"] = tos_bucket
        if tos_endpoint:
            body["TosEndpoint"] = tos_endpoint
        if tos_region:
            body["TosRegion"] = tos_region
        if callback_url:
            body["CallbackUrl"] = callback_url

        resp = self._do_call("POST", "CreateAgentRunConfig", body)
        config_id = resp.get("ConfigId", "")
        logger.info(f"Created AgentRunConfig: {config_id}")
        return config_id

    def update_agent_run_config(
        self,
        config_id: str,
        max_step: Optional[int] = None,
        timeout: Optional[int] = None,
        tos_bucket: Optional[str] = None,
        tos_endpoint: Optional[str] = None,
        tos_region: Optional[str] = None,
        callback_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """更新代理运行配置

        Args:
            config_id: 配置 ID
            其他参数同 create_agent_run_config (None 表示不更新)

        Returns:
            API 响应
        """
        body = {"ConfigId": config_id}
        if max_step is not None:
            body["MaxStep"] = max_step
        if timeout is not None:
            body["Timeout"] = timeout
        if tos_bucket is not None:
            body["TosBucket"] = tos_bucket
        if tos_endpoint is not None:
            body["TosEndpoint"] = tos_endpoint
        if tos_region is not None:
            body["TosRegion"] = tos_region
        if callback_url is not None:
            body["CallbackUrl"] = callback_url

        return self._do_call("POST", "UpdateAgentRunConfig", body)

    def delete_agent_run_config(self, config_id: str) -> Dict[str, Any]:
        """删除代理运行配置

        Args:
            config_id: 配置 ID

        Returns:
            API 响应
        """
        body = {"ConfigId": config_id}
        return self._do_call("POST", "DeleteAgentRunConfig", body)

    def list_agent_run_config(
        self,
        page_size: int = 10,
        page_number: int = 1,
    ) -> Dict[str, Any]:
        """查询代理运行配置列表

        Args:
            page_size: 每页数量
            page_number: 页码

        Returns:
            API 响应
        """
        body = {
            "PageSize": page_size,
            "PageNumber": page_number,
        }
        return self._do_call("GET", "ListAgentRunConfig", body)

    # ========================
    # 任务管理
    # ========================

    def run_agent_task(
        self,
        run_name: str,
        pod_id: str,
        product_id: str,
        user_prompt: str,
        agent_run_config_id: str,
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """运行代理任务 (需先创建代理运行配置)

        Args:
            run_name: 运行名称
            pod_id: 云手机实例 ID (Pod ID)
            product_id: 云手机业务 ID (Product ID)
            user_prompt: 用户提示词
            agent_run_config_id: 代理运行配置 ID
            thread_id: 线程 ID (可选, 不传则自动生成)

        Returns:
            API 响应, 包含 RunId 等信息
        """
        body = {
            "RunName": run_name,
            "PodId": pod_id,
            "ProductId": product_id,
            "UserPrompt": user_prompt,
            "AgentRunConfigId": agent_run_config_id,
        }
        if thread_id is None:
            thread_id = str(uuid.uuid4())
        body["ThreadId"] = thread_id

        resp = self._do_call("POST", "RunAgentTask", body)
        run_id = resp.get("RunId", "")
        logger.info(f"Started AgentTask: run_id={run_id}, thread_id={thread_id}")
        return resp

    def run_agent_task_one_step(
        self,
        run_name: str,
        pod_id: str,
        product_id: str,
        user_prompt: str,
        thread_id: Optional[str] = None,
        use_base64_screenshot: bool = False,
        max_step: int = 100,
        timeout: int = 120,
        callback_info: Optional[Dict[str, Any]] = None,
        output_schema: Optional[str] = None,
        retry_limit: int = 3,
        system_prompt: Optional[str] = None,
        tos_bucket: Optional[str] = None,
        tos_endpoint: Optional[str] = None,
        tos_region: Optional[str] = None,
        is_screen_record: bool = False,
        mcp_json: Optional[str] = None,
        max_output_tokens: int = 0,
        gps_info: Optional[str] = None,
    ) -> Dict[str, Any]:
        """一键运行代理任务 (无需先创建代理运行配置)

        Args:
            run_name: 运行名称 (1~127 字节)
            pod_id: 云手机实例 ID (Pod ID, 1~63 字节)
            product_id: 云手机业务 ID (Product ID, 1~63 字节)
            user_prompt: 用户提示词 (最多 10000 字节)
            thread_id: 线程 ID (可选)
            use_base64_screenshot: 是否使用 Base64 编码传输截屏
            max_step: 最大操作步骤数, 默认 100 (1~500, 或 -1 不限制)
            timeout: 超时时间 (秒), 默认 120 (1~86400, 或 -1 不限制)
            callback_info: 回调配置
            output_schema: 输出格式 (JSON 字符串)
            retry_limit: 失败重试次数, 默认 3 (0~10)
            system_prompt: 系统提示词 (最多 20000 字符)
            tos_bucket: TOS 存储桶名称
            tos_endpoint: TOS 端点地址
            tos_region: TOS 区域
            is_screen_record: 是否开启录屏
            mcp_json: 第三方 MCP 工具配置 (JSON 字符串)
            max_output_tokens: 单次最大输出 Token 数 (0=不限制, 最大 65526)
            gps_info: GPS 注入信息 ("经度,纬度,海拔,速度,方位角,定位精度")

        Returns:
            API 响应, 包含 RunId, RunName, ThreadId 等
        """
        body = {
            "RunName": run_name,
            "PodId": pod_id,
            "ProductId": product_id,
            "UserPrompt": user_prompt,
        }

        if thread_id is None:
            thread_id = str(uuid.uuid4())
        body["ThreadId"] = thread_id

        body["UseBase64Screenshot"] = use_base64_screenshot
        body["MaxStep"] = max_step
        body["Timeout"] = timeout
        body["RetryLimit"] = retry_limit
        body["MaxOutputTokens"] = max_output_tokens
        body["IsScreenRecord"] = is_screen_record

        if callback_info is not None:
            body["CallbackInfo"] = callback_info
        if output_schema is not None:
            body["OutputSchema"] = output_schema
        if system_prompt is not None:
            body["SystemPrompt"] = system_prompt
        if tos_bucket is not None:
            body["TosBucket"] = tos_bucket
        if tos_endpoint is not None:
            body["TosEndpoint"] = tos_endpoint
        if tos_region is not None:
            body["TosRegion"] = tos_region
        if mcp_json is not None:
            body["McpJson"] = mcp_json
        if gps_info is not None:
            body["GpsInfo"] = gps_info

        resp = self._do_call("POST", "RunAgentTaskOneStep", body)
        run_id = resp.get("RunId", "")
        logger.info(
            f"Started AgentTaskOneStep: run_id={run_id}, thread_id={thread_id}"
        )
        return resp

    def cancel_task(self, run_id: str) -> Dict[str, Any]:
        """取消代理任务

        Args:
            run_id: 运行 ID

        Returns:
            API 响应
        """
        body = {"RunId": run_id}
        return self._do_call("POST", "CancelTask", body)

    def list_agent_run_current_step(self, run_id: str) -> Dict[str, Any]:
        """查询任务当前步骤

        Args:
            run_id: 运行 ID

        Returns:
            API 响应, 包含当前执行步骤信息
        """
        body = {"RunId": run_id}
        return self._do_call("GET", "ListAgentRunCurrentStep", body)

    def list_agent_run_task(
        self,
        run_id: Optional[str] = None,
        run_name: Optional[str] = None,
        page_size: int = 10,
        page_number: int = 1,
    ) -> Dict[str, Any]:
        """查询代理任务列表

        Args:
            run_id: 运行 ID (可选筛选)
            run_name: 运行名称 (可选筛选)
            page_size: 每页数量
            page_number: 页码

        Returns:
            API 响应
        """
        body = {
            "PageSize": page_size,
            "PageNumber": page_number,
        }
        if run_id:
            body["RunId"] = run_id
        if run_name:
            body["RunName"] = run_name
        return self._do_call("GET", "ListAgentRunTask", body)

    def get_agent_result(self, run_id: str) -> Dict[str, Any]:
        """获取任务运行结果

        Args:
            run_id: 运行 ID

        Returns:
            API 响应, 包含最终执行结果
        """
        body = {"RunId": run_id}
        return self._do_call("GET", "GetAgentResult", body)

    # ========================
    # 高级功能
    # ========================

    def run_and_wait(
        self,
        run_name: str,
        pod_id: str,
        product_id: str,
        user_prompt: str,
        max_step: int = 100,
        timeout: int = 300,
        poll_interval: int = 5,
        system_prompt: Optional[str] = None,
        use_base64_screenshot: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """运行任务并轮询等待完成

        一键运行代理任务, 然后轮询当前步骤直到任务完成或超时。

        Args:
            run_name: 运行名称
            pod_id: Pod ID
            product_id: Product ID
            user_prompt: 用户提示词
            max_step: 最大步数
            timeout: 任务超时时间 (秒)
            poll_interval: 轮询间隔 (秒)
            system_prompt: 系统提示词
            use_base64_screenshot: 是否使用 Base64 截图
            **kwargs: 其他 run_agent_task_one_step 参数

        Returns:
            任务结果 (GetAgentResult 的响应)
        """
        # 1. 启动任务
        print(f"\n{'='*60}")
        print(f"  [启动任务] {run_name}")
        print(f"  ProductId: {product_id}")
        print(f"  PodId:     {pod_id}")
        print(f"  Prompt:   {user_prompt[:80]}{'...' if len(user_prompt)>80 else ''}")
        print(f"  MaxStep:  {max_step}  Timeout: {timeout}s")
        print(f"  GpsInfo:  {kwargs.get('gps_info') or '(未注入)'}")
        print(f"{'='*60}\n")

        resp = self.run_agent_task_one_step(
            run_name=run_name,
            pod_id=pod_id,
            product_id=product_id,
            user_prompt=user_prompt,
            max_step=max_step,
            timeout=timeout,
            system_prompt=system_prompt,
            use_base64_screenshot=use_base64_screenshot,
            **kwargs,
        )

        run_id = resp.get("RunId", "")
        if not run_id:
            raise RuntimeError(f"No RunId in response: {resp}")

        print(f"  [RunId] {run_id}")
        print(f"  [ThreadId] {resp.get('ThreadId', '')}")
        if resp.get("Tips"):
            print(f"  [Tips] {resp['Tips']}")
        print()

        # 2. 轮询当前步骤 (增量打印, 每步只输出一次)
        start_time = time.time()
        max_wait = max(timeout + 60, 3600)  # 最多等待 timeout+60s
        seen_count = 0  # 已打印的步骤数

        while True:
            elapsed = int(time.time() - start_time)
            if elapsed > max_wait:
                print(f"\n  [超时] 已等待 {elapsed}s, 超过最大等待时间")
                break

            time.sleep(poll_interval)
            try:
                step_resp = self.list_agent_run_current_step(run_id)
                results = extract_results(step_resp)
                # 增量打印: 只打印新出现的步骤
                if len(results) > seen_count:
                    for i in range(seen_count, len(results)):
                        print(format_step(results[i], i + 1))
                    seen_count = len(results)
                else:
                    print(f"  [{elapsed}s] 执行中... (已产生 {seen_count} 条步骤记录)")
            except MobileUseError as e:
                # 认证/授权错误: 凭证问题会一直失败, 直接终止
                if e.category == CATEGORY_AUTH:
                    raise
                print(f"  [{elapsed}s] 轮询异常: {e.desc} → {e.advice}")
            except Exception as e:
                print(f"  [{elapsed}s] 轮询异常: {e}")

            # 检查任务是否完成 (GetAgentResult.IsSuccess)
            try:
                result = self.get_agent_result(run_id)
                if isinstance(result, dict):
                    inner = result.get("Result")
                    src = inner if isinstance(inner, dict) else result
                    is_success = src.get("IsSuccess")
                    if is_success is not None:
                        ok = is_success == 1 or is_success is True
                        if ok:
                            print(f"\n  [任务结束] 状态: 成功")
                        else:
                            print(f"\n  [任务结束] 状态: 失败/未成功 (IsSuccess={is_success})")
                            # 扫描失败原因 (业务错误码)
                            err = scan_error_in_response(result)
                            if err:
                                print(f"  [失败原因] {err.desc}")
                                print(f"  [操作建议] {err.advice}")
                                if err.code_n is not None:
                                    print(
                                        f"  [错误码]   {err.code_n} {err.code or ''}".rstrip()
                                    )
                        return result
            except MobileUseError as e:
                # 任务未完成时 GetAgentResult 可能返回 "任务仍在执行" 等,
                # 可重试/任务状态类错误继续轮询, 认证错误终止
                if e.category == CATEGORY_AUTH:
                    raise
                if not e.retryable and e.category != CATEGORY_TASK:
                    print(f"  [{elapsed}s] 查询结果出错: {e.desc} → {e.advice}")
            except Exception:
                pass  # 任务未完成时 GetAgentResult 可能报错, 继续轮询

        # 3. 获取最终结果
        print("\n  [获取最终结果...]")
        try:
            result = self.get_agent_result(run_id)
            return result
        except Exception as e:
            print(f"  [获取结果失败] {e}")
            return {"RunId": run_id, "error": str(e)}
