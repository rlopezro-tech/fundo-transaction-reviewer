# Inputs

- `transactions/` — model/reviewer inputs. The main file contains 2,000 synthetic transactions for ten businesses.
- `ground_truth/` — evaluation-only labels. **Never pass these files to a provider or reviewer.**
- `../tests/fixtures/` — small contract and replay samples used by automated tests.

Regenerate the deterministic synthetic inputs from the repository root with:

```bash
PYTHONPATH=src uv run --locked python -m fundo_reviewer.synthetic --output-root data
```

Generation overwrites the two fixture directories above.
