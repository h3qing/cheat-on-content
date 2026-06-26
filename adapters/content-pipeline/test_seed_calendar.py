"""Unit tests for seed_calendar pure logic (no DB)."""
import datetime as dt

import seed_calendar as sc


def test_upcoming_posting_days_are_tue_thu():
    # 2026-06-29 is a Monday.
    days = sc.upcoming_posting_days(dt.date(2026, 6, 29), weeks=2)
    assert days == ["2026-06-30", "2026-07-02", "2026-07-07", "2026-07-09"]
    for d in days:
        assert dt.date.fromisoformat(d).weekday() in sc.POSTING_DAYS


def test_window_size_scales_with_weeks():
    # Two posting days (Tue/Thu) per week.
    assert len(sc.upcoming_posting_days(dt.date(2026, 6, 29), weeks=4)) == 8


def test_seed_from_pillar_shape():
    row = sc._seed_from_pillar("2026-07-02", "Framework", "A mental model.")
    assert row["scheduled_for"] == "2026-07-02"
    assert row["status"] == "draft"
    assert row["topic"] == "Framework"
    assert row["source_signal_ids"] is None
    assert "Replace with your post" in row["body"]
    assert "—" not in row["body"]  # no em-dash -> won't trip the draft em-dash flag


def test_seed_from_signal_links_signal():
    s = {"id": 7, "theme": "AI", "title": "Big news", "summary": "Details", "url": "http://x", "source_name": "src"}
    row = sc._seed_from_signal("2026-07-07", s)
    assert row["source_signal_ids"] == [7]
    assert row["hook"] == "Big news"
    assert row["topic"] == "AI"
    assert row["scheduled_for"] == "2026-07-07"
    assert "—" not in row["body"]


def test_pillars_have_no_emdash():
    for label, prompt in sc.EVERGREEN_PILLARS:
        assert "—" not in label and "—" not in prompt
