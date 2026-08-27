#!/usr/bin/env bash
# install.sh - 一键安装 mua 全局命令 (含独立 Python 环境)
#
# 做什么:
#   1. 创建独立 Python 环境 (venv) 并安装全部依赖
#      -> 不依赖、也不污染你电脑上已有的 Python / 系统环境
#      -> 精简安装: 官方 SDK 是 137 个产品的全家桶 (2.6 万个文件, 完整安装约
#         5-10 分钟), 本工具只用其中 1 个模块, 因此只抽取安装, 通常 1 分钟内完成
#   2. 将 bin/mua 软链到 ~/.local/bin/mua, 之后任意目录可直接使用:
#      mua setup / mua run / mua status ...
#
# 用法:
#   ./install.sh          # 安装 (默认 ~/.local/bin, 环境放 ~/.local/share/mobile-use-agent/venv)
#   INSTALL_DIR=/usr/local/bin ./install.sh   # 指定命令安装目录
#   VENV_DIR=/opt/mua-venv ./install.sh       # 指定 Python 环境位置
#
# 重复执行安全: 环境已就绪则跳过安装, 直接重做软链。
set -euo pipefail

SCRIPT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"
VENV_DIR="${VENV_DIR:-$HOME/.local/share/mobile-use-agent/venv}"
TARGET="$INSTALL_DIR/mua"

# --- 0. 前置检查: 需要 python3 ---
if ! command -v python3 >/dev/null 2>&1; then
  echo "错误: 未找到 python3, 请先安装 (https://www.python.org/downloads/)" >&2
  exit 1
fi
if ! python3 -c 'import venv, ensurepip' >/dev/null 2>&1; then
  echo "错误: 当前 python3 缺少 venv 模块。" >&2
  echo "       macOS: 请安装完整版 Python (python.org 或 brew install python)" >&2
  echo "       Ubuntu/Debian: sudo apt install python3-venv" >&2
  exit 1
fi

# --- 1. 创建独立 Python 环境 (幂等) ---
echo "[1/3] 准备独立 Python 环境..."
if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "      创建环境: $VENV_DIR"
  mkdir -p "$(dirname "$VENV_DIR")"
  python3 -m venv "$VENV_DIR"
else
  echo "      环境已存在, 复用: $VENV_DIR"
fi

# --- 2. 安装依赖 (仅当 SDK 缺失时) ---
echo "[2/3] 检查依赖..."
if ! "$VENV_DIR/bin/python" -c "import volcenginesdkcore" >/dev/null 2>&1; then
  echo "      正在安装依赖到独立环境..."
  # 精简安装: 全家桶 2.6 万个文件里本工具只用 volcenginesdkcore (81 个文件),
  # 只下载官方 wheel 并抽取该模块, 安装耗时从 ~9 分钟降到 ~1 分钟。
  TMP_DEP="$(mktemp -d)"
  install_deps_slim() {
    local sdk_spec
    sdk_spec="$(grep -iE '^[[:space:]]*volcengine-python-sdk' "$SCRIPT_DIR/requirements.txt" 2>/dev/null | head -1 | tr -d '[:space:]')"
    [ -z "$sdk_spec" ] && sdk_spec="volcengine-python-sdk"
    echo "      [a] 下载官方 SDK 安装包 (43MB, 只下载一次, 请稍候)..."
    "$VENV_DIR/bin/pip" download "$sdk_spec" --no-deps -d "$TMP_DEP/wheel" || return 1
    echo "      [b] 构建精简包 (只保留用到的 1/137 个模块)..."
    "$VENV_DIR/bin/python" "$SCRIPT_DIR/scripts/make_slim_sdk.py" \
      "$TMP_DEP/wheel" "$TMP_DEP/slim" || return 1
    echo "      [c] 安装精简 SDK 及依赖 (certifi/python-dateutil/six/urllib3)..."
    "$VENV_DIR/bin/pip" install "$TMP_DEP/slim/"*.whl || return 1
    # 其余依赖 (Pillow / pyobjc 等, 都是小包; 注释和空行 pip 会自动忽略)
    grep -viE '^[[:space:]]*volcengine-python-sdk' "$SCRIPT_DIR/requirements.txt" \
      > "$TMP_DEP/req-rest.txt" 2>/dev/null || true
    if [ -s "$TMP_DEP/req-rest.txt" ]; then
      "$VENV_DIR/bin/pip" install -r "$TMP_DEP/req-rest.txt" || return 1
    fi
    return 0
  }
  if install_deps_slim; then
    echo "      依赖安装完成 (精简模式, 只装用得到的部分)"
  else
    echo "      [提示] 精简安装未成功, 回退到官方完整安装 (约 5-10 分钟)..."
    "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
    echo "      依赖安装完成 (完整模式)"
  fi
  rm -rf "$TMP_DEP"
else
  echo "      依赖已就绪, 跳过安装"
fi

# --- 3. 软链全局命令 ---
echo "[3/3] 安装全局命令..."
mkdir -p "$INSTALL_DIR"
chmod +x "$SCRIPT_DIR/bin/mua"
ln -sf "$SCRIPT_DIR/bin/mua" "$TARGET"
echo "      已安装: $TARGET -> $SCRIPT_DIR/bin/mua"

# --- 检查 PATH ---
case ":$PATH:" in
  *":$INSTALL_DIR:"*) ;;
  *)
    echo ""
    echo "[提示] $INSTALL_DIR 不在 PATH 中, 请执行以下命令后重开终端:"
    if [[ "$INSTALL_DIR" == "$HOME/.local/bin" ]]; then
      echo "   echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc && source ~/.zshrc"
    else
      echo "   export PATH=\"$INSTALL_DIR:\$PATH\""
    fi
    ;;
esac

echo ""
echo "安装完成! 依赖已装入独立环境, 不影响系统 Python。"
echo "试试:"
echo "   mua whoami    # 查看凭证状态"
echo "   mua setup     # 配置 AK/SK (首次使用)"
echo "   mua run       # 问答式向导运行任务"
