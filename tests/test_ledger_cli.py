import json
import sys
from pathlib import Path

import pytest

from fundo_reviewer.cache import BudgetExceeded, SpendLedger
from fundo_reviewer.data import load_input
from fundo_reviewer.ledger_cli import main
from fundo_reviewer.legacy import label_transactions
from fundo_reviewer.reviewer import build_request

ROOT = Path(__file__).resolve().parents[1]


def _ledger_with_reservation(path: Path):
    normalized = load_input(ROOT / "tests/fixtures/input_90_days.json")
    labels = {label.transaction_id: label for label in label_transactions(normalized.transactions)}
    transaction = normalized.transactions[0]
    request = build_request(transaction, labels[transaction.transaction_id])
    ledger = SpendLedger(path)
    reservation = ledger.reserve(request, "gpt-6-luna")
    return ledger, reservation


def test_status_lists_only_outstanding_reservation_metadata(tmp_path, monkeypatch, capsys):
    path = tmp_path / "spend.jsonl"
    _, reservation = _ledger_with_reservation(path)
    monkeypatch.setattr(sys, "argv", ["ledger", "--ledger", str(path), "status"])

    main()

    result = json.loads(capsys.readouterr().out)
    assert result["outstanding_reservations"] == [
        {
            "call_id": reservation.call_id,
            "reserved_usd": str(reservation.reserved_usd),
            "model": "gpt-6-luna",
            "at_utc": result["outstanding_reservations"][0]["at_utc"],
        }
    ]
    assert result["committed_usd"] == str(reservation.reserved_usd)


def test_reconcile_settles_only_within_reservation_and_is_auditable(tmp_path, monkeypatch, capsys):
    path = tmp_path / "spend.jsonl"
    ledger, reservation = _ledger_with_reservation(path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ledger",
            "--ledger",
            str(path),
            "reconcile",
            "--call-id",
            reservation.call_id,
            "--input-tokens",
            "100",
            "--output-tokens",
            "25",
        ],
    )

    main()

    result = json.loads(capsys.readouterr().out)
    assert result["call_id"] == reservation.call_id
    assert result["warning"].startswith("estimate from provider-reported tokens")
    assert ledger.outstanding_reservations() == []
    assert ledger.settled_usd > 0
    assert len(ledger.events) == 2
    assert ledger.events[-1]["usage"] == {"input_tokens": 100, "output_tokens": 25}


def test_reconcile_refuses_usage_above_reserved_amount(tmp_path):
    ledger, reservation = _ledger_with_reservation(tmp_path / "spend.jsonl")

    with pytest.raises(BudgetExceeded, match="exceeds reserved cost"):
        ledger.reconcile(
            reservation.call_id,
            {"input_tokens": 10**12, "output_tokens": 10**12},
        )

    assert len(ledger.events) == 1
    assert len(ledger.outstanding_reservations()) == 1


def test_reconcile_rejects_non_outstanding_call_id(tmp_path):
    ledger, _ = _ledger_with_reservation(tmp_path / "spend.jsonl")

    with pytest.raises(ValueError, match="not an outstanding"):
        ledger.reconcile("unknown-call", {"input_tokens": 10, "output_tokens": 5})


@pytest.mark.parametrize(
    "usage",
    [
        {},
        {"input_tokens": 1},
        {"input_tokens": -1, "output_tokens": 2},
        {"input_tokens": True, "output_tokens": 2},
        {"input_tokens": 1, "output_tokens": 2, "cached_tokens": 1},
    ],
)
def test_reconcile_requires_exact_nonnegative_integer_token_counts(tmp_path, usage):
    ledger, reservation = _ledger_with_reservation(tmp_path / "spend.jsonl")

    with pytest.raises(ValueError, match="provider-reported input/output tokens"):
        ledger.reconcile(reservation.call_id, usage)

    assert len(ledger.events) == 1
    assert len(ledger.outstanding_reservations()) == 1
