import json
import types

import pytest

import repoman.checks as checks
from repoman.checks import run_self_check, self_check_exit
from repoman.registry import REGISTRY


def _names(result):
    return {item.name: item for item in result}


_PYPROJECT_TESTEE = """[project]
name = "x"
version = "0.0.0"
requires-python = ">=3.13"
dependencies = []

[dependency-groups]
dev = ["testee"]
"""


@pytest.fixture
def toolchain(tmp_path, monkeypatch):
    root = tmp_path / "toolchain"
    bin_dir = root / "bin"
    manifest_dir = root / "share" / "vendomat"
    bin_dir.mkdir(parents=True)
    manifest_dir.mkdir(parents=True)
    for command in ("repoman", "copyroom", "gitman", "docman"):
        (bin_dir / command).write_text("")
    manifest = {
        "python": "3.13",
        "roster": "core",
        "tools": {
            "repoman": {"version": "0.9.0", "store": "/nix/store/repoman"},
            "copyroom": {"version": "0.7.7", "store": "/nix/store/copyroom"},
            "gitman": {"version": "0.6.2", "store": "/nix/store/gitman"},
            "docman": {"version": "0.4.0", "store": "/nix/store/docman"},
        },
    }
    manifest_path = manifest_dir / "toolchain.json"
    manifest_path.write_text(json.dumps(manifest))
    monkeypatch.setenv("REPOMAN_TOOLCHAIN_BIN", str(bin_dir))
    monkeypatch.delenv("REPOMAN_TOOLCHAIN_MANIFEST", raising=False)
    monkeypatch.delenv("DEVENV_STATE", raising=False)
    monkeypatch.delenv("DEVENV_ROOT", raising=False)
    monkeypatch.setattr(
        checks.shutil,
        "which",
        lambda command: str(bin_dir / command) if (bin_dir / command).exists() else None,
    )

    def write(data):
        manifest_path.write_text(json.dumps(data) if isinstance(data, dict) else data)

    return types.SimpleNamespace(root=root, bin=bin_dir, manifest=manifest_path, write=write)


@pytest.fixture
def consumer_venv(tmp_path, monkeypatch):
    bin_dir = tmp_path / ".devenv" / "state" / "venv" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "testee").write_text("")
    monkeypatch.setenv("DEVENV_STATE", str(tmp_path / ".devenv" / "state"))
    return bin_dir


def test_missing_toolchain_store_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("REPOMAN_TOOLCHAIN_BIN", raising=False)
    result = run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills")
    store = _names(result)["toolchain:store"]
    assert store.level == "fail"
    assert "REPOMAN_TOOLCHAIN_BIN" in store.detail
    assert self_check_exit(result) == 2


def test_store_manifest_is_required(toolchain):
    toolchain.manifest.unlink()
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    store = _names(result)["toolchain:store"]
    assert store.level == "fail"
    assert "toolchain.json" in store.detail


def test_invalid_store_manifest_is_reported(toolchain):
    toolchain.manifest.write_text("{not json")
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    assert _names(result)["toolchain:store"].level == "fail"


def test_missing_self_entry_fails(toolchain):
    toolchain.write({"python": "3.13", "roster": "core", "tools": {"gitman": {"version": "x"}}})
    assert _names(run_self_check([REGISTRY["git"]], ".", ".claude/skills"))["toolchain:self"].level == "fail"


def test_store_manager_rows_are_present(toolchain):
    names = _names(run_self_check([REGISTRY["git"], REGISTRY["doc"]], ".", ".claude/skills"))
    assert names["lock:git"].level == "ok"
    assert names["version:git"].detail == "gitman 0.6.2 (Nix store)"
    assert names["lock:doc"].level == "ok"
    assert names["installed:git"].level == "ok"


def test_selected_manager_absent_from_store_manifest_fails(toolchain):
    toolchain.write(
        {
            "python": "3.13",
            "roster": "core",
            "tools": {"repoman": {"version": "0.9.0", "store": "/nix/store/repoman"}},
        }
    )
    names = _names(run_self_check([REGISTRY["git"]], ".", ".claude/skills"))
    assert names["lock:git"].level == "fail"
    assert "store manifest" in names["lock:git"].detail


def test_uninstalled_toolchain_manager_fails(toolchain):
    (toolchain.bin / "gitman").unlink()
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    installed = _names(result)["installed:git"]
    assert installed.level == "fail" and "repoman-sync" in installed.detail


def test_installed_checks_exact_store_binary(toolchain):
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    assert _names(result)["installed:git"].detail == str(toolchain.bin / "gitman")


def test_installed_warns_when_path_shadows_store(toolchain, tmp_path, monkeypatch):
    stale = tmp_path / "stale" / "gitman"
    stale.parent.mkdir()
    stale.write_text("")
    monkeypatch.setattr(checks.shutil, "which", lambda command: str(stale) if command == "gitman" else None)
    installed = _names(run_self_check([REGISTRY["git"]], ".", ".claude/skills"))["installed:git"]
    assert installed.level == "warn"
    assert str(stale) in installed.detail and str(toolchain.bin / "gitman") in installed.detail


def test_store_and_consumer_binary_resolution(toolchain, consumer_venv, tmp_path):
    assert checks.manager_binary(REGISTRY["git"]) == toolchain.bin / "gitman"
    assert checks.manager_binary(REGISTRY["test"]) == consumer_venv / "testee"


def test_uv_manager_is_declared_in_dependency_group(toolchain, consumer_venv, tmp_path):
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_TESTEE)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["uv:test"].level == "ok"
    assert _names(result)["installed:test"].level == "ok"


def test_uv_manager_not_declared_fails(toolchain, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.0.0"\n')
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["uv:test"].level == "fail"


def test_uv_requirement_normalisation(toolchain, consumer_venv, tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n'
        '[dependency-groups]\ndev = ["TESTEE[all]>=0.3 ; python_version>\\"3.12\\""]\n'
    )
    assert _names(run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills"))["uv:test"].level == "ok"


def test_unparseable_pyproject_is_reported(toolchain, tmp_path):
    (tmp_path / "pyproject.toml").write_text("this is not [ toml")
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["pyproject"].level == "fail"


def test_uv_manager_has_no_store_lock_row(toolchain, tmp_path):
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_TESTEE)
    names = _names(run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills"))
    assert "lock:test" not in names


def test_detect_context_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("REPOMAN_MANAGERS", "")
    assert checks.detect_context(str(tmp_path)).kind == "managed-repo-shell"
    monkeypatch.delenv("REPOMAN_MANAGERS")
    (tmp_path / ".gitman").mkdir()
    assert checks.detect_context(str(tmp_path)).kind == "managed-repo-bare-shell"


def test_devenv_vars_alone_are_not_a_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVENV_ROOT", str(tmp_path))
    monkeypatch.setenv("DEVENV_STATE", str(tmp_path / "state"))
    monkeypatch.setenv("REPOMAN_TOOLCHAIN_BIN", str(tmp_path / "toolchain"))
    assert checks.detect_context(str(tmp_path)).kind == "not-a-repo"


def test_approach_b_input_warning_is_nonfatal(toolchain, monkeypatch):
    monkeypatch.delenv("REPOMAN_PROVISIONED_DOC", raising=False)
    result = run_self_check([REGISTRY["doc"]], ".", ".claude/skills")
    assert _names(result)["provisioned:doc"].level == "warn"
    assert self_check_exit(result) == 0


def test_entrypoint_skill_missing_warns(toolchain, tmp_path):
    result = run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills")
    assert _names(result)["skill:entrypoint"].level == "warn"


def test_sub_skill_deferral_is_checked(toolchain, tmp_path):
    sub = tmp_path / ".claude/skills" / "gitman" / "SKILL.md"
    sub.parent.mkdir(parents=True)
    sub.write_text("No deferral")
    assert (
        _names(run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills"))["skill:git:defers"].level == "warn"
    )
    sub.write_text("See the repoman skill for ordering.")
    assert _names(run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills"))["skill:git:defers"].level == "ok"
