"""LinkedIn adapter CLI（发现阶段）。

用法：
    python review.py login                # 首次：弹出浏览器登录 LinkedIn（存 cookie）
    python review.py dashboard            # DOM 抽取创作者面板 4 指标（headless，只打印）
    python review.py pull [--dry-run]     # 抽取 → INSERT profile_stats（--dry-run 只打印不写）
    python review.py resolve <permalink-or-urn>  # 永久链接/share urn → 规范 activity id（登记前归一）
    python review.py post <activity_id|permalink>  # DOM 抽取单帖分析（只打印；接受 URL/urn）
    python review.py posts [--limit=N] [--dry-run]  # 最新 N 帖 → engagement_snapshots
    python review.py audience [--dry-run] # 受众分析（aggregate）→ audience_snapshots
    python review.py discover [seconds]   # 发现 XHR 接口

  逐人受众画像（audience_members）：
    python review.py import-connections <Connections.csv> [--dry-run]  # 导入连接 → upsert
    python review.py followers [--max=N] [--dry-run]   # 爬关注者 → upsert（insert-only）
    python review.py classify [--limit=N] [--dry-run]  # 规则分类 + 导出模糊行给 LLM
    python review.py set-categories <labeled.json>     # 写回 LLM 标注 [{profile_key,category}]
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
    if len(sys.argv) > 1 and sys.argv[1] == "resolve":
        if len(sys.argv) < 3:
            print("用法：python review.py resolve <permalink-or-urn>")
            return
        # 登记前归一：永久链接/share urn → 规范 activity id，存这个数当 external_id。
        activity_id = asyncio.run(crawler.resolve_activity_id(sys.argv[2]))
        if not activity_id:
            print("❌ 没解析出 activity id", file=sys.stderr)
            sys.exit(1)
        print(activity_id)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "post":
        if len(sys.argv) < 3:
            print("用法：python review.py post <activity_id|permalink>")
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
    if len(sys.argv) > 1 and sys.argv[1] == "import-connections":
        from pathlib import Path
        rest = sys.argv[2:]
        dry = "--dry-run" in rest
        files = [a for a in rest if not a.startswith("--")]
        if not files:
            print("用法：python review.py import-connections <Connections.csv> [--dry-run]")
            return
        import audience_members
        text = Path(files[0]).expanduser().read_text(encoding="utf-8", errors="replace")
        members = audience_members.parse_connections_csv(text)
        if not members:
            print("❌ 没解析出连接（确认是 Connections.csv，含 'First Name' 表头）")
            return
        if dry:
            print(f"[dry-run] 将 upsert {len(members)} 个 connection（前 5 行）：")
            print(json.dumps(members[:5], ensure_ascii=False, indent=2))
            return
        import sink_supabase
        client = sink_supabase._client()
        out = sink_supabase.upsert_members(client, members, update=True)
        print(f"✓ upsert {len(members)} 个 connection（受影响 {len(out)} 行）。下一步：classify")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "followers":
        rest = sys.argv[2:]
        dry = "--dry-run" in rest
        max_people = 5000
        for a in rest:
            if a.startswith("--max="):
                max_people = int(a.split("=", 1)[1])
        rows = asyncio.run(crawler.fetch_followers(headless=True, max_people=max_people))
        if not rows:
            print("❌ 没抽到关注者（未写库）")
            return
        if dry:
            print(f"[dry-run] 将 upsert {len(rows)} 个 follower（insert-only，前 5 行）：")
            print(json.dumps(rows[:5], ensure_ascii=False, indent=2))
            return
        import sink_supabase
        client = sink_supabase._client()
        out = sink_supabase.upsert_members(client, rows, update=False)
        print(f"✓ 抓到 {len(rows)} 个关注者，新增 {len(out)} 行。下一步：classify")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "classify":
        rest = sys.argv[2:]
        dry = "--dry-run" in rest
        limit = None
        for a in rest:
            if a.startswith("--limit="):
                limit = int(a.split("=", 1)[1])
        import sink_supabase
        from classify import classify_row
        from paths import debug_dir
        client = sink_supabase._client()
        rows = sink_supabase.fetch_unclassified(client, limit=limit)
        if not rows:
            print("没有待分类的成员（category 全已填）。")
            return
        ruled, tail = [], []
        for r in rows:
            cat = classify_row(r.get("headline"), r.get("company"))
            if cat:
                ruled.append({"profile_key": r["profile_key"], "category": cat})
            else:
                tail.append(r)
        print(f"规则判定：{len(ruled)} 命中 / {len(tail)} 模糊（待 LLM）")
        if not dry and ruled:
            sink_supabase.apply_categories(client, ruled)
            print(f"✓ 写回 {len(ruled)} 行 category")
        if tail:
            dbg = debug_dir()
            dbg.mkdir(parents=True, exist_ok=True)
            tail_file = dbg / "classify_tail.json"
            tail_file.write_text(json.dumps(tail, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"→ {len(tail)} 个模糊行写到 {tail_file}")
            print("  让 Claude 读它按 8 类打标，再跑：python review.py set-categories <labeled.json>")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "set-categories":
        from pathlib import Path
        files = [a for a in sys.argv[2:] if not a.startswith("--")]
        if not files:
            print("用法：python review.py set-categories <labeled.json>  # [{profile_key,category},...]")
            return
        import sink_supabase
        items = json.loads(Path(files[0]).expanduser().read_text(encoding="utf-8"))
        valid = [it for it in items if it.get("profile_key") and it.get("category")]
        client = sink_supabase._client()
        out = sink_supabase.apply_categories(client, valid)
        print(f"✓ 写回 {len(out)} 行 category（输入 {len(items)} / 有效 {len(valid)}）")
        return
    print(__doc__)


if __name__ == "__main__":
    main()
