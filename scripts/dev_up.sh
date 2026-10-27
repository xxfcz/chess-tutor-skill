#!/usr/bin/env bash
# dev_up.sh — 一条命令还原完整开发/运行环境
# =========================================
# 适用场景：新会话 / 新沙箱 clone 仓库后，快速恢复成"可开发、可观战"的状态。
#
# 做四件事：
#   1. 检查 Python 依赖（flask / python-chess），缺则装
#   2. 检查 Stockfish 引擎可用
#   3. 起 app.py（默认 8080，可用 PORT 覆盖），等待健康检查通过
#   4. 可选起 bridge.py 常驻观战桥（--with-bridge，或 FEED=1）
#
# 用法：
#   bash scripts/dev_up.sh                 # 只起网站
#   bash scripts/dev_up.sh --with-bridge   # 网站 + 观战桥
#   PORT=9000 bash scripts/dev_up.sh       # 换端口
#   bash scripts/dev_up.sh --restart       # 先杀旧进程再起
#
# 幂等：重复执行不会起重复进程（已有健康实例则直接复用）。
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLAY="$ROOT/play"
PORT="${PORT:-8080}"
WITH_BRIDGE=0
RESTART=0

for a in "$@"; do
  case "$a" in
    --with-bridge) WITH_BRIDGE=1 ;;
    --restart)     RESTART=1 ;;
    -h|--help)     sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "未知参数: $a（--help 看用法）" >&2; exit 2 ;;
  esac
done

mkdir -p "$ROOT/.run"

say()  { printf '\033[36m[dev_up]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[dev_up] %s\033[0m\n' "$*"; }
die()  { printf '\033[31m[dev_up] %s\033[0m\n' "$*" >&2; exit 1; }

# ---------- 0. 选 Python ----------
PY=""
for c in python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
[ -n "$PY" ] || die "找不到 python3，请先安装 Python 3.11"
say "Python: $($PY -V 2>&1)"

# ---------- 1. 依赖 ----------
need_mod() { "$PY" -c "import $1" >/dev/null 2>&1; }
if ! need_mod flask || ! need_mod chess; then
  say "安装依赖（flask / python-chess）…"
  "$PY" -m pip install -q -r "$PLAY/requirements.txt" \
    || die "依赖安装失败，请检查网络或手动执行: $PY -m pip install -r play/requirements.txt"
  need_mod flask || die "flask 安装后仍不可用"
  need_mod chess || die "python-chess 安装后仍不可用"
fi
say "依赖 OK（flask / python-chess）"

# ---------- 2. Stockfish ----------
SF="$(command -v stockfish || true)"
if [ -z "$SF" ]; then
  warn "未找到 stockfish 可执行文件 —— 对弈陪练/开局演示的引擎讲解会不可用"
  warn "  Debian/Ubuntu: apt-get install -y stockfish   或放一个 stockfish 到 PATH"
  warn "  （不影响页面渲染与开局默写）"
else
  say "Stockfish: $SF ($("$SF" --help 2>&1 | head -1 | cut -c1-60))"
fi

# ---------- 3. 起 app.py ----------
healthy() { curl -s -o /dev/null -w '%{http_code}' --max-time 3 "http://127.0.0.1:$PORT/?view=train" 2>/dev/null | grep -q '^200$'; }

if [ "$RESTART" = "1" ]; then
  say "--restart: 停止旧的 app.py / bridge.py"
  pkill -f "$PLAY/app.py" 2>/dev/null || true
  pkill -f "$PLAY/bridge.py" 2>/dev/null || true
  pkill -f "python.* app\.py" 2>/dev/null || true
  pkill -f "python.* bridge\.py" 2>/dev/null || true
  sleep 1
fi

if healthy; then
  say "端口 $PORT 上已有健康实例，复用"
else
  if ss -tln 2>/dev/null | grep -q ":$PORT "; then
    die "端口 $PORT 被其他进程占用，请换端口: PORT=9000 bash scripts/dev_up.sh"
  fi
  say "启动 app.py（0.0.0.0:$PORT）…"
  ( cd "$PLAY" && PORT="$PORT" setsid "$PY" app.py >"$ROOT/.run/app.log" 2>&1 & )
  for i in $(seq 1 40); do
    healthy && break
    sleep 0.5
  done
  if ! healthy; then
    echo "----- .run/app.log 末尾 -----" >&2
    tail -30 "$ROOT/.run/app.log" >&2
    die "app.py 未能在 20s 内就绪"
  fi
  say "app.py 就绪: http://127.0.0.1:$PORT/"
fi

# ---------- 4. bridge（可选） ----------
if [ "$WITH_BRIDGE" = "1" ] || [ "${FEED:-0}" = "1" ]; then
  if pgrep -f "$PLAY/bridge.py" >/dev/null 2>&1 || pgrep -f "python.* bridge\.py" >/dev/null 2>&1; then
    say "bridge.py 已在运行，跳过"
  else
    say "启动 bridge.py（观战桥 → play/live_feed.jsonl）…"
    ( cd "$PLAY" && setsid "$PY" bridge.py >"$ROOT/.run/bridge.log" 2>&1 & )
    sleep 2
    if pgrep -f "bridge\.py" >/dev/null 2>&1; then
      say "bridge.py 就绪，feed: play/live_feed.jsonl"
    else
      warn "bridge.py 似乎未启动，见 .run/bridge.log"
      tail -10 "$ROOT/.run/bridge.log" 2>/dev/null || true
    fi
  fi
fi

cat <<EOF

────────────────────────────────────────
  就绪
  对弈    http://127.0.0.1:$PORT/
  练习    http://127.0.0.1:$PORT/?view=train
  解说    http://127.0.0.1:$PORT/?view=narrate
  日志    $ROOT/.run/app.log
$( [ "$WITH_BRIDGE" = "1" ] && echo "  feed    $ROOT/play/live_feed.jsonl" )
────────────────────────────────────────
停止: pkill -f 'app.py' ; pkill -f 'bridge.py'
重启: bash scripts/dev_up.sh --restart$( [ "$WITH_BRIDGE" = "1" ] && echo ' --with-bridge' )
EOF
