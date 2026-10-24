#!/usr/bin/env bash
# 把工作区源码副本同步到两处技能注册目录，使新会话能发现最新版技能。
# 用法: bash /workspace/chess-coach/scripts/sync_skill.sh
set -euo pipefail

SRC="/workspace/chess-coach"
PROJECT_DIR="/workspace/.codebuddy/skills/chess-coach"
USER_DIR="/root/.codebuddy/skills/chess-coach"

[ -d "$SRC" ] || { echo "[ERR] 源码目录不存在: $SRC"; exit 1; }

for dst in "$PROJECT_DIR" "$USER_DIR"; do
  mkdir -p "$(dirname "$dst")"
  # 用 rsync 语义手工实现：整目录覆盖，但排除运行时产物
  mkdir -p "$dst"
  ( cd "$SRC" && tar -cf - \
      --exclude='__pycache__' \
      --exclude='*.pyc' \
      --exclude='live_feed.jsonl' \
      . ) | ( cd "$dst" && tar -xf - )
  echo "[OK] $dst"
done

echo "--- 校验 ---"
python3 - <<'PY'
import yaml, hashlib, pathlib
paths = [
    "/workspace/chess-coach/SKILL.md",
    "/workspace/.codebuddy/skills/chess-coach/SKILL.md",
    "/root/.codebuddy/skills/chess-coach/SKILL.md",
]
for p in paths:
    f = pathlib.Path(p)
    if not f.is_file():
        print(f"  MISSING {p}")
        continue
    s = f.read_text(encoding="utf-8")
    d = yaml.safe_load(s.split("---", 2)[1])
    h = hashlib.md5(s.encode()).hexdigest()[:8]
    print(f"  {h}  name={d.get('name'):12s} desc={len(d.get('description','')):4d}字  {p}")
PY
