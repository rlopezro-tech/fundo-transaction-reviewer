"""Ticket 06: fixed-source financial arithmetic and offer boundaries."""

import json
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from fundo_reviewer.cli import run_pipeline
from fundo_reviewer.credit import CreditLabel, build_credit_report, calculate_offer, compute_features
from fundo_reviewer.data import BusinessCoverage, NormalizedInput, NormalizedTransaction
from fundo_reviewer.legacy import label_transactions
from fundo_reviewer.reviewer import ProviderReply, review_all


def _input(specs, *, days=90):
    as_of = date(2026, 10, 8)
    transactions = tuple(
        NormalizedTransaction(
            transaction_id=f"tx_{index}", business_id="biz", account_id="acct",
            date=as_of, amount=Decimal(amount), name=name, merchant_name=None,
            category=None, personal_finance_category=None, pending=False,
            pending_transaction_id=None, raw={},
        )
        for index, (name, amount) in enumerate(specs)
    )
    coverage = BusinessCoverage("biz", ("acct",), as_of - timedelta(days=days - 1), as_of, days)
    return NormalizedInput("input-v1", as_of, as_of - timedelta(days=89), as_of,
                           (), (coverage,), transactions, ())


def _labels(normalized, groups_and_statuses):
    return {
        transaction.transaction_id: CreditLabel(transaction.transaction_id, group, status)
        for transaction, (group, status) in zip(normalized.transactions, groups_and_statuses, strict=True)
    }


def test_deposits_revenue_debits_and_funder_payment_signs():
    normalized = _input([
        ("client sale", "-100.00"), ("owner inflow", "-50.00"),
        ("advance disbursement", "-300.00"), ("own transfer", "-20.00"),
        ("funder repayment", "60.00"), ("personal repayment", "20.00"),
        ("casino", "10.00"), ("ordinary bill", "5.00"),
    ])
    labels = _labels(normalized, [
        ("unmatched", "business"), ("unmatched", "personal"),
        ("Active advance", "business"), ("Internal transfer", "business"),
        ("Active advance", "business"), ("Active advance", "personal"),
        ("High risk — gambling", "business"), ("unmatched", "business"),
    ])
    features = compute_features(normalized, labels)["biz"]
    assert features.deposit_total == Decimal("470.00")
    assert features.eligible_revenue_total == Decimal("100.00")
    assert features.revenue_to_deposits == Decimal(100) / Decimal(470)
    assert features.average_monthly_revenue == Decimal(100) / Decimal(3)
    assert features.debit_total == Decimal("95.00")
    assert features.high_risk_debit_total == Decimal("10.00")
    assert features.high_risk_debit_share == Decimal(10) / Decimal(95)
    assert features.funder_repayment_total == Decimal("60.00")
    assert features.other_funder_daily_payments == Decimal(60) / Decimal(90)
    assert calculate_offer(features).final == Decimal("26.67")
    # A false positive Active advance on an ordinary debit lowers the offer;
    # correcting it raises the offer. An incoming disbursement never counts.
    false_advance = dict(labels)
    false_advance["tx_7"] = CreditLabel("tx_7", "Active advance", "business")
    wrong = compute_features(normalized, false_advance)["biz"]
    assert wrong.funder_repayment_total == Decimal("65.00")
    assert calculate_offer(wrong).final < calculate_offer(features).final


def test_zero_denominators_are_null_not_zero_percent_and_labels_align():
    only_debit = _input([("rent", "25.00")])
    features = compute_features(only_debit, _labels(only_debit, [("unmatched", "business")]))["biz"]
    assert features.deposit_total == 0 and features.revenue_to_deposits is None
    only_credit = _input([("sale", "-25.00")])
    features = compute_features(only_credit, _labels(only_credit, [("unmatched", "business")]))["biz"]
    assert features.debit_total == 0 and features.high_risk_debit_share is None
    with pytest.raises(ValueError, match="exactly"):
        compute_features(only_credit, {})


def test_offer_nsf_cutoff_floor_and_final_only_half_up_rounding():
    normalized = _input([("sale", "-1.00")])
    base = compute_features(normalized, _labels(normalized, [("unmatched", "business")]))["biz"]
    at_five = replace(base, average_monthly_revenue=Decimal("1.005"),
                      other_funder_daily_payments=Decimal("0.0001"), nsf_count=5)
    offer = calculate_offer(at_five)
    assert offer.raw == Decimal("1.2040")
    assert offer.final == Decimal("1.20")
    assert not offer.nsf_cutoff_applied
    at_six = calculate_offer(replace(at_five, nsf_count=6))
    assert at_six.raw == offer.raw and at_six.final == 0 and at_six.nsf_cutoff_applied
    negative = calculate_offer(replace(base, average_monthly_revenue=Decimal(0),
                                      other_funder_daily_payments=Decimal(1)))
    assert negative.raw == Decimal(-20)
    assert negative.after_nonnegative_floor == negative.final == 0
    half_up = calculate_offer(replace(base, average_monthly_revenue=Decimal("0.0125"),
                                      other_funder_daily_payments=Decimal(0)))
    assert half_up.raw == Decimal("0.01500") and half_up.final == Decimal("0.02")


class _KeepProvider:
    def review(self, request):
        return ProviderReply("completed", parsed={
            "transaction_id": request.transaction.transaction_id,
            "decision": "keep", "group": request.legacy.group,
            "status": request.legacy.status, "confidence": 0.8, "reason": "Keep existing label",
        })


def test_61_day_credit_report_warns_and_same_label_yields_zero_deltas():
    normalized = _input([("sale", "-61.00")], days=61)
    legacy = label_transactions(normalized.transactions)
    outcomes = review_all(normalized.transactions, legacy, _KeepProvider())
    report = build_credit_report(normalized, legacy, outcomes)
    business = report["businesses"][0]
    assert business["coverage"]["observed_common_days"] == 61
    assert business["coverage"]["not_directly_comparable_with_90_day_training"]
    assert business["legacy"] == business["reviewed"]
    assert business["reviewed_minus_legacy"]["final_offer_usd"] == "0.00"
    assert business["legacy"]["average_monthly_revenue_usd"] == "30.00"


def test_cli_emits_deterministic_truth_free_credit_report(tmp_path):
    source = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "input_90_days.json"
    first = run_pipeline(source, tmp_path / "first", "online", tmp_path / "cache.jsonl",
                         tmp_path / "spend.jsonl", provider=_KeepProvider())
    second = run_pipeline(source, tmp_path / "second", "offline", tmp_path / "cache.jsonl",
                          tmp_path / "spend.jsonl")
    report = json.loads((tmp_path / "second" / "credit_report.json").read_text())
    assert first["credit_report_sha256"] == second["credit_report_sha256"]
    assert (tmp_path / "first" / "credit_report.json").read_bytes() == (
        tmp_path / "second" / "credit_report.json"
    ).read_bytes()
    assert len(report["businesses"]) == len(first["coverage"])
    assert all("offer" in business["reviewed"] for business in report["businesses"])
    assert "truth" not in (tmp_path / "second" / "credit_report.json").read_text()
