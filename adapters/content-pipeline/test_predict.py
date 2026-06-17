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


if __name__ == "__main__":
    test_composite_weights()
    test_bucket_boundaries()
    print("✓ all predict.py unit tests passed")
