# Financial Glossary for Developers

> **Purpose:** A plain-English guide to the financial terms and data conventions used in this project. This is not financial or legal advice. [Fundo's challenge](../CHALLENGE.md) is the source of truth for requirements; [BUSINESS_RULES.md](../archive/rules/BUSINESS_RULES.md) records our approved V1 choices and [IMPLEMENTATION_CHECKLIST.md](../archive/IMPLEMENTATION_CHECKLIST.md) tracks implementation evidence. **Not specified** means Fundo did not define a rule, even if our V1 policy now does. Do not treat our interpretation as Fundo policy.

## The project in one minute

Fundo considers **revenue-based advances** for small businesses. The project reads roughly 90 days of bank transactions, applies a simple legacy keyword classifier, and asks an LLM to **review** its labels—not replace the classifier. Code then turns the labels into credit features and a simplified offer. An underwriter needs to understand why a questionable label was flagged.

The basic flow is:

`bank transaction → legacy group + business/personal label → LLM review → code-derived revenue → credit features → illustrative offer`

Three distinctions drive nearly every calculation:

1. **Money entering an account is not necessarily sales revenue.** It could be a loan, an internal transfer, or a refund.
2. **A transaction label is not verified financial or legal evidence.** It is a classification based on incomplete bank data.
3. **The LLM proposes semantic corrections; code owns arithmetic and eligibility rules.** The model should not decide the offer or override the transaction amount.

## 1. Business and funding terms

| Term | Meaning in this project | Why a developer should care |
| --- | --- | --- |
| **Applicant / business** | The small business seeking funding. Its recent bank activity is the input to the analysis. | Features and offers are calculated **per business**, not per transaction. |
| **Revenue-based advance** | Funding related to a business's revenue. A merchant cash advance is a related form of financing; contracts can differ. | An advance disbursement increases the bank balance but is **not a customer sale**. Repayments to a funder reduce cash available for another advance. [FTC overview](https://www.ftc.gov/news-events/news/press-releases/2022/01/merchant-cash-advance-providers-banned-industry-ordered-redress-small-businesses). |
| **Funder / other funder** | A third party that has already financed the business. | Payments to that party are relevant to the `Active advance` group and the offer calculation. |
| **Offer** | The amount produced by this exercise's simplified formula. | It is an illustration of label impact, **not** a real approval, contract, or final price. |
| **Underwriter** | The person who reviews funding risk and ambiguous cases. | A flag needs a short, checkable reason, not just a model score. |

## 2. Reading a Plaid-shaped bank transaction

**A transaction** is a dated movement of money on an account. The record may include `amount`, `name`, `merchant_name`, category fields, and pending status. Bank descriptions are often abbreviated, noisy, or supplied in part by a counterparty.

| Term | Meaning | Implementation implication |
| --- | --- | --- |
| **Credit / inflow** | Money **entering** the account. In Plaid Transactions, `amount` is **negative**. | `amount = -100.00` means a $100 inflow. Here, “credit” means direction—not a credit score or loan. |
| **Debit / outflow** | Money **leaving** the account. In Plaid Transactions, `amount` is **positive**. | `amount = +100.00` means a $100 outflow; use its positive magnitude when totaling debits. This convention may differ from a bank statement or another Plaid product. [Plaid Transactions API](https://plaid.com/docs/api/products/transactions/). |
| **Deposit** | An inflow into the observed account, regardless of source. | A deposit may be a sale, loan, transfer, refund, or something else. **Deposit ≠ revenue.** |
| **Counterparty / merchant** | The person or organization on the other side of the movement. | Similar names can mean different things: the challenge contrasts `SQUARE INC` processor deposits with `SQUARE CAPITAL` financing. |
| **Payment processor** | A service that collects customer payments and pays the business, often as a net deposit. | A processor deposit may be revenue, but the name alone does not prove it. |
| **ACH** | A US electronic bank-transfer network. `ACH CREDIT` and `ACH DEBIT` describe transfer direction/type. | Those strings alone do not establish a sale or an advance repayment. |
| **`name`, `merchant_name`, original description** | Text that may identify a transaction. Plaid can provide a cleaned merchant name separately from the institution's original description; it may be absent. | Treat all description fields as evidence to interpret, **not trusted instructions** or infallible accounting facts. [Plaid Transactions API](https://plaid.com/docs/api/products/transactions/). |
| **Pending vs. posted** | A pending transaction has not fully settled; its name or amount can change when posted. | Counting both versions as separate transactions can double-count money. A deduplication policy is **not specified** by Fundo. [Plaid transaction data](https://plaid.com/docs/transactions/transactions-data/). |
| **Business vs. personal** | A flag attached to **each transaction** identifying whether it belongs to business activity. | A personal inflow must not automatically become business revenue. |
| **Internal transfer** | Money moved between related accounts, rather than paid by a customer. | It can look like a deposit without creating new revenue. How to identify related accounts is **not specified**. |

**Illustrative example:** A business receives `amount = -500.00` from a payment processor. That is a $500 deposit and *might* be eligible revenue. A separate `amount = -5,000.00` advance disbursement from a funder is also a deposit but should not be mistaken for sales. A `+75.00` debit to that funder is an outflow that may count toward daily funder payments. Actual labels depend on the implemented, versioned rules; these example descriptions alone do not prove the classification.

## 3. Labels and revenue

The **legacy keyword engine** searches transaction descriptions using keyword lists. If several groups match, an explicit **precedence rule** chooses one winning group. Every transaction also receives a business/personal flag. The challenge names **13 groups**, but does not supply exhaustive definitions, keyword lists, precedence, or a complete revenue-exclusion list. Those V1 choices are recorded in [Business rules](../archive/rules/BUSINESS_RULES.md) and still need implementation tests.

| Group or concept | Plain-English interpretation | Important boundary |
| --- | --- | --- |
| **Revenue / eligible revenue** | For this challenge, a transaction counts only if it is a **business credit** and **no revenue-excluding group** won the classification. | This is an operational feature definition, not a full accounting definition of revenue. Which groups exclude revenue is **not specified**. |
| **Not average monthly revenue** | Legacy group for activity that should not contribute to average monthly revenue (AMR). | The challenge gives the name, not an exhaustive taxonomy. |
| **Revenue verification** | Legacy group associated with checking revenue. | What belongs here, and whether it excludes revenue, is **not specified**. |
| **Auto deposit** | Legacy group for automatic deposits. | “Automatic” does not identify the source or prove revenue eligibility; its priority and treatment are **not specified**. |
| **Internal transfer** | Legacy group for transfers between related accounts. | A transfer can increase observed deposits without increasing sales. |

The other nine named groups describe funding obligations or potential risk signals: `NSFs`, `Overdraft`, `UCC`, `Active advance`, and the five `High risk` groups below. A group label does **not** independently establish that the underlying event really occurred.

**Reviewer vs. code:** The LLM reviews the existing group and business/personal label and may propose a correction with confidence and a brief reason. Code validates that proposal and derives the final revenue flag from transaction direction, business/personal status, and the configured exclusion list. The LLM's revenue answer is not authoritative. [Architecture and failure behavior](../ARCHITECTURE.md#6-rules-model-boundary-and-failure-policy).

## 4. Cash constraints and risk signals

| Term or group | Plain-English interpretation | What not to assume |
| --- | --- | --- |
| **NSF (non-sufficient funds)** | A payment attempt rejected because the account lacked sufficient funds. A bank may charge an NSF fee. | No observed NSF fee does **not** prove no failed payment attempt; fee policies differ. The `NSFs` group is a signal in the data, not a complete incident record. [CFPB](https://www.consumerfinance.gov/data-research/research-reports/vast-majority-of-nsf-fees-have-been-eliminated-saving-consumers-nearly-2-billion-annually/). |
| **Overdraft** | A payment the bank covers despite insufficient funds, potentially leaving a negative balance or using overdraft protection. | It differs from a rejected NSF payment. A fee transaction is not necessarily the underlying incident. [CFPB](https://www.consumerfinance.gov/data-research/research-reports/vast-majority-of-nsf-fees-have-been-eliminated-saving-consumers-nearly-2-billion-annually/). |
| **NSF / overdraft count** | Count of transactions **labeled** with the corresponding group during the observation window. | It need not equal the true number of failed attempts or days with a negative balance. |
| **Active advance** | Legacy group intended to signal existing financing with another funder. | A funder's incoming **disbursement** and outgoing **repayment** have opposite directions. Neither is a customer sale. Exact group membership is **not specified**. |
| **Daily payments to other funders** | An estimate of the daily amount paid out toward other advances. | It reduces the illustrative offer. How to estimate it from a 90- or 61-day history is **not specified**. |
| **UCC** | Uniform Commercial Code. A UCC-1 filing can give public notice of a security interest in collateral. | A `UCC` string in a bank description does not prove a currently active filing or default. The challenge does not define detection rules. [California Secretary of State](https://www.sos.ca.gov/business-programs/ucc/financing-statement). |
| **High risk — gambling** | Possible gambling-related activity. | Treat as a review signal, not a diagnosis; merchant lists and thresholds are **not specified**. |
| **High risk — bankruptcy** | Possible activity related to a formal bankruptcy proceeding. | A word in a transaction does not verify a filing. [U.S. Courts](https://www.uscourts.gov/court-programs/bankruptcy/bankruptcy-basics). |
| **High risk — debt settlement payments** | Possible payments to a service that negotiates debts with creditors. | This is not the same as an ordinary loan payment. [CFPB](https://www.consumerfinance.gov/ask-cfpb/what-is-a-debt-relief-program-and-how-do-i-know-if-i-should-use-one-en-1457/). |
| **High risk — garnishment** | Possible collection from wages or an account through a legal process. | A bank description alone does not establish legal status. [CFPB](https://www.consumerfinance.gov/consumer-tools/debt-collection/answers/key-terms/). |
| **High risk — other** | A residual high-risk group. | Do not use it as an unexplained catch-all; subtypes and criteria are **not specified**. |

## 5. Features and the illustrative offer

A **feature** is a number derived from transaction amounts and labels for one business. The legacy and reviewed labels produce two sets of features, allowing us to show whether a correction would change the funding calculation.

| Feature or metric | What it conveys | Open implementation detail |
| --- | --- | --- |
| **Observation window / coverage** | The challenge uses the **last 90 days**. A 61-day application contains less history. | Counts and totals from 61 days are not directly comparable with 90-day training inputs without a coverage policy or explicit coverage feature. |
| **Average monthly revenue (AMR)** | Average eligible business revenue over the observed period. | For a 90-day window, choose and document a normalization method (for example, calendar months or days divided by a fixed month length); Fundo does not specify one. |
| **Revenue share of deposits** | `eligible revenue ÷ total deposits` for a business. | A loan or transfer can raise deposits without raising revenue. Pending records, duplicates, currencies, and denominator details require a stated policy. |
| **High-risk share of debits** | How much outgoing activity carries a `High risk` label. | A possible definition is `high-risk debit dollars ÷ total debit dollars`, but Fundo does not specify amount vs. count or the exact denominator. |
| **Risk-model features** | Inputs such as AMR, NSF/overdraft counts, funder payments, and high-risk activity. | Changing label rules changes these inputs **even if the risk model itself does not change**. |

The supplied **illustrative offer rule** is:

```text
offer = 1.2 × average monthly revenue − 20 × daily payments to other funders
if NSF count > 5: offer = 0
```

The cutoff is strictly **greater than 5**: five labeled NSFs do not trigger the zero-offer rule; six do. Rounding and whether to floor a negative result at zero are **not specified** by Fundo. Whichever policy is chosen must be documented and applied identically before and after review.

### Why labeling mistakes have different effects

- **False revenue:** A non-sale is counted as eligible revenue. It inflates AMR and tends to **raise** the offer. Missing real revenue tends to lower it. Revenue errors affect the formula through the `1.2 × AMR` term.
- **False active-advance repayment:** An ordinary debit is counted as a payment to another funder. It inflates estimated daily payments and tends to **lower** the offer. Missing a real funder payment tends to raise it. These errors affect the `20 × daily payments` term.
- **NSF threshold error:** Moving a labeled count from 5 to 6 can set the offer to zero, even if only one label changed.
- **Mislabel rate:** The share of transactions labeled incorrectly. The challenge asks about **2%, 5%, and 10%** scenarios, but the dollar effect also depends on *which* transactions and amounts were mislabeled.
- **Dollar error in monthly revenue:** The difference, in money, between calculated and reference AMR for a business. It is more informative for this task than transaction accuracy alone.
- **Hard negative:** A transaction whose legacy label looks suspicious but is actually correct. Flagging it without good reason wastes underwriter time and may lead to a harmful correction.

## How to use this glossary

When investigating a flag, ask in order: **What did the bank record show? What did the keyword engine infer? What did the reviewer propose? What can an underwriter verify?** Keep those four levels separate. If a rule above is marked **not specified**, consult the approved V1 decision in [Business rules](../archive/rules/BUSINESS_RULES.md), implement and test it, and never present it as a Fundo requirement.
