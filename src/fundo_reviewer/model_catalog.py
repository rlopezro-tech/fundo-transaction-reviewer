"""Approved model/provider metadata shared by routing and spend controls."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

DEFAULT_MODEL = "gpt-6-luna"


@dataclass(frozen=True, slots=True)
class ModelSpec:
    model: str
    provider: str
    api_key_env: str | None
    input_usd_per_million: Decimal
    output_usd_per_million: Decimal
    pricing_version: str
    provider_model: str | None = None
    response_format: Literal["json_schema", "json_object"] = "json_schema"


_MODELS = {
    spec.model: spec
    for spec in (
        ModelSpec(
            DEFAULT_MODEL,
            "openai",
            "OPENAI_API_KEY",
            Decimal("0.10"),
            Decimal("0.50"),
            "gpt-6-luna-standard-2026-10-08",
        ),
        ModelSpec(
            "gpt-5.6-luna",
            "openai",
            "OPENAI_API_KEY",
            Decimal("0.20"),
            Decimal("1.20"),
            "gpt-5.6-luna-standard-2026-10-09",
        ),
        ModelSpec(
            "openrouter/free",
            "openrouter",
            "OPENROUTER_API_KEY",
            Decimal(0),
            Decimal(0),
            "openrouter-free-model-router-2026-10-09",
            provider_model="openrouter/free",
        ),
        ModelSpec(
            "openrouter/openai/gpt-oss-20b:free",
            "openrouter",
            "OPENROUTER_API_KEY",
            Decimal(0),
            Decimal(0),
            "openrouter-gpt-oss-20b-free-2026-10-09",
            provider_model="openai/gpt-oss-20b:free",
        ),
        ModelSpec(
            "openrouter/google/gemma-4-26b-a4b-it:free",
            "openrouter",
            "OPENROUTER_API_KEY",
            Decimal(0),
            Decimal(0),
            "openrouter-gemma-4-26b-a4b-it-free-2026-10-09",
            provider_model="google/gemma-4-26b-a4b-it:free",
            response_format="json_object",
        ),
        ModelSpec(
            "openrouter/meta-llama/llama-3.3-70b-instruct:free",
            "openrouter",
            "OPENROUTER_API_KEY",
            Decimal(0),
            Decimal(0),
            "openrouter-llama-3.3-70b-free-2026-10-09",
            provider_model="meta-llama/llama-3.3-70b-instruct:free",
            response_format="json_object",
        ),
        ModelSpec(
            "openrouter/openai/gpt-oss-20b",
            "openrouter",
            "OPENROUTER_API_KEY",
            Decimal("0.02"),
            Decimal("0.10"),
            "openrouter-gpt-oss-20b-standard-2026-10-09",
            provider_model="openai/gpt-oss-20b",
        ),
    )
}


def model_spec(model: str) -> ModelSpec:
    """Return approved metadata; Ollama IDs are local and have no API price."""
    if model.startswith("ollama:"):
        return ModelSpec(
            model, "ollama", None, Decimal(0), Decimal(0), "ollama-local-no-api-cost-v1"
        )
    try:
        return _MODELS[model]
    except KeyError as exc:
        raise ValueError(f"model {model!r} is not in the approved model catalog") from exc


def registered_models() -> tuple[ModelSpec, ...]:
    return tuple(_MODELS.values())
