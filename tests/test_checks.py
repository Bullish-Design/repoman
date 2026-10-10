import types

import pytest

import repoman.checks as checks
from repoman.checks import run_self_check, self_check_exit
from repoman.registry import REGISTRY, Manager


def _names(result):
    return {item.name: item for item in result}


_PYPROJECT_UV = """[project]
name = "x"
version = "0.0.0"
requires-python = ">=3.13"
dependencies = []

[dependency-groups]
dev = ["uv-tool"]
"""

UV_MANAGER = Manager("uv-tool", "uv-tool", "core", "test fixture", install="uv")


@pytest.fixture
def host(tmp_path, monkeypatch):
    """A fake host profile: a bin dir with the host commands, found through PATH."""

    bin_dir = tmp_path / "host-bin"
    bin_dir.mkdir()
    for command in ("repoman", "copyroom", "gitman"):
        binary = bin_dir / command
        binary.write_text("#!/bin/sh\nexit 0\n")
        binary.chmod(0o755)
    testee = bin_dir / "testee"
    testee.write_text('#!/bin/sh\nprintf "testee 0.5.0\\n"\n')
    testee.chmod(0o755)
    monkeypatch.delenv("DEVENV_STATE", raising=False)
    monkeypatch.delenv("DEVENV_ROOT", raising=False)
    monkeypatch.setenv("REPOMAN_TESTEE_HOST_BIN", str(testee))
    monkeypatch.setenv("REPOMAN_TESTEE_VERSION", "0.5.0")
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
    (bin_dir / "uv-tool").write_text("")
    monkeypatch.setenv("DEVENV_STATE", str(tmp_path / ".devenv" / "state"))
    return bin_dir


def test_host_manager_on_path_is_installed(host):
    names = _names(run_self_check([REGISTRY["git"], REGISTRY["copy"]], ".", ".claude/skills"))
    assert names["installed:git"].level == "ok"
    assert names["installed:git"].detail == str(host.bin / "gitman")
    assert names["installed:copy"].level == "ok"


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
    assert checks.manager_binary(REGISTRY["test"]) == host.bin / "testee"
    assert checks.manager_binary(UV_MANAGER) == consumer_venv / "uv-tool"


def test_uv_manager_warns_when_path_shadows_the_venv(host, consumer_venv, tmp_path, monkeypatch):
    stale = tmp_path / "stale" / "uv-tool"
    stale.parent.mkdir()
    stale.write_text("")
    monkeypatch.setattr(checks.shutil, "which", lambda command: str(stale) if command == "uv-tool" else None)
    installed = _names(run_self_check([UV_MANAGER], ".", ".claude/skills"))["installed:uv-tool"]
    assert installed.level == "warn"
    assert str(stale) in installed.detail and str(consumer_venv / "uv-tool") in installed.detail


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
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_UV)
    result = run_self_check([UV_MANAGER], str(tmp_path), ".claude/skills")
    assert _names(result)["uv:uv-tool"].level == "ok"
    assert _names(result)["installed:uv-tool"].level == "ok"


def test_uv_manager_not_declared_fails(host, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.0.0"\n')
    result = run_self_check([UV_MANAGER], str(tmp_path), ".claude/skills")
    assert _names(result)["uv:uv-tool"].level == "fail"


def test_uv_requirement_normalisation(host, consumer_venv, tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n'
        '[dependency-groups]\ndev = ["UV_TOOL[all]>=0.3 ; python_version>\\"3.12\\""]\n'
    )
    assert _names(run_self_check([UV_MANAGER], str(tmp_path), ".claude/skills"))["uv:uv-tool"].level == "ok"


def test_unparseable_pyproject_is_reported(host, tmp_path):
    (tmp_path / "pyproject.toml").write_text("this is not [ toml")
    result = run_self_check([UV_MANAGER], str(tmp_path), ".claude/skills")
    assert _names(result)["pyproject"].level == "fail"


def test_uv_manager_has_no_host_rows(host, tmp_path):
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_UV)
    names = _names(run_self_check([UV_MANAGER], str(tmp_path), ".claude/skills"))
    assert "lock:uv-tool" not in names


def test_testee_version_matches_the_pinned_package(host):
    names = _names(run_self_check([REGISTRY["test"]], ".", ".claude/skills"))
    assert names["installed:test"].level == "ok"
    assert names["version:test"].level == "ok"
    assert "0.5.0" in names["version:test"].detail


def test_testee_path_must_match_the_host_binary(host, tmp_path, monkeypatch):
    shadow = tmp_path / "shadow" / "testee"
    shadow.parent.mkdir()
    shadow.write_text('#!/bin/sh\nprintf "testee 0.5.0\\n"\n')
    shadow.chmod(0o755)
    monkeypatch.setattr(
        checks.shutil,
        "which",
        lambda command: str(shadow) if command == "testee" else str(host.bin / command),
    )
    names = _names(run_self_check([REGISTRY["test"]], ".", ".claude/skills"))
    assert names["installed:test"].level == "fail"
    assert "tasks use" in names["installed:test"].detail


def test_testee_version_mismatch_fails(host):
    testee = host.bin / "testee"
    testee.write_text('#!/bin/sh\nprintf "testee 0.4.0\\n"\n')
    testee.chmod(0o755)
    names = _names(run_self_check([REGISTRY["test"]], ".", ".claude/skills"))
    assert names["version:test"].level == "fail"
    assert "reports 0.4.0" in names["version:test"].detail


def test_testee_requires_a_pinned_version(host, monkeypatch):
    monkeypatch.delenv("REPOMAN_TESTEE_VERSION")
    names = _names(run_self_check([REGISTRY["test"]], ".", ".claude/skills"))
    assert names["version:test"].level == "fail"
    assert "REPOMAN_TESTEE_VERSION is missing" in names["version:test"].detail


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


# No shipped manager uses approach B. This synthetic one keeps the extension seam tested.
APPROACH_B_MANAGER = Manager("example", "gitman", "situational", "test fixture", nix_input="examplman")


def test_approach_b_input_warning_is_nonfatal(host, monkeypatch):
    monkeypatch.delenv("REPOMAN_PROVISIONED_EXAMPLE", raising=False)
    result = run_self_check([APPROACH_B_MANAGER], ".", ".claude/skills")
    row = _names(result)["provisioned:example"]
    assert row.level == "warn"
    assert "'examplman' input" in row.detail
    assert self_check_exit(result) == 0


def test_approach_b_input_signal_clears_the_warning(host, monkeypatch):
    monkeypatch.setenv("REPOMAN_PROVISIONED_EXAMPLE", "1")
    result = run_self_check([APPROACH_B_MANAGER], ".", ".claude/skills")
    assert _names(result)["provisioned:example"].level == "ok"


def test_roster_check_is_silent_for_known_keys():
    assert checks.roster_check(["copy", "git", "test", "git"]) is None
    assert checks.roster_check([]) is None


def test_roster_check_names_removed_and_unknown_keys_once():
    row = checks.roster_check(["doc", "test", "doc", "bogus"])
    assert row is not None
    assert row.name == "roster:unknown-manager" and row.level == "warn"
    assert row.detail.count("'doc'") == 1
    assert "'doc' was removed in 0.13.0" in row.detail
    assert "'bogus' is not a RepoMan manager" in row.detail
    assert ".repoman/project.toml" in row.detail


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
