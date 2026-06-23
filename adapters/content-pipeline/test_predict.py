"""Unit tests for predict.py pure functions (no network, no secrets needed).

    python test_predict.py        # standalone
    pytest test_predict.py        # or via pytest
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import predict  # noqa: E402


def test_composite_weights():
    # all 5s → (5·1.5·3 + 5·1.0·3) / 7.5 = 37.5 / 7.5 = 5.0
    assert predict.compute_composite({"H": 5, "S": 5, "N": 5, "A": 5, "T": 5, "B": 5}) == 5.0
    # all 10s → ceiling
    assert predict.compute_composite({"H": 10, "S": 10, "N": 10, "A": 10, "T": 10, "B": 10}) == 10.0
    # draft 14's real blind scores → 6.87 (the seeded ledger value)
    assert predict.compute_composite({"H": 8, "S": 8, "N": 3, "A": 9, "T": 8, "B": 6}) == 6.87


def test_bucket_boundaries():
    assert predict.bucket_of(66_700) == "30k+"
    assert predict.bucket_of(30_000) == "30k+"
    assert predict.bucket_of(29_999) == "12–30k"
    assert predict.bucket_of(12_000) == "12–30k"
    assert predict.bucket_of(11_999) == "4–12k"
    assert predict.bucket_of(4_000) == "4–12k"
    assert predict.bucket_of(3_999) == "<4k"
    assert predict.bucket_of(0) == "<4k"


def test_canonical_bucket_normalizes_dashes():
    canon_mid = predict.bucket_of(13_291)  # "12–30k" — en-dash sourced from source-of-truth
    # hyphen-minus and em-dash both fold to the canonical en-dash
    assert predict._canonical_bucket("12-30k") == canon_mid
    assert predict._canonical_bucket("12—30k") == canon_mid  # — = em-dash
    # already-canonical and dashless labels pass through untouched
    assert predict._canonical_bucket(canon_mid) == canon_mid
    assert predict._canonical_bucket("30k+") == "30k+"
    assert predict._canonical_bucket("<4k") == "<4k"
    # a missing label is tolerated, not coerced
    assert predict._canonical_bucket(None) is None


def test_verdict_dash_insensitive():
    # Regression for the 2026-06-24 settle: draft 16 / post 19 reached 13,291 impressions —
    # a genuine 12–30k hit — but the stored predicted_bucket used a hyphen-minus ("12-30k")
    # instead of the canonical en-dash. The old retro() recorded "miss" for it (and lost the
    # under/over-predicted distinction) because == failed and LABELS.index() raised ValueError.
    # _verdict() must settle hyphen-typed labels identically to their en-dash twins.
    mid_high = predict.bucket_of(13_291)  # "12–30k" — canonical en-dash, straight from source
    mid_low = predict.bucket_of(5_000)    # "4–12k"  — ditto, no hand-typed dash to get wrong

    # hit: same bucket, only the dash differs
    assert predict._verdict(mid_high, "12-30k") == "hit"
    assert predict._verdict(mid_low, "4-12k") == "hit"
    # under-predicted: bet the lower bucket (hyphen), reality landed higher
    assert predict._verdict(mid_high, "4-12k") == "under-predicted"
    # over-predicted: bet the higher bucket (hyphen), reality landed lower
    assert predict._verdict(mid_low, "12-30k") == "over-predicted"
    # canonical labels keep settling exactly as before
    assert predict._verdict(mid_high, mid_high) == "hit"
    assert predict._verdict(mid_low, mid_high) == "over-predicted"


if __name__ == "__main__":
    test_composite_weights()
    test_bucket_boundaries()
    test_canonical_bucket_normalizes_dashes()
    test_verdict_dash_insensitive()
    print("✓ all predict.py unit tests passed")
