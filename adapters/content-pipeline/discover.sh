#!/usr/bin/env bash
#
# Scheduled SIGNAL DISCOVERY for Megaphone — a headless `claude -p` pass that web-searches +
# scans X for fresh, on-pillar content and writes new rows to Supabase `source_signals`.
#
# Unlike the capture cron (linkedin-session/daily.sh), discovery needs JUDGMENT (relevance +
# voice-fit scoring), so it runs Claude. Reads discover-prompt.md. Records the run to `job_runs`.
#
# SAFETY: NO --dangerously-skip-permissions, and Bash is locked to ONLY the two discovery
# scripts (pipeline.py, x-discover crawler.py) via the venv python — NOT arbitrary python, so
# no `python -c "..."` and no other binaries. It ingests untrusted web/social content, but an
# injected shell command, a `-c` code string, a secret read, or any other action is DENIED by
# the harness. Residual risk: a stray low-value signal row (curate via ☆ / relevance).
#
# Scheduled via launchd (com.megaphone.discover, Mon/Wed/Fri 08:00). Manual:
#   CHEAT_PROJECT_ROOT=$HOME/linkedin-tracker bash discover.sh
set -uo pipefail

ROOT="${CHEAT_PROJECT_ROOT:-$HOME/linkedin-tracker}"
export CHEAT_PROJECT_ROOT="$ROOT"   # inherited by the venv python children (finds .cheat-secrets.json + .auth-x)
ADAPTER="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
CLAUDE="$(command -v claude || echo "$HOME/.local/bin/claude")"

PY="$HOME/linkedin-tracker/.venv/bin/python"
PIPE="/Users/heqinghuang/Media/cheat-on-content/adapters/content-pipeline/pipeline.py"
XDISC="/Users/heqinghuang/Media/cheat-on-content/adapters/trend-sources/x-discover/crawler.py"

if [[ ! -x "$CLAUDE" ]]; then echo "❌ claude CLI not found ($CLAUDE)" >&2; exit 2; fi

echo "===== $(date '+%Y-%m-%d %H:%M:%S') discover ====="
START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
OUT="$("$CLAUDE" -p "$(cat "$ADAPTER/discover-prompt.md")" \
  --model claude-sonnet-4-6 \
  --output-format text \
  --allowedTools \
    "WebSearch" \
    "WebFetch" \
    "Write(/tmp/new-signals.json)" \
    "Read($HOME/linkedin-tracker/voice-profile.md)" \
    "Read($HOME/linkedin-tracker/rubric.md)" \
    "Bash($PY $PIPE:*)" \
    "Bash($PY $XDISC:*)" 2>&1)"
RC=$?
printf '%s\n' "$OUT"
echo "===== done ====="

# observability → job_runs (best-effort; never fails the run)
STATUS=$([ "$RC" -eq 0 ] && echo success || echo failed)
SUM="$(printf '%s\n' "$OUT" | grep -iE 'inserted|skipped|signal|error|denied|❌|⚠' | tail -1)"
[ -z "$SUM" ] && SUM="$(printf '%s\n' "$OUT" | tail -1)"
"$PY" "$ADAPTER/joblog.py" discover "$STATUS" "$START" "$SUM" "$RC" 2>/dev/null || true

# seed the calendar with post suggestions for upcoming posting-days (deterministic, no Claude;
# fills only empty future Tue/Thu slots from the freshly-discovered signals + evergreen pillars)
echo "===== $(date '+%Y-%m-%d %H:%M:%S') seed-calendar ====="
SEED_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
SEED_OUT="$("$PY" "$ADAPTER/seed_calendar.py" 2>&1)"; SEED_RC=$?
printf '%s\n' "$SEED_OUT"
echo "===== done ====="
SEED_STATUS=$([ "$SEED_RC" -eq 0 ] && echo success || echo failed)
SEED_SUM="$(printf '%s\n' "$SEED_OUT" | grep -iE 'inserted|seeding|nothing|full|error' | tail -1)"
[ -z "$SEED_SUM" ] && SEED_SUM="$(printf '%s\n' "$SEED_OUT" | tail -1)"
"$PY" "$ADAPTER/joblog.py" seed-calendar "$SEED_STATUS" "$SEED_START" "$SEED_SUM" "$SEED_RC" 2>/dev/null || true
