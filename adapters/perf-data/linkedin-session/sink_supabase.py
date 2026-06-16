"""把抽取结果写入用户现有的 Supabase 表。

凭据从项目根的 .cheat-secrets.json 读（已 gitignore）：
    {"supabase_url": "https://xxxx.supabase.co", "supabase_service_key": "sb_secret_... 或 service_role JWT"}

创作者面板 → 现有表 profile_stats（append 一行快照，匹配其 captured_at 时间序列）。
落库走 supabase-py（PostgREST），不依赖 Supabase MCP。
"""
from __future__ import annotations

import datetime as dt
import json

from paths import secrets_file


def _load_secrets() -> dict:
    p = secrets_file()
    if not p.is_file():
        raise SystemExit(
            f"❌ 缺 {p}\n   放：{{\"supabase_url\": \"https://xxxx.supabase.co\", "
            f"\"supabase_service_key\": \"sb_secret_...\"}}"
        )
    return json.loads(p.read_text(encoding="utf-8"))


def _client():
    try:
        from supabase import create_client
    except ImportError:
        raise SystemExit("❌ 未装 supabase。跑：pip install supabase>=2.4")
    s = _load_secrets()
    url, key = s.get("supabase_url"), s.get("supabase_service_key")
    if not url or not key:
        raise SystemExit("❌ .cheat-secrets.json 需要 supabase_url + supabase_service_key")
    return create_client(url, key)


def build_profile_stats_row(result: dict, captured_at: str | None = None) -> dict:
    """创作者面板抽取结果 → profile_stats 行。纯函数，可测。

    growth_pct 列留空：方向（▲/▼）在 DOM 里是图标，文本拿不到；趋势从 captured_at 序列自己算。
    connections_label 不在面板页，留空。
    """
    m = result.get("metrics") or {}
    return {
        "captured_at": captured_at or dt.datetime.now(dt.timezone.utc).isoformat(),
        "followers": m.get("followers"),
        "profile_viewers_90d": m.get("profile_viewers"),
        "post_impressions_7d": m.get("post_impressions"),
        "search_appearances_prev_week": m.get("search_appearances"),
        "raw": result,
    }


def insert_profile_stats(result: dict) -> dict:
    """append 一行到 profile_stats。"""
    row = build_profile_stats_row(result)
    client = _client()
    resp = client.table("profile_stats").insert(row).execute()
    data = resp.data[0] if resp.data else {}
    return {"id": data.get("id"), "row": row, "data": resp.data}


# ---- 单帖分析 → engagement_snapshots ----

def fetch_linkedin_posts(client, limit: int | None = None) -> list:
    """从 posts 表取 linkedin 帖（id / external_id / posted_at），按发布时间倒序。"""
    q = (client.table("posts")
         .select("id,external_id,posted_at")
         .eq("platform", "linkedin")
         .order("posted_at", desc=True))
    if limit:
        q = q.limit(limit)
    return q.execute().data or []


def build_engagement_row(post_id: int, result: dict, posted_at: str | None = None,
                         captured_at: str | None = None) -> dict:
    """单帖分析结果 → engagement_snapshots 行。纯函数，可测。

    impressions 即 Cowork 留空的那列。reach/saves/sends/profile_views 等全在 raw 里。
    """
    m = result.get("metrics") or {}
    cap = captured_at or dt.datetime.now(dt.timezone.utc).isoformat()
    minutes = None
    if posted_at:
        try:
            p = dt.datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
            c = dt.datetime.fromisoformat(cap.replace("Z", "+00:00"))
            minutes = int((c - p).total_seconds() // 60)
        except ValueError:
            minutes = None
    return {
        "post_id": post_id,
        "captured_at": cap,
        "impressions": m.get("impressions"),
        "reactions": m.get("reactions"),
        "comments": m.get("comments"),
        "reposts": m.get("reposts"),
        "raw": result,
        "capture_phase": "analytics",
        "minutes_since_post": minutes,
    }


def insert_engagement_rows(client, rows: list) -> list:
    """批量 append 到 engagement_snapshots。"""
    if not rows:
        return []
    return client.table("engagement_snapshots").insert(rows).execute().data or []


# ---- 受众分析 → audience_snapshots ----

def build_audience_row(result: dict, captured_at: str | None = None) -> dict:
    """受众结果 → audience_snapshots 行。纯函数，可测。"""
    return {
        "captured_at": captured_at or dt.datetime.now(dt.timezone.utc).isoformat(),
        "total_followers": result.get("total_followers"),
        "top_demographics": result.get("top_demographics") or {},
        "raw": result,
    }


def insert_audience_snapshot(result: dict) -> dict:
    row = build_audience_row(result)
    client = _client()
    resp = client.table("audience_snapshots").insert(row).execute()
    data = resp.data[0] if resp.data else {}
    return {"id": data.get("id"), "row": row, "data": resp.data}
