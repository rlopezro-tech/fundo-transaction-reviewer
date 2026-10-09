"""Ticket 01 contract tests; these fixtures contain no ground-truth labels."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from fundo_reviewer.data import InputValidationError, load_input, normalize_input


FIXTURES = Path(__file__).parent / "fixtures"


def envelope(name: str = "input_90_days.json") -> dict:
    return json.loads((FIXTURES / name).read_text(), parse_float=Decimal)


def test_valid_90_day_file_preserves_raw_fields_and_signs() -> None:
    result = load_input(FIXTURES / "input_90_days.json")
    assert result.contract_version == "input-v1"
    assert result.window_start == date(2026, 7, 11)
    assert result.window_end == date(2026, 10, 8)
    assert result.business_coverage[0].days == 90
    assert result.business_coverage[0].is_complete_90_days
    assert [tx.transaction_id for tx in result.transactions] == [
        "tx_start",
        "tx_end",
        "tx_posted",
    ]
    inflow = result.transactions[0]
    assert inflow.business_id == "biz_001"
    assert inflow.amount == Decimal("-100.00")
    assert inflow.is_inflow and not inflow.is_outflow
    assert inflow.magnitude == Decimal("100.00")
    assert inflow.merchant_name == "Example Customer"
    assert inflow.category == ("Transfer", "Credit")
    assert inflow.personal_finance_category == {
        "primary": "INCOME",
        "detailed": "INCOME_OTHER_INCOME",
    }
    assert inflow.raw["category"] == ["Transfer", "Credit"]
    outflow = result.transactions[1]
    assert outflow.amount == Decimal("100.00")
    assert outflow.is_outflow and not outflow.is_inflow
    assert outflow.magnitude == Decimal("100.00")
    assert result.transactions[2].pending_transaction_id == "tx_pending"
    assert result.transactions[2].amount == Decimal("10.25")  # Not the pending $10.00.
    assert result.exclusion_counts == {"out_of_window": 1, "pending": 1}
    assert {item.transaction_id: item.raw["name"] for item in result.excluded} == {
        "tx_old": "OLDER DEPOSIT",
        "tx_pending": "CARD PURCHASE PENDING",
    }


def test_file_parser_uses_decimal_not_binary_float(tmp_path: Path) -> None:
    source = (FIXTURES / "input_90_days.json").read_text()
    path = tmp_path / "input.json"
    path.write_text(source.replace('"amount": -100.00', '"amount": -0.10'))
    result = load_input(path)
    assert result.transactions[0].amount == Decimal("-0.10")
    assert isinstance(result.transactions[0].raw["amount"], Decimal)


def test_61_day_history_is_separate_and_not_scaled_to_90() -> None:
    result = load_input(FIXTURES / "input_61_days.json")
    coverage = result.business_coverage[0]
    assert result.window_start == date(2026, 7, 11)
    assert coverage.start == date(2026, 8, 9)
    assert coverage.end == date(2026, 10, 8)
    assert coverage.days == 61
    assert not coverage.is_complete_90_days
    assert len(result.transactions) == 2


def test_multi_account_intersection_uses_declared_coverage_not_first_activity() -> None:
    data = envelope()
    data["accounts"].append(
        {
            "account_id": "acct_002",
            "business_id": "biz_001",
            "coverage_start": "2026-08-09",
            "coverage_end": "2026-10-08",
        }
    )
    data["transactions"].append(
        {
            "transaction_id": "tx_second_account",
            "account_id": "acct_002",
            "date": "2026-09-01",
            "amount": Decimal("-25.00"),
            "name": "CUSTOMER",
            "pending": False,
            "iso_currency_code": "USD",
        }
    )
    result = normalize_input(data)
    coverage = result.business_coverage[0]
    assert coverage.account_ids == ("acct_001", "acct_002")
    assert coverage.start == date(2026, 8, 9)
    assert coverage.days == 61  # First transaction on acct_002 is September 1.
    assert not coverage.is_complete_90_days
    assert "tx_start" not in {tx.transaction_id for tx in result.transactions}
    assert result.exclusion_counts == {
        "out_of_window": 1,
        "outside_common_coverage": 1,
        "pending": 1,
    }


def test_no_common_account_coverage_is_rejected() -> None:
    data = envelope()
    data["accounts"].append(
        {
            "account_id": "acct_002",
            "business_id": "biz_001",
            "coverage_start": "2026-06-01",
            "coverage_end": "2026-06-30",
        }
    )
    with pytest.raises(InputValidationError, match="no common coverage"):
        normalize_input(data)


def test_in_window_transaction_outside_own_account_coverage_is_invalid() -> None:
    data = envelope()
    data["accounts"][0]["coverage_start"] = "2026-08-09"
    with pytest.raises(InputValidationError, match="tx_start.*outside account.*coverage"):
        normalize_input(data)


def test_both_window_boundaries_included_and_after_window_excluded() -> None:
    data = envelope()
    future = deepcopy(data["transactions"][0])
    future.update(transaction_id="tx_future", date="2026-10-09")
    data["transactions"].append(future)
    result = normalize_input(data)
    accepted_ids = {tx.transaction_id for tx in result.transactions}
    assert {"tx_start", "tx_end"} <= accepted_ids
    assert "tx_old" not in accepted_ids
    assert "tx_future" not in accepted_ids
    assert result.exclusion_counts["out_of_window"] == 2


def test_posted_only_even_if_pending_is_unlinked_or_text_is_similar() -> None:
    data = envelope()
    pending = deepcopy(data["transactions"][2])
    pending.update(transaction_id="tx_unlinked_pending", pending=True)
    pending.pop("pending_transaction_id")
    data["transactions"].append(pending)
    result = normalize_input(data)
    assert {tx.transaction_id for tx in result.transactions} == {
        "tx_start",
        "tx_posted",
        "tx_end",
    }
    assert result.exclusion_counts["pending"] == 2


def test_duplicate_id_is_rejected_even_when_one_record_is_pending() -> None:
    data = envelope()
    data["transactions"][1]["transaction_id"] = "tx_start"
    with pytest.raises(InputValidationError, match=r"transactions\[1\].*duplicate 'tx_start'"):
        normalize_input(data)


def test_duplicate_id_is_rejected_even_if_record_is_out_of_window() -> None:
    data = envelope()
    data["transactions"][-1]["transaction_id"] = "tx_start"
    with pytest.raises(InputValidationError, match="duplicate 'tx_start'"):
        normalize_input(data)


def test_input_order_does_not_change_normalized_order() -> None:
    data = envelope()
    original = normalize_input(data)
    data["transactions"].reverse()
    data["accounts"].reverse()
    reordered = normalize_input(data)
    assert original.transactions == reordered.transactions
    assert original.excluded == reordered.excluded
    assert original.business_coverage == reordered.business_coverage


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("transaction_id", "", "transaction_id"),
        ("account_id", "unknown", "unknown account"),
        ("date", "2026-02-30", "invalid calendar date"),
        ("date", "20261008", "YYYY-MM-DD"),
        ("amount", "100.00", "amount"),
        ("amount", 100.0, "amount"),
        ("amount", True, "amount"),
        ("amount", Decimal("1.234"), "at most two decimals"),
        ("amount", Decimal("0.00"), "zero amount"),
        ("iso_currency_code", "MXN", "iso_currency_code"),
        ("iso_currency_code", None, "iso_currency_code"),
        ("unofficial_currency_code", "USD", "unofficial_currency_code"),
        ("pending", "false", "pending"),
        ("merchant_name", 1, "merchant_name"),
        ("category", "Transfer", "category"),
        ("personal_finance_category", "INCOME", "personal_finance_category"),
        ("business_id", "other_business", "conflicts"),
    ],
)
def test_malformed_transaction_has_actionable_field_error(field: str, value: object, message: str) -> None:
    data = envelope()
    data["transactions"][0][field] = value
    with pytest.raises(InputValidationError, match=message):
        normalize_input(data)


def test_missing_amount_fails_with_transaction_context() -> None:
    data = envelope()
    del data["transactions"][0]["amount"]
    with pytest.raises(InputValidationError, match="tx_start.*amount"):
        normalize_input(data)


def test_account_ownership_and_coverage_errors() -> None:
    data = envelope()
    data["accounts"][0]["coverage_start"] = "2026-10-09"
    with pytest.raises(InputValidationError, match="coverage_start is after coverage_end"):
        normalize_input(data)
    data = envelope()
    data["accounts"].append(deepcopy(data["accounts"][0]))
    with pytest.raises(InputValidationError, match="duplicate 'acct_001'"):
        normalize_input(data)


def test_truth_is_not_required_and_truth_fields_are_rejected() -> None:
    data = envelope()
    assert normalize_input(data).transactions
    data["transactions"][0]["scenario_id"] = "secret_truth"
    with pytest.raises(InputValidationError, match="truth-only field"):
        normalize_input(data)
    data = envelope()
    data["ground_truth"] = {"tx_start": "revenue"}
    with pytest.raises(InputValidationError, match="truth-only field"):
        normalize_input(data)


def test_loader_needs_no_api_key_or_plaid_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = load_input(FIXTURES / "input_90_days.json")
    assert len(result.transactions) == 3


def test_bad_json_and_duplicate_json_keys_fail_clearly(tmp_path: Path) -> None:
    path = tmp_path / "input.json"
    path.write_text('{"as_of": "2026-10-08", "as_of": "2026-10-07"}')
    with pytest.raises(InputValidationError, match="duplicate JSON key 'as_of'"):
        load_input(path)
    path.write_text("{")
    with pytest.raises(InputValidationError, match="invalid JSON.*line 1"):
        load_input(path)
    path.write_text('{"as_of": NaN}')
    with pytest.raises(InputValidationError, match="invalid JSON numeric constant 'NaN'"):
        load_input(path)
    path.write_bytes(b"\xff")
    with pytest.raises(InputValidationError, match="cannot read input"):
        load_input(path)


def test_missing_file_and_window_underflow_fail_clearly(tmp_path: Path) -> None:
    with pytest.raises(InputValidationError, match="cannot read input"):
        load_input(tmp_path / "missing.json")
    data = envelope()
    data["as_of"] = "0001-01-01"
    with pytest.raises(InputValidationError, match="cannot form a 90-day window"):
        normalize_input(data)
