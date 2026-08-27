#!/usr/bin/env python3
"""
Mobile Use Agent - 编程式调用示例

演示如何在 Python 代码中直接调用 Mobile Use Agent API。
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mobile_use_agent import MobileUseAgentClient, format_steps, format_result
from geo import acquire_gps


def example_gps_injection():
    """示例: 获取本地位置并注入 GpsInfo

    geo.acquire_gps(prompt=...) 按降级链自动尝试多个来源:
      1. 提示词中直接含坐标 (如 "39.916527,116.397128") → 直接解析
      2. 提示词指向含 GPS 元数据的图片 → 解析 EXIF
      3. macOS CoreLocation 系统定位 (米级精度, 需权限)
      4. IP 定位 (城市级精度)
      5. 提示词含地名/地址 → 地理编码为坐标
      6. 全部失败 → 交互式询问手动输入坐标或地址
    生产环境中是否获取位置, 应先征求用户同意 (见 cli.py 的 ask_location_permission)。
    """
    print(">>> 示例: 获取本地位置并注入 GpsInfo")

    client = MobileUseAgentClient(
        ak="YOUR_AK",
        sk="YOUR_SK",
    )

    # 获取当前位置; 传入用户提示词可启用文本坐标/图片EXIF/地名地理编码
    gps_info = acquire_gps(prompt="帮我看看附近有什么好吃的")
    if not gps_info:
        print("未获取到位置, 任务将不注入 GpsInfo")
        return

    resp = client.run_agent_task_one_step(
        run_name="demo-gps-task",
        pod_id="YOUR_POD_ID",
        product_id="YOUR_PRODUCT_ID",
        user_prompt="打开地图应用, 搜索附近的美食",
        gps_info=gps_info,  # 例如 "121.458100,31.222200,0,0.0,0,10000"
        max_step=50,
        timeout=300,
    )
    print(f"启动结果: {json.dumps(resp, indent=2, ensure_ascii=False)}")


def example_one_step_run():
    """示例 1: 一键运行代理任务"""
    print(">>> 示例 1: 一键运行代理任务")

    # AK/SK/ProductId/PodId 在每次发起任务时传入
    client = MobileUseAgentClient(
        ak="YOUR_AK",
        sk="YOUR_SK",
    )

    # 启动任务
    resp = client.run_agent_task_one_step(
        run_name="demo-task",
        pod_id="YOUR_POD_ID",
        product_id="YOUR_PRODUCT_ID",
        user_prompt="打开设置应用, 查看系统版本信息",
        max_step=50,
        timeout=300,
    )
    print(f"启动结果: {json.dumps(resp, indent=2, ensure_ascii=False)}")

    run_id = resp.get("RunId")
    if not run_id:
        return

    # 轮询当前步骤
    import time
    for i in range(60):
        time.sleep(5)
        step = client.list_agent_run_current_step(run_id)
        print(f"\n[{i*5}s] 当前步骤:")
        print(format_steps(step))

    # 获取最终结果
    result = client.get_agent_result(run_id)
    print(f"\n最终结果:")
    print(format_result(result))


def example_config_workflow():
    """示例 2: 创建配置 -> 运行任务 -> 查询 -> 删除配置"""
    print(">>> 示例 2: 完整配置工作流")

    client = MobileUseAgentClient(ak="YOUR_AK", sk="YOUR_SK")

    # 1. 创建代理运行配置
    config_id = client.create_agent_run_config(
        max_step=55,
        timeout=300,
    )
    print(f"ConfigId: {config_id}")

    # 2. 运行任务
    resp = client.run_agent_task(
        run_name="config-based-task",
        pod_id="YOUR_POD_ID",
        product_id="YOUR_PRODUCT_ID",
        user_prompt="截图当前屏幕",
        agent_run_config_id=config_id,
    )
    run_id = resp.get("RunId")
    print(f"RunId: {run_id}")

    # 3. 查询任务列表
    tasks = client.list_agent_run_task()
    print(f"任务列表: {json.dumps(tasks, indent=2, ensure_ascii=False)}")

    # 4. 取消任务
    cancel_resp = client.cancel_task(run_id)
    print(f"取消结果: {cancel_resp}")

    # 5. 删除配置
    del_resp = client.delete_agent_run_config(config_id)
    print(f"删除配置: {del_resp}")


def example_with_tos_and_recording():
    """示例 3: 带 TOS 存储和录屏的任务"""
    print(">>> 示例 3: 带 TOS 和录屏")

    client = MobileUseAgentClient(ak="YOUR_AK", sk="YOUR_SK")

    resp = client.run_agent_task_one_step(
        run_name="tos-recording-task",
        pod_id="YOUR_POD_ID",
        product_id="YOUR_PRODUCT_ID",
        user_prompt="打开相册应用",
        max_step=100,
        timeout=600,
        tos_bucket="your-bucket",
        tos_endpoint="tos-cn-beijing.volces.com",
        tos_region="cn-beijing",
        is_screen_record=True,
        use_base64_screenshot=True,
        system_prompt="你是一个专注于操作手机应用的助手",
    )
    print(f"启动结果: {json.dumps(resp, indent=2, ensure_ascii=False)}")


def example_with_mcp():
    """示例 4: 带第三方 MCP 工具"""
    print(">>> 示例 4: 带 MCP 工具")

    client = MobileUseAgentClient(ak="YOUR_AK", sk="YOUR_SK")

    mcp_config = json.dumps({
        "mcpServers": {
            "amap-maps": {
                "url": "https://mcp.amap.com/mcp?key=xxx",
                "transport": "streamable_http"
            }
        }
    })

    resp = client.run_agent_task_one_step(
        run_name="mcp-task",
        pod_id="YOUR_POD_ID",
        product_id="YOUR_PRODUCT_ID",
        user_prompt="打开地图, 导航到北京天安门",
        max_step=200,
        timeout=600,
        mcp_json=mcp_config,
        gps_info="116.397128,39.916527,50,0,0,10",
    )
    print(f"启动结果: {json.dumps(resp, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    examples = {
        "1": example_one_step_run,
        "2": example_config_workflow,
        "3": example_with_tos_and_recording,
        "4": example_with_mcp,
        "5": example_gps_injection,
    }

    print("\nMobile Use Agent - 编程式调用示例\n")
    print("  1. 一键运行代理任务")
    print("  2. 完整配置工作流")
    print("  3. 带 TOS 存储和录屏")
    print("  4. 带第三方 MCP 工具")
    print("  5. 获取本地位置并注入 GpsInfo")
    print()

    choice = input("选择示例 (1-5): ").strip()
    if choice in examples:
        examples[choice]()
    else:
        print("无效选择")
