# Fundo Transaction Reviewer

> Tickets 01–04 are implemented. Ticket 05's provider/cache/CLI and Ticket 06's credit/offer calculation are implemented, but the full paid cache and no-key 2,000-record replay are **pending**. Tickets 07–08 and final validation remain in progress.

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
- [REVIEWER_BOUNDARY.md](docs/REVIEWER_BOUNDARY.md) — Ticket 04 prompt/schema, model-versus-code boundary, injection and failure policy.
- [EXECUTION.md](docs/EXECUTION.md) — Ticket 05 model, pilot, cache, budget and execution assumptions.
- [CREDIT_POLICY.md](docs/CREDIT_POLICY.md) — Ticket 06 feature denominators, coverage, and illustrative offer policy.

## Setup and run

The project uses Python 3.12 and `uv`. Dependencies are declared in
`pyproject.toml` and pinned in `uv.lock`. Install with `uv sync --group dev`.
For online cache filling, set `OPENAI_API_KEY` in your environment; never commit
it. The implementation-stage pipeline command is:

```bash
PYTHONPATH=src uv run python -m fundo_reviewer.cli --mode online --input data/transactions/main_90_days.json --output-dir reports/main
```

This command will call the paid model for uncached batches and is **not yet a
completed demonstration**. It may stop at the account's daily request limit;
rerunning resumes from validated cached batches. A conservative pre-call spend
guard stops before the USD 8 operating ceiling. See [EXECUTION.md](docs/EXECUTION.md)
for the measured pilot, pricing assumptions and current limitations.

Fast local tests run with `uv run --group dev pytest -q`; they require no API key.

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
[`docs/LEGACY_POLICY.md`](docs/LEGACY_POLICY.md).

## Reproduce from cache

Once the final cache is committed, reproduce labels with no API key or provider call:

```bash
env -u OPENAI_API_KEY PYTHONPATH=src uv run python -m fundo_reviewer.cli --mode offline --input data/transactions/main_90_days.json --output-dir reports/main
```

**This main-cohort replay does not pass yet** because the full cache has not
been filled. Offline mode deliberately fails on missing or corrupt entries;
it never silently treats a missing response as a model `keep`. A new
Plaid-shaped input without truth uses the same `--input` option, but requires
online mode unless its exact requests were already cached.

## Outputs

The CLI emits ordered `review_outcomes.json`, `credit_report.json`, and `run_manifest.json` in
`--output-dir`. The manifest separates new API usage from historical cache
usage and labels the cost as usage-derived estimate, not a billing receipt.
The credit report shows legacy and reviewed features/illustrative offers with
their deltas; it does not represent a real Fundo funding decision.
