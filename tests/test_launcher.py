import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run_with_fake_uv(tmp_path: Path, *args: str) -> str:
    project = tmp_path / "project"
    (project / "scripts").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "run", project / "scripts" / "run")
    (project / ".env").write_text("OPENAI_API_KEY=sentinel-test-key\n")

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"${2-}\" == \"--env-file\" && -f \"${3-}\" ]]; then\n"
        "  IFS='=' read -r key value < \"$3\"\n"
        "  export \"$key=$value\"\n"
        "fi\n"
        "printf 'key=%s\\n' \"${OPENAI_API_KEY-}\"\n"
        "printf 'args=%s\\n' \"$*\"\n"
    )
    fake_uv.chmod(0o755)

    environment = os.environ.copy()
    environment.pop("OPENAI_API_KEY", None)
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    result = subprocess.run(
        [str(project / "scripts" / "run"), *args],
        cwd=project,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout


def test_launcher_never_loads_env_for_offline_or_default_mode(tmp_path):
    for args in ((), ("--mode", "offline"), ("--mode=offline",)):
        output = _run_with_fake_uv(tmp_path / str(len(args)), *args)
        assert "key=\n" in output
        assert "--env-file" not in output


def test_launcher_loads_env_only_for_explicit_online_mode(tmp_path):
    output = _run_with_fake_uv(tmp_path, "--mode=online")
    assert "key=sentinel-test-key\n" in output
    assert "--env-file .env" in output
