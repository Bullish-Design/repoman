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


def _names(result):
    return {c.name: c for c in result}


@pytest.fixture
def toolchain(tmp_path, monkeypatch):
    """A fake bootstrapped shared toolchain venv, wired via REPOMAN_TOOLCHAIN_VENV."""

    venv = tmp_path / "toolchain"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "repoman").write_text("")
    monkeypatch.setenv("REPOMAN_TOOLCHAIN_VENV", str(venv))

    def write(manifest: str):
        (venv / "repoman-toolchain.toml").write_text(manifest)
        return venv

    write(_GOOD_LOCK)
    return types.SimpleNamespace(venv=venv, write=write)


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


def test_unparseable_recorded_manifest_warns(toolchain, monkeypatch):
    toolchain.write("this is = = not toml [")
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    tl = _names(result)["toolchain:lock"]
    # warn, not fail: a broken recorded manifest must not mask installed:* (the real signal).
    assert tl.level == "warn" and "unparseable" in tl.detail
    assert self_check_exit(result) == 0


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


def test_native_pseudo_entry_satisfies_base_manager(toolchain, monkeypatch):
    # git-pyjutsu pseudo-entry counts for the git manager (guide 1).
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    assert _names(result)["lock:git"].level == "ok"


def test_pseudo_entry_must_match_base_manager_exactly(toolchain, monkeypatch):
    # "gitx-pyjutsu" splits to base "gitx", which must NOT satisfy the "git"
    # manager — only an exact base match counts (the positive case above).
    toolchain.write(
        '[repoman]\npackage = "repoman"\nsource = "path:/x"\n'
        '[managers.gitx-pyjutsu]\npackage = "pyjutsu"\nsource = "path:/x"\n'
    )
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    assert _names(result)["lock:git"].level == "fail"


def test_doc_lock_and_installed_ok(toolchain, monkeypatch):
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["doc"]], ".", ".claude/skills")
    assert _names(result)["lock:doc"].level == "ok"
    assert _names(result)["installed:doc"].level == "ok"


# ---------------------------------------------------------------- installed:<key>


def test_uninstalled_toolchain_manager_fails(toolchain, monkeypatch):
    monkeypatch.setattr(checks.shutil, "which", lambda _c: None)
    result = run_self_check([REGISTRY["git"]], ".", ".claude/skills")
    inst = _names(result)["installed:git"]
    assert inst.level == "fail" and "repoman-sync --machine" in inst.detail
    assert self_check_exit(result) == 2


def test_uninstalled_uv_manager_fails(toolchain, monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_TESTEE)
    monkeypatch.setattr(checks.shutil, "which", lambda _c: None)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    inst = _names(result)["installed:test"]
    assert inst.level == "fail" and "uv sync" in inst.detail


# ---------------------------------------------------------------- uv:<key> (D5)


def test_uv_declared_manager_is_ok_from_dependency_groups(toolchain, tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_TESTEE)
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    uv = _names(result)["uv:test"]
    assert uv.level == "ok" and "[dependency-groups] dev" in uv.detail


def test_uv_declared_manager_is_ok_from_optional_dependencies(toolchain, tmp_path, monkeypatch):
    # the pre-PEP-735 style is still recognized (D4 keeps [dependency-groups] canonical).
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n'
        '[project.optional-dependencies]\ndev = ["testee>=0.2"]\n'
    )
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["uv:test"].level == "ok"


def test_uv_declared_manager_is_ok_from_project_dependencies(toolchain, tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n'
        'dependencies = ["testee"]\n'
    )
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["uv:test"].level == "ok"


def test_uv_manager_not_declared_fails(toolchain, tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.0.0"\n')
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    uv = _names(result)["uv:test"]
    assert uv.level == "fail"
    assert "pyproject.toml" in uv.detail and "[dependency-groups]" in uv.detail
    assert self_check_exit(result) == 2


def test_uv_manager_requirement_specifier_and_extras_are_stripped(toolchain, tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n'
        '[dependency-groups]\n'
        'dev = ["testee[all]>=0.3 ; python_version>\'3.12\'"]\n'
    )
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["uv:test"].level == "ok"


def test_uv_manager_name_normalisation(toolchain, tmp_path, monkeypatch):
    # PEP 503 normalisation: "TESTEE" matches package "testee" (case-folded).
    # (Note: "test_ee" normalises to "test-ee", a different name — deliberately
    # not tested as a match; the underscore-fold direction is covered by
    # test_uv_manager_requirement_specifier_and_extras_are_stripped.)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n'
        '[dependency-groups]\ndev = ["TESTEE"]\n'
    )
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["uv:test"].level == "ok"


def test_include_group_entries_are_skipped(toolchain, tmp_path, monkeypatch):
    # dependency-groups entries may be {include-group = "lint"} dicts — don't crash.
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n'
        '[dependency-groups]\ndev = [{include-group = "lint"}]\n'
    )
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["uv:test"].level == "fail"


def test_no_pyproject_fails_uv_check_cleanly(toolchain, tmp_path, monkeypatch):
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["uv:test"].level == "fail"


def test_uv_manager_gets_no_lock_row(toolchain, tmp_path, monkeypatch):
    # the regression CONCEPT §5.3 warns about: testee must never get a lock:test row.
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_TESTEE)
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    names = _names(result)
    assert "lock:test" not in names
    assert names["uv:test"].level == "ok"


# ---------------------------------------------------------------- lock:orphan


def test_orphan_repo_lock_warns(toolchain, tmp_path, monkeypatch):
    (tmp_path / "repoman.lock").write_text(_GOOD_LOCK)
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_TESTEE)
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    orphan = _names(result)["lock:orphan"]
    assert orphan.level == "warn" and "delete this file" in orphan.detail
    assert self_check_exit(result) == 0  # non-fatal


# ---------------------------------------------------------------- skill:*


def test_entrypoint_skill_missing_warns(toolchain, tmp_path, monkeypatch):
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills")
    assert _names(result)["skill:entrypoint"].level == "warn"


def test_sub_skill_without_deferral_warns(toolchain, tmp_path, monkeypatch):
    sub = tmp_path / ".claude/skills" / "gitman" / "SKILL.md"
    sub.parent.mkdir(parents=True)
    sub.write_text("---\nname: gitman\n---\nNo deferral footer here.\n")
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills")
    assert _names(result)["skill:git:defers"].level == "warn"


def test_sub_skill_with_deferral_ok(toolchain, tmp_path, monkeypatch):
    sub = tmp_path / ".claude/skills" / "gitman" / "SKILL.md"
    sub.parent.mkdir(parents=True)
    sub.write_text("For when to verify vs commit, see the `repoman` skill.\n")
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills")
    assert _names(result)["skill:git:defers"].level == "ok"


# ---------------------------------------------------------------- provisioned:<key>


def test_provisioned_warns_when_input_signal_absent(toolchain, monkeypatch):
    # doc is approach-B: CLI installed (installed:doc ok) but no REPOMAN_PROVISIONED_DOC
    # → provisioned:doc warns, and warn is non-fatal so the aggregate exit stays 0.
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    monkeypatch.delenv("REPOMAN_PROVISIONED_DOC", raising=False)
    result = run_self_check([REGISTRY["doc"]], ".", ".claude/skills")
    prov = _names(result)["provisioned:doc"]
    assert prov.level == "warn"
    assert "docman" in prov.detail and "devenv.yaml" in prov.detail
    assert self_check_exit(result) == 0


def test_provisioned_ok_when_input_signalled(toolchain, monkeypatch):
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    monkeypatch.setenv("REPOMAN_PROVISIONED_DOC", "1")
    result = run_self_check([REGISTRY["doc"]], ".", ".claude/skills")
    assert _names(result)["provisioned:doc"].level == "ok"


def test_no_provisioned_row_for_approach_a_manager(toolchain, monkeypatch):
    # copy (approach-A, nix_input="") gets no provisioned: row at all.
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
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


def test_healthy_wiring_is_all_ok(toolchain, tmp_path, monkeypatch):
    # the full roster, healthy: toolchain manifest + PATH + testee declared + skill.
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT_TESTEE)
    skill = tmp_path / ".claude/skills" / "repoman" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: repoman\n---\n")
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    monkeypatch.setenv("REPOMAN_PROVISIONED_DOC", "1")
    managers = list(REGISTRY.values())
    result = run_self_check(managers, str(tmp_path), ".claude/skills")
    names = _names(result)
    assert self_check_exit(result) == 0
    assert all(c.level == "ok" for c in result)
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
