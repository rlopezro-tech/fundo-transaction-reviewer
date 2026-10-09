# Ticket 07 — Reviewer evaluation and mislabel sensitivity

**Status:** Evaluation/sensitivity code and seeded simulation implemented; final paid-cohort quality report pending end-to-end review cache.

**Type:** Measurement and error analysis

**Depends on:** [Ticket 02 — independent ground truth](02-synthetic-dataset-and-ground-truth.md), [Ticket 05 — replayable reviewer](05-cache-provider-and-cli.md), [Ticket 06 — credit features and offer](06-credit-features-and-offer.md)

**Next:** Final delivery and production design (Ticket 08)

## Goal

Measure whether LLM review improves the **funding-relevant** outputs, not just transaction-level agreement. Compare legacy, reviewed, and independent synthetic truth; inspect hard negatives and concrete mistakes; show how 2%, 5%, and 10% mislabel rates can move features and offers. Keep measured synthetic results separate from estimates and real-world claims.

## Scope

1. Join transaction, legacy label, reviewed label, and Ticket 02 truth strictly by stable ID. Fail on missing or duplicate truth IDs for the synthetic evaluation set. Do not expose truth to the reviewer; a separate new input without truth must still produce flags/features but no accuracy claims.
2. Compare group, business/personal, and revenue correctness. Report **signed and absolute monthly revenue dollar error per business** against truth before and after review, not only an aggregate accuracy percentage. Use Ticket 06's AMR formula and the same coverage for all three label sets.
3. Count true corrections, missed mistakes, false changes, and **false flags on hard negatives**. Inspect a small named set of concrete false positives/false negatives with transaction ID, redacted/synthetic description, legacy/reviewed/truth labels, reason, and financial effect. An underwriter should see why a wrong flag matters.
4. Produce before/after/truth per-business tables for Ticket 06 features and offers, including signed offer delta and revenue/deposit, NSF/overdraft, high-risk debit, and daily funder-payment changes. Distinguish a corrected label that changes an offer from one that does not.
5. Define and version a reproducible **2%/5%/10% mislabel experiment**. Start from a clearly stated label baseline (preferably truth), sample a documented number of transactions with a fixed seed, inject **valid alternative labels** rather than arbitrary impossible combinations, and recompute features/offers with the same Ticket 06 functions. Record sampled IDs, error types, amounts, seed, and whether rates are rounded to a whole transaction count. Include both common low-impact and targeted high-impact error cases.
6. Quantify and explain both directions: false revenue tends to inflate AMR/offer; missed revenue tends to reduce it. A false `Active advance` repayment tends to raise daily payments and reduce the offer; a missed repayment tends to do the opposite. Include the `NSF = 5` versus `6` discontinuity and any zero-floor effects when interpreting dollar impact.
7. Label every number as **measured on synthetic data**, simulated sensitivity, estimated cost, or unmeasured assumption. If pilot results show the selected model/prompt is poor, record at least one unsuccessful approach and either revise it within the budget or disclose the limitation honestly.

## Deliverables

- `src/fundo_reviewer/evaluation.py` and reporting support with deterministic joins, quality/error metrics, and seeded sensitivity calculations.
- Reproducible reports in `reports/` for transaction flags, per-business legacy/reviewed/truth metrics, monthly-revenue dollar error, offer deltas, hard-negative false flags, concrete error examples, and 2%/5%/10% sensitivity.
- Tests for joins, sign and magnitude of revenue/advance errors, hard-negative false flags, seeded sampling, NSF threshold discontinuity, and a truth-free input path.
- Short experiment notes and evidence for the final model/prompt choice and a failed or weaker attempt, to be summarized in `SOLUTION.md` in Ticket 08.

## Acceptance criteria

- [ ] Every synthetic transaction is accounted for exactly once in the evaluation join; no truth-only field appears in review requests or cache keys.
- [ ] Per-business **monthly revenue dollar error** is reported before and after review against truth, with signed and absolute values; aggregate scores do not replace it.
- [ ] Hard-negative false flags and representative reviewer errors are visible with reasons and financial consequences, including cases with no offer impact.
- [ ] Legacy, reviewed, and truth-derived features/offers use the same Ticket 06 policy and show clear before/after deltas.
- [ ] The 2%, 5%, and 10% scenarios are seeded, replayable, and document actual sampled counts, IDs, error types, and calculation assumptions.
- [ ] False revenue, false active-advance repayment, and NSF threshold effects are numerically demonstrated in the expected direction, subject to the documented offer floor.
- [ ] A truth-free new file produces no measured-accuracy claims; reports distinguish synthetic measurements from simulations and estimates.

## Out of scope

Do **not** present synthetic accuracy as production performance, retrain the risk model, or automatically change live funding decisions. Ticket 08 packages measured results, caveats, and a production design for human review.

## References

- [Original challenge](../CHALLENGE.md) — dollar revenue error, hard negatives, credit impact, and 2%/5%/10% scenarios.
- [Ticket 02](02-synthetic-dataset-and-ground-truth.md) — independent truth and hard-negative inventory.
- [Ticket 05](05-cache-provider-and-cli.md) — replayed reviewer outcomes and cost records.
- [Ticket 06](06-credit-features-and-offer.md) — shared feature and offer arithmetic.
- [Implementation checklist](../IMPLEMENTATION_CHECKLIST.md) — evaluation evidence and measured/estimated distinctions.
