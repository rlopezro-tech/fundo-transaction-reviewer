# Fundo Transaction Reviewer

> Ticket 01 input validation is implemented; the reviewer has not been implemented yet.

## Source of truth

- [CHALLENGE.md](docs/CHALLENGE.md) — original Fundo challenge.
- [BUSINESS_RULES.md](docs/rules/BUSINESS_RULES.md) — approved v1 financial and labeling decisions; implementation pending.
- [DEVELOPMENT_RULES.md](docs/rules/DEVELOPMENT_RULES.md) — approved v1 scope, safety, testing, and delivery decisions; implementation pending.
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — high-level design.
- [IMPLEMENTATION_CHECKLIST.md](docs/IMPLEMENTATION_CHECKLIST.md) — v1 implementation and evidence checklist.
- [FINANCIAL_GLOSSARY.md](docs/FINANCIAL_GLOSSARY.md) — plain-English financial glossary for developers.
- [INPUT_CONTRACT.md](docs/INPUT_CONTRACT.md) — implemented Ticket 01 envelope and validation policy.

## Setup and run

The project uses Python 3.12 and `uv`. Dependencies are declared in
`pyproject.toml` and pinned in `uv.lock`. The CLI has **not** been implemented,
so there is no runnable reviewer command yet. After implementation, this section
will contain the single copy-paste run command and the environment variable
needed for new LLM calls.

Ticket 01 data-contract tests can already be run with
`uv run --group dev pytest tests/test_data.py`. They require no API key.

## Reproduce from cache

To be documented after implementation: one command that regenerates all results
from the committed cache without an API key.

## Outputs

To be documented after implementation: generated files and how to inspect flags, metrics, and offer impact.
