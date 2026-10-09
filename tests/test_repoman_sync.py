import os
import shutil
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "modules" / "scripts" / "repoman-sync.sh"


def _which(tool: str) -> str:
    found = shutil.which(tool)
    assert found is not None, f"{tool} is not on PATH"
    return found


def _host(tmp_path):
    """A host bin dir whose `repoman` logs its arguments."""

    bin_dir = tmp_path / "host-bin"
    bin_dir.mkdir()
    log = tmp_path / "repoman.log"
    repoman = bin_dir / "repoman"
    repoman.write_text(f'#!/usr/bin/env bash\necho "$@" >> {log}\nexit 0\n')
    repoman.chmod(0o755)
    return bin_dir, log


def _run(tmp_path, *, bin_dir=None, lock=False, argv=()):
    if bin_dir is None:
        bin_dir, _ = _host(tmp_path)
    if lock:
        (tmp_path / "repoman.lock").write_text('[repoman]\npackage = "repoman"\nsource = "path:/repo"\n')
    env = dict(os.environ)
    env["DEVENV_ROOT"] = str(tmp_path)
    # Only the tools the script needs, so an ambient `repoman` never leaks in.
    tool_dirs = {str(Path(_which(tool)).parent) for tool in ("bash", "sed", "grep", "dirname")}
    env["PATH"] = ":".join([str(bin_dir), *sorted(tool_dirs)])
    return subprocess.run([_which("bash"), str(SCRIPT), *argv], env=env, capture_output=True, text=True)


def test_sync_runs_the_repoman_on_path(tmp_path):
    bin_dir, log = _host(tmp_path)
    result = _run(tmp_path, bin_dir=bin_dir)
    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == ["install-skills"]


def test_sync_requires_repoman_on_path(tmp_path):
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    result = _run(tmp_path, bin_dir=empty)
    assert result.returncode == 2
    assert "repoman is not on PATH" in result.stderr


def test_sync_rejects_a_consumer_repoman_lock(tmp_path):
    result = _run(tmp_path, lock=True)
    assert result.returncode == 2
    assert "obsolete in a consumer repo" in result.stderr


def test_repo_man_self_may_keep_its_lock(tmp_path):
    bin_dir, log = _host(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "repoman"\n')
    result = _run(tmp_path, bin_dir=bin_dir, lock=True)
    assert result.returncode == 0
    assert log.read_text().splitlines() == ["install-skills"]


def test_unknown_arguments_are_rejected(tmp_path):
    result = _run(tmp_path, argv=("--wat",))
    assert result.returncode == 2
    assert "unknown argument" in result.stderr


def test_the_retired_machine_flag_is_an_unknown_argument(tmp_path):
    result = _run(tmp_path, argv=("--machine",))
    assert result.returncode == 2
    assert "unknown argument" in result.stderr


def test_help_describes_the_script(tmp_path):
    result = _run(tmp_path, argv=("--help",))
    assert result.returncode == 0
    assert "generate the lifecycle router skill" in result.stdout
