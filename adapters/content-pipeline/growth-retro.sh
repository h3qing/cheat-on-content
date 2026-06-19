#!/usr/bin/env bash
#
# Weekly GROWTH RETRO for Megaphone — a headless `claude -p` that fuses fresh external LinkedIn
# growth research with own-data analysis into the `growth_tactics` playbook + a `growth_retros`
# digest. The distribution-mechanics layer (timing / comments / format / cadence). Reads
# growth-retro-prompt.md. Records the run to `job_runs`.
#
# SAFETY: NO --dangerously-skip-permissions. Bash is locked to ONLY growth_pipeline.py (the venv
# python) — no arbitrary python/-c, no other binaries. It ingests untrusted web content, but an
# injected shell command is DENIED by the harness (same model as discover.sh).
#
# Scheduled via launchd (com.megaphone.growth, Mon 07:30). Manual:
#   CHEAT_PROJECT_ROOT=$HOME/linkedin-tracker bash growth-retro.sh
set -uo pipefail

ROOT="${CHEAT_PROJECT_ROOT:-$HOME/linkedin-tracker}"
export CHEAT_PROJECT_ROOT="$ROOT"
ADAPTER="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
CLAUDE="$(command -v claude || echo "$HOME/.local/bin/claude")"
PY="$HOME/linkedin-tracker/.venv/bin/python"
GP="/Users/heqinghuang/Media/cheat-on-content/adapters/content-pipeline/growth_pipeline.py"

if [[ ! -x "$CLAUDE" ]]; then echo "❌ claude CLI not found ($CLAUDE)" >&2; exit 2; fi

echo "===== $(date '+%Y-%m-%d %H:%M:%S') growth-retro ====="
START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
OUT="$("$CLAUDE" -p "$(cat "$ADAPTER/growth-retro-prompt.md")" \
  --model claude-sonnet-4-6 \
  --output-format text \
  --allowedTools \
    "WebSearch" \
    "WebFetch" \
    "Write(/tmp/growth-tactics.json)" \
    "Write(/tmp/growth-retro.json)" \
    "Read($HOME/linkedin-tracker/voice-profile.md)" \
    "Read($HOME/linkedin-tracker/rubric.md)" \
    "Bash($PY $GP:*)" 2>&1)"
RC=$?
printf '%s\n' "$OUT"
echo "===== done ====="

STATUS=$([ "$RC" -eq 0 ] && echo success || echo failed)
SUM="$(printf '%s\n' "$OUT" | grep -iE 'tactic|retro|upsert|error|denied' | tail -1)"
[ -z "$SUM" ] && SUM="$(printf '%s\n' "$OUT" | tail -1)"
"$PY" "$ADAPTER/joblog.py" growth "$STATUS" "$START" "$SUM" "$RC" 2>/dev/null || true
