# Ticket 01 — Transaction data contract and observation window

**Status:** Completed — input validation and normalization only; downstream pipeline remains pending.

**Type:** Foundation

**Depends on:** None

**Next:** Synthetic dataset and independent ground truth (Ticket 02)

## Goal

Define and implement the smallest reproducible input contract for **Plaid-shaped transaction data**. V1 uses Plaid's transaction format and sign convention; it does **not** need Plaid API access or Plaid Sandbox. Both generated data and a new file supplied during the debrief must pass through the same validation and normalization path.

## Scope

1. Implement the approved [single JSON envelope](../rules/BUSINESS_RULES.md): `as_of`, account metadata (`account_id`, `business_id`, inclusive coverage dates), and a `transactions` array of Plaid-shaped records. The normalized record needs a stable transaction ID, associated business/account IDs, date, signed amount, and description (`name`); `business_id` comes from the account mapping, not a required transaction field. Retain optional `merchant_name`, category and pending-to-posted linkage fields, plus the original record for traceability.
2. Use the **Plaid Transactions** sign convention: negative `amount` is money in; positive is money out. Normalize monetary values with `Decimal` or integer cents, not binary floating-point arithmetic. Define treatment of zero amounts and currency fields explicitly.
3. Define a deterministic observation window using an explicit `as_of` date: the 90 calendar dates ending on `as_of`, inclusive. Document how dates outside that window are handled. Keep a separate 61-day input case for coverage-shift testing; do not silently scale it to 90 days.
4. Carry **explicit coverage start/end metadata** for each account or business. Do not infer coverage from the earliest transaction: a day with no transaction is not proof that bank history was unavailable. Define how coverage is combined when a business has multiple accounts.
5. Implement the approved posted-only policy: pending records (linked or unlinked) are excluded with a count, posted records count once, and duplicate transaction IDs anywhere in the raw file fail independently of pending-to-posted linkage. Do not fuzzy-deduplicate by text or amount.
6. Reject malformed or unsupported input clearly (for example: missing IDs, invalid dates, non-numeric amounts, unsupported currency, or inconsistent account/business association). Errors should identify the offending record or field rather than silently guessing.
7. Accept an input file **without ground truth**. Truth labels belong in a separate file and must not be required by the input validator or passed to the reviewer.

## Deliverables

- A short, versioned input-contract section or note referencing [BUSINESS_RULES.md](../rules/BUSINESS_RULES.md) and covering the exact envelope schema, boundaries, coverage, pending/posted handling, USD/zero policy, and invalid records without duplicating policy authority.
- Validation/normalization code in `src/fundo_reviewer/data.py` (or an equally small module if implementation reveals a better boundary).
- Focused tests in `tests/` using small synthetic Plaid-shaped fixtures, including one 90-day and one 61-day coverage case.
- A minimal example of the accepted input format for a developer bringing new transactions. This can live with the tests until the CLI and README are completed in a later ticket.

## Acceptance criteria

- [x] A valid new transaction file normalizes to stable records while preserving raw fields and business/account association.
- [x] Tests prove `-100.00` is a $100 inflow and `+100.00` is a $100 outflow; money is not calculated with binary floating point.
- [x] Window tests cover both inclusive boundaries, an out-of-window record, 90-day coverage, and a separately identified 61-day history.
- [x] Coverage is read from explicit metadata, not guessed from the first transaction date; multiple-account behavior is documented and tested.
- [x] Pending/posted examples cannot be counted twice; duplicate IDs and malformed records fail with actionable errors.
- [x] Currency and zero-amount policies are documented and tested.
- [x] Validation works without truth labels, an API key, or a Plaid connection.
- [x] The challenge's required behavior is distinguished from our chosen policies in the contract and tests.

## Completion evidence

- `src/fundo_reviewer/data.py` implements the versioned `input-v1` contract, Decimal parsing, inclusive coverage intersection, posted-only filtering, validation and stable output order.
- [Input contract](../INPUT_CONTRACT.md) documents the exact JSON envelope and approved policies without presenting them as Fundo rules.
- `tests/fixtures/input_90_days.json` and `tests/fixtures/input_61_days.json` are small truth-free examples; `tests/test_data.py` covers the acceptance criteria and error paths.
- `uv run --group dev pytest -q` passed **34 tests**. This does **not** claim that the full reviewer CLI, dataset or reports exist.

## Out of scope

Do **not** connect Plaid Sandbox or its API; generate the full synthetic dataset; assign the 13 keyword groups; calculate revenue, features, or offers; call an LLM; or build reports here. Those belong to later tickets. Avoid claiming the pipeline is runnable end to end after this ticket alone.

## References

- [Original challenge](../CHALLENGE.md) — Plaid-shaped data, approximately 90 days, no real customer data, and the 61-day coverage question.
- [Implementation checklist](../IMPLEMENTATION_CHECKLIST.md) — data-contract decisions and validation evidence.
- [Architecture](../ARCHITECTURE.md) — input-module boundary and raw-versus-normalized records.
- [Financial glossary](../FINANCIAL_GLOSSARY.md) — sign convention and deposit-versus-revenue distinction.
