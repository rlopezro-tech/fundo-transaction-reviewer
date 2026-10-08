# Ticket 04 — LLM label reviewer and safety boundary

**Status:** Ready for implementation; this ticket does not make model calls.

**Type:** Review logic

**Depends on:** [Ticket 03 — legacy labels and revenue](03-legacy-keyword-labels-and-revenue.md)

**Next:** Provider, cache, and CLI replay (Ticket 05)

## Goal

Build the reviewer that inspects **each existing legacy label** and either keeps it or proposes a semantic correction. It must produce an underwriter-readable flag only when it doubts the legacy result. The model is not allowed to edit transaction facts, compute revenue, or decide an offer.

## Scope

1. Define a versioned prompt and structured response contract containing transaction ID, `keep`/`change`, proposed group or `unmatched`, proposed business/personal flag, confidence, and a short reason. The request must include the existing legacy group/flag and only the transaction fields needed for review. Never include Ticket 02 ground truth.
2. Define a deterministic **flag policy**: which validated `change` proposals become underwriter flags, including any confidence threshold and what happens below it. Record both the raw proposal and the applied decision so the threshold can be audited. A `keep` response is an outcome, not a flag.
3. Treat `name`, `merchant_name`, and other bank descriptions as **untrusted data**. Delimit them in the prompt and explicitly instruct the model not to obey commands inside them. Include the Ticket 02 instruction-like transaction as an adversarial test.
4. Validate the response in code: exact transaction ID, allowed group and flag values, confidence range, `keep`/`change` consistency, and bounded reason length. Reject invented groups, changed amounts/dates/IDs, malformed or incomplete output, and contradictory proposals.
5. Apply a validated correction only to the semantic group and business/personal flag. Recompute revenue using Ticket 03's authoritative code function and the original signed amount. Preserve legacy label, proposed label, final label, reason, confidence, and provenance for later comparison.
6. Define a safe fallback for refused, invalid, incomplete, or unavailable **online** responses: retain the legacy label and record a visible degraded status. A provider outage must not silently appear as model agreement. Offline cache misses have a different policy in Ticket 05.
7. Keep provider access behind a small interface so unit tests use fakes. Select the actual model and finalize the prompt only after a measured, budget-controlled pilot in Ticket 05 and quality review in Ticket 07; do not claim an untested model is good enough.

## Deliverables

- `src/fundo_reviewer/reviewer.py` (or an equally small module) with request/response schemas, prompt builder, validator, flag policy, and final-label application.
- A versioned prompt/schema and short model-versus-code boundary note, including the untrusted-text rule and failure behavior.
- Tests in `tests/` for keep/change, group and business/personal corrections, revenue recomputation, threshold boundaries, invalid output, ID mismatch, provider failure, and prompt-injection text.

## Acceptance criteria

- [ ] A fake-provider run produces exactly one review outcome per legacy-labeled transaction; no transaction is silently skipped or independently relabeled without its legacy result.
- [ ] Each flagged change has a valid proposed group, business/personal flag, code-derived revenue yes/no, confidence, and reason short enough for a quick underwriter review.
- [ ] The model cannot change source transaction fields, revenue arithmetic, feature definitions, or offer logic; tests prove attempts are rejected.
- [ ] Truth-only fields never appear in prompts, proposals, or model-facing context.
- [ ] An instruction embedded in a bank description remains data rather than controlling the review; the test documents the observed behavior rather than assuming the prompt alone guarantees safety.
- [ ] Invalid/refused/incomplete/failed **online** reviews retain legacy labels with explicit degraded status; a valid `keep` result remains distinguishable.
- [ ] Prompt, schema, and flag-policy versions are available for Ticket 05 cache keys and Ticket 08 decision replay.

## Out of scope

Do **not** run the full live dataset without Ticket 05's cache and spend guard; do not calculate credit features or measured reviewer accuracy here. The reviewer is a correction proposal mechanism, not an autonomous funding decision maker.

## References

- [Original challenge](../CHALLENGE.md) — review existing labels, hard negatives, untrusted text, and underwriter-readable reasons.
- [Ticket 02](02-synthetic-dataset-and-ground-truth.md) — adversarial cases and truth isolation.
- [Ticket 03](03-legacy-keyword-labels-and-revenue.md) — input labels and authoritative revenue rule.
- [Implementation checklist](../IMPLEMENTATION_CHECKLIST.md) — reviewer requirements and failure tests.
- [Architecture](../ARCHITECTURE.md) — model/code boundary and provenance.
