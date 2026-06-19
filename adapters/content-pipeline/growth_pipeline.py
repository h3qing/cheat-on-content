"""Growth-retro Supabase I/O for Megaphone — own-data engagement-MECHANICS analysis + the
`growth_tactics` playbook + `growth_retros` digests. Reuses the content-pipeline client.

    analyze                 # print own-data findings as JSON (timing PT, comment-reply, follower-drivers, format)
    upsert-tactics <json>   # [{category,title,recommendation,evidence,confidence,basis,status}, ...] upsert by title
    add-retro <json>        # {week_of, headline, body, changes}
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from collections import defaultdict

import store  # reuse the content-pipeline Supabase client

try:
    from zoneinfo import ZoneInfo
    PT = ZoneInfo("America/Los_Angeles")  # audience tz (SF Bay) — when to post is about the AUDIENCE
except Exception:
    PT = dt.timezone(dt.timedelta(hours=-7))  # PDT fallback if tzdata missing

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _avg(xs):
    return round(sum(xs) / len(xs)) if xs else None


def analyze() -> dict:
    c = store._client()
    posts = c.table("posts").select("id,posted_at,format,is_opinionated,topic,content").execute().data or []
    eng = (
        c.table("engagement_snapshots")
        .select("post_id,impressions,reactions,comments,reposts,raw,captured_at")
        .order("captured_at", desc=True)
        .execute()
        .data
        or []
    )
    comments = c.table("post_comments").select("post_id,is_author_reply,user_has_replied").execute().data or []

    latest: dict = {}
    for e in eng:
        if e["post_id"] not in latest and e.get("impressions") is not None:
            latest[e["post_id"]] = e

    def impr(pid):
        e = latest.get(pid)
        return e["impressions"] if e else None

    def eng_total(pid):
        e = latest.get(pid)
        return (e.get("reactions") or 0) + (e.get("comments") or 0) + (e.get("reposts") or 0) if e else None

    def foll(pid):
        e = latest.get(pid) or {}
        raw = e.get("raw") if isinstance(e.get("raw"), dict) else {}
        m = (raw or {}).get("metrics") or {}
        return m.get("followers_from_post")

    # timing (in audience tz)
    by_dow, by_hour = defaultdict(list), defaultdict(list)
    for p in posts:
        if not p.get("posted_at"):
            continue
        i = impr(p["id"])
        if i is None:
            continue
        t = dt.datetime.fromisoformat(p["posted_at"].replace("Z", "+00:00")).astimezone(PT)
        by_dow[DOW[t.weekday()]].append(i)
        by_hour[t.hour].append(i)
    dow_avg = {d: _avg(v) for d, v in by_dow.items()}
    hour_avg = {h: _avg(v) for h, v in by_hour.items()}
    best_day = max(dow_avg, key=lambda d: dow_avg[d] or 0) if dow_avg else None
    best_hours = sorted(hour_avg, key=lambda h: hour_avg[h] or 0, reverse=True)[:3]

    # comment-reply behaviour
    replied = {cm["post_id"] for cm in comments if cm.get("is_author_reply") or cm.get("user_has_replied")}
    with_reply = [eng_total(p["id"]) for p in posts if p["id"] in replied and eng_total(p["id"]) is not None]
    without_reply = [eng_total(p["id"]) for p in posts if p["id"] not in replied and eng_total(p["id"]) is not None]

    # follower drivers
    drivers = sorted(((p, foll(p["id"])) for p in posts if foll(p["id"])), key=lambda x: x[1] or 0, reverse=True)[:5]

    # format / opinionated splits
    by_fmt, by_op = defaultdict(list), defaultdict(list)
    for p in posts:
        i = impr(p["id"])
        if i is None:
            continue
        by_fmt[p.get("format") or "text"].append(i)
        by_op["opinionated" if p.get("is_opinionated") else "neutral"].append(i)

    return {
        "n_posts_analyzed": len([p for p in posts if impr(p["id"]) is not None]),
        "timing_pt": {
            "avg_impressions_by_dow": dow_avg,
            "best_day": best_day,
            "avg_impressions_by_hour": {str(h): hour_avg[h] for h in hour_avg},
            "best_hours_pt": best_hours,
        },
        "comments": {
            "posts_with_author_reply": len(with_reply),
            "avg_engagement_with_reply": _avg(with_reply),
            "avg_engagement_without_reply": _avg(without_reply),
        },
        "follower_drivers": [
            {"topic": p.get("topic"), "format": p.get("format"), "followers_from_post": f, "hook": (p.get("content") or "")[:80]}
            for p, f in drivers
        ],
        "format_splits": {
            "avg_impressions_by_format": {k: _avg(v) for k, v in by_fmt.items()},
            "avg_impressions_by_opinionated": {k: _avg(v) for k, v in by_op.items()},
        },
    }


def upsert_tactics(tactics: list) -> dict:
    c = store._client()
    existing = {t["title"]: t["id"] for t in (c.table("growth_tactics").select("id,title").execute().data or [])}
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    ins = upd = 0
    for t in tactics:
        row = {k: t.get(k) for k in ("category", "title", "recommendation", "evidence", "confidence", "basis")}
        row["status"] = t.get("status") or "active"
        row["updated_at"] = now
        if t.get("title") in existing:
            c.table("growth_tactics").update(row).eq("id", existing[t["title"]]).execute()
            upd += 1
        else:
            c.table("growth_tactics").insert(row).execute()
            ins += 1
    return {"inserted": ins, "updated": upd}


def add_retro(r: dict) -> dict:
    c = store._client()
    row = {
        "week_of": r.get("week_of"),
        "headline": r.get("headline"),
        "body": r.get("body"),
        "changes": r.get("changes"),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    c.table("growth_retros").insert(row).execute()
    return {"ok": True, "week_of": row["week_of"]}


def _load(p):
    return json.loads(sys.stdin.read() if p == "-" else open(p, encoding="utf-8").read())


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "analyze":
        print(json.dumps(analyze(), ensure_ascii=False, indent=2))
    elif cmd == "upsert-tactics":
        print(json.dumps(upsert_tactics(_load(sys.argv[2])), ensure_ascii=False))
    elif cmd == "add-retro":
        print(json.dumps(add_retro(_load(sys.argv[2])), ensure_ascii=False))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
