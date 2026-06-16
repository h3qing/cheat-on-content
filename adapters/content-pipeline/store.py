"""Supabase I/O for the content pipeline: source_signals (discovered ideas) + post_ideas (drafts).

Claude supplies the judgment (web-search relevance scoring, voice drafting); this module just
does the reads/writes. Reuses .cheat-secrets.json (CHEAT_PROJECT_ROOT or cwd), same as the
linkedin-session adapter. Run with that venv's python.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path


def _secrets() -> dict:
    root = os.environ.get("CHEAT_PROJECT_ROOT") or str(Path.cwd())
    p = Path(root).expanduser() / ".cheat-secrets.json"
    if not p.is_file():
        raise SystemExit(f"❌ missing {p} (set CHEAT_PROJECT_ROOT to your linkedin-tracker dir)")
    return json.loads(p.read_text(encoding="utf-8"))


def _client():
    try:
        from supabase import create_client
    except ImportError:
        raise SystemExit("❌ supabase not installed — pip install supabase")
    s = _secrets()
    return create_client(s["supabase_url"], s["supabase_service_key"])


def _existing_urls(client) -> set:
    rows = client.table("source_signals").select("url").execute().data or []
    return {r.get("url") for r in rows if r.get("url")}


def insert_signals(signals: list[dict]) -> dict:
    """Append discovered signals to source_signals, deduped by url."""
    client = _client()
    seen = _existing_urls(client)
    fresh = [s for s in signals if s.get("url") and s["url"] not in seen]
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    rows = [
        {
            "captured_at": now,
            "source_type": s.get("source_type", "news"),
            "source_name": s.get("source_name", ""),
            "title": s.get("title", ""),
            "summary": s.get("summary", ""),
            "url": s.get("url", ""),
            "theme": s.get("theme", ""),
            "relevance_score": str(s.get("relevance_score", "")),
        }
        for s in fresh
    ]
    inserted = client.table("source_signals").insert(rows).execute().data if rows else []
    return {"inserted": len(inserted or []), "skipped_dupes": len(signals) - len(fresh)}


def insert_idea(idea: dict) -> dict:
    """Append one draft to post_ideas (status defaults to 'draft')."""
    row = {
        "topic": idea.get("topic", ""),
        "angle": idea.get("angle", ""),
        "hook": idea.get("hook", ""),
        "body": idea.get("body", ""),
        "format": idea.get("format", "text"),
        "status": idea.get("status", "draft"),
        "predicted_engagement": idea.get("predicted_engagement"),
        "notes": idea.get("notes"),
    }
    data = _client().table("post_ideas").insert(row).execute().data
    return {"id": (data or [{}])[0].get("id"), "topic": row["topic"]}


def list_signals(limit: int = 25) -> list[dict]:
    rows = (
        _client()
        .table("source_signals")
        .select("id,relevance_score,theme,title,source_name")
        .limit(limit)
        .execute()
        .data
        or []
    )
    rows.sort(key=lambda r: float(r.get("relevance_score") or 0), reverse=True)
    return rows


def list_ideas(limit: int = 25) -> list[dict]:
    return (
        _client()
        .table("post_ideas")
        .select("id,status,topic,hook")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
