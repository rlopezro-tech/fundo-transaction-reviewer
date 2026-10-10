"""Focused regression coverage for the OpenAI transport adapter."""

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from openai import RateLimitError

from fundo_reviewer.data import load_input
from fundo_reviewer.legacy import label_transaction
from fundo_reviewer.provider import BatchProviderShape, OpenAIProvider, build_batch_request
from fundo_reviewer.reviewer import FatalReviewError, build_request

ROOT = Path(__file__).resolve().parents[1]
SMALL = ROOT / "tests" / "fixtures" / "input_90_days.json"


def _request():
    transaction = load_input(SMALL).transactions[0]
    return build_request(transaction, label_transaction(transaction))


def test_openai_batch_adapter_uses_structured_outputs_without_tools_or_key():
    request = _request()
    proposal = {
        "transaction_id": request.transaction.transaction_id,
        "decision": "keep",
        "group": request.legacy.group,
        "status": request.legacy.status,
        "confidence": 0.7,
        "reason": "Supported",
    }
    response = SimpleNamespace(
        id="resp_fake",
        status="completed",
        model="gpt-6-luna",
        output_text=json.dumps({"reviews": [proposal]}),
        output=[],
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
            response = httpx.Response(
                429, request=httpx.Request("POST", "https://api.openai.com/v1/responses")
            )
            raise RateLimitError(
                "insufficient_quota: credit_balance_exhausted: You have no credits remaining",
                response=response,
                body={"code": "credit_balance_exhausted"},
            )

    adapter = object.__new__(OpenAIProvider)
    adapter.model = "gpt-5.6-luna"
    adapter.client = SimpleNamespace(responses=NoCreditResponses())
    adapter._last_call_at = None
    with pytest.raises(FatalReviewError, match="credit balance exhausted"):
        adapter.review_batch(build_batch_request((_request(),)))
    assert len(calls) == 1


def test_openai_structured_credit_code_is_classified_without_message_match():
    calls = []

    class StructuredQuotaResponses:
        def parse(self, **kwargs):
            calls.append(kwargs)
            response = httpx.Response(
                429, request=httpx.Request("POST", "https://api.openai.com/v1/responses")
            )
            raise RateLimitError(
                "Request rejected",
                response=response,
                body={"code": "insufficient_quota", "message": "billing restriction"},
            )

    adapter = object.__new__(OpenAIProvider)
    adapter.model = "gpt-6-luna"
    adapter.client = SimpleNamespace(responses=StructuredQuotaResponses())
    adapter._last_call_at = None
    with pytest.raises(FatalReviewError, match="credit balance exhausted"):
        adapter.review_batch(build_batch_request((_request(),)))
    assert len(calls) == 1


def test_openai_non_rate_limit_transport_errors_are_fatal_without_retries():
    calls = []

    class BrokenResponses:
        def parse(self, **kwargs):
            calls.append(kwargs)
            raise RuntimeError("sensitive provider error details")

    adapter = object.__new__(OpenAIProvider)
    adapter.model = "gpt-6-luna"
    adapter.client = SimpleNamespace(responses=BrokenResponses())
    adapter._last_call_at = None
    with pytest.raises(FatalReviewError, match=r"OpenAI request failed \(RuntimeError\)") as error:
        adapter.review_batch(build_batch_request((_request(),)))
    assert "sensitive provider error details" not in str(error.value)
    assert len(calls) == 1


def test_openai_long_retry_after_stops_without_retrying_early():
    calls = []

    class LongCooldownResponses:
        def parse(self, **kwargs):
            calls.append(kwargs)
            response = httpx.Response(
                429,
                headers={"retry-after": "30"},
                request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
            )
            raise RateLimitError(
                "Temporary rate limit",
                response=response,
                body={"code": "rate_limit_exceeded", "message": "try again later"},
            )

    adapter = object.__new__(OpenAIProvider)
    adapter.model = "gpt-6-luna"
    adapter.client = SimpleNamespace(responses=LongCooldownResponses())
    adapter._last_call_at = None
    with pytest.raises(FatalReviewError, match="OpenAI requested a long rate-limit cooldown"):
        adapter.review_batch(build_batch_request((_request(),)))
    assert len(calls) == 1
