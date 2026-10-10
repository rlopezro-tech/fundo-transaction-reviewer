from decimal import Decimal
from pathlib import Path

import pytest

from fundo_reviewer.cache import MODEL_PRICES, pricing_version, usage_derived_cost
from fundo_reviewer.model_catalog import DEFAULT_MODEL, model_spec, registered_models
from fundo_reviewer import provider as provider_module


def test_catalog_is_single_source_for_pricing_and_environment_metadata():
    specs = {spec.model: spec for spec in registered_models()}
    assert specs[DEFAULT_MODEL].provider == "openai"
    assert specs[DEFAULT_MODEL].api_key_env == "OPENAI_API_KEY"
    assert specs["openrouter/openai/gpt-oss-20b"].provider == "openrouter"
    assert specs["openrouter/openai/gpt-oss-20b"].api_key_env == "OPENROUTER_API_KEY"
    assert set(MODEL_PRICES) == set(specs)
    for model, spec in specs.items():
        assert MODEL_PRICES[model] == (
            spec.input_usd_per_million, spec.output_usd_per_million, spec.pricing_version
        )
        assert pricing_version(model) == spec.pricing_version


def test_env_example_documents_every_registered_hosted_provider_key():
    project_root = Path(__file__).resolve().parents[1]
    declared = {
        line.split("=", 1)[0]
        for line in (project_root / "env.example").read_text().splitlines()
        if line and not line.startswith("#") and "=" in line
    }
    required = {spec.api_key_env for spec in registered_models() if spec.api_key_env}
    assert required <= declared


def test_model_costs_remain_unchanged_after_catalog_extraction():
    million_tokens = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
    assert usage_derived_cost(million_tokens, "gpt-6-luna") == Decimal("0.60")
    assert usage_derived_cost(million_tokens, "gpt-5.6-luna") == Decimal("1.40")
    assert usage_derived_cost(million_tokens, "openrouter/openai/gpt-oss-20b") == Decimal("0.12")


def test_ollama_is_explicitly_local_but_unknown_hosted_models_are_rejected():
    local = model_spec("ollama:qwen3.5:9b-q4_K_M@sha256-example")
    assert local.provider == "ollama"
    assert local.api_key_env is None
    assert local.input_usd_per_million == local.output_usd_per_million == Decimal(0)
    with pytest.raises(ValueError, match="approved model catalog"):
        model_spec("unlisted-provider/model")


@pytest.mark.parametrize(
    ("model", "adapter"),
    [("gpt-6-luna", "openai"), ("openrouter/openai/gpt-oss-20b", "openrouter")],
)
def test_provider_factory_routes_by_catalog_not_model_prefix(monkeypatch, model, adapter):
    sentinel = object()
    selected = []
    monkeypatch.setattr(provider_module, "OpenAIProvider", lambda _: selected.append("openai") or sentinel)
    monkeypatch.setattr(provider_module, "OpenRouterProvider", lambda _: selected.append("openrouter") or sentinel)
    assert provider_module.create_provider(model) is sentinel
    assert selected == [adapter]
    with pytest.raises(ValueError, match="no hosted review adapter"):
        provider_module.create_provider("ollama:qwen3.5:9b-q4_K_M@sha256-example")
