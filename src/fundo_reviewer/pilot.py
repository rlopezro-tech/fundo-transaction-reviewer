"""Small stratified paid pilot; no full-run call or truth enters provider requests."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

from fundo_reviewer.cache import CacheMiss, ReviewCache, SpendLedger, usage_derived_cost
from fundo_reviewer.data import load_input
from fundo_reviewer.legacy import label_transaction
from fundo_reviewer.provider import BudgetedProvider, DEFAULT_MODEL, OpenAIProvider
from fundo_reviewer.reviewer import ProviderReply, build_request, review_one


# Fixed before calling the provider; 20 scenarios across biz_01..biz_08.
# biz_09 and biz_10 remain a held-out business cohort.
PILOT_IDS = (
    "tx_biz_01_0050", "tx_biz_02_0006", "tx_biz_03_0006", "tx_biz_04_0001",
    "tx_biz_05_0071", "tx_biz_06_0094", "tx_biz_07_0083", "tx_biz_08_0031",
    "tx_biz_01_0116", "tx_biz_02_0140", "tx_biz_03_0086", "tx_biz_04_0008",
    "tx_biz_05_0006", "tx_biz_06_0052", "tx_biz_07_0131", "tx_biz_08_0038",
    "tx_biz_01_0033", "tx_biz_02_0009", "tx_biz_03_0106", "tx_biz_04_0106",
)
WEAK_PROMPT = "Review the existing legacy group and status. Reply with keep or change in the required schema."


class _Static:
    def __init__(self, reply: ProviderReply):
        self.reply = reply

    def review(self, request):
        return self.reply


def run_pilot(variant: str, model: str = DEFAULT_MODEL) -> dict:
    if variant not in {"weak", "current"}:
        raise ValueError("pilot variant must be weak or current")
    normalized = load_input(Path("data/transactions/main_90_days.json"))
    transactions = {item.transaction_id: item for item in normalized.transactions}
    cache_path = Path("cache/pilot_weak.jsonl" if variant == "weak" else "cache/pilot_current.jsonl")
    cache = ReviewCache(cache_path)
    ledger = SpendLedger(Path("cache/spend_ledger.jsonl"))
    provider = BudgetedProvider(OpenAIProvider(model), ledger, model)
    attempts_path = Path(f"reports/pilot_{variant}_attempts.jsonl")
    attempts_path.parent.mkdir(parents=True, exist_ok=True)
    records = []
    counts = Counter()
    new_calls = 0
    for transaction_id in PILOT_IDS:
        transaction = transactions[transaction_id]
        request = build_request(transaction, label_transaction(transaction))
        if variant == "weak":
            request = replace(request, system_prompt=WEAK_PROMPT)
        try:
            reply = cache.replay(request, model)
        except CacheMiss:
            new_calls += 1
            outcome = review_one(request, provider)
            with attempts_path.open("a", encoding="utf-8") as attempts:
                attempts.write(json.dumps({
                    "transaction_id": transaction_id,
                    "variant": variant,
                    "review_status": outcome.review_status,
                    "raw_response": outcome.raw_response,
                    "proposal": outcome.proposal.model_dump(mode="json") if outcome.proposal else None,
                    "error": (
                        f"provider call failed: {outcome.error.split(':', 1)[0]}"
                        if outcome.review_status == "provider_failure" and outcome.error
                        else outcome.error
                    ),
                    "usage": outcome.usage,
                }, ensure_ascii=False, sort_keys=True) + "\n")
            if outcome.review_status == "provider_failure":
                raise RuntimeError(f"pilot stopped after provider failure for {transaction_id}: {outcome.error}")
            if not outcome.degraded:
                cache.append(request, model, outcome, usage_derived_cost(outcome.usage, model))
        else:
            outcome = review_one(request, _Static(reply))
            if outcome.degraded:
                raise ValueError(f"corrupt pilot cache entry for {transaction_id}")
        counts[outcome.review_status] += 1
        records.append({
            "transaction_id": transaction_id,
            "variant": variant,
            "legacy_group": outcome.legacy.group,
            "legacy_status": outcome.legacy.status,
            "review_status": outcome.review_status,
            "final_group": outcome.final_group,
            "final_status": outcome.final_status,
            "flag": outcome.flag,
            "reason": outcome.proposal.reason if outcome.proposal else None,
            "usage": outcome.usage,
        })
    result = {
        "variant": variant, "model": model, "pilot_ids": list(PILOT_IDS),
        "new_calls": new_calls, "status_counts": dict(sorted(counts.items())),
        "ledger_settled_usage_derived_cost_usd": str(ledger.settled_usd),
        "records": records,
    }
    output = Path(f"reports/pilot_{variant}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a 20-item stratified review pilot")
    parser.add_argument("--variant", choices=("weak", "current"), required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    result = run_pilot(args.variant, args.model)
    print(json.dumps({key: result[key] for key in ("variant", "model", "new_calls", "status_counts", "ledger_settled_usage_derived_cost_usd")}, sort_keys=True))


if __name__ == "__main__":
    main()
