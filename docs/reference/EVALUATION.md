# Evaluation notes

Evaluation is separate from the truth-free review CLI. Ground truth is not read or sent to the provider by review code.

```bash
PYTHONPATH=src uv run python -m fundo_reviewer.evaluation --review-dir reports/main --output-dir reports/evaluation
```

This command validates the 2,000-row input/truth/review join and writes `quality_report.json` plus the deterministic sensitivity report. The whole-cohort quality metrics include 1,200 marked `provider_failure` fallbacks that retain the baseline; they are **not** 2,000 model judgments. For model-response-only results, see the measured 799-row subset described in [`../../SOLUTION.md`](../../SOLUTION.md).

The sensitivity analysis is a simulation from authored alternative labels: seed `20261009` samples 40, 100, and 200 labels (2%, 5%, and 10% of 2,000); it is not a model-error estimate. Six targeted cases separately demonstrate false/missed revenue, funder repayment, and NSF cutoff effects. See `reports/evaluation/sensitivity_report.json`.
