from typer.testing import CliRunner

from repoman.cli import app

runner = CliRunner()


def test_managers_lists_enabled(monkeypatch):
    monkeypatch.setenv("REPOMAN_MANAGERS", "copy test")
    result = runner.invoke(app, ["managers"])
    assert result.exit_code == 0
    assert "copyroom" in result.stdout and "testee" in result.stdout
    assert "gitman" not in result.stdout


def test_doctor_skips_managers_without_doctor(monkeypatch):
    # copy (copyroom) has doctor=None → skipped; with no others installed, exit 0.
    monkeypatch.setenv("REPOMAN_MANAGERS", "copy")
    result = runner.invoke(app, ["doctor"])
    assert "no doctor, skipped" in result.stdout
    assert result.exit_code == 0


def test_install_skills_writes_file(monkeypatch, tmp_path):
    monkeypatch.setenv("REPOMAN_MANAGERS", "copy test")
    monkeypatch.setenv("REPOMAN_SKILLS_DIR", ".claude/skills")
    monkeypatch.setenv("DEVENV_ROOT", str(tmp_path))
    result = runner.invoke(app, ["install-skills"])
    assert result.exit_code == 0
    assert (tmp_path / ".claude/skills/repoman/SKILL.md").exists()
