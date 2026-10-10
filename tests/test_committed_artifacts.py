"""Consistency checks for the checked-in partial main-run deliverables."""

import hashlib
import json
from collections import Counter
from pathlib import Path

from fundo_reviewer.cache import BatchReviewCache, batch_identity
from fundo_reviewer.data import load_input
from fundo_reviewer.legacy import label_transactions
from fundo_reviewer.provider import build_batch_request
from fundo_reviewer.reviewer import build_request


ROOT = Path(__file__).resolve().parents[1]


def _canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def test_checked_in_main_reports_and_partial_cache_are_consistent():
    input_path = ROOT / "data/transactions/main_90_days.json"
    report_dir = ROOT / "reports/main"
    manifest = json.loads((report_dir / "run_manifest.json").read_text())
    outcomes = json.loads((report_dir / "review_outcomes.json").read_text())
    credit = json.loads((report_dir / "credit_report.json").read_text())
    quality = json.loads((ROOT / "reports/evaluation/quality_report.json").read_text())

    assert manifest["input_sha256"] == hashlib.sha256(input_path.read_bytes()).hexdigest()
    assert manifest["review_outcomes_sha256"] == hashlib.sha256(
        (report_dir / "review_outcomes.json").read_bytes()
    ).hexdigest()
    assert manifest["credit_report_sha256"] == hashlib.sha256(
        (report_dir / "credit_report.json").read_bytes()
    ).hexdigest()

    statuses = Counter(outcome["review_status"] for outcome in outcomes)
    assert len(outcomes) == manifest["accepted_transactions"]
    assert dict(sorted(statuses.items())) == manifest["review_status_counts"]
    assert manifest["degraded_count"] == sum(
        count for status, count in statuses.items() if status not in {"kept", "changed"}
    )
    assert manifest["flag_count"] == sum(outcome["flag"] for outcome in outcomes)

    normalized = load_input(input_path)
    labels = {label.transaction_id: label for label in label_transactions(normalized.transactions)}
    batch_size = manifest["batch_size"]
    expected_identities = []
    for offset in range(0, len(normalized.transactions), batch_size):
        chunk = normalized.transactions[offset:offset + batch_size]
        requests = tuple(build_request(item, labels[item.transaction_id]) for item in chunk)
        batch = build_batch_request(requests)
        identity = batch_identity(requests, manifest["model"], batch.system_prompt, batch.user_prompt)
        expected_identities.append((identity, len(chunk)))

    cache = BatchReviewCache(ROOT / "cache/batch_reviews.jsonl")
    cached_by_identity = {_canonical(entry["identity"]): entry for entry in cache.entries.values()}
    matched = [
        (cached_by_identity[_canonical(identity)], rows)
        for identity, rows in expected_identities
        if _canonical(identity) in cached_by_identity
    ]
    assert manifest["cache_batch_hits"] == len(matched)
    assert manifest["cache_hits"] == sum(rows for _, rows in matched)

    assert sum(business["reviewed"]["transaction_count"] for business in credit["businesses"]) == len(outcomes)
    assert quality["input_sha256"] == manifest["input_sha256"]
    scope = quality["review_quality_by_scope"]
    assert scope["model_reviewed"]["counts"]["transactions"] == statuses["kept"] + statuses["changed"]
    assert scope["degraded_fallback"]["counts"]["transactions"] == manifest["degraded_count"]
    assert quality["counts"]["transactions"] == len(outcomes)
