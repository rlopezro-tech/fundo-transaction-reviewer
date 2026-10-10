import sys

import pytest

from fundo_reviewer import local_pilot
from fundo_reviewer.local_pilot import DEFAULT_MODEL, MODEL_DIGEST, model_identity


def test_local_pilot_model_identity_includes_verified_digest():
    assert model_identity(DEFAULT_MODEL) == f"ollama:{DEFAULT_MODEL}@{MODEL_DIGEST}"


def test_local_pilot_rejects_unpinned_model_before_cache_or_api_use():
    with pytest.raises(ValueError, match="add and verify a digest"):
        model_identity("some-other-model:latest")


def test_local_pilot_cli_reports_local_service_errors_without_traceback(monkeypatch, capsys):
    def fail_run(model):
        raise OSError("private local service details")

    monkeypatch.setattr(local_pilot, "run_pilot", fail_run)
    monkeypatch.setattr(sys, "argv", ["local-pilot"])

    with pytest.raises(SystemExit) as error:
        local_pilot.main()

    assert error.value.code == 1
    stderr = capsys.readouterr().err
    assert "local-pilot: error: local pilot failed (OSError)" in stderr
    assert "private local service details" not in stderr
    assert "Traceback" not in stderr
