import types

import pytest

import repoman.checks as checks
from repoman.checks import run_self_check, self_check_exit
from repoman.devman.check import skill_ownership_checks
from repoman.registry import REGISTRY

# A recorded machine manifest (the shape `repoman-sync --machine` writes into the
# shared venv). Toolchain managers (copy/git/doc + the git-pyjutsu pseudo-entry);
# testee is deliberately absent — it is a uv-declared per-repo dependency now.
_GOOD_LOCK = (
    '[repoman]\npackage = "repoman"\nsource = "path:/x"\n'
    '[managers.copy]\npackage = "copyroom"\nsource = "path:/x"\n'
    '[managers.git]\npackage = "gitman"\nsource = "path:/x"\n'
    '[managers.git-pyjutsu]\npackage = "pyjutsu"\nsource = "wheel:pyjutsu>=0.8"\n'
    '[managers.doc]\npackage = "docman"\nsource = "path:/x"\n'
)

# The consumer pyproject that declares testee the uv-native way (D4).
_PYPROJECT_TESTEE = (
    '[project]\nname = "x"\nversion = "0.0.0"\nrequires-python = ">=3.13"\n'
    'dependencies = []\n'
    '[dependency-groups]\ndev = ["testee"]\n'
)

#: Every pure-CLI manager command that lives in the shared toolchain venv.
_TOOLCHAIN_COMMANDS = ("repoman", "copyroom", "gitman", "docman")


def _names(result):
    return {c.name: c for c in result}


@pytest.fixture
def toolchain(tmp_path, monkeypatch):
    """A fake bootstrapped shared toolchain venv, wired via REPOMAN_TOOLCHAIN_VENV.

    Also pins `shutil.which` to resolve out of that venv's bin — modelling the PATH
    order `modules/devenv.nix` establishes (toolchain ahead of the consumer venv), so
    `installed:<key>` sees PATH and the task-exec path agreeing.
    """

    venv = tmp_path / "toolchain"
    bin_dir = venv / "bin"
    bin_dir.mkdir(parents=True)
    for command in _TOOLCHAIN_COMMANDS:
        (bin_dir / command).write_text("")
    monkeypatch.setenv("REPOMAN_TOOLCHAIN_VENV", str(venv))
    monkeypatch.delenv("DEVENV_STATE", raising=False)
    monkeypatch.delenv("DEVENV_ROOT", raising=False)
    monkeypatch.setattr(
        checks.shutil, "which",
        lambda c: str(bin_dir / c) if (bin_dir / c).exists() else None,
    )

    def write(manifest: str):
        (venv / "repoman-toolchain.toml").write_text(manifest)
        return venv

    write(_GOOD_LOCK)
    return types.SimpleNamespace(venv=venv, bin=bin_dir, write=write)


@pytest.fixture
def consumer_venv(tmp_path, monkeypatch):
    """A fake consumer devenv venv — where a uv-declared manager (testee) lands."""

    bin_dir = tmp_path / ".devenv" / "state" / "venv" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "testee").write_text("")
    monkeypatch.setenv("DEVENV_STATE", str(tmp_path / ".devenv" / "state"))
    return bin_dir


# ---------------------------------------------------------------- toolchain:venv


def test_missing_toolchain_venv_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("REPOMAN_TOOLCHAIN_VENV", str(tmp_path / "nope"))
    result = run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills")
    tv = _names(result)["toolchain:venv"]
    assert tv.level == "fail"
    assert "repoman-sync --machine" in tv.detail
    assert self_check_exit(result) == 2


def test_toolchain_venv_from_xdg_data_home(tmp_path, monkeypatch):
    monkeypatch.delenv("REPOMAN_TOOLCHAIN_VENV", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert checks.toolchain_venv() == tmp_path / "data" / "repoman" / "venv"


def test_toolchain_venv_from_home_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("REPOMAN_TOOLCHAIN_VENV", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(checks.Path, "home", lambda: tmp_path / "home")
    assert checks.toolchain_venv() == tmp_path / "home" / ".local" / "share" / "repoman" / "venv"


# ---------------------------------------------------------------- toolchain:lock


def test_unparseable_recorded_manifest_warns(toolchain):
    toolchain.write("this is = = not toml [")
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    tl = _names(result)["toolchain:lock"]
    # warn, not fail: a broken recorded manifest must not mask installed:* (the real signal).
    assert tl.level == "warn" and "unparseable" in tl.detail
    assert self_check_exit(result) == 0


def test_unreadable_recorded_manifest_warns_instead_of_raising(toolchain):
    # The doctor must survive the broken environments it exists to diagnose: a
    # permission error used to escape as a traceback.
    manifest = toolchain.venv / "repoman-toolchain.toml"
    manifest.chmod(0o000)
    try:
        result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    finally:
        manifest.chmod(0o644)
    tl = _names(result)["toolchain:lock"]
    assert tl.level == "warn" and "unreadable" in tl.detail


def test_missing_recorded_manifest_warns(toolchain, tmp_path, monkeypatch):
    (toolchain.venv / "repoman-toolchain.toml").unlink()
    monkeypatch.chdir(tmp_path)
    result = run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills")
    tl = _names(result)["toolchain:lock"]
    assert tl.level == "warn"
    assert "repoman-sync --machine" in tl.detail


def test_missing_self_entry_warns(toolchain):
    toolchain.write('[managers.git]\npackage = "gitman"\nsource = "path:/x"\n')
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    assert _names(result)["toolchain:self"].level == "warn"


# ---------------------------------------------------------------- lock:<key>


def test_selected_manager_absent_from_machine_lock_fails(toolchain):
    toolchain.write('[repoman]\npackage = "repoman"\nsource = "path:/x"\n')
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    assert _names(result)["lock:git"].level == "fail"


def test_native_pseudo_entry_satisfies_base_manager(toolchain):
    # git-pyjutsu pseudo-entry counts for the git manager (guide 1).
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    assert _names(result)["lock:git"].level == "ok"


def test_pseudo_entry_must_match_base_manager_exactly(toolchain):
    # "gitx-pyjutsu" splits to base "gitx", which must NOT satisfy the "git"
    # manager — only an exact base match counts (the positive case above).
    toolchain.write(
        '[repoman]\npackage = "repoman"\nsource = "path:/x"\n'
        '[managers.gitx-pyjutsu]\npackage = "pyjutsu"\nsource = "path:/x"\n'
    )
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    assert _names(result)["lock:git"].level == "fail"


def test_doc_lock_and_installed_ok(toolchain):
    result = run_self_check([REGISTRY["doc"]], ".", ".claude/skills")
    assert _names(result)["lock:doc"].level == "ok"
    assert _names(result)["installed:doc"].level == "ok"


# ---------------------------------------------------------------- installed:<key>


def test_uninstalled_toolchain_manager_fails(toolchain):
    (toolchain.bin / "gitman").unlink()
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    inst = _names(result)["installed:git"]
    assert inst.level == "fail" and "repoman-sync --machine" in inst.detail
    assert self_check_exit(result) == 2


def test_uninstalled_uv_manager_fails(toolchain, tmp_path):
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_TESTEE)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    inst = _names(result)["installed:test"]
    assert inst.level == "fail" and "uv sync" in inst.detail


def test_installed_validates_the_binary_the_tasks_exec(toolchain):
    # The nix tasks run "$toolchainBin"/gitman, so that is what must be validated —
    # not merely "something called gitman is somewhere on PATH".
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    assert _names(result)["installed:git"].detail == str(toolchain.bin / "gitman")


def test_installed_warns_when_path_shadows_the_toolchain(toolchain, tmp_path, monkeypatch):
    # A stale pre-migration copy in the consumer venv shadowing the shared toolchain is
    # the exact divergence the PATH order in modules/devenv.nix exists to prevent:
    # doctor would be green while `devenv tasks run` used a different binary.
    stale = tmp_path / "stale" / "gitman"
    stale.parent.mkdir()
    stale.write_text("")
    monkeypatch.setattr(checks.shutil, "which", lambda c: str(stale) if c == "gitman" else None)
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    inst = _names(result)["installed:git"]
    assert inst.level == "warn"
    assert str(stale) in inst.detail and str(toolchain.bin / "gitman") in inst.detail


def test_installed_missing_names_the_other_copy_on_path(toolchain, tmp_path, monkeypatch):
    (toolchain.bin / "gitman").unlink()
    elsewhere = tmp_path / "elsewhere" / "gitman"
    elsewhere.parent.mkdir()
    elsewhere.write_text("")
    monkeypatch.setattr(checks.shutil, "which", lambda c: str(elsewhere) if c == "gitman" else None)
    inst = _names(run_self_check([REGISTRY["git"]], ".", ".claude/skills"))["installed:git"]
    assert inst.level == "fail" and str(elsewhere) in inst.detail


def test_uv_manager_resolves_through_the_consumer_venv(toolchain, consumer_venv, tmp_path):
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_TESTEE)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    inst = _names(result)["installed:test"]
    assert inst.level == "ok" and inst.detail == str(consumer_venv / "testee")


# ---------------------------------------------------------------- uv:<key> (D5)


def test_uv_declared_manager_is_ok_from_dependency_groups(toolchain, tmp_path):
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_TESTEE)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    uv = _names(result)["uv:test"]
    assert uv.level == "ok" and "[dependency-groups] dev" in uv.detail


def test_uv_declared_manager_is_ok_from_optional_dependencies(toolchain, tmp_path):
    # the pre-PEP-735 style is still recognized (D4 keeps [dependency-groups] canonical).
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n'
        '[project.optional-dependencies]\ndev = ["testee>=0.2"]\n'
    )
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["uv:test"].level == "ok"


def test_uv_declared_manager_is_ok_from_project_dependencies(toolchain, tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n'
        'dependencies = ["testee"]\n'
    )
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["uv:test"].level == "ok"


def test_uv_manager_not_declared_fails(toolchain, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.0.0"\n')
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    uv = _names(result)["uv:test"]
    assert uv.level == "fail"
    assert "pyproject.toml" in uv.detail and "[dependency-groups]" in uv.detail
    assert self_check_exit(result) == 2


def test_uv_manager_requirement_specifier_and_extras_are_stripped(toolchain, tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n'
        '[dependency-groups]\n'
        'dev = ["testee[all]>=0.3 ; python_version>\'3.12\'"]\n'
    )
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["uv:test"].level == "ok"


def test_uv_manager_name_normalisation(toolchain, tmp_path):
    # PEP 503 normalisation: "TESTEE" matches package "testee" (case-folded).
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n'
        '[dependency-groups]\ndev = ["TESTEE"]\n'
    )
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["uv:test"].level == "ok"


def test_include_group_entries_are_skipped(toolchain, tmp_path):
    # dependency-groups entries may be {include-group = "lint"} dicts — don't crash.
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n'
        '[dependency-groups]\ndev = [{include-group = "lint"}]\n'
    )
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["uv:test"].level == "fail"


def test_non_list_dependency_table_is_skipped(toolchain, tmp_path):
    # A hand-mangled pyproject must produce a finding, not a TypeError.
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\ndependencies = "testee"\n'
    )
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["uv:test"].level == "fail"


def test_no_pyproject_fails_uv_check_cleanly(toolchain, tmp_path):
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    names = _names(result)
    assert names["uv:test"].level == "fail"
    assert "pyproject" not in names  # genuinely absent is not "broken"


def test_unparseable_pyproject_is_reported_not_raised(toolchain, tmp_path):
    (tmp_path / "pyproject.toml").write_text("this is not [ toml")
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    names = _names(result)
    assert names["pyproject"].level == "fail" and "unparseable" in names["pyproject"].detail


def test_unreadable_pyproject_is_reported_not_raised(toolchain, tmp_path):
    # A directory named pyproject.toml used to escape as IsADirectoryError.
    (tmp_path / "pyproject.toml").mkdir()
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["pyproject"].level == "fail"


def test_uv_manager_gets_no_lock_row(toolchain, tmp_path):
    # the regression CONCEPT §5.3 warns about: testee must never get a lock:test row.
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_TESTEE)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    names = _names(result)
    assert "lock:test" not in names
    assert names["uv:test"].level == "ok"


# ---------------------------------------------------------------- version:<key>


def _install_dist(venv, name, version):
    """Materialise a dist-info inside the fake toolchain venv's site-packages."""

    site = venv / "lib" / "python3.13" / "site-packages"
    dist = site / f"{name}-{version}.dist-info"
    dist.mkdir(parents=True)
    (dist / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n")
    return dist


def test_no_version_rows_when_site_packages_is_uninspectable(toolchain):
    # A venv we can't introspect yields NO version rows: a false staleness alarm from
    # the doctor is worse than a missing check.
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    assert not [c for c in result if c.name.startswith("version:")]


def test_version_ok_when_pin_is_satisfied(toolchain):
    _install_dist(toolchain.venv, "repoman", "0.5.0")
    _install_dist(toolchain.venv, "gitman", "0.4.2")
    _install_dist(toolchain.venv, "pyjutsu", "0.9.1")
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    names = _names(result)
    assert names["version:managers.git-pyjutsu"].level == "ok"
    assert "0.9.1" in names["version:managers.git-pyjutsu"].detail
    assert names["version:managers.git"].level == "ok"  # path: source pins nothing


def test_version_fails_when_the_installed_package_is_behind_the_pin(toolchain):
    # THE staleness case: `uv pip install` is add-only, so a machine that never
    # re-synced keeps an old pyjutsu while every other row reports green.
    _install_dist(toolchain.venv, "repoman", "0.5.0")
    _install_dist(toolchain.venv, "gitman", "0.4.2")
    _install_dist(toolchain.venv, "pyjutsu", "0.7.0")
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    row = _names(result)["version:managers.git-pyjutsu"]
    assert row.level == "fail"
    assert ">=0.8" in row.detail and "0.7.0" in row.detail
    assert self_check_exit(result) == 2


def test_version_fails_when_a_pinned_package_is_absent(toolchain):
    _install_dist(toolchain.venv, "repoman", "0.5.0")
    _install_dist(toolchain.venv, "gitman", "0.4.2")
    row = _names(run_self_check([REGISTRY["git"]], ".", ".claude/skills"))["version:managers.git-pyjutsu"]
    assert row.level == "fail" and "not installed" in row.detail


def test_version_checks_exact_git_ref_pins(toolchain):
    toolchain.write(
        '[repoman]\npackage = "repoman"\nsource = "path:/x"\n'
        '[managers.git]\npackage = "gitman"\n'
        'source = "git+https://github.com/Bullish-Design/gitman@v0.4.2"\n'
    )
    _install_dist(toolchain.venv, "repoman", "0.5.0")
    _install_dist(toolchain.venv, "gitman", "0.3.0")
    row = _names(run_self_check([REGISTRY["git"]], ".", ".claude/skills"))["version:managers.git"]
    assert row.level == "fail" and "==0.4.2" in row.detail


def test_version_ignores_managers_outside_the_roster(toolchain):
    _install_dist(toolchain.venv, "repoman", "0.5.0")
    _install_dist(toolchain.venv, "gitman", "0.4.2")
    _install_dist(toolchain.venv, "pyjutsu", "0.9.0")
    names = _names(run_self_check([REGISTRY["git"]], ".", ".claude/skills"))
    assert "version:managers.doc" not in names
    assert "version:managers.copy" not in names


def test_version_does_not_guess_on_prerelease_versions(toolchain):
    # 0.8.0rc1 vs >=0.8 has no honest answer without full PEP 440 parsing — report the
    # installed version rather than inventing an ordering.
    _install_dist(toolchain.venv, "repoman", "0.5.0")
    _install_dist(toolchain.venv, "gitman", "0.4.2")
    _install_dist(toolchain.venv, "pyjutsu", "0.8.0rc1")
    row = _names(run_self_check([REGISTRY["git"]], ".", ".claude/skills"))["version:managers.git-pyjutsu"]
    assert row.level == "ok" and "0.8.0rc1" in row.detail


@pytest.mark.parametrize(
    ("installed", "operator", "wanted", "expected"),
    [
        ("1.0", "==", "1.0.0", True),      # zero-padded equality, per PEP 440
        ("0.9", ">=", "0.8", True),
        ("0.7", ">=", "0.8", False),
        ("1.2.3", "<", "1.10.0", True),    # numeric, not lexicographic
        ("1.0rc1", ">=", "1.0", None),     # not evaluable → not evaluated
    ],
)
def test_satisfies_matrix(installed, operator, wanted, expected):
    assert checks._satisfies(installed, operator, wanted) is expected


# ---------------------------------------------------------------- lock:orphan


def test_orphan_repo_lock_warns(toolchain, consumer_venv, tmp_path):
    (tmp_path / "repoman.lock").write_text(_GOOD_LOCK)
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_TESTEE)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    orphan = _names(result)["lock:orphan"]
    assert orphan.level == "warn" and "delete this file" in orphan.detail
    assert self_check_exit(result) == 0


# ---------------------------------------------------------------- skill:*


def test_entrypoint_skill_missing_warns(toolchain, tmp_path):
    result = run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills")
    assert _names(result)["skill:entrypoint"].level == "warn"


def test_sub_skill_without_deferral_warns(toolchain, tmp_path):
    sub = tmp_path / ".claude/skills" / "gitman" / "SKILL.md"
    sub.parent.mkdir(parents=True)
    sub.write_text("---\nname: gitman\n---\nNo deferral footer here.\n")
    result = run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills")
    assert _names(result)["skill:git:defers"].level == "warn"


def test_sub_skill_with_deferral_ok(toolchain, tmp_path):
    sub = tmp_path / ".claude/skills" / "gitman" / "SKILL.md"
    sub.parent.mkdir(parents=True)
    sub.write_text("For when to verify vs commit, see the `repoman` skill.\n")
    result = run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills")
    assert _names(result)["skill:git:defers"].level == "ok"


def test_non_utf8_sub_skill_warns_instead_of_raising(toolchain, tmp_path):
    # A stray binary SKILL.md used to blow up the whole doctor with UnicodeDecodeError.
    sub = tmp_path / ".claude/skills" / "gitman" / "SKILL.md"
    sub.parent.mkdir(parents=True)
    sub.write_bytes(b"\xff\xfe\x00 not utf-8")
    result = run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills")
    assert _names(result)["skill:git:defers"].level == "warn"


# ---------------------------------------------------------------- provisioned:<key>


def test_provisioned_warns_when_input_signal_absent(toolchain, monkeypatch):
    # doc is approach-B: CLI installed (installed:doc ok) but no REPOMAN_PROVISIONED_DOC
    # → provisioned:doc warns, and warn is non-fatal so the aggregate exit stays 0.
    monkeypatch.delenv("REPOMAN_PROVISIONED_DOC", raising=False)
    result = run_self_check([REGISTRY["doc"]], ".", ".claude/skills")
    prov = _names(result)["provisioned:doc"]
    assert prov.level == "warn"
    assert "docman" in prov.detail and "devenv.yaml" in prov.detail
    assert self_check_exit(result) == 0


def test_provisioned_ok_when_input_signalled(toolchain, monkeypatch):
    monkeypatch.setenv("REPOMAN_PROVISIONED_DOC", "1")
    result = run_self_check([REGISTRY["doc"]], ".", ".claude/skills")
    assert _names(result)["provisioned:doc"].level == "ok"


def test_no_provisioned_row_for_approach_a_manager(toolchain):
    # copy (approach-A, nix_input="") gets no provisioned: row at all.
    result = run_self_check([REGISTRY["copy"]], ".", ".claude/skills")
    assert "provisioned:copy" not in _names(result)


# ---------------------------------------------------------------- level mapping


def test_self_check_exit_unknown_level_falls_back_to_2():
    # A level outside ok/warn/fail maps to fail (2), never silently 0 — a future
    # level that forgets the mapping can't hide a broken wiring.
    assert self_check_exit([checks.SelfCheck("x", "??")]) == 2


def test_format_self_check_unknown_level_is_question_marked():
    formatted = checks.format_self_check([checks.SelfCheck("x", "??", "detail")])
    assert "? x — detail" in formatted


# ---------------------------------------------------------------- full roster


def test_healthy_wiring_is_all_ok(toolchain, consumer_venv, tmp_path, monkeypatch):
    # the full roster, healthy: toolchain manifest + binaries + testee declared + skill.
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_TESTEE)
    skill = tmp_path / ".claude/skills" / "repoman" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: repoman\n---\n")
    monkeypatch.setenv("REPOMAN_PROVISIONED_DOC", "1")
    managers = list(REGISTRY.values())
    result = run_self_check(managers, str(tmp_path), ".claude/skills")
    names = _names(result)
    assert self_check_exit(result) == 0
    assert all(c.level == "ok" for c in result), [c for c in result if c.level != "ok"]
    # toolchain managers are validated against the machine manifest; testee is uv-declared.
    assert {n for n in names if n.startswith("lock:")} == {"lock:copy", "lock:git", "lock:doc"}
    assert names["uv:test"].level == "ok"
    assert {n for n in names if n.startswith("provisioned:")} == {"provisioned:doc"}


# ---------------------------------------------------------------- skill-ownership


def test_ownership_warns_when_nothing_installed(tmp_path):
    result = skill_ownership_checks(str(tmp_path), ".agents/skills")
    names = _names(result)
    assert names["skill:tool-shipped"].level == "warn"
    # warn is non-fatal under the shared exit mapping.
    assert self_check_exit(result) == 0


def test_ownership_ok_after_canonical_skills_present(tmp_path):
    skills = tmp_path / ".agents/skills"
    from repoman.devman.check import CANONICAL_COPYROOM_SKILLS

    for name in CANONICAL_COPYROOM_SKILLS:
        skill = skills / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    result = skill_ownership_checks(str(tmp_path), ".agents/skills")
    names = _names(result)
    assert names["skill:tool-shipped"].level == "ok"


def test_ownership_survives_an_unreadable_skills_dir(tmp_path):
    skills = tmp_path / ".agents/skills"
    skills.mkdir(parents=True)
    skills.chmod(0o000)
    try:
        result = skill_ownership_checks(str(tmp_path), ".agents/skills")
    finally:
        skills.chmod(0o755)
    assert _names(result)["skill:tool-shipped"].level == "warn"


def test_malformed_manifest_entries_are_skipped_not_crashed(toolchain):
    # A hand-mangled machine manifest must not take the version check down with it.
    toolchain.write(
        '[repoman]\npackage = "repoman"\nsource = "path:/x"\n'
        '[managers]\ngit = "oops-not-a-table"\n'
    )
    _install_dist(toolchain.venv, "repoman", "0.5.0")
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    names = _names(result)
    assert names["version:repoman"].level == "ok"
    assert "version:managers.git" not in names


def test_manifest_entry_with_non_string_source_is_skipped(toolchain):
    toolchain.write(
        '[repoman]\npackage = "repoman"\nsource = "path:/x"\n'
        '[managers.git]\npackage = "gitman"\nsource = 42\n'
    )
    _install_dist(toolchain.venv, "repoman", "0.5.0")
    _install_dist(toolchain.venv, "gitman", "0.4.2")
    names = _names(run_self_check([REGISTRY["git"]], ".", ".claude/skills"))
    assert "version:managers.git" not in names


def test_unreadable_sub_skill_warns_instead_of_raising(toolchain, tmp_path):
    sub = tmp_path / ".claude/skills" / "gitman" / "SKILL.md"
    sub.parent.mkdir(parents=True)
    sub.write_text("whatever")
    sub.chmod(0o000)
    try:
        result = run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills")
    finally:
        sub.chmod(0o644)
    row = _names(result)["skill:git:defers"]
    assert row.level == "warn" and "unreadable" in row.detail
