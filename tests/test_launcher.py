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
        "for ((index = 1; index < $#; index++)); do\n"
        '  if [[ "${!index}" == "--env-file" ]]; then\n'
        "    env_index=$((index + 1))\n"
        '    env_file="${!env_index}"\n'
        '    if [[ -f "$env_file" ]]; then\n'
        "      IFS='=' read -r key value < \"$env_file\"\n"
        '      export "$key=$value"\n'
        "    fi\n"
        "  fi\n"
        "done\n"
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
        assert "--locked" in output


def test_launcher_loads_env_only_for_explicit_online_mode(tmp_path):
    output = _run_with_fake_uv(tmp_path, "--mode=online")
    assert "key=sentinel-test-key\n" in output
    assert "--env-file .env" in output
    assert "--locked" in output


def test_launcher_resolves_repository_root_when_called_from_elsewhere(tmp_path):
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        "#!/usr/bin/env bash\n"
        'printf "cwd=%s\\n" "$PWD"\n'
        "[[ -f tests/fixtures/input_90_days.json ]] && echo input=found\n"
    )
    fake_uv.chmod(0o755)

    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    result = subprocess.run(
        [str(ROOT / "scripts" / "run"), "--mode=offline"],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    )

    assert f"cwd={ROOT}\n" in result.stdout
    assert "input=found\n" in result.stdout
