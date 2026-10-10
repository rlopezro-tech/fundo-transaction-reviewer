# Fundo Transaction Reviewer — final submission

## Status

Implementation, synthetic-data tests, credit calculations, and sensitivity simulation are complete. **The paid model evaluation is partial:** out of 2,000 accepted transactions, 799 received valid model decisions, one response was invalid, and 1,200 retained the keyword baseline after provider failures. Both configured OpenAI organizations returned a 100k tokens-per-minute (TPM) limit error. The full cache-only replay is therefore not reproducible yet. The outcome snapshot is in `reports/main/`; measured and simulated results are distinguished below. All data is synthetic; no output is a real funding decision.

## What was built

The input is a deterministic, Plaid-shaped dataset of 10 businesses and 2,000 transactions over 90 days, plus a separate 61-day fixture. Truth labels are stored separately and never sent to the reviewer. Plaid's sign convention is preserved (negative inflow, positive outflow).

The 13-group keyword engine intentionally includes noisy descriptions and errors. The reviewer sees the baseline label and a sanitized transaction; it can propose only keep/change, group, business/personal, confidence, and a short reason. Code validates the response, derives revenue, computes features, and applies the offer rule. A valid change is a review flag, not an automatic lending action. Invalid, missing, refused, or unavailable responses retain the baseline and are marked degraded. Bank descriptions are untrusted data; the model has no tools.

## Results and limitations

**Model-reviewed rows (measured against synthetic scenario intent, not production truth):** the 799 valid model responses included 603 keeps and 196 changes. Among those rows, joint group/status agreement was **668/799 (83.6%)**, versus **533/799 (66.7%)** for the baseline on the same subset. The 196 flags comprised 135 corrections to the authored label and 61 changes that remained wrong. One additional response was invalid. These are not a representative full-cohort estimate: the reviewed subset is incomplete and concentrated in the first five businesses; `biz_09` and `biz_10` were not reviewed by the model.

**Whole-cohort report:** `reports/evaluation/quality_report.json` evaluates all 2,000 outcomes, but 1,200 of them are degraded baseline fallbacks. It reports 1,499/2,000 joint matches for the final outcome set and aggregate absolute AMR error of **$90,146.95**, versus **$153,343.33** for the baseline. These figures mix model output with fallbacks and must not be presented as full-cohort LLM performance. The per-business table and examples are in the report. There were 278 authored hard negatives; the report records three hard-negative false flags. Synthetic scenario intent is an imperfect proxy, not adjudicated financial truth.

The evaluator's 2%/5%/10% cases are **simulations**, not observed model error rates. They alter 40/100/200 of 2,000 truth labels from a fixed pool of 1,033 authored alternatives. Targeted examples show why error type matters: a false $28,743.36 revenue label raises the illustrative offer by $11,497.34; a $1,985.34 false advance repayment lowers it by $441.19; moving NSF count from five to six can zero an otherwise $45,160.26 offer. Full details are in `reports/evaluation/sensitivity_report.json`.

**Provider and cost:** GPT-6 Luna was used for the main cached responses. Those 799 valid decisions have **$0.0269049 usage-derived estimated cost**. Across the paid OpenAI and OpenRouter ledgers, recorded successful usage totals **$0.0491458**; unresolved reservations total about **$0.63675024** and are conservative holds, not confirmed charges. Neither number is a billing receipt. The latest retries with `OPENAI_API_KEY` and `OPENAI_API_KEY_TEMP` failed before returning model output due to organization-level TPM limits (the service reported waits of about 10 h and 33 h). No successful usage is recorded for those retries. Local Qwen3.5 9B Q4 matched the baseline on 12/20 pilot rows, made no flags, and had one invalid response, so it was not a replacement. The attempted free OpenRouter models did not provide a reliable schema-compliant alternative. Recorded successful usage is below the challenge's **$10** ceiling; exact billed spend was not independently verified.

The local suite passes **116 tests**. The main response cache contains 10/25 batches; a complete no-key 2,000-row replay remains unverified and will fail explicitly on the 15 missing batches. The committed report is a complete outcome snapshot only because missing model calls used a marked legacy fallback; it is not a complete model run.

## Credit questions

**No-fee bank, zero NSF fees:** Zero observed NSF fees are not evidence that no payments failed. The feature is censored by bank fee policy. Keep fee observability and coverage as separate inputs, use returned-payment signals only with provenance, and avoid treating an unobservable zero as a favorable risk signal.

**61 days when the risk model expects 90:** Normalizing revenue to 30 days does not restore the missing NSF opportunities, seasonality, or stability evidence. Expose observed coverage days, monitor their distribution, and route short-history cases to a separately validated policy or human review instead of silently passing 61-day counts as 90-day features.

## Production proposal (not implemented)

Run the versioned reviewer in shadow beside the frozen keyword engine on an underwriter-annotated sample spanning banks and coverage lengths. Do not let it change live decisions. Measure AMR dollar error, harmful changes, hard-negative false flags, outage/schema failure rates, and underwriter burden. Promote only after risk and operations sign-off against pre-registered quality thresholds; require a human to approve any decision-changing correction.

Monitor input coverage, label and feature distributions, and offer distributions by bank and rules/model/prompt version. Compare every keyword or model update with a frozen canary set and investigate unexplained shifts before release. For historical reproducibility, retain an immutable input snapshot/hash, coverage, baseline and reviewed labels, raw response and cache provenance, all calculation/model versions, derived features, offer, actual decision, and underwriter action. Underwriter corrections enter a versioned evaluation set; an override is not automatically ground truth.

## Tools and scope

Tools: Python 3.12, `uv`, Pydantic, the OpenAI Python SDK, pytest, Git, official Plaid/OpenAI documentation, and **OpenAI Codex** as an AI coding/research assistant. AI-assisted code and interpretations were checked with source review, deterministic fixture generation, boundary/fake-provider tests, and the measured pilot. No real customer data, Plaid API, production service, database, or live funding automation was used.
