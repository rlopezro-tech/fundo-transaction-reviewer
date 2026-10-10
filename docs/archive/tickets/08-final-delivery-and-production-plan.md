# Ticket 08 — Final reproducible delivery and production plan

**Status:** README/SOLUTION and evidence matrix drafted; final paid cache, full quality report, no-key clean-checkout replay, spend and repository audit remain pending. Not accepted yet.

**Type:** Integration, documentation, and final verification

**Depends on:** [Ticket 07 — evaluation and sensitivity](07-evaluation-and-sensitivity.md) and all preceding tickets

**Next:** Submit only after the acceptance and completion audit below passes.

## Goal

Turn the implemented tickets into a small, defensible take-home submission: one documented run command, no-key cache replay, measured results with honest limits, and a production plan that explains how an LLM reviewer could be introduced without silently changing funding decisions. This ticket is **not** permission to build a production service.

## Scope

1. Complete `README.md` with copy-paste setup and run commands from a clean checkout; explain the environment variable for **online** calls, the default/offline mode, how to regenerate reports from committed cache without a key, where outputs live, and how to run a small new Plaid-shaped input without truth. State clearly that Plaid API/Sandbox is not needed for v1.
2. Finish a concise **2–3 page `SOLUTION.md`** for an engineering lead. Cover chosen scope and deliberate omissions; data/source and Plaid sign convention; legacy rules and LLM reviewer; model/prompt choices and at least one unsuccessful approach; model-versus-code boundary; failure handling; **measured** results versus simulations/estimates; dollar revenue error, hard negatives, concrete mistakes, before/after credit features and offers, and total actual LLM spend.
3. Answer the two challenge questions in one short paragraph each: (a) why zero observed NSF fees at a no-fee bank is a missing or biased risk signal rather than proof of low risk, and what signal/coverage flag or mitigation to use; (b) what breaks when 61-day histories reach a model trained on 90 days, and how coverage is detected, monitored, and handled. Use Ticket 01 coverage metadata and Ticket 06 feature policy.
4. Write the approximately one-page **production design** in `SOLUTION.md`: run the reviewer in shadow beside the keyword engine; compare measured dollar error, hard-negative flags, decision-impacting changes, and underwriter burden; define a concrete quality/risk gate plus human approval before live changes. Describe how to monitor transaction coverage and label/feature/offer distributions by rules/model version so upstream retraining or keyword fixes cannot silently shift risk inputs.
5. Explain **historical decision replay** after a later keyword fix. List the immutable transaction/input snapshot, legacy and reviewed labels, matched rule trace, generator/input hash, rules/model/prompt/schema/feature/offer versions, cache/provider status, derived features, offer, final decision, and underwriter action needed to reproduce a past decline. Describe how underwriter corrections enter a versioned evaluation set before rule/prompt updates.
6. Disclose all tools used, including AI assistants and how generated code or analysis was checked. Avoid claiming measured results before reports exist. Record actual token usage/spend separately from any price-based estimate; confirm total live LLM spend stayed below **US$10**.
7. Perform the final integration and repository audit: regenerate data and reports from the documented command; replay from cache with no key and provider/network disabled; run tests; verify stable hashes/order; verify a new small input without truth; ensure committed cache and synthetic fixtures are present, no secrets/customer data are committed, and all documentation links resolve. Keep the final report artifacts reproducible and versioned.

## Deliverables

- Completed `README.md` with one-command run and explicit cache-only replay instructions.
- Completed `SOLUTION.md` with results, caveats, credit answers, production plan, and tool disclosure.
- Committed response cache and synthetic fixtures, reproducible `reports/` outputs or documented regeneration, and a run manifest tying inputs and all relevant versions to each result.
- Passing unit and end-to-end tests plus a clean-checkout replay check on a separate temporary environment.
- A short completion matrix mapping each checked item in [the implementation checklist](../IMPLEMENTATION_CHECKLIST.md) to code, test, report, or document evidence; intentionally skipped items remain unchecked and are explained.

## Acceptance criteria

- [ ] The documented command works from a clean checkout; cache-only replay runs without an API key or provider access and reproduces the submitted output hashes.
- [ ] The CLI can process a small new Plaid-shaped input envelope without ground truth **online or from its exact existing cache entries**; it reports flags/features/offers but makes **no measured-accuracy claim**. An uncached strict-offline run fails visibly rather than pretending to review unseen transactions.
- [ ] `README.md` and `SOLUTION.md` contain all challenge deliverables, including measured versus estimated labels, actual spend below US$10, a failed/less successful attempt, explicit omissions, and all tools used.
- [ ] `SOLUTION.md` includes the two short NSF/61-day answers and the four production topics: shadow gate, drift, historical replay, and underwriter feedback.
- [ ] The final reports show per-business before/after/truth metrics, monthly-revenue dollar error, hard-negative false flags, concrete mistakes, offer comparisons, and 2%/5%/10% sensitivity with reproducible method.
- [ ] All tests pass; no secret, real customer data, truth leakage, broken local Markdown link, or undocumented runtime dependency remains.
- [ ] Each implemented requirement has direct evidence in the completion matrix; omitted items are disclosed rather than marked complete.
- [ ] The repository stays small enough to run, explain, and modify during the 60-minute live debrief.

## Out of scope

Do **not** add a frontend, Plaid API/Sandbox integration, production HTTP service, database, cloud deployment, risk-model retraining, or an agent framework merely to appear complete. Do not push or submit the repository unless separately requested.

## References

- [Original challenge](../../CHALLENGE.md) — submission format, debrief, and evaluation criteria.
- [Ticket 05](05-cache-provider-and-cli.md) — replay, budget, CLI, and manifest.
- [Ticket 06](06-credit-features-and-offer.md) — feature/offer definitions.
- [Ticket 07](07-evaluation-and-sensitivity.md) — measured results and sensitivity.
- [Architecture](../../ARCHITECTURE.md) — proposed production controls and verification plan.
- [Implementation checklist](../IMPLEMENTATION_CHECKLIST.md) — final evidence audit.
