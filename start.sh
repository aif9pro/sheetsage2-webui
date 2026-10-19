#!/usr/bin/env bash
# ---------------------------------------------------------------------------
#  SheetSage2 WebUI - launcher for macOS / Linux.
#
#  与 start.bat 对应的 POSIX 版本：找到解释器 -> python -m app.server。
#  Windows 用 start.bat；macOS / Linux 用本脚本。
#
#  解释器查找顺序（先本目录，再逐级往上 4 层，取最先命中的）：
#      runtime/python/bin/python3        <- 便携运行时（如随包分发）
#      runtime/python/bin/python
#      .venv/bin/python                  <- 源码方式的虚拟环境
#
#  用法：
#      ./start.sh                 # 默认端口 8777
#      ./start.sh --port 8898     # 换端口
#      ./start.sh --no-browser    # 不自动开浏览器
# ---------------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")"
HERE="$(pwd)"

export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"

# --- 找解释器 ---------------------------------------------------------------
PY=""
probe() {
  local dir="$1"
  [ -n "$PY" ] && return 0
  for cand in \
      "$dir/runtime/python/bin/python3" \
      "$dir/runtime/python/bin/python" \
      "$dir/.venv/bin/python"; do
    if [ -x "$cand" ]; then
      PY="$cand"
      return 0
    fi
  done
  return 0
}

probe "$HERE"
probe "$HERE/.."
probe "$HERE/../.."
probe "$HERE/../../.."
probe "$HERE/../../../.."

if [ -z "$PY" ]; then
  echo
  echo "  [错误] 没找到 Python 解释器。已在当前目录及上溯 4 层查找，"
  echo "         位置为 runtime/python/bin/python3 与 .venv/bin/python。"
  echo
  echo "  源码方式请先建好虚拟环境："
  echo "      python3.12 -m venv .venv"
  echo "      # 或： uv venv --python 3.12 .venv"
  echo "  详细步骤见 docs/macOS安装指南.md"
  echo
  exit 1
fi

if [ ! -f "$HERE/app/server.py" ]; then
  echo "  [错误] 找不到 app/server.py，请在项目根目录运行本脚本。"
  exit 1
fi

# --- 依赖预检：缺依赖时给一句人话，而不是稍后抛栈 ---------------------------
if ! "$PY" -c "import fastapi" >/dev/null 2>&1; then
  REQ="$HERE/requirements-base.txt"
  if [ "$(uname -s)" = "Darwin" ] && [ -f "$HERE/requirements-macos.txt" ]; then
    REQ="$HERE/requirements-macos.txt"
  fi
  echo
  echo "  [错误] 这个解释器还没装依赖："
  echo "         $PY"
  echo
  echo "  装好再运行本脚本："
  echo "         \"$PY\" -m pip install -r \"$REQ\""
  echo
  exit 1
fi

echo
echo "  SheetSage2 扒谱 Web 工具"
echo "  代码目录：  $HERE"
echo "  解释器：    $PY"
echo
echo "  正在启动…浏览器会自动打开。关闭本窗口即停止服务。"
echo
echo "  提示：若 8777 端口已被另一个 SheetSage2 占用，程序会直接打开那一个。"
echo "        想在空闲端口测试本目录：  ./start.sh --port 8898"
echo

"$PY" -m app.server "$@"
