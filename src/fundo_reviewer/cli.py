"""Ticket 05: truth-free batch CLI with strict offline and budgeted online modes."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from fundo_reviewer.cache import (
    PRICING_VERSION, BatchReviewCache, CacheCorrupt, CacheMiss, ReviewCache, SpendLedger,
    batch_identity,
    usage_derived_cost,
)
from fundo_reviewer.credit import FEATURE_POLICY_VERSION, OFFER_POLICY_VERSION, build_credit_report
from fundo_reviewer.data import load_input
from fundo_reviewer.legacy import RULESET_VERSION, label_transactions
from fundo_reviewer.provider import (
    DEFAULT_MODEL, BudgetedBatchProvider, BudgetedProvider, OpenAIProvider, build_batch_request,
)
from fundo_reviewer.revenue import REVENUE_POLICY_VERSION
from fundo_reviewer.reviewer import (
    FLAG_POLICY_VERSION, PROMPT_VERSION, SCHEMA_VERSION,
    FatalReviewError, ProviderReply, ReviewOutcome, ReviewProvider, build_request, review_one,
)


class _StaticProvider:
    def __init__(self, reply: ProviderReply):
        self.reply = reply

    def review(self, request):
        return self.reply


def _outcome_record(outcome: ReviewOutcome) -> dict[str, Any]:
    proposal = outcome.proposal
    return {
        "transaction_id": outcome.transaction_id,
        "legacy": {
            "group": outcome.legacy.group,
            "status": outcome.legacy.status,
            "revenue_eligible": outcome.legacy.revenue_eligible,
            "matched_rule_ids": list(outcome.legacy.matched_rule_ids),
            "personal_rule_ids": list(outcome.legacy.personal_rule_ids),
        },
        "review_status": outcome.review_status,
        "flag": outcome.flag,
        "proposal": proposal.model_dump(mode="json") if proposal is not None else None,
        "final": {
            "group": outcome.final_group,
            "status": outcome.final_status,
            "revenue_eligible": outcome.final_revenue_eligible,
        },
        "error": outcome.error,
    }


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _run_batched(normalized, labels, *, mode, cache_path, ledger_path, model, provider, batch_size):
    cache = BatchReviewCache(cache_path)
    budgeted = None
    if mode == "online":
        live = provider if provider is not None else OpenAIProvider(model)
        if not hasattr(live, "review_batch"):
            raise TypeError("batch mode requires provider.review_batch")
        budgeted = BudgetedBatchProvider(live, SpendLedger(ledger_path), model)
    outcomes = []
    cache_hits = 0
    batch_hits = 0
    new_api_calls = 0
    new_usage = Counter()
    historical_usage = Counter()
    historical_cost = 0
    transactions = normalized.transactions
    for offset in range(0, len(transactions), batch_size):
        chunk = transactions[offset:offset + batch_size]
        requests = tuple(build_request(item, labels[item.transaction_id]) for item in chunk)
        batch = build_batch_request(requests)
        identity = batch_identity(requests, model, batch.system_prompt, batch.user_prompt)
        was_cache_hit = False
        try:
            reply = cache.replay(identity)
        except CacheMiss:
            if mode == "offline":
                raise
            assert budgeted is not None
            new_api_calls += 1
            try:
                reply = budgeted.review_batch(batch)
            except FatalReviewError:
                raise
            except Exception as exc:
                reply = ProviderReply(
                    "provider_failure", raw_response={"error_type": type(exc).__name__, "message": "provider call failed"}
                )
            if reply.usage:
                new_usage.update(reply.usage)
        else:
            was_cache_hit = True
            cache_hits += len(chunk)
            batch_hits += 1
            if reply.usage:
                historical_usage.update(reply.usage)
            historical_cost += usage_derived_cost(reply.usage)
        by_id = None
        if reply.status == "completed" and isinstance(reply.parsed, list):
            try:
                by_id = {item["transaction_id"]: item for item in reply.parsed}
                if len(by_id) != len(reply.parsed) or set(by_id) != {item.transaction_id for item in chunk}:
                    by_id = None
            except (KeyError, TypeError):
                by_id = None
        if reply.status == "completed" and by_id is None:
            reply = ProviderReply("invalid_response", raw_response=reply.raw_response, usage=reply.usage)
        batch_outcomes = []
        for request in requests:
            item_reply = (
                ProviderReply("completed", parsed=by_id[request.transaction.transaction_id],
                              raw_response=reply.raw_response)
                if by_id is not None else reply
            )
            batch_outcomes.append(review_one(request, _StaticProvider(item_reply)))
        validated = [_outcome_record(item) for item in batch_outcomes]
        if was_cache_hit:
            if cache.validated_outcomes(identity) != validated:
                raise CacheCorrupt("cached validated outcomes differ from replayed validation")
        elif reply.status != "provider_failure":
            # A returned but invalid/refused response is replayable with its
            # explicit degraded status. A transport failure has no model
            # decision to replay and must be eligible for a later online retry.
            cache.append(identity, reply, validated)
        outcomes.extend(batch_outcomes)
    return outcomes, cache_hits, batch_hits, new_api_calls, new_usage, historical_usage, historical_cost


def run_pipeline(
    input_path: Path,
    output_dir: Path,
    mode: str,
    cache_path: Path,
    ledger_path: Path,
    model: str = DEFAULT_MODEL,
    provider: ReviewProvider | None = None,
    batch_size: int = 1,
) -> dict[str, Any]:
    if mode not in {"offline", "online"}:
        raise ValueError("mode must be offline or online")
    if batch_size <= 0 or batch_size > 80:
        raise ValueError("batch_size must be between 1 and 80")
    # Crucial: no truth file is opened or passed to the provider here.
    normalized = load_input(input_path)
    legacy = label_transactions(normalized.transactions)
    labels = {item.transaction_id: item for item in legacy}
    batch_hits = 0
    if batch_size > 1:
        outcomes, cache_hits, batch_hits, new_api_calls, new_usage, historical_usage, historical_cost = _run_batched(
            normalized, labels, mode=mode, cache_path=cache_path, ledger_path=ledger_path,
            model=model, provider=provider, batch_size=batch_size,
        )
    else:
        cache = ReviewCache(cache_path)
        budgeted: BudgetedProvider | None = None
        if mode == "online":
            # Lazy key/provider access. Offline imports no SDK client or key.
            live_provider = provider if provider is not None else OpenAIProvider(model)
            budgeted = BudgetedProvider(live_provider, SpendLedger(ledger_path), model)
        outcomes = []
        cache_hits = 0
        new_api_calls = 0
        new_usage = Counter()
        historical_usage = Counter()
        historical_cost = 0
        for transaction in normalized.transactions:
            request = build_request(transaction, labels[transaction.transaction_id])
            try:
                cached = cache.replay(request, model)
            except CacheMiss:
                if mode == "offline":
                    raise  # no silent partial replay or fake keep
                assert budgeted is not None
                new_api_calls += 1
                outcome = review_one(request, budgeted)
                if outcome.review_status in {"kept", "changed"}:
                    cache.append(request, model, outcome, usage_derived_cost(outcome.usage))
                if outcome.usage:
                    new_usage.update(outcome.usage)
            else:
                cache_hits += 1
                outcome = review_one(request, _StaticProvider(cached))
                if outcome.degraded:
                    raise CacheCorrupt(f"cached proposal invalid for {transaction.transaction_id}: {outcome.error}")
                if cached.usage:
                    historical_usage.update(cached.usage)
                historical_cost += usage_derived_cost(cached.usage)
            outcomes.append(outcome)
    input_sha256 = hashlib.sha256(input_path.read_bytes()).hexdigest()
    status_counts = dict(sorted(Counter(item.review_status for item in outcomes).items()))
    credit_report = build_credit_report(normalized, legacy, outcomes)
    credit_path = output_dir / "credit_report.json"
    _write_json(credit_path, credit_report)
    manifest = {
        "input_name": input_path.name,
        "input_sha256": input_sha256,
        "as_of": normalized.as_of.isoformat(),
        "coverage": [
            {"business_id": business.business_id, "start": business.start.isoformat(),
             "end": business.end.isoformat(), "days": business.days,
             "is_complete_90_days": business.is_complete_90_days}
            for business in normalized.business_coverage
        ],
        "accepted_transactions": len(normalized.transactions),
        "excluded_counts": normalized.exclusion_counts,
        "mode": mode,
        "model": model,
        "versions": {
            "input_contract": normalized.contract_version,
            "ruleset": RULESET_VERSION,
            "revenue_policy": REVENUE_POLICY_VERSION,
            "prompt": PROMPT_VERSION,
            "response_schema": SCHEMA_VERSION,
            "flag_policy": FLAG_POLICY_VERSION,
            "pricing": PRICING_VERSION,
            "credit_features": FEATURE_POLICY_VERSION,
            "illustrative_offer": OFFER_POLICY_VERSION,
        },
        "review_status_counts": status_counts,
        "flag_count": sum(item.flag for item in outcomes),
        "degraded_count": sum(item.degraded for item in outcomes),
        "cache_hits": cache_hits,
        "cache_batch_hits": batch_hits,
        "batch_size": batch_size,
        "new_api_calls": new_api_calls,
        "new_provider_usage": dict(sorted(new_usage.items())),
        "historical_cached_usage": dict(sorted(historical_usage.items())),
        "new_usage_derived_cost_usd": str(usage_derived_cost(dict(new_usage))),
        "historical_cache_usage_derived_cost_usd": str(historical_cost),
        "accuracy": "not_measured_without_separate_truth_evaluation",
        "credit_report_sha256": hashlib.sha256(credit_path.read_bytes()).hexdigest(),
    }
    _write_json(output_dir / "review_outcomes.json", [_outcome_record(item) for item in outcomes])
    _write_json(output_dir / "run_manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Review Plaid-shaped input with cache-only or online execution")
    parser.add_argument("--input", type=Path, default=Path("data/transactions/main_90_days.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    parser.add_argument("--mode", choices=("offline", "online"), default="offline")
    parser.add_argument("--cache", type=Path, default=Path("cache/batch_reviews.jsonl"))
    parser.add_argument("--spend-ledger", type=Path, default=Path("cache/spend_ledger.jsonl"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=80)
    args = parser.parse_args()
    result = run_pipeline(args.input, args.output_dir, args.mode, args.cache, args.spend_ledger, args.model, batch_size=args.batch_size)
    print(json.dumps({key: result[key] for key in ("accepted_transactions", "review_status_counts", "flag_count", "degraded_count", "cache_hits", "new_api_calls", "new_usage_derived_cost_usd")}, sort_keys=True))


if __name__ == "__main__":
    main()
