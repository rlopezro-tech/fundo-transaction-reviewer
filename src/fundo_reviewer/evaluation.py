"""Ticket 07: separate synthetic-truth evaluation and seeded mislabel sensitivity.

This module is deliberately not imported by the reviewer CLI or provider.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from fundo_reviewer.credit import (
    FEATURE_POLICY_VERSION, OFFER_POLICY_VERSION, CreditLabel, calculate_offer,
    compute_features, feature_record,
)
from fundo_reviewer.data import NormalizedInput, load_input
from fundo_reviewer.legacy import LegacyLabel, label_transactions
from fundo_reviewer.revenue import ALLOWED_GROUPS, is_revenue_eligible
from fundo_reviewer.reviewer import build_request, validate_proposal


EVALUATION_VERSION = "synthetic-evaluation-v1"
SENSITIVITY_VERSION = "valid-alternative-sensitivity-v1"
SENSITIVITY_SEED = 20261009
RATES = (2, 5, 10)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _label(transaction_id: str, record: Mapping[str, Any]) -> CreditLabel:
    group, status = record.get("group"), record.get("status")
    if group not in ALLOWED_GROUPS or status not in {"business", "personal"}:
        raise ValueError(f"invalid semantic label for {transaction_id}")
    return CreditLabel(transaction_id, group, status)


def load_truth(normalized: NormalizedInput, path: Path) -> tuple[dict[str, dict], dict[str, CreditLabel], dict]:
    data = _json(path)
    if not isinstance(data, dict) or not isinstance(data.get("labels"), dict):
        raise ValueError("synthetic truth must have an ID-keyed labels object")
    if data.get("as_of") != normalized.as_of.isoformat():
        raise ValueError("truth as_of does not match input")
    records = data["labels"]
    expected = {transaction.transaction_id for transaction in normalized.transactions}
    if set(records) != expected:
        raise ValueError(f"truth ID join mismatch: missing={len(expected - set(records))}, extra={len(set(records) - expected)}")
    labels = {}
    for transaction in normalized.transactions:
        record = records[transaction.transaction_id]
        if not isinstance(record, dict):
            raise ValueError(f"truth for {transaction.transaction_id} is not an object")
        label = _label(transaction.transaction_id, record)
        calculated = is_revenue_eligible(transaction.amount, group=label.group, status=label.status)
        if type(record.get("revenue_eligible")) is not bool or record["revenue_eligible"] != calculated:
            raise ValueError(f"truth revenue inconsistent with code policy for {transaction.transaction_id}")
        if type(record.get("hard_negative")) is not bool or type(record.get("ambiguous")) is not bool:
            raise ValueError(f"truth hard_negative/ambiguous metadata missing for {transaction.transaction_id}")
        if "alternative_label" in record:
            alternative = _label(transaction.transaction_id, record["alternative_label"])
            if alternative == label:
                raise ValueError(f"truth alternative label does not differ for {transaction.transaction_id}")
        labels[transaction.transaction_id] = label
    return records, labels, data


def _legacy_labels(normalized: NormalizedInput) -> tuple[tuple[LegacyLabel, ...], dict[str, CreditLabel]]:
    results = label_transactions(normalized.transactions)
    return results, {
        item.transaction_id: CreditLabel(item.transaction_id, item.group, item.status)
        for item in results
    }


def load_reviewed(
    normalized: NormalizedInput, input_path: Path, review_dir: Path,
    legacy_labels: tuple[LegacyLabel, ...],
) -> tuple[dict[str, dict], dict[str, CreditLabel], dict]:
    manifest = _json(review_dir / "run_manifest.json")
    digest = hashlib.sha256(input_path.read_bytes()).hexdigest()
    if manifest.get("input_sha256") != digest or manifest.get("accepted_transactions") != len(normalized.transactions):
        raise ValueError("review manifest input hash or count does not match evaluation input")
    outcomes_path = review_dir / "review_outcomes.json"
    if manifest.get("review_outcomes_sha256") != hashlib.sha256(outcomes_path.read_bytes()).hexdigest():
        raise ValueError("review outcomes hash does not match run manifest")
    records_list = _json(outcomes_path)
    if not isinstance(records_list, list):
        raise ValueError("review outcomes must be a list")
    records = {}
    for record in records_list:
        if not isinstance(record, dict) or not isinstance(record.get("transaction_id"), str):
            raise ValueError("review outcome has no transaction ID")
        transaction_id = record["transaction_id"]
        if transaction_id in records:
            raise ValueError(f"duplicate review outcome {transaction_id}")
        records[transaction_id] = record
    expected = {item.transaction_id for item in normalized.transactions}
    if set(records) != expected:
        raise ValueError(f"review ID join mismatch: missing={len(expected - set(records))}, extra={len(set(records) - expected)}")
    labels = {}
    for transaction, legacy in zip(normalized.transactions, legacy_labels, strict=True):
        record = records[transaction.transaction_id]
        baseline = record.get("legacy")
        if (not isinstance(baseline, dict) or baseline.get("group") != legacy.group
                or baseline.get("status") != legacy.status
                or baseline.get("revenue_eligible") != legacy.revenue_eligible
                or baseline.get("matched_rule_ids") != list(legacy.matched_rule_ids)
                or baseline.get("personal_rule_ids") != list(legacy.personal_rule_ids)):
            raise ValueError(f"review legacy evidence mismatch for {transaction.transaction_id}")
        final = record.get("final")
        if not isinstance(final, dict):
            raise ValueError(f"missing final label for {transaction.transaction_id}")
        label = _label(transaction.transaction_id, final)
        if final.get("revenue_eligible") != is_revenue_eligible(
            transaction.amount, group=label.group, status=label.status
        ):
            raise ValueError(f"review revenue mismatch for {transaction.transaction_id}")
        status = record.get("review_status")
        if status in {"kept", "changed"}:
            proposal = validate_proposal(record.get("proposal"), build_request(transaction, legacy))
            if (label.group, label.status) != (proposal.group, proposal.status):
                raise ValueError(f"review final/proposal mismatch for {transaction.transaction_id}")
            if status != ("changed" if proposal.decision == "change" else "kept") or record.get("flag") is not (status == "changed"):
                raise ValueError(f"review status/flag mismatch for {transaction.transaction_id}")
        elif status in {"invalid_response", "refused", "incomplete", "provider_failure"}:
            if (label.group, label.status) != (legacy.group, legacy.status) or record.get("flag") is not False or record.get("proposal") is not None:
                raise ValueError(f"degraded review cannot alter label for {transaction.transaction_id}")
        else:
            raise ValueError(f"unknown review status for {transaction.transaction_id}")
        labels[transaction.transaction_id] = label
    if dict(sorted(Counter(record["review_status"] for record in records.values()).items())) != manifest.get("review_status_counts"):
        raise ValueError("review manifest status counts do not match outcomes")
    return records, labels, manifest


def _d(value: Decimal | int) -> str:
    return str(value)


def _offer_delta(after, before) -> str:
    return _d(calculate_offer(after).final - calculate_offer(before).final)


def _marginal_effect(
    normalized: NormalizedInput, base: dict[str, CreditLabel], transaction_id: str,
    alternative: CreditLabel,
) -> dict:
    transaction = next(item for item in normalized.transactions if item.transaction_id == transaction_id)
    original = base[transaction_id]
    coverage = next(item for item in normalized.business_coverage if item.business_id == transaction.business_id)
    old_revenue = is_revenue_eligible(transaction.amount, group=original.group, status=original.status)
    new_revenue = is_revenue_eligible(transaction.amount, group=alternative.group, status=alternative.status)
    revenue_delta = (-transaction.amount if new_revenue else Decimal(0)) - (
        -transaction.amount if old_revenue else Decimal(0)
    )
    changed = dict(base)
    changed[transaction_id] = alternative
    before = compute_features(normalized, base)[transaction.business_id]
    after = compute_features(normalized, changed)[transaction.business_id]
    return {
        "revenue_delta_usd": _d(revenue_delta),
        "amr_delta_usd": _d(revenue_delta * Decimal(30) / Decimal(coverage.days)),
        "daily_funder_payment_delta_usd": _d(after.other_funder_daily_payments - before.other_funder_daily_payments),
        "final_offer_delta_usd": _offer_delta(after, before),
        "nsf_count_delta": after.nsf_count - before.nsf_count,
    }


def _quality_report(
    normalized: NormalizedInput, input_path: Path, truth_path: Path,
    truth_records: dict[str, dict], truth: dict[str, CreditLabel], truth_data: dict,
    legacy: dict[str, CreditLabel], reviewed_records: dict[str, dict],
    reviewed: dict[str, CreditLabel], manifest: dict,
) -> dict:
    truth_features = compute_features(normalized, truth)
    legacy_features = compute_features(normalized, legacy)
    reviewed_features = compute_features(normalized, reviewed)
    categories: dict[str, list[str]] = {
        "false_changes": [], "missed_mistakes": [], "true_corrections": [],
        "changed_but_still_wrong": [], "hard_negative_false_flags": [],
    }
    counts = Counter()
    per_business = {coverage.business_id: Counter() for coverage in normalized.business_coverage}
    transaction_by_id = {item.transaction_id: item for item in normalized.transactions}
    for transaction in normalized.transactions:
        tid = transaction.transaction_id
        t, l, r = truth[tid], legacy[tid], reviewed[tid]
        record = reviewed_records[tid]
        legacy_correct = (l.group, l.status) == (t.group, t.status)
        reviewed_correct = (r.group, r.status) == (t.group, t.status)
        for target in (counts, per_business[transaction.business_id]):
            target["transactions"] += 1
            target["legacy_group_correct"] += l.group == t.group
            target["reviewed_group_correct"] += r.group == t.group
            target["legacy_status_correct"] += l.status == t.status
            target["reviewed_status_correct"] += r.status == t.status
            target["legacy_group_status_correct"] += legacy_correct
            target["reviewed_group_status_correct"] += reviewed_correct
            target["legacy_revenue_correct"] += is_revenue_eligible(transaction.amount, group=l.group, status=l.status) == truth_records[tid]["revenue_eligible"]
            target["reviewed_revenue_correct"] += is_revenue_eligible(transaction.amount, group=r.group, status=r.status) == truth_records[tid]["revenue_eligible"]
            target["flags"] += record["flag"]
            target["degraded"] += record["review_status"] not in {"kept", "changed"}
            target["hard_negatives"] += truth_records[tid]["hard_negative"]
            target["hard_negative_false_flags"] += truth_records[tid]["hard_negative"] and record["flag"] and not reviewed_correct
            target["ambiguous_scenarios"] += truth_records[tid]["ambiguous"]
            target["true_corrections"] += not legacy_correct and reviewed_correct
            target["missed_mistakes"] += not legacy_correct and not reviewed_correct and not record["flag"]
            target["false_changes"] += legacy_correct and not reviewed_correct and record["flag"]
            target["changed_but_still_wrong"] += not legacy_correct and not reviewed_correct and record["flag"]
        if not legacy_correct and reviewed_correct:
            categories["true_corrections"].append(tid)
        elif not legacy_correct and not reviewed_correct and record["flag"]:
            categories["changed_but_still_wrong"].append(tid)
        elif not legacy_correct and not reviewed_correct:
            categories["missed_mistakes"].append(tid)
        elif legacy_correct and not reviewed_correct and record["flag"]:
            categories["false_changes"].append(tid)
        if truth_records[tid]["hard_negative"] and record["flag"] and not reviewed_correct:
            categories["hard_negative_false_flags"].append(tid)
    examples = []
    for category, ids in categories.items():
        for tid in sorted(ids, key=lambda item: (-abs(transaction_by_id[item].amount), item))[:3]:
            transaction = transaction_by_id[tid]
            record = reviewed_records[tid]
            examples.append({
                "category": category, "transaction_id": tid, "business_id": transaction.business_id,
                "synthetic_description": transaction.name, "amount_usd": _d(transaction.amount),
                "legacy": {"group": legacy[tid].group, "status": legacy[tid].status},
                "reviewed": {"group": reviewed[tid].group, "status": reviewed[tid].status},
                "truth": {"group": truth[tid].group, "status": truth[tid].status},
                "scenario_id": truth_records[tid]["scenario_id"],
                "ambiguous": truth_records[tid]["ambiguous"],
                "review_reason": (record.get("proposal") or {}).get("reason"),
                "actual_reviewed_marginal_effect": _marginal_effect(normalized, legacy, tid, reviewed[tid]),
                "truth_correction_marginal_effect": _marginal_effect(normalized, legacy, tid, truth[tid]),
            })
    businesses = []
    for coverage in normalized.business_coverage:
        bid = coverage.business_id
        t, l, r = truth_features[bid], legacy_features[bid], reviewed_features[bid]
        businesses.append({
            "business_id": bid,
            "evaluation_split": truth_data["business_metadata"][bid]["evaluation_split"],
            "nsf_fee_observable": truth_data["business_metadata"][bid]["nsf_fee_observable"],
            "coverage_days": coverage.days,
            "label_counts": dict(sorted(per_business[bid].items())),
            "legacy": feature_record(l), "reviewed": feature_record(r), "truth": feature_record(t),
            "amr_error_usd": {
                "legacy_signed": _d(l.average_monthly_revenue - t.average_monthly_revenue),
                "legacy_absolute": _d(abs(l.average_monthly_revenue - t.average_monthly_revenue)),
                "reviewed_signed": _d(r.average_monthly_revenue - t.average_monthly_revenue),
                "reviewed_absolute": _d(abs(r.average_monthly_revenue - t.average_monthly_revenue)),
            },
            "offer_delta_usd": {
                "reviewed_minus_legacy": _offer_delta(r, l),
                "legacy_minus_truth": _offer_delta(l, t),
                "reviewed_minus_truth": _offer_delta(r, t),
            },
        })
    return {
        "measurement_type": "measured_against_independent_synthetic_scenario_intent_not_real_world_accuracy",
        "evaluation_version": EVALUATION_VERSION,
        "feature_policy_version": FEATURE_POLICY_VERSION,
        "offer_policy_version": OFFER_POLICY_VERSION,
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "truth_sha256": hashlib.sha256(truth_path.read_bytes()).hexdigest(),
        "review_manifest_input_sha256": manifest["input_sha256"],
        "counts": dict(sorted(counts.items())),
        "businesses": businesses,
        "representative_examples": examples,
        "aggregate_absolute_amr_error_usd": {
            "legacy": _d(sum((Decimal(item["amr_error_usd"]["legacy_absolute"]) for item in businesses), Decimal(0))),
            "reviewed": _d(sum((Decimal(item["amr_error_usd"]["reviewed_absolute"]) for item in businesses), Decimal(0))),
        },
        "limitations": [
            "Synthetic scenario intent is not verified real-world ground truth.",
            "Ambiguous bank descriptions cannot establish sales purpose, legal event, or failed payment.",
            "Self-reported model confidence is not calibrated probability.",
        ],
    }


def _error_type(transaction, truth: CreditLabel, alternative: CreditLabel) -> str:
    truth_revenue = is_revenue_eligible(transaction.amount, group=truth.group, status=truth.status)
    alt_revenue = is_revenue_eligible(transaction.amount, group=alternative.group, status=alternative.status)
    if not truth_revenue and alt_revenue:
        return "false_revenue"
    if truth_revenue and not alt_revenue:
        return "missed_revenue"
    truth_repay = transaction.amount > 0 and truth.group == "Active advance" and truth.status == "business"
    alt_repay = transaction.amount > 0 and alternative.group == "Active advance" and alternative.status == "business"
    if not truth_repay and alt_repay:
        return "false_active_advance_repayment"
    if truth_repay and not alt_repay:
        return "missed_active_advance_repayment"
    if truth.group == "NSFs" and alternative.group != "NSFs":
        return "missed_nsf_label"
    if truth.group != "NSFs" and alternative.group == "NSFs":
        return "false_nsf_label"
    return "other_valid_label_error"


def _sensitivity_case(
    normalized: NormalizedInput, truth: dict[str, CreditLabel], changes: dict[str, CreditLabel],
    case_name: str, metadata: dict,
) -> dict:
    transactions = {item.transaction_id: item for item in normalized.transactions}
    labels = dict(truth)
    labels.update(changes)
    before = compute_features(normalized, truth)
    after = compute_features(normalized, labels)
    selected = [{
        "transaction_id": tid, "business_id": transactions[tid].business_id,
        "amount_usd": _d(transactions[tid].amount),
        "error_type": _error_type(transactions[tid], truth[tid], changes[tid]),
        "truth": {"group": truth[tid].group, "status": truth[tid].status},
        "alternative": {"group": changes[tid].group, "status": changes[tid].status},
    } for tid in sorted(changes)]
    per_business = []
    for coverage in normalized.business_coverage:
        bid = coverage.business_id
        t, a = before[bid], after[bid]
        per_business.append({
            "business_id": bid,
            "selected_count": sum(item["business_id"] == bid for item in selected),
            "revenue_delta_usd": _d(a.eligible_revenue_total - t.eligible_revenue_total),
            "amr_delta_usd": _d(a.average_monthly_revenue - t.average_monthly_revenue),
            "revenue_to_deposits_delta": _d(a.revenue_to_deposits - t.revenue_to_deposits)
            if a.revenue_to_deposits is not None and t.revenue_to_deposits is not None else None,
            "nsf_count_before": t.nsf_count, "nsf_count_after": a.nsf_count,
            "overdraft_count_delta": a.overdraft_count - t.overdraft_count,
            "high_risk_debit_share_delta": _d(a.high_risk_debit_share - t.high_risk_debit_share)
            if a.high_risk_debit_share is not None and t.high_risk_debit_share is not None else None,
            "daily_funder_payment_delta_usd": _d(a.other_funder_daily_payments - t.other_funder_daily_payments),
            "offer_before_usd": _d(calculate_offer(t).final),
            "offer_after_usd": _d(calculate_offer(a).final),
            "offer_delta_usd": _offer_delta(a, t),
        })
    return {
        "case": case_name, **metadata, "selected_count": len(changes),
        "selected": selected,
        "error_type_counts": dict(sorted(Counter(item["error_type"] for item in selected).items())),
        "businesses": per_business,
        "aggregate_absolute_offer_movement_usd": _d(sum(
            (abs(Decimal(item["offer_delta_usd"])) for item in per_business), Decimal(0)
        )),
    }


def build_sensitivity_report(
    normalized: NormalizedInput, truth_records: dict[str, dict], truth: dict[str, CreditLabel],
) -> dict:
    transactions = {item.transaction_id: item for item in normalized.transactions}
    candidates = sorted(tid for tid, record in truth_records.items() if "alternative_label" in record)
    if len(candidates) < round(len(transactions) * max(RATES) / 100):
        raise ValueError("not enough valid alternative-label scenarios for requested rates")
    rng = random.Random(SENSITIVITY_SEED)
    rng.shuffle(candidates)
    random_cases = []
    for rate in RATES:
        count = round(len(transactions) * rate / 100)
        ids = candidates[:count]
        changes = {tid: _label(tid, truth_records[tid]["alternative_label"]) for tid in ids}
        random_cases.append(_sensitivity_case(normalized, truth, changes, f"random_{rate}_percent", {
            "nominal_rate_percent": rate,
            "actual_rate_percent": _d(Decimal(count) * Decimal(100) / Decimal(len(transactions))),
            "count_rounding": "Python round to nearest integer, ties to even",
            "sampling_pool": "only truth scenarios with a documented valid alternative label",
        }))
    def largest(predicate):
        matches = [item for item in normalized.transactions if predicate(item)]
        if not matches:
            raise ValueError("targeted sensitivity case has no eligible transaction")
        return max(matches, key=lambda item: (abs(item.amount), item.transaction_id))

    false_revenue = largest(lambda item: item.amount < 0 and not truth_records[item.transaction_id]["revenue_eligible"]
                            and "alternative_label" in truth_records[item.transaction_id]
                            and is_revenue_eligible(item.amount, **truth_records[item.transaction_id]["alternative_label"]))
    missed_revenue = largest(lambda item: item.amount < 0 and truth_records[item.transaction_id]["revenue_eligible"]
                             and "alternative_label" in truth_records[item.transaction_id]
                             and not is_revenue_eligible(item.amount, **truth_records[item.transaction_id]["alternative_label"]))
    false_repayment = largest(lambda item: item.amount > 0 and truth[item.transaction_id].group == "unmatched"
                              and truth[item.transaction_id].status == "business"
                              and truth_records[item.transaction_id]["scenario_id"] == "capital_equipment")
    missed_repayment = largest(lambda item: item.amount > 0 and truth[item.transaction_id].group == "Active advance"
                               and truth[item.transaction_id].status == "business")
    biz01_non_nsf = largest(lambda item: item.business_id == "biz_01" and item.amount > 0
                            and truth[item.transaction_id].group != "NSFs")
    biz02_nsf = largest(lambda item: item.business_id == "biz_02" and truth[item.transaction_id].group == "NSFs")
    targeted_specs = (
        ("false_revenue_high_dollar", false_revenue, _label(false_revenue.transaction_id, truth_records[false_revenue.transaction_id]["alternative_label"])),
        ("missed_revenue_high_dollar", missed_revenue, _label(missed_revenue.transaction_id, truth_records[missed_revenue.transaction_id]["alternative_label"])),
        ("false_active_advance_repayment", false_repayment, CreditLabel(false_repayment.transaction_id, "Active advance", "business")),
        ("missed_active_advance_repayment", missed_repayment, CreditLabel(missed_repayment.transaction_id, "unmatched", "business")),
        ("nsf_five_to_six", biz01_non_nsf, CreditLabel(biz01_non_nsf.transaction_id, "NSFs", "business")),
        ("nsf_six_to_five", biz02_nsf, CreditLabel(biz02_nsf.transaction_id, "unmatched", "business")),
    )
    targeted = [_sensitivity_case(normalized, truth, {transaction.transaction_id: alternative}, case, {
        "nominal_rate_percent": None, "selection": "targeted synthetic high-impact example",
    }) for case, transaction, alternative in targeted_specs]
    return {
        "measurement_type": "simulated_sensitivity_from_independent_synthetic_truth_not_model_accuracy",
        "sensitivity_version": SENSITIVITY_VERSION,
        "feature_policy_version": FEATURE_POLICY_VERSION,
        "offer_policy_version": OFFER_POLICY_VERSION,
        "seed": SENSITIVITY_SEED,
        "baseline": "independent_synthetic_scenario_intent_truth",
        "total_accepted_transactions": len(transactions),
        "candidate_alternative_count": len(candidates),
        "sampling_method": "fixed-seed shuffle of sorted eligible IDs; nested prefixes for 2/5/10 percent; rate denominator is all accepted transactions",
        "random_cases": random_cases,
        "targeted_cases": targeted,
        "limitations": [
            "Random cases sample only scenarios with a valid authored alternative and are not a real-world error distribution.",
            "Targeted cases are separate stress tests, not extra random-sample observations.",
            "NSF and offer effects are label/formula simulations, not verified underwriting outcomes.",
        ],
    }


def run_evaluation(input_path: Path, truth_path: Path, review_dir: Path | None, output_dir: Path) -> dict:
    normalized = load_input(input_path)
    truth_records, truth, truth_data = load_truth(normalized, truth_path)
    sensitivity = build_sensitivity_report(normalized, truth_records, truth)
    _write(output_dir / "sensitivity_report.json", sensitivity)
    result = {"sensitivity_cases": len(sensitivity["random_cases"]) + len(sensitivity["targeted_cases"])}
    if review_dir is not None:
        legacy_labels, legacy = _legacy_labels(normalized)
        reviewed_records, reviewed, manifest = load_reviewed(normalized, input_path, review_dir, legacy_labels)
        quality = _quality_report(normalized, input_path, truth_path, truth_records, truth, truth_data,
                                  legacy, reviewed_records, reviewed, manifest)
        _write(output_dir / "quality_report.json", quality)
        result["transactions_evaluated"] = quality["counts"]["transactions"]
        result["aggregate_absolute_amr_error_usd"] = quality["aggregate_absolute_amr_error_usd"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate synthetic truth separately from truth-free reviewer CLI")
    parser.add_argument("--input", type=Path, default=Path("data/transactions/main_90_days.json"))
    parser.add_argument("--truth", type=Path, default=Path("data/ground_truth/main_90_days.json"))
    parser.add_argument("--review-dir", type=Path, help="CLI output directory; omit for sensitivity-only development")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/evaluation"))
    args = parser.parse_args()
    print(json.dumps(run_evaluation(args.input, args.truth, args.review_dir, args.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
