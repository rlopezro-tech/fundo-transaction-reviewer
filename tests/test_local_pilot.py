import pytest

from fundo_reviewer.local_pilot import DEFAULT_MODEL, MODEL_DIGEST, model_identity


def test_local_pilot_model_identity_includes_verified_digest():
    assert model_identity(DEFAULT_MODEL) == f"ollama:{DEFAULT_MODEL}@{MODEL_DIGEST}"


def test_local_pilot_rejects_unpinned_model_before_cache_or_api_use():
    with pytest.raises(ValueError, match="add and verify a digest"):
        model_identity("some-other-model:latest")
