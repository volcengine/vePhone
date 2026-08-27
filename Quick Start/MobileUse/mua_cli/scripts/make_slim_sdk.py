#!/usr/bin/env python3
"""
make_slim_sdk.py - 从官方 volcengine-python-sdk wheel 构建精简 wheel

为什么需要:
  官方 wheel 是 137 个火山引擎产品的"全家桶", 解压 507MB / 2.6 万个文件,
  首次 pip install 约 5-10 分钟, 绝大部分时间花在与本工具无关的产品模块上。
  本 skill 通过 volcenginesdkcore.UniversalApi 通用调用 Mobile Use Agent
  OpenAPI, 实际只需要其中 1 个模块:
      volcenginesdkcore  (约 81 个文件 / 604KB, 含签名 / 认证 / REST 客户端)

做什么:
  从官方 wheel 只抽取 volcenginesdkcore + 官方 METADATA (依赖声明原样保留),
  重新打包成"同名同版本"的合法 wheel。pip 安装它时与官方包行为一致:
  - pip list 仍显示 volcengine-python-sdk <版本>
  - 依赖 (certifi / python-dateutil / six / urllib3) 照常自动安装
  - 之后 pip install -U volcengine-python-sdk 可无缝升级回官方完整包

用法:
  python3 make_slim_sdk.py <官方 wheel 所在目录> <输出目录>
  # 输出: <输出目录>/volcengine_python_sdk-<版本>-py2.py3-none-any.whl

仅依赖标准库 (zipfile / hashlib), 无需安装任何第三方包。
退出码: 0 成功; 2 用法错误; 其他为构建失败 (install.sh 会回退完整安装)。
"""

import base64
import glob
import hashlib
import io
import os
import sys
import zipfile

DIST = "volcengine_python_sdk"
KEEP_TOP_LEVELS = ("volcenginesdkcore",)  # 本 skill 用到的全部 SDK 模块


def find_official_wheel(indir: str) -> str:
    """在目录中查找官方 wheel, 多个版本时取版本号最大的。"""
    wheels = sorted(glob.glob(os.path.join(indir, DIST + "-*.whl")))
    if not wheels:
        raise SystemExit(f"[错误] {indir} 下未找到 {DIST}-*.whl")
    return wheels[-1]


def main() -> int:
    if len(sys.argv) != 3:
        print("[用法] python3 make_slim_sdk.py <官方wheel目录> <输出目录>")
        return 2
    indir, outdir = sys.argv[1], sys.argv[2]

    src_path = find_official_wheel(indir)
    parts = os.path.basename(src_path).split("-")
    version, tag_part = parts[1], "-".join(parts[2:])
    dist_info = f"{DIST}-{version}.dist-info"
    os.makedirs(outdir, exist_ok=True)
    out_path = os.path.join(outdir, f"{DIST}-{version}-{tag_part}")

    keep: list = []  # [(arcname, bytes), ...]
    with zipfile.ZipFile(src_path) as src:
        names = src.namelist()
        for n in names:
            top = n.split("/", 1)[0]
            if top in KEEP_TOP_LEVELS:
                keep.append((n, src.read(n)))          # 包源码
            elif n == f"{dist_info}/METADATA":
                keep.append((n, src.read(n)))          # 依赖声明原样保留
            elif n.startswith(f"{dist_info}/licenses/"):
                keep.append((n, src.read(n)))          # LICENSE / NOTICE

    if not any(n.split("/", 1)[0] in KEEP_TOP_LEVELS for n, _ in keep):
        raise SystemExit("[错误] 官方 wheel 中未找到 volcenginesdkcore, 结构可能已变化")

    wheel_meta = (
        "Wheel-Version: 1.0\n"
        "Generator: make_slim_sdk\n"
        "Root-Is-Purelib: true\n"
        "Tag: py2-none-any\n"
        "Tag: py3-none-any\n"
    )
    top_level = "".join(t + "\n" for t in KEEP_TOP_LEVELS)

    # RECORD: name,sha256=<urlsafe-b64>,<size> (RECORD 自身条目按规范留空 hash)
    buf = io.StringIO()
    for n, data in keep:
        digest = base64.urlsafe_b64encode(
            hashlib.sha256(data).digest()
        ).rstrip(b"=").decode()
        buf.write(f"{n},sha256={digest},{len(data)}\n")
    for extra in (f"{dist_info}/WHEEL", f"{dist_info}/top_level.txt"):
        buf.write(f"{extra},,\n")
    record = buf.getvalue().encode()

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as out:
        for n, data in keep:
            out.writestr(n, data)
        out.writestr(f"{dist_info}/WHEEL", wheel_meta)
        out.writestr(f"{dist_info}/top_level.txt", top_level)
        out.writestr(f"{dist_info}/RECORD", record)

    slim_files = len(keep) + 3
    print(f"[完成] 精简 wheel: {out_path}")
    print(f"       官方 wheel: {len(names)} 个文件 / {os.path.getsize(src_path) / 1048576:.1f}MB")
    print(f"       精简 wheel: {slim_files} 个文件 / {os.path.getsize(out_path) / 1024:.0f}KB"
          f" (仅保留 {', '.join(KEEP_TOP_LEVELS)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
