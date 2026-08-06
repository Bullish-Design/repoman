import json

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


#: Commands that live in the shared toolchain venv (testee is uv-declared, so it does not).
_TOOLCHAIN_COMMANDS = ("repoman", "copyroom", "gitman", "docman")


def _healthy_repo(tmp_path, monkeypatch, managers):
    """A tmp repo whose toolchain venv + consumer venv + pyproject satisfy the doctor.

    Models the PATH order `modules/devenv.nix` establishes — toolchain ahead of the
    consumer venv — so `installed:<key>` sees PATH agreeing with the absolute path the
    nix tasks exec.
    """
    selected = managers.split()

    # fake bootstrapped SYSTEM-WIDE toolchain venv (project 12)
    venv = tmp_path / "toolchain"
    toolchain_bin = venv / "bin"
    toolchain_bin.mkdir(parents=True)
    for command in _TOOLCHAIN_COMMANDS:
        (toolchain_bin / command).write_text("")
    manifest = '[repoman]\npackage = "repoman"\nsource = "path:/x"\n'
    for key in ("copy", "git", "doc"):
        if key in selected:
            manifest += f'[managers.{key}]\npackage = "{key}"\nsource = "path:/x"\n'
    if "git" in selected:
        manifest += '[managers.git-pyjutsu]\npackage = "pyjutsu"\nsource = "wheel:pyjutsu>=0.8"\n'
    (venv / "repoman-toolchain.toml").write_text(manifest)

    # the consumer declares testee as a uv dev dependency and `uv sync` put it here
    state = tmp_path / ".devenv" / "state"
    consumer_bin = state / "venv" / "bin"
    consumer_bin.mkdir(parents=True)
    if "test" in selected:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.0.0"\nrequires-python = ">=3.13"\n'
            'dependencies = []\n[dependency-groups]\ndev = ["testee"]\n'
        )
        (consumer_bin / "testee").write_text("")

    def which(command):
        for directory in (toolchain_bin, consumer_bin):  # toolchain first, as on a real PATH
            if (directory / command).exists():
                return str(directory / command)
        return None

    monkeypatch.setenv("REPOMAN_TOOLCHAIN_VENV", str(venv))
    monkeypatch.setenv("DEVENV_STATE", str(state))
    monkeypatch.setenv("REPOMAN_MANAGERS", managers)
    monkeypatch.setenv("DEVENV_ROOT", str(tmp_path))
    monkeypatch.setattr("repoman.checks.shutil.which", which)


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
    (tmp_path / ".devenv" / "state" / "venv" / "bin" / "testee").unlink()
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


# ---------------------------------------------------------------- roster semantics


def test_empty_roster_is_not_the_default_roster(monkeypatch):
    # `repoman.managers = [ ]` in nix exports REPOMAN_MANAGERS="". "Wire nothing" must
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


def test_duplicate_roster_entries_are_collapsed(monkeypatch, tmp_path):
    # "git git" must not run gitman's doctor twice.
    _healthy_repo(tmp_path, monkeypatch, "git git test")
    ran = []
    monkeypatch.setattr(
        "repoman.cli.run_sub",
        lambda manager, args: (ran.append(manager.key),
                               SubResult(manager.key, [manager.command, *args], 0, True))[1],
    )
    result = runner.invoke(app, ["doctor"])
    assert ran == ["git", "test"]
    assert result.exit_code == 0


# ---------------------------------------------------------------- context preflight (project 13)


def test_doctor_outside_a_repo_short_circuits(monkeypatch, tmp_path):
    # Not-a-repo: one clear message + exit 2 — NOT a pile of plausible-looking rows.
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 2
    assert "not inside a repoman-managed repo" in result.stdout
    assert "devenv shell" in result.stdout
    assert "===" not in result.stdout  # no self-check header, no sub-doctor headers
    assert "FAIL" not in result.stdout and "skill:" not in result.stdout


def test_doctor_self_only_short_circuits_identically(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["doctor", "--self-only"])
    assert result.exit_code == 2
    assert "not inside a repoman-managed repo" in result.stdout
    assert "===" not in result.stdout


def test_doctor_bare_shell_in_a_repo_short_circuits(monkeypatch, tmp_path):
    # Managed repo, bare shell: "enter the devenv shell" — NOT the not-a-repo
    # message (acceptance criterion 3 distinguishes the two contexts).
    repo = tmp_path / "managed-repo"
    repo.mkdir()
    (repo / "gitman.toml").write_text("")
    (repo / ".gitman").mkdir()
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
    result = runner.invoke(app, ["doctor", "--self-only"])
    assert result.exit_code == 0
    assert "=== repoman (self-check) ===" in result.stdout
    assert "OK   toolchain:venv" in result.stdout


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
    (repo / "gitman.toml").write_text("")
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
    result = runner.invoke(app, ["doctor", "--self-only", "--json"])
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


def test_unavailable_manager_explains_itself(monkeypatch, tmp_path):
    # `repoman status` used to print a bare header and exit 2 with no explanation.
    _healthy_repo(tmp_path, monkeypatch, "git")
    monkeypatch.setattr(
        "repoman.cli.run_sub",
        lambda manager, args: SubResult(
            manager.key, [manager.command, *args], 127, False,
            reason="gitman is not installed — run `repoman-sync --machine`",
        ),
    )
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 2
    assert "gitman is not installed" in result.output


def test_manager_without_a_doctor_is_reported_as_skipped(monkeypatch, tmp_path):
    from repoman.registry import Manager

    _healthy_repo(tmp_path, monkeypatch, "git")
    doctorless = Manager("git", "gitman", "core", "s", doctor=None)
    monkeypatch.setattr("repoman.cli._enabled", lambda: [doctorless])
    called = []
    monkeypatch.setattr("repoman.cli.run_sub", lambda m, a: called.append(m.key))
    result = runner.invoke(app, ["doctor"])
    assert "no doctor, skipped" in result.stdout
    assert called == []


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
    assert result.exit_code == 3  # invalid usage
    assert not outside.exists()


def test_parent_traversal_skills_dir_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("REPOMAN_MANAGERS", "test")
    monkeypatch.setenv("REPOMAN_SKILLS_DIR", "../escape/skills")
    monkeypatch.setenv("DEVENV_ROOT", str(tmp_path / "repo"))
    result = runner.invoke(app, ["install-skills"])
    assert result.exit_code == 3
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
