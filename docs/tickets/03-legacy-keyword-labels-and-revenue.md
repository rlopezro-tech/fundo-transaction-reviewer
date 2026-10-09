# Ticket 03 — Legacy keyword labels and revenue eligibility

**Status:** Implemented and verified. This is the deliberately imperfect `legacy-v1` baseline, not a reviewer or accuracy report.

**Type:** Deterministic labeling

**Depends on:** [Ticket 01 — transaction data contract](01-transaction-data-contract.md), [Ticket 02 — synthetic dataset and ground truth](02-synthetic-dataset-and-ground-truth.md)

**Next:** LLM label reviewer (Ticket 04)

## Goal

Build a small, **deliberately imperfect** keyword engine that assigns one legacy group and a business/personal flag to every normalized transaction. Code—not the LLM—then derives whether that transaction is eligible revenue. The engine is the baseline the reviewer will inspect, not a financial-fact verification system.

## Scope

1. Define versioned keyword lists for **all 13 groups named by Fundo**: `Not average monthly revenue`, `NSFs`, `Overdraft`, `Internal transfer`, `UCC`, `Active advance`, `Auto deposit`, `Revenue verification`, `High risk — gambling`, `High risk — bankruptcy`, `High risk — debt settlement payments`, `High risk — garnishment`, and `High risk — other`. Provide an explicit `unmatched` state when no group wins; it is **not** a fourteenth Fundo group.
2. Implement the approved literal keyword list, text fields, Unicode/case/whitespace normalization and punctuation-preserving substring behavior in [BUSINESS_RULES.md](../rules/BUSINESS_RULES.md). Keep the engine simple enough to explain live. Preserve the original text and a trace of every matched rule ID.
3. Define one explicit, stable **precedence order** for multiple matches. Output the winning group and the full match trace so a reviewer or developer can see why a group won. Do not resolve ties by incidental dictionary order.
4. Define a reproducible rule for the **business/personal flag** on every transaction, including an explicit default or fallback when keywords are inconclusive. Document the expected errors of this deliberately simple baseline.
5. Define the precise **revenue-excluding group set** as a project policy. Fundo requires `business credit AND no excluding group`, but does not specify that set. Explicitly decide how `Auto deposit` and `Revenue verification` affect eligibility rather than assuming their names answer the question.
6. Implement one authoritative revenue function: eligible only for a **business inflow** (`amount < 0` in Plaid Transactions) whose winning group is not in the exclusion set. A deposit or funder disbursement must not become revenue merely because money entered the account. Use the same function for later reviewed-label calculations.
7. Run the engine deterministically over Ticket 02 transactions and keep the legacy output distinct from synthetic ground truth. Include intentional, documented failure examples—such as processor-versus-funder confusion or punctuation-sensitive misses—so the LLM reviewer has meaningful errors to find. Do not secretly tune rules against the truth file until all errors disappear.

## Deliverables

- A versioned ruleset and implementation in `src/fundo_reviewer/legacy.py` (or an equally small module), including keyword lists, normalization, rule IDs, and precedence.
- A single revenue-eligibility function in `src/fundo_reviewer/revenue.py`, shared by legacy and later reviewed labels.
- A concise policy note in `docs/` or alongside the ruleset stating the business/personal rule, unmatched behavior, exclusion set, and which details are **our choices**, not Fundo requirements.
- Tests in `tests/` for taxonomy coverage, every transaction receiving one outcome, deterministic matching, collisions, punctuation, sign direction, personal credits, transfers, funder disbursements, and ordinary processor deposits.

## Acceptance criteria

- [x] All 13 groups are representable; `label_transactions()` assigns one group or `unmatched` and one status to all 2,000 main records. **Evidence:** `tests/test_legacy.py`.
- [x] `LegacyLabel` carries `legacy-v1`, group, status, derived revenue, matched rule IDs, field/keyword/rank trace, and personal-marker IDs. **Evidence:** `src/fundo_reviewer/legacy.py`.
- [x] Ordering is stable across reversed transaction input and reversed rule tuple; fixed precedence is independent of map iteration. **Evidence:** deterministic/collision tests.
- [x] Collision and no-match tests verify explicit precedence and `unmatched` behavior. **Evidence:** `tests/test_legacy.py`.
- [x] `SQUARE INC` versus `SQUARE CAPITAL`, `UCC 1`, `OD-FEE`, and the `nsf`/`transfer` collision expose known v1 errors without modifying truth. **Evidence:** [policy note](../LEGACY_POLICY.md), tests.
- [x] One `revenue-v1` function rejects positive amounts, personal credits, transfer/funder groups, and allows eligible business credits. **Evidence:** `src/fundo_reviewer/revenue.py`, tests.
- [x] `Auto deposit` and `Revenue verification` are non-excluding by name; this is documented and tested. **Evidence:** [policy note](../LEGACY_POLICY.md), tests.
- [x] The implementation uses no Plaid API, LLM, feature or offer calculation.

## Out of scope

Do **not** correct labels with an LLM, optimize keyword rules until the synthetic truth is perfectly matched, calculate credit metrics, or report model accuracy here. Those are later tickets. The synthetic truth remains a separate evaluation artifact, never an input to the legacy labeling function.

## References

- [Original challenge](../CHALLENGE.md) — 13 groups, keyword precedence, business/personal flag, and revenue condition.
- [Ticket 01](01-transaction-data-contract.md) — normalized transaction input and Plaid sign convention.
- [Ticket 02](02-synthetic-dataset-and-ground-truth.md) — synthetic cases and independent evaluation truth.
- [Implementation checklist](../IMPLEMENTATION_CHECKLIST.md) — open rule-policy decisions and required tests.
- [Architecture](../ARCHITECTURE.md) — legacy and revenue module boundaries.
