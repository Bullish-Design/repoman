# Drives the real, embedded resolver in modules/scripts/repoman-sync.sh against fixture
# locks, with `uv`/`repoman` stubbed on PATH. Covers the wheel: source kind, path: editable
# resolution, and the wheel:/UV_FIND_LINKS guard (issue #1).
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "modules" / "scripts" / "repoman-sync.sh"

REPO_SELF = '[repoman]\npackage = "repoman"\nsource = "path:/repo/repoman"\n'
GIT_MANAGER = '[managers.git]\npackage = "gitman"\nsource = "path:/repo/gitman"\n'
GIT_PYJUTSU_WHEEL = '[managers.git-pyjutsu]\npackage = "pyjutsu"\nsource = "wheel:pyjutsu>=0.8"\n'


def _run(tmp_path, lock_body, managers="git", find_links=None):
    (tmp_path / "repoman.lock").write_text(lock_body)

    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    for name in ("uv", "repoman"):
        p = stub_bin / name
        p.write_text("#!/usr/bin/env bash\nexit 0\n")
        p.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{stub_bin}{os.pathsep}{env['PATH']}"
    env["DEVENV_ROOT"] = str(tmp_path)
    env["REPOMAN_MANAGERS"] = managers
    env.pop("UV_FIND_LINKS", None)
    if find_links is not None:
        env["UV_FIND_LINKS"] = find_links

    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)


def test_wheel_source_resolves_to_bare_requirement(tmp_path):
    # wheel:pyjutsu>=0.8 -> pyjutsu>=0.8 (uv resolves it from UV_FIND_LINKS).
    r = _run(
        tmp_path,
        REPO_SELF + GIT_MANAGER + GIT_PYJUTSU_WHEEL,
        managers="git",
        find_links=str(tmp_path / "wheelhouse"),
    )
    assert r.returncode == 0, r.stderr
    assert "pyjutsu>=0.8" in r.stdout
    assert "wheel:" not in r.stdout  # the prefix is stripped, not passed to uv


def test_path_source_resolves_to_editable(tmp_path):
    r = _run(tmp_path, REPO_SELF + GIT_MANAGER, managers="git")
    assert r.returncode == 0, r.stderr
    assert "--editable=/repo/gitman" in r.stdout


def test_wheel_guard_aborts_without_find_links(tmp_path):
    # A wheel: source with no wheelhouse must fail loudly before any install.
    r = _run(
        tmp_path,
        REPO_SELF + GIT_MANAGER + GIT_PYJUTSU_WHEEL,
        managers="git",
        find_links=None,
    )
    assert r.returncode == 2
    assert "UV_FIND_LINKS is unset" in r.stderr
    assert "pyjutsu>=0.8" in r.stderr  # names the offending source


def test_no_wheel_source_does_not_trip_guard(tmp_path):
    # path:/git+ locks resolve fine with UV_FIND_LINKS unset (no regression).
    r = _run(tmp_path, REPO_SELF + GIT_MANAGER, managers="git", find_links=None)
    assert r.returncode == 0, r.stderr


def test_git_https_source_passes_through_verbatim(tmp_path):
    # An unrecognized source kind (git+https://…@ref) goes to uv verbatim: no
    # prefix strip, no --editable. A regression that mangled git sources would
    # surface here — uv must resolve the name/ref itself.
    lock_body = (
        REPO_SELF
        + '[managers.git]\npackage = "gitman"\nsource = "git+https://github.com/Bullish-Design/gitman@v0.3.0"\n'
    )
    r = _run(tmp_path, lock_body, managers="git")
    assert r.returncode == 0, r.stderr
    # Emitted verbatim — no prefix strip, no --editable on the git source itself
    # (the lock's own path: self-entry may legitimately resolve editable).
    assert "git+https://github.com/Bullish-Design/gitman@v0.3.0" in r.stdout
    assert "--editable=git+https" not in r.stdout
    assert "git+https" not in r.stderr
