#!/usr/bin/env python3
"""
Mobile Use Agent - 快速运行脚本

凭证策略:
  - AK/SK: 首次运行时配置并保存到本地, 后续自动加载
  - ProductId / PodId / 用户提示词: 每次运行时输入
"""

import sys
import os
import json

# 同目录导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mobile_use_agent import MobileUseAgentClient, format_result
from error_codes import MobileUseError, format_error, CATEGORY_AUTH
from credential_store import get_credentials_interactive
from geo import ask_location_permission, acquire_gps


def main():
    print("=" * 60)
    print("  Mobile Use Agent - 快速运行")
    print("=" * 60)

    try:
        _main()
    except KeyboardInterrupt:
        print("\n[中断] 操作已取消")
    except MobileUseError as e:
        print("\n[API 错误]")
        print(format_error(e))
        if e.category == CATEGORY_AUTH:
            print()
            print("[引导] 凭证无效或已过期, 请重新配置: python cli.py setup")
    except Exception as e:
        print(f"\n[错误] {type(e).__name__}: {str(e)[:500]}")


def _main():
    # 1. 凭证: 首次配置并保存, 之后自动加载
    ak, sk = get_credentials_interactive()
    client = MobileUseAgentClient(ak=ak, sk=sk)

    # 2. 每次运行都要输入的参数
    print("\n--- 云手机实例配置 ---")
    product_id = input("请输入 ProductId (云手机业务 ID): ").strip()
    pod_id = input("请输入 PodId (云手机实例 ID): ").strip()

    if not product_id or not pod_id:
        print("[错误] ProductId/PodId 不能为空!")
        sys.exit(1)

    user_prompt = input("\n请输入用户提示词 (你想让 Agent 做什么): ").strip()
    if not user_prompt:
        print("[错误] 提示词不能为空!")
        sys.exit(1)

    # 3. 可选参数
    run_name = input("\n运行名称 (回车自动生成): ").strip()
    max_step_input = input("最大步数 [100]: ").strip()
    timeout_input = input("超时时间(秒) [300]: ").strip()

    max_step = int(max_step_input) if max_step_input else 100
    timeout = int(timeout_input) if timeout_input else 300

    # 4. GPS 定位注入 (每次询问是否允许, 多来源自动降级, 并告知获取结果)
    print("\n--- GPS 定位注入 ---")
    gps_info = None
    if ask_location_permission(user_prompt):
        # 已授权: 系统定位 → IP 定位 → 文本坐标/地理编码 → 手动输入
        gps_info = acquire_gps(prompt=user_prompt)
    else:
        # 拒绝自动获取: 仅走无隐私来源 (提示词中的坐标/地名) + 手动输入兜底
        gps_info = acquire_gps(prompt=user_prompt, allow_permission=False, allow_ip=False)
        if gps_info is None:
            print("[跳过] 未提供位置, 本次任务不注入 GpsInfo")

    # 5. 运行任务并等待结果
    result = client.run_and_wait(
        run_name=run_name or None,
        pod_id=pod_id,
        product_id=product_id,
        user_prompt=user_prompt,
        max_step=max_step,
        timeout=timeout,
        gps_info=gps_info,
    )

    print("\n" + "=" * 60)
    print("  最终结果")
    print("=" * 60)
    print(format_result(result))


if __name__ == "__main__":
    main()
