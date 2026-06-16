"""sink_supabase.build_profile_stats_row 的单元测试（不连 DB，合成数据）。

跑：python test_sink.py
"""
from sink_supabase import build_audience_row, build_engagement_row, build_profile_stats_row

SAMPLE = {
    "metrics": {
        "post_impressions": 11111,
        "followers": 222,
        "profile_viewers": 333,
        "search_appearances": 44,
    },
    "context": {"post_impressions": "10.0% past 7 days"},
    "as_of_label": "Wednesday, January 1",
}


def test_row_mapping():
    row = build_profile_stats_row(SAMPLE, "2026-01-01T00:00:00+00:00")
    assert row["captured_at"] == "2026-01-01T00:00:00+00:00"
    assert row["followers"] == 222
    assert row["profile_viewers_90d"] == 333
    assert row["post_impressions_7d"] == 11111
    assert row["search_appearances_prev_week"] == 44
    assert row["raw"] == SAMPLE


def test_row_handles_missing():
    row = build_profile_stats_row({}, "2026-01-01T00:00:00+00:00")
    assert row["followers"] is None
    assert row["post_impressions_7d"] is None
    assert row["raw"] == {}


def test_captured_at_defaults():
    row = build_profile_stats_row(SAMPLE)
    assert row["captured_at"]  # 非空（默认 now）
    assert "T" in row["captured_at"]


POST_RESULT = {
    "metrics": {"impressions": 1379, "reach": 838, "reactions": 10, "comments": 7,
                "reposts": 1, "saves": 0, "sends": 1, "social_engagement": 19},
    "activity_id": "7470493738918920193",
}


def test_engagement_row_mapping():
    row = build_engagement_row(17, POST_RESULT,
                               posted_at="2026-06-11T09:00:00+00:00",
                               captured_at="2026-06-15T09:00:00+00:00")
    assert row["post_id"] == 17
    assert row["impressions"] == 1379
    assert row["reactions"] == 10
    assert row["comments"] == 7
    assert row["reposts"] == 1
    assert row["capture_phase"] == "analytics"
    assert row["minutes_since_post"] == 4 * 24 * 60  # 4 天
    assert row["raw"] == POST_RESULT


def test_engagement_row_missing_posted_at():
    row = build_engagement_row(1, POST_RESULT)
    assert row["minutes_since_post"] is None
    assert row["impressions"] == 1379


AUDIENCE_RESULT = {
    "total_followers": 6636,
    "top_demographics": {"seniority": {"bucket": "Senior", "pct": 35.0},
                         "company": {"bucket": "Scale AI", "pct": 4.0}},
}


def test_audience_row_mapping():
    row = build_audience_row(AUDIENCE_RESULT, captured_at="2026-06-15T09:00:00+00:00")
    assert row["captured_at"] == "2026-06-15T09:00:00+00:00"
    assert row["total_followers"] == 6636
    assert row["top_demographics"]["seniority"]["pct"] == 35.0
    assert row["raw"] == AUDIENCE_RESULT


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"✓ {fn.__name__}")
    print(f"\n{len(fns)} passed")
