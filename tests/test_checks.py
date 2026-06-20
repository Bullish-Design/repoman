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
    (tmp_path / "repoman.lock").write_text(
        _GOOD_LOCK + '[managers.git-pyjutsu]\npackage="pyjutsu"\nsource="path:/x"\n'
    )
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills")
    assert _names(result)["lock:git"].level == "ok"


def test_session_lock_and_installed_ok(tmp_path, monkeypatch):
    (tmp_path / "repoman.lock").write_text(
        _GOOD_LOCK + '[managers.session]\npackage="zelligate"\nsource="path:/x"\n'
    )
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["session"]], str(tmp_path), ".claude/skills")
    assert _names(result)["lock:session"].level == "ok"
    assert _names(result)["installed:session"].level == "ok"


def test_uninstalled_manager_fails(tmp_path, monkeypatch):
    (tmp_path / "repoman.lock").write_text(
        _GOOD_LOCK + '[managers.test]\npackage="testee"\nsource="path:/x"\n'
    )
    monkeypatch.setattr(checks.shutil, "which", lambda _c: None)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    inst = _names(result)["installed:test"]
    assert inst.level == "fail" and "repoman-sync" in inst.detail
    assert self_check_exit(result) == 2


def test_entrypoint_skill_missing_warns(tmp_path, monkeypatch):
    (tmp_path / "repoman.lock").write_text(
        _GOOD_LOCK + '[managers.test]\npackage="testee"\nsource="path:/x"\n'
    )
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["skill:entrypoint"].level == "warn"


def test_healthy_wiring_is_all_ok(tmp_path, monkeypatch):
    (tmp_path / "repoman.lock").write_text(
        _GOOD_LOCK + '[managers.test]\npackage="testee"\nsource="path:/x"\n'
    )
    skill = tmp_path / ".claude/skills" / "repoman" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: repoman\n---\n")
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert self_check_exit(result) == 0
    assert all(c.level == "ok" for c in result)


def test_sub_skill_without_deferral_warns(tmp_path, monkeypatch):
    (tmp_path / "repoman.lock").write_text(
        _GOOD_LOCK + '[managers.test]\npackage="testee"\nsource="path:/x"\n'
    )
    sub = tmp_path / ".claude/skills" / "testee" / "SKILL.md"
    sub.parent.mkdir(parents=True)
    sub.write_text("---\nname: testee\n---\nNo deferral footer here.\n")
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["skill:test:defers"].level == "warn"


def test_sub_skill_with_deferral_ok(tmp_path, monkeypatch):
    (tmp_path / "repoman.lock").write_text(
        _GOOD_LOCK + '[managers.test]\npackage="testee"\nsource="path:/x"\n'
    )
    sub = tmp_path / ".claude/skills" / "testee" / "SKILL.md"
    sub.parent.mkdir(parents=True)
    sub.write_text("For when to verify vs commit, see the `repoman` skill.\n")
    monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
    result = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert _names(result)["skill:test:defers"].level == "ok"


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
