# Challenge acceptance checklist

Status reflects repository evidence on the current branch. **Partial** means an implementation or artifact exists but does not fully satisfy the challenge claim; it must not be presented as complete.

| Challenge requirement | Status | Evidence | Remaining gate |
|---|---|---|---|
| Synthetic Plaid-shaped data, about 10 businesses × 90 days and ~2,000 transactions | Pass | `data/transactions/main_90_days.json`; separate truth under `data/ground_truth/` | None for this synthetic scope |
| 13-group baseline plus business/personal and revenue eligibility | Pass | `src/fundo_reviewer/legacy.py`, `revenue.py`; unit tests | None for v1 |
| Reviewer decision and reason for every accepted row | **Partial** | `reports/main/run_manifest.json`: 799 valid, 1 invalid, 1,200 provider failures; 1,201 outcomes are degraded and retain legacy labels | Obtain valid responses for remaining rows; resolve the invalid response |
| Reviewer cache reproduces full output offline | **Partial / not met** | `cache/batch_reviews.jsonl`: 10/25 batches | Fill and validate the remaining 15 batches; run a no-key replay from a clean environment and compare output hashes |
| Per-business credit features and illustrative offer | Pass as code; model comparison partial | `src/fundo_reviewer/credit.py`; `reports/main/credit_report.json`; scope split in `reports/evaluation/quality_report.json` | Evaluate a representative/held-out model-reviewed cohort; current credit output remains a synthetic outcome-set comparison |
| 2%, 5%, 10% mislabel sensitivity | Pass as simulation | `reports/evaluation/sensitivity_report.json` | Keep clearly labelled as authored-error simulation, not measured model error |
| Dollar AMR error, hard negatives, and reviewer mistakes | Partial | `reports/evaluation/quality_report.json`: separate `model_reviewed` / `degraded_fallback` counts and per-business coverage | Evaluate a representative/held-out business cohort with adjudicated labels; synthetic truth is only scenario intent |
| NSF observability and 61-day coverage answers | Pass as written analysis | `SOLUTION.md` | None for the take-home response |
| Shadow rollout, drift, historical replay, underwriter feedback | Pass as proposed design | `SOLUTION.md` | Design only; no production service is expected |
| One run command with API key in environment | Pass for online execution | `README.md`; `OPENAI_API_KEY` in local ignored `.env` | Verify from a clean checkout; API quota is currently a blocker |
| Total LLM cost below $10 | Within limit by recorded estimate; not independently billed | Append-only provider ledgers; `SOLUTION.md` | Reconcile final usage and reservations; do not call usage estimate a receipt |
| Central model/provider metadata and routing | Pass for registered hosted models | `src/fundo_reviewer/model_catalog.py`; CLI and pilot call the provider factory; pricing tests | A new provider still requires its adapter/factory entry; Ollama remains diagnostic-only |
| Clean-checkout install and test | **Pass locally / CI pending** | Prior clean Git archive: 133 passed before the latest CLI-choice test; current locked local suite: `134 passed`; sample offline replay matched all committed artifacts byte-for-byte | Re-run the updated 134-test suite from a fresh Git archive, then push branch and confirm GitHub Actions succeeds |

## Submission decision

This repository supports an honest **partial** submission. It does not support claiming a complete 2,000-row LLM evaluation or full-cache, no-key replay. The release gate is either (a) complete the 15 missing batches, correct/resolve invalid output, regenerate reports, and pass offline replay; or (b) submit explicitly as partial with the limitations above prominent.
