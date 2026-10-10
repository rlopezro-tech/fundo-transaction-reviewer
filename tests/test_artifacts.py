import json

import pytest

from fundo_reviewer.artifacts import write_json_atomic


def test_atomic_json_write_replaces_destination_with_formatted_utf8(tmp_path):
    destination = tmp_path / "nested" / "report.json"
    destination.parent.mkdir()
    destination.write_text('{"old": true}\n', encoding="utf-8")

    write_json_atomic(destination, {"label": "café", "count": 2})

    assert json.loads(destination.read_text(encoding="utf-8")) == {"count": 2, "label": "café"}
    assert destination.read_text(encoding="utf-8").endswith("\n")
    assert list(destination.parent.glob("*.tmp")) == []


def test_atomic_json_write_preserves_existing_file_when_serialization_fails(tmp_path):
    destination = tmp_path / "report.json"
    destination.write_text('{"old": true}\n', encoding="utf-8")

    with pytest.raises(TypeError):
        write_json_atomic(destination, {"not_json": object()})

    assert destination.read_text(encoding="utf-8") == '{"old": true}\n'
    assert list(tmp_path.iterdir()) == [destination]


def test_atomic_json_write_cleans_temp_file_when_replace_fails(tmp_path, monkeypatch):
    destination = tmp_path / "report.json"
    destination.write_text('{"old": true}\n', encoding="utf-8")

    def fail_replace(_source, _destination):
        raise OSError("simulated replacement failure")

    monkeypatch.setattr("fundo_reviewer.artifacts.os.replace", fail_replace)
    with pytest.raises(OSError, match="simulated replacement failure"):
        write_json_atomic(destination, {"new": True})

    assert destination.read_text(encoding="utf-8") == '{"old": true}\n'
    assert list(tmp_path.iterdir()) == [destination]
