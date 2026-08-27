#!/usr/bin/env python3
"""
Mobile Use Agent - 交互式 CLI

凭证策略:
  - AK/SK: 首次运行时配置, 保存到本地 (~/.mobile_use_agent/credentials.json)
           后续运行自动加载, 无需重复输入
  - ProductId / PodId: 可选保存为"默认手机" (setup 时配置),
           之后运行任务直接回车沿用; 命令行参数始终优先
  - 用户提示词: 每次发起任务时输入

用法:
  # 交互式模式 (首次运行会引导配置 AK/SK)
  python cli.py

  # 重新配置凭证 (可选配置默认手机)
  python cli.py setup

  # 查看当前凭证状态 / 默认手机
  python cli.py whoami

  # 查看/清除默认手机
  python cli.py device [--clear]

  # 一键运行任务 (问答式向导: 先描述任务, 手机默认值回车沿用)
  python cli.py run

  # 命令行直接传参 (跳过交互, 完全可控)
  python cli.py run --product-id PID --pod-id POD --prompt "打开企业微信，回复最新客户消息"

  # 查询任务状态 / 结果 / 取消 / 列表
  python cli.py status --run-id RUN_XXX
  python cli.py result --run-id RUN_XXX
  python cli.py cancel --run-id RUN_XXX
  python cli.py list
"""

import argparse
import json
import os
import sys
import time

# 同目录导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mobile_use_agent import (
    MobileUseAgentClient,
    format_steps,
    format_result,
)
from error_codes import (
    MobileUseError,
    format_error,
    format_friendly_error,
)
from credential_store import (
    load_credentials,
    get_credentials_interactive,
    delete_credentials,
    mask_secret,
    mask_id,
    has_credentials,
    get_default_device,
    set_default_device,
    clear_default_device,
    CREDENTIALS_FILE,
)
from geo import needs_location, ask_location_permission, acquire_gps
from templates import resolve_template, format_template_menu


def print_json(data):
    """格式化输出 JSON"""
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def show_api_error(e: MobileUseError, context: str = ""):
    """展示 API 错误: 优先人话版, 技术细节折叠成一行"""
    print()
    print(format_friendly_error(e, context=context))
    # 资深用户想看完整细节时, 展开技术版
    if os.environ.get("MUA_VERBOSE_ERROR"):
        print()
        print(format_error(e))


def print_welcome():
    """首次使用欢迎页: 大白话说明这是什么 + 要准备什么"""
    print()
    print("=" * 60)
    print("  欢迎使用「云手机小助手」")
    print("=" * 60)
    print("  它会在云端的一台手机上, 帮你自动完成操作")
    print("  (回客户消息、录 CRM 客户、查库存、处理订单审批... 你说一句话, 它来做)")
    print()
    print("  第一次使用, 需要从火山引擎控制台准备 4 个值:")
    print("    ProductId  云手机业务 ID")
    print("    PodId      云手机实例 ID")
    print("    AK / SK    访问密钥 (相当于你的账号密码)")
    print("  只需配置一次, 之后每次运行都会自动记住。")
    print("  详细图文教程: https://github.com/chenjie1129/mobile-use-agent")
    print("=" * 60)


def extract_result_status(result):
    """从 GetAgentResult 响应中提取 (是否成功, 结果文本)"""
    src = result
    if isinstance(result, dict):
        inner = result.get("Result")
        src = inner if isinstance(inner, dict) else result

    is_success = src.get("IsSuccess") if isinstance(src, dict) else None
    ok = is_success == 1 or is_success is True

    result_text = ""
    if isinstance(src, dict):
        r = src.get("Result")
        if isinstance(r, str):
            result_text = r[:200]
        elif isinstance(r, dict):
            result_text = json.dumps(r, ensure_ascii=False, default=str)[:200]
    return ok, result_text


def get_client(force_setup: bool = False) -> MobileUseAgentClient:
    """获取已配置凭证的客户端

    优先使用命令行传入的 --ak/--sk;
    否则从本地加载; 本地也没有则引导首次配置。
    """
    ak, sk = get_credentials_interactive(force_setup=force_setup)
    return MobileUseAgentClient(ak=ak, sk=sk)


def get_product_pod(use_default: bool = True):
    """交互式获取 ProductId/PodId (优先沿用保存的默认手机)

    Args:
        use_default: True 时先显示保存的默认手机, 用户回车即可沿用

    Returns:
        (product_id, pod_id); 用户取消/输入为空时返回 (None, None)
    """
    saved_pid, saved_pod = get_default_device() if use_default else ("", "")

    print("\n--- 云手机实例配置 ---")
    if saved_pid and saved_pod:
        print(f"[提示] 默认手机: ProductId={mask_id(saved_pid)}  PodId={mask_id(saved_pod)}")
        print("       (直接回车沿用默认手机; 输入新值切换)")

    product_id = input(f"ProductId (云手机业务 ID) [{saved_pid}]: ").strip() or saved_pid
    pod_id = input(f"PodId (云手机实例 ID) [{saved_pod}]: ").strip() or saved_pod

    if not product_id or not pod_id:
        print("[错误] ProductId 和 PodId 不能为空! (可用 mua setup 配置默认手机)")
        return None, None

    # 提示可保存为默认 (仅在本次是新输入且与已保存不同时询问)
    if (product_id, pod_id) != (saved_pid, saved_pod):
        try:
            ans = input("将这台手机保存为默认 (下次回车即可用)? [y/N]: ").strip().lower()
            if ans in ("y", "yes"):
                set_default_device(product_id, pod_id)
                print("[成功] 已保存默认手机")
        except ValueError as e:
            print(f"[提示] {e}")

    return product_id, pod_id


def cmd_setup(args):
    """重新配置 AK/SK 凭证 (可选配置默认手机)"""
    if has_credentials():
        saved = load_credentials()
        if saved:
            print(f"当前已保存凭证: AK = {mask_secret(saved[0])}")
            confirm = input("将覆盖已有凭证, 继续? [y/N]: ").strip().lower()
            if confirm != "y":
                print("已取消")
                return

    ak, sk = get_credentials_interactive(force_setup=True)

    # 可选: 配置默认云手机
    print("\n--- 默认云手机 (可选) ---")
    print("配置后运行任务时可直接回车沿用, 不用每次查找 ID")
    saved_pid, saved_pod = get_default_device()
    if saved_pid and saved_pod:
        print(f"[当前默认] ProductId={mask_id(saved_pid)}  PodId={mask_id(saved_pod)}")
        ans = input("保留当前默认手机? [Y/n]: ").strip().lower()
        if ans in ("", "y", "yes"):
            return
    else:
        print("(没有已保存的默认手机)")

    ans = input("是否现在配置默认手机? [y/N]: ").strip().lower()
    if ans not in ("y", "yes"):
        return

    product_id = input("ProductId (云手机业务 ID): ").strip()
    pod_id = input("PodId (云手机实例 ID): ").strip()
    if not product_id or not pod_id:
        print("[提示] 输入为空, 跳过默认手机配置 (仍可在 run 时临时输入)")
        return

    try:
        set_default_device(product_id, pod_id)
        print("[成功] 已保存默认手机, 运行任务时回车即可沿用")
    except ValueError as e:
        print(f"[警告] 保存失败: {e}")


def cmd_whoami(args):
    """查看凭证状态"""
    saved = load_credentials()
    if saved:
        ak, sk = saved
        print(f"凭证文件: {CREDENTIALS_FILE}")
        print(f"AK:       {mask_secret(ak)}")
        print(f"SK:       {mask_secret(sk)}")
        saved_pid, saved_pod = get_default_device()
        if saved_pid and saved_pod:
            print(f"默认手机: ProductId={mask_id(saved_pid)}  PodId={mask_id(saved_pod)}")
        else:
            print("默认手机: (未设置, 运行任务时临时输入即可)")
        print("\n如需重新配置, 运行: python cli.py setup")
    else:
        print("尚未配置凭证")
        print(f"首次运行任意命令时会自动引导配置, 或运行: python cli.py setup")


def cmd_device(args):
    """查看/清除默认云手机"""
    if args.clear:
        try:
            clear_default_device()
            print("[成功] 已清除默认手机 (AK/SK 保留)")
        except Exception as e:
            print(f"[错误] 清除失败: {e}")
        return

    saved_pid, saved_pod = get_default_device()
    if saved_pid and saved_pod:
        print(f"默认手机: ProductId={mask_id(saved_pid)}  PodId={mask_id(saved_pod)}")
        print("\n如需清除, 运行: python cli.py device --clear")
        print("如需更换, 运行: python cli.py setup")
    else:
        print("默认手机: (未设置)")
        print("运行 python cli.py setup 可配置默认手机, 之后任务直接回车沿用")


def cmd_logout(args):
    """删除本地凭证"""
    if not has_credentials():
        print("没有已保存的凭证")
        return

    saved = load_credentials()
    if saved:
        print(f"将删除凭证: AK = {mask_secret(saved[0])}")
    confirm = input("确认删除? [y/N]: ").strip().lower()
    if confirm != "y":
        print("已取消")
        return

    if delete_credentials():
        print(f"[成功] 已删除 {CREDENTIALS_FILE}")
    else:
        print("[失败] 删除失败")


def cmd_run_one_step(client, args):
    """一键运行代理任务 (向导式: 先问做什么, 手机默认值优先)"""
    product_id = args.product_id
    pod_id = args.pod_id
    user_prompt = args.prompt

    # --- 第一步: 用户提示词 (每次输入, 任务的核心) ---
    if not user_prompt:
        print("\n--- 任务配置 ---")
        print("描述你想在云手机上完成的操作。")
        # 0 基础用户引导: 展示现成示例, 输入序号即可用
        print(format_template_menu())
        print()
        user_prompt = input("请描述任务 (输入序号用示例，或直接输入你的任务): ").strip()

        # 解析"输入序号用示例"
        user_prompt, tpl_name = resolve_template(user_prompt)
        if tpl_name:
            print(f"[示例] 已选用「{tpl_name}」模板")
            print(f"       任务内容: {user_prompt}")

    if not user_prompt:
        print("[错误] 任务描述不能为空!")
        return

    # --- 第二步: 云手机 (命令行参数 > 保存的默认手机 > 交互输入) ---
    saved_pid, saved_pod = get_default_device()
    if not product_id:
        product_id = saved_pid
    if not pod_id:
        pod_id = saved_pod

    if not product_id or not pod_id:
        # 需要交互输入 (有默认值时允许回车沿用)
        product_id, pod_id = get_product_pod(use_default=True)
        if not product_id:
            return

    # 提示当前使用的手机 (命令行/默认值时不重复询问)
    if args.product_id or args.pod_id:
        pass  # 命令行显式指定, 已确认
    elif (product_id, pod_id) == (saved_pid, saved_pod) and saved_pid:
        print(f"[手机] 使用默认云手机: ProductId={mask_id(product_id)}  PodId={mask_id(pod_id)}")

    run_name = args.run_name or f"mua-task-{int(__import__('time').time())}"

    # 高级参数 (默认值折叠, 交互模式回车跳过)
    max_step = args.max_step if args.max_step else 100
    timeout = args.timeout if args.timeout else 300
    system_prompt = args.system_prompt or None

    if not args.no_interactive:
        print(f"\n--- 高级参数 (回车使用默认值) ---")
        max_step_input = input(f"最大步数 [{max_step}]: ").strip()
        if max_step_input:
            max_step = int(max_step_input)
        timeout_input = input(f"超时时间(秒) [{timeout}]: ").strip()
        if timeout_input:
            timeout = int(timeout_input)
        system_prompt = (
            input("系统提示词 (可选, 回车跳过): ").strip() or None
        )

    # --- GPS 定位注入 (按任务智能询问, 多来源自动降级) ---
    gps_info = None
    if args.gps:
        # 命令行显式授权 (非交互模式唯一注入途径)
        gps_info = acquire_gps(prompt=user_prompt, allow_manual=not args.no_interactive)
    elif not args.no_interactive and needs_location(user_prompt):
        # 任务与位置相关才询问; 无关任务自动跳过, 不打扰
        print("\n--- GPS 定位注入 ---")
        print("[提示] 任务涉及位置, 可注入本机定位到云手机")
        if ask_location_permission(user_prompt):
            # 已授权: 系统定位 → IP 定位 → 文本坐标/地理编码 → 手动输入
            gps_info = acquire_gps(prompt=user_prompt)
        else:
            # 拒绝自动获取: 仅走无隐私来源 (提示词中的坐标/地名) + 手动输入兜底
            print("[提示] 已拒绝自动获取。如提示词含坐标/地址仍会自动解析, 也可手动输入")
            gps_info = acquire_gps(
                prompt=user_prompt, allow_permission=False, allow_ip=False
            )
            if gps_info is None:
                print("[跳过] 未提供位置, 本次任务不注入 GpsInfo")

    # --- 运行并等待 (统计耗时) ---
    t0 = time.time()
    result = client.run_and_wait(
        run_name=run_name,
        pod_id=pod_id,
        product_id=product_id,
        user_prompt=user_prompt,
        max_step=max_step,
        timeout=timeout,
        system_prompt=system_prompt,
        gps_info=gps_info,
    )
    elapsed = int(time.time() - t0)

    # 成功反馈: 明确告诉用户"完成/未成功"和用时 (确定感)
    ok, _ = extract_result_status(result)
    if ok:
        print(f"\n[完成] 任务成功！用时约 {elapsed} 秒")
    else:
        print(f"\n[未完成] 任务没有成功, 用时约 {elapsed} 秒")
        print("         可以换个更清楚的说法再试一次 (运行 mua run)")

    print("\n" + "=" * 60)
    print("  [最终结果]")
    print("=" * 60)
    print(format_result(result))


def cmd_status(client, args):
    """查询任务当前步骤"""
    run_id = args.run_id
    if not run_id:
        run_id = input("请输入 RunId: ").strip()
    if not run_id:
        print("[错误] RunId 不能为空!")
        return

    resp = client.list_agent_run_current_step(run_id)
    print("\n" + "=" * 60)
    print(f"  [任务步骤] RunId: {run_id}")
    print("=" * 60)
    print(format_steps(resp))


def cmd_result(client, args):
    """获取任务运行结果"""
    run_id = args.run_id
    if not run_id:
        run_id = input("请输入 RunId: ").strip()
    if not run_id:
        print("[错误] RunId 不能为空!")
        return

    resp = client.get_agent_result(run_id)
    print("\n" + "=" * 60)
    print(f"  [任务结果] RunId: {run_id}")
    print("=" * 60)
    print(format_result(resp))


def cmd_cancel(client, args):
    """取消代理任务"""
    run_id = args.run_id
    if not run_id:
        run_id = input("请输入 RunId: ").strip()
    if not run_id:
        print("[错误] RunId 不能为空!")
        return

    confirm = input(f"确认取消任务 {run_id}? [y/N]: ").strip()
    if confirm.lower() != "y":
        print("已取消操作")
        return

    resp = client.cancel_task(run_id)
    print_json(resp)


def cmd_list(client, args):
    """查询代理任务列表"""
    resp = client.list_agent_run_task(
        run_id=args.run_id,
        run_name=args.run_name,
        page_size=args.page_size or 10,
        page_number=args.page_number or 1,
    )
    print_json(resp)


def cmd_config_create(client, args):
    """创建代理运行配置"""
    max_step = args.max_step or 55
    timeout = args.timeout or 300

    if not args.no_interactive:
        max_step_input = input(f"最大步数 [{max_step}]: ").strip()
        if max_step_input:
            max_step = int(max_step_input)
        timeout_input = input(f"超时时间(秒) [{timeout}]: ").strip()
        if timeout_input:
            timeout = int(timeout_input)

    config_id = client.create_agent_run_config(
        max_step=max_step,
        timeout=timeout,
        tos_bucket=args.tos_bucket or "",
        tos_endpoint=args.tos_endpoint or "",
        tos_region=args.tos_region or "",
        callback_url=args.callback_url or "",
    )
    print(f"\n[成功] ConfigId: {config_id}")


def cmd_config_list(client, args):
    """查询代理运行配置列表"""
    resp = client.list_agent_run_config(
        page_size=args.page_size or 10,
        page_number=args.page_number or 1,
    )
    print_json(resp)


def cmd_config_delete(client, args):
    """删除代理运行配置"""
    config_id = args.config_id
    if not config_id:
        config_id = input("请输入 ConfigId: ").strip()
    if not config_id:
        print("[错误] ConfigId 不能为空!")
        return

    resp = client.delete_agent_run_config(config_id)
    print_json(resp)


def interactive_menu(client):
    """交互式菜单 (凭证已就绪)"""

    while True:
        print("\n" + "=" * 50)
        print("  Mobile Use Agent - 交互式菜单")
        print("=" * 50)
        print("  1. 运行代理任务  (问答式向导, 默认手机回车沿用)")
        print("  2. 查询任务当前步骤")
        print("  3. 获取任务运行结果")
        print("  4. 取消代理任务")
        print("  5. 查询代理任务列表")
        print("  6. 创建代理运行配置")
        print("  7. 查询代理运行配置列表")
        print("  8. 删除代理运行配置")
        print("  9. 重新配置凭证 (AK/SK)")
        print("  0. 退出")
        print("=" * 50)

        choice = input("请选择操作: ").strip()

        if choice == "1":
            # 复用命令行向导 (同一套流程, 避免逻辑漂移)
            fake_args = argparse.Namespace(
                product_id="", pod_id="", prompt="", run_name="",
                max_step=0, timeout=0, system_prompt="",
                gps=False, no_interactive=False,
            )
            cmd_run_one_step(client, fake_args)

        elif choice == "2":
            run_id = input("请输入 RunId: ").strip()
            if run_id:
                resp = client.list_agent_run_current_step(run_id)
                print("\n" + "=" * 60)
                print(f"  [任务步骤] RunId: {run_id}")
                print("=" * 60)
                print(format_steps(resp))

        elif choice == "3":
            run_id = input("请输入 RunId: ").strip()
            if run_id:
                resp = client.get_agent_result(run_id)
                print("\n" + "=" * 60)
                print(f"  [任务结果] RunId: {run_id}")
                print("=" * 60)
                print(format_result(resp))

        elif choice == "4":
            run_id = input("请输入 RunId: ").strip()
            if run_id:
                confirm = input(f"确认取消? [y/N]: ").strip()
                if confirm.lower() == "y":
                    resp = client.cancel_task(run_id)
                    print_json(resp)

        elif choice == "5":
            resp = client.list_agent_run_task()
            print_json(resp)

        elif choice == "6":
            max_step_input = input("最大步数 [55]: ").strip()
            max_step = int(max_step_input) if max_step_input else 55
            timeout_input = input("超时时间(秒) [300]: ").strip()
            timeout = int(timeout_input) if timeout_input else 300

            config_id = client.create_agent_run_config(
                max_step=max_step, timeout=timeout
            )
            print(f"\n[成功] ConfigId: {config_id}")

        elif choice == "7":
            resp = client.list_agent_run_config()
            print_json(resp)

        elif choice == "8":
            config_id = input("请输入 ConfigId: ").strip()
            if config_id:
                resp = client.delete_agent_run_config(config_id)
                print_json(resp)

        elif choice == "9":
            get_credentials_interactive(force_setup=True)
            client = get_client()

        elif choice == "0":
            print("再见!")
            break
        else:
            print("无效选择, 请重试")


def main():
    parser = argparse.ArgumentParser(
        description="Mobile Use Agent CLI - 火山引擎云手机 Agent OpenAPI 工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # 全局凭证参数 (可选, 覆盖本地保存的凭证)
    parser.add_argument(
        "--ak", default=os.environ.get("VOLC_ACCESSKEY", ""),
        help="Access Key ID (不传则使用本地保存的凭证)"
    )
    parser.add_argument(
        "--sk", default=os.environ.get("VOLC_SECRETKEY", ""),
        help="Secret Access Key (不传则使用本地保存的凭证)"
    )

    subparsers = parser.add_subparsers(dest="command", help="操作命令")

    # setup - 配置凭证
    subparsers.add_parser("setup", help="配置/重新配置 AK/SK 凭证")

    # whoami - 查看凭证状态
    subparsers.add_parser("whoami", help="查看当前凭证状态")

    # logout - 删除本地凭证
    subparsers.add_parser("logout", help="删除本地保存的凭证")

    # device - 查看/清除默认云手机
    p_device = subparsers.add_parser("device", help="查看/清除默认云手机 (ProductId/PodId)")
    p_device.add_argument("--clear", action="store_true", help="清除保存的默认手机")

    # run - 运行代理任务 (每次输入 ProductId/PodId/提示词)
    p_run = subparsers.add_parser("run", help="运行代理任务 (RunAgentTaskOneStep)")
    p_run.add_argument("--product-id", default="", help="云手机业务 ID")
    p_run.add_argument("--pod-id", default="", help="云手机实例 ID")
    p_run.add_argument("--run-name", default="", help="运行名称")
    p_run.add_argument("--prompt", default="", help="用户提示词")
    p_run.add_argument("--max-step", type=int, default=0, help="最大步数 (默认 100)")
    p_run.add_argument("--timeout", type=int, default=0, help="超时时间秒 (默认 300)")
    p_run.add_argument("--system-prompt", default="", help="系统提示词")
    p_run.add_argument(
        "--gps", action="store_true",
        help="允许获取当前位置并注入 GpsInfo (非交互模式下自动获取, 不再询问)"
    )
    p_run.add_argument("--no-interactive", action="store_true", help="跳过交互式参数确认")

    # status - 查询当前步骤
    p_status = subparsers.add_parser("status", help="查询任务当前步骤")
    p_status.add_argument("--run-id", default="", help="运行 ID")

    # result - 获取结果
    p_result = subparsers.add_parser("result", help="获取任务运行结果")
    p_result.add_argument("--run-id", default="", help="运行 ID")

    # cancel - 取消任务
    p_cancel = subparsers.add_parser("cancel", help="取消代理任务")
    p_cancel.add_argument("--run-id", default="", help="运行 ID")

    # list - 列出任务
    p_list = subparsers.add_parser("list", help="查询代理任务列表")
    p_list.add_argument("--run-id", default="", help="运行 ID (筛选)")
    p_list.add_argument("--run-name", default="", help="运行名称 (筛选)")
    p_list.add_argument("--page-size", type=int, default=0, help="每页数量")
    p_list.add_argument("--page-number", type=int, default=0, help="页码")

    # config create
    p_cc = subparsers.add_parser("config-create", help="创建代理运行配置")
    p_cc.add_argument("--max-step", type=int, default=0, help="最大步数 (默认 55)")
    p_cc.add_argument("--timeout", type=int, default=0, help="超时时间秒 (默认 300)")
    p_cc.add_argument("--tos-bucket", default="", help="TOS 存储桶")
    p_cc.add_argument("--tos-endpoint", default="", help="TOS 端点")
    p_cc.add_argument("--tos-region", default="", help="TOS 区域")
    p_cc.add_argument("--callback-url", default="", help="回调 URL")
    p_cc.add_argument("--no-interactive", action="store_true", help="跳过交互式确认")

    # config list
    p_cl = subparsers.add_parser("config-list", help="查询代理运行配置列表")
    p_cl.add_argument("--page-size", type=int, default=0, help="每页数量")
    p_cl.add_argument("--page-number", type=int, default=0, help="页码")

    # config delete
    p_cd = subparsers.add_parser("config-delete", help="删除代理运行配置")
    p_cd.add_argument("--config-id", default="", help="配置 ID")

    args = parser.parse_args()

    # ---------- 凭证管理类命令 (无需 API 客户端) ----------
    if args.command == "setup":
        cmd_setup(args)
        return
    if args.command == "whoami":
        cmd_whoami(args)
        return
    if args.command == "logout":
        cmd_logout(args)
        return
    if args.command == "device":
        cmd_device(args)
        return

    # ---------- 获取凭证 ----------
    ak = args.ak
    sk = args.sk

    if ak and sk:
        # 命令行/环境变量显式传入: 直接使用, 不读本地
        client = MobileUseAgentClient(ak=ak, sk=sk)
    else:
        # 首次使用: 先展示欢迎页, 再引导配置并保存
        if not has_credentials():
            print_welcome()
        # 本地加载 -> 首次引导配置并保存
        client = get_client()

    # ---------- 无命令 -> 交互式菜单 ----------
    if not args.command:
        interactive_menu(client)
        return

    # ---------- 分发命令 ----------
    handlers = {
        "run": cmd_run_one_step,
        "status": cmd_status,
        "result": cmd_result,
        "cancel": cmd_cancel,
        "list": cmd_list,
        "config-create": cmd_config_create,
        "config-list": cmd_config_list,
        "config-delete": cmd_config_delete,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return

    try:
        handler(client, args)
    except KeyboardInterrupt:
        print("\n[中断] 操作已取消")
    except SystemExit:
        raise
    except MobileUseError as e:
        # 带错误码的 API 错误: 展示中文描述 + 操作建议 + 分类引导
        show_api_error(e)
    except Exception as e:
        # 其他异常: 友好呈现, 凭证失效时给出重新配置提示
        msg = str(e)
        print(f"\n[错误] {type(e).__name__}: {msg[:500]}")

        if "InvalidAccessKey" in msg or "Unauthorized" in msg or "401" in msg:
            print("\n[提示] 凭证无效或已过期, 请重新配置:")
            print("       python cli.py setup")


if __name__ == "__main__":
    main()
