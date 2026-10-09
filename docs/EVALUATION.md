# Synthetic evaluation and mislabel sensitivity — Ticket 07

Run this **separately** from the truth-free reviewer. The reviewer/provider never imports `evaluation.py`, and no truth field enters review requests or cache keys.

```bash
# Available now: deterministic simulated sensitivity, no API key or reviewer result needed
PYTHONPATH=src uv run python -m fundo_reviewer.evaluation --output-dir reports/evaluation

# After final reviewed cohort exists: also measure quality against synthetic intent truth
PYTHONPATH=src uv run python -m fundo_reviewer.evaluation --review-dir reports/main --output-dir reports/evaluation
```

The first command writes `sensitivity_report.json`; the second additionally writes `quality_report.json`. The latter is **not yet available for the paid full cohort** while its cache is incomplete. A fake-provider test verifies the 2,000-ID join, but fake keeps are not model-quality evidence. Evaluation validates the input hash, review-output hash, manifest counts, exact accepted/truth/review ID sets, baseline labels, proposal consistency, and truth revenue against the same code policy. Missing, duplicate or inconsistent records fail rather than disappearing from a denominator.

`quality_report.json` will contain group, status, joint-label and revenue correctness; true corrections, missed mistakes, false changes, degraded reviews and hard-negative false flags; per-business signed/absolute **AMR dollar error** against independent synthetic scenario intent; and legacy/reviewed/truth features and offers from the same `credit-features-v1` arithmetic. It includes high-dollar examples with synthetic description, labels, review reason and *single-transaction marginal* AMR/daily-payment/offer effect. A marginal effect is a counterfactual on the fixed legacy baseline, not an additive decomposition of all simultaneous changes. Ambiguous descriptions and no-fee-bank metadata remain visible; synthetic intent is not verified real-world truth.

`valid-alternative-sensitivity-v1` starts from the independent synthetic truth labels. Seed **20261009** shuffles the sorted IDs of the **1,033** transactions with an authored valid alternative; the nested first **40, 100, 200** IDs produce exactly 2%, 5%, 10% mislabels relative to all **2,000** accepted transactions (`round(total × rate/100)`). The report records every ID, original/alternative labels, amount and error type. Because only authored-alternative scenarios are eligible, this is **not a realistic error distribution**; the random mix is heavy on missed revenue. Do not compare its aggregate offer movement to expected production losses.

Separate targeted single-label stress cases show false and missed revenue, false and missed `Active advance` repayments, and the **NSF five-to-six / six-to-five** cutoff. They are not extra observations in the random sample. Their signs follow the formula before zero floors or NSF cutoffs: false revenue raises AMR and tends to raise the offer; missed revenue lowers both. A false repayment raises daily funder payments and tends to lower the offer; a missed repayment does the reverse. The offer may have zero marginal movement if already floored at zero or cut off for `NSF_count > 5`. Each case reports actual synthetic USD effects rather than claiming a universal per-error amount.

The v1 individual structured pilot was a weaker/unsuccessful approach: 5 of 20 outputs were rejected for invalid groups or overlong reasons. V2's 20-item batch made three false changes against synthetic **development** truth. The revised v3 prompt made zero false changes and matched 19/20 group/status labels on the same tuned development batch, versus 12/20 for legacy. These numbers justified *provisionally* using v3 for the full run; they do **not** establish held-out or production improvement. The final quality report, including held-out `biz_09`/`biz_10`, must decide whether to retain it and disclose remaining errors in `SOLUTION.md`.
