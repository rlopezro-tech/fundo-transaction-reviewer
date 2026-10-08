# Ticket 02 — Synthetic dataset and independent ground truth

**Status:** Ready for implementation; no dataset or generator is created by writing this ticket.

**Type:** Data foundation

**Depends on:** [Ticket 01 — transaction data contract](01-transaction-data-contract.md)

**Next:** Legacy keyword rules and revenue eligibility (Ticket 03)

## Goal

Create a deterministic, entirely **synthetic** evaluation dataset that follows the Ticket 01 Plaid-shaped input contract. Store transaction records and their correct labels separately so later tickets can measure whether the legacy engine and LLM reviewer improve a funding decision. Plaid is the **format reference**, not an API dependency.

## Scope

1. Generate **10 businesses**, each with about **90 days of explicit account coverage**, and approximately 2,000 transactions in total. Use the approved seed `20261008` and `as_of` date `2026-10-08`; fix the generator version and output ordering so regeneration is byte-for-byte reproducible.
2. Produce transaction records accepted by the Ticket 01 validator, including project business/account IDs, Plaid-style signed amounts, dates, descriptions, optional merchant/category fields, and coverage metadata. Use no real customer data or copied customer descriptions.
3. Build a **scenario inventory** before generation. Include ordinary processor/customer revenue, routine business expenses, internal transfers, personal inflows/outflows, advance disbursements and funder repayments, NSF and overdraft signals, high-risk examples, and examples for each of the challenge's 13 named groups. Include noisy descriptions, punctuation-sensitive keyword misses, and the `SQUARE INC` versus `SQUARE CAPITAL` contrast.
4. Include **hard negatives**: transactions that look suspicious under a shallow text rule but whose initial label should remain correct. Include a business at a bank that does not charge NSF fees; make absence of fees an incomplete observation, not proof of no payment failures. Include at least one counterparty-controlled description containing instruction-like text for later prompt-safety testing.
5. Generate **independent, ID-keyed ground truth** from each scenario's intended economic meaning—not from legacy keyword matches, LLM outputs, or the eventual offer. Record the intended group (or explicit unmatched state), business/personal status, revenue eligibility, scenario ID, and a short rationale. If a case is intentionally ambiguous, mark and explain it rather than pretending the description proves a legal or financial fact.
6. Keep the main evaluation set near 90-day coverage. Generate a **separate 61-day fixture** to test coverage shift; do not mix it into the main 90-day accuracy results without an explicit cohort label.
7. Save transactions under `data/transactions/` and truth under `data/ground_truth/`. Make the generator's normal output path separate from the reviewer input path: truth must never be embedded in transaction records or sent to the LLM. Summarize counts, coverage, amount directions, and scenario distribution without leaking truth into reviewer prompts.

## Deliverables

- A seeded generator in `src/fundo_reviewer/data.py` or a small adjacent module, reusing Ticket 01 validation rather than inventing a second input format.
- Committed synthetic transaction fixture(s) in `data/transactions/`, independent truth fixture(s) in `data/ground_truth/`, and the separate 61-day fixture.
- A concise scenario inventory and regeneration instructions in `docs/` or beside the generator; include the seed, `as_of` date, generator version, and how to verify identical outputs.
- Tests in `tests/` for deterministic regeneration, schema validity, transaction/truth ID alignment, scenario coverage, and truth isolation.

## Acceptance criteria

- [ ] The committed main dataset has about 10 businesses, approximately 90 days of explicit coverage per business, and a couple thousand transactions; the exact counts are reported.
- [ ] Re-running the generator with the documented seed/version produces the same ordered files or hashes.
- [ ] Every generated transaction passes Ticket 01 validation, has a unique stable ID, and has exactly one matching truth record in the separate truth file.
- [ ] Truth comes from scenario intent, not from the legacy engine or reviewer; transaction files, review requests, and cache keys contain no truth-only fields.
- [ ] The scenario inventory and tests cover all 13 named groups plus unmatched/ordinary activity, business and personal activity, processor-versus-funder ambiguity, punctuation misses, hard negatives, and an instruction-like description.
- [ ] The no-fee-bank scenario does not equate zero observed NSF fees with verified zero incidents.
- [ ] A separate 61-day fixture exposes its actual coverage and is not silently treated as a 90-day sample.
- [ ] No real customer data, Plaid API call, or Sandbox credential is needed to generate or validate the fixtures.

## Out of scope

Do **not** build the legacy keyword engine, call an LLM, score reviewer quality, calculate credit features or offers, or integrate Plaid Sandbox here. Those are later tickets. Do not claim model accuracy from the generated truth until the reviewer and evaluation code actually run.

## References

- [Original challenge](../CHALLENGE.md) — synthetic data is allowed; target scale and funder-relevant examples.
- [Ticket 01](01-transaction-data-contract.md) — accepted records, window boundaries, and coverage metadata.
- [Implementation checklist](../IMPLEMENTATION_CHECKLIST.md) — required scenarios and truth separation.
- [Architecture](../ARCHITECTURE.md) — generator, input validation, and evaluation boundaries.
