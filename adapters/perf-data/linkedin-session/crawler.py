"""LinkedIn 分析数据抓取 —— 发现阶段（capture-first）。

登录一次后 Cookie 持久化在 .auth-linkedin/，之后直接复用。

LinkedIn 网页前端走内部 voyager/api（GraphQL/Restli）JSON 接口，接口形状按账号
feature flag 变、且无公开文档——照搬不了。所以这一版先"发现"：导航到各分析页时，
把前端自动发出的所有 voyager XHR 响应 dump 到 .cheat-cache/linkedin-session-debug/voyager/，
据此再写 4 个正式 parser（见 README 的 Roadmap）。和 douyin-session 的 capture-first 同思路。
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Page, Response, async_playwright

from paths import auth_dir, debug_dir, voyager_dump_dir
from extract import parse_audience, parse_dashboard, parse_post_meta, parse_post_summary

FEED = "https://www.linkedin.com/feed/"
DASHBOARD = "https://www.linkedin.com/dashboard/"
POST_SUMMARY = "https://www.linkedin.com/analytics/post-summary/urn:li:activity:{activity_id}/"
AUDIENCE = "https://www.linkedin.com/analytics/creator/audience/"

# 已知分析落地页：导航过去，拦截前端自动发的 voyager XHR。
# 单帖 / 公司主页 URL 含动态 id —— 发现阶段靠 discover() 的人工导航窗口补齐。
ANALYTICS_LANDING = {
    "creator_dashboard": "https://www.linkedin.com/dashboard/",
    "analytics_home": "https://www.linkedin.com/analytics/",
}

VOYAGER_MARKERS = ("voyager/api", "/api/graphql")

_ACTIVITY_RE = re.compile(r"urn:li:activity:(\d+)|activity[:-](\d+)|/(\d{15,25})\b")


def extract_activity_id(raw: str) -> str:
    """从帖子 URL 或裸 id 提取 activity_id。

    支持裸 id（`7470493738918920193`）、帖子链接
    （/feed/update/urn:li:activity:<id>/）、分析链接
    （/analytics/post-summary/urn:li:activity:<id>/）。抽不出时原样返回（交上层报错）。
    """
    raw = raw.strip()
    if raw.isdigit():
        return raw
    m = _ACTIVITY_RE.search(raw)
    if m:
        return next(g for g in m.groups() if g)
    return raw


class Session:
    """单浏览器会话，持久化登录态。"""

    def __init__(self, ctx: BrowserContext, pw: Any) -> None:
        self.ctx = ctx
        self.pw = pw

    @classmethod
    async def open(cls, headless: bool = False) -> "Session":
        pw = await async_playwright().start()
        auth_path = auth_dir()
        auth_path.mkdir(parents=True, exist_ok=True)
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(auth_path),
            headless=headless,
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        return cls(ctx, pw)

    async def close(self) -> None:
        try:
            await self.ctx.close()
        finally:
            await self.pw.stop()


async def _logged_in(ctx: BrowserContext) -> bool:
    cookies = await ctx.cookies("https://www.linkedin.com")
    return any(c["name"] == "li_at" for c in cookies)


async def ensure_login(timeout_s: int = 300) -> bool:
    """打开 LinkedIn，等待用户登录；检测到 li_at cookie 后返回。"""
    sess = await Session.open()
    try:
        page = await sess.ctx.new_page()
        await page.goto(FEED)
        print(f"[登录] 在弹出的 Chromium 里登录 LinkedIn。最多等 {timeout_s} 秒……")
        for i in range(timeout_s):
            if await _logged_in(sess.ctx):
                print(f"[登录] ✓ 检测到 li_at（用时 {i}s）。Cookie 已存到 .auth-linkedin/")
                await asyncio.sleep(1)
                return True
            await asyncio.sleep(1)
        print("[登录] 超时未检测到登录态。")
        return False
    finally:
        await sess.close()


async def fetch_creator_dashboard(headless: bool = True) -> dict:
    """DOM 抽取创作者面板（/dashboard/）的 4 个顶线指标。

    LinkedIn 把这些数据 SSR/inline 进页面，没有可拦的 voyager XHR，所以读渲染后 DOM。
    headless 下登录态可用（已验证），适合无人值守 routine。
    """
    sess = await Session.open(headless=headless)
    try:
        if not await _logged_in(sess.ctx):
            print("[dashboard] 未登录。先跑：python review.py login")
            return {}
        page = await sess.ctx.new_page()
        await page.goto(DASHBOARD, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(6)
        if "dashboard" not in page.url:
            print(f"[dashboard] ⚠ 可能被登出 / 重定向：{page.url}")
        txt = await page.inner_text("body")
        dbg = debug_dir()
        dbg.mkdir(parents=True, exist_ok=True)
        (dbg / "dashboard.txt").write_text(txt, encoding="utf-8")
        result = parse_dashboard(txt)
        missing = [k for k, v in result["metrics"].items() if v is None]
        if missing:
            print(f"[dashboard] ⚠ 没抽到 {missing}（结构可能变了，看 {dbg}/dashboard.txt）")
        return result
    finally:
        await sess.close()


async def _scrape_post(page: Page, activity_id: str) -> dict:
    await page.goto(POST_SUMMARY.format(activity_id=activity_id),
                    wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(7)
    if "post-summary" not in page.url:
        print(f"[post] ⚠ 可能被登出 / 重定向：{page.url}")
    txt = await page.inner_text("body")
    dbg = debug_dir()
    dbg.mkdir(parents=True, exist_ok=True)
    (dbg / f"post_{activity_id}.txt").write_text(txt, encoding="utf-8")
    result = parse_post_summary(txt)
    result["meta"] = parse_post_meta(txt)
    result["activity_id"] = activity_id
    if result["metrics"].get("impressions") is None:
        print(f"[post] ⚠ {activity_id} 没抽到 impressions（看 {dbg}/post_{activity_id}.txt）")
    return result


async def fetch_post_summary(activity_id: str, headless: bool = True) -> dict:
    """DOM 抽取单帖分析（/analytics/post-summary/）。仅本人帖子可看。"""
    sess = await Session.open(headless=headless)
    try:
        if not await _logged_in(sess.ctx):
            print("[post] 未登录。先跑：python review.py login")
            return {}
        page = await sess.ctx.new_page()
        return await _scrape_post(page, activity_id)
    finally:
        await sess.close()


async def fetch_post_summaries(activity_ids: list[str], headless: bool = True,
                               delay_s: float = 4.0) -> dict:
    """一个会话里顺序抓多帖，帖间停顿（对 LinkedIn 温和些）。"""
    sess = await Session.open(headless=headless)
    out: dict = {}
    try:
        if not await _logged_in(sess.ctx):
            print("[post] 未登录。先跑：python review.py login")
            return {}
        page = await sess.ctx.new_page()
        for i, aid in enumerate(activity_ids):
            if i:
                await asyncio.sleep(delay_s)
            out[aid] = await _scrape_post(page, aid)
            m = out[aid]["metrics"]
            print(f"  [{aid}] impressions={m.get('impressions')} eng={m.get('social_engagement')}")
        return out
    finally:
        await sess.close()


async def fetch_all(activity_id: str, headless: bool = True) -> dict:
    """抓单帖分析（指标 + meta），返回 {'post': {...}} —— 对齐 review.py video 的渲染入口。"""
    print(f"  → 打开单帖分析页 activity:{activity_id}")
    post = await fetch_post_summary(activity_id, headless=headless)
    if post:
        m = post.get("metrics", {})
        print(f"       impressions={m.get('impressions')} reactions={m.get('reactions')} comments={m.get('comments')}")
    return {"post": post}


async def fetch_audience(headless: bool = True) -> dict:
    """DOM 抽取受众分析（/analytics/creator/audience/）：总粉丝 + 各维度 Top demographic。"""
    sess = await Session.open(headless=headless)
    try:
        if not await _logged_in(sess.ctx):
            print("[audience] 未登录。先跑：python review.py login")
            return {}
        page = await sess.ctx.new_page()
        await page.goto(AUDIENCE, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(7)
        txt = await page.inner_text("body")
        dbg = debug_dir()
        dbg.mkdir(parents=True, exist_ok=True)
        (dbg / "audience.txt").write_text(txt, encoding="utf-8")
        result = parse_audience(txt)
        if not result.get("top_demographics"):
            print(f"[audience] ⚠ 没抽到 demographics（看 {dbg}/audience.txt）")
        return result
    finally:
        await sess.close()


def _sanitize(url: str, max_len: int = 80) -> str:
    path = url.split("?", 1)[0]
    for marker in ("voyager/api/", "/api/"):
        if marker in path:
            path = path.split(marker, 1)[-1]
            break
    bad = '<>:"/\\|?*&=\n\r\t .'
    out = "".join("_" if ch in bad else ch for ch in path)
    return out[:max_len] or "root"


def _attach_logger(target: Any, captured: list[dict], dump: Path) -> None:
    """拦截并落盘所有 voyager 响应（target 可为 Page 或 BrowserContext；
    用 context 能覆盖用户手动新开的标签页）。"""
    seq = {"n": 0}

    async def on_response(resp: Response) -> None:
        if not any(m in resp.url for m in VOYAGER_MARKERS):
            return
        try:
            data = await resp.json()
        except Exception:
            return
        seq["n"] += 1
        rec = {"url": resp.url, "status": resp.status, "data": data}
        captured.append(rec)
        fname = f"{seq['n']:04d}__{_sanitize(resp.url)}.json"
        try:
            (dump / fname).write_text(
                json.dumps(rec, ensure_ascii=False, indent=2)[:200000],
                encoding="utf-8",
            )
        except Exception:
            pass

    target.on("response", on_response)


async def discover(manual_seconds: int = 180) -> int:
    """登录态下导航各分析页 + 人工补充导航，dump 所有 voyager XHR。"""
    sess = await Session.open()
    captured: list[dict] = []
    dump = voyager_dump_dir()
    dump.mkdir(parents=True, exist_ok=True)
    try:
        if not await _logged_in(sess.ctx):
            print("[发现] 未登录。先跑：python review.py login")
            return 0

        _attach_logger(sess.ctx, captured, dump)
        page = await sess.ctx.new_page()

        for name, url in ANALYTICS_LANDING.items():
            print(f"[发现] → {name}: {url}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(6)
                await page.screenshot(path=str(dump / f"surface_{name}.png"))
            except Exception as e:
                print(f"        加载失败: {e}")

        print("\n[发现] 现在请在弹出的浏览器里手动点开你要追踪的页面：")
        print("        ① 某条帖子 → View analytics（单帖分析）")
        print("        ② 创作者面板 / Show all analytics（曝光 / 粉丝 / 搜索出现）")
        print("        ③ 你的 Company Page → Admin → Analytics（如果有）")
        print("        ④ 受众 / Followers demographics")
        print(f"        后台在记录所有 voyager 接口。窗口保持 {manual_seconds}s，期间随便点开各页。")
        # 非交互 stdin 下 input() 会立即 EOF，所以用固定时长 + 进度提示
        waited = 0
        step = 20
        while waited < manual_seconds:
            await asyncio.sleep(min(step, manual_seconds - waited))
            waited += step
            print(f"        … {min(waited, manual_seconds)}/{manual_seconds}s，已抓 {len(captured)} 个接口")

        index = [
            {"seq": i + 1, "status": r["status"], "url": r["url"]}
            for i, r in enumerate(captured)
        ]
        (dump / "_index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n[发现] ✓ 共抓到 {len(captured)} 个 voyager 响应 → {dump}")
        print("        把这个目录（或 _index.json）给我，我据此写 4 个 parser。")
        return len(captured)
    finally:
        await sess.close()


if __name__ == "__main__":
    asyncio.run(ensure_login())
