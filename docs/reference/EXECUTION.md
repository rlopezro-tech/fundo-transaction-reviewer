# Execution and cost record

## Main cohort

- Dataset: 2,000 synthetic transactions; batch size 80.
- Model: GPT-6 Luna through the OpenAI Responses API.
- Cache: 10 of 25 batches; 799 valid decisions, one invalid response.
- Remainder: 1,200 outcomes marked `provider_failure`; these retain legacy labels and are not model decisions.
- Latest provider responses on both configured OpenAI organizations: 100k TPM exceeded. Reported cooldowns were about 10 hours and 33 hours from the respective attempts. Calls stopped rather than retrying against the distant limit.
- Successful cached usage: `$0.0269049` usage-derived estimate. Not a billing receipt. Rejected calls returned no usage and no model output.
- A no-key replay works for the separate three-record fixture (`reports/new_input/`), but **not yet for the full 2,000-row cohort**, which has 15 missing batches.

## Other model trials

The local Qwen3.5 9B Q4 diagnostic matched baseline labels on 12/20 examples, made no flags, and produced one invalid response; it was not suitable as a replacement. OpenRouter free/low-cost experiments did not produce a reliable end-to-end cache. Earlier v1/v2 prompt and schema pilots are kept as historical experiments; the small development pilots do not establish generalization.

## Resume

When provider quota is available, run from the repository root:

```bash
PYTHONPATH=src uv run --env-file .env python -m fundo_reviewer.cli --mode online --model gpt-6-luna --batch-size 80 --input data/transactions/main_90_days.json --output-dir reports/main
```

The CLI reuses exact cached batches. Keep `.env` out of Git. The ledger conservatively reserves up to the configured $8 operating ceiling; an unresolved reservation is a safety hold, not confirmed spend. Do not raise the $10 challenge limit.
