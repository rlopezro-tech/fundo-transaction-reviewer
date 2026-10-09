# Delivery evidence matrix

This matrix supplements the [implementation checklist](IMPLEMENTATION_CHECKLIST.md). **A checked item means direct evidence exists; a pending item is not accepted merely because code was written.** Fundo's challenge remains authoritative. No production service or real customer data is claimed.

| Challenge/checklist area | Current evidence | Status |
| --- | --- | --- |
| Plaid-shaped input, sign/cents, account coverage, pending/window policy | `src/fundo_reviewer/data.py`, `docs/INPUT_CONTRACT.md`, `tests/test_data.py` | Checked |
| Seeded 10-business/2,000-transaction 90-day synthetic cohort, adversarial scenarios, separate 61-day case | `src/fundo_reviewer/synthetic.py`, `data/transactions/`, `docs/SYNTHETIC_DATA.md`, `tests/test_synthetic.py` | Checked |
| Separate independent scenario-intent truth | `data/ground_truth/`, generator ID alignment tests; truth-free reviewer request/cache tests | Checked |
| All 13 legacy groups, precedence, personal flag, matched trace, revenue exclusions | `src/fundo_reviewer/legacy.py`, `revenue.py`, `docs/LEGACY_POLICY.md`, `tests/test_legacy.py` | Checked |
| Safe reviewer boundary, exact-ID/schema/semantic validation, degraded fallback | `src/fundo_reviewer/reviewer.py`, `docs/REVIEWER_BOUNDARY.md`, `tests/test_reviewer.py` | Checked |
| Provider, version-keyed cache, spend guard, online/offline CLI | `src/fundo_reviewer/{provider,cache,cli}.py`, `docs/EXECUTION.md`, `tests/test_cache_cli.py`; full cache still absent | Implemented; final replay pending |
| V1 credit feature/offer policy and boundaries | `src/fundo_reviewer/credit.py`, `docs/CREDIT_POLICY.md`, `tests/test_credit.py`; CLI produces `credit_report.json` | Implemented; full paid-cohort artifact pending |
| Strict synthetic evaluation with signed/absolute per-business AMR error, hard negatives and examples | `src/fundo_reviewer/evaluation.py`, `tests/test_evaluation.py`; real review `quality_report.json` not yet generated | Implemented; final measurement pending |
| Seeded 2%/5%/10% valid-label simulation and targeted high-impact cases | `reports/evaluation/sensitivity_report.json`, `docs/EVALUATION.md`, `tests/test_evaluation.py` | Checked (simulation, not model accuracy) |
| NSF no-fee-bank and 61-day credit answers; proposed shadow gate, drift, replay and human loop | `SOLUTION.md` | Drafted; final review pending |
| Copy-paste setup/run/replay/new-file instructions and tool disclosure | `README.md`, `SOLUTION.md` | Drafted; clean-checkout proof pending |
| Actual spend below $10, settled usage and conservative unresolved exposure | Append-only `cache/spend_ledger.jsonl`, `docs/EXECUTION.md`, `SOLUTION.md`; final paid run and billing receipt not yet available | Pending final accounting |
| Committed full response cache, no-key/no-network stable 2,000-record replay | `cache/batch_reviews.jsonl`, two identical offline hashes and separate clean-checkout audit **still required** | Pending |
| Final quality/error and per-business offer interpretation | `reports/evaluation/quality_report.json` and updated `SOLUTION.md` **still required** | Pending |
| Final tests, fixture hashes, secret scan and Markdown-link audit | Local tests pass; final clean-checkout, no-key and repository audits **still required** | Pending |

**Explicit non-goals:** Plaid API/Sandbox, real data, UI, database, cloud service, risk-model retraining, agent framework, live offer changes. These are outside the approved V1 scope, not secretly incomplete deliverables. Any unforeseen challenge omission will remain unchecked and be disclosed in `SOLUTION.md`.
