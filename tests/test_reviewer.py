"""Ticket 04: fake-provider review, validation, provenance, and trust boundary."""

import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from fundo_reviewer.data import NormalizedTransaction, load_input
from fundo_reviewer.legacy import label_transaction, label_transactions
from fundo_reviewer.reviewer import (
    FLAG_POLICY_VERSION,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    ProviderReply,
    ReviewProposal,
    build_request,
    review_all,
    review_one,
)


ROOT = Path(__file__).resolve().parents[1]


def _transaction(name="ACH CREDIT CUSTOMER", amount="-100.00"):
    return NormalizedTransaction(
        transaction_id="tx_test", business_id="biz_test", account_id="acct_test",
        date=date(2026, 10, 8), amount=Decimal(amount), name=name,
        merchant_name=None, category=None, personal_finance_category=None,
        pending=False, pending_transaction_id=None, raw={"name": name, "amount": amount},
    )


def _proposal(request, *, decision="keep", group=None, status=None, confidence=0.9, reason="Label supported"):
    return {
        "transaction_id": request.transaction.transaction_id,
        "decision": decision,
        "group": group if group is not None else request.legacy.group,
        "status": status if status is not None else request.legacy.status,
        "confidence": confidence,
        "reason": reason,
    }


class FakeProvider:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def review(self, request):
        self.calls.append(request)
        return self.response(request) if callable(self.response) else self.response


def test_versions_and_fake_provider_reviews_every_existing_legacy_label():
    assert (PROMPT_VERSION, SCHEMA_VERSION, FLAG_POLICY_VERSION) == (
        "review-prompt-v3", "review-schema-v3", "all-valid-changes-v1"
    )
    normalized = load_input(ROOT / "data" / "transactions" / "main_90_days.json")
    labels = label_transactions(normalized.transactions)
    provider = FakeProvider(lambda request: ProviderReply("completed", _proposal(request)))
    outcomes = review_all(normalized.transactions, labels, provider)
    assert len(outcomes) == len(provider.calls) == len(labels) == 2000
    assert {outcome.transaction_id for outcome in outcomes} == {label.transaction_id for label in labels}
    assert all(outcome.review_status == "kept" and not outcome.flag and not outcome.degraded for outcome in outcomes)
    assert all(outcome.legacy.transaction_id == outcome.transaction_id for outcome in outcomes)
    assert outcomes == review_all(tuple(reversed(normalized.transactions)), tuple(reversed(labels)), provider)
    with pytest.raises(ValueError, match="identical unique IDs"):
        review_all(normalized.transactions[:2], labels[:1], provider)
    with pytest.raises(ValueError, match="identical unique IDs"):
        review_all((normalized.transactions[0],) * 2, (labels[0],) * 2, provider)


def test_valid_change_applies_only_semantic_labels_and_recomputes_revenue():
    transaction = _transaction("SQUARE INC MERCHANT SETTLEMENT", "-300.55")
    legacy = label_transaction(transaction)
    assert legacy.group == "Active advance" and not legacy.revenue_eligible
    request = build_request(transaction, legacy)
    provider = FakeProvider(lambda request: ProviderReply(
        "completed", _proposal(request, decision="change", group="Revenue verification",
                                confidence=0.0, reason="Processor sale, not loan"),
        raw_response={"provider": "synthetic fake"}, usage={"input_tokens": 12, "output_tokens": 15},
    ))
    outcome = review_one(request, provider)
    assert outcome.review_status == "changed" and outcome.flag and not outcome.degraded
    assert outcome.proposal == ReviewProposal.model_validate(_proposal(
        request, decision="change", group="Revenue verification", confidence=0.0,
        reason="Processor sale, not loan",
    ))
    assert outcome.final_group == "Revenue verification" and outcome.final_status == "business"
    assert outcome.final_revenue_eligible
    assert transaction.amount == Decimal("-300.55") and transaction.date == date(2026, 10, 8)
    assert outcome.legacy == legacy and outcome.raw_response == {"provider": "synthetic fake"}
    assert outcome.usage == {"input_tokens": 12, "output_tokens": 15}
    assert len(outcome.proposal.reason) <= 160


def test_personal_change_makes_customer_credit_nonrevenue_and_confidence_one_allowed():
    transaction = _transaction()
    request = build_request(transaction, label_transaction(transaction))
    provider = FakeProvider(lambda request: ProviderReply(
        "completed", _proposal(request, decision="change", status="personal", confidence=1.0),
    ))
    outcome = review_one(request, provider)
    assert outcome.flag and outcome.final_status == "personal"
    assert outcome.final_group == request.legacy.group
    assert not outcome.final_revenue_eligible


@pytest.mark.parametrize("edit", [
    {"transaction_id": "wrong"}, {"decision": "keep", "group": "NSFs"},
    {"decision": "change"}, {"group": "invented"}, {"status": "unknown"},
    {"confidence": -0.01}, {"confidence": 1.01}, {"confidence": True},
    {"reason": " "}, {"reason": "x" * 161}, {"date": "2026-01-01"},
    {"amount": "-1.00"}, {"revenue_eligible": True}, {"truth_label": "NSFs"},
])
def test_invalid_or_source_editing_proposals_degrade_and_keep_legacy(edit):
    transaction = _transaction()
    request = build_request(transaction, label_transaction(transaction))
    proposal = _proposal(request)
    proposal.update(edit)
    outcome = review_one(request, FakeProvider(ProviderReply("completed", proposal, proposal)))
    assert outcome.review_status == "invalid_response" and outcome.degraded
    assert not outcome.flag and outcome.proposal is None
    assert (outcome.final_group, outcome.final_status, outcome.final_revenue_eligible) == (
        request.legacy.group, request.legacy.status, request.legacy.revenue_eligible
    )
    assert outcome.raw_response == proposal and outcome.error


@pytest.mark.parametrize(("reply", "status"), [
    (ProviderReply("refused", raw_response={"refusal": "cannot"}), "refused"),
    (ProviderReply("incomplete", raw_response={"partial": True}), "incomplete"),
    (ProviderReply("completed", parsed=None), "invalid_response"),
    (ProviderReply("completed", parsed="not-json"), "invalid_response"),
])
def test_noncompleted_and_malformed_online_results_are_not_keeps(reply, status):
    transaction = _transaction()
    request = build_request(transaction, label_transaction(transaction))
    outcome = review_one(request, FakeProvider(reply))
    assert outcome.review_status == status and outcome.degraded
    assert outcome.proposal is None and not outcome.flag
    assert outcome.final_group == request.legacy.group


def test_provider_failure_is_visible_degraded_fallback():
    request = build_request(_transaction(), label_transaction(_transaction()))

    def fail(_):
        raise TimeoutError("simulated outage")

    outcome = review_one(request, FakeProvider(fail))
    assert outcome.review_status == "provider_failure" and outcome.degraded
    assert outcome.final_group == request.legacy.group and not outcome.flag
    assert "simulated outage" in outcome.error


def test_injection_description_is_json_data_and_fake_observed_keep_not_guaranteed_model_safety():
    normalized = load_input(ROOT / "data" / "transactions" / "main_90_days.json")
    transaction = next(item for item in normalized.transactions if "IGNORE PRIOR INSTRUCTIONS" in item.name)
    legacy = label_transaction(transaction)
    # Simulate an accidental raw truth field; explicit request allowlist must not serialize it.
    transaction = replace(transaction, raw={**transaction.raw, "scenario_id": "secret", "truth_label": "unmatched"})
    request = build_request(transaction, legacy)
    assert not hasattr(request.transaction, "raw")
    assert "IGNORE PRIOR INSTRUCTIONS" in request.user_prompt
    assert "IGNORE PRIOR INSTRUCTIONS" not in request.system_prompt
    assert "scenario_id" not in request.user_prompt and "truth_label" not in request.user_prompt
    assert "secret" not in request.user_prompt
    assert json.loads(request.user_prompt.split("\n", 1)[1]) == request.payload
    assert request.payload["transaction"]["name"] == transaction.name
    provider = FakeProvider(lambda request: ProviderReply("completed", _proposal(request)))
    outcome = review_one(request, provider)
    assert outcome.review_status == "kept" and not outcome.flag
    assert outcome.final_revenue_eligible == legacy.revenue_eligible
    # This tests request isolation + a fake's observed behavior, not a guarantee about a real LLM.
