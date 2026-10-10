import sys

import pytest

from fundo_reviewer import pilot
from fundo_reviewer.reviewer import FatalReviewError


def test_pilot_cli_reports_provider_quota_errors_without_traceback(monkeypatch, capsys):
    def fail_run(variant, model):
        raise FatalReviewError("OpenAI API credit balance exhausted")

    monkeypatch.setattr(pilot, "run_pilot", fail_run)
    monkeypatch.setattr(sys, "argv", ["fundo-pilot", "--variant", "current"])

    with pytest.raises(SystemExit) as error:
        pilot.main()

    assert error.value.code == 1
    stderr = capsys.readouterr().err
    assert "fundo-pilot: error: OpenAI API credit balance exhausted" in stderr
    assert "Traceback" not in stderr
