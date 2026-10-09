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
def host(tmp_path, monkeypatch):
    """A fake host profile: a bin dir with the host commands, found through PATH."""

    bin_dir = tmp_path / "host-bin"
    bin_dir.mkdir()
    for command in ("repoman", "copyroom", "gitman", "docman"):
        (bin_dir / command).write_text("")
    monkeypatch.delenv("DEVENV_STATE", raising=False)
    monkeypatch.delenv("DEVENV_ROOT", raising=False)
    monkeypatch.setattr(
        checks.shutil,
        "which",
        lambda command: str(bin_dir / command) if (bin_dir / command).exists() else None,
    )
    return types.SimpleNamespace(bin=bin_dir)


@pytest.fixture
def consumer_venv(tmp_path, monkeypatch):
    bin_dir = tmp_path / ".devenv" / "state" / "venv" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "testee").write_text("")
    monkeypatch.setenv("DEVENV_STATE", str(tmp_path / ".devenv" / "state"))
    return bin_dir


def test_host_manager_on_path_is_installed(host):
    names = _names(run_self_check([REGISTRY["git"], REGISTRY["doc"]], ".", ".claude/skills"))
    assert names["installed:git"].level == "ok"
    assert names["installed:git"].detail == str(host.bin / "gitman")
    assert names["installed:doc"].level == "ok"


def test_self_check_reads_no_vendomat_closure(host):
    names = _names(run_self_check([REGISTRY["git"]], ".", ".claude/skills"))
    assert not {n for n in names if n.startswith(("toolchain:", "lock:", "version:"))}


def test_host_manager_missing_from_path_fails(host):
    (host.bin / "gitman").unlink()
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    installed = _names(result)["installed:git"]
    assert installed.level == "fail" and "not on PATH" in installed.detail
    assert self_check_exit(result) == 1


def test_binary_resolution(host, consumer_venv):
    assert checks.manager_binary(REGISTRY["git"]) == host.bin / "gitman"
    assert checks.manager_binary(REGISTRY["test"]) == consumer_venv / "testee"


def test_uv_manager_warns_when_path_shadows_the_venv(host, consumer_venv, tmp_path, monkeypatch):
    stale = tmp_path / "stale" / "testee"
    stale.parent.mkdir()
    stale.write_text("")
    monkeypatch.setattr(checks.shutil, "which", lambda command: str(stale) if command == "testee" else None)
    installed = _names(run_self_check([REGISTRY["test"]], ".", ".claude/skills"))["installed:test"]
    assert installed.level == "warn"
    assert str(stale) in installed.detail and str(consumer_venv / "testee") in installed.detail


def test_gitman_interface_check_needs_the_work_only_binary_and_jj_0_46(host, tmp_path, monkeypatch):
    gitman = host.bin / "gitman"
    gitman.write_text('#!/bin/sh\nprintf "usage: gitman [-h] {work} ...\\n"\n')
    gitman.chmod(0o755)
    jj = tmp_path / "jj-bin" / "jj"
    jj.parent.mkdir()
    jj.write_text('#!/bin/sh\nprintf "jj 0.46.0\\n"\n')
    jj.chmod(0o755)
    monkeypatch.setenv("PATH", f"{jj.parent}:{host.bin}")

    names = _names(run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills"))
    assert names["interface:git"].level == "ok"

    gitman.write_text('#!/bin/sh\nprintf "usage: gitman [-h] {start,status} ...\\n"\n')
    names = _names(run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills"))
    assert names["interface:git"].level == "fail"

    gitman.write_text('#!/bin/sh\nprintf "usage: gitman [-h] {work} ...\\n"\n')
    jj.write_text('#!/bin/sh\nprintf "jj 0.45.0\\n"\n')
    names = _names(run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills"))
    assert names["interface:git"].level == "fail"


def test_uv_manager_is_declared_in_dependency_group(host, consumer_venv, tmp_path):
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_TESTEE)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["uv:test"].level == "ok"
    assert _names(result)["installed:test"].level == "ok"


def test_uv_manager_not_declared_fails(host, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.0.0"\n')
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["uv:test"].level == "fail"


def test_uv_requirement_normalisation(host, consumer_venv, tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n'
        '[dependency-groups]\ndev = ["TESTEE[all]>=0.3 ; python_version>\\"3.12\\""]\n'
    )
    assert _names(run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills"))["uv:test"].level == "ok"


def test_unparseable_pyproject_is_reported(host, tmp_path):
    (tmp_path / "pyproject.toml").write_text("this is not [ toml")
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["pyproject"].level == "fail"


def test_uv_manager_has_no_host_rows(host, tmp_path):
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_TESTEE)
    names = _names(run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills"))
    assert "lock:test" not in names


def test_detect_context_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("REPOMAN_MANAGERS", "")
    assert checks.detect_context(str(tmp_path)).kind == "managed-repo-shell"
    monkeypatch.delenv("REPOMAN_MANAGERS")
    (tmp_path / ".repoman").mkdir()
    (tmp_path / ".repoman" / "project.toml").write_text("")
    assert checks.detect_context(str(tmp_path)).kind == "managed-repo-bare-shell"


def test_devenv_vars_alone_are_not_a_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVENV_ROOT", str(tmp_path))
    monkeypatch.setenv("DEVENV_STATE", str(tmp_path / "state"))
    assert checks.detect_context(str(tmp_path)).kind == "not-a-repo"


def test_approach_b_input_warning_is_nonfatal(host, monkeypatch):
    monkeypatch.delenv("REPOMAN_PROVISIONED_DOC", raising=False)
    result = run_self_check([REGISTRY["doc"]], ".", ".claude/skills")
    assert _names(result)["provisioned:doc"].level == "warn"
    assert self_check_exit(result) == 0


def test_entrypoint_skill_missing_warns(host, tmp_path):
    result = run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills")
    assert _names(result)["skill:entrypoint"].level == "warn"


def test_sub_skill_deferral_is_checked(host, tmp_path):
    sub = tmp_path / ".claude/skills" / "gitman" / "SKILL.md"
    sub.parent.mkdir(parents=True)
    sub.write_text("No deferral")
    assert (
        _names(run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills"))["skill:git:defers"].level == "warn"
    )
    sub.write_text("See the repoman skill for ordering.")
    assert _names(run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills"))["skill:git:defers"].level == "ok"
