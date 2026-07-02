"""Blind-prediction + retro I/O for the LinkedIn flywheel → Supabase `predictions` ledger.

The JUDGMENT (the 0–10 dimension scores) lives with Claude reading the draft against
~/linkedin-tracker/rubric.md — exactly like store.py keeps relevance/voice judgment with
Claude. This CLI is only the immutable write + the T+Nd settle. It mirrors
cheat-on-content's predict→retro lifecycle onto Megaphone's `predictions` table so the
dashboard's Calibration view can read predicted-vs-actual.

    # 1) blind bet — written BEFORE publish, immutable once in (principle #1):
    CHEAT_PROJECT_ROOT=~/linkedin-tracker ~/linkedin-tracker/.venv/bin/python predict.py predict bet.json
    #    bet.json: {"post_idea_id": 14, "dimension_scores": {"H":8,"S":8,"N":3,"A":9,"T":8,"B":6},
    #               "predicted_bucket": "12–30k", "rubric_version": "v0", "notes": "..."}
    #    (pass "-" to read JSON from stdin)

    # 2) settle at T+Nd against the post's latest engagement snapshot:
    ... predict.py retro <post_idea_id>

    # 3) read the ledger:
    ... predict.py list
"""
from __future__ import annotations

import datetime as dt
import json
import sys

import store  # reuse the same .cheat-secrets.json client/secrets the pipeline already uses

# rubric.md v0 weights — keep in sync with ~/linkedin-tracker/rubric.md
RUBRIC_WEIGHTS = {"H": 1.5, "S": 1.5, "N": 1.5, "A": 1.0, "T": 1.0, "B": 1.0}
DENOM = 7.5
# reach buckets, highest first — labels are canonical (en-dash), shared by predict + retro
BUCKETS = [(30_000, "30k+"), (12_000, "12–30k"), (4_000, "4–12k"), (0, "<4k")]
LABELS = [b[1] for b in BUCKETS]


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def compute_composite(scores: dict) -> float:
    missing = [k for k in RUBRIC_WEIGHTS if k not in scores]
    if missing:
        raise SystemExit(f"❌ dimension_scores missing {missing} (need {list(RUBRIC_WEIGHTS)})")
    for k, w in RUBRIC_WEIGHTS.items():
        if not (0 <= float(scores[k]) <= 10):
            raise SystemExit(f"❌ {k}={scores[k]} out of 0–10")
    return round(sum(float(scores[k]) * w for k, w in RUBRIC_WEIGHTS.items()) / DENOM, 2)


def bucket_of(impressions: int) -> str:
    for floor, label in BUCKETS:
        if impressions >= floor:
            return label
    return "<4k"


def bucket_for_composite(composite: float) -> str:
    """rubric.md「Predicted reach buckets」表：composite → 预测档。跟 RUBRIC_WEIGHTS 一样
    与 rubric.md 手工同步（改表时两边一起改）。"""
    if composite >= 7.5:
        return "30k+"
    if composite >= 6.0:
        return "12–30k"
    if composite >= 4.8:
        return "4–12k"
    return "<4k"


def _canonical_bucket(label):
    """Normalize dash variants (hyphen-minus, em-dash) to the canonical en-dash used in
    BUCKETS, so a hyphen-typed "12-30k" settles identically to the canonical "12–30k".
    Returns the input unchanged when it's falsy (e.g. a missing/None label)."""
    return label.replace("-", "–").replace("—", "–") if label else label


def _verdict(actual_bucket: str, pred_bucket) -> str:
    """Settle an actual reach bucket against a predicted one, returning hit /
    under-predicted / over-predicted (or "miss" if a label isn't recognized). Dash-insensitive:
    a hyphen-typed predicted_bucket settles identically to its canonical en-dash twin."""
    actual_bucket = _canonical_bucket(actual_bucket)
    pred_bucket = _canonical_bucket(pred_bucket)
    try:
        return "hit" if actual_bucket == pred_bucket else (
            "under-predicted" if LABELS.index(actual_bucket) < LABELS.index(pred_bucket) else "over-predicted"
        )
    except ValueError:
        return "hit" if actual_bucket == pred_bucket else "miss"


def predict(bet: dict) -> dict:
    """Write one immutable blind prediction. Refuses to re-predict the same idea under the
    same rubric_version (principle #1: a prediction is written once, never rewritten)."""
    pid = bet["post_idea_id"]
    version = bet.get("rubric_version", "v0")
    client = store._client()
    dupe = (
        client.table("predictions")
        .select("id")
        .eq("post_idea_id", pid)
        .eq("rubric_version", version)
        .execute()
        .data
    )
    if dupe:
        raise SystemExit(
            f"❌ prediction already exists for post_idea {pid} @ rubric {version} "
            f"(id={dupe[0]['id']}). Predictions are immutable — bump to a new rubric_version to re-score."
        )
    composite = compute_composite(bet["dimension_scores"])
    row = {
        "post_idea_id": pid,
        "rubric_version": version,
        "dimension_scores": bet["dimension_scores"],
        "composite": composite,
        "predicted_bucket": _canonical_bucket(bet.get("predicted_bucket")) or bucket_for_composite(composite),
        "predicted_at": _now(),
        "notes": bet.get("notes"),
    }
    data = client.table("predictions").insert(row).execute().data
    return {"id": (data or [{}])[0].get("id"), "composite": composite, "bucket": row["predicted_bucket"]}


def retro(post_idea_id: int) -> dict:
    """Settle the open prediction for an idea against its post's latest engagement snapshot."""
    client = store._client()
    preds = (
        client.table("predictions")
        .select("*")
        .eq("post_idea_id", post_idea_id)
        .is_("retro_at", "null")
        .order("predicted_at", desc=True)
        .execute()
        .data
    )
    if not preds:
        raise SystemExit(f"❌ no open (un-settled) prediction for post_idea {post_idea_id}")
    pred = preds[0]

    idea = client.table("post_ideas").select("posted_post_id").eq("id", post_idea_id).execute().data
    post_id = (idea or [{}])[0].get("posted_post_id")
    if not post_id:
        raise SystemExit(
            f"❌ post_idea {post_idea_id} has no posted_post_id — register the published post first "
            f"(insert a posts row + link it), else there's nothing to settle against."
        )

    snaps = (
        client.table("engagement_snapshots")
        .select("impressions,captured_at")
        .eq("post_id", post_id)
        .not_.is_("impressions", "null")
        .order("captured_at", desc=True)
        .execute()
        .data
    )
    if not snaps:
        raise SystemExit(f"❌ no engagement snapshot with impressions yet for post {post_id} — wait for capture.")
    actual = int(snaps[0]["impressions"])
    actual_bucket = bucket_of(actual)
    pred_bucket = _canonical_bucket(pred.get("predicted_bucket"))
    verdict = _verdict(actual_bucket, pred_bucket)
    client.table("predictions").update(
        {"actual_impressions": actual, "retro_at": _now(), "verdict": verdict, "post_id": post_id}
    ).eq("id", pred["id"]).execute()
    return {
        "prediction_id": pred["id"], "predicted_bucket": pred_bucket, "composite": pred.get("composite"),
        "actual_impressions": actual, "actual_bucket": actual_bucket, "verdict": verdict,
    }


def list_predictions() -> list[dict]:
    return (
        store._client()
        .table("predictions")
        .select("id,post_idea_id,rubric_version,composite,predicted_bucket,actual_impressions,verdict,predicted_at")
        .order("predicted_at", desc=True)
        .execute()
        .data
        or []
    )


def _load(path: str):
    return json.loads(sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read())


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "predict":
        print(json.dumps(predict(_load(sys.argv[2])), ensure_ascii=False))
    elif cmd == "retro":
        print(json.dumps(retro(int(sys.argv[2])), ensure_ascii=False))
    elif cmd == "list":
        for r in list_predictions():
            print(r)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
