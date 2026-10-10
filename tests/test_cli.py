import json

from typer.testing import CliRunner

from repoman.cli import app

runner = CliRunner()


def test_managers_lists_enabled(monkeypatch):
    monkeypatch.setenv("REPOMAN_MANAGERS", "copy test")
    result = runner.invoke(app, ["managers"])
    assert result.exit_code == 0
    assert "copyroom" in result.stdout and "testee" in result.stdout
    assert "gitman" not in result.stdout


def test_managers_drops_the_removed_doc_manager(monkeypatch):
    monkeypatch.setenv("REPOMAN_MANAGERS", "doc test")
    result = runner.invoke(app, ["managers"])
    assert result.exit_code == 0
    assert "testee" in result.stdout
    assert "docman" not in result.stdout


def test_enabled_drops_unknown_manager_keys(monkeypatch):
    # Garbage REPOMAN_MANAGERS entries are dropped, not KeyError: the registry is
    # the trusted filter, so a stale/hand-edited env can't crash the CLI.
    monkeypatch.setenv("REPOMAN_MANAGERS", "test bogus")
    result = runner.invoke(app, ["managers"])
    assert result.exit_code == 0
    assert "testee" in result.stdout
    assert "bogus" not in result.stdout


# Commands the host profile puts on PATH.
_HOST_COMMANDS = ("repoman", "copyroom", "gitman", "testee")


def _healthy_repo(tmp_path, monkeypatch, managers):
    """Create a healthy repo for the doctor tests with host commands on PATH."""

    host_bin = tmp_path / "host-bin"
    host_bin.mkdir()
    for command in _HOST_COMMANDS:
        binary = host_bin / command
        if command == "testee":
            binary.write_text('#!/bin/sh\nprintf "testee 0.5.0\\n"\n')
            binary.chmod(0o755)
        else:
            binary.write_text("#!/bin/sh\nexit 0\n")
            binary.chmod(0o755)

    state = tmp_path / ".devenv" / "state"
    consumer_bin = state / "venv" / "bin"
    consumer_bin.mkdir(parents=True)

    def which(command):
        for directory in (host_bin, consumer_bin):
            if (directory / command).exists():
                return str(directory / command)
        return None

    monkeypatch.setenv("DEVENV_STATE", str(state))
    monkeypatch.setenv("REPOMAN_MANAGERS", managers)
    monkeypatch.setenv("DEVENV_ROOT", str(tmp_path))
    monkeypatch.setenv("REPOMAN_TESTEE_HOST_BIN", str(host_bin / "testee"))
    monkeypatch.setenv("REPOMAN_TESTEE_VERSION", "0.5.0")
    monkeypatch.setattr("repoman.checks.shutil.which", which)


def test_doctor_fails_when_testee_host_binary_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("REPOMAN_MANAGERS", "test")
    monkeypatch.setenv("DEVENV_ROOT", str(tmp_path))
    monkeypatch.setenv("REPOMAN_TESTEE_HOST_BIN", str(tmp_path / "missing-testee"))
    monkeypatch.setenv("REPOMAN_TESTEE_VERSION", "0.5.0")
    monkeypatch.setattr("repoman.checks.shutil.which", lambda _c: None)
    result = runner.invoke(app, ["doctor"])
    assert "FAIL installed:test" in result.stdout
    assert result.exit_code == 1


def test_doctor_fails_when_testee_version_does_not_match(monkeypatch, tmp_path):
    _healthy_repo(tmp_path, monkeypatch, "test")
    (tmp_path / "host-bin" / "testee").write_text('#!/bin/sh\nprintf "testee 0.4.0\\n"\n')
    result = runner.invoke(app, ["doctor"])
    assert "FAIL version:test" in result.stdout
    assert "pinned package requires 0.5.0" in result.stdout
    assert result.exit_code == 1


def test_doctor_warns_about_the_removed_doc_manager(monkeypatch, tmp_path):
    # A repo that still lists `doc` keeps working: the CLI drops the key and the
    # doctor names it. The row is a warning, so the exit code stays 0.
    _healthy_repo(tmp_path, monkeypatch, "test doc")
    result = runner.invoke(app, ["doctor"])
    assert "WARN roster:unknown-manager" in result.stdout
    assert "'doc' was removed in 0.13.0" in result.stdout
    assert "installed:doc" not in result.stdout
    assert result.exit_code == 0


def test_doctor_json_carries_the_unknown_manager_row(monkeypatch, tmp_path):
    _healthy_repo(tmp_path, monkeypatch, "test doc bogus doc")
    result = runner.invoke(app, ["doctor", "--json"])
    rows = {row["name"]: row for row in json.loads(result.stdout)["checks"]}
    row = rows["roster:unknown-manager"]
    assert row["warn_only"] is True and row["ok"] is False
    assert "'doc' was removed in 0.13.0" in row["detail"]
    assert "'bogus' is not a RepoMan manager" in row["detail"]
    assert row["detail"].count("'doc'") == 1  # a duplicate key reports once


def test_doctor_has_no_unknown_manager_row_for_a_clean_roster(monkeypatch, tmp_path):
    _healthy_repo(tmp_path, monkeypatch, "test")
    result = runner.invoke(app, ["doctor"])
    assert "roster:unknown-manager" not in result.stdout


def test_install_skills_writes_entrypoint_only(monkeypatch, tmp_path):
    monkeypatch.setenv("REPOMAN_MANAGERS", "copy test")
    monkeypatch.setenv("REPOMAN_SKILLS_DIR", ".agents/skills")
    monkeypatch.setenv("DEVENV_ROOT", str(tmp_path))
    result = runner.invoke(app, ["install-skills"])
    assert result.exit_code == 0
    assert (tmp_path / ".agents/skills/repoman/SKILL.md").exists()
    # The router is the ONLY skill RepoMan installs — manager skills are devman
    # pool links and project-specific skills are real content in the central dir.
    assert not (tmp_path / ".agents/skills/devenv-run-commands").exists()
    assert not (tmp_path / ".agents/skills/.devman-source").exists()


def test_doctor_reports_skill_ownership(monkeypatch, tmp_path):
    _healthy_repo(tmp_path, monkeypatch, "copy test")
    result = runner.invoke(app, ["doctor"])
    # Nothing installed in the tmp repo → warn, but warn is non-fatal (exit stays 0).
    assert "WARN skill:tool-shipped" in result.stdout
    assert result.exit_code == 0


def test_doctor_ownership_ok_when_expected_skills_present(monkeypatch, tmp_path):
    _healthy_repo(tmp_path, monkeypatch, "copy test")
    skills = tmp_path / ".agents/skills"
    from repoman.devman.check import expected_skills

    for name in expected_skills(["copy", "test"]):
        skill = skills / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    result = runner.invoke(app, ["doctor"])
    assert "skill:tool-shipped — expected pool links present" in result.stdout
    assert result.exit_code == 0


# ---------------------------------------------------------------- roster semantics


def test_empty_roster_is_not_the_default_roster(monkeypatch):
    # An empty project manifest exports REPOMAN_MANAGERS="". "Wire nothing" must
    # not silently become the three core managers.
    monkeypatch.setenv("REPOMAN_MANAGERS", "")
    result = runner.invoke(app, ["managers"])
    assert result.exit_code == 0
    assert result.stdout.strip() == ""


def test_unset_roster_falls_back_to_the_core_default(monkeypatch):
    monkeypatch.delenv("REPOMAN_MANAGERS", raising=False)
    result = runner.invoke(app, ["managers"])
    assert result.exit_code == 0
    for command in ("copyroom", "gitman", "testee"):
        assert command in result.stdout


def test_duplicate_roster_entries_are_collapsed(monkeypatch):
    # "git git" must list gitman once.
    monkeypatch.setenv("REPOMAN_MANAGERS", "git git test")
    result = runner.invoke(app, ["managers"])
    assert result.exit_code == 0
    assert result.stdout.count("Version control") == 1
    assert "testee" in result.stdout


# ---------------------------------------------------------------- context preflight (project 13)


def test_doctor_outside_a_repo_short_circuits(monkeypatch, tmp_path):
    # Not-a-repo: one clear message + exit 2 — NOT a pile of plausible-looking rows.
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 2
    assert "not inside a repoman-managed repo" in result.stdout
    assert "devenv shell" in result.stdout
    assert "===" not in result.stdout  # no self-check header
    assert "FAIL" not in result.stdout and "skill:" not in result.stdout


def test_doctor_bare_shell_in_a_repo_short_circuits(monkeypatch, tmp_path):
    # Managed repo, bare shell: "enter the devenv shell" — NOT the not-a-repo
    # message (acceptance criterion 3 distinguishes the two contexts).
    repo = tmp_path / "managed-repo"
    repo.mkdir()
    (repo / ".repoman").mkdir()
    (repo / ".repoman" / "project.toml").write_text("")
    monkeypatch.chdir(repo)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 2
    assert "managed repo found, but not inside its devenv shell" in result.stdout
    assert str(repo) in result.stdout  # the hint names the detected repo
    assert "not inside a repoman-managed repo" not in result.stdout


def test_doctor_in_shell_passes_through_unscathed(monkeypatch, tmp_path):
    # The regression baseline: in-shell doctor behaves exactly as before — same
    # rows, same exit. (The existing _healthy_repo tests cover the row shapes;
    # this pins that the preflight doesn't interfere with the in-shell path.)
    _healthy_repo(tmp_path, monkeypatch, "copy test")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "=== repoman (self-check) ===" in result.stdout
    assert "OK   installed:copy" in result.stdout
    assert "OK   version:test" in result.stdout
    assert "uv:test" not in result.stdout


def test_doctor_json_context_error(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["context"]["ok"] is False
    assert payload["context"]["kind"] == "not-a-repo"
    assert "devenv shell" in payload["context"]["hint"]
    assert payload["checks"] == []
    assert payload["exit"] == 2


def test_doctor_json_bare_shell(monkeypatch, tmp_path):
    repo = tmp_path / "managed-repo"
    repo.mkdir()
    (repo / ".repoman").mkdir()
    (repo / ".repoman" / "project.toml").write_text("")
    monkeypatch.chdir(repo)
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["context"]["ok"] is False
    assert payload["context"]["kind"] == "managed-repo-bare-shell"
    assert "devenv shell" in payload["context"]["hint"]
    assert payload["checks"] == []
    assert payload["exit"] == 2


def test_doctor_json_in_shell(monkeypatch, tmp_path):
    _healthy_repo(tmp_path, monkeypatch, "copy test")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["context"]["ok"] is True
    assert payload["context"]["kind"] == "managed-repo-shell"
    assert payload["exit"] == 0
    assert payload["checks"]
    for check in payload["checks"]:
        # family row shape, no extra keys (copyroom's doctor --json convention)
        assert set(check) == {"name", "ok", "detail", "warn_only"}


# ---------------------------------------------------------------- reporting


# ---------------------------------------------------------------- version / robustness


def test_version_flag_reports_the_package_version():
    from repoman import __version__

    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_absolute_skills_dir_is_rejected(monkeypatch, tmp_path):
    # Path(repo_root) / "/abs" collapses to "/abs", so install-skills would write
    # outside the repo entirely.
    outside = tmp_path / "outside"
    monkeypatch.setenv("REPOMAN_MANAGERS", "test")
    monkeypatch.setenv("REPOMAN_SKILLS_DIR", str(outside))
    monkeypatch.setenv("DEVENV_ROOT", str(tmp_path / "repo"))
    result = runner.invoke(app, ["install-skills"])
    assert result.exit_code == 2  # the tool could not run
    assert not outside.exists()


def test_parent_traversal_skills_dir_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("REPOMAN_MANAGERS", "test")
    monkeypatch.setenv("REPOMAN_SKILLS_DIR", "../escape/skills")
    monkeypatch.setenv("DEVENV_ROOT", str(tmp_path / "repo"))
    result = runner.invoke(app, ["install-skills"])
    assert result.exit_code == 2
    assert not (tmp_path / "escape").exists()


def test_unexpected_exception_exits_infra_not_domain(monkeypatch, capsys):
    # A crashed conductor exiting 1 would read as "a domain decision is needed".
    import repoman.cli as cli

    monkeypatch.setattr(cli, "app", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    try:
        cli.main()
    except SystemExit as exc:
        assert exc.code == 2
    else:  # pragma: no cover - main() must not return normally here
        raise AssertionError("main() swallowed the failure")
    assert "internal error" in capsys.readouterr().err


def test_keyboard_interrupt_exits_130(monkeypatch):
    import repoman.cli as cli

    monkeypatch.setattr(cli, "app", lambda: (_ for _ in ()).throw(KeyboardInterrupt))
    try:
        cli.main()
    except SystemExit as exc:
        assert exc.code == 130


def test_normal_exit_codes_pass_through_the_crash_guard(monkeypatch):
    # The guard must not rewrite a deliberate typer.Exit — only unexpected exceptions.
    import repoman.cli as cli

    monkeypatch.setattr(cli, "app", lambda: (_ for _ in ()).throw(SystemExit(1)))
    try:
        cli.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:  # pragma: no cover
        raise AssertionError("main() swallowed the exit")
