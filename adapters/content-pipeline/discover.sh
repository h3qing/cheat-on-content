#!/usr/bin/env bash
#
# Scheduled SIGNAL DISCOVERY for Megaphone — a headless `claude -p` pass that web-searches +
# scans X for fresh, on-pillar content and writes new rows to Supabase `source_signals`.
#
# Unlike the capture cron (linkedin-session/daily.sh), discovery needs JUDGMENT (relevance +
# voice-fit scoring), so it runs Claude. Reads discover-prompt.md.
#
# SAFETY: NO --dangerously-skip-permissions, and Bash is locked to ONLY the two discovery
# scripts (pipeline.py, x-discover crawler.py) via the venv python — NOT arbitrary python, so
# no `python -c "..."` and no other binaries. It ingests untrusted web/social content, but an
# injected shell command, a `-c` code string, a secret read, or any other action is DENIED by
# the harness. Residual risk: a stray low-value signal row (curate via ☆ / relevance) — no code
# execution, no secret exfiltration.
#
# crontab (every 2 days, 08:00 local):
#   0 8 */2 * * CHEAT_PROJECT_ROOT=$HOME/linkedin-tracker bash <adapter>/discover.sh >> $HOME/linkedin-tracker/discover.log 2>&1
set -uo pipefail

ROOT="${CHEAT_PROJECT_ROOT:-$HOME/linkedin-tracker}"
export CHEAT_PROJECT_ROOT="$ROOT"   # inherited by the venv python children (finds .cheat-secrets.json + .auth-x)
CLAUDE="$(command -v claude || echo "$HOME/.local/bin/claude")"

PY="$HOME/linkedin-tracker/.venv/bin/python"
PIPE="/Users/heqinghuang/Media/cheat-on-content/adapters/content-pipeline/pipeline.py"
XDISC="/Users/heqinghuang/Media/cheat-on-content/adapters/trend-sources/x-discover/crawler.py"

if [[ ! -x "$CLAUDE" ]]; then echo "❌ claude CLI not found ($CLAUDE)" >&2; exit 2; fi

echo "===== $(date '+%Y-%m-%d %H:%M:%S') discover ====="
"$CLAUDE" -p "$(cat "$(dirname -- "${BASH_SOURCE[0]}")/discover-prompt.md")" \
  --model claude-sonnet-4-6 \
  --output-format text \
  --allowedTools \
    "WebSearch" \
    "WebFetch" \
    "Write(/tmp/new-signals.json)" \
    "Read($HOME/linkedin-tracker/voice-profile.md)" \
    "Read($HOME/linkedin-tracker/rubric.md)" \
    "Bash($PY $PIPE:*)" \
    "Bash($PY $XDISC:*)"
echo "===== done ====="
