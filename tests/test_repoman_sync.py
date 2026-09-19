import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "modules" / "scripts" / "repoman-sync.sh"


def _closure(tmp_path, *, manifest=True):
    root = tmp_path / "closure"
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True)
    log = tmp_path / "repoman.log"
    repoman = bin_dir / "repoman"
    repoman.write_text(f'#!/usr/bin/env bash\necho "$@" >> {log}\nexit 0\n')
    repoman.chmod(0o755)
    if manifest:
        manifest_dir = root / "share" / "vendomat"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "toolchain.json").write_text(
            json.dumps(
                {
                    "roster": "core",
                    "python": "3.13",
                    "tools": {
                        "repoman": {
                            "version": "0.9.0",
                            "store": "/nix/store/repoman",
                            "commands": ["repoman"],
                        },
                        "copyroom": {
                            "version": "0.7.7",
                            "store": "/nix/store/copyroom",
                            "commands": ["copyroom"],
                        },
                    },
                }
            )
        )
    return root, log


def _run(tmp_path, *, closure=None, lock=False, argv=()):
    if closure is None:
        closure, _ = _closure(tmp_path)
    if lock:
        (tmp_path / "repoman.lock").write_text('[repoman]\npackage = "repoman"\nsource = "path:/repo"\n')
    env = dict(os.environ)
    env["DEVENV_ROOT"] = str(tmp_path)
    env["REPOMAN_TOOLCHAIN_BIN"] = str(closure / "bin")
    return subprocess.run(["bash", str(SCRIPT), *argv], env=env, capture_output=True, text=True)


def test_store_consumer_runs_verified_repoman(tmp_path):
    closure, log = _closure(tmp_path)
    result = _run(tmp_path, closure=closure)
    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == ["install-skills"]
    assert "shared command closure" in result.stdout
    assert "roster core, python 3.13" in result.stdout


def test_store_consumer_does_not_install_packages(tmp_path):
    result = _run(tmp_path)
    assert result.returncode == 0
    assert "uv" not in result.stdout


def test_store_consumer_requires_repoman_binary(tmp_path):
    closure, _ = _closure(tmp_path)
    (closure / "bin" / "repoman").unlink()
    result = _run(tmp_path, closure=closure)
    assert result.returncode == 2
    assert "has no repoman" in result.stderr


def test_store_consumer_requires_toolchain_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("REPOMAN_TOOLCHAIN_BIN", raising=False)
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env={**os.environ, "DEVENV_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "REPOMAN_TOOLCHAIN_BIN is unset" in result.stderr


def test_store_consumer_warns_when_manifest_is_missing(tmp_path):
    closure, log = _closure(tmp_path, manifest=False)
    result = _run(tmp_path, closure=closure)
    assert result.returncode == 0
    assert "no provenance manifest" in result.stderr
    assert log.read_text().splitlines() == ["install-skills"]


def test_store_consumer_rejects_consumer_repoman_lock(tmp_path):
    result = _run(tmp_path, lock=True)
    assert result.returncode == 2
    assert "obsolete in a consumer repo" in result.stderr


def test_repo_man_self_may_keep_its_lock(tmp_path):
    closure, log = _closure(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "repoman"\n')
    result = _run(tmp_path, closure=closure, lock=True)
    assert result.returncode == 0
    assert log.read_text().splitlines() == ["install-skills"]


def test_machine_mode_is_retired(tmp_path):
    result = _run(tmp_path, argv=("--machine",))
    assert result.returncode == 2
    assert "--machine is retired" in result.stderr


def test_unknown_arguments_are_rejected(tmp_path):
    result = _run(tmp_path, argv=("--wat",))
    assert result.returncode == 2
    assert "unknown argument" in result.stderr


def test_help_describes_store_only_operation(tmp_path):
    result = _run(tmp_path, argv=("--help",))
    assert result.returncode == 0
    assert "verify Vendomat's toolchain closure" in result.stdout
    assert "--machine" not in result.stdout
