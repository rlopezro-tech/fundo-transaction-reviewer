"""One code-owned revenue policy shared by legacy and reviewed labels."""

from __future__ import annotations

from decimal import Decimal


REVENUE_POLICY_VERSION = "revenue-v1"
UNMATCHED = "unmatched"
GROUPS = (
    "Not average monthly revenue",
    "NSFs",
    "Overdraft",
    "Internal transfer",
    "UCC",
    "Active advance",
    "Auto deposit",
    "Revenue verification",
    "High risk — gambling",
    "High risk — bankruptcy",
    "High risk — debt settlement payments",
    "High risk — garnishment",
    "High risk — other",
)
ALLOWED_GROUPS = frozenset((*GROUPS, UNMATCHED))
REVENUE_EXCLUSIONS = frozenset(
    {
        "Not average monthly revenue",
        "NSFs",
        "Overdraft",
        "Internal transfer",
        "UCC",
        "Active advance",
        "High risk — gambling",
        "High risk — bankruptcy",
        "High risk — debt settlement payments",
        "High risk — garnishment",
        "High risk — other",
    }
)


def is_revenue_eligible(amount: Decimal, *, group: str, status: str) -> bool:
    """Return V1 eligibility; negative Plaid amount means a business inflow.

    Semantic labels can come from the keyword engine or a later validated
    reviewer proposal. Source amount is never supplied by the reviewer.
    """
    if not isinstance(amount, Decimal) or not amount.is_finite() or amount == 0:
        raise ValueError("amount must be a finite, nonzero Decimal from validated input")
    if group not in ALLOWED_GROUPS:
        raise ValueError(f"unsupported group {group!r}")
    if status not in {"business", "personal"}:
        raise ValueError(f"unsupported business/personal status {status!r}")
    return amount < 0 and status == "business" and group not in REVENUE_EXCLUSIONS
