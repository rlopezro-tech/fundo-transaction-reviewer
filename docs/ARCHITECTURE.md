# Architecture

## Scope

A deterministic Python batch pipeline for synthetic, Plaid-shaped transactions. It is an evaluation tool, not a production underwriting system. Ground truth is isolated from the reviewer and read only by the evaluator.

```text
transaction JSON → validate/window → keyword baseline → cached/provider review
                                         ↓                        ↓
                                  baseline features        validate proposal
                                                                  ↓
                                                      code-derived revenue
                                                                  ↓
                                                reviewed features + report
                                                                  ↓
                          separate synthetic truth → evaluation/sensitivity
```

## Boundaries

- **Code owns:** input validation, signed amount interpretation, 13-group precedence, revenue eligibility, feature formulas, offer calculation, cache identity, and output validation.
- **Model proposes only:** keep/change, group, business/personal, confidence, and a short reason. It cannot edit transaction facts, revenue, features, or offer.
- **Failure behavior:** invalid, incomplete, refused, or unavailable provider output retains the baseline label and is marked degraded. An uncached offline request fails instead of pretending it was reviewed.
- **Safety:** descriptions are untrusted JSON data; the provider has no tools. Structured output is checked again in application code.
- **Reproducibility:** model/prompt/schema/input identity is hashed into cache entries; output artifacts include hashes and status counts.

## Main modules

| Module | Responsibility |
| --- | --- |
| `data.py`, `synthetic.py` | Plaid-shaped validation and deterministic synthetic fixtures |
| `legacy.py`, `revenue.py` | Keyword labels and code-derived revenue eligibility |
| `reviewer.py`, `provider.py` | Prompt/schema validation, provider access, and degraded fallback |
| `cache.py` | Integrity-checked replay cache and conservative spend ledger |
| `credit.py` | Per-business feature and illustrative offer calculations |
| `cli.py` | Online cache fill or offline cache replay |
| `evaluation.py` | Separate truth-based quality and seeded sensitivity reports |

## Current delivery limitation

The main cohort contains 2,000 rows; 799 have valid model proposals, one model response is invalid, and 1,200 rows use degraded legacy fallback. OpenAI returned organization-level 100k TPM errors on both configured keys. Thus the report is complete as an **outcome/fallback snapshot**, but the model cache and no-key replay are partial. See [`../SOLUTION.md`](../SOLUTION.md).
