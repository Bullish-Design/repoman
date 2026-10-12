import types

import pytest

import repoman.checks as checks
from repoman.checks import run_self_check, self_check_exit
from repoman.registry import REGISTRY


def _names(result):
    return {item.name: item for item in result}


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
    testee.write_text('#!/bin/sh\nprintf "testee 0.6.0\\n"\n')
    testee.chmod(0o755)
    monkeypatch.setattr(
        checks.shutil,
        "which",
        lambda command: str(bin_dir / command) if (bin_dir / command).exists() else None,
    )
    return types.SimpleNamespace(bin=bin_dir)


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


def test_binary_resolution(host):
    assert checks.manager_binary(REGISTRY["git"]) == host.bin / "gitman"
    assert checks.manager_binary(REGISTRY["test"]) == host.bin / "testee"


def test_gitman_interface_check_needs_the_work_command_and_jj_0_46(host, tmp_path, monkeypatch):
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

    gitman.write_text('#!/bin/sh\nprintf "usage: gitman [-h] {work,done} ...\\n"\n')
    names = _names(run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills"))
    assert names["interface:git"].level == "ok"

    gitman.write_text('#!/bin/sh\nprintf "usage: gitman [-h] {start,status} ...\\n"\n')
    names = _names(run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills"))
    assert names["interface:git"].level == "fail"

    gitman.write_text('#!/bin/sh\nprintf "usage: gitman [-h] {done,status} ...\\n"\n')
    names = _names(run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills"))
    assert names["interface:git"].level == "fail"

    gitman.write_text('#!/bin/sh\nprintf "usage: gitman [-h] {work} ...\\n"\n')
    jj.write_text('#!/bin/sh\nprintf "jj 0.45.0\\n"\n')
    names = _names(run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills"))
    assert names["interface:git"].level == "fail"


def _testee_prints(host, text):
    testee = host.bin / "testee"
    testee.write_text(f'#!/bin/sh\nprintf "{text}\\n"\n')
    testee.chmod(0o755)


def test_testee_at_the_minimum_passes(host):
    names = _names(run_self_check([REGISTRY["test"]], ".", ".claude/skills"))
    assert names["installed:test"].level == "ok"
    assert names["version:test"].level == "ok"
    assert "reports 0.6.0; needs 0.6.0 or later" in names["version:test"].detail


@pytest.mark.parametrize("reported", ["testee 0.6.2", "testee 0.10.0", "testee 1.0.0"])
def test_testee_newer_than_the_minimum_passes(host, reported):
    _testee_prints(host, reported)
    assert _names(run_self_check([REGISTRY["test"]], ".", ".claude/skills"))["version:test"].level == "ok"


@pytest.mark.parametrize("reported", ["testee 0.5.1", "testee 0.4.0"])
def test_testee_older_than_the_minimum_fails(host, reported):
    _testee_prints(host, reported)
    row = _names(run_self_check([REGISTRY["test"]], ".", ".claude/skills"))["version:test"]
    assert row.level == "fail"
    assert f"reports {reported.split()[1]}; needs 0.6.0 or later" in row.detail


def test_version_check_fails_when_the_version_flag_fails(host):
    testee = host.bin / "testee"
    testee.write_text("#!/bin/sh\nexit 3\n")
    testee.chmod(0o755)
    row = _names(run_self_check([REGISTRY["test"]], ".", ".claude/skills"))["version:test"]
    assert row.level == "fail" and "exited 3" in row.detail


def test_managers_without_a_minimum_get_no_version_row(host):
    names = _names(run_self_check([REGISTRY["copy"], REGISTRY["git"]], ".", ".claude/skills"))
    assert not {n for n in names if n.startswith("version:")}


def test_unrecognized_version_output_fails(host):
    testee = host.bin / "testee"
    testee.write_text('#!/bin/sh\nprintf "no version here\\n"\n')
    testee.chmod(0o755)
    names = _names(run_self_check([REGISTRY["test"]], ".", ".claude/skills"))
    assert names["version:test"].level == "fail"
    assert "unrecognized version" in names["version:test"].detail


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
