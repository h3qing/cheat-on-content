"""受众成员（per-person）的入库前处理：profile_key 归一 + Connections.csv 解析。

纯函数，可测（见 test_audience.py）。落库在 sink_supabase.py（audience_members 表）。
"""
from __future__ import annotations

import csv
import io
import re

# LinkedIn 个人页 URL 里 /in/<slug> 的 slug 即稳定去重键（vanity 改了也仍能对上历史导出）。
_PROFILE_RE = re.compile(r"/in/([^/?#]+)", re.IGNORECASE)


def profile_key_from_url(url: str | None) -> str | None:
    """https://www.linkedin.com/in/<slug>/?trk=... → '<slug>'。拿不到返回 None。"""
    m = _PROFILE_RE.search(url or "")
    if not m:
        return None
    return m.group(1).strip("/").strip() or None


def _clean(v: str | None) -> str | None:
    s = (v or "").strip()
    return s or None


def parse_connections_csv(text: str) -> list[dict]:
    """LinkedIn 数据导出里的 Connections.csv → 成员 dict 列表。

    导出文件头部有 2~3 行 "Notes:" 说明 + 空行，真正的表头是 'First Name,...'，
    所以先定位表头行再交给 csv.DictReader。无 URL（拿不到 profile_key）的行跳过。
    """
    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if line.lstrip('"').startswith("First Name"):
            header_idx = i
            break
    if header_idx is None:
        return []

    reader = csv.DictReader(io.StringIO("\n".join(lines[header_idx:])))
    out: list[dict] = []
    for row in reader:
        key = profile_key_from_url(row.get("URL"))
        if not key:
            continue
        name = " ".join(p for p in (_clean(row.get("First Name")),
                                    _clean(row.get("Last Name"))) if p) or None
        out.append({
            "profile_key": key,
            "full_name": name,
            "headline": _clean(row.get("Position")),
            "company": _clean(row.get("Company")),
            "relationship": "connection",
            "raw": {
                "source": "connections_csv",
                "url": _clean(row.get("URL")),
                "connected_on": _clean(row.get("Connected On")),
            },
        })
    return out
