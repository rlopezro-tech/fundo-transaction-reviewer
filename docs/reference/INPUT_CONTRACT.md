# Input contract v1 — Ticket 01

> **Status:** implemented input boundary, not an end-to-end reviewer. Fundo requires Plaid-shaped transaction data; the single-envelope format and validation policies are our approved choices in [Business rules](../archive/rules/BUSINESS_RULES.md). No Plaid API, Sandbox, ground truth, or API key is needed here.

## File shape

One UTF-8 JSON object requires these top-level keys:

```json
{
  "as_of": "2026-10-08",
  "accounts": [
    {
      "account_id": "acct_demo",
      "business_id": "biz_demo",
      "coverage_start": "2026-07-11",
      "coverage_end": "2026-10-08"
    }
  ],
  "transactions": [
    {
      "transaction_id": "tx_demo",
      "account_id": "acct_demo",
      "date": "2026-10-08",
      "amount": -100.00,
      "name": "ACH CREDIT CUSTOMER",
      "merchant_name": "Example Customer",
      "pending": false,
      "iso_currency_code": "USD"
    }
  ]
}
```

`as_of` and all dates use `YYYY-MM-DD`. The `accounts` array is nonempty; account IDs are unique, each account maps to one business, and inclusive coverage start must not exceed end. Transactions need a unique ID, known account, date, numeric nonzero amount, nonempty `name`, Boolean `pending`, and explicit `iso_currency_code: "USD"`. `business_id` comes from account metadata; if repeated on a transaction, it must agree. Optional `merchant_name`, `pending_transaction_id`, `category`, and `personal_finance_category` are retained alongside the original raw record. `unofficial_currency_code` must be absent or null. Truth-only fields must live in a separate file, never in this envelope.

## Validation and filtering

- **Required Plaid sign:** negative amount is money **in**, positive amount is money **out**. JSON numeric tokens are parsed directly as `Decimal`; strings, binary `float` objects passed to the normalizer, zero, non-finite values, more than two decimal places, or non-USD currencies are rejected—not rounded or converted.
- **V1 window:** the 90 inclusive dates from `as_of - 89 days` through `as_of`. A business with multiple accounts uses their **common declared coverage** intersected with this window. Quiet days within coverage still count. An empty common interval is invalid; a transaction dated within the 90-day window but outside its own account coverage is invalid. A 61-day result remains 61 days, with `is_complete_90_days == false`.
- **V1 posting:** only `pending: false` records are returned for later labeling and arithmetic. Pending records, linked or not, are excluded; a linked posted record counts once. Duplicate IDs anywhere in the raw file are rejected independently of pending linkage; there is no fuzzy text/amount deduplication.
- All records are validated before filtering. Exclusion reasons are `out_of_window`, `pending`, or `outside_common_coverage`, in that precedence; counts and each excluded raw record remain available for audit. Accepted records are sorted by business, date, account and transaction ID; accounts/coverage and exclusions are also stably ordered. Invalid JSON, duplicate JSON keys and malformed or unsupported values receive actionable errors.

## Use and evidence

```bash
uv run --group dev pytest tests/test_data.py
```

`load_input("tests/fixtures/input_90_days.json")` returns a `NormalizedInput` object with accepted transactions, account/business coverage, and exclusions. [The 90-day fixture](../../tests/fixtures/input_90_days.json) is also a copyable example of a new input. [The separate 61-day fixture](../../tests/fixtures/input_61_days.json) tests coverage shift. Ticket 02 now supplies the [full synthetic dataset](SYNTHETIC_DATA.md); the CLI, legacy labels, reviewer, and reports belong to later tickets.
