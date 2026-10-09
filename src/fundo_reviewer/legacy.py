"""Versioned, deliberately imperfect literal-keyword baseline (Ticket 03)."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Iterable

from fundo_reviewer.data import NormalizedTransaction
from fundo_reviewer.revenue import GROUPS, UNMATCHED, is_revenue_eligible


RULESET_VERSION = "legacy-v1"

# Approved BUSINESS_RULES.md priority; never derive it from a dict's iteration.
PRECEDENCE = (
    "NSFs",
    "Overdraft",
    "High risk — garnishment",
    "High risk — bankruptcy",
    "High risk — debt settlement payments",
    "High risk — gambling",
    "High risk — other",
    "Internal transfer",
    "Active advance",
    "UCC",
    "Not average monthly revenue",
    "Revenue verification",
    "Auto deposit",
)
if set(PRECEDENCE) != set(GROUPS) or len(PRECEDENCE) != len(GROUPS):
    raise AssertionError("precedence must list each of the 13 groups exactly once")
_PRIORITY = {group: rank for rank, group in enumerate(PRECEDENCE)}


@dataclass(frozen=True, slots=True)
class KeywordRule:
    rule_id: str
    group: str
    keyword: str


# Stable IDs and keywords are the approved v1 starter rules, not learned from truth.
RULES = (
    KeywordRule("NAMR_01", "Not average monthly revenue", "tax refund"),
    KeywordRule("NAMR_02", "Not average monthly revenue", "insurance payout"),
    KeywordRule("NAMR_03", "Not average monthly revenue", "refund"),
    KeywordRule("NAMR_04", "Not average monthly revenue", "reversal"),
    KeywordRule("NSF_01", "NSFs", "nsf"),
    KeywordRule("NSF_02", "NSFs", "returned item"),
    KeywordRule("OD_01", "Overdraft", "overdraft"),
    KeywordRule("OD_02", "Overdraft", "od fee"),
    KeywordRule("XFER_01", "Internal transfer", "internal transfer"),
    KeywordRule("XFER_02", "Internal transfer", "xfer own"),
    KeywordRule("UCC_01", "UCC", "ucc-1"),
    KeywordRule("UCC_02", "UCC", "ucc filing"),
    KeywordRule("ADV_01", "Active advance", "square"),
    KeywordRule("ADV_02", "Active advance", "capital"),
    KeywordRule("ADV_03", "Active advance", "funding"),
    KeywordRule("ADV_04", "Active advance", "advance"),
    KeywordRule("AUTO_01", "Auto deposit", "auto deposit"),
    KeywordRule("AUTO_02", "Auto deposit", "direct deposit"),
    KeywordRule("REV_01", "Revenue verification", "merchant settlement"),
    KeywordRule("REV_02", "Revenue verification", "processor"),
    KeywordRule("REV_03", "Revenue verification", "sales deposit"),
    KeywordRule("GAMB_01", "High risk — gambling", "casino"),
    KeywordRule("GAMB_02", "High risk — gambling", "sportsbook"),
    KeywordRule("BK_01", "High risk — bankruptcy", "bankruptcy"),
    KeywordRule("BK_02", "High risk — bankruptcy", "chapter 11"),
    KeywordRule("DEBT_01", "High risk — debt settlement payments", "debt settlement"),
    KeywordRule("DEBT_02", "High risk — debt settlement payments", "debt relief"),
    KeywordRule("GARN_01", "High risk — garnishment", "garnishment"),
    KeywordRule("GARN_02", "High risk — garnishment", "wage levy"),
    KeywordRule("RISK_01", "High risk — other", "fraud recovery"),
    KeywordRule("RISK_02", "High risk — other", "collection agency"),
)
PERSONAL_RULES = (
    ("PERS_01", "personal"),
    ("PERS_02", "owner draw"),
    ("PERS_03", "owner contribution"),
    ("PERS_04", "family transfer"),
    ("PERS_05", "household"),
)
if len({rule.rule_id for rule in RULES}) != len(RULES):
    raise AssertionError("duplicate keyword rule ID")


def normalize_text(value: str) -> str:
    """NFKC, casefold, collapse whitespace; intentionally preserve punctuation."""
    if not isinstance(value, str):
        raise TypeError("keyword text must be a string")
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


@dataclass(frozen=True, slots=True)
class RuleMatch:
    rule_id: str
    group: str
    keyword: str
    fields: tuple[str, ...]
    precedence_rank: int


@dataclass(frozen=True, slots=True)
class LegacyLabel:
    transaction_id: str
    ruleset_version: str
    source_name: str
    source_merchant_name: str | None
    group: str
    status: str
    revenue_eligible: bool
    matched_rule_ids: tuple[str, ...]
    matches: tuple[RuleMatch, ...]
    personal_rule_ids: tuple[str, ...]
    winning_precedence_rank: int | None


def label_transaction(transaction: NormalizedTransaction) -> LegacyLabel:
    """Assign one group/status; never read scenario intent or synthetic truth."""
    fields = {"name": normalize_text(transaction.name)}
    if transaction.merchant_name is not None:
        fields["merchant_name"] = normalize_text(transaction.merchant_name)
    matches = tuple(
        sorted(
            (
                RuleMatch(
                    rule.rule_id,
                    rule.group,
                    rule.keyword,
                    tuple(field for field in ("name", "merchant_name") if rule.keyword in fields.get(field, "")),
                    _PRIORITY[rule.group],
                )
                for rule in RULES
                if any(rule.keyword in value for value in fields.values())
            ),
            key=lambda match: (match.precedence_rank, match.rule_id),
        )
    )
    personal_rule_ids = tuple(
        rule_id for rule_id, marker in PERSONAL_RULES
        if any(marker in value for value in fields.values())
    )
    group = matches[0].group if matches else UNMATCHED
    status = "personal" if personal_rule_ids else "business"
    return LegacyLabel(
        transaction_id=transaction.transaction_id,
        ruleset_version=RULESET_VERSION,
        source_name=transaction.raw.get("name", transaction.name),
        source_merchant_name=transaction.raw.get("merchant_name", transaction.merchant_name),
        group=group,
        status=status,
        revenue_eligible=is_revenue_eligible(transaction.amount, group=group, status=status),
        matched_rule_ids=tuple(match.rule_id for match in matches),
        matches=matches,
        personal_rule_ids=personal_rule_ids,
        winning_precedence_rank=matches[0].precedence_rank if matches else None,
    )


def label_transactions(transactions: Iterable[NormalizedTransaction]) -> tuple[LegacyLabel, ...]:
    """Emit stable input-contract order, independent of caller iteration order."""
    ordered = sorted(
        transactions,
        key=lambda item: (item.business_id, item.date, item.account_id, item.transaction_id),
    )
    seen: set[str] = set()
    labels: list[LegacyLabel] = []
    for transaction in ordered:
        if transaction.transaction_id in seen:
            raise ValueError(f"duplicate transaction ID {transaction.transaction_id!r}")
        seen.add(transaction.transaction_id)
        labels.append(label_transaction(transaction))
    return tuple(labels)
