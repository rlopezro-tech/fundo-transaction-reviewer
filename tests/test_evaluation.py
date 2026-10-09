"""Ticket 07: strict synthetic joins and reproducible financial sensitivity."""

import json
import hashlib
from decimal import Decimal
from pathlib import Path

import pytest

from fundo_reviewer.cli import run_pipeline
from fundo_reviewer.data import load_input
from fundo_reviewer.evaluation import (
    SENSITIVITY_SEED, build_sensitivity_report, load_truth, run_evaluation,
)
from fundo_reviewer.reviewer import ProviderReply


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "data" / "transactions" / "main_90_days.json"
TRUTH = ROOT / "data" / "ground_truth" / "main_90_days.json"


class _KeepBatch:
    def review_batch(self, batch):
        return ProviderReply("completed", parsed=[{
            "transaction_id": request.transaction.transaction_id,
            "decision": "keep", "group": request.legacy.group,
            "status": request.legacy.status, "confidence": 0.7,
            "reason": "Kept existing synthetic label",
        } for request in batch.requests], raw_response={"synthetic_test_provider": True},
                             usage={"input_tokens": 200, "output_tokens": 100})


def _target(report, name):
    return next(item for item in report["targeted_cases"] if item["case"] == name)


def _selected_business(case):
    return next(item for item in case["businesses"] if item["selected_count"])


def test_seeded_sensitivity_counts_ids_and_financial_directions(tmp_path):
    normalized = load_input(MAIN)
    records, labels, _ = load_truth(normalized, TRUTH)
    first = build_sensitivity_report(normalized, records, labels)
    second = build_sensitivity_report(normalized, records, labels)
    assert first == second
    assert first["seed"] == SENSITIVITY_SEED
    assert [item["selected_count"] for item in first["random_cases"]] == [40, 100, 200]
    assert [len(item["selected"]) for item in first["random_cases"]] == [40, 100, 200]
    ids = [{item["transaction_id"] for item in case["selected"]} for case in first["random_cases"]]
    assert ids[0] < ids[1] < ids[2]
    assert all(item["truth"] != item["alternative"] for case in first["random_cases"] for item in case["selected"])

    assert Decimal(_selected_business(_target(first, "false_revenue_high_dollar"))["offer_delta_usd"]) > 0
    assert Decimal(_selected_business(_target(first, "missed_revenue_high_dollar"))["offer_delta_usd"]) < 0
    false_repayment = _selected_business(_target(first, "false_active_advance_repayment"))
    missed_repayment = _selected_business(_target(first, "missed_active_advance_repayment"))
    assert Decimal(false_repayment["daily_funder_payment_delta_usd"]) > 0
    assert Decimal(false_repayment["offer_delta_usd"]) < 0
    assert Decimal(missed_repayment["daily_funder_payment_delta_usd"]) < 0
    assert Decimal(missed_repayment["offer_delta_usd"]) > 0
    five_to_six = _selected_business(_target(first, "nsf_five_to_six"))
    six_to_five = _selected_business(_target(first, "nsf_six_to_five"))
    assert (five_to_six["nsf_count_before"], five_to_six["nsf_count_after"], five_to_six["offer_after_usd"]) == (5, 6, "0.00")
    assert (six_to_five["nsf_count_before"], six_to_five["nsf_count_after"], six_to_five["offer_before_usd"]) == (6, 5, "0.00")


def test_truth_join_rejects_missing_extra_ids_and_inconsistent_revenue(tmp_path):
    normalized = load_input(MAIN)
    source = json.loads(TRUTH.read_text())
    missing = dict(source)
    missing["labels"] = dict(source["labels"])
    missing["labels"].pop(next(iter(missing["labels"])))
    path = tmp_path / "truth.json"
    path.write_text(json.dumps(missing))
    with pytest.raises(ValueError, match="truth ID join mismatch"):
        load_truth(normalized, path)
    corrupted = dict(source)
    corrupted["labels"] = dict(source["labels"])
    tid = next(iter(corrupted["labels"]))
    corrupted["labels"][tid] = {**corrupted["labels"][tid],
                                 "revenue_eligible": not corrupted["labels"][tid]["revenue_eligible"]}
    path.write_text(json.dumps(corrupted))
    with pytest.raises(ValueError, match="truth revenue inconsistent"):
        load_truth(normalized, path)


def test_full_synthetic_evaluation_accounts_for_every_id_and_detects_tampering(tmp_path):
    review_dir = tmp_path / "review"
    cache = tmp_path / "cache.jsonl"
    ledger = tmp_path / "spend.jsonl"
    run_pipeline(MAIN, review_dir, "online", cache, ledger, provider=_KeepBatch(), batch_size=80)
    result = run_evaluation(MAIN, TRUTH, review_dir, tmp_path / "evaluation")
    quality = json.loads((tmp_path / "evaluation" / "quality_report.json").read_text())
    assert result["transactions_evaluated"] == 2000
    assert quality["counts"]["transactions"] == 2000
    assert len(quality["businesses"]) == 10
    assert all("legacy_signed" in item["amr_error_usd"] and "reviewed_absolute" in item["amr_error_usd"]
               for item in quality["businesses"])
    assert quality["counts"]["hard_negatives"] > 0
    assert quality["counts"]["hard_negative_false_flags"] == 0
    assert quality["counts"]["true_corrections"] == 0
    assert quality["counts"]["missed_mistakes"] > 0
    assert quality["representative_examples"]
    assert "ground_truth" not in cache.read_text()
    assert "scenario_id" not in cache.read_text()

    outcomes = json.loads((review_dir / "review_outcomes.json").read_text())
    (review_dir / "review_outcomes.json").write_text(json.dumps(outcomes[:-1]))
    with pytest.raises(ValueError, match="review outcomes hash"):
        run_evaluation(MAIN, TRUTH, review_dir, tmp_path / "bad")
    outcomes.append(outcomes[0])
    outcomes_path = review_dir / "review_outcomes.json"
    outcomes_path.write_text(json.dumps(outcomes))
    manifest_path = review_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["review_outcomes_sha256"] = hashlib.sha256(outcomes_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="duplicate review outcome"):
        run_evaluation(MAIN, TRUTH, review_dir, tmp_path / "duplicate")


def test_sensitivity_only_never_claims_review_accuracy(tmp_path):
    result = run_evaluation(MAIN, TRUTH, None, tmp_path / "sensitivity_only")
    assert result == {"sensitivity_cases": 9}
    assert not (tmp_path / "sensitivity_only" / "quality_report.json").exists()
    report = json.loads((tmp_path / "sensitivity_only" / "sensitivity_report.json").read_text())
    assert report["measurement_type"].startswith("simulated_sensitivity")
