"""Seed the calendar with lightweight post SUGGESTIONS for the upcoming weeks.

Each run, fill empty future posting-days (Tue/Thu) over the next 4 weeks with a draft
`post_ideas` row seeded from the top fresh, unused signals (evergreen pillars as fallback).
These are SEEDS: a topic + angle + a brief, no finished hook/body, so the calendar shows a
plan ahead of time and you (or Claude) write the actual post. Idempotent: only fills slots
that are still empty, so running it every cron pass just tops up the schedule.

    python seed_calendar.py [--dry-run] [--weeks N]

Deterministic (no LLM). Mirrors the cockpit's evergreen pillars (megaphone lib/evergreen.ts)
and posting cadence (Tue/Thu). Keep those two in sync.
"""
from __future__ import annotations

import argparse
import datetime as dt

import store

WEEKS = 4
POSTING_DAYS = (1, 3)  # Mon=0 .. Sun=6  ->  Tue, Thu  (mirrors cockpit POSTING_DAYS)
SIGNAL_MAX_AGE_DAYS = 30

# Mirrors megaphone lib/evergreen.ts EVERGREEN_PILLARS (kept em-dash-free so seeds don't
# trip the draft em-dash flag).
EVERGREEN_PILLARS = [
    ("Operator lesson", "Something you learned building agents at Scale that most teams get wrong."),
    ("Contrarian take", "A widely-held AI belief you think is wrong, and the evidence."),
    ("Framework", "A repeatable mental model your audience can apply this week."),
    ("Build in public", "What changed in your workflow, stack, or fleet since last week."),
    ("Teardown", "How a real agent system works under the hood. The part the demo skips."),
]


def _iso(d: dt.date) -> str:
    return d.isoformat()


def upcoming_posting_days(today: dt.date, weeks: int) -> list[str]:
    out = []
    for i in range(weeks * 7):
        d = today + dt.timedelta(days=i)
        if d.weekday() in POSTING_DAYS:
            out.append(_iso(d))
    return out


def _seed_from_signal(date: str, s: dict) -> dict:
    angle = (s.get("summary") or s.get("title") or "").strip()
    src = (s.get("source_name") or "signal").strip()
    url = (s.get("url") or "").strip()
    body = (
        f"Auto-suggested for {date}. Replace with your post.\n\n"
        f"Angle: {angle}\nSource: {src}" + (f" ({url})" if url else "")
    )
    return {
        "topic": (s.get("theme") or "AI").strip(),
        "angle": angle,
        "hook": (s.get("title") or "").strip(),
        "body": body,
        "format": "text",
        "status": "draft",
        "source_signal_ids": [s["id"]],
        "scheduled_for": date,
        "notes": None,
    }


def _seed_from_pillar(date: str, label: str, prompt: str) -> dict:
    body = (
        f"Auto-suggested for {date}. Replace with your post.\n\n"
        f"Evergreen pillar: {label}.\n{prompt}"
    )
    return {
        "topic": label,
        "angle": prompt,
        "hook": "",
        "body": body,
        "format": "text",
        "status": "draft",
        "source_signal_ids": None,
        "scheduled_for": date,
        "notes": None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--weeks", type=int, default=WEEKS)
    args = ap.parse_args()

    c = store._client()
    today = dt.datetime.now(dt.timezone.utc).date()
    slots = upcoming_posting_days(today, args.weeks)
    if not slots:
        print("no upcoming posting days in window")
        return
    lo, hi = slots[0], slots[-1]

    ideas = c.table("post_ideas").select("id,status,scheduled_for,source_signal_ids").execute().data or []
    # A slot is occupied by any non-rejected scheduled draft (the calendar hides rejected).
    occupied = {
        i["scheduled_for"]
        for i in ideas
        if i.get("scheduled_for") and (i.get("status") or "draft") != "rejected"
    }
    used_signal_ids = {sid for i in ideas for sid in (i.get("source_signal_ids") or [])}

    empty = [s for s in slots if s not in occupied]
    if not empty:
        print(f"calendar already full for {lo}..{hi} ({len(slots)} posting days) — nothing to seed")
        return

    cutoff = _iso(today - dt.timedelta(days=SIGNAL_MAX_AGE_DAYS))
    sigs = (
        c.table("source_signals")
        .select("id,relevance_score,theme,title,summary,url,source_name,captured_at")
        .gte("captured_at", cutoff)
        .execute()
        .data
        or []
    )
    sigs = [s for s in sigs if s["id"] not in used_signal_ids]
    sigs.sort(key=lambda s: float(s.get("relevance_score") or 0), reverse=True)

    rows, plan = [], []
    si = ei = 0
    for date in empty:
        if si < len(sigs):
            s = sigs[si]; si += 1
            rows.append(_seed_from_signal(date, s))
            plan.append(f"  {date}  signal #{s['id']} (rel {s.get('relevance_score')}): {(s.get('title') or '')[:56]}")
        else:
            label, prompt = EVERGREEN_PILLARS[ei % len(EVERGREEN_PILLARS)]; ei += 1
            rows.append(_seed_from_pillar(date, label, prompt))
            plan.append(f"  {date}  evergreen: {label}")

    print(
        f"window {lo}..{hi}: {len(slots)} posting days, {len(slots) - len(empty)} filled, "
        f"{len(empty)} empty -> seeding {len(rows)} ({si} from signals, {ei} evergreen)"
    )
    for line in plan:
        print(line)

    if args.dry_run:
        print("[dry-run] no rows written")
        return
    inserted = c.table("post_ideas").insert(rows).execute().data if rows else []
    print(f"inserted {len(inserted or [])} suggestion drafts")


if __name__ == "__main__":
    main()
