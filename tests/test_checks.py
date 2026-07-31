import repoman.checks as checks
from repoman.checks import run_self_check, self_check_exit
from repoman.devman.check import devman_checks
from repoman.devman.install import MANIFEST, install_devman
from repoman.registry import REGISTRY

_GOOD_LOCK = '[repoman]\npackage="repoman"\nsource="path:/x"\n'


def _names(result):
    return {c.name: c for c in result}


def test_missing_lock_fails(tmp_path):
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert any(c.name == "lock" and c.level == "fail" for c in result)
    assert self_check_exit(result) == 2


def test_selected_manager_absent_from_lock_fails(tmp_path):
    (tmp_path / "repoman.lock").write_text(_GOOD_LOCK)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert any(c.name == "lock:test" and c.level == "fail" for c in result)


def test_unparseable_lock_fails(tmp_path):
    (tmp_path / "repoman.lock").write_text("this is = = not toml [")
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    lock = _names(result)["lock"]
    assert lock.level == "fail" and "unparseable" in lock.detail


def test_missing_self_entry_warns(tmp_path):
    (tmp_path / "repoman.lock").write_text('[managers.test]\npackage="testee"\nsource="path:/x"\n')
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["lock:self"].level == "warn"


def test_native_pseudo_entry_satisfies_base_manager(tmp_path, monkeypatch):
    # git-pyjutsu pseudo-entry counts for the git manager (guide 1).
    (tmp_path / "repoman.lock").write_text(_GOOD_LOCK + '[managers.git-pyjutsu]\npackage="pyjutsu"\nsource="path:/x"\n')
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills")
    assert _names(result)["lock:git"].level == "ok"


def test_pseudo_entry_must_match_base_manager_exactly(tmp_path, monkeypatch):
    # "gitx-pyjutsu" splits to base "gitx", which must NOT satisfy the "git"
    # manager — only an exact base match counts (the positive case above).
    (tmp_path / "repoman.lock").write_text(
        _GOOD_LOCK + '[managers.gitx-pyjutsu]\npackage="pyjutsu"\nsource="path:/x"\n'
    )
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills")
    assert _names(result)["lock:git"].level == "fail"


def test_self_check_exit_unknown_level_falls_back_to_2():
    # A level outside ok/warn/fail maps to fail (2), never silently 0 — a future
    # level that forgets the mapping can't hide a broken wiring.
    assert self_check_exit([checks.SelfCheck("x", "??")]) == 2


def test_format_self_check_unknown_level_is_question_marked():
    formatted = checks.format_self_check([checks.SelfCheck("x", "??", "detail")])
    assert "? x — detail" in formatted


def test_session_lock_and_installed_ok(tmp_path, monkeypatch):
    (tmp_path / "repoman.lock").write_text(_GOOD_LOCK + '[managers.session]\npackage="zelligate"\nsource="path:/x"\n')
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["session"]], str(tmp_path), ".claude/skills")
    assert _names(result)["lock:session"].level == "ok"
    assert _names(result)["installed:session"].level == "ok"


def test_agent_lock_and_installed_ok(tmp_path, monkeypatch):
    # agent's lock key/package/command mismatch: key "agent", package "mypi-agent",
    # command "mypi". installed:agent checks shutil.which("mypi") — the command.
    (tmp_path / "repoman.lock").write_text(_GOOD_LOCK + '[managers.agent]\npackage="mypi-agent"\nsource="path:/x"\n')
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["agent"]], str(tmp_path), ".claude/skills")
    assert _names(result)["lock:agent"].level == "ok"
    assert _names(result)["installed:agent"].level == "ok"


def test_doc_lock_and_installed_ok(tmp_path, monkeypatch):
    (tmp_path / "repoman.lock").write_text(_GOOD_LOCK + '[managers.doc]\npackage="docman"\nsource="path:/x"\n')
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["doc"]], str(tmp_path), ".claude/skills")
    assert _names(result)["lock:doc"].level == "ok"
    assert _names(result)["installed:doc"].level == "ok"


def test_spec_lock_and_installed_ok(tmp_path, monkeypatch):
    # spec's command is "alliman" (not the 3rd-party "allium"); installed:spec checks
    # shutil.which("alliman").
    (tmp_path / "repoman.lock").write_text(_GOOD_LOCK + '[managers.spec]\npackage="alliman"\nsource="path:/x"\n')
    seen = {}
    monkeypatch.setattr(checks.shutil, "which", lambda c: seen.setdefault(c, "/usr/bin/" + c))
    result = run_self_check([REGISTRY["spec"]], str(tmp_path), ".claude/skills")
    assert _names(result)["lock:spec"].level == "ok"
    assert _names(result)["installed:spec"].level == "ok"
    assert "alliman" in seen and "allium" not in seen  # never probes the 3rd-party binary


def test_uninstalled_manager_fails(tmp_path, monkeypatch):
    (tmp_path / "repoman.lock").write_text(_GOOD_LOCK + '[managers.test]\npackage="testee"\nsource="path:/x"\n')
    monkeypatch.setattr(checks.shutil, "which", lambda _c: None)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    inst = _names(result)["installed:test"]
    assert inst.level == "fail" and "repoman-sync" in inst.detail
    assert self_check_exit(result) == 2


def test_entrypoint_skill_missing_warns(tmp_path, monkeypatch):
    (tmp_path / "repoman.lock").write_text(_GOOD_LOCK + '[managers.test]\npackage="testee"\nsource="path:/x"\n')
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["skill:entrypoint"].level == "warn"


def test_healthy_wiring_is_all_ok(tmp_path, monkeypatch):
    (tmp_path / "repoman.lock").write_text(_GOOD_LOCK + '[managers.test]\npackage="testee"\nsource="path:/x"\n')
    skill = tmp_path / ".claude/skills" / "repoman" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: repoman\n---\n")
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert self_check_exit(result) == 0
    assert all(c.level == "ok" for c in result)


def test_sub_skill_without_deferral_warns(tmp_path, monkeypatch):
    (tmp_path / "repoman.lock").write_text(_GOOD_LOCK + '[managers.test]\npackage="testee"\nsource="path:/x"\n')
    sub = tmp_path / ".claude/skills" / "testee" / "SKILL.md"
    sub.parent.mkdir(parents=True)
    sub.write_text("---\nname: testee\n---\nNo deferral footer here.\n")
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["skill:test:defers"].level == "warn"


def test_sub_skill_with_deferral_ok(tmp_path, monkeypatch):
    (tmp_path / "repoman.lock").write_text(_GOOD_LOCK + '[managers.test]\npackage="testee"\nsource="path:/x"\n')
    sub = tmp_path / ".claude/skills" / "testee" / "SKILL.md"
    sub.parent.mkdir(parents=True)
    sub.write_text("For when to verify vs commit, see the `repoman` skill.\n")
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["skill:test:defers"].level == "ok"


# --- provisioned:<key> (nix-layer presence) --------------------------------


def test_provisioned_warns_when_input_signal_absent(tmp_path, monkeypatch):
    # doc is approach-B: CLI installed (installed:doc ok) but no REPOMAN_PROVISIONED_DOC
    # → provisioned:doc warns, and warn is non-fatal so the aggregate exit stays 0.
    (tmp_path / "repoman.lock").write_text(_GOOD_LOCK + '[managers.doc]\npackage="docman"\nsource="path:/x"\n')
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    monkeypatch.delenv("REPOMAN_PROVISIONED_DOC", raising=False)
    result = run_self_check([REGISTRY["doc"]], str(tmp_path), ".claude/skills")
    prov = _names(result)["provisioned:doc"]
    assert prov.level == "warn"
    assert "docman" in prov.detail and "devenv.yaml" in prov.detail
    assert self_check_exit(result) == 0


def test_provisioned_ok_when_input_signalled(tmp_path, monkeypatch):
    (tmp_path / "repoman.lock").write_text(_GOOD_LOCK + '[managers.doc]\npackage="docman"\nsource="path:/x"\n')
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    monkeypatch.setenv("REPOMAN_PROVISIONED_DOC", "1")
    result = run_self_check([REGISTRY["doc"]], str(tmp_path), ".claude/skills")
    assert _names(result)["provisioned:doc"].level == "ok"


def test_no_provisioned_row_for_approach_a_manager(tmp_path, monkeypatch):
    # copy (approach-A, nix_input="") gets no provisioned: row at all.
    (tmp_path / "repoman.lock").write_text(_GOOD_LOCK + '[managers.copy]\npackage="copyroom"\nsource="path:/x"\n')
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["copy"]], str(tmp_path), ".claude/skills")
    assert "provisioned:copy" not in _names(result)


# --- full-roster capstone (Phase 6) ----------------------------------------


def test_full_roster_self_check_is_green(tmp_path, monkeypatch):
    """The whole roster, healthy: lock + PATH + provisioning signals → all OK, exit 0.

    Locks in the Phase 1-5 bridge wiring at the unit level: every selected manager
    is installed (venv CLI) and — for the three approach-B managers — provisioned
    (nix module imported). The capstone end-to-end re-verify lives in the
    consumer-example; this guards the self-check shape against regression.
    """
    managers = list(REGISTRY.values())
    lock = _GOOD_LOCK
    for key in REGISTRY:
        lock += f'[managers.{key}]\npackage="{key}"\nsource="path:/x"\n'
    # gitman's native-dep pseudo-entry (resolved off the selected "git").
    lock += '[managers.git-pyjutsu]\npackage="pyjutsu"\nsource="path:/x"\n'
    (tmp_path / "repoman.lock").write_text(lock)
    skill = tmp_path / ".claude/skills" / "repoman" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: repoman\n---\n")
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    for key in ("doc", "spec", "agent"):
        monkeypatch.setenv(f"REPOMAN_PROVISIONED_{key.upper()}", "1")

    result = run_self_check(managers, str(tmp_path), ".claude/skills")
    names = _names(result)
    assert self_check_exit(result) == 0
    assert all(c.level == "ok" for c in result)
    # Exactly the three approach-B managers get a provisioned: row, all OK.
    assert {n for n in names if n.startswith("provisioned:")} == {
        "provisioned:doc",
        "provisioned:spec",
        "provisioned:agent",
    }


# --- devman self-checks ----------------------------------------------------


def test_devman_warns_when_nothing_installed(tmp_path):
    result = devman_checks(str(tmp_path), ".claude/skills", ".agents/devenv")
    names = _names(result)
    assert names["devman:skills"].level == "warn"
    assert names["devman:docs"].level == "warn"
    # No manifest yet → no devman:current row.
    assert "devman:current" not in names
    # warn is non-fatal under the shared exit mapping.
    assert self_check_exit(result) == 0


def test_devman_ok_after_install(tmp_path):
    install_devman(".claude/skills", ".agents/devenv", str(tmp_path))
    result = devman_checks(str(tmp_path), ".claude/skills", ".agents/devenv")
    names = _names(result)
    assert names["devman:skills"].level == "ok"
    assert names["devman:docs"].level == "ok"
    assert names["devman:current"].level == "ok"


def test_devman_stale_manifest_warns(tmp_path):
    install_devman(".claude/skills", ".agents/devenv", str(tmp_path))
    manifest = tmp_path / ".claude/skills" / MANIFEST
    manifest.write_text("repoman version: 0.0.0-ancient\nskills: \n")
    result = devman_checks(str(tmp_path), ".claude/skills", ".agents/devenv")
    assert _names(result)["devman:current"].level == "warn"
