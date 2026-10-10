# Ticket 06 — Credit features and illustrative offer

**Status:** Implemented and locally tested; final paid-cohort reviewed artifact is deferred to the end-to-end validation phase.

**Type:** Deterministic credit arithmetic

**Depends on:** [Ticket 03 — labels and revenue](03-legacy-keyword-labels-and-revenue.md), [Ticket 05 — runnable review pipeline](05-cache-provider-and-cli.md)

**Next:** Evaluation and sensitivity reports (Ticket 07)

## Goal

Turn legacy and reviewed labels into **the same per-business feature set** and apply Fundo's simplified offer rule to both. Definitions not supplied by Fundo must be written as versioned project policies and tested before results are interpreted as credit impact. This is an exercise calculation, not a live approval system.

## Scope and approved v1 policies to implement

1. Use the accepted transactions and explicit account/business coverage from Ticket 01, after its pending/posted and date-window policy. Calculate legacy and reviewed features with one shared function; only labels may differ. Keep the original signed amounts unchanged.
2. **Deposit total:** sum the magnitudes of all accepted inflows (`amount < 0`) in the business's analyzed accounts, including loans, transfers and personal inflows. **Eligible revenue total:** sum inflows whose code-derived revenue flag is true. **Revenue/deposits:** eligible revenue divided by deposit total; return a documented `undefined`/`null` when deposits are zero, not a misleading zero-percent claim. These are approved project choices, not Fundo-specified denominators.
3. **Average monthly revenue (AMR):** use eligible revenue total × `30 / observed_common_days` under the approved normalization. Compute coverage days from Ticket 01 account metadata, never from the first transaction date. Do not silently treat 61 days as 90; expose coverage and a comparability warning in every business result.
4. **NSF and overdraft counts:** count accepted transactions with the corresponding winning group. They are observed **label counts**, not verified failed-payment incidents or negative-balance days. Do not infer a healthy account from zero NSF fees at a no-fee bank.
5. **High-risk share of debits:** sum positive debit amounts whose winning group is one of the five `High risk` groups, divided by all accepted positive debit amounts in the business's analyzed accounts, **including personal debits** under the approved policy. Use the same denominator before and after review. Return `undefined`/`null` for zero total debits.
6. **Other-funder daily payments:** sum **positive business** `Active advance` repayment debits and divide by observed common coverage days. Never count an incoming funder disbursement, personal debit, or ordinary expense as a funder payment merely because a counterparty name looks similar. Semantic labeling must distinguish repayment from other advance-related activity.
7. Apply the supplied formula: `raw_offer = 1.2 × AMR − 20 × other_funder_daily_payments`; if `NSF_count > 5`, set offer to zero. Under the approved v1 choice, floor negative raw offers at zero and round only the final USD amount to cents with `ROUND_HALF_UP`. Do not round intermediate features before calculation.
8. Version the feature and offer policies. Preserve totals, denominators, coverage days, raw and final offer, and the rule version in machine-readable per-business output so Ticket 07 can explain each delta.

## Deliverables

- `src/fundo_reviewer/credit.py` (or an equally small module) with shared feature and offer functions for legacy, reviewed, and later truth-derived labels.
- A concise feature/offer policy note in `docs/` that distinguishes Fundo's formula from our denominator, normalization, zero-denominator, negative-floor, and rounding choices.
- Deterministic per-business legacy/reviewed feature and offer artifacts in `reports/` or produced by the CLI; include coverage and version metadata.
- Unit tests in `tests/` for signs, denominators, credit features, incomplete coverage, money precision, and offer boundaries.

## Acceptance criteria

- [ ] Every business has legacy and reviewed values for revenue/deposits, NSF count, overdraft count, high-risk debit share, AMR, daily other-funder payments, coverage, and offer.
- [ ] The same transaction set, coverage, and formula are used for both label sets; only corrected labels can change the result.
- [ ] Tests prove a funder **disbursement** is not a payment, a funder **repayment** can be, and a false active-advance label moves the payment term in the correct direction.
- [ ] Tests cover zero deposits/debits, personal and internal-transfer inflows, money precision, a negative raw offer, and a 61-day history flagged as not directly comparable with 90-day-trained inputs.
- [ ] At `NSF_count = 5`, the zero-offer cutoff does not fire; at `NSF_count = 6`, it does. The final floor and cent-rounding policy is explicit.
- [ ] Output exposes numerator, denominator, coverage, policy versions, and before/after deltas; no result is described as a real Fundo funding decision.

## Out of scope

Do **not** train or change a risk model, approve a business, run the 2%/5%/10% sensitivity study, or claim that a labeled risk event is legally verified. Ticket 07 evaluates the impact; Ticket 08 writes the final interpretation and production plan.

## References

- [Original challenge](../../CHALLENGE.md) — required features, supplied offer formula, NSF cutoff, and 61-day question.
- [Ticket 01](01-transaction-data-contract.md) — accepted records and explicit coverage.
- [Ticket 03](03-legacy-keyword-labels-and-revenue.md) — revenue and active-advance labels.
- [Implementation checklist](../IMPLEMENTATION_CHECKLIST.md) — open metric policies and boundary tests.
- [Financial glossary](../../reference/FINANCIAL_GLOSSARY.md) — feature meanings and interpretation limits.
