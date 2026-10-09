"""Ticket 06: shared, deterministic credit features and illustrative offer."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Mapping

from fundo_reviewer.data import BusinessCoverage, NormalizedInput, NormalizedTransaction
from fundo_reviewer.legacy import LegacyLabel
from fundo_reviewer.revenue import is_revenue_eligible
from fundo_reviewer.reviewer import ReviewOutcome


FEATURE_POLICY_VERSION = "credit-features-v1"
OFFER_POLICY_VERSION = "illustrative-offer-v1"
HIGH_RISK_GROUPS = frozenset({
    "High risk — gambling", "High risk — bankruptcy", "High risk — debt settlement payments",
    "High risk — garnishment", "High risk — other",
})
OFFER_AMR_MULTIPLIER = Decimal("1.2")
OFFER_FUNDER_PAYMENT_MULTIPLIER = Decimal("20")
NSF_ZERO_CUTOFF = 5
CENT = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class CreditLabel:
    transaction_id: str
    group: str
    status: str


@dataclass(frozen=True, slots=True)
class CreditFeatures:
    business_id: str
    transaction_count: int
    coverage_days: int
    deposit_total: Decimal
    eligible_revenue_total: Decimal
    revenue_to_deposits: Decimal | None
    average_monthly_revenue: Decimal
    nsf_count: int
    overdraft_count: int
    debit_total: Decimal
    high_risk_debit_total: Decimal
    high_risk_debit_share: Decimal | None
    funder_repayment_total: Decimal
    other_funder_daily_payments: Decimal


@dataclass(frozen=True, slots=True)
class OfferResult:
    raw: Decimal
    after_nsf_cutoff: Decimal
    after_nonnegative_floor: Decimal
    final: Decimal
    nsf_cutoff_applied: bool


def _aligned_labels(transactions: tuple[NormalizedTransaction, ...], labels: Mapping[str, CreditLabel]) -> None:
    expected = {item.transaction_id for item in transactions}
    if len(expected) != len(transactions) or set(labels) != expected:
        raise ValueError("credit labels must cover exactly the accepted transaction IDs")
    for transaction_id, label in labels.items():
        if label.transaction_id != transaction_id:
            raise ValueError(f"credit label ID mismatch for {transaction_id}")
        if label.status not in {"business", "personal"}:
            raise ValueError(f"invalid credit status for {transaction_id}")
        # The shared revenue function also validates the approved group.
        is_revenue_eligible(Decimal("-1"), group=label.group, status=label.status)


def compute_features(normalized: NormalizedInput, labels: Mapping[str, CreditLabel]) -> dict[str, CreditFeatures]:
    """Same accepted transactions and coverage for legacy, reviewed, and truth."""
    _aligned_labels(normalized.transactions, labels)
    by_business: dict[str, list[NormalizedTransaction]] = {
        coverage.business_id: [] for coverage in normalized.business_coverage
    }
    for transaction in normalized.transactions:
        by_business[transaction.business_id].append(transaction)
    result: dict[str, CreditFeatures] = {}
    for coverage in normalized.business_coverage:
        transactions = by_business[coverage.business_id]
        deposits = sum((-item.amount for item in transactions if item.amount < 0), Decimal(0))
        debits = sum((item.amount for item in transactions if item.amount > 0), Decimal(0))
        revenue = sum((
            -item.amount for item in transactions
            if is_revenue_eligible(item.amount, group=labels[item.transaction_id].group,
                                   status=labels[item.transaction_id].status)
        ), Decimal(0))
        high_risk_debits = sum((
            item.amount for item in transactions
            if item.amount > 0 and labels[item.transaction_id].group in HIGH_RISK_GROUPS
        ), Decimal(0))
        funder_repayments = sum((
            item.amount for item in transactions
            if item.amount > 0 and labels[item.transaction_id].group == "Active advance"
            and labels[item.transaction_id].status == "business"
        ), Decimal(0))
        days = Decimal(coverage.days)
        result[coverage.business_id] = CreditFeatures(
            business_id=coverage.business_id,
            transaction_count=len(transactions),
            coverage_days=coverage.days,
            deposit_total=deposits,
            eligible_revenue_total=revenue,
            revenue_to_deposits=revenue / deposits if deposits else None,
            average_monthly_revenue=revenue * Decimal(30) / days,
            nsf_count=sum(labels[item.transaction_id].group == "NSFs" for item in transactions),
            overdraft_count=sum(labels[item.transaction_id].group == "Overdraft" for item in transactions),
            debit_total=debits,
            high_risk_debit_total=high_risk_debits,
            high_risk_debit_share=high_risk_debits / debits if debits else None,
            funder_repayment_total=funder_repayments,
            other_funder_daily_payments=funder_repayments / days,
        )
    return result


def calculate_offer(features: CreditFeatures) -> OfferResult:
    raw = (OFFER_AMR_MULTIPLIER * features.average_monthly_revenue
           - OFFER_FUNDER_PAYMENT_MULTIPLIER * features.other_funder_daily_payments)
    cutoff = features.nsf_count > NSF_ZERO_CUTOFF
    after_cutoff = Decimal(0) if cutoff else raw
    floored = max(after_cutoff, Decimal(0))
    return OfferResult(raw, after_cutoff, floored, floored.quantize(CENT, rounding=ROUND_HALF_UP), cutoff)


def _decimal(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def feature_record(features: CreditFeatures) -> dict:
    offer = calculate_offer(features)
    return {
        "transaction_count": features.transaction_count,
        "deposit_total_usd": _decimal(features.deposit_total),
        "eligible_revenue_total_usd": _decimal(features.eligible_revenue_total),
        "revenue_to_deposits": {
            "numerator_usd": _decimal(features.eligible_revenue_total),
            "denominator_usd": _decimal(features.deposit_total),
            "ratio": _decimal(features.revenue_to_deposits),
            "undefined_reason": None if features.revenue_to_deposits is not None else "zero_deposits",
        },
        "average_monthly_revenue_usd": _decimal(features.average_monthly_revenue),
        "nsf_count": features.nsf_count,
        "overdraft_count": features.overdraft_count,
        "high_risk_debit_share": {
            "numerator_usd": _decimal(features.high_risk_debit_total),
            "denominator_usd": _decimal(features.debit_total),
            "ratio": _decimal(features.high_risk_debit_share),
            "undefined_reason": None if features.high_risk_debit_share is not None else "zero_debits",
        },
        "other_funder_payments": {
            "repayment_total_usd": _decimal(features.funder_repayment_total),
            "coverage_days": features.coverage_days,
            "daily_usd": _decimal(features.other_funder_daily_payments),
        },
        "offer": {
            "raw_usd": _decimal(offer.raw),
            "after_nsf_cutoff_usd": _decimal(offer.after_nsf_cutoff),
            "after_nonnegative_floor_usd": _decimal(offer.after_nonnegative_floor),
            "final_usd": _decimal(offer.final),
            "nsf_cutoff_applied": offer.nsf_cutoff_applied,
            "policy_version": OFFER_POLICY_VERSION,
            "is_live_funding_decision": False,
        },
    }


def _delta(after: Decimal | int | None, before: Decimal | int | None) -> str | int | None:
    if after is None or before is None:
        return None
    difference = after - before
    return str(difference) if isinstance(difference, Decimal) else difference


def _business_record(coverage: BusinessCoverage, legacy: CreditFeatures, reviewed: CreditFeatures) -> dict:
    if (legacy.business_id != reviewed.business_id or legacy.transaction_count != reviewed.transaction_count
            or legacy.coverage_days != reviewed.coverage_days or legacy.deposit_total != reviewed.deposit_total
            or legacy.debit_total != reviewed.debit_total):
        raise ValueError("legacy and reviewed features must share transactions, coverage, and cash denominators")
    return {
        "business_id": coverage.business_id,
        "coverage": {
            "account_ids": list(coverage.account_ids), "start": coverage.start.isoformat(),
            "end": coverage.end.isoformat(), "observed_common_days": coverage.days,
            "is_complete_90_days": coverage.is_complete_90_days,
            "not_directly_comparable_with_90_day_training": not coverage.is_complete_90_days,
        },
        "legacy": feature_record(legacy),
        "reviewed": feature_record(reviewed),
        "reviewed_minus_legacy": {
            "eligible_revenue_total_usd": _delta(reviewed.eligible_revenue_total, legacy.eligible_revenue_total),
            "revenue_to_deposits_ratio": _delta(reviewed.revenue_to_deposits, legacy.revenue_to_deposits),
            "average_monthly_revenue_usd": _delta(reviewed.average_monthly_revenue, legacy.average_monthly_revenue),
            "nsf_count": _delta(reviewed.nsf_count, legacy.nsf_count),
            "overdraft_count": _delta(reviewed.overdraft_count, legacy.overdraft_count),
            "high_risk_debit_share_ratio": _delta(reviewed.high_risk_debit_share, legacy.high_risk_debit_share),
            "other_funder_daily_payments_usd": _delta(
                reviewed.other_funder_daily_payments, legacy.other_funder_daily_payments
            ),
            "final_offer_usd": _delta(calculate_offer(reviewed).final, calculate_offer(legacy).final),
        },
    }


def build_credit_report(
    normalized: NormalizedInput, legacy_labels: tuple[LegacyLabel, ...],
    reviewed_outcomes: tuple[ReviewOutcome, ...] | list[ReviewOutcome],
) -> dict:
    legacy = {item.transaction_id: CreditLabel(item.transaction_id, item.group, item.status)
              for item in legacy_labels}
    reviewed = {item.transaction_id: CreditLabel(item.transaction_id, item.final_group, item.final_status)
                for item in reviewed_outcomes}
    if len(legacy) != len(legacy_labels) or len(reviewed) != len(reviewed_outcomes):
        raise ValueError("duplicate credit label transaction ID")
    before = compute_features(normalized, legacy)
    after = compute_features(normalized, reviewed)
    return {
        "feature_policy_version": FEATURE_POLICY_VERSION,
        "offer_policy_version": OFFER_POLICY_VERSION,
        "source": "same_accepted_records_legacy_vs_illustrative_reviewed_labels",
        "is_live_funding_decision": False,
        "businesses": [
            _business_record(coverage, before[coverage.business_id], after[coverage.business_id])
            for coverage in normalized.business_coverage
        ],
    }
