from typer.testing import CliRunner

from repoman.cli import app

runner = CliRunner()


def test_managers_lists_enabled(monkeypatch):
    monkeypatch.setenv("REPOMAN_MANAGERS", "copy test")
    result = runner.invoke(app, ["managers"])
    assert result.exit_code == 0
    assert "copyroom" in result.stdout and "testee" in result.stdout
    assert "gitman" not in result.stdout


def test_managers_lists_agent(monkeypatch):
    monkeypatch.setenv("REPOMAN_MANAGERS", "agent")
    result = runner.invoke(app, ["managers"])
    assert result.exit_code == 0 and "mypi" in result.stdout


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


def test_install_skills_writes_file(monkeypatch, tmp_path):
    monkeypatch.setenv("REPOMAN_MANAGERS", "copy test")
    monkeypatch.setenv("REPOMAN_SKILLS_DIR", ".claude/skills")
    monkeypatch.setenv("DEVENV_ROOT", str(tmp_path))
    result = runner.invoke(app, ["install-skills"])
    assert result.exit_code == 0
    assert (tmp_path / ".claude/skills/repoman/SKILL.md").exists()
