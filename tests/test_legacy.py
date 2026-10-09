"""Ticket 03: frozen, explainable baseline and shared revenue policy."""

import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from fundo_reviewer.data import NormalizedTransaction, load_input
from fundo_reviewer.legacy import (
    PERSONAL_RULES,
    PRECEDENCE,
    RULES,
    RULESET_VERSION,
    label_transaction,
    label_transactions,
    normalize_text,
)
from fundo_reviewer.revenue import (
    ALLOWED_GROUPS,
    GROUPS,
    REVENUE_EXCLUSIONS,
    REVENUE_POLICY_VERSION,
    UNMATCHED,
    is_revenue_eligible,
)


ROOT = Path(__file__).resolve().parents[1]


def _transaction(name: str, amount: str = "-100.00", merchant_name: str | None = None):
    return NormalizedTransaction(
        transaction_id="tx_test", business_id="biz_test", account_id="acct_test",
        date=date(2026, 10, 8), amount=Decimal(amount), name=name,
        merchant_name=merchant_name, category=None, personal_finance_category=None,
        pending=False, pending_transaction_id=None, raw={"name": name, "amount": amount},
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("TAX REFUND", "Not average monthly revenue"),
        ("RETURNED ITEM FEE", "NSFs"),
        ("OVERDRAFT FEE", "Overdraft"),
        ("XFER OWN RESERVE", "Internal transfer"),
        ("UCC-1 FILING", "UCC"),
        ("SQUARE CAPITAL", "Active advance"),
        ("DIRECT DEPOSIT CLIENT", "Auto deposit"),
        ("MERCHANT SETTLEMENT", "Revenue verification"),
        ("CASINO PURCHASE", "High risk — gambling"),
        ("CHAPTER 11 COUNSEL", "High risk — bankruptcy"),
        ("DEBT RELIEF PAYMENT", "High risk — debt settlement payments"),
        ("WAGE LEVY", "High risk — garnishment"),
        ("FRAUD RECOVERY SERVICE", "High risk — other"),
    ],
)
def test_each_fundo_group_is_representable(text, expected):
    label = label_transaction(_transaction(text))
    assert label.group == expected
    assert label.matches
    assert all(match.group in GROUPS for match in label.matches)


def test_frozen_taxonomy_ids_keywords_and_precedence():
    assert RULESET_VERSION == "legacy-v1"
    assert REVENUE_POLICY_VERSION == "revenue-v1"
    assert len(GROUPS) == len(PRECEDENCE) == 13
    assert set(GROUPS) == set(PRECEDENCE) == {rule.group for rule in RULES}
    assert len({rule.rule_id for rule in RULES}) == len(RULES)
    assert ALLOWED_GROUPS == set(GROUPS) | {UNMATCHED}
    assert UNMATCHED not in GROUPS
    assert len(PERSONAL_RULES) == 5


def test_literal_matching_normalization_merchant_trace_and_collision():
    assert normalize_text("  ＳＱＵＡＲＥ\u00a0  INC  ") == "square inc"
    assert normalize_text("UCC-1") != normalize_text("UCC 1")
    label = label_transaction(_transaction("  ＳＱＵＡＲＥ   INC  MERCHANT SETTLEMENT ", merchant_name="Square Inc"))
    assert label.group == "Active advance"  # explicit priority beats revenue verification
    assert label.source_name == "  ＳＱＵＡＲＥ   INC  MERCHANT SETTLEMENT "
    assert label.source_merchant_name == "Square Inc"
    assert label.status == "business"
    assert not label.revenue_eligible
    assert label.matched_rule_ids == ("ADV_01", "REV_01")
    assert label.matches[0].fields == ("name", "merchant_name")
    assert label.matches[0].precedence_rank < label.matches[1].precedence_rank
    assert label.winning_precedence_rank == PRECEDENCE.index("Active advance")


def test_precedence_does_not_depend_on_rule_tuple_or_map_order(monkeypatch):
    import fundo_reviewer.legacy as legacy

    record = _transaction("NSF OVERDRAFT SQUARE CAPITAL MERCHANT SETTLEMENT UCC-1")
    expected = label_transaction(record)
    monkeypatch.setattr(legacy, "RULES", tuple(reversed(RULES)))
    actual = label_transaction(record)
    assert actual == expected
    assert actual.group == "NSFs"
    assert len(actual.matches) >= 6


def test_literal_nsf_collision_inside_transfer_is_preserved_as_known_error():
    label = label_transaction(_transaction("INTERNAL TRANSFER FROM RESERVE"))
    assert label.group == "NSFs"
    assert label.matched_rule_ids == ("NSF_01", "XFER_01")
    assert not label.revenue_eligible


def test_no_match_personal_fallback_category_ignored_and_punctuation_misses():
    label = label_transaction(_transaction("ACME INVOICE PAYMENT"))
    assert label.group == UNMATCHED
    assert label.status == "business"  # explicit, intentionally imperfect fallback
    assert label.matched_rule_ids == label.personal_rule_ids == ()
    assert label.winning_precedence_rank is None
    assert label.revenue_eligible
    assert label_transaction(_transaction("UCC 1 FILING SERVICE", "35.00")).group == UNMATCHED
    assert label_transaction(_transaction("OD-FEE CHARGE", "35.00")).group == UNMATCHED
    category_only = replace(_transaction("GENERIC PAYMENT"), category=("BANK_FEES", "NSF"))
    assert label_transaction(category_only).group == UNMATCHED


@pytest.mark.parametrize("marker", ["PERSONAL", "OWNER DRAW", "OWNER CONTRIBUTION", "FAMILY TRANSFER", "HOUSEHOLD"])
def test_all_personal_markers_apply_to_either_text_field(marker):
    assert label_transaction(_transaction("SOMETHING", merchant_name=marker)).status == "personal"
    assert label_transaction(_transaction(marker)).status == "personal"


def test_revenue_boundaries_auto_deposit_verification_and_no_inference_from_text():
    assert not is_revenue_eligible(Decimal("100"), group=UNMATCHED, status="business")
    assert not is_revenue_eligible(Decimal("-100"), group=UNMATCHED, status="personal")
    for group in REVENUE_EXCLUSIONS:
        assert not is_revenue_eligible(Decimal("-100"), group=group, status="business")
    for group in ("Auto deposit", "Revenue verification", UNMATCHED):
        assert is_revenue_eligible(Decimal("-100"), group=group, status="business")
    assert label_transaction(_transaction("AUTO DEPOSIT CLIENT")).revenue_eligible
    assert label_transaction(_transaction("MERCHANT SETTLEMENT CLIENT")).revenue_eligible
    assert not label_transaction(_transaction("OWNER CONTRIBUTION PERSONAL")).revenue_eligible
    assert not label_transaction(_transaction("INTERNAL TRANSFER FROM RESERVE")).revenue_eligible
    assert not label_transaction(_transaction("SQUARE CAPITAL FUNDING DISBURSEMENT")).revenue_eligible
    assert not label_transaction(_transaction("RENT PAYMENT", "100.00")).revenue_eligible
    with pytest.raises(ValueError, match="unsupported group"):
        is_revenue_eligible(Decimal("-100"), group="invented", status="business")
    with pytest.raises(ValueError, match="unsupported business/personal"):
        is_revenue_eligible(Decimal("-100"), group=UNMATCHED, status="unknown")
    with pytest.raises(ValueError, match="Decimal"):
        is_revenue_eligible(-100.0, group=UNMATCHED, status="business")


@pytest.mark.parametrize(("cohort", "count"), [("main_90_days", 2000), ("short_61_days", 120)])
def test_all_synthetic_records_labeled_once_stably_without_truth_input(cohort, count):
    source = ROOT / "data" / "transactions" / f"{cohort}.json"
    normalized = load_input(source)
    labels = label_transactions(normalized.transactions)
    assert len(labels) == len(normalized.transactions) == count
    assert len({label.transaction_id for label in labels}) == len(labels)
    assert {label.status for label in labels} == {"business", "personal"}
    assert all(label.ruleset_version == RULESET_VERSION for label in labels)
    assert all(label.group in ALLOWED_GROUPS for label in labels)
    assert labels == label_transactions(reversed(normalized.transactions))
    assert labels == label_transactions(normalized.transactions)
    with pytest.raises(ValueError, match="duplicate transaction ID"):
        label_transactions([normalized.transactions[0], normalized.transactions[0]])


def test_known_baseline_errors_do_not_mutate_independent_truth():
    normalized = load_input(ROOT / "data" / "transactions" / "main_90_days.json")
    truth_path = ROOT / "data" / "ground_truth" / "main_90_days.json"
    truth_bytes = truth_path.read_bytes()
    truth = json.loads(truth_bytes)
    by_id = {record.transaction_id: record for record in normalized.transactions}
    by_scenario = {}
    for transaction_id, intended in truth["labels"].items():
        by_scenario.setdefault(intended["scenario_id"], []).append(transaction_id)
    square = by_scenario["processor_square"][0]
    assert truth["labels"][square]["group"] == "Revenue verification"
    assert label_transaction(by_id[square]).group == "Active advance"
    ucc = by_scenario["ucc_punctuation"][0]
    assert truth["labels"][ucc]["group"] == "UCC"
    assert label_transaction(by_id[ucc]).group == UNMATCHED
    no_fee = by_scenario["nsf_name_collision"][0]
    assert truth["labels"][no_fee]["group"] == UNMATCHED
    assert label_transaction(by_id[no_fee]).group == "NSFs"
    assert truth_path.read_bytes() == truth_bytes
