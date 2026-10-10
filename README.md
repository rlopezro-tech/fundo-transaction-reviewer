# Fundo Transaction Reviewer

Python CLI that compares a deterministic keyword baseline with an LLM reviewer on synthetic, Plaid-shaped bank transactions. It computes illustrative credit features; it is not a lending decision service.

## Run locally

```bash
uv sync --group dev
uv run --group dev pytest -q
```

GitHub Actions runs the locked dependency install and test suite, then verifies that the offline sample replay matches committed outputs byte-for-byte; see [the test workflow](.github/workflows/tests.yml). The workflow needs no API key or external model calls.

`scripts/run` is the short CLI launcher: it sets `PYTHONPATH` and loads `.env` only when `--mode online` is explicit. To configure hosted calls, copy `env.example` to `.env` and set the key for the selected provider; never commit `.env`.

Generate the synthetic fixtures (no Plaid account or API key needed):

```bash
PYTHONPATH=src uv run python -m fundo_reviewer.synthetic --output-root data
```

## Input and output locations

- `data/transactions/` — reviewer inputs; add a new Plaid-shaped file here.
- `data/ground_truth/` — evaluator-only expected labels; never send these to a provider.
- `cache/` — provider responses and spend ledgers used for exact replay.
- `reports/main/` — main review outputs; `reports/evaluation/` — quality and sensitivity analysis.

## Reproduce the cached example offline

This replays the committed three-transaction example without an API key or provider call, and writes fresh output under `/tmp`:

```bash
./scripts/run --mode offline \
  --input tests/fixtures/input_90_days.json \
  --cache cache/new_input.jsonl \
  --output-dir /tmp/fundo-offline-replay
```

The command should report 3 cache hits and 0 API calls. The regenerated `review_outcomes.json`, `credit_report.json`, and `run_manifest.json` match the committed artifacts in `reports/new_input/` byte for byte. The main 2,000-row run is different: its cache is partial, so a full offline replay intentionally fails on missing batches.

The committed main report has 2,000 rows, but its LLM cache is partial. The model returned usable decisions for **799 rows**, returned one invalid response, and the remaining **1,200 rows fell back to legacy labels** after provider rate limits. Therefore the full 2,000-row offline replay is not currently possible; offline mode intentionally errors on missing cache entries.

To continue online when API quota is available, add `OPENAI_API_KEY=...` to a local `.env` (gitignored), then run:

```bash
./scripts/run --mode online --model gpt-6-luna --batch-size 80 --input data/transactions/main_90_days.json --output-dir reports/main
```

This resumes from validated cached batches and can incur API charges. Successful main-run responses have an estimated usage-derived cost of **$0.0269049**; this is not a billing receipt. The two configured OpenAI organizations most recently returned 100k TPM limit errors. See [the final results](SOLUTION.md) before retrying.

To regenerate the existing full result artifacts from the available outcome snapshot and synthetic truth (no API call):

```bash
PYTHONPATH=src uv run python -m fundo_reviewer.evaluation --review-dir reports/main --output-dir reports/evaluation
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
