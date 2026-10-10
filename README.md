# Fundo Transaction Reviewer

Python CLI that compares a deterministic keyword baseline with an LLM reviewer on synthetic, Plaid-shaped bank transactions. It computes illustrative credit features; it is not a lending decision service.

## Run locally

```bash
uv sync --group dev
uv run --group dev pytest -q
```

Generate the synthetic fixtures (no Plaid account or API key needed):

```bash
PYTHONPATH=src uv run python -m fundo_reviewer.synthetic --output-root data
```

The committed main report has 2,000 rows, but its LLM cache is partial. The model returned usable decisions for **799 rows**, returned one invalid response, and the remaining **1,200 rows fell back to legacy labels** after provider rate limits. Therefore the full 2,000-row offline replay is not currently possible; offline mode intentionally errors on missing cache entries.

To continue online when API quota is available, add `OPENAI_API_KEY=...` to a local `.env` (gitignored), then run:

```bash
PYTHONPATH=src uv run --env-file .env python -m fundo_reviewer.cli --mode online --model gpt-6-luna --batch-size 80 --input data/transactions/main_90_days.json --output-dir reports/main
```

This resumes from validated cached batches and can incur API charges. Successful main-run responses have an estimated usage-derived cost of **$0.0269049**; this is not a billing receipt. The two configured OpenAI organizations most recently returned 100k TPM limit errors. See [the final results](SOLUTION.md) before retrying.

To regenerate the existing full result artifacts from the available outcome snapshot and synthetic truth (no API call):

```bash
PYTHONPATH=src uv run python -m fundo_reviewer.evaluation --review-dir reports/main --output-dir reports/evaluation
```

The evaluator includes provider-failure fallbacks in full-cohort denominators, so read the scope caveat in [SOLUTION.md](SOLUTION.md). The `reports/evaluation/sensitivity_report.json` is a separate simulation, not model accuracy.

## Project files

- [`SOLUTION.md`](SOLUTION.md) — measured results, limitations, challenge answers, production plan, and tools used.
- [`docs/CHALLENGE.md`](docs/CHALLENGE.md) — challenge brief and final completion status.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — implemented data flow and safety boundaries.
- [`docs/reference/`](docs/reference/README.md) — concise implementation references; `docs/archive/` retains planning history.
