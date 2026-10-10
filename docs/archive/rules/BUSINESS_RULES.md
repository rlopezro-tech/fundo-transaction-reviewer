# Business rules — approved v1 decisions

> **Status:** all 17 planning blocks are approved across this file and [DEVELOPMENT_RULES.md](DEVELOPMENT_RULES.md); implementation and measured results are still pending. [CHALLENGE.md](../../CHALLENGE.md) is the source of truth. Rules tagged **Fundo** come from the challenge; **V1 choices** are our interpretations, not Fundo policy or verified financial facts. Changing an approved choice requires a policy-version change and renewed tests/reports.

## 1. Purpose and limits

- **Fundo:** Review the legacy keyword label of every transaction, flag doubtful labels, and show their effect on credit features and a simplified offer. The reviewer does not replace the keyword engine.
- **V1 choice:** This is an illustrative, synthetic-data analysis. Neither a label nor a model confidence verifies a sale, failed payment, UCC filing, bankruptcy, or actual funding obligation. No result authorizes an advance or a live decline.
- **V1 choice:** Each transaction has exactly one winning group (one of Fundo's 13 groups or `unmatched`) and one business/personal value. Other matched keywords remain in the trace, but do not become extra winning groups.

## 2. Accepted transaction and observation window

| Decision | Challenge requirement | Our decision | Reason | Status |
| --- | --- | --- | --- | --- |
| BUS-02 — input envelope | Use Plaid-shaped transactions and accept a new input without ground truth; Fundo does not prescribe how to supply business/account coverage metadata. | Use **one JSON input file** containing `as_of`, account metadata (`account_id`, `business_id`, coverage dates), and a `transactions` array of Plaid-shaped records. Keep evaluation truth in a separate file. Map each transaction's `account_id` to its business through account metadata; do not require `business_id` on every transaction. | One file is simpler for clean-checkout and live-debrief runs; explicit account metadata prevents guessed ownership/coverage. | **Approved** |
| BUS-03 — amount and currency | Plaid Transactions uses negative amounts for inflows and positive for outflows; Fundo does not specify a currency, precision, or zero-amount policy. | Require explicit `iso_currency_code: "USD"` on every transaction, accept signed amounts with at most two decimal places, parse directly to `Decimal`, and reject missing/non-USD/non-finite/over-precision/zero amounts with record and field context. Never convert or infer currency. | Prevents silent direction, precision, or mixed-currency errors in revenue and offer calculations. | **Approved** |
| BUS-04 — observation coverage | Fundo asks for the last 90 days and discusses 61-day histories, but does not prescribe account-coverage aggregation. | Use the 90 inclusive calendar dates ending on `as_of`; take each business's **intersection of declared account coverage** with that window; reject an empty intersection and inconsistent in-window records; report observed days, excluded out-of-window records, and a warning below 90 days. Keep the 61-day case separate from the main evaluation cohort. | Prevents mixing account histories of different lengths and treating absent transactions as absent bank coverage. | **Approved** |
| BUS-05 — posting and duplicates | The challenge does not prescribe pending/posted or duplicate handling. | Review and calculate from posted records only; report pending exclusions, count linked posted records once, reject duplicate IDs across the raw file, and never fuzzy-merge by text/amount. | Avoids counting unsettled authorizations twice or hiding distinct activity. | **Approved** |
| BUS-06 — synthetic truth | About 10 businesses, 90 days and a couple thousand Plaid-shaped transactions; no real data. | Fixed seeded 10-business synthetic cohort near 2,000 transactions, separate 61-day fixture, independent scenario-intent truth, hard negatives and explicit ambiguity. | Reproducible evidence without pretending transaction text proves every fact. | **Approved** |
| BUS-07 — keyword engine | Fundo names 13 groups but not lists, normalization or precedence. | Use the fixed literal rules and explicit priority below; keep matched-rule trace and deliberate errors. | Makes the legacy baseline explainable without tuning it against truth. | **Approved** |
| BUS-08 — business/personal | A flag is required but Fundo gives no baseline rule. | Personal-marker keywords below; otherwise default business. | Simple, auditable and intentionally reviewable. | **Approved** |
| BUS-09 — revenue | Business credit and no excluding group; exclusions unspecified. | Use the explicit exclusion set below, with `Auto deposit`, `Revenue verification` and `unmatched` not excluding by name alone. | One code-owned eligibility function makes effects comparable. | **Approved** |
| BUS-10 — flags | Doubtful labels need corrections, confidence and reasons; no threshold prescribed. | All valid `change` proposals become flags and are applied only in the illustrative reviewed scenario; no confidence threshold or live automation. | Avoids hiding doubts behind uncalibrated confidence. | **Approved** |
| BUS-14 — credit features | Fundo names features but not denominators or incomplete-window arithmetic. | Use the explicit denominators and 30-day AMR normalization below; return `null` for zero denominators and flag short coverage. | Keeps before/after/truth comparisons consistent. | **Approved** |
| BUS-15 — funder payments | Daily other-funder payments affect offer; estimator unspecified. | Count positive business `Active advance` repayments only, divided by observed common days. | Incoming disbursements are not repayments. | **Approved** |
| BUS-16 — offer | Fundo supplies formula and `NSF_count > 5` zero rule, but not negative floor/rounding. | Floor negative offer at zero, round final USD cents `ROUND_HALF_UP`, retain raw terms. | Prevents negative offers and opaque penny differences. | **Approved** |
| BUS-17 — evaluation | Dollar AMR error, hard negatives and 2/5/10% sensitivity are required; sampling unspecified. | Truth-based per-business signed/absolute errors and seeded valid-label perturbations, with random and targeted cases kept separate. | Exposes financial impact, not just label accuracy. | **Approved** |

| Topic | Rule |
| --- | --- |
| Sign | **Fundo/Plaid Transactions:** negative `amount` is an inflow; positive is an outflow. Never invert it based on description. |
| Money | **Approved V1 choice:** require `iso_currency_code: "USD"` on each transaction and a signed amount with at most two decimal places. Parse JSON numbers directly to `Decimal` (never through binary float). Reject absent, non-finite, over-precision, zero, or non-USD amounts with record and field context; never infer or convert currency. Preserve the raw source value. |
| Identity | **V1 choice:** every transaction has a nonempty stable `transaction_id` and `account_id`; account metadata supplies `business_id`. An account belongs to exactly one business per input. Duplicate transaction IDs are errors, not deduplication candidates. |
| Time | **Approved V1 choice:** use the 90 calendar dates ending on an explicit `as_of` date, inclusive (`as_of - 89 days` through `as_of`). Dates outside the analyzed window are excluded with a count and reason, not silently included. |
| Coverage | **Approved V1 choice:** the input envelope declares inclusive coverage start/end for every analyzed account. Do not infer coverage from the first transaction. For multiple accounts, analyze only their common covered dates within the 90-day window; report those dates and any excluded records. Reject an empty common period or a transaction inside the window but outside its account's declared coverage. Expose observed-day count and a warning below 90 days. A 61-day case is a separate cohort. |
| Posting | **Approved V1 choice:** label, review and calculate only posted (`pending: false`) transactions. Exclude all pending records, including unlinked ones, and report their count. If posted links to pending, count only posted. |
| Missing/invalid data | **V1 choice:** reject malformed dates, invalid amounts, missing required fields, inconsistent account ownership, and unsupported currencies with record/field context. No implicit defaults for facts that change arithmetic. |

The project-specific envelope supplies business identity and coverage; these are **not** claimed to be native Plaid transaction fields. The validator accepts an input file without ground truth. Plaid documents the [Transactions amount convention](https://plaid.com/docs/api/products/transactions/) and [pending-to-posted behavior](https://plaid.com/docs/transactions/transactions-data/).

The envelope requires `as_of`, `accounts`, and `transactions`. Each account requires unique nonempty `account_id`, nonempty `business_id`, and inclusive `coverage_start`/`coverage_end` with start ≤ end. Each transaction requires unique nonempty `transaction_id`, known `account_id`, `YYYY-MM-DD` date, JSON numeric (not Boolean) nonzero `amount`, nonempty `name`, Boolean `pending`, and `iso_currency_code: "USD"`; `unofficial_currency_code` must be absent or null. Optional Plaid fields include `merchant_name`, `pending_transaction_id` and category data. Reject duplicate IDs across **all raw transactions**, even if one is pending; never merge on similar text, date or amount. A transaction within the 90-day window but outside its own account's declared coverage is invalid; transactions outside the analyzed common period are excluded with reason counts. The generator uses fixed `as_of = 2026-10-08` and seed `20261008`; new inputs supply their own `as_of`.

## 2a. Synthetic truth boundary

Generate 10 entirely synthetic businesses with approximately 90 days of explicit coverage and approximately 2,000 transactions in the main cohort; keep a separate 61-day fixture. Commit the seed, generator version, ordered fixtures and hashes. Include normal processor/customer revenue, expenses, personal activity, transfers, advance disbursements and repayments, NSF/overdraft signals, all 13 groups, `SQUARE INC` versus `SQUARE CAPITAL`, punctuation misses, hard negatives, high-dollar errors, and an instruction-like counterparty description. A no-fee-bank scenario has zero **observed fees**, not proven zero failed attempts; latent incidents belong in scenario metadata/limitations, not invented bank transactions.

Truth is a separate ID-keyed artifact created from **scenario intent**, never from legacy rules or LLM output. Store intended group, business/personal, code-consistent revenue, scenario ID, hard-negative marker and rationale. Mark cases whose intended meaning is not inferable from bank text as ambiguous; do not present performance on them as verified real-world accuracy. Reserve scenario templates/businesses for a held-out final check instead of tuning every rule/prompt against the whole truth file.

## 3. Legacy labels and revenue

- **Fundo:** Represent these 13 groups: `Not average monthly revenue`, `NSFs`, `Overdraft`, `Internal transfer`, `UCC`, `Active advance`, `Auto deposit`, `Revenue verification`, `High risk — gambling`, `High risk — bankruptcy`, `High risk — debt settlement payments`, `High risk — garnishment`, `High risk — other`. `unmatched` means no winning keyword; it is not a fourteenth Fundo group.
- **Approved V1 choice:** Search `name` and present `merchant_name` after Unicode NFKC normalization, case-folding and whitespace collapse; preserve punctuation. Use literal substring matching against the fixed starter list below, with stable rule IDs and all matches retained. Do not fuzzy-match, stem, or silently override from Plaid category. This is deliberately imperfect; `square` can catch `SQUARE INC`, while `ucc-1` misses `UCC 1`. Version the ruleset and do not tune it secretly against truth.
- **V1 choice:** When multiple groups match, the explicit priority is: `NSFs` > `Overdraft` > `High risk — garnishment` > `High risk — bankruptcy` > `High risk — debt settlement payments` > `High risk — gambling` > `High risk — other` > `Internal transfer` > `Active advance` > `UCC` > `Not average monthly revenue` > `Revenue verification` > `Auto deposit`. The exact list order cannot depend on dictionary iteration. This is a baseline rule, not a claim that one risk signal matters more than another.
- **Approved V1 choice:** Baseline personal markers in the same normalized text are `personal`, `owner draw`, `owner contribution`, `family transfer`, and `household`; any match means personal, otherwise default business. That fallback will create errors and is deliberately reviewable. Do not infer legal business ownership solely from Plaid category.
- **Fundo:** Revenue requires a **business credit** and no excluding winning group.
- **Approved V1 choice:** Exclude revenue when the winner is `Not average monthly revenue`, `NSFs`, `Overdraft`, `Internal transfer`, `UCC`, `Active advance`, or any of the five `High risk` groups. `Auto deposit`, `Revenue verification`, and `unmatched` do **not** exclude a business inflow by name alone. Thus they may still cause false revenue; this is an explicit weakness for the reviewer and evaluation to expose. A positive amount or personal inflow is never revenue.
- **V1 choice:** An incoming funder disbursement is `Active advance` but is **not** a payment and is **not** revenue. A business debit labeled `Active advance` represents an estimated repayment only when its description supports a funder payment; otherwise it should be another group or flagged as ambiguous. Code never changes an amount's direction.

| Group | Approved starter literal keywords |
| --- | --- |
| Not average monthly revenue | `tax refund`, `insurance payout`, `refund`, `reversal` |
| NSFs | `nsf`, `returned item` |
| Overdraft | `overdraft`, `od fee` |
| Internal transfer | `internal transfer`, `xfer own` |
| UCC | `ucc-1`, `ucc filing` |
| Active advance | `square`, `capital`, `funding`, `advance` |
| Auto deposit | `auto deposit`, `direct deposit` |
| Revenue verification | `merchant settlement`, `processor`, `sales deposit` |
| High risk — gambling | `casino`, `sportsbook` |
| High risk — bankruptcy | `bankruptcy`, `chapter 11` |
| High risk — debt settlement payments | `debt settlement`, `debt relief` |
| High risk — garnishment | `garnishment`, `wage levy` |
| High risk — other | `fraud recovery`, `collection agency` |

## 4. Reviewer decisions

- **Fundo:** The model reviews the existing label, not a blank transaction. Every doubtful label needs a proposed group, business/personal value, confidence, and a brief underwriter-readable reason; revenue is recomputed in code.
- **Approved V1 choice:** Every valid `change` proposal is reported as a flag, regardless of confidence. For the **illustrative demonstration only** (whether replayed offline or generated online), apply every valid change to calculate the reviewed counterfactual. Preserve the original proposal and legacy label. Confidence is a self-reported model value, **not calibrated probability** and not a live-decision gate. No threshold suppresses valid doubts.
- **V1 choice:** If evidence is insufficient, the model should `keep` and explain uncertainty briefly instead of inventing a verified fact. `keep`, invalid response, refusal, provider failure, and cache miss are different statuses. Invalid/refused/failed **online** review leaves legacy unchanged and is visibly degraded. An **offline** cache miss is an error, not a silent `keep`.
- **V1 choice:** No model correction automatically changes a live funding decision. A future production gate requires measured quality and human approval.

The structured proposal contains exact transaction ID, `keep`/`change`, allowed group or `unmatched`, business/personal value, confidence in `[0,1]`, and a reason of at most 160 characters. For `keep`, proposed semantic labels must equal legacy labels; for `change`, at least one must differ. Code rejects extra/contradictory source edits and recomputes revenue from the final semantic label plus original signed amount. A valid `keep`, valid `change`, invalid response, refusal, provider failure, and offline cache miss remain distinct outcomes.

## 5. Credit features and offer

Calculate legacy, reviewed, and (synthetic evaluation only) truth values from the **same accepted records, dates, and functions**. Only labels differ. Use `Decimal` or integer cents throughout.

| Feature | V1 definition |
| --- | --- |
| Deposits | Sum of magnitudes of all accepted negative amounts across the analyzed accounts, including personal inflows, loans, and transfers. This is cash entering observed accounts, not sales. |
| Eligible revenue | Sum of magnitudes of inflows satisfying the code-owned rule in §3. |
| Revenue/deposits | Eligible revenue / deposits; `null` with a reason if deposits are zero. |
| Average monthly revenue (AMR) | Eligible revenue × `30 / observed_common_days`. Coverage comes from envelope metadata/common period, not transaction dates. A 61-day normalized result must be marked **not directly comparable** with a 90-day-trained risk input. |
| NSF / overdraft counts | Counts of accepted transactions whose winning group is `NSFs` / `Overdraft`. They are observed label counts, not verified incidents. |
| High-risk debit share | Sum of positive amounts in the five `High risk` winning groups / all accepted positive amounts, including personal transactions. `null` with a reason when total debits are zero. Report numerator and denominator. |
| Other-funder daily payments | Sum of positive **business** `Active advance` repayment amounts / observed common days. Never count incoming disbursements or personal debits. The label is an estimate, not proof of a contract. |

**Fundo's formula:** `1.2 × AMR − 20 × other-funder daily payments`, set to zero when **NSF count > 5** (not at 5). **V1 choices:** floor a negative result at zero; round only the final USD offer to cents using `ROUND_HALF_UP`; keep unrounded components and the pre-floor value in reports. The result is an illustrative formula output, not Fundo's actual underwriting decision.

Zero observed NSF fees at a no-fee bank is a **missing/biased signal**, not proof of zero failed payments. Store the bank-fee-observability scenario/flag separately and explain the limitation. Coverage shorter than 90 days also changes the meaning of counts and amount distributions, even when AMR is normalized; never silently treat a 61-day application as a complete 90-day one.

## 6. Evaluation meaning

- Ground truth is ID-keyed, generated from independent scenario intent, and never included in transactions sent to the reviewer or cache keys. Ambiguous scenarios must say what is and is not observable from bank text.
- Report signed **and absolute AMR dollar error per business**, hard-negative false flags, concrete errors, and offer deltas. A synthetic truth score is not production accuracy.
- Run seeded 2%/5%/10% mislabel simulations from truth using valid alternative labels; record selected IDs, counts, amounts, seed, and error types. Show both random/common errors and targeted high-dollar/NSF-threshold cases. Label these **simulations**, not measured reviewer performance.

For each rate, select `round-half-up(rate × N)` accepted transactions without replacement from the truth baseline, where `N` is **all accepted transactions**. Candidate transactions must have at least one scenario-authored, economically plausible `alternative_label` stored **only with truth**; report that eligible pool size so the sampling bias is visible, and fail rather than silently undersample if the pool is too small. Use fixed seeds `20261009`, `20261010`, and `20261011` for the 2%, 5%, and 10% scenarios respectively. Record each scenario's sampled IDs, actual counts, error types and amounts; separately report targeted high-dollar false revenue, missed revenue, false/missed funder repayment, and NSF 5→6 stress cases. Never portray targeted cases as random or one seeded draw as a distribution estimate. Apply the sampled alternative group/business labels, then recompute revenue and offers through the same code as the main comparison. Report transaction group/business/revenue correctness, per-business signed and absolute AMR error, hard-negative false flags, concrete false positives/negatives, and offer-impacting versus no-impact corrections.

## 7. Policy change control

The choices above are approved as v1 policy, not implemented evidence. Any later change to keywords, precedence, exclusions, coverage, denominators, payment criteria, flag application, or offer arithmetic must be versioned, tested, and disclosed before comparing results. Do not rewrite a baseline quietly after seeing ground truth.
