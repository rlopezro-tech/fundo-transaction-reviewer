# V1 Implementation Checklist

> **Status:** implementation checklist; unchecked items are not implemented or verified. [CHALLENGE.md](CHALLENGE.md) is the source of truth. The 17 planning decisions are approved in [BUSINESS_RULES.md](rules/BUSINESS_RULES.md) and [DEVELOPMENT_RULES.md](rules/DEVELOPMENT_RULES.md), but **approval is not implementation evidence**. [ARCHITECTURE.md](ARCHITECTURE.md) defines the technical design. The user chose to complete all in-scope deliverables without unnecessary extras; disclose any unforeseen omission in `SOLUTION.md` rather than silently checking an item.

Use this file to track **what must be built or written** and **how completion will be verified**. The policy choices are approved in the two rules documents, but a checkbox is complete only when its code, test, report, or delivery-document evidence exists. The policies are **our design choices**, not rules supplied by Fundo.

## 1. Approved policies to implement and verify

- [x] Define the exact transaction fields retained from Plaid-shaped input; document date-window boundaries, currency handling, pending/posted duplicates, and malformed-record behavior. **Evidence:** [input contract](INPUT_CONTRACT.md), `src/fundo_reviewer/data.py`, `tests/test_data.py`.
- [x] Define the 13 keyword lists, normalization/matching behavior, explicit group precedence, and representation of unmatched transactions. Keep the deliberately imperfect engine versioned. **Evidence:** `src/fundo_reviewer/legacy.py`, [policy note](LEGACY_POLICY.md), `tests/test_legacy.py`.
- [x] Define how the business/personal flag is assigned and the exact groups that exclude a business credit from revenue. **Evidence:** `src/fundo_reviewer/revenue.py`, [policy note](LEGACY_POLICY.md), `tests/test_legacy.py`.
- [ ] Define average monthly revenue normalization for 90-day and incomplete windows, the denominator for revenue/deposits, and the denominator and unit for high-risk debit share. **Evidence:** feature definitions and arithmetic tests.
- [ ] Define which active-advance **debits** count as other-funder payments and how to estimate their daily amount. Do not treat funder disbursements or ordinary expenses as payments. **Evidence:** estimator and direction tests.
- [ ] Implement the approved offer rounding/negative floor, all-valid-change flag policy (no confidence threshold), and seeded sampling method for 2%/5%/10% mislabel scenarios. **Evidence:** policy notes and boundary tests.

## 2. Data and legacy labels — build

- [x] Generate a deterministic, synthetic dataset of 10 businesses, 90 days each, and 2,000 Plaid-shaped transactions. Use **no real customer data**. **Evidence:** `src/fundo_reviewer/synthetic.py`, [dataset summary/hashes](SYNTHETIC_DATA.md), `tests/test_synthetic.py`.
- [x] Include normal and funder-relevant adversarial cases: noisy descriptions; processor revenue versus funder loan (`SQUARE INC` / `SQUARE CAPITAL`); punctuation-sensitive keyword misses; internal transfers; personal credits; hard negatives; and a bank with no NSF fees. **Evidence:** [scenario inventory](SYNTHETIC_DATA.md), `tests/test_synthetic.py`.
- [x] Keep a **separate, ID-keyed ground-truth label** derived from scenario intent, not copied from the legacy engine. **Evidence:** `data/ground_truth/`, ID-alignment and truth-isolation tests. Reviewer prompt/cache inspection remains for Tickets 04–05, when those artifacts exist.
- [x] Validate Plaid Transactions sign convention: positive `amount` is money out; negative is money in. Validate required IDs, dates, amounts, and business/account association. **Evidence:** `src/fundo_reviewer/data.py`, `tests/test_data.py`.
- [x] Label every transaction with a versioned, deliberately simple keyword engine; log matched rules and apply explicit precedence when groups collide. **Evidence:** `label_transactions()` full-fixture deterministic test; run-output persistence belongs to Ticket 05.
- [x] Support all 13 groups: Not average monthly revenue; NSFs; Overdraft; Internal transfer; UCC; Active advance; Auto deposit; Revenue verification; High risk — gambling; High risk — bankruptcy; High risk — debt settlement payments; High risk — garnishment; High risk — other. Also assign business/personal. **Evidence:** taxonomy coverage tests in `tests/test_legacy.py`.
- [x] Derive revenue in code **only** for an eligible business credit after the exclusion rule; do not equate every deposit with sales. **Evidence:** `is_revenue_eligible()` and direction/exclusion tests.
- [x] Keep the main evaluation dataset at 90 days; add a **separate 61-day fixture/scenario** for coverage-shift analysis. **Evidence:** `data/transactions/short_61_days.json`, `tests/test_synthetic.py`.

## 3. LLM reviewer — build

- [x] Review **every** legacy-labeled transaction rather than relabeling the dataset without seeing the legacy result. **Evidence:** 2,000-record fake-provider test in `tests/test_reviewer.py`; online execution belongs to Ticket 05.
- [x] For each doubted label, report the proposed group, business/personal flag, **code-derived revenue yes/no**, confidence, and a reason an underwriter can read in about five seconds. **Evidence:** `ReviewOutcome`, schema/flag tests; persisted report belongs to Ticket 05.
- [x] Keep the boundary explicit: the LLM proposes semantic corrections; code validates allowed values and derives revenue. The LLM cannot change source amounts, dates, IDs, credit direction, features, or offer math. **Evidence:** [boundary note](REVIEWER_BOUNDARY.md), validator tests.
- [x] Treat description fields as untrusted counterparty-authored data, not instructions; include an adversarial description case. **Evidence:** JSON prompt boundary and fake observed behavior in `tests/test_reviewer.py`; live behavior remains to be measured.
- [x] Validate response schema, transaction ID, keep/change consistency, confidence range, and reason length. Invalid, refused, incomplete, or unavailable **online** responses retain the legacy label and record degraded status. **Evidence:** failure-path tests.
- [ ] Choose a model/prompt based on observed results, not only price; explain the choice and at least one unsuccessful attempt in `SOLUTION.md`. **Evidence:** experiment notes and measured comparison.

## 4. Reviewer evaluation — build and report

- [ ] Compare legacy and reviewed labels against independent ground truth, including **monthly revenue dollar error per business** before and after review. **Evidence:** per-business report.
- [ ] Count false flags on **hard negatives** and inspect concrete false positives/false negatives, not just aggregate accuracy. **Evidence:** error-case report.
- [ ] Separate measured results on synthetic truth from estimates or assumptions. On a new file without truth, show flags/features but **do not claim measured accuracy**. **Evidence:** report labels and no-truth CLI test.

## 5. Credit impact — build and report

- [ ] Compute, per business for both legacy and reviewed labels: revenue/deposits, NSF count, overdraft count, high-risk debit share, average monthly revenue, and daily payments to other funders. **Evidence:** before/after feature table and tests.
- [ ] Apply the same offer rule to both feature sets: `offer = 1.2 × average monthly revenue − 20 × other funders' daily payments`. Set the offer to **zero only when NSF count > 5**. **Evidence:** offer table and tests at NSF 5 and 6.
- [ ] Show seeded 2%, 5%, and 10% mislabel scenarios and how each moves relevant features and offers; distinguish high-impact errors from inconsequential ones. **Evidence:** sensitivity report with method and seed.
- [ ] Explain the different **direction and dollar effect** of false revenue and false active-advance labels, including false positives and false negatives. **Evidence:** short analysis with examples in `SOLUTION.md`.
- [ ] Answer in one short paragraph why zero observed NSF fees at a no-fee bank is an incomplete risk signal and how to mitigate it. **Evidence:** `SOLUTION.md`.
- [ ] Answer in one short paragraph what breaks when a 90-day-trained risk model receives 61 days, and how to detect/handle the shift. **Evidence:** `SOLUTION.md`.

## 6. Reproducible delivery — build and document

- [ ] Provide **one documented command** that runs the pipeline from a clean checkout, with an API key read from an environment variable only for live calls. **Evidence:** fresh-environment CLI test and `README.md`.
- [ ] Commit version-keyed LLM responses as a cache. An **offline** replay must never call the provider or require an API key; a missing/corrupt cache entry must fail visibly instead of silently changing results. **Evidence:** replay tests and stable output hashes.
- [ ] Keep actual total LLM spend **under US$10**; record token usage, actual spend, and the pricing assumption separately. **Evidence:** cost report and `SOLUTION.md`.
- [ ] Generate deterministic, underwriter-readable flags, per-business metrics, offer comparisons, error examples, and a run manifest with relevant input/rule/model/prompt/offer versions. **Evidence:** committed or reproducible report artifacts.
- [ ] Write `README.md` with copy-paste setup/run and cache-replay commands. Write a concise 2–3 page `SOLUTION.md` with scope/omissions, measured versus estimated results, model/prompt choice, failed attempts, code/model boundary, credit answers, production design, and all tools used (including AI assistants). **Evidence:** both documents.
- [ ] Verify the code can accept a small new Plaid-shaped transaction file for the live debrief without requiring ground truth. **Evidence:** end-to-end fixture test.

## 7. Production design — document only

- [ ] Describe running the reviewer in **shadow mode** next to the keyword engine and a measurable quality/risk gate before any correction changes a live funding decision. **Evidence:** approximately one page in `SOLUTION.md`.
- [ ] Describe monitoring for label/feature/offer drift after keyword-engine or classifier changes, including input-window coverage. **Evidence:** same production page.
- [ ] Describe how to reproduce a historical decline after a later keyword fix: retain source snapshot, labels, rules/model/prompt versions, derived features, offer logic, decision, and human action. **Evidence:** same production page.
- [ ] Describe where underwriters approve/correct flags and how their feedback enters a versioned evaluation set before rule/prompt changes. **Evidence:** same production page.

## 8. Explicit non-goals for this take-home

- [ ] Record any intentionally skipped challenge item and why in `SOLUTION.md`. Do **not** mark an omitted item above as completed.
- Plaid Sandbox integration, real customer data, a production API, a frontend, a database, cloud deployment, retraining the risk model, and an agent framework are **not required for v1**.
