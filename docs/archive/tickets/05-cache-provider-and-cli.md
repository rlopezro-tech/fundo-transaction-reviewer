# Ticket 05 — Provider integration, cache, budget, and CLI replay

**Status:** Implementation committed; partial paid cache now contains 800/2,000 `gpt-6-luna` rows (799 valid, one invalid), but the full-cohort cache and no-key replay remain blocked by the organization's 100k TPM limit. Do not treat this ticket as accepted until the remaining 1,200 rows and replay gates pass.

**Type:** Reproducible execution

**Depends on:** [Ticket 04 — LLM label reviewer](04-llm-label-reviewer.md)

**Next:** Credit features and offer calculation (Ticket 06)

## Goal

Make the review pipeline runnable from a clean checkout and **replayable without an API key**. The committed response cache, explicit execution modes, and pre-call budget guard must make thousands of transaction reviews reproducible while keeping actual LLM spend below **US$10**.

## Scope

1. Integrate a configurable model/provider through Ticket 04's interface. Keep credentials in an environment variable, never in source, fixtures, cache, reports, or Git. Verify the chosen model, structured-output support, and current pricing before the first paid run; record exact model identifier and pricing assumption.
2. Define a canonical cache key from every reviewer-visible normalized field, the legacy label and ruleset version, model ID, prompt version, response schema version, and relevant review-policy version. A changed input or version must cause a miss. Keep ground truth out of both the request and key.
3. Store validated response data plus raw provider response, usage, cost metadata, and status under `cache/`. Validate cache integrity and request-key correspondence before replay. Commit the responses needed to reproduce the submitted demonstration.
4. Provide distinct **offline** and **online** behavior. Offline mode never loads a key or calls the provider and fails visibly on a missing/corrupt cache entry. Online mode reads cache hits first, fills misses only, bounds retries, and retains the legacy label with explicit degraded status if a provider request fails or is refused.
5. Enforce a pre-call **spend ceiling** using a conservative token/cost estimate and stop before a call could exceed the configured budget. Track actual provider usage and spend separately from estimates, including which requests were cache hits. Never call the full dataset before estimating cost with a small pilot.
6. Build a single CLI entry point accepting the Ticket 01 JSON envelope path (including `as_of` and account coverage), mode, and output directory. It must validate/normalize input, run legacy labels, review every transaction, and emit stable transaction-level outcomes and a run manifest. It must accept a small new Plaid-shaped input **without ground truth**.
7. Keep output ordering deterministic. The manifest should record input hash, coverage, data/rules/model/prompt/schema/flag-policy versions, cache mode, review counts, degraded counts, and usage/cost. Tickets 06–08 may add feature, offer, and evaluation artifacts to this CLI without changing its core contract.

## Deliverables

- Provider adapter, `src/fundo_reviewer/cache.py`, and `src/fundo_reviewer/cli.py` (or equivalent small module boundaries).
- A documented command shape for online cache filling and offline replay, with no-key offline mode.
- A small measured model/prompt pilot and cost estimate before full execution; commit the resulting full-run cache only if within budget.
- Tests for cache hit/miss/corruption/invalidation, no-key replay, provider failure, budget ceiling, deterministic outputs, and a new-file CLI path.

## Acceptance criteria

- [ ] A clean-checkout command reviews every transaction in the committed synthetic input and writes deterministic outcomes; the CLI also accepts a small new truth-free file.
- [ ] With network/provider access disabled and no API key, offline mode reproduces the committed outcomes from cache without a call; a missing/corrupt entry fails explicitly.
- [ ] Modifying a reviewer-visible field, legacy label/ruleset, model, prompt, schema, or flag policy invalidates the affected cache key.
- [ ] Online failure/refusal is recorded as degraded with the legacy label retained; it is not misreported as a valid cache miss or model `keep` decision.
- [ ] Pre-call budget tests block an unsafe request, and measured total actual LLM spend remains **below US$10**; usage and pricing assumptions are reported separately.
- [ ] Cache and reports contain no secret or ground-truth leakage, and repeated offline runs have stable ordered output hashes.
- [ ] Model and prompt choice remains provisional until the quality/error analysis in Ticket 07; experiments and unsuccessful attempts are retained for `SOLUTION.md`.

## Out of scope

Do **not** calculate the full credit report or claim reviewer improvement in this ticket. Plaid API/Sandbox, a web UI, database, deployment service, and agent framework remain outside v1.

## References

- [Original challenge](../../CHALLENGE.md) — one command, committed response cache, no-key replay, and US$10 cap.
- [Ticket 04](04-llm-label-reviewer.md) — review request, validated response, and online failure policy.
- [Architecture](../../ARCHITECTURE.md) — canonical keys, replay modes, and run manifest.
- [Implementation checklist](../IMPLEMENTATION_CHECKLIST.md) — delivery acceptance and cost evidence.
