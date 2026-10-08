# Ticket 03 — Legacy keyword labels and revenue eligibility

**Status:** Ready for implementation; writing this ticket does not implement the engine.

**Type:** Deterministic labeling

**Depends on:** [Ticket 01 — transaction data contract](01-transaction-data-contract.md), [Ticket 02 — synthetic dataset and ground truth](02-synthetic-dataset-and-ground-truth.md)

**Next:** LLM label reviewer (Ticket 04)

## Goal

Build a small, **deliberately imperfect** keyword engine that assigns one legacy group and a business/personal flag to every normalized transaction. Code—not the LLM—then derives whether that transaction is eligible revenue. The engine is the baseline the reviewer will inspect, not a financial-fact verification system.

## Scope

1. Define versioned keyword lists for **all 13 groups named by Fundo**: `Not average monthly revenue`, `NSFs`, `Overdraft`, `Internal transfer`, `UCC`, `Active advance`, `Auto deposit`, `Revenue verification`, `High risk — gambling`, `High risk — bankruptcy`, `High risk — debt settlement payments`, `High risk — garnishment`, and `High risk — other`. Provide an explicit `unmatched` state when no group wins; it is **not** a fourteenth Fundo group.
2. Document exactly which transaction text fields are searched, their normalization, how keyword boundaries and punctuation are handled, and whether matching is case-sensitive. Keep the engine simple enough to explain live. Preserve the original text and a trace of every matched rule ID.
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

- [ ] All 13 named groups are representable, and every normalized transaction gets exactly one winning group or `unmatched` plus one business/personal flag.
- [ ] The ruleset has a version; output records include that version, winning group, business/personal flag, derived revenue, matched rule IDs, and enough trace to explain precedence.
- [ ] Tests show the same input and ruleset always produce the same labels, regardless of input ordering or incidental map iteration order.
- [ ] Collision tests prove the documented precedence is applied; no-match tests produce `unmatched` without inventing a Fundo category.
- [ ] Punctuation and `SQUARE INC` versus `SQUARE CAPITAL` cases expose and document at least one baseline error without corrupting the independent ground truth.
- [ ] Revenue tests prove that positive Plaid amounts, personal credits, internal transfers, and funder disbursements cannot be eligible revenue under the chosen exclusion policy; ordinary eligible business credits can be.
- [ ] The exclusion treatment of `Auto deposit` and `Revenue verification` is explicitly documented and tested.
- [ ] No Plaid API call, LLM call, feature calculation, or offer calculation is required for this ticket.

## Out of scope

Do **not** correct labels with an LLM, optimize keyword rules until the synthetic truth is perfectly matched, calculate credit metrics, or report model accuracy here. Those are later tickets. The synthetic truth remains a separate evaluation artifact, never an input to the legacy labeling function.

## References

- [Original challenge](../CHALLENGE.md) — 13 groups, keyword precedence, business/personal flag, and revenue condition.
- [Ticket 01](01-transaction-data-contract.md) — normalized transaction input and Plaid sign convention.
- [Ticket 02](02-synthetic-dataset-and-ground-truth.md) — synthetic cases and independent evaluation truth.
- [Implementation checklist](../IMPLEMENTATION_CHECKLIST.md) — open rule-policy decisions and required tests.
- [Architecture](../ARCHITECTURE.md) — legacy and revenue module boundaries.
