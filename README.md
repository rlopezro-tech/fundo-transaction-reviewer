# Fundo Transaction Reviewer

Python CLI that compares a deterministic keyword baseline with an LLM reviewer on synthetic, Plaid-shaped bank transactions. It computes illustrative credit features; it is not a lending decision service.

## Run locally

```bash
uv sync --locked --group dev
uv run --locked --group dev pytest -q
```

GitHub Actions runs the locked dependency install and test suite, then verifies that the offline sample replay matches committed outputs byte-for-byte; see [the test workflow](.github/workflows/tests.yml). The workflow needs no API key or external model calls.

`scripts/run` is the short CLI launcher: it sets `PYTHONPATH` and loads `.env` only when `--mode online` is explicit. To configure hosted calls, copy `env.example` to `.env` and set the key for the selected provider; never commit `.env`.
To switch among registered models/providers, select an ID listed by `./scripts/run --help` and set its matching key in `.env`; no source edits are needed. A completely new provider still needs a transport adapter. The model catalog is the source of supported IDs and key mapping.
Online and offline batch runs print progress and per-batch status to stderr; the final machine-readable summary remains on stdout. Logs contain row counts and status only, not transaction descriptions or credentials.

Generate the synthetic fixtures (no Plaid account or API key needed):

```bash
PYTHONPATH=src uv run --locked python -m fundo_reviewer.synthetic --output-root data
```

## Input and output locations

- `data/transactions/` — reviewer inputs; add a new Plaid-shaped file here.
- `data/ground_truth/` — evaluator-only expected labels; never send these to a provider.
- `cache/` — provider responses and spend ledgers used for exact replay.
- `reports/main/` — main review outputs; `reports/evaluation/` — quality and sensitivity analysis.

## Review another input

Put a Plaid-shaped JSON input in `data/transactions/`, then use a separate cache and output folder for that run. This makes it obvious which source was reviewed and where its results went:

```bash
./scripts/run --mode online --model gpt-6-luna --batch-size 80 \
  --input data/transactions/my_input.json \
  --cache cache/my_input_reviews.jsonl \
  --output-dir reports/my_input
```

The command uses the selected provider's key from `.env` and may incur API charges. Once every batch has a cache entry, replay the exact input without a key or provider call by changing `--mode online` to `--mode offline` and using the same `--input` and `--cache`. Do not put ground truth in the input or use real customer data for this challenge.

## Reproduce the cached example offline

This replays the committed three-transaction example without an API key or provider call, and writes fresh output under `/tmp`:

```bash
./scripts/run --mode offline \
  --input tests/fixtures/input_90_days.json \
  --cache cache/new_input.jsonl \
  --output-dir /tmp/fundo-offline-replay
```

The command should report 3 cache hits and 0 API calls. The regenerated `review_outcomes.json`, `credit_report.json`, and `run_manifest.json` match the committed artifacts in `reports/new_input/` byte for byte. The main 2,000-row run is different: its cache is partial, so a full offline replay intentionally fails on missing batches.

The committed main report has 2,000 rows, but its LLM cache is partial. It contains 10 cached batches covering 800 rows: **799 usable model decisions and one invalid response**. The other **1,201 rows retain legacy labels**: one because its cached response was invalid and 1,200 after provider failures. In the manifest, `cache_hits: 800` counts rows read from cached batches, while `degraded_count: 1201` counts all outcomes that fell back to legacy labels. Therefore the full 2,000-row offline replay is not currently possible; offline mode intentionally errors on missing cache entries.

To continue online when API quota is available, add `OPENAI_API_KEY=...` to a local `.env` (gitignored), then run:

```bash
./scripts/run --mode online --model gpt-6-luna --batch-size 80 --input data/transactions/main_90_days.json --output-dir reports/main
```

This resumes from validated cached batches and can incur API charges. Successful main-run responses have an estimated usage-derived cost of **$0.0269049**; this is not a billing receipt. The two configured OpenAI organizations most recently returned 100k TPM limit errors. See [the final results](SOLUTION.md) before retrying.

To regenerate the existing full result artifacts from the available outcome snapshot and synthetic truth (no API call):

```bash
PYTHONPATH=src uv run --locked python -m fundo_reviewer.evaluation --review-dir reports/main --output-dir reports/evaluation
```

The quality report separates valid model-reviewed rows from degraded legacy fallbacks (including per-business coverage); whole-cohort credit-feature results still include the fallback labels. Read the scope caveat in [SOLUTION.md](SOLUTION.md). The `reports/evaluation/sensitivity_report.json` is a separate simulation, not model accuracy.

## Project files

- [`data/`](data/README.md) — input transactions and isolated evaluation truth.
- [`cache/`](cache/README.md) — active response cache, spend ledger, and archived experiments.
- [`reports/`](reports/README.md) — selected outputs and clearly separated experiments.
- [`SOLUTION.md`](SOLUTION.md) — measured results, limitations, challenge answers, production plan, and tools used.
- [`docs/CHALLENGE.md`](docs/CHALLENGE.md) — challenge brief and final completion status.
- [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md) — requirement-by-requirement status and remaining gates.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — implemented data flow and safety boundaries.
- [`docs/reference/`](docs/reference/README.md) — concise input, policy, evaluation, and execution references.
