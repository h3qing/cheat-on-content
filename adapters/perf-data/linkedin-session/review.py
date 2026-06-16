"""LinkedIn adapter CLI（发现阶段）。

用法：
    python review.py login                # 首次：弹出浏览器登录 LinkedIn（存 cookie）
    python review.py dashboard            # DOM 抽取创作者面板 4 指标（headless，只打印）
    python review.py pull [--dry-run]     # 抽取 → INSERT profile_stats（--dry-run 只打印不写）
    python review.py post <activity_id>   # DOM 抽取单帖分析（只打印）
    python review.py posts [--limit=N] [--dry-run]  # 最新 N 帖 → engagement_snapshots
    python review.py audience [--dry-run] # 受众分析 → audience_snapshots
    python review.py discover [seconds]   # 发现 XHR 接口
"""
from __future__ import annotations

import asyncio
import json
import sys

import crawler


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "login":
        asyncio.run(crawler.ensure_login())
        return
    if len(sys.argv) > 1 and sys.argv[1] == "discover":
        secs = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 180
        asyncio.run(crawler.discover(manual_seconds=secs))
        return
    if len(sys.argv) > 1 and sys.argv[1] == "dashboard":
        result = asyncio.run(crawler.fetch_creator_dashboard(headless=True))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if len(sys.argv) > 1 and sys.argv[1] == "pull":
        dry = "--dry-run" in sys.argv[2:]
        result = asyncio.run(crawler.fetch_creator_dashboard(headless=True))
        metrics = result.get("metrics") or {}
        if not any(v is not None for v in metrics.values()):
            print("❌ 没抽到任何指标，终止（未写库）")
            return
        import sink_supabase
        if dry:
            row = sink_supabase.build_profile_stats_row(result)
            print("[dry-run] 将 INSERT 进 profile_stats（未写库）：")
            print(json.dumps(row, ensure_ascii=False, indent=2))
            return
        out = sink_supabase.insert_profile_stats(result)
        print(f"✓ 已 INSERT profile_stats（id={out.get('id')}）")
        print(json.dumps(out["row"], ensure_ascii=False, indent=2))
        return
    if len(sys.argv) > 1 and sys.argv[1] == "post":
        if len(sys.argv) < 3:
            print("用法：python review.py post <activity_id>")
            return
        result = asyncio.run(crawler.fetch_post_summary(sys.argv[2], headless=True))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if len(sys.argv) > 1 and sys.argv[1] == "posts":
        rest = sys.argv[2:]
        dry = "--dry-run" in rest
        limit = 5
        for a in rest:
            if a.startswith("--limit="):
                limit = int(a.split("=", 1)[1])
        import sink_supabase
        client = sink_supabase._client()
        posts = sink_supabase.fetch_linkedin_posts(client, limit=limit)
        if not posts:
            print("posts 表里没有 linkedin 帖子")
            return
        print(f"抓最新 {len(posts)} 帖的单帖分析……")
        results = asyncio.run(crawler.fetch_post_summaries([p["external_id"] for p in posts]))
        rows = []
        for p in posts:
            r = results.get(p["external_id"]) or {}
            if not (r.get("metrics") or {}).get("impressions"):
                print(f"  ⚠ {p['external_id']} 没抽到 impressions，跳过")
                continue
            rows.append(sink_supabase.build_engagement_row(p["id"], r, p.get("posted_at")))
        if dry:
            print("[dry-run] 将 INSERT engagement_snapshots（未写库）：")
            print(json.dumps(rows, ensure_ascii=False, indent=2))
            return
        out = sink_supabase.insert_engagement_rows(client, rows)
        print(f"✓ 已 INSERT {len(out)} 行 engagement_snapshots")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "audience":
        dry = "--dry-run" in sys.argv
        result = asyncio.run(crawler.fetch_audience(headless=True))
        if not result.get("top_demographics"):
            print("❌ 没抽到 demographics，终止（未写库）")
            return
        if dry:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        import sink_supabase
        out = sink_supabase.insert_audience_snapshot(result)
        print(f"✓ 已 INSERT audience_snapshots（id={out.get('id')}）")
        print(json.dumps(out["row"], ensure_ascii=False, indent=2))
        return
    print(__doc__)


if __name__ == "__main__":
    main()
