#!/usr/bin/env bash
#
# linkedin-session 每日 routine：创作者面板 + 最新 N 帖互动 → Supabase。
#
# crontab（每天 9:00）：
#   0 9 * * * CHEAT_PROJECT_ROOT=$HOME/linkedin-tracker bash <adapter>/daily.sh >> $HOME/linkedin-tracker/cron.log 2>&1
#
# 帖数用 LINKEDIN_POSTS_LIMIT 覆盖（默认 10，只扫最新的——老帖互动已稳定）。
set -uo pipefail

ROOT="${CHEAT_PROJECT_ROOT:-$HOME/linkedin-tracker}"
export CHEAT_PROJECT_ROOT="$ROOT"
ADAPTER="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PY="$ROOT/.venv/bin/python"
LIMIT="${LINKEDIN_POSTS_LIMIT:-10}"

if [[ ! -x "$PY" ]]; then
  echo "❌ 找不到 venv python：$PY（先按 README 装环境）" >&2
  exit 2
fi

JOBLOG="/Users/heqinghuang/Media/cheat-on-content/adapters/content-pipeline/joblog.py"
START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "===== $(date '+%Y-%m-%d %H:%M:%S') ====="
PULL_OUT="$( "$PY" "$ADAPTER/review.py" pull 2>&1 )"; PULL_RC=$?
POSTS_OUT="$( "$PY" "$ADAPTER/review.py" posts --limit="$LIMIT" 2>&1 )"; POSTS_RC=$?
OUT="$PULL_OUT"$'\n'"$POSTS_OUT"
RC=$(( PULL_RC != 0 ? PULL_RC : POSTS_RC ))
printf '%s\n' "$OUT"
echo "===== done ====="

# observability → job_runs (best-effort; never fails the run)
STATUS=$([ "$RC" -eq 0 ] && echo success || echo failed)
SUM="$(printf '%s\n' "$OUT" | grep -iE 'INSERT|impressions|error|❌|⚠' | tail -1)"
[ -z "$SUM" ] && SUM="pull + posts (limit $LIMIT)"
"$PY" "$JOBLOG" capture "$STATUS" "$START" "$SUM" "$RC" 2>/dev/null || true
