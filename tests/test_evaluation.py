"""Tests for strict synthetic joins and reproducible financial sensitivity."""

import json
import hashlib
from decimal import Decimal
from pathlib import Path

import pytest

import fundo_reviewer.evaluation as evaluation_module
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
    dataset = load_truth(normalized, TRUTH)
    records, labels = dataset.records, dataset.labels
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
    assert quality["review_quality_by_scope"]["model_reviewed"]["counts"]["transactions"] == 2000
    assert quality["review_quality_by_scope"]["degraded_fallback"]["counts"]["transactions"] == 0
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


def test_checked_in_partial_run_partitions_model_and_fallback_metrics(tmp_path):
    run_evaluation(MAIN, TRUTH, ROOT / "reports" / "main", tmp_path / "partial-evaluation")
    quality = json.loads((tmp_path / "partial-evaluation" / "quality_report.json").read_text())
    scopes = quality["review_quality_by_scope"]
    model = scopes["model_reviewed"]
    fallback = scopes["degraded_fallback"]
    assert model["counts"]["transactions"] + fallback["counts"]["transactions"] == 2000
    assert sum(model["review_status_counts"].values()) == model["counts"]["transactions"]
    assert sum(fallback["review_status_counts"].values()) == fallback["counts"]["transactions"]
    assert fallback["counts"]["reviewed_group_status_correct"] == fallback["counts"]["legacy_group_status_correct"]
    for business in quality["businesses"]:
        covered = sum(scopes[scope]["by_business"][business["business_id"]]["transactions"]
                      for scope in ("model_reviewed", "degraded_fallback"))
        assert covered == business["label_counts"]["transactions"]


def test_quality_report_hashes_exact_truth_snapshot_used(tmp_path, monkeypatch):
    truth_path = tmp_path / "truth.json"
    original_truth = TRUTH.read_bytes()
    truth_path.write_bytes(original_truth)
    original_builder = evaluation_module.build_sensitivity_report

    def mutate_truth_after_validation(*args):
        report = original_builder(*args)
        truth_path.write_bytes(original_truth + b"\n")
        return report

    monkeypatch.setattr(evaluation_module, "build_sensitivity_report", mutate_truth_after_validation)
    run_evaluation(MAIN, truth_path, ROOT / "reports" / "main", tmp_path / "evaluation")

    quality = json.loads((tmp_path / "evaluation" / "quality_report.json").read_text())
    assert quality["truth_sha256"] == hashlib.sha256(original_truth).hexdigest()
    assert hashlib.sha256(truth_path.read_bytes()).hexdigest() != quality["truth_sha256"]


def test_sensitivity_only_never_claims_review_accuracy(tmp_path):
    result = run_evaluation(MAIN, TRUTH, None, tmp_path / "sensitivity_only")
    assert result == {"sensitivity_cases": 9}
    assert not (tmp_path / "sensitivity_only" / "quality_report.json").exists()
    report = json.loads((tmp_path / "sensitivity_only" / "sensitivity_report.json").read_text())
    assert report["measurement_type"].startswith("simulated_sensitivity")
