# Fundo Transaction Reviewer

> Tickets 01–04 are implemented. Tickets 05–07 have provider/cache/CLI, credit/offer, and evaluation/sensitivity code, but the full paid cache, measured quality report, and no-key 2,000-record replay are **pending**. On 2026-10-09, `gpt-6-luna` completed and cached 10 of 25 main-cohort batches (800/2,000 rows; 799 valid, 1 invalid) before hitting the organization's 100k TPM limit. The run can resume from cache after the quota resets; final reports and evaluation are still pending. Ticket 08 and final validation remain in progress.

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
- [EVALUATION.md](docs/EVALUATION.md) — Ticket 07 strict synthetic-truth join and seeded sensitivity method.
- [COMPLETION_MATRIX.md](docs/COMPLETION_MATRIX.md) — direct evidence and remaining final gates.

## Setup and run

The project uses Python 3.12 and `uv`. Dependencies are declared in
`pyproject.toml` and pinned in `uv.lock`. Install with `uv sync --group dev`.
For the OpenAI path, put `OPENAI_API_KEY=...` in a local, gitignored `.env`
file, or export it in your shell; never commit it. `uv run --env-file .env`
loads that file for one command. The selected `gpt-6-luna` is the least-cost
model in OpenAI's current flagship family at the published standard short-context
prices; it was already the code default, so no model change or cache invalidation
is needed. The implementation-stage pipeline command is:

```bash
PYTHONPATH=src uv run --env-file .env python -m fundo_reviewer.cli --mode online --model gpt-6-luna --input data/transactions/main_90_days.json --output-dir reports/main
```

This command calls the paid model for uncached batches and is **not yet a
completed demonstration**. It may stop at an account rate limit; rerunning
resumes from validated cached batches. On 2026-10-09 it cached 10 batches
(800/2,000 rows) before a 100k TPM limit stopped the run. The cache is partial;
the final report is not yet available. A conservative pre-call spend guard stops
before the USD 8 operating ceiling.
See [EXECUTION.md](docs/EXECUTION.md) for the alternative-provider experiment,
measured pilot, pricing assumptions and current limitations. If you export the
key instead, omit `--env-file .env`.

## OpenRouter experiment (incomplete)

An OpenRouter-compatible adapter is available with `OPENROUTER_API_KEY` in the
ignored `.env` file. The least-cost paid model tested was `openai/gpt-oss-20b`;
its reported price is USD 0.02/M input and USD 0.10/M output. The attempt to
review the 2,000-row cohort was stopped: only 160 rows (8%) had valid responses,
while many large-batch responses were invalid or incomplete. No full report was
generated. The experimental caches are kept separate from the OpenAI main
cache; do not resume them until the provider output is fixed and a clean pilot
passes. Details and exact progress are in [EXECUTION.md](docs/EXECUTION.md).

Fast local tests run with `uv run --group dev pytest -q`; they require no API key.

## Local-model diagnostic pilot

The repository also includes a **20-transaction local-only diagnostic** using
Ollama and Qwen3.5 9B Q4. It does not use `OPENAI_API_KEY` or incur OpenAI API
charges. Install/start Ollama and pull the model once, then run:

```bash
ollama serve
ollama pull qwen3.5:9b-q4_K_M
PYTHONPATH=src uv run python -m fundo_reviewer.local_pilot
```

The pilot response cache and truth-based diagnostic are in
`cache/local_qwen35_9b_pilot.jsonl` and `reports/local_qwen35_9b_pilot.json`.
On the fixed development sample, this local model matched legacy at 12/20,
produced no flags, and had one invalid response; this is **not** evidence of
improvement and is not the 2,000-transaction main run. The selected main model
remains `gpt-6-luna` unless a separately evaluated alternative is explicitly
chosen.

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

For a **small truth-free input** using the same documented envelope, use the
included sample as a shape example, or replace its path with a new file. The
new file needs online mode until its exact responses have been cached:

```bash
PYTHONPATH=src uv run --env-file .env python -m fundo_reviewer.cli --mode online --model gpt-6-luna --input tests/fixtures/input_90_days.json --output-dir reports/new_input --cache cache/new_input.jsonl
```

This path emits flags, features and illustrative offers, **not measured
accuracy**. It does not require Plaid API or Sandbox credentials. An uncached
offline run must fail explicitly. Keep real customer files and keys out of Git.

Run the separate synthetic sensitivity/evaluation command from
[`docs/EVALUATION.md`](docs/EVALUATION.md). The committed sensitivity artifact
is a **simulation**, not measured reviewer quality; the latter waits for the
full reviewed cohort.

Once `reports/main` contains a complete reviewed run, generate the separate
synthetic-truth quality report and deterministic sensitivity results:

```bash
PYTHONPATH=src uv run python -m fundo_reviewer.evaluation --review-dir reports/main --output-dir reports/evaluation
```

The truth file is opened only by this evaluation command, never by the
reviewer. See [`SOLUTION.md`](SOLUTION.md) for the engineering interpretation,
limitations, production plan and tool disclosure.
