"""Run a small Ollama-backed reviewer pilot without using the OpenAI API."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.request import Request, urlopen

from fundo_reviewer.cache import BatchReviewCache, CacheMiss, batch_identity
from fundo_reviewer.data import load_input
from fundo_reviewer.legacy import label_transaction
from fundo_reviewer.provider import BatchProviderShape, build_batch_request
from fundo_reviewer.reviewer import ProviderReply, ReviewOutcome, build_request, review_one
from fundo_reviewer.pilot import PILOT_IDS


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = "qwen3.5:9b-q4_K_M"
MODEL_DIGEST = "56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90"
MODEL_ID = f"ollama:{DEFAULT_MODEL}@{MODEL_DIGEST}"


class _StaticProvider:
    def __init__(self, reply: ProviderReply):
        self.reply = reply

    def review(self, request):
        return self.reply


def _outcome_record(outcome: ReviewOutcome) -> dict:
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
        "proposal": proposal.model_dump(mode="json") if proposal else None,
        "final": {
            "group": outcome.final_group,
            "status": outcome.final_status,
            "revenue_eligible": outcome.final_revenue_eligible,
        },
        "error": outcome.error,
    }


def _call_ollama(model: str, system_prompt: str, user_prompt: str) -> ProviderReply:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "format": BatchProviderShape.model_json_schema(),
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "num_ctx": 16384, "num_predict": 4096},
    }
    request = Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=1800) as response:
        result = json.loads(response.read())
    raw_text = result.get("message", {}).get("content", "")
    parsed = BatchProviderShape.model_validate_json(raw_text)
    usage = {
        "input_tokens": int(result.get("prompt_eval_count", 0)),
        "output_tokens": int(result.get("eval_count", 0)),
    }
    raw = {
        "provider": "ollama-local",
        "model": result.get("model", model),
        "model_digest": MODEL_DIGEST,
        "response": raw_text,
        "usage": usage,
    }
    return ProviderReply("completed", parsed=parsed.model_dump(mode="json")["reviews"], raw_response=raw, usage=usage)


def _evaluate(outcomes: list[ReviewOutcome], truth: dict[str, dict]) -> dict:
    by_id = {item.transaction_id: item for item in outcomes}
    if set(by_id) != set(truth):
        raise ValueError("pilot and truth ID sets differ")
    records = []
    counts = Counter()
    for tx_id in PILOT_IDS:
        outcome, expected = by_id[tx_id], truth[tx_id]
        joint = outcome.final_group == expected["group"] and outcome.final_status == expected["status"]
        legacy_joint = outcome.legacy.group == expected["group"] and outcome.legacy.status == expected["status"]
        counts["review_joint_correct"] += int(joint)
        counts["legacy_joint_correct"] += int(legacy_joint)
        counts["review_flags"] += int(outcome.flag)
        counts["hard_negative_false_flags"] += int(outcome.flag and expected["hard_negative"])
        counts["degraded"] += int(outcome.degraded)
        records.append({
            "transaction_id": tx_id,
            "scenario_id": expected["scenario_id"],
            "hard_negative": expected["hard_negative"],
            "legacy_group": outcome.legacy.group,
            "legacy_status": outcome.legacy.status,
            "reviewed_group": outcome.final_group,
            "reviewed_status": outcome.final_status,
            "truth_group": expected["group"],
            "truth_status": expected["status"],
            "review_status": outcome.review_status,
            "flag": outcome.flag,
            "reason": outcome.proposal.reason if outcome.proposal else None,
        })
    return {
        "model": MODEL_ID,
        "provider": "Ollama local; no OpenAI API call",
        "pilot_ids": list(PILOT_IDS),
        "sample_size": len(PILOT_IDS),
        "metrics": dict(counts),
        "records": records,
    }


def run_pilot(model: str = DEFAULT_MODEL, cache_path: Path | None = None, output_path: Path | None = None) -> dict:
    transactions_path = ROOT / "data/transactions/main_90_days.json"
    truth_path = ROOT / "data/ground_truth/main_90_days.json"
    cache_path = cache_path or ROOT / "cache/local_qwen35_9b_pilot.jsonl"
    output_path = output_path or ROOT / "reports/local_qwen35_9b_pilot.json"

    normalized = load_input(transactions_path)
    transactions = {item.transaction_id: item for item in normalized.transactions}
    requests = tuple(
        build_request(transactions[tx_id], label_transaction(transactions[tx_id]))
        for tx_id in PILOT_IDS
    )
    batch = build_batch_request(requests)
    identity = batch_identity(requests, MODEL_ID, batch.system_prompt, batch.user_prompt)
    cache = BatchReviewCache(cache_path)
    try:
        reply = cache.replay(identity)
        cache_hit = True
    except CacheMiss:
        reply = _call_ollama(model, batch.system_prompt, batch.user_prompt)
        cache_hit = False

    if reply.status != "completed" or not isinstance(reply.parsed, list):
        raise RuntimeError(f"local model returned {reply.status}")
    by_id = {item["transaction_id"]: item for item in reply.parsed}
    if len(by_id) != len(reply.parsed) or set(by_id) != {r.transaction.transaction_id for r in requests}:
        raise ValueError("local model omitted or duplicated pilot transaction IDs")
    outcomes = [
        review_one(
            request,
            _StaticProvider(ProviderReply("completed", parsed=by_id[request.transaction.transaction_id])),
        )
        for request in requests
    ]
    validated = [_outcome_record(outcome) for outcome in outcomes]
    if cache_hit:
        if cache.validated_outcomes(identity) != validated:
            raise ValueError("cached local outcomes differ from revalidated outputs")
    else:
        cache.append(identity, reply, validated)

    truth_doc = json.loads(truth_path.read_text(encoding="utf-8"))
    truth = {tx_id: truth_doc["labels"][tx_id] for tx_id in PILOT_IDS}
    report = _evaluate(outcomes, truth)
    report.update({
        "cache_hit": cache_hit,
        "cache_file": str(cache_path.relative_to(ROOT)),
        "output_sha256": hashlib.sha256(json.dumps(validated, sort_keys=True).encode()).hexdigest(),
        "ollama_usage_tokens": reply.usage,
        "api_cost_usd": "0",
    })
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a 20-record local Ollama reviewer pilot")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    report = run_pilot(args.model)
    print(json.dumps({key: report[key] for key in ("provider", "model", "sample_size", "metrics", "ollama_usage_tokens", "api_cost_usd", "cache_hit")}, sort_keys=True))


if __name__ == "__main__":
    main()
