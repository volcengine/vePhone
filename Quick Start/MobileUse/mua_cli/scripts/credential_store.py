"""
凭证持久化管理

AK/SK 在首次运行时由用户配置，保存到本地文件:
    ~/.mobile_use_agent/credentials.json

文件权限设为 600 (仅所有者可读写)，后续运行自动加载，无需重复输入。

ProductId / PodId (默认云手机) 也可选持久化:
    - setup 时可选配置默认手机, 之后 run 时回车即可沿用, 无需每次查找
    - 命令行 --product-id / --pod-id 始终优先于保存的默认值
    - 用户提示词每次运行时输入 (不做持久化)
"""

import json
import os
import sys
import getpass
from pathlib import Path
from typing import Optional, Tuple

# 凭证文件位置: 用户主目录下
CREDENTIALS_DIR = Path.home() / ".mobile_use_agent"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"


def _secret_input(prompt: str) -> str:
    """读取敏感输入: 终端下隐藏回显 (getpass), 管道/非交互场景回退普通输入"""
    if sys.stdin.isatty():
        return getpass.getpass(prompt).strip()
    # 管道输入 (CI/脚本): getpass 会阻塞等待 TTY, 回退为普通读取
    return input(prompt).strip()


def _read_file() -> dict:
    """读取凭证文件内容 (不存在/损坏时返回空 dict)"""
    if not CREDENTIALS_FILE.exists():
        return {}
    try:
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _write_file(data: dict) -> Path:
    """写入凭证文件, 权限 600 / 目录 700"""
    CREDENTIALS_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.chmod(CREDENTIALS_FILE, 0o600)
    os.chmod(CREDENTIALS_DIR, 0o700)
    return CREDENTIALS_FILE


def has_credentials() -> bool:
    """检查是否已保存凭证"""
    return CREDENTIALS_FILE.exists()


def load_credentials() -> Optional[Tuple[str, str]]:
    """加载已保存的凭证 (兼容旧接口)

    Returns:
        (ak, sk) 元组; 未保存或文件损坏时返回 None
    """
    data = _read_file()
    ak = data.get("ak", "")
    sk = data.get("sk", "")
    if ak and sk:
        return ak, sk
    return None


def load_profile() -> dict:
    """加载完整配置档案

    Returns:
        dict: {ak, sk, product_id, pod_id} 各项可能为空字符串
    """
    data = _read_file()
    return {
        "ak": data.get("ak", ""),
        "sk": data.get("sk", ""),
        "product_id": data.get("product_id", ""),
        "pod_id": data.get("pod_id", ""),
    }


def save_credentials(
    ak: str,
    sk: str,
    product_id: str = "",
    pod_id: str = "",
) -> Path:
    """保存凭证 (可选附带默认云手机) 到本地文件

    文件权限设为 600 (仅所有者可读写)。

    Args:
        ak: Access Key ID
        sk: Secret Access Key
        product_id: 默认云手机业务 ID (可选, 留空不保存)
        pod_id: 默认云手机实例 ID (可选, 留空不保存)

    Returns:
        保存的文件路径
    """
    if not ak or not sk:
        raise ValueError("AK/SK 不能为空")

    data = {"ak": ak, "sk": sk}
    if product_id:
        data["product_id"] = product_id
    if pod_id:
        data["pod_id"] = pod_id

    return _write_file(data)


def set_default_device(product_id: str, pod_id: str) -> Path:
    """保存默认云手机 (不修改 AK/SK)

    Args:
        product_id: 云手机业务 ID
        pod_id: 云手机实例 ID

    Returns:
        保存的文件路径; AK/SK 未配置时抛 ValueError
    """
    if not product_id or not pod_id:
        raise ValueError("ProductId/PodId 不能为空")
    if not has_credentials():
        raise ValueError("请先配置 AK/SK 凭证 (mua setup)")

    data = _read_file()
    data["product_id"] = product_id
    data["pod_id"] = pod_id
    return _write_file(data)


def clear_default_device() -> Path:
    """清除保存的默认云手机 (保留 AK/SK)"""
    data = _read_file()
    data.pop("product_id", None)
    data.pop("pod_id", None)
    return _write_file(data)


def get_default_device() -> Tuple[str, str]:
    """获取保存的默认云手机

    Returns:
        (product_id, pod_id), 未配置时均为空字符串
    """
    data = _read_file()
    return data.get("product_id", ""), data.get("pod_id", "")


def delete_credentials() -> bool:
    """删除已保存的凭证

    Returns:
        是否成功删除 (文件不存在时返回 False)
    """
    if CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.unlink()
        return True
    return False


def mask_secret(secret: str, show_prefix: int = 4, show_suffix: int = 4) -> str:
    """脱敏展示密钥

    Args:
        secret: 原始密钥
        show_prefix: 展示前缀字符数
        show_suffix: 展示后缀字符数

    Returns:
        脱敏后的字符串, 如 "AKLT****abcd"
    """
    if not secret:
        return "(空)"

    if len(secret) <= show_prefix + show_suffix:
        return "*" * len(secret)

    return (
        secret[:show_prefix]
        + "*" * 8
        + secret[-show_suffix:]
    )


def mask_id(id_str: str, show_head: int = 6, show_tail: int = 4) -> str:
    """脱敏展示长 ID (ProductId/PodId 等)

    Args:
        id_str: 原始 ID
        show_head: 展示头部字符数
        show_tail: 展示尾部字符数

    Returns:
        脱敏后的字符串, 如 "prod-1f3a****9c2e"; 短 ID 直接返回
    """
    if not id_str:
        return "(未设置)"
    if len(id_str) <= show_head + show_tail:
        return id_str
    return f"{id_str[:show_head]}****{id_str[-show_tail:]}"


def get_credentials_interactive(force_setup: bool = False) -> Tuple[str, str]:
    """获取凭证: 优先从本地加载, 首次使用(或强制重配)时交互式输入并保存

    Args:
        force_setup: True 表示忽略已保存凭证, 强制重新输入

    Returns:
        (ak, sk) 元组
    """
    # 尝试加载已保存的凭证
    if not force_setup:
        saved = load_credentials()
        if saved:
            ak, sk = saved
            print(f"[凭证] 已加载本地配置: {mask_secret(ak)}")
            print(f"[凭证] 文件位置: {CREDENTIALS_FILE}")
            return ak, sk

    # 首次使用或强制重配: 交互式输入
    if force_setup:
        print("\n--- 重新配置火山引擎凭证 ---")
    else:
        print("\n--- 首次使用: 配置火山引擎凭证 (仅此一次) ---")
        print("凭证将保存到本地, 后续运行自动加载。")

    print("获取方式: 火山引擎控制台 -> 右上角头像 -> 访问密钥\n")

    while True:
        ak = _secret_input("请输入 AK (Access Key ID): ")
        if not ak:
            print("[错误] AK 不能为空, 请重新输入")
            continue

        sk = _secret_input("请输入 SK (Secret Access Key): ")
        if not sk:
            print("[错误] SK 不能为空, 请重新输入")
            continue

        # 确认
        print(f"\nAK: {mask_secret(ak)}")
        confirm = input("确认保存? [Y/n]: ").strip().lower()
        if confirm in ("", "y", "yes"):
            break
        print("请重新输入。\n")

    # 保存到本地
    try:
        path = save_credentials(ak, sk)
        print(f"\n[成功] 凭证已保存到: {path}")
        print("[提示] 如需重新配置, 运行: python cli.py setup\n")
    except Exception as e:
        print(f"\n[警告] 凭证保存失败 ({e}), 本次会话仍可继续使用")

    return ak, sk
