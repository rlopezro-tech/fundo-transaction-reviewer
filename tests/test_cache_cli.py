"""Ticket 05: strict replay, invalidation, budget and truth-free CLI evidence."""

import hashlib
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from openai import RateLimitError

from fundo_reviewer import cache as cache_module
from fundo_reviewer.cache import (
    BatchReviewCache, BudgetExceeded, CacheCorrupt, CacheMiss, ReviewCache, SpendLedger,
    batch_identity, pricing_version, request_key, usage_derived_cost,
)
from fundo_reviewer.cli import run_pipeline
from fundo_reviewer.data import load_input
from fundo_reviewer.legacy import label_transaction
from fundo_reviewer.provider import (
    BatchProviderShape, BudgetedBatchProvider, BudgetedProvider, OpenAIProvider, build_batch_request,
)
from fundo_reviewer.reviewer import FatalReviewError, ProviderReply, build_request, review_one


ROOT = Path(__file__).resolve().parents[1]
SMALL = ROOT / "tests" / "fixtures" / "input_90_days.json"


def _request():
    transaction = load_input(SMALL).transactions[0]
    return build_request(transaction, label_transaction(transaction))


class FakeProvider:
    def __init__(self, *, decision="keep", failure=None):
        self.calls = 0
        self.decision = decision
        self.failure = failure

    def review(self, request):
        self.calls += 1
        if self.failure:
            if isinstance(self.failure, Exception):
                raise self.failure
            return ProviderReply(self.failure, raw_response={"status": self.failure}, usage={"input_tokens": 10, "output_tokens": 5})
        group = request.legacy.group if self.decision == "keep" else "Not average monthly revenue"
        if group == request.legacy.group and self.decision == "change":
            group = "unmatched"
        parsed = {
            "transaction_id": request.transaction.transaction_id,
            "decision": self.decision,
            "group": group,
            "status": request.legacy.status,
            "confidence": 0.8,
            "reason": "Fake response for test",
        }
        return ProviderReply("completed", parsed=parsed, raw_response={"parsed": parsed},
                             usage={"input_tokens": 100, "output_tokens": 40})


class FakeBatchProvider:
    def __init__(self, omit_one=False):
        self.calls = 0
        self.omit_one = omit_one

    def review_batch(self, batch):
        self.calls += 1
        reviews = [
            {
                "transaction_id": request.transaction.transaction_id,
                "decision": "keep", "group": request.legacy.group,
                "status": request.legacy.status, "confidence": 0.7,
                "reason": "Batch fake sees existing legacy label",
            }
            for request in batch.requests
        ]
        if self.omit_one:
            reviews = reviews[1:]
        return ProviderReply("completed", parsed=list(reversed(reviews)),
                             raw_response={"output_text": json.dumps(reviews)},
                             usage={"input_tokens": 300, "output_tokens": 100})


def test_request_key_invalidates_every_relevant_field_and_version(monkeypatch):
    request = _request()
    original = request_key(request, "gpt-6-luna")
    assert request_key(request, "other-model") != original
    changed_payload = {**request.payload, "transaction": {**request.payload["transaction"], "name": "CHANGED"}}
    assert request_key(replace(request, payload=changed_payload), "gpt-6-luna") != original
    changed_transaction = replace(load_input(SMALL).transactions[0], name="NEW CUSTOMER DESCRIPTION")
    changed_request = build_request(changed_transaction, label_transaction(changed_transaction))
    assert request_key(changed_request, "gpt-6-luna") != original
    changed_legacy = replace(request.legacy, group="NSFs")
    assert request_key(replace(request, legacy=changed_legacy), "gpt-6-luna") != original
    changed_ruleset = replace(request.legacy, ruleset_version="legacy-v2")
    assert request_key(replace(request, legacy=changed_ruleset), "gpt-6-luna") != original
    assert request_key(replace(request, system_prompt="new prompt"), "gpt-6-luna") != original
    for name in ("PROMPT_VERSION", "SCHEMA_VERSION", "FLAG_POLICY_VERSION", "REVENUE_POLICY_VERSION"):
        current = getattr(cache_module, name)
        with monkeypatch.context() as patch:
            patch.setattr(cache_module, name, current + "-changed")
            assert request_key(request, "gpt-6-luna") != original
    assert request_key(request, "gpt-6-luna") == original
    identity_text = json.dumps(cache_module.request_identity(request, "gpt-6-luna"))
    assert "ground_truth" not in identity_text and "scenario_id" not in identity_text


def test_cache_hit_miss_integrity_and_validated_only(tmp_path):
    request = _request()
    path = tmp_path / "reviews.jsonl"
    store = ReviewCache(path)
    with pytest.raises(CacheMiss):
        store.replay(request, "gpt-6-luna")
    outcome = review_one(request, FakeProvider())
    store.append(request, "gpt-6-luna", outcome, usage_derived_cost(outcome.usage))
    replayed = ReviewCache(path).replay(request, "gpt-6-luna")
    assert review_one(request, type("Static", (), {"review": lambda self, _: replayed})()).review_status == "kept"
    with pytest.raises(CacheMiss):
        store.replay(request, "other-model")
    with pytest.raises(ValueError, match="duplicate"):
        store.append(request, "gpt-6-luna", outcome, Decimal(0))
    invalid = review_one(request, FakeProvider(failure="refused"))
    with pytest.raises(ValueError, match="only validated"):
        store.append(request, "other-model", invalid, Decimal(0))
    line = path.read_text().replace("Fake response for test", "Tampered response")
    path.write_text(line)
    with pytest.raises(CacheCorrupt, match="integrity"):
        ReviewCache(path)


def test_spend_ledger_reservation_persists_and_budget_blocks_before_call(tmp_path):
    path = tmp_path / "spend.jsonl"
    request = _request()
    ledger = SpendLedger(path, ceiling_usd=Decimal("0.001"))
    first = ledger.reserve(request, "gpt-6-luna")
    assert first.reserved_usd > 0
    assert SpendLedger(path, ceiling_usd=Decimal("0.001")).committed_usd == first.reserved_usd
    settled = ledger.settle(first, {"input_tokens": 100, "output_tokens": 40})
    assert settled == Decimal("0.000030")
    assert SpendLedger(path, ceiling_usd=Decimal("0.001")).settled_usd == settled
    with pytest.raises(BudgetExceeded):
        ledger.reserve(request, "gpt-6-luna", max_output_tokens=10_000)
    assert len(path.read_text().splitlines()) == 2
    with pytest.raises(ValueError, match="below"):
        SpendLedger(tmp_path / "invalid.jsonl", ceiling_usd=Decimal("10.00"))


def test_unsafe_budget_blocks_provider_before_any_paid_call(tmp_path):
    request = _request()
    provider = FakeProvider()
    ledger = SpendLedger(tmp_path / "tiny.jsonl", ceiling_usd=Decimal("0.000001"))
    with pytest.raises(BudgetExceeded):
        review_one(request, BudgetedProvider(provider, ledger, "gpt-6-luna"))
    assert provider.calls == 0
    with pytest.raises(BudgetExceeded, match="no approved price"):
        review_one(request, BudgetedProvider(provider, ledger, "unpriced-model"))
    assert provider.calls == 0


def test_batch_key_changes_with_context_and_budget_blocks_before_call(tmp_path):
    first = _request()
    second_transaction = load_input(SMALL).transactions[1]
    second = build_request(second_transaction, label_transaction(second_transaction))
    one = build_batch_request((first,))
    two = build_batch_request((first, second))
    key_one = batch_identity(one.requests, "gpt-6-luna", one.system_prompt, one.user_prompt)
    key_two = batch_identity(two.requests, "gpt-6-luna", two.system_prompt, two.user_prompt)
    assert key_one != key_two
    fake = FakeBatchProvider()
    guard = BudgetedBatchProvider(fake, SpendLedger(tmp_path / "tiny.jsonl", ceiling_usd=Decimal("0.000001")),
                                  "gpt-6-luna")
    with pytest.raises(BudgetExceeded):
        guard.review_batch(two)
    assert fake.calls == 0


def test_alternative_model_has_distinct_price_budget_and_cache_key(tmp_path):
    request = _request()
    assert request_key(request, "gpt-5.6-luna") != request_key(request, "gpt-6-luna")
    assert pricing_version("gpt-5.6-luna") != pricing_version("gpt-6-luna")
    usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
    assert usage_derived_cost(usage, "gpt-5.6-luna") == Decimal("1.40")
    assert usage_derived_cost(usage, "gpt-6-luna") == Decimal("0.60")
    ledger = SpendLedger(tmp_path / "mixed.jsonl")
    first = ledger.reserve(request, "gpt-6-luna")
    second = ledger.reserve(request, "gpt-5.6-luna")
    assert second.reserved_usd > first.reserved_usd
    ledger.settle(first, {"input_tokens": 100, "output_tokens": 40})
    ledger.settle(second, {"input_tokens": 100, "output_tokens": 40})
    assert ledger.settled_usd == Decimal("0.000030") + Decimal("0.000068")
    assert SpendLedger(tmp_path / "mixed.jsonl").settled_usd == ledger.settled_usd


def test_local_ollama_cache_has_zero_api_cost_and_stable_pricing_version():
    model = "ollama:qwen3.5:9b-q4_K_M@sha256-example"
    assert pricing_version(model) == "ollama-local-no-api-cost-v1"
    assert usage_derived_cost({"input_tokens": 10_000, "output_tokens": 5_000}, model) == Decimal(0)


def test_alternative_model_batch_replays_without_key_at_its_own_price(tmp_path, monkeypatch):
    path = tmp_path / "alternative.jsonl"
    ledger = tmp_path / "ledger.jsonl"
    fake = FakeBatchProvider()
    online = run_pipeline(SMALL, tmp_path / "online", "online", path, ledger,
                          model="gpt-5.6-luna", provider=fake, batch_size=80)
    assert online["degraded_count"] == 0
    assert online["versions"]["pricing"] == pricing_version("gpt-5.6-luna")
    assert online["new_usage_derived_cost_usd"] == str(usage_derived_cost(
        online["new_provider_usage"], "gpt-5.6-luna"
    ))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    offline = run_pipeline(SMALL, tmp_path / "offline", "offline", path, ledger,
                           model="gpt-5.6-luna", batch_size=80)
    assert offline["cache_hits"] == online["accepted_transactions"]
    assert (tmp_path / "online" / "review_outcomes.json").read_bytes() == (
        tmp_path / "offline" / "review_outcomes.json"
    ).read_bytes()
    with pytest.raises(CacheMiss):
        run_pipeline(SMALL, tmp_path / "wrong_model", "offline", path, ledger,
                     model="gpt-6-luna", batch_size=80)


def test_online_fill_then_no_key_offline_replay_is_byte_identical(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache" / "reviews.jsonl"
    ledger_path = tmp_path / "cache" / "spend.jsonl"
    online_out = tmp_path / "online"
    first_offline = tmp_path / "offline1"
    second_offline = tmp_path / "offline2"
    provider = FakeProvider()
    manifest = run_pipeline(SMALL, online_out, "online", cache_path, ledger_path, provider=provider)
    assert manifest["accepted_transactions"] == provider.calls
    assert manifest["new_api_calls"] == provider.calls
    assert manifest["degraded_count"] == 0
    assert manifest["accuracy"] == "not_measured_without_separate_truth_evaluation"
    assert ledger_path.exists() and cache_path.exists()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("fundo_reviewer.cli.OpenAIProvider", lambda *args: pytest.fail("offline loaded provider"))
    replay = run_pipeline(SMALL, first_offline, "offline", cache_path, ledger_path)
    run_pipeline(SMALL, second_offline, "offline", cache_path, ledger_path)
    assert replay["cache_hits"] == provider.calls and replay["new_api_calls"] == 0
    for file_name in ("review_outcomes.json", "run_manifest.json"):
        assert (first_offline / file_name).read_bytes() == (second_offline / file_name).read_bytes()
    assert (online_out / "review_outcomes.json").read_bytes() == (first_offline / "review_outcomes.json").read_bytes()
    assert "OPENAI_API_KEY" not in cache_path.read_text()
    assert "ground_truth" not in cache_path.read_text()
    assert "scenario_id" not in cache_path.read_text()


def test_uncached_strict_offline_new_input_fails_and_online_failure_degrades(tmp_path):
    cache_path = tmp_path / "cache.jsonl"
    ledger_path = tmp_path / "spend.jsonl"
    with pytest.raises(CacheMiss):
        run_pipeline(SMALL, tmp_path / "offline", "offline", cache_path, ledger_path)
    assert not (tmp_path / "offline" / "run_manifest.json").exists()
    provider = FakeProvider(failure=TimeoutError("outage"))
    manifest = run_pipeline(SMALL, tmp_path / "failed", "online", cache_path, ledger_path, provider=provider)
    assert manifest["degraded_count"] == provider.calls == manifest["accepted_transactions"]
    assert manifest["review_status_counts"] == {"provider_failure": provider.calls}
    assert not cache_path.exists()  # failure is never a valid keep cache entry
    with pytest.raises(CacheMiss):
        run_pipeline(SMALL, tmp_path / "offline_after_failure", "offline", cache_path, ledger_path)


def test_new_truth_free_envelope_is_accepted_online_without_accuracy_claim(tmp_path):
    source = json.loads(SMALL.read_text())
    source["transactions"] = source["transactions"][:1]
    source["transactions"][0]["transaction_id"] = "tx_new_unseen"
    input_path = tmp_path / "new.json"
    input_path.write_text(json.dumps(source))
    manifest = run_pipeline(input_path, tmp_path / "output", "online", tmp_path / "cache.jsonl",
                            tmp_path / "spend.jsonl", provider=FakeProvider())
    assert manifest["accepted_transactions"] == 1
    assert manifest["accuracy"] == "not_measured_without_separate_truth_evaluation"
    assert "truth" not in (tmp_path / "output" / "review_outcomes.json").read_text()
    assert hashlib.sha256((tmp_path / "output" / "review_outcomes.json").read_bytes()).hexdigest()


def test_batch_review_replays_all_ids_without_key_and_detects_corruption(tmp_path, monkeypatch):
    path = tmp_path / "batch.jsonl"
    ledger = tmp_path / "ledger.jsonl"
    fake = FakeBatchProvider()
    online = run_pipeline(SMALL, tmp_path / "online", "online", path, ledger,
                          provider=fake, batch_size=2)
    assert fake.calls == online["new_api_calls"]
    assert online["accepted_transactions"] == sum(online["review_status_counts"].values())
    assert online["degraded_count"] == 0
    assert len(BatchReviewCache(path).entries) == fake.calls
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("fundo_reviewer.cli.OpenAIProvider", lambda *args: pytest.fail("offline loaded provider"))
    offline = run_pipeline(SMALL, tmp_path / "offline", "offline", path, ledger, batch_size=2)
    assert offline["cache_hits"] == online["accepted_transactions"]
    assert offline["cache_batch_hits"] == fake.calls
    assert (tmp_path / "online" / "review_outcomes.json").read_bytes() == (
        tmp_path / "offline" / "review_outcomes.json"
    ).read_bytes()
    lines = path.read_text().splitlines()
    path.write_text("\n".join(lines).replace("Batch fake", "Tampered fake") + "\n")
    with pytest.raises(CacheCorrupt):
        run_pipeline(SMALL, tmp_path / "corrupt", "offline", path, ledger, batch_size=2)


def test_batch_missing_id_is_explicit_degraded_not_silent_keep(tmp_path):
    path = tmp_path / "batch.jsonl"
    ledger = tmp_path / "ledger.jsonl"
    online = run_pipeline(SMALL, tmp_path / "online", "online", path, ledger,
                          provider=FakeBatchProvider(omit_one=True), batch_size=2)
    assert online["degraded_count"] == online["accepted_transactions"]
    assert online["review_status_counts"] == {"invalid_response": online["accepted_transactions"]}
    offline = run_pipeline(SMALL, tmp_path / "offline", "offline", path, ledger, batch_size=2)
    assert offline["review_status_counts"] == online["review_status_counts"]
    assert not any(record["flag"] for record in json.loads((tmp_path / "offline" / "review_outcomes.json").read_text()))


def test_openrouter_degraded_batch_stops_after_caching_response(tmp_path):
    path = tmp_path / "openrouter.jsonl"
    ledger = tmp_path / "ledger.jsonl"
    with pytest.raises(FatalReviewError, match="OpenRouter batch response was degraded"):
        run_pipeline(
            SMALL, tmp_path / "online", "online", path, ledger,
            model="openrouter/openai/gpt-oss-20b",
            provider=FakeBatchProvider(omit_one=True), batch_size=2,
        )
    assert path.exists()
    # A cached malformed response is still not treated as a success on replay.
    with pytest.raises(FatalReviewError, match="OpenRouter batch response was degraded"):
        run_pipeline(
            SMALL, tmp_path / "offline", "offline", path, ledger,
            model="openrouter/openai/gpt-oss-20b", batch_size=2,
        )


def test_batch_transport_failure_degrades_but_can_be_retried_online(tmp_path):
    class FailingBatchProvider:
        def review_batch(self, batch):
            raise TimeoutError("temporary outage")

    path = tmp_path / "batch.jsonl"
    ledger = tmp_path / "ledger.jsonl"
    failed = run_pipeline(SMALL, tmp_path / "failed", "online", path, ledger,
                          provider=FailingBatchProvider(), batch_size=80)
    assert failed["degraded_count"] == failed["accepted_transactions"]
    assert failed["review_status_counts"] == {"provider_failure": failed["accepted_transactions"]}
    assert not path.exists()  # no model answer to replay, unlike a refusal
    with pytest.raises(CacheMiss):
        run_pipeline(SMALL, tmp_path / "offline", "offline", path, ledger, batch_size=80)
    recovered = run_pipeline(SMALL, tmp_path / "recovered", "online", path, ledger,
                             provider=FakeBatchProvider(), batch_size=80)
    assert recovered["degraded_count"] == 0
    assert path.exists()


def test_full_2000_record_batch_pipeline_fake_replays_without_key(tmp_path, monkeypatch):
    main = ROOT / "data" / "transactions" / "main_90_days.json"
    cache_path = tmp_path / "batch.jsonl"
    ledger_path = tmp_path / "ledger.jsonl"
    fake = FakeBatchProvider()
    online = run_pipeline(main, tmp_path / "online", "online", cache_path, ledger_path,
                          provider=fake, batch_size=80)
    assert online["accepted_transactions"] == 2000
    assert online["new_api_calls"] == fake.calls == 25
    assert online["degraded_count"] == 0
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    offline = run_pipeline(main, tmp_path / "offline", "offline", cache_path, ledger_path,
                           batch_size=80)
    assert offline["cache_hits"] == 2000
    assert offline["cache_batch_hits"] == 25
    assert offline["new_api_calls"] == 0
    assert (tmp_path / "online" / "review_outcomes.json").read_bytes() == (
        tmp_path / "offline" / "review_outcomes.json"
    ).read_bytes()


def test_openai_batch_adapter_uses_structured_outputs_without_tools_or_key(monkeypatch):
    request = _request()
    proposal = {
        "transaction_id": request.transaction.transaction_id,
        "decision": "keep", "group": request.legacy.group,
        "status": request.legacy.status, "confidence": 0.7, "reason": "Supported",
    }
    response = SimpleNamespace(
        id="resp_fake", status="completed", model="gpt-6-luna",
        output_text=json.dumps({"reviews": [proposal]}), output=[],
        usage=SimpleNamespace(input_tokens=300, output_tokens=100),
        output_parsed=BatchProviderShape.model_validate({"reviews": [proposal]}),
    )
    captured = {}

    class FakeResponses:
        def parse(self, **kwargs):
            captured.update(kwargs)
            return response

    adapter = object.__new__(OpenAIProvider)
    adapter.model = "gpt-6-luna"
    adapter.client = SimpleNamespace(responses=FakeResponses())
    adapter._last_call_at = None
    reply = adapter.review_batch(build_batch_request((request,)))
    assert reply.status == "completed" and reply.parsed == [proposal]
    assert reply.raw_response["output_text"] == response.output_text
    assert reply.usage == {"input_tokens": 300, "output_tokens": 100}
    assert captured["model"] == "gpt-6-luna"
    assert captured["text_format"] is BatchProviderShape
    assert captured["max_output_tokens"] == 16000
    assert captured["store"] is False and captured["reasoning"] == {"effort": "none"}
    assert "tools" not in captured


def test_openai_credit_exhaustion_is_fatal_without_retries():
    calls = []

    class NoCreditResponses:
        def parse(self, **kwargs):
            calls.append(kwargs)
            response = httpx.Response(429, request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
            raise RateLimitError(
                "insufficient_quota: credit_balance_exhausted: You have no credits remaining",
                response=response, body={"code": "credit_balance_exhausted"},
            )

    adapter = object.__new__(OpenAIProvider)
    adapter.model = "gpt-5.6-luna"
    adapter.client = SimpleNamespace(responses=NoCreditResponses())
    adapter._last_call_at = None
    with pytest.raises(FatalReviewError, match="credit balance exhausted"):
        adapter.review_batch(build_batch_request((_request(),)))
    assert len(calls) == 1
