"""从渲染后的 DOM 文本里抽取 LinkedIn 分析指标。

LinkedIn 把分析数据 SSR/inline 进页面（不是 voyager XHR），所以读 inner_text 文本、
按已知标签锚点解析。纯函数，可独立测试（见 test_extract.py）。
"""
from __future__ import annotations

import re

# 创作者面板（/dashboard/）4 个顶线指标：标签 → 输出 key
DASHBOARD_LABELS = {
    "Post impressions": "post_impressions",
    "Followers": "followers",
    "Profile viewers": "profile_viewers",
    "Search appearances": "search_appearances",
}


def _to_int(s: str) -> int | None:
    """'34,057' → 34057；'1.2K' → 1200；抽不出返回 None。"""
    s = s.strip().replace(",", "")
    m = re.fullmatch(r"([\d.]+)\s*([KMB]?)", s)
    if not m:
        return None
    mult = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[m.group(2)]
    try:
        return int(float(m.group(1)) * mult)
    except ValueError:
        return None


def parse_dashboard(text: str) -> dict:
    """DOM 文本 → {'metrics': {...}, 'context': {...}, 'as_of_label': str}。

    版式（reading order）：值行 → 标签行 → 上下文行（周期或 delta）。
    锚定在 'Analytics & tools' 之后，取标签行的前一行为值、后一行为上下文。
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    start = 0
    for i, l in enumerate(lines):
        if l.startswith("Analytics & tools") or l == "Analytics":
            start = i
            break
    as_of_label = lines[start + 1] if start + 1 < len(lines) else ""

    metrics = {key: None for key in DASHBOARD_LABELS.values()}
    context = {key: "" for key in DASHBOARD_LABELS.values()}
    scan = lines[start:]
    for i, line in enumerate(scan):
        key = DASHBOARD_LABELS.get(line)
        if key is None or metrics[key] is not None:
            continue
        if i > 0:
            metrics[key] = _to_int(scan[i - 1])
        if i + 1 < len(scan):
            context[key] = scan[i + 1]
    return {"metrics": metrics, "context": context, "as_of_label": as_of_label}


# 单帖分析页（/analytics/post-summary/）。LinkedIn 在 日/英 间**随机切换**语言（同 session 都会变），
# 所以每个指标存多语言别名。版式两段：顶部指标“值在标签上一行”(before)，互动明细“值在标签下一行”(after)。
# (labels, key, value_position)
POST_METRICS = [
    (("インプレッション数", "Impressions"), "impressions", "before"),
    (("リーチしたメンバー", "Members reached"), "reach", "before"),
    (("この投稿からのプロフィール閲覧ユーザー", "Profile viewers from this post"), "profile_views_from_post", "before"),
    (("この投稿で獲得したフォロワー", "Followers gained from this post"), "followers_from_post", "before"),
    (("ソーシャルエンゲージメント", "Social engagements"), "social_engagement", "before"),
    (("リアクション", "Reactions"), "reactions", "after"),
    (("コメント", "Comments"), "comments", "after"),
    (("再投稿", "Reposts"), "reposts", "after"),
    (("保存数", "Saves"), "saves", "after"),
    (("LinkedInでの送信数", "Sends on LinkedIn"), "sends", "after"),
]

_IMPRESSION_LABELS = ("インプレッション数", "Impressions")


def parse_post_summary(text: str) -> dict:
    """单帖分析 DOM 文本 → {'metrics': {...}}。支持 日/英（LinkedIn 随机切换）。
    锚在第一个指标（Impressions）后，避开正文里的数字；每个指标按 value_position 取前/后一行。"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    start = 0
    for i, l in enumerate(lines):
        if l in _IMPRESSION_LABELS:
            start = max(0, i - 1)
            break
    scan = lines[start:]
    out = {key: None for _, key, _ in POST_METRICS}
    for i, line in enumerate(scan):
        for labels, key, pos in POST_METRICS:
            if line not in labels or out[key] is not None:
                continue
            j = i - 1 if pos == "before" else i + 1
            if 0 <= j < len(scan):
                out[key] = _to_int(scan[j])
    return {"metrics": out}


# 受众分析页（/analytics/creator/audience/）。demographics 区按 "%" 锚点解析（语言无关），
# 取 %行 的前两行为 维度/桶；维度名规范化成统一 key。total_followers 锚双语标签。
AUDIENCE_TOTAL_LABELS = ("フォロワー合計", "Total followers")
AUDIENCE_DEMO_HEADER = ("上位統計データ", "Top demographics")

DIMENSION_CANON = {
    "職務レベル": "seniority", "Seniority": "seniority",
    "会社規模": "company_size", "Company size": "company_size",
    "場所": "location", "Location": "location", "Locations": "location",
    "業種": "industry", "Industry": "industry", "Industries": "industry",
    "役職": "job_title", "Job title": "job_title", "Job titles": "job_title",
    "会社": "company", "Company": "company", "Companies": "company",
}


def _pct_to_float(s: str):
    s = s.strip().rstrip("%").strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse_audience(text: str) -> dict:
    """受众分析 DOM → {'total_followers': int, 'top_demographics': {canon_dim: {bucket, pct}}}。
    demographics 锚 '%' 行（语言无关）：取前两行为 维度/桶。"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    total = None
    for i, l in enumerate(lines):
        if l in AUDIENCE_TOTAL_LABELS and i > 0:
            total = _to_int(lines[i - 1])
            break
    start = None
    for i, l in enumerate(lines):
        if l in AUDIENCE_DEMO_HEADER:
            start = i
            break
    demographics: dict = {}
    if start is not None:
        scan = lines[start + 1:]
        for i, l in enumerate(scan):
            if l.endswith("%") and i >= 2:
                dim = DIMENSION_CANON.get(scan[i - 2], scan[i - 2])
                if dim not in demographics:
                    demographics[dim] = {"bucket": scan[i - 1], "pct": _pct_to_float(l)}
    return {"total_followers": total, "top_demographics": demographics}
