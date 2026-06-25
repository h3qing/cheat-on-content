"""crawler 的 share→activity 归一逻辑单测（含一个用假 page 的异步集成测）。

纯函数（extract_activity_id / activity_id_from_ref / _post_url_for）零网络；
resolve_activity_id / normalize_to_activity_id 用 _FakePage 跑通异步路径，不开真浏览器。

跑：python test_crawler.py
（需在装了 playwright 的 venv 里——crawler 顶层 import playwright；见 README 安装步骤）
"""
from __future__ import annotations

import asyncio

from crawler import (
    _post_url_for,
    activity_id_from_ref,
    extract_activity_id,
    normalize_to_activity_id,
    resolve_activity_id,
)

# 复刻 2026-06-24 的 repro：永久链接给的是 share urn，分析页要的却是另一串 activity id。
SHARE_ID = "7475279004321632256"
ACTIVITY_ID = "7475279004976205824"
SHARE_PERMALINK = f"https://www.linkedin.com/feed/update/urn:li:share:{SHARE_ID}/"

# 真实帖子页 HTML 里 activity urn 多处出现，share urn 只在规范链接里出现一次；
# 评论区还引用了另一条帖子的 activity id（出现 1 次），不该被选中。
SAMPLE_HTML = f"""<html><head>
<link rel="canonical" href="https://www.linkedin.com/feed/update/urn:li:share:{SHARE_ID}/"/>
</head><body>
<div data-urn="urn:li:activity:{ACTIVITY_ID}">
  <a href="/analytics/post-summary/urn:li:activity:{ACTIVITY_ID}/">View analytics</a>
  <div data-id="urn:li:activity:{ACTIVITY_ID}"></div>
  <div data-urn="urn:li:activity:7470000000000000000"></div>
</div>
</body></html>"""


class _FakePage:
    """最小 async page：只实现 resolve_activity_id 用到的 goto / content。"""

    def __init__(self, html: str) -> None:
        self._html = html
        self.goto_url: str | None = None

    async def goto(self, url: str, **_kw) -> None:
        self.goto_url = url

    async def content(self) -> str:
        return self._html


class _BoomPage:
    """任何网络调用都炸——用来断言某些 ref 不该联网。"""

    async def goto(self, *_a, **_k):
        raise AssertionError("不该联网")

    async def content(self):
        raise AssertionError("不该联网")


# ---- 纯函数 ----

def test_extract_activity_id_picks_highest_frequency():
    assert extract_activity_id(SAMPLE_HTML) == ACTIVITY_ID, extract_activity_id(SAMPLE_HTML)


def test_extract_activity_id_none_when_absent():
    assert extract_activity_id("no urn here") is None
    assert extract_activity_id("") is None


def test_extract_activity_id_tie_breaks_first_seen():
    # 各出现一次 → 取先出现的那个
    assert extract_activity_id("urn:li:activity:111 urn:li:activity:222") == "111"


def test_activity_id_from_ref_local_hits():
    assert activity_id_from_ref(f"urn:li:activity:{ACTIVITY_ID}") == ACTIVITY_ID
    assert activity_id_from_ref(
        f"https://www.linkedin.com/feed/update/urn:li:activity:{ACTIVITY_ID}/"
    ) == ACTIVITY_ID
    assert activity_id_from_ref(ACTIVITY_ID) == ACTIVITY_ID            # 裸数字当 activity
    assert activity_id_from_ref(f"  {ACTIVITY_ID}  ") == ACTIVITY_ID   # 去空白


def test_activity_id_from_ref_needs_network():
    # share urn / 不含 activity 的链接 → None（交给 resolve 联网解析）
    assert activity_id_from_ref(f"urn:li:share:{SHARE_ID}") is None
    assert activity_id_from_ref(SHARE_PERMALINK) is None
    assert activity_id_from_ref("https://www.linkedin.com/posts/foo") is None
    assert activity_id_from_ref("") is None


def test_post_url_for():
    assert _post_url_for(f"urn:li:share:{SHARE_ID}") == SHARE_PERMALINK
    assert _post_url_for(SHARE_PERMALINK) == SHARE_PERMALINK           # 已是 URL → 原样
    assert _post_url_for(SHARE_ID) == SHARE_PERMALINK                  # 裸号 → 兜底成 share urn
    assert _post_url_for(f"urn:li:activity:{ACTIVITY_ID}") == (
        f"https://www.linkedin.com/feed/update/urn:li:activity:{ACTIVITY_ID}/"
    )


# ---- 异步：用假 page 跑通解析路径 ----

def test_resolve_activity_id_from_share_permalink_loads_page():
    page = _FakePage(SAMPLE_HTML)
    got = asyncio.run(resolve_activity_id(SHARE_PERMALINK, page=page))
    assert got == ACTIVITY_ID, got
    assert page.goto_url == SHARE_PERMALINK, page.goto_url  # 确实加载了帖子页


def test_resolve_activity_id_from_bare_share_id_loads_page():
    # 已入库的裸 share id（repro 那行）也能补救：resolve 兜底成 share urn 再解析
    page = _FakePage(SAMPLE_HTML)
    got = asyncio.run(resolve_activity_id(SHARE_ID, page=page))
    assert got == ACTIVITY_ID, got
    assert page.goto_url == SHARE_PERMALINK, page.goto_url


def test_resolve_activity_id_short_circuits_activity_urn():
    # 已是 activity urn：不该联网
    got = asyncio.run(resolve_activity_id(f"urn:li:activity:{ACTIVITY_ID}", page=_BoomPage()))
    assert got == ACTIVITY_ID, got


def test_normalize_activity_and_bare_skip_network():
    assert asyncio.run(normalize_to_activity_id(ACTIVITY_ID, page=_BoomPage())) == ACTIVITY_ID
    assert asyncio.run(
        normalize_to_activity_id(f"urn:li:activity:{ACTIVITY_ID}", page=_BoomPage())
    ) == ACTIVITY_ID


def test_normalize_share_permalink_resolves_via_page():
    page = _FakePage(SAMPLE_HTML)
    got = asyncio.run(normalize_to_activity_id(SHARE_PERMALINK, page=page))
    assert got == ACTIVITY_ID, got
    assert page.goto_url == SHARE_PERMALINK


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"✓ {fn.__name__}")
    print(f"\n{len(fns)} passed")
