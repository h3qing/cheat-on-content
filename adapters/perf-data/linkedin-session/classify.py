"""受众分类（per-person）—— 确定性关键词规则。纯函数，可测（见 test_audience.py）。

目标是"全受众"画像：把每个人按 headline（= LinkedIn 的 Position 字段）归到一个桶。
规则命中返回 category，命中不了返回 None —— None 即"模糊行"，交给 LLM tail 再判
（见 review.py classify / set-categories）。规则只做高置信度的判定，宁可返回 None。

顺序敏感：student 在最前（"PhD Student" 是学生不是 educator；"Student Body President"
是学生不是 leadership）。第一个命中的桶胜出。
"""
from __future__ import annotations

import re

# (category, [关键词])，按优先级从上到下；headline 命中任一关键词即归该桶。
# 关键词都用小写，匹配前 headline 也转小写。
RULES: list[tuple[str, list[str]]] = [
    ("student", [
        "student", "aspiring", "candidate", "class of 20", "intern", "internship",
        "undergrad", "freshman", "sophomore", "b.s.", "m.s.",
        "research assistant", "teaching assistant", "graduate assistant",
        "学生", "在读", "実習生", "インターン",
    ]),
    ("educator", [
        "professor", "lecturer", "postdoc", "post-doc", "researcher",
        "faculty", "teacher", "dean", "教授", "讲师", "教員", "研究員",
    ]),
    ("recruiter_hr", [
        "recruiter", "recruiting", "talent acquisition", "talent partner",
        "headhunter", "sourcer", "people operations", "human resources",
        "hr", "hrbp", "talent", "招聘", "人事",
    ]),
    ("leadership", [
        "founder", "co-founder", "cofounder", "ceo", "cto", "coo", "cfo",
        "cmo", "chief", "president", "vp", "svp", "evp", "vice president",
        "head of", "head", "board", "director", "owner", "managing partner",
        "创始人", "总裁", "总监",
    ]),
    ("creator_media", [
        "content creator", "creator", "influencer", "youtuber", "podcaster",
        "blogger", "journalist", "writer", "author", "columnist",
        "editor", "host", "coach", "博主", "自媒体", "作家",
    ]),
    ("early_career", [
        "junior", "associate", "trainee", "entry level", "entry-level",
        "graduate engineer", "graduate analyst",
    ]),
    ("professional", [
        "engineer", "developer", "designer", "manager", "consultant",
        "specialist", "scientist", "analyst", "accountant", "lawyer",
        "architect", "marketing", "sales", "product", "operations",
        "executive", "lead", "staff", "principal", "account", "gtm",
        "analytics", "strategy", "strategist", "strategic", "advisor",
        "partner", "ops", "finance", "growth", "engineering", "sde",
        "business development", "trader", "supervisor", "coordinator",
        "工程师", "设计师", "经理", "顾问",
    ]),
]


def _kw_match(text: str, kw: str) -> bool:
    """ASCII 关键词按词边界匹配（避免 'intern' 命中 'international'/'internal'）；
    CJK 关键词无 ASCII 词边界，退回子串匹配。"""
    if kw.isascii():
        return re.search(r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])", text) is not None
    return kw in text


def classify_row(headline: str | None, company: str | None = None) -> str | None:
    """headline（+ company）→ category 或 None（模糊，交给 LLM tail）。"""
    text = (headline or "").lower()
    if not text.strip():
        return None
    for category, keywords in RULES:
        if any(_kw_match(text, kw) for kw in keywords):
            return category
    return None
