"""Inspect and reconcile conservative spend-ledger reservations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fundo_reviewer.cache import SpendLedger


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect outstanding provider spend reservations or reconcile verified usage"
    )
    parser.add_argument("--ledger", type=Path, default=Path("cache/spend_ledger.jsonl"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="list outstanding reservations without prompts or secrets")
    reconcile = commands.add_parser(
        "reconcile", help="settle a reservation with provider-confirmed token counts"
    )
    reconcile.add_argument("--call-id", required=True)
    reconcile.add_argument("--input-tokens", required=True, type=int)
    reconcile.add_argument("--output-tokens", required=True, type=int)
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        ledger = SpendLedger(args.ledger)
        if args.command == "status":
            print(
                json.dumps(
                    {
                        "ledger": str(args.ledger),
                        "settled_usd": str(ledger.settled_usd),
                        "committed_usd": str(ledger.committed_usd),
                        "outstanding_reservations": ledger.outstanding_reservations(),
                    },
                    sort_keys=True,
                )
            )
            return

        cost = ledger.reconcile(
            args.call_id,
            {"input_tokens": args.input_tokens, "output_tokens": args.output_tokens},
        )
        print(
            json.dumps(
                {
                    "call_id": args.call_id,
                    "usage_derived_cost_usd": str(cost),
                    "settled_usd": str(ledger.settled_usd),
                    "warning": "estimate from provider-reported tokens, not a billing receipt",
                },
                sort_keys=True,
            )
        )
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"ledger: error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
