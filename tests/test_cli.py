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


def test_managers_lists_doc(monkeypatch):
    monkeypatch.setenv("REPOMAN_MANAGERS", "doc")
    result = runner.invoke(app, ["managers"])
    assert result.exit_code == 0 and "docman" in result.stdout


def test_enabled_drops_unknown_manager_keys(monkeypatch):
    # Garbage REPOMAN_MANAGERS entries are dropped, not KeyError: the registry is
    # the trusted filter, so a stale/hand-edited env can't crash the CLI.
    monkeypatch.setenv("REPOMAN_MANAGERS", "test bogus")
    result = runner.invoke(app, ["managers"])
    assert result.exit_code == 0
    assert "testee" in result.stdout
    assert "bogus" not in result.stdout


def _healthy_repo(tmp_path, monkeypatch, managers):
    """A tmp repo whose toolchain venv + pyproject satisfy the doctor self-check."""
    # fake bootstrapped SYSTEM-WIDE toolchain venv (project 12)
    venv = tmp_path / "toolchain"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "repoman").write_text("")
    manifest = '[repoman]\npackage = "repoman"\nsource = "path:/x"\n'
    for key in ("copy", "git", "doc"):
        if key in managers.split():
            manifest += f'[managers.{key}]\npackage = "{key}"\nsource = "path:/x"\n'
    if "git" in managers.split():
        manifest += '[managers.git-pyjutsu]\npackage = "pyjutsu"\nsource = "wheel:pyjutsu>=0.8"\n'
    (venv / "repoman-toolchain.toml").write_text(manifest)
    # the consumer declares testee as a uv dev dependency
    if "test" in managers.split():
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.0.0"\nrequires-python = ">=3.13"\n'
            'dependencies = []\n[dependency-groups]\ndev = ["testee"]\n'
        )
    monkeypatch.setenv("REPOMAN_TOOLCHAIN_VENV", str(venv))
    monkeypatch.setenv("REPOMAN_MANAGERS", managers)
    monkeypatch.setenv("DEVENV_ROOT", str(tmp_path))
    monkeypatch.setattr("repoman.checks.shutil.which", lambda c: "/usr/bin/" + c)


def test_doctor_runs_every_enabled_manager(monkeypatch, tmp_path):
    # Every roster manager ships a doctor now (copyroom 0.6+ included) — the
    # aggregate invokes them all; a green self-check → exit 0.
    _healthy_repo(tmp_path, monkeypatch, "copy test")
    ran = []

    def fake_run(manager, args):
        ran.append(manager.key)
        return SubResult(manager.key, [manager.command, *args], exit_code=0, available=True)

    monkeypatch.setattr("repoman.cli.run_sub", fake_run)
    result = runner.invoke(app, ["doctor"])
    assert "self-check" in result.stdout
    assert ran == ["copy", "test"]
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


def test_doctor_mixed_roster_runs_all_doctors(monkeypatch, tmp_path):
    # copyroom and testee both run their doctors in one invocation — the roster
    # has no doctor-less manager anymore.
    _healthy_repo(tmp_path, monkeypatch, "copy test")
    ran = []

    def fake_run(manager, args):
        ran.append(manager.key)
        return SubResult(manager.key, [manager.command, *args], exit_code=0, available=True)

    monkeypatch.setattr("repoman.cli.run_sub", fake_run)
    result = runner.invoke(app, ["doctor"])
    assert "=== copy (copyroom) ===" in result.stdout
    assert "=== test (testee) ===" in result.stdout
    assert ran == ["copy", "test"]
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


def test_doctor_fails_when_selected_manager_not_declared(monkeypatch, tmp_path):
    # test selected but NOT declared in pyproject.toml (uv-declared manager, project 12)
    # → uv:test FAIL, exit 2. The toolchain venv itself is healthy.
    venv = tmp_path / "toolchain"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "repoman").write_text("")
    (venv / "repoman-toolchain.toml").write_text('[repoman]\npackage="repoman"\nsource="path:/x"\n')
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.0.0"\n')
    monkeypatch.setenv("REPOMAN_TOOLCHAIN_VENV", str(venv))
    monkeypatch.setenv("REPOMAN_MANAGERS", "test")
    monkeypatch.setenv("DEVENV_ROOT", str(tmp_path))
    monkeypatch.setattr("repoman.checks.shutil.which", lambda _c: None)
    result = runner.invoke(app, ["doctor", "--self-only"])
    assert "FAIL uv:test" in result.stdout
    assert result.exit_code == 2


def test_doctor_warns_when_approach_b_input_missing(monkeypatch, tmp_path):
    # doc selected + CLI on PATH but no REPOMAN_PROVISIONED_DOC → WARN provisioned:doc,
    # non-fatal (exit 0).
    _healthy_repo(tmp_path, monkeypatch, "doc")
    monkeypatch.delenv("REPOMAN_PROVISIONED_DOC", raising=False)
    result = runner.invoke(app, ["doctor", "--self-only"])
    assert "WARN provisioned:doc" in result.stdout
    assert result.exit_code == 0


def test_install_skills_writes_entrypoint_only(monkeypatch, tmp_path):
    monkeypatch.setenv("REPOMAN_MANAGERS", "copy test")
    monkeypatch.setenv("REPOMAN_SKILLS_DIR", ".agents/skills")
    monkeypatch.setenv("DEVENV_ROOT", str(tmp_path))
    result = runner.invoke(app, ["install-skills"])
    assert result.exit_code == 0
    assert (tmp_path / ".agents/skills/repoman/SKILL.md").exists()
    # The router is the ONLY skill RepoMan installs — manager skills are
    # tool-shipped (copyroom agent-files export) or genome-shipped (copyroom update).
    assert not (tmp_path / ".agents/skills/devenv-run-commands").exists()
    assert not (tmp_path / ".agents/skills/.devman-source").exists()


def test_doctor_reports_skill_ownership(monkeypatch, tmp_path):
    _healthy_repo(tmp_path, monkeypatch, "copy test")
    result = runner.invoke(app, ["doctor", "--self-only"])
    # Nothing installed in the tmp repo → warn, but warn is non-fatal (exit stays 0).
    assert "WARN skill:tool-shipped" in result.stdout
    assert result.exit_code == 0


def test_doctor_ownership_ok_when_canonical_skills_present(monkeypatch, tmp_path):
    _healthy_repo(tmp_path, monkeypatch, "copy test")
    skills = tmp_path / ".agents/skills"
    from repoman.devman.check import CANONICAL_COPYROOM_SKILLS

    for name in CANONICAL_COPYROOM_SKILLS:
        skill = skills / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    result = runner.invoke(app, ["doctor", "--self-only"])
    assert "skill:tool-shipped — canonical copyroom skills present" in result.stdout
    assert result.exit_code == 0
