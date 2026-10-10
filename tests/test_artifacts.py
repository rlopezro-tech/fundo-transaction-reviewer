import json
import multiprocessing
import queue

import pytest

from fundo_reviewer.artifacts import (
    artifact_set_lock,
    write_bytes_atomic,
    write_json_atomic,
)


def _artifact_lock_waiter(directory, events):
    events.put("waiting")
    with artifact_set_lock(directory):
        events.put("acquired")


def test_artifact_set_lock_serializes_process_writers(tmp_path):
    context = multiprocessing.get_context("spawn")
    events = context.Queue()
    with artifact_set_lock(tmp_path):
        process = context.Process(target=_artifact_lock_waiter, args=(tmp_path, events))
        process.start()
        assert events.get(timeout=10) == "waiting"
        with pytest.raises(queue.Empty):
            events.get(timeout=0.2)
    process.join(timeout=10)
    assert process.exitcode == 0
    assert events.get(timeout=10) == "acquired"


def test_atomic_json_write_replaces_destination_with_formatted_utf8(tmp_path):
    destination = tmp_path / "nested" / "report.json"
    destination.parent.mkdir()
    destination.write_text('{"old": true}\n', encoding="utf-8")

    write_json_atomic(destination, {"label": "café", "count": 2})

    assert json.loads(destination.read_text(encoding="utf-8")) == {"count": 2, "label": "café"}
    assert destination.read_text(encoding="utf-8").endswith("\n")
    assert list(destination.parent.glob("*.tmp")) == []


def test_atomic_bytes_write_preserves_exact_generated_fixture_bytes(tmp_path):
    destination = tmp_path / "transactions" / "input.json"
    payload = b'{"amount": -100.00}\n'

    write_bytes_atomic(destination, payload)

    assert destination.read_bytes() == payload


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
