"""Version-keyed, integrity-checked response cache and append-only spend guard."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from fundo_reviewer.revenue import REVENUE_POLICY_VERSION
from fundo_reviewer.reviewer import (
    FLAG_POLICY_VERSION, PROMPT_VERSION, SCHEMA_VERSION,
    FatalReviewError, ProviderReply, ReviewOutcome, ReviewRequest,
)


CACHE_VERSION = "review-cache-v1"
PRICING_VERSION = "gpt-6-luna-standard-2026-10-08"
PRICED_MODEL = "gpt-6-luna"
INPUT_USD_PER_MILLION = Decimal("0.10")
OUTPUT_USD_PER_MILLION = Decimal("0.50")
OPERATING_CEILING_USD = Decimal("8.00")
HARD_LIMIT_USD = Decimal("10.00")
MAX_OUTPUT_TOKENS = 500
BATCH_MAX_OUTPUT_TOKENS = 16000


class CacheMiss(LookupError):
    pass


class CacheCorrupt(ValueError):
    pass


class BudgetExceeded(FatalReviewError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def request_identity(request: ReviewRequest, model: str) -> dict[str, Any]:
    """Only whitelisted reviewer-visible data; no raw transaction or truth."""
    return {
        "cache_version": CACHE_VERSION,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "flag_policy_version": FLAG_POLICY_VERSION,
        "revenue_policy_version": REVENUE_POLICY_VERSION,
        "ruleset_version": request.legacy.ruleset_version,
        "legacy_group": request.legacy.group,
        "legacy_status": request.legacy.status,
        "legacy_matched_rule_ids": list(request.legacy.matched_rule_ids),
        "legacy_personal_rule_ids": list(request.legacy.personal_rule_ids),
        "system_prompt": request.system_prompt,
        "user_prompt": request.user_prompt,
        "payload": request.payload,
    }


def request_key(request: ReviewRequest, model: str) -> str:
    return _digest(request_identity(request, model))


class ReviewCache:
    def __init__(self, path: Path):
        self.path = path
        self.entries: dict[str, dict[str, Any]] = {}
        if path.exists():
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                try:
                    entry = json.loads(line)
                    integrity = entry.pop("integrity_sha256")
                    if integrity != _digest(entry):
                        raise ValueError("integrity hash mismatch")
                    if entry["key"] != _digest(entry["request_identity"]):
                        raise ValueError("request key mismatch")
                    if entry["status"] not in {"kept", "changed"}:
                        raise ValueError("degraded response cannot be cached as valid")
                    if entry["key"] in self.entries:
                        raise ValueError("duplicate cache key")
                    self.entries[entry["key"]] = entry
                except (ValueError, TypeError, KeyError) as exc:
                    raise CacheCorrupt(f"{path}:{line_number}: {exc}") from exc

    def replay(self, request: ReviewRequest, model: str) -> ProviderReply:
        identity = request_identity(request, model)
        key = _digest(identity)
        entry = self.entries.get(key)
        if entry is None:
            raise CacheMiss(f"cache miss for transaction {request.transaction.transaction_id} key {key}")
        if entry["request_identity"] != identity:
            raise CacheCorrupt(f"cache request mismatch for {key}")
        return ProviderReply(
            status="completed", parsed=entry["proposal"],
            raw_response=entry["raw_response"], usage=entry["usage"],
        )

    def append(self, request: ReviewRequest, model: str, outcome: ReviewOutcome, cost_usd: Decimal) -> None:
        if outcome.review_status not in {"kept", "changed"} or outcome.proposal is None:
            raise ValueError("only validated keep/change responses may enter the replay cache")
        identity = request_identity(request, model)
        key = _digest(identity)
        if key in self.entries:
            raise ValueError(f"duplicate cache key {key}")
        entry = {
            "key": key,
            "request_identity": identity,
            "status": outcome.review_status,
            "proposal": outcome.proposal.model_dump(mode="json"),
            "raw_response": outcome.raw_response,
            "usage": outcome.usage,
            "pricing_version": PRICING_VERSION,
            "usage_derived_cost_usd": str(cost_usd),
        }
        integrity = _digest(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(_canonical({**entry, "integrity_sha256": integrity}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.entries[key] = entry


def batch_identity(requests: tuple[ReviewRequest, ...], model: str, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    return {
        "batch_version": "review-batch-v1",
        "model": model,
        "request_keys": [request_key(request, model) for request in requests],
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "flag_policy_version": FLAG_POLICY_VERSION,
        "revenue_policy_version": REVENUE_POLICY_VERSION,
    }


class BatchReviewCache:
    """One integrity-checked raw response per exact batch of reviewer-visible requests."""

    def __init__(self, path: Path):
        self.path = path
        self.entries: dict[str, dict[str, Any]] = {}
        if path.exists():
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                try:
                    entry = json.loads(line)
                    integrity = entry.pop("integrity_sha256")
                    if integrity != _digest(entry) or entry["key"] != _digest(entry["identity"]):
                        raise ValueError("batch cache integrity/key mismatch")
                    if entry["key"] in self.entries:
                        raise ValueError("duplicate batch cache key")
                    self.entries[entry["key"]] = entry
                except (ValueError, TypeError, KeyError) as exc:
                    raise CacheCorrupt(f"{path}:{line_number}: {exc}") from exc

    def replay(self, identity: dict[str, Any]) -> ProviderReply:
        key = _digest(identity)
        entry = self.entries.get(key)
        if entry is None:
            raise CacheMiss(f"batch cache miss for key {key}")
        if entry["identity"] != identity:
            raise CacheCorrupt(f"batch request mismatch for key {key}")
        return ProviderReply(
            entry["status"], entry["parsed"], entry["raw_response"], entry["usage"]
        )

    def validated_outcomes(self, identity: dict[str, Any]) -> list[dict[str, Any]]:
        key = _digest(identity)
        entry = self.entries.get(key)
        if entry is None:
            raise CacheMiss(f"batch cache miss for key {key}")
        return entry["validated_outcomes"]

    def append(self, identity: dict[str, Any], reply: ProviderReply, validated_outcomes: list[dict[str, Any]]) -> None:
        key = _digest(identity)
        if key in self.entries:
            raise ValueError(f"duplicate batch cache key {key}")
        entry = {
            "key": key,
            "identity": identity,
            "status": reply.status,
            "parsed": reply.parsed,
            "raw_response": reply.raw_response,
            "usage": reply.usage,
            "validated_outcomes": validated_outcomes,
            "pricing_version": PRICING_VERSION,
            "usage_derived_cost_usd": str(usage_derived_cost(reply.usage)),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(_canonical({**entry, "integrity_sha256": _digest(entry)}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.entries[key] = entry


def usage_derived_cost(usage: dict[str, int] | None) -> Decimal:
    """Conservative standard-tier amount from actual token counts, no cache discount."""
    if not usage:
        return Decimal(0)
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    if (not isinstance(input_tokens, int) or not isinstance(output_tokens, int)
            or input_tokens < 0 or output_tokens < 0):
        raise ValueError("provider usage token counts must be nonnegative integers")
    return (Decimal(input_tokens) * INPUT_USD_PER_MILLION
            + Decimal(output_tokens) * OUTPUT_USD_PER_MILLION) / Decimal(1_000_000)


@dataclass(frozen=True)
class Reservation:
    call_id: str
    reserved_usd: Decimal


class SpendLedger:
    """Append-only reservations survive crashes and later invocations.

    A reservation without a settlement remains charged to the safe budget.
    """

    def __init__(self, path: Path, ceiling_usd: Decimal = OPERATING_CEILING_USD):
        if ceiling_usd >= HARD_LIMIT_USD or ceiling_usd <= 0:
            raise ValueError("ceiling must be positive and strictly below $10")
        self.path = path
        self.ceiling_usd = ceiling_usd
        self.events: list[dict[str, Any]] = []
        if path.exists():
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                try:
                    event = json.loads(line)
                    integrity = event.pop("integrity_sha256")
                    if integrity != _digest(event):
                        raise ValueError("ledger integrity mismatch")
                    self.events.append(event)
                except (ValueError, KeyError, TypeError) as exc:
                    raise CacheCorrupt(f"{path}:{line_number}: {exc}") from exc
        self._balances()  # validate event pairing on load

    def _balances(self) -> tuple[Decimal, Decimal, dict[str, Decimal]]:
        reserved: dict[str, Decimal] = {}
        settled = Decimal(0)
        for event in self.events:
            call_id = event["call_id"]
            if event["type"] == "reserve":
                if call_id in reserved:
                    raise CacheCorrupt(f"duplicate reservation {call_id}")
                reserved[call_id] = Decimal(event["reserved_usd"])
            elif event["type"] == "settle":
                if call_id not in reserved:
                    raise CacheCorrupt(f"settlement without reservation {call_id}")
                limit = reserved.pop(call_id)
                cost = Decimal(event["usage_derived_cost_usd"])
                if cost < 0 or cost > limit:
                    raise CacheCorrupt(f"settlement exceeds reservation {call_id}")
                settled += cost
            else:
                raise CacheCorrupt(f"invalid ledger event type {event['type']!r}")
        outstanding = sum(reserved.values(), Decimal(0))
        return settled, outstanding, reserved

    @property
    def committed_usd(self) -> Decimal:
        settled, outstanding, _ = self._balances()
        return settled + outstanding

    @property
    def settled_usd(self) -> Decimal:
        return self._balances()[0]

    def _append(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(_canonical({**event, "integrity_sha256": _digest(event)}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.events.append(event)

    def reserve(self, request: ReviewRequest, model: str, max_output_tokens: int = MAX_OUTPUT_TOKENS) -> Reservation:
        if model != PRICED_MODEL:
            raise BudgetExceeded(f"no approved price/budget guard for model {model!r}")
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        # Deliberately overestimate tokenization using UTF-8 byte count plus
        # fixed framing/schema overhead. Standard price ignores discounts.
        input_bound = len((request.system_prompt + request.user_prompt).encode("utf-8")) + 3000
        reserved = usage_derived_cost({"input_tokens": input_bound, "output_tokens": max_output_tokens})
        if self.committed_usd + reserved > self.ceiling_usd:
            raise BudgetExceeded(f"next call may exceed ${self.ceiling_usd} operating ceiling")
        call_id = f"{request_key(request, model)}-{len(self.events):08d}"
        self._append({
            "type": "reserve", "call_id": call_id, "reserved_usd": str(reserved),
            "request_key": request_key(request, model), "model": model,
            "pricing_version": PRICING_VERSION,
            "at_utc": datetime.now(timezone.utc).isoformat(),
        })
        return Reservation(call_id, reserved)

    def reserve_batch(
        self, identity: dict[str, Any], model: str, system_prompt: str,
        user_prompt: str, max_output_tokens: int = BATCH_MAX_OUTPUT_TOKENS,
    ) -> Reservation:
        if model != PRICED_MODEL:
            raise BudgetExceeded(f"no approved price/budget guard for model {model!r}")
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        input_bound = len((system_prompt + user_prompt).encode("utf-8")) + 6000
        reserved = usage_derived_cost({"input_tokens": input_bound, "output_tokens": max_output_tokens})
        if self.committed_usd + reserved > self.ceiling_usd:
            raise BudgetExceeded(f"next batch may exceed ${self.ceiling_usd} operating ceiling")
        key = _digest(identity)
        call_id = f"{key}-{len(self.events):08d}"
        self._append({
            "type": "reserve", "call_id": call_id, "reserved_usd": str(reserved),
            "request_key": key, "model": model, "pricing_version": PRICING_VERSION,
            "at_utc": datetime.now(timezone.utc).isoformat(),
        })
        return Reservation(call_id, reserved)

    def settle(self, reservation: Reservation, usage: dict[str, int] | None) -> Decimal:
        cost = usage_derived_cost(usage)
        if cost > reservation.reserved_usd:
            raise BudgetExceeded("actual usage exceeded reserved worst-case cost; stop further calls")
        self._append({
            "type": "settle", "call_id": reservation.call_id,
            "usage": usage, "usage_derived_cost_usd": str(cost),
            "at_utc": datetime.now(timezone.utc).isoformat(),
        })
        return cost
