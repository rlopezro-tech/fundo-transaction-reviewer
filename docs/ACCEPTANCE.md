# Challenge acceptance checklist

Status reflects repository evidence on the current branch. **Partial** means an implementation or artifact exists but does not fully satisfy the challenge claim; it must not be presented as complete.

| Challenge requirement | Status | Evidence | Remaining gate |
|---|---|---|---|
| Synthetic Plaid-shaped data, about 10 businesses × 90 days and ~2,000 transactions | Pass | `data/transactions/main_90_days.json`; separate truth under `data/ground_truth/` | None for this synthetic scope |
| 13-group baseline plus business/personal and revenue eligibility | Pass | `src/fundo_reviewer/legacy.py`, `revenue.py`; unit tests | None for v1 |
| Reviewer decision and reason for every accepted row | **Partial; final submission is intentionally limited to available results** | `reports/main/run_manifest.json`: 799 valid, 1 invalid, 1,200 provider failures; `tests/test_committed_artifacts.py` cross-checks outcome counts, report hashes, and matching cache batches; 1,201 outcomes retain legacy labels | No additional provider calls planned for this submission; preserve the limitation in the handoff |
| Reviewer cache reproduces full output offline | **Partial / not met** | `cache/batch_reviews.jsonl`: 10/25 batches | Full replay is not a delivery claim; offline mode must continue to fail clearly for missing batches |
| Per-business credit features and illustrative offer | Pass as code; model comparison partial | `src/fundo_reviewer/credit.py`; `reports/main/credit_report.json`; scope split in `reports/evaluation/quality_report.json` | Evaluate a representative/held-out model-reviewed cohort; current credit output remains a synthetic outcome-set comparison |
| 2%, 5%, 10% mislabel sensitivity | Pass as simulation | `reports/evaluation/sensitivity_report.json` | Keep clearly labelled as authored-error simulation, not measured model error |
| Dollar AMR error, hard negatives, and reviewer mistakes | Partial | `reports/evaluation/quality_report.json`: separate `model_reviewed` / `degraded_fallback` counts and per-business coverage | Evaluate a representative/held-out business cohort with adjudicated labels; synthetic truth is only scenario intent |
| NSF observability and 61-day coverage answers | Pass as written analysis | `SOLUTION.md` | None for the take-home response |
| Shadow rollout, drift, historical replay, underwriter feedback | Pass as proposed design | `SOLUTION.md` | Design only; no production service is expected |
| One run command with API key in environment | Pass for online execution | `README.md`; `OPENAI_API_KEY` in local ignored `.env` | Verify from a clean checkout; API quota is currently a blocker |
| Total LLM cost below $10 | Within limit by recorded estimate; not independently billed | Append-only provider ledgers; `SOLUTION.md` | Reconcile final usage and reservations; do not call usage estimate a receipt |
| Central model/provider metadata and routing | Pass for registered hosted models | `src/fundo_reviewer/model_catalog.py`; CLI and pilot call the provider factory; pricing tests | A new provider still requires its adapter/factory entry; Ollama remains diagnostic-only |
| Isolated locked install, static checks, and tests | **Pass locally and on GitHub Actions** | `ruff check .`, `ruff format --check .`, and `180` locked-dependency tests passed in isolated environments on CPython 3.12.14, 3.13.1, and 3.14.8. Includes launcher invocation outside the checkout, concise hosted/local pilot error handling, ledger reservation/settlement failure handling and verified-usage reconciliation, long-cooldown stop behavior for both hosted adapters, and spawned-process regressions for single-flight provider requests and serialized artifact writers. Cache-only launcher replay returned 3 cache hits, 0 API calls, and matched all three committed artifacts byte-for-byte. [GitHub Actions passed for commit `d095cbf`](https://github.com/rlopezro-tech/fundo-transaction-reviewer/actions/runs/38092086102) | This architecture-documentation change does not alter the tested code |

## Submission decision

This repository supports an honest **partial** submission only. It does not support claiming a complete 2,000-row LLM evaluation or full-cache, no-key replay. The remaining 1,200 provider failures and one invalid response are explicitly out of scope for this handoff; do not retry paid calls or present fallback rows as model-reviewed results. Keep the limitations above prominent in any submission.
