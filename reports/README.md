# Outputs

- `main/` — selected 2,000-row outcome snapshot; 799 valid model results, one invalid response, and 1,200 provider failures. The invalid response and provider failures account for 1,201 degraded outcomes that retain legacy labels. Its manifest records requested model/provider, versioned price assumptions, usage, status counts and output hashes.
- `evaluation/` — synthetic-truth quality and seeded sensitivity reports. Whole-cohort metrics include the fallback rows; consult `SOLUTION.md` for the valid-model-only denominator.
- `new_input/` — small, complete three-row example, replayable without an API key from `cache/new_input.jsonl`.
- `experiments/` — prior prompt/provider pilots and unsuccessful attempts; not final cohort evidence.

Run outputs are reproducible only when the corresponding exact cache is complete. The main cohort cache is still partial.
