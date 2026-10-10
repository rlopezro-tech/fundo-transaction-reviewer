# Credit features and illustrative offer — Ticket 06

`credit-features-v1` and `illustrative-offer-v1` implement the approved [business rules](../archive/rules/BUSINESS_RULES.md#5-credit-features-and-offer). **Fundo supplies only the simplified formula and the `NSF_count > 5` cutoff.** The denominators, 30-day AMR normalization, zero-denominator handling, negative floor and cent rounding are our versioned V1 choices, not Fundo underwriting policy.

The CLI uses exactly the accepted posted transactions and account-coverage intersection from Ticket 01 for both legacy and reviewed calculations. Only validated semantic labels differ; it never changes dates, signs or amounts. `credit_report.json` has one business entry with both feature sets and `reviewed_minus_legacy` deltas. Each includes the transaction count, common coverage dates/days, denominators, raw offer terms and policy versions. The run manifest includes a SHA-256 of the report. This remains an **illustrative counterfactual**, not a live funding decision.

| Feature | V1 calculation and limit |
| --- | --- |
| Deposits | Magnitudes of **all** negative Plaid amounts (inflows), including loans, transfers and personal inflows. This measures observed cash in, not sales. |
| Eligible revenue | Magnitudes of inflows satisfying the shared code-owned business/status/group revenue rule. A positive amount cannot be revenue. |
| Revenue/deposits | Eligible revenue ÷ all deposits. `null` with `zero_deposits` when the denominator is zero. Both amounts remain in the output. |
| AMR | Eligible revenue × `30 / observed_common_days` using declared common account coverage, not dates of transactions. Short coverage is flagged as **not directly comparable with 90-day-trained inputs**. |
| NSF / overdraft | Counts of winning labels, not verified incidents or negative-balance days. Zero observed NSF fees at a no-fee bank is not evidence that no payment failed. |
| High-risk debit share | Positive debits in the five high-risk winning groups ÷ **all** positive debits, including personal debits. `null` with `zero_debits` when none exist. |
| Other-funder daily payments | Positive **business** `Active advance` debits ÷ observed common days. Incoming funder disbursements and personal debits are excluded. This is a label-based repayment estimate, not a verified contract; false `Active advance` labels can understate an offer. |

The offer uses `raw = 1.2 × AMR − 20 × other_funder_daily_payments`. Set the post-cutoff amount to zero **only when NSF count exceeds five**. Otherwise floor a negative amount at zero. Round only that final nonnegative USD amount to cents with `ROUND_HALF_UP`; retain unrounded `raw`, `after_nsf_cutoff` and `after_nonnegative_floor` values. A 61-day history can be normalized for arithmetic but does **not** become equivalent to a complete 90-day risk-model input. All values are decimal strings to avoid binary-float changes in money.

`src/fundo_reviewer/credit.py` exposes `compute_features()` for any aligned mapping of semantic labels, so Ticket 07 can calculate synthetic-truth comparators with the exact same accepted records and arithmetic. The provider never receives these features, the offer, or truth.
