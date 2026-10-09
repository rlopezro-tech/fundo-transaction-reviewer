"""Ticket 01: validate and normalize Plaid-shaped transaction envelopes.

This module deliberately does not assign labels, calculate revenue, or call a
provider. Rules are versioned in docs/rules/BUSINESS_RULES.md.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any


INPUT_CONTRACT_VERSION = "input-v1"
WINDOW_DAYS = 90
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_TRUTH_ONLY_FIELDS = frozenset(
    {
        "truth",
        "ground_truth",
        "truth_label",
        "scenario_id",
        "intended_group",
        "intended_personal",
        "intended_revenue",
        "hard_negative",
        "alternative_label",
    }
)


class InputValidationError(ValueError):
    """Input violates the project contract; the message names the offending field."""


@dataclass(frozen=True, slots=True)
class AccountCoverage:
    account_id: str
    business_id: str
    start: date
    end: date
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class BusinessCoverage:
    business_id: str
    account_ids: tuple[str, ...]
    start: date
    end: date
    days: int

    @property
    def is_complete_90_days(self) -> bool:
        return self.days == WINDOW_DAYS


@dataclass(frozen=True, slots=True)
class NormalizedTransaction:
    transaction_id: str
    business_id: str
    account_id: str
    date: date
    amount: Decimal
    name: str
    merchant_name: str | None
    category: tuple[str, ...] | None
    personal_finance_category: dict[str, Any] | None
    pending: bool
    pending_transaction_id: str | None
    raw: dict[str, Any]

    @property
    def is_inflow(self) -> bool:
        """Plaid Transactions: negative amount means money entering the account."""
        return self.amount < 0

    @property
    def is_outflow(self) -> bool:
        return self.amount > 0

    @property
    def magnitude(self) -> Decimal:
        return abs(self.amount)


@dataclass(frozen=True, slots=True)
class ExcludedTransaction:
    transaction_id: str
    reason: str
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class NormalizedInput:
    contract_version: str
    as_of: date
    window_start: date
    window_end: date
    accounts: tuple[AccountCoverage, ...]
    business_coverage: tuple[BusinessCoverage, ...]
    transactions: tuple[NormalizedTransaction, ...]
    excluded: tuple[ExcludedTransaction, ...]

    @property
    def exclusion_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(item.reason for item in self.excluded).items()))


def _reject_constant(value: str) -> None:
    raise InputValidationError(f"invalid JSON numeric constant {value!r}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise InputValidationError(f"duplicate JSON key {key!r}")
        obj[key] = value
    return obj


def load_input(path: str | Path) -> NormalizedInput:
    """Read one JSON envelope without requiring truth, an API key, or Plaid."""
    path = Path(path)
    try:
        contents = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise InputValidationError(f"cannot read input {path}: {exc}") from exc
    try:
        payload = json.loads(
            contents,
            parse_float=Decimal,
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except json.JSONDecodeError as exc:
        raise InputValidationError(
            f"invalid JSON in {path} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    return normalize_input(payload)


def _object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputValidationError(f"{location}: expected an object")
    return value


def _nonempty_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputValidationError(f"{location}: expected a nonempty string")
    return value.strip()


def _date(value: Any, location: str) -> date:
    if not isinstance(value, str) or not _ISO_DATE.fullmatch(value):
        raise InputValidationError(f"{location}: expected YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InputValidationError(f"{location}: invalid calendar date {value!r}") from exc


def _no_truth_fields(record: dict[str, Any], location: str) -> None:
    found = sorted(_TRUTH_ONLY_FIELDS.intersection(record))
    if found:
        raise InputValidationError(
            f"{location}: truth-only field(s) {', '.join(found)} belong in a separate file"
        )


def _amount(value: Any, location: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise InputValidationError(f"{location}: expected a JSON number, not a string or float")
    amount = Decimal(value)
    if not amount.is_finite():
        raise InputValidationError(f"{location}: amount must be finite")
    if amount == 0:
        raise InputValidationError(f"{location}: zero amount is not supported")
    if amount.as_tuple().exponent < -2:
        raise InputValidationError(f"{location}: USD amount may have at most two decimals")
    return amount


def _accounts(value: Any) -> tuple[AccountCoverage, ...]:
    if not isinstance(value, list) or not value:
        raise InputValidationError("accounts: expected a nonempty array")
    accounts: list[AccountCoverage] = []
    seen: set[str] = set()
    for index, value in enumerate(value):
        location = f"accounts[{index}]"
        record = _object(value, location)
        _no_truth_fields(record, location)
        account_id = _nonempty_string(record.get("account_id"), f"{location}.account_id")
        if account_id in seen:
            raise InputValidationError(f"{location}.account_id: duplicate {account_id!r}")
        seen.add(account_id)
        business_id = _nonempty_string(record.get("business_id"), f"{location}.business_id")
        start = _date(record.get("coverage_start"), f"{location}.coverage_start")
        end = _date(record.get("coverage_end"), f"{location}.coverage_end")
        if start > end:
            raise InputValidationError(f"{location}: coverage_start is after coverage_end")
        accounts.append(AccountCoverage(account_id, business_id, start, end, deepcopy(record)))
    return tuple(sorted(accounts, key=lambda account: account.account_id))


def _business_coverage(
    accounts: tuple[AccountCoverage, ...], window_start: date, as_of: date
) -> tuple[BusinessCoverage, ...]:
    grouped: dict[str, list[AccountCoverage]] = {}
    for account in accounts:
        grouped.setdefault(account.business_id, []).append(account)
    businesses: list[BusinessCoverage] = []
    for business_id, group in sorted(grouped.items()):
        start = max(window_start, *(account.start for account in group))
        end = min(as_of, *(account.end for account in group))
        if start > end:
            raise InputValidationError(
                f"business {business_id!r}: accounts have no common coverage in the 90-day window"
            )
        businesses.append(
            BusinessCoverage(
                business_id=business_id,
                account_ids=tuple(sorted(account.account_id for account in group)),
                start=start,
                end=end,
                days=(end - start).days + 1,
            )
        )
    return tuple(businesses)


def _transaction(
    value: Any, index: int, account_by_id: dict[str, AccountCoverage]
) -> NormalizedTransaction:
    location = f"transactions[{index}]"
    record = _object(value, location)
    _no_truth_fields(record, location)
    transaction_id = _nonempty_string(record.get("transaction_id"), f"{location}.transaction_id")
    location = f"transactions[{index}] ({transaction_id!r})"
    account_id = _nonempty_string(record.get("account_id"), f"{location}.account_id")
    account = account_by_id.get(account_id)
    if account is None:
        raise InputValidationError(f"{location}.account_id: unknown account {account_id!r}")
    if "business_id" in record and record["business_id"] != account.business_id:
        raise InputValidationError(
            f"{location}.business_id: conflicts with account {account_id!r} owner"
        )
    transaction_date = _date(record.get("date"), f"{location}.date")
    amount = _amount(record.get("amount"), f"{location}.amount")
    name = _nonempty_string(record.get("name"), f"{location}.name")
    if record.get("iso_currency_code") != "USD":
        raise InputValidationError(f"{location}.iso_currency_code: expected explicit 'USD'")
    if record.get("unofficial_currency_code") is not None:
        raise InputValidationError(f"{location}.unofficial_currency_code: must be null or absent")
    pending = record.get("pending")
    if not isinstance(pending, bool):
        raise InputValidationError(f"{location}.pending: expected a Boolean")
    merchant_name = record.get("merchant_name")
    if merchant_name is not None:
        if not isinstance(merchant_name, str):
            raise InputValidationError(f"{location}.merchant_name: expected a string or null")
        merchant_name = merchant_name.strip() or None
    pending_transaction_id = record.get("pending_transaction_id")
    if pending_transaction_id is not None:
        pending_transaction_id = _nonempty_string(
            pending_transaction_id, f"{location}.pending_transaction_id"
        )
    category = record.get("category")
    if category is not None:
        if not isinstance(category, list) or not all(isinstance(part, str) for part in category):
            raise InputValidationError(f"{location}.category: expected an array of strings or null")
        category = tuple(category)
    personal_finance_category = record.get("personal_finance_category")
    if personal_finance_category is not None and not isinstance(personal_finance_category, dict):
        raise InputValidationError(f"{location}.personal_finance_category: expected an object or null")
    return NormalizedTransaction(
        transaction_id=transaction_id,
        business_id=account.business_id,
        account_id=account_id,
        date=transaction_date,
        amount=amount,
        name=name,
        merchant_name=merchant_name,
        category=category,
        personal_finance_category=deepcopy(personal_finance_category),
        pending=pending,
        pending_transaction_id=pending_transaction_id,
        raw=deepcopy(record),
    )


def normalize_input(payload: Any) -> NormalizedInput:
    """Validate an already decoded envelope and return posted, in-window records.

    Parsed file amounts are ``Decimal``; direct callers must pass ``int`` or
    ``Decimal`` rather than binary floats.
    """
    envelope = _object(payload, "input")
    _no_truth_fields(envelope, "input")
    as_of = _date(envelope.get("as_of"), "as_of")
    try:
        window_start = as_of - timedelta(days=WINDOW_DAYS - 1)
    except OverflowError as exc:
        raise InputValidationError("as_of: cannot form a 90-day window") from exc
    accounts = _accounts(envelope.get("accounts"))
    businesses = _business_coverage(accounts, window_start, as_of)
    account_by_id = {account.account_id: account for account in accounts}
    business_by_id = {business.business_id: business for business in businesses}
    records = envelope.get("transactions")
    if not isinstance(records, list):
        raise InputValidationError("transactions: expected an array")
    seen: set[str] = set()
    accepted: list[NormalizedTransaction] = []
    excluded: list[ExcludedTransaction] = []
    for index, record in enumerate(records):
        transaction = _transaction(record, index, account_by_id)
        if transaction.transaction_id in seen:
            raise InputValidationError(
                f"transactions[{index}].transaction_id: duplicate {transaction.transaction_id!r}"
            )
        seen.add(transaction.transaction_id)
        account = account_by_id[transaction.account_id]
        business = business_by_id[transaction.business_id]
        if not window_start <= transaction.date <= as_of:
            reason = "out_of_window"
        elif not account.start <= transaction.date <= account.end:
            raise InputValidationError(
                f"transactions[{index}] ({transaction.transaction_id!r}).date: "
                f"inside 90-day window but outside account {account.account_id!r} coverage"
            )
        elif transaction.pending:
            reason = "pending"
        elif not business.start <= transaction.date <= business.end:
            reason = "outside_common_coverage"
        else:
            accepted.append(transaction)
            continue
        excluded.append(ExcludedTransaction(transaction.transaction_id, reason, transaction.raw))
    return NormalizedInput(
        contract_version=INPUT_CONTRACT_VERSION,
        as_of=as_of,
        window_start=window_start,
        window_end=as_of,
        accounts=accounts,
        business_coverage=businesses,
        transactions=tuple(
            sorted(
                accepted,
                key=lambda transaction: (
                    transaction.business_id,
                    transaction.date,
                    transaction.account_id,
                    transaction.transaction_id,
                ),
            )
        ),
        excluded=tuple(sorted(excluded, key=lambda item: (item.reason, item.transaction_id))),
    )
