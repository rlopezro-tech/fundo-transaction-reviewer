# Cache and spend records

Active run files:

- `batch_reviews.jsonl` — partial, validated main-cohort batch-response cache. It contains 10 of 25 batches; do not claim full no-key replay yet.
- `spend_ledger.jsonl` — append-only OpenAI budget reservations and settlements used by the main CLI.

The response caches and spend ledger serialize JSONL read/repair/append operations with sidecar advisory locks, preventing a reader from truncating an active write or concurrent writers from adding duplicate keys. Online cache misses also take a per-identity lock through provider response validation and persistence, then recheck the cache after waiting; concurrent local runs therefore reuse one paid provider call for the same request/batch. The spend ledger reloads current events before enforcing its budget ceiling and rejects duplicate settlements. Hidden lock files are runtime state and are gitignored. Locks are local only; do not share these files across hosts or network filesystems as a distributed lock service.
- `new_input.jsonl` — complete cache for the separate three-transaction offline replay example.

Inspect outstanding reservations without showing prompts or transaction data:

```bash
./scripts/ledger status
```

If a provider response succeeded but its usage could not be written to the ledger, reconcile only with token counts confirmed by that provider (for example, from its usage dashboard):

```bash
./scripts/ledger reconcile --call-id '<call-id-from-status>' \
  --input-tokens 1234 --output-tokens 567
```

The command appends a normal settlement event and reports an estimate, not a billing receipt. It rejects non-outstanding call IDs and usage above the original reservation. Do not guess token counts or manually edit the JSONL file; if usage cannot be confirmed, leave the reservation as a conservative budget hold.

Cache and spend-ledger files are append-only JSONL. On load, an unterminated final fragment is discarded so a later run can resume after an interrupted append; malformed or integrity-invalid complete records remain fatal errors.

`experiments/` contains prior model/prompt trials and provider ledgers, grouped by provider (`openai/`, `openrouter/`, `local/`). These are retained for audit/history and are not the selected main-run cache. The JSONL caches contain synthetic transaction evidence and model responses; never put real customer data or credentials here.
