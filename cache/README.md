# Cache and spend records

Active run files:

- `batch_reviews.jsonl` — partial, validated main-cohort batch-response cache. It contains 10 of 25 batches; do not claim full no-key replay yet.
- `spend_ledger.jsonl` — append-only OpenAI budget reservations and settlements used by the main CLI.
- `new_input.jsonl` — complete cache for the separate three-transaction offline replay example.

Cache and spend-ledger files are append-only JSONL. On load, an unterminated final fragment is discarded so a later run can resume after an interrupted append; malformed or integrity-invalid complete records remain fatal errors.

`experiments/` contains prior model/prompt trials and provider ledgers, grouped by provider (`openai/`, `openrouter/`, `local/`). These are retained for audit/history and are not the selected main-run cache. The JSONL caches contain synthetic transaction evidence and model responses; never put real customer data or credentials here.
