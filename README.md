# Fundo Transaction Reviewer

> Tickets 01–03 (input, synthetic fixtures, legacy labels/revenue) are implemented; the reviewer has not been implemented yet.

## Source of truth

- [CHALLENGE.md](docs/CHALLENGE.md) — original Fundo challenge.
- [BUSINESS_RULES.md](docs/rules/BUSINESS_RULES.md) — approved v1 financial and labeling decisions; implementation pending.
- [DEVELOPMENT_RULES.md](docs/rules/DEVELOPMENT_RULES.md) — approved v1 scope, safety, testing, and delivery decisions; implementation pending.
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — high-level design.
- [IMPLEMENTATION_CHECKLIST.md](docs/IMPLEMENTATION_CHECKLIST.md) — v1 implementation and evidence checklist.
- [FINANCIAL_GLOSSARY.md](docs/FINANCIAL_GLOSSARY.md) — plain-English financial glossary for developers.
- [INPUT_CONTRACT.md](docs/INPUT_CONTRACT.md) — implemented Ticket 01 envelope and validation policy.
- [SYNTHETIC_DATA.md](docs/SYNTHETIC_DATA.md) — Ticket 02 scenario inventory, counts, regeneration, and fixture hashes.
- [LEGACY_POLICY.md](docs/LEGACY_POLICY.md) — Ticket 03 keyword baseline, precedence, revenue eligibility, and known errors.

## Setup and run

The project uses Python 3.12 and `uv`. Dependencies are declared in
`pyproject.toml` and pinned in `uv.lock`. The CLI has **not** been implemented,
so there is no runnable reviewer command yet. After implementation, this section
will contain the single copy-paste run command and the environment variable
needed for new LLM calls.

Ticket 01 data-contract tests can already be run with
`uv run --group dev pytest tests/test_data.py`. They require no API key.

Regenerate the entirely synthetic Ticket 02 fixtures and verify their exact bytes:

```bash
PYTHONPATH=src uv run python -m fundo_reviewer.synthetic --output-root data
uv run --group dev pytest -q
git diff --exit-code -- data/transactions data/ground_truth
```

This produces separate 90-day transaction/truth files (10 businesses, 2,000
transactions) and 61-day files (1 business, 120 transactions) under `data/`.
No Plaid API, Sandbox credentials, or LLM key is used. The future reviewer must
read only `data/transactions/`, never `data/ground_truth/`.

The Ticket 03 baseline labels every accepted record without an API key. Its
group/status/revenue rules and deliberate failure cases are in
[`docs/LEGACY_POLICY.md`](docs/LEGACY_POLICY.md); run
`uv run --group dev pytest tests/test_legacy.py` to verify them. A CLI and
saved pipeline reports are still later tickets.

## Reproduce from cache

To be documented after implementation: one command that regenerates all results
from the committed cache without an API key.

## Outputs

To be documented after implementation: generated files and how to inspect flags, metrics, and offer impact.
