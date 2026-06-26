#!/usr/bin/env bash
#
# linkedin-session adapter wrapper（领英单帖分析）
#
# Called by /cheat-retro when state.data_collection=adapter and platform=linkedin.
#
# Usage:
#   bash run.sh <activity_id_or_permalink> <video_folder> [<script_path>]
#
# Examples:
#   bash run.sh 7341234567890123456 ~/my-channel/videos/2026-05-04_li_停止期待
#   bash run.sh 'https://www.linkedin.com/feed/update/urn:li:activity:7341234567890123456/' <folder>
#
# 第一个参数原样传给 crawler——它会把 permalink / share urn / 裸 id 归一成 activity id
# （share→activity 需联网解析，见 crawler.normalize_to_activity_id）。
#
# Output: writes report.md INTO the video_folder.
# Exit codes:
#   0 = success (report.md written)
#   1 = login expired or required
#   2 = adapter dependency missing (playwright not installed)
#   3 = other failure (network, parse error, can't resolve activity id, etc.)

set -uo pipefail

ACTIVITY_REF="${1:-}"
VIDEO_FOLDER="${2:-}"
SCRIPT_PATH="${3:-}"

if [[ -z "$ACTIVITY_REF" || -z "$VIDEO_FOLDER" ]]; then
  echo "Usage: bash run.sh <activity_id_or_permalink> <video_folder> [<script_path>]" >&2
  exit 3
fi

# Resolve adapter source dir (where this script lives)
ADAPTER_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Find Python — prefer venv in user's project root if exists
PYTHON=""
# Walk up from VIDEO_FOLDER to find project root (.cheat-state.json)
PROJECT_ROOT="$( realpath "$VIDEO_FOLDER" )"
while [[ "$PROJECT_ROOT" != "/" && ! -f "$PROJECT_ROOT/.cheat-state.json" ]]; do
  PROJECT_ROOT="$( dirname "$PROJECT_ROOT" )"
done
if [[ ! -f "$PROJECT_ROOT/.cheat-state.json" ]]; then
  echo "❌ Cannot find project root (.cheat-state.json) from $VIDEO_FOLDER" >&2
  exit 3
fi
if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  PYTHON="$PROJECT_ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
else
  echo "❌ python3 not found — install Python 3.11+ first" >&2
  exit 2
fi

# Verify playwright is installed
if ! "$PYTHON" -c "import playwright" 2>/dev/null; then
  cat >&2 <<EOF
❌ playwright not installed.

Install in your project venv:
  cd "$PROJECT_ROOT"
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r "$ADAPTER_DIR/requirements.txt"
  playwright install chromium

Then re-run /cheat-retro.
EOF
  exit 2
fi

# Verify auth dir exists in project root (cookie persistence — 独立于 douyin 的 .auth/)
if [[ ! -d "$PROJECT_ROOT/.auth-linkedin" ]]; then
  cat >&2 <<EOF
❌ Not logged in to LinkedIn.

First-time login (one-shot):
  cd "$PROJECT_ROOT"
  source .venv/bin/activate
  $PYTHON "$ADAPTER_DIR/crawler.py" login

A Chromium window will pop up — log in to LinkedIn.
Cookie will be saved to .auth-linkedin/ for future runs.
EOF
  exit 1
fi

# Make sure video_folder exists
mkdir -p "$VIDEO_FOLDER"

# Resolve script path (optional — passed through to renderer for the 原始稿子 section)
SCRIPT_ARG=""
if [[ -n "$SCRIPT_PATH" && -f "$SCRIPT_PATH" ]]; then
  SCRIPT_ARG="$SCRIPT_PATH"
fi

# Run from PROJECT_ROOT so paths.py resolves .auth-linkedin/ + .cheat-cache/ there.
# (renderer.py is invoked by absolute path, so its dir is on sys.path → crawler/extract/paths import fine.)
cd "$PROJECT_ROOT"
export CHEAT_PROJECT_ROOT="$PROJECT_ROOT"

# renderer.py fetches (crawler normalizes ref → activity id) + writes report.md straight into
# video_folder. No auto-named-folder dance like douyin/xhs: LinkedIn analytics has no post title.
echo "[linkedin-session] fetching $ACTIVITY_REF into $VIDEO_FOLDER"
if [[ -n "$SCRIPT_ARG" ]]; then
  "$PYTHON" "$ADAPTER_DIR/renderer.py" "$ACTIVITY_REF" "$VIDEO_FOLDER" "$SCRIPT_ARG"
else
  "$PYTHON" "$ADAPTER_DIR/renderer.py" "$ACTIVITY_REF" "$VIDEO_FOLDER"
fi

if [[ ! -f "$VIDEO_FOLDER/report.md" ]]; then
  echo "❌ report.md not produced — see renderer.py output above for details" >&2
  exit 3
fi

echo "✅ report.md written to $VIDEO_FOLDER/report.md"
exit 0
