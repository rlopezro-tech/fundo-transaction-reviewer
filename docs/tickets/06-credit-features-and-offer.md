# Ticket 06 — Credit features and illustrative offer

**Status:** Ready for implementation; no feature or offer result is measured by writing this ticket.

**Type:** Deterministic credit arithmetic

**Depends on:** [Ticket 03 — labels and revenue](03-legacy-keyword-labels-and-revenue.md), [Ticket 05 — runnable review pipeline](05-cache-provider-and-cli.md)

**Next:** Evaluation and sensitivity reports (Ticket 07)

## Goal

Turn legacy and reviewed labels into **the same per-business feature set** and apply Fundo's simplified offer rule to both. Definitions not supplied by Fundo must be written as versioned project policies and tested before results are interpreted as credit impact. This is an exercise calculation, not a live approval system.

## Scope and proposed v1 policies

1. Use the accepted transactions and explicit account/business coverage from Ticket 01, after its pending/posted and date-window policy. Calculate legacy and reviewed features with one shared function; only labels may differ. Keep the original signed amounts unchanged.
2. **Deposit total:** sum the magnitudes of all accepted inflows (`amount < 0`) in the business's analyzed accounts, including loans and transfers. **Eligible revenue total:** sum inflows whose code-derived revenue flag is true. **Revenue/deposits:** eligible revenue divided by deposit total; return a documented `undefined`/`null` when deposits are zero, not a misleading zero-percent claim. These are proposed project choices, not Fundo-specified denominators.
3. **Average monthly revenue (AMR):** use eligible revenue total × `30 / observed_coverage_days` as a proposed normalization. Compute coverage days from Ticket 01 metadata, never from the first transaction date. Do not silently treat 61 days as 90; expose coverage and a comparability warning in every business result.
4. **NSF and overdraft counts:** count accepted transactions with the corresponding winning group. They are observed **label counts**, not verified failed-payment incidents or negative-balance days. Do not infer a healthy account from zero NSF fees at a no-fee bank.
5. **High-risk share of debits:** as a proposed policy, sum positive debit amounts whose winning group is one of the five `High risk` groups, divided by all accepted positive debit amounts in the business's analyzed accounts. Keep the treatment of personal transactions explicit; use the same denominator before and after review. Return `undefined`/`null` for zero total debits.
6. **Other-funder daily payments:** as a proposed policy, sum **positive** `Active advance` debits and divide by observed coverage days. Never count an incoming funder disbursement or an ordinary expense as a funder payment merely because a counterparty name looks similar. Document any additional requirement used to distinguish repayments from other `Active advance` activity.
7. Apply the supplied formula: `raw_offer = 1.2 × AMR − 20 × other_funder_daily_payments`; if `NSF_count > 5`, set offer to zero. Proposed additional policy: floor negative raw offers at zero and round the final currency amount to cents with a documented `Decimal` rounding mode. Do not round intermediate features before calculation.
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

- [Original challenge](../CHALLENGE.md) — required features, supplied offer formula, NSF cutoff, and 61-day question.
- [Ticket 01](01-transaction-data-contract.md) — accepted records and explicit coverage.
- [Ticket 03](03-legacy-keyword-labels-and-revenue.md) — revenue and active-advance labels.
- [Implementation checklist](../IMPLEMENTATION_CHECKLIST.md) — open metric policies and boundary tests.
- [Financial glossary](../FINANCIAL_GLOSSARY.md) — feature meanings and interpretation limits.
