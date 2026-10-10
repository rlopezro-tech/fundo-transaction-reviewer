# Development rules and delivery limits — approved v1 decisions

> **Status:** all 17 planning blocks are approved across this file and [BUSINESS_RULES.md](BUSINESS_RULES.md); implementation and measured results are still pending. [CHALLENGE.md](../../CHALLENGE.md) wins over this document. Business rules own financial meaning; this file owns implementation, tests, execution, reproducibility, and scope. A ticket is not complete because its document exists.

## 1. Scope and timebox

| Decision | Challenge requirement | Our decision | Reason | Status |
| --- | --- | --- | --- | --- |
| DEV-01 — scope | Deliver a working reviewer, credit-impact analysis, reproducible output, and production plan; the challenge suggests 6–8 hours and permits omissions. | Complete all **in-scope** challenge deliverables and acceptance criteria across Tickets 01–08. Do not add components that are unused or explicitly out of scope. Report actual effort honestly rather than claiming it fit 6–8 hours if it did not. | The user chose full in-scope completion without unnecessary extras. | **Approved** |
| DEV-11 — safety/failure | Untrusted counterparty text, invalid outputs and outages must be handled; Fundo gives no schema/fallback mechanics. | Separate instructions from JSON-quoted description data; strict schema and semantic validation; retain legacy with degraded status on online failure. | Text and provider output cannot be allowed to change transaction facts or hide missing review. | **Approved** |
| DEV-12 — model/budget | Any provider is allowed, but actual total LLM spend must stay below US$10 and be reported. | Pilot `gpt-6-luna` as a candidate on stratified examples; select final model/prompt only from observed quality and current pricing. Use an $8 operating ceiling and hard stop below $10. | Cost and quality are both evidence-dependent; avoid a blind full-run call. | **Approved** |
| DEV-13 — cache/new input | Commit responses for no-key replay; accept new transactions; failure behavior unspecified. | Strict offline cache-only replay with visible miss/corruption error; online fills misses and visibly degrades on provider failure. A new uncached file needs online review, not an impossible offline claim. | Keeps submitted results reproducible without pretending unseen inputs were reviewed. | **Approved** |
| DEV-17 — evaluation/production/delivery | Explain shadow gate, drift, historical replay, underwriter feedback; deliver README/SOLUTION, tests and measured results. | Use concrete shadow quality gates and immutable decision provenance below; production is design-only. Perform a clean-checkout/no-key audit and disclose every tool/limitation. | Demonstrates operational judgment without building unused production infrastructure. | **Approved** |

- Build the smallest defensible **Python batch CLI** that satisfies the full in-scope challenge, not a production platform. The challenge estimates 6–8 hours; this is an expectation to report against, not permission to skip accepted scope silently. Prefer a thin end-to-end path, then finish the required evidence.
- **Must show:** seeded Plaid-shaped synthetic data and separate truth; 13-group legacy baseline; review of every legacy label; cache-only replay without a key; per-business revenue dollar error and hard-negative review; before/after credit features and offer; a reproducible mislabel sensitivity exercise; concise `README.md` and `SOLUTION.md` with production reasoning.
- **Do not build for v1:** web UI, HTTP API, database, cloud service, real customer data, Plaid API/Sandbox integration, risk-model retraining, agent framework, or automated live funding decisions. Do not add a dependency merely to make the project appear sophisticated.
- If an unforeseen limitation prevents an item, disclose it **openly** in `SOLUTION.md` and the checklist rather than claiming it passed. Reserve time for actual replay, reports, and the 60-minute live debrief; code must be explainable and modifiable under pressure.

## 2. Decision and source hierarchy

1. `docs/CHALLENGE.md`: Fundo's requirements.
2. `docs/rules/BUSINESS_RULES.md`: explicitly adopted v1 business policies, once reviewed.
3. This document: development and delivery constraints.
4. `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION_CHECKLIST.md`, and tickets: proposed design and work tracking. Correct them if they conflict with adopted rules.

Decision blocks **02–10 and 14–16** are detailed in `BUSINESS_RULES.md`; block **17** spans evaluation there and production/delivery here. The 17 blocks define policy, not 17 completed implementation tickets.

**Source trace:** blocks 02–09 derive from the challenge's [Data](../../CHALLENGE.md#data) and [reviewer](../../CHALLENGE.md#1-the-reviewer) sections; blocks 10–13 from [reviewer](../../CHALLENGE.md#1-the-reviewer) and [Environment](../../CHALLENGE.md#environment); blocks 14–16 from [Credit impact](../../CHALLENGE.md#2-credit-impact); block 17 from [Credit impact](../../CHALLENGE.md#2-credit-impact), [Production](../../CHALLENGE.md#3-production), [Deliverables](../../CHALLENGE.md#deliverables) and [Debrief](../../CHALLENGE.md#the-debrief). The tables explicitly separate what those sections require from the V1 choices used to fill gaps.

Every rule we invent must be labeled as a project choice, versioned if it changes outputs, and backed by at least one test. Never attribute a v1 policy to Fundo. No measured-performance claim before a report exists.

## 3. Input and artifact contracts

- **Approved BUS-02:** Ticket 01 will document one JSON input envelope with `as_of`, account/business/coverage metadata, and a Plaid-shaped `transactions` array. Generated data and new debrief input use the **same** validator. Ground truth remains separate. Raw transaction fields are preserved; normalized money uses `Decimal` or cents.
- Keep synthetic transactions in `data/transactions/`, truth in `data/ground_truth/`, response cache in `cache/`, and generated reports in `reports/`. Never embed truth in model-visible data, requests, or cache keys. No real customer data or secrets in Git.
- Use stable transaction IDs and deterministic ordering. Fix generator seed, `as_of`, scenario definitions, and versions. Record input hashes in a run manifest.
- A new file **without truth** must still yield labels, flags, features, and offers when online responses are available; it must not yield accuracy claims. A new uncached file cannot be reviewed in strict offline mode: online cache-fill or an explicitly named degraded/no-review mode is required. Do not blur that distinction in the README.

## 4. Model, safety, and cash budget

- The model sees the normalized evidence needed for review **plus the legacy label and matched-rule trace**, never ground truth or offer/truth metrics. Description fields are untrusted, counterparty-controlled data. Delimit them, instruct the model not to follow embedded commands, and test an instruction-like description. Do not pretend prompt wording alone guarantees safety.
- Put fixed reviewer instructions outside a JSON-serialized transaction-data block; description text has no authority. Give the model no tools. The model may propose only `keep`/`change`, allowed group, business/personal status, confidence, and a short reason. Code uses a strict schema that rejects extra fields, then validates exact ID, allowed values, keep/change consistency, confidence range, and 160-character reason limit; code derives revenue and all credit arithmetic. Preserve raw proposal, validated proposal, applied label, and status.
- Use a small provider interface with fakes in tests. The actual model/prompt is provisional until a measured pilot and error review. Verify current model availability, Structured Outputs support, pricing, account access, and SDK behavior **before** paid calls. `gpt-6-luna` is a candidate, not a proven winner.
- Pilot on a small, representative stratified set first, including hard negatives, Square processor/funder, punctuation and injection cases. Compare at least one weaker prompt/approach, reserve distinct held-out scenarios for the final report, and estimate full-run spend conservatively. Set an **$8 operating ceiling** for cumulative new calls and a hard stop before cumulative actual spend could reach the challenge's **US$10 maximum**, including conservative per-call output-token allowance and retries. Persist an append-only experiment spend ledger so a second run cannot reset the budget; record provider usage, pricing assumption, and actual/estimated cost separately. Cache hits cost no new model call. Never launch thousands of uncached reviews blindly. If measured quality is poor, improve within budget or report the limitation rather than claim success.
- Invalid/refused/incomplete/provider-failed **online** responses retain legacy and surface degraded status. Bound retries. Offline mode must never load an API key or contact the provider; missing/corrupt cache entries fail visibly.

## 5. Cache and reproducibility

- Cache keys hash canonical reviewer-visible normalized fields, legacy label and ruleset version, model ID, prompt version, schema version, and review/flag-policy version. Exclude ground truth and secrets. A changed relevant field/version must miss rather than reuse stale output.
- Store raw response, validated proposal, usage, cost assumption, request digest and status to audit a replay, but never a key. Validate cache integrity and request-key correspondence. Commit the cache entries needed for the submitted demonstration. A refused/failed online response must not be cached as a valid `keep`.
- Use explicit `offline` and `online` modes. Offline only replays committed entries and fails on an unseen/corrupt request. Online reads hits, fills misses and records degraded legacy fallbacks on bounded provider failure. Thus a new truth-free input needs online access unless its exact requests were previously cached; it must never claim measured accuracy.
- The README must provide copy-paste setup and **one documented pipeline command**, plus a distinct cache-only replay command that works without a key. Record the exact dependency lockfile and run versions. Stable inputs and cache must produce stable ordered output hashes.
- The final clean-checkout audit includes no-key/no-network replay, test run, committed-fixture/hash check, secret scan, and a small truth-free input path. A synthetic fixture and a cache alone do not prove clean-checkout reproducibility until this audit passes.

## 6. Tests and evidence, not just checkboxes

For each ticket, require its smallest direct evidence before moving on:

1. **Input/data:** sign, cents, dates, currency, zero amount, pending/posted, duplicate IDs, account ownership, 90/61-day coverage and truth isolation.
2. **Legacy/revenue:** all 13 groups plus unmatched, explicit precedence, punctuation miss, processor/funder collision, business/personal fallback, exclusion set, and no revenue from outflows/personal credits/loans/transfers.
3. **Reviewer/cache:** one outcome per transaction, short useful flags, prompt-injection example, schema and semantic rejection, provider failure, cache invalidation, strict offline miss, no-key replay, and budget guard.
4. **Credit/evaluation:** same accepted records before/after; offer at NSF 5 versus 6; negative floor and cents; false revenue and false repayment direction; per-business AMR dollar errors; hard-negative false flags; truth-free output without accuracy; seeded sensitivity.

`SOLUTION.md` must distinguish **measured on synthetic data**, **simulated**, **estimated**, and **not measured**. Include actual wrong labels, a weaker/failed attempt, limits of descriptions as evidence, two short NSF/61-day answers, a one-page production plan, and all tools used (including AI assistants and how their work was checked).

## 7. Production boundary (document only)

The `SOLUTION.md` production plan must describe the following **proposed future controls**, not claim they were deployed:

1. Run reviewer in shadow beside the keyword engine for at least four weeks on a consented, underwriter-annotated sample spanning businesses, banks and coverage lengths. Compare per-business absolute AMR dollar error, high-impact false changes, hard-negative false-flag rate, offer changes and review burden against the same legacy baseline. A proposed promotion gate is at least **20% lower aggregate absolute AMR error**, **≤5% false flags among annotated hard negatives**, **zero unmitigated high-impact false corrections** in the gate sample, and underwriting/risk sign-off. These are project-proposed thresholds, not Fundo policy; change them only with documented risk-owner approval. Even after the gate, decision-changing flags require human approval before affecting a live offer.
2. Monitor input coverage, pending exclusions, label distributions, revenue/AMR, NSF/overdraft, high-risk share, funder payments and offer distributions by bank, business cohort, ruleset/model/prompt/feature version. Alert or block rollout on unexplained shifts after keyword/classifier updates; compare to a frozen canary corpus and investigate changes before promoting.
3. For historical decline replay, retain an immutable access-controlled input snapshot, accepted/excluded records, account coverage, input hash, legacy labels and matched-rule trace, raw/validated reviewer outputs and cache/provider status, all rules/model/prompt/schema/feature/offer versions, derived features, illustrative offer, **actual** human decision and underwriter action. A later keyword fix creates a new version; it never rewrites the old decision record.
4. Underwriters inspect source evidence, accept/reject/correct flags, and record reason. Their corrections enter a versioned, quality-checked evaluation set before rule/prompt updates; do not treat every override as automatically correct ground truth. **Do not implement this production service for v1.**

## 8. Decision-to-evidence map

| Blocks | Required future proof |
| --- | --- |
| 01–05 | Ticket 01 schema/policy tests, CLI input example, and scope/omissions statement in `SOLUTION.md`. |
| 06–09 | Ticket 02 fixture counts/hashes/truth isolation and Ticket 03 taxonomy, precedence, personal and revenue tests. |
| 10–13 | Ticket 04/05 fake-provider, injection, schema, budget, cache-miss, online-failure and no-key replay tests; measured pilot and spend report. |
| 14–16 | Ticket 06 same-input feature/offer tests, 61-day and NSF 5/6 boundaries, per-business report. |
| 17 | Ticket 07 measured/simulated reports and Ticket 08 `README.md`, 2–3 page `SOLUTION.md`, production design, tool disclosure, clean-checkout replay and final acceptance matrix. |

The map says **what will prove completion**. It is not a claim that code, data, cache, reports or tests already exist.
