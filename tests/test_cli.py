from typer.testing import CliRunner

from repoman.aggregate import SubResult
from repoman.cli import app

runner = CliRunner()


def test_managers_lists_enabled(monkeypatch):
    monkeypatch.setenv("REPOMAN_MANAGERS", "copy test")
    result = runner.invoke(app, ["managers"])
    assert result.exit_code == 0
    assert "copyroom" in result.stdout and "testee" in result.stdout
    assert "gitman" not in result.stdout


def test_managers_lists_session(monkeypatch):
    monkeypatch.setenv("REPOMAN_MANAGERS", "session")
    result = runner.invoke(app, ["managers"])
    assert result.exit_code == 0 and "zelligate" in result.stdout


def test_managers_lists_agent(monkeypatch):
    monkeypatch.setenv("REPOMAN_MANAGERS", "agent")
    result = runner.invoke(app, ["managers"])
    assert result.exit_code == 0 and "mypi" in result.stdout


def test_managers_lists_doc(monkeypatch):
    monkeypatch.setenv("REPOMAN_MANAGERS", "doc")
    result = runner.invoke(app, ["managers"])
    assert result.exit_code == 0 and "docman" in result.stdout


def test_managers_lists_spec(monkeypatch):
    # spec maps to the family CLI `alliman`, not the 3rd-party `allium`.
    monkeypatch.setenv("REPOMAN_MANAGERS", "spec")
    result = runner.invoke(app, ["managers"])
    assert result.exit_code == 0 and "alliman" in result.stdout


def test_enabled_drops_unknown_manager_keys(monkeypatch):
    # Garbage REPOMAN_MANAGERS entries are dropped, not KeyError: the registry is
    # the trusted filter, so a stale/hand-edited env can't crash the CLI.
    monkeypatch.setenv("REPOMAN_MANAGERS", "test bogus")
    result = runner.invoke(app, ["managers"])
    assert result.exit_code == 0
    assert "testee" in result.stdout
    assert "bogus" not in result.stdout


def _healthy_repo(tmp_path, monkeypatch, managers):
    """A tmp repo whose lock + PATH satisfy the doctor self-check for ``managers``."""
    lock = '[repoman]\npackage="repoman"\nsource="path:/x"\n'
    for key in managers.split():
        lock += f'[managers.{key}]\npackage="{key}"\nsource="path:/x"\n'
    (tmp_path / "repoman.lock").write_text(lock)
    monkeypatch.setenv("REPOMAN_MANAGERS", managers)
    monkeypatch.setenv("DEVENV_ROOT", str(tmp_path))
    monkeypatch.setattr("repoman.checks.shutil.which", lambda c: "/usr/bin/" + c)


def test_doctor_skips_managers_without_doctor(monkeypatch, tmp_path):
    # copy (copyroom) has doctor=None → skipped; self-check green → exit 0.
    _healthy_repo(tmp_path, monkeypatch, "copy")
    result = runner.invoke(app, ["doctor"])
    assert "self-check" in result.stdout
    assert "no doctor, skipped" in result.stdout
    assert result.exit_code == 0


def test_doctor_exit_collapses_sub_doctor_exit(monkeypatch, tmp_path):
    # The conductor's whole reason for existing: a sub-doctor's non-zero exit (1)
    # must win over a green self-check (0) — proves max() combines both sides.
    _healthy_repo(tmp_path, monkeypatch, "test")
    monkeypatch.setattr(
        "repoman.cli.run_sub",
        lambda manager, args: SubResult(manager.key, [manager.command, *args], exit_code=1, available=True),
    )
    result = runner.invoke(app, ["doctor"])
    assert "=== test (testee) ===" in result.stdout
    assert result.exit_code == 1


def test_doctor_exit_is_worst_of_self_and_sub(monkeypatch, tmp_path):
    # self-check FAIL (2) + sub-doctor 1 → exit 2: proves the max() folds the
    # self side in too, not just the sub-doctors' worst.
    _healthy_repo(tmp_path, monkeypatch, "test")
    # installed:test fails → self_code 2, while the mocked sub-doctor returns 1.
    monkeypatch.setattr("repoman.checks.shutil.which", lambda _c: None)
    monkeypatch.setattr(
        "repoman.cli.run_sub",
        lambda manager, args: SubResult(manager.key, [manager.command, *args], exit_code=1, available=True),
    )
    result = runner.invoke(app, ["doctor"])
    assert "FAIL installed:test" in result.stdout
    assert result.exit_code == 2


def test_doctor_mixed_roster_skips_and_runs(monkeypatch, tmp_path):
    # copy (no doctor) is skipped AND testee's doctor runs, in one invocation —
    # both halves of the roster behavior in a single call.
    _healthy_repo(tmp_path, monkeypatch, "copy test")
    ran = []

    def fake_run(manager, args):
        ran.append(manager.key)
        return SubResult(manager.key, [manager.command, *args], exit_code=0, available=True)

    monkeypatch.setattr("repoman.cli.run_sub", fake_run)
    result = runner.invoke(app, ["doctor"])
    assert "no doctor, skipped" in result.stdout
    assert ran == ["test"]  # only the doctor-bearing manager was invoked
    assert result.exit_code == 0


def test_status_exits_worst_of_sub_results(monkeypatch):
    # git returns 0, test returns 1 → status exits 1 (worst).
    monkeypatch.setenv("REPOMAN_MANAGERS", "git test")

    def fake_run(manager, args):
        code = 1 if manager.key == "test" else 0
        return SubResult(manager.key, [manager.command, *args], exit_code=code, available=True)

    monkeypatch.setattr("repoman.cli.run_sub", fake_run)
    result = runner.invoke(app, ["status"])
    assert "=== git (gitman) ===" in result.stdout
    assert "=== test (testee) ===" in result.stdout
    assert result.exit_code == 1


def test_status_skips_managers_without_status(monkeypatch):
    # doc has status=None → skipped entirely: no run_sub call, no echo, exit 0.
    monkeypatch.setenv("REPOMAN_MANAGERS", "copy doc")
    called = []

    def fake_run(manager, args):
        called.append(manager.key)
        return SubResult(manager.key, [manager.command, *args], exit_code=0, available=True)

    monkeypatch.setattr("repoman.cli.run_sub", fake_run)
    result = runner.invoke(app, ["status"])
    assert called == ["copy"]
    assert "docman" not in result.stdout
    assert result.exit_code == 0


def test_doctor_self_only_skips_manager_doctors(monkeypatch, tmp_path):
    _healthy_repo(tmp_path, monkeypatch, "copy test")
    result = runner.invoke(app, ["doctor", "--self-only"])
    assert "self-check" in result.stdout
    assert "=== test (testee) ===" not in result.stdout  # sub-doctors not run
    assert result.exit_code == 0


def test_doctor_fails_when_selected_manager_unbuilt(monkeypatch, tmp_path):
    # session selected but absent from lock and not on PATH → self-check FAIL, exit 2.
    (tmp_path / "repoman.lock").write_text('[repoman]\npackage="repoman"\nsource="path:/x"\n')
    monkeypatch.setenv("REPOMAN_MANAGERS", "session")
    monkeypatch.setenv("DEVENV_ROOT", str(tmp_path))
    monkeypatch.setattr("repoman.checks.shutil.which", lambda _c: None)
    result = runner.invoke(app, ["doctor", "--self-only"])
    assert "FAIL" in result.stdout
    assert result.exit_code == 2


def test_doctor_warns_when_approach_b_input_missing(monkeypatch, tmp_path):
    # doc selected + CLI on PATH but no REPOMAN_PROVISIONED_DOC → WARN provisioned:doc,
    # non-fatal (exit 0).
    _healthy_repo(tmp_path, monkeypatch, "doc")
    monkeypatch.delenv("REPOMAN_PROVISIONED_DOC", raising=False)
    result = runner.invoke(app, ["doctor", "--self-only"])
    assert "WARN provisioned:doc" in result.stdout
    assert result.exit_code == 0


def test_install_skills_writes_file(monkeypatch, tmp_path):
    monkeypatch.setenv("REPOMAN_MANAGERS", "copy test")
    monkeypatch.setenv("REPOMAN_SKILLS_DIR", ".claude/skills")
    monkeypatch.setenv("DEVENV_ROOT", str(tmp_path))
    result = runner.invoke(app, ["install-skills"])
    assert result.exit_code == 0
    assert (tmp_path / ".claude/skills/repoman/SKILL.md").exists()


def test_install_skills_also_installs_devman(monkeypatch, tmp_path):
    monkeypatch.setenv("REPOMAN_MANAGERS", "copy test")
    monkeypatch.setenv("REPOMAN_SKILLS_DIR", ".claude/skills")
    monkeypatch.setenv("REPOMAN_DOCS_DIR", ".agents/devenv")
    monkeypatch.setenv("DEVENV_ROOT", str(tmp_path))
    result = runner.invoke(app, ["install-skills"])
    assert result.exit_code == 0
    # A devman skill lands beside the entrypoint, and the docs export lands under docs_dir.
    assert (tmp_path / ".claude/skills/devenv-run-commands/SKILL.md").exists()
    assert (tmp_path / ".agents/devenv/lock-and-cache.md").exists()


def test_doctor_reports_devman_checks(monkeypatch, tmp_path):
    _healthy_repo(tmp_path, monkeypatch, "copy test")
    result = runner.invoke(app, ["doctor", "--self-only"])
    assert "devman:skills" in result.stdout
    assert "devman:docs" in result.stdout
    # Nothing installed in the tmp repo → warn, but warn is non-fatal (exit stays 0).
    assert "WARN devman:skills" in result.stdout
    assert result.exit_code == 0
