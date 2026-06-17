"""X (Twitter) discovery — login + engagement-aware search.

Headless after a one-time login (cookie in .auth-x/). Navigates X search, passively
intercepts the SearchTimeline GraphQL response, and parses tweets + full engagement
(views / likes / retweets / replies / bookmarks). Output is tweets ranked by engagement —
the "what's driving volume on X" signal. Relevance curation → source_signals is done by
the agent (or pipe `discover` JSON into content-pipeline).

Run with the project venv + CHEAT_PROJECT_ROOT pointing at your tracker dir:
    CHEAT_PROJECT_ROOT=~/linkedin-tracker python crawler.py login
    CHEAT_PROJECT_ROOT=~/linkedin-tracker python crawler.py discover "AI agents"
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.parse
from pathlib import Path

from playwright.async_api import async_playwright


def _root() -> Path:
    return Path(os.environ.get("CHEAT_PROJECT_ROOT") or Path.cwd()).expanduser()


def auth_dir() -> Path:
    return _root() / ".auth-x"


X_LOGIN = "https://x.com/login"


class Session:
    def __init__(self, ctx, pw):
        self.ctx = ctx
        self.pw = pw

    @classmethod
    async def open(cls, headless: bool = True) -> "Session":
        pw = await async_playwright().start()
        a = auth_dir()
        a.mkdir(parents=True, exist_ok=True)
        ctx = await pw.chromium.launch_persistent_context(
            str(a), headless=headless, viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        return cls(ctx, pw)

    async def close(self) -> None:
        try:
            await self.ctx.close()
        finally:
            await self.pw.stop()


async def _logged_in(ctx) -> bool:
    return any(c["name"] == "auth_token" for c in await ctx.cookies("https://x.com"))


async def ensure_login(timeout_s: int = 300) -> bool:
    sess = await Session.open(headless=False)
    try:
        page = await sess.ctx.new_page()
        await page.goto(X_LOGIN)
        print(f"[x] 在弹出的 Chromium 里登录 X（最多 {timeout_s}s）……")
        for i in range(timeout_s):
            if await _logged_in(sess.ctx):
                print(f"[x] ✓ auth_token 检测到（{i}s），会话存到 .auth-x/")
                await asyncio.sleep(1)
                return True
            await asyncio.sleep(1)
        print("[x] 超时未检测到登录。")
        return False
    finally:
        await sess.close()


def _author(o: dict):
    try:
        r = o["core"]["user_results"]["result"]
        return (r.get("core", {}) or {}).get("screen_name") or (r.get("legacy", {}) or {}).get("screen_name")
    except Exception:
        return None


def _walk(o, out: list) -> None:
    """Recursively pull every tweet (objects whose legacy has full_text)."""
    if isinstance(o, dict):
        leg = o.get("legacy")
        if isinstance(leg, dict) and "full_text" in leg:
            author = _author(o)
            tid = o.get("rest_id")
            v = (o.get("views") or {}).get("count")
            out.append({
                "id": tid,
                "author": author,
                "url": f"https://x.com/{author}/status/{tid}" if author and tid else None,
                "text": leg.get("full_text", "")[:280],
                "views": int(v) if v else None,
                "likes": leg.get("favorite_count"),
                "retweets": leg.get("retweet_count"),
                "replies": leg.get("reply_count"),
                "bookmarks": leg.get("bookmark_count"),
            })
        for x in o.values():
            _walk(x, out)
    elif isinstance(o, list):
        for x in o:
            _walk(x, out)


async def search(keyword: str, limit: int = 15, headless: bool = True) -> list:
    sess = await Session.open(headless=headless)
    tweets: list = []
    try:
        if not await _logged_in(sess.ctx):
            print("[x] 未登录。先跑：python crawler.py login")
            return []

        async def on_resp(resp):
            if "SearchTimeline" in resp.url:
                try:
                    _walk(await resp.json(), tweets)
                except Exception:
                    pass

        sess.ctx.on("response", on_resp)
        page = await sess.ctx.new_page()
        await page.goto(
            f"https://x.com/search?q={urllib.parse.quote(keyword)}&f=top",
            wait_until="domcontentloaded", timeout=60000,
        )
        await asyncio.sleep(6)
        try:
            for _ in range(3):
                await page.evaluate("window.scrollBy(0,1800)")
                await asyncio.sleep(2.5)
        except Exception:
            pass
    finally:
        await sess.close()

    seen, uniq = set(), []
    for t in tweets:
        k = (t["text"] or "")[:80]
        if not k or k in seen:
            continue
        seen.add(k)
        uniq.append(t)
    uniq.sort(key=lambda t: (t["views"] or 0, t["likes"] or 0), reverse=True)
    return uniq[:limit]


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "login":
        asyncio.run(ensure_login())
    elif len(sys.argv) > 1 and sys.argv[1] == "discover":
        kw = sys.argv[2] if len(sys.argv) > 2 else "AI agents"
        print(json.dumps(asyncio.run(search(kw)), ensure_ascii=False, indent=2))
    else:
        print("usage: crawler.py login | discover <keyword>")
