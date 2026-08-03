# Drives the real, embedded resolver in modules/scripts/repoman-sync.sh against fixture
# locks, with `uv`/`repoman` stubbed on PATH. Covers both modes (project 12): machine mode
# resolves the WHOLE machine lock into the shared toolchain venv (add-only `uv pip install`);
# consumer mode installs nothing and only verifies the shared venv + installs skills.
import os
import subprocess
import tomllib
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "modules" / "scripts" / "repoman-sync.sh"

REPO_SELF = '[repoman]\npackage = "repoman"\nsource = "path:/repo/repoman"\n'
GIT_MANAGER = '[managers.git]\npackage = "gitman"\nsource = "path:/repo/gitman"\n'
GIT_PYJUTSU_WHEEL = '[managers.git-pyjutsu]\npackage = "pyjutsu"\nsource = "wheel:pyjutsu>=0.8"\n'


def _stub_bin(tmp_path, *, uv_log, repoman_log=None, toolchain_venv=None):
    """PATH stubs.

    `uv` records its argv to ``uv_log`` and materialises a fake venv on `uv venv`
    (so subsequent `pip install --python …` sees a python). `repoman` records argv
    to ``repoman_log`` (consumer mode's `install-skills` tail).
    """
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir(parents=True, exist_ok=True)

    repoman = stub_bin / "repoman"
    repoman.write_text(f"#!/usr/bin/env bash\necho \"$@\" >> {repoman_log or '/dev/null'}\nexit 0\n")
    repoman.chmod(0o755)

    uv = stub_bin / "uv"
    uv.write_text(
        f"""#!/usr/bin/env bash
echo "$@" >> {uv_log}
if [ "$1" = "venv" ]; then
  # args: uv venv [--python 3.13] <path>
  last=""
  for a in "$@"; do last="$a"; done
  mkdir -p "$last/bin"
  touch "$last/bin/python"
fi
exit 0
"""
    )
    uv.chmod(0o755)

    if toolchain_venv is not None:
        (Path(toolchain_venv) / "bin").mkdir(parents=True, exist_ok=True)


def _run(
    tmp_path,
    lock_body,
    mode="machine",
    managers="git",
    find_links=None,
    *,
    argv=None,
    toolchain_venv=None,
    lock_dir=None,
    root_env=None,
):
    """Run the script against ``lock_body``; returns the CompletedProcess.

    ``toolchain_venv`` defaults to ``<tmp>/toolchain-venv`` (never the real
    ``~/.local/share/repoman/venv``). ``lock_dir`` lets a test place the lock
    somewhere other than ``$DEVENV_ROOT`` (REPOMAN_ROOT test).
    """
    if toolchain_venv is None:
        toolchain_venv = str(tmp_path / "toolchain-venv")
    lock_path = Path(lock_dir) if lock_dir else tmp_path
    if lock_body is not None:
        (lock_path / "repoman.lock").write_text(lock_body)

    uv_log = tmp_path / "uv.log"
    repoman_log = tmp_path / "repoman.log"
    _stub_bin(tmp_path, uv_log=uv_log, repoman_log=repoman_log, toolchain_venv=toolchain_venv)

    env = dict(os.environ)
    env["PATH"] = f"{tmp_path / 'bin'}{os.pathsep}{env['PATH']}"
    env["DEVENV_ROOT"] = str(tmp_path)
    env["REPOMAN_MANAGERS"] = managers
    env["REPOMAN_TOOLCHAIN_VENV"] = toolchain_venv
    env.pop("UV_FIND_LINKS", None)
    if find_links is not None:
        env["UV_FIND_LINKS"] = find_links
    if root_env is not None:
        env["REPOMAN_ROOT"] = root_env

    cmd = ["bash", str(SCRIPT)] + (argv or (["--machine"] if mode == "machine" else []))
    return subprocess.run(cmd, env=env, capture_output=True, text=True)


def _uv_log(tmp_path):
    p = tmp_path / "uv.log"
    return p.read_text().splitlines() if p.exists() else []


# ---------------------------------------------------------------- resolver (machine mode)


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


# ---------------------------------------------------------------- machine mode behaviour


def test_machine_installs_every_manager_ignoring_roster(tmp_path):
    # select-all: an empty REPOMAN_MANAGERS still installs the whole machine lock.
    lock = REPO_SELF + GIT_MANAGER + '[managers.copy]\npackage = "copyroom"\nsource = "path:/repo/copyroom"\n'
    r = _run(tmp_path, lock, managers="", find_links=str(tmp_path / "wh"))
    assert r.returncode == 0, r.stderr
    assert "--editable=/repo/gitman" in r.stdout
    assert "--editable=/repo/copyroom" in r.stdout


def test_machine_creates_venv_when_absent(tmp_path):
    r = _run(tmp_path, REPO_SELF + GIT_MANAGER)
    assert r.returncode == 0, r.stderr
    log = _uv_log(tmp_path)
    venv_lines = [l for l in log if l.startswith("venv --python")]
    assert len(venv_lines) == 1
    assert venv_lines[0] == "venv --python 3.13 " + str(tmp_path / "toolchain-venv")


def test_machine_skips_venv_creation_when_present(tmp_path):
    venv = tmp_path / "toolchain-venv"
    (venv / "bin").mkdir(parents=True, exist_ok=True)
    py = venv / "bin" / "python"
    py.write_text("")
    py.chmod(0o755)  # the gate is -x on bin/python
    r = _run(tmp_path, REPO_SELF + GIT_MANAGER, toolchain_venv=str(venv))
    assert r.returncode == 0, r.stderr
    assert not any(l.startswith("venv ") for l in _uv_log(tmp_path))


def test_machine_installs_into_shared_venv(tmp_path):
    # --python <shared venv>/bin/python is load-bearing: the bootstrap may run
    # inside another devenv venv (VIRTUAL_ENV set) and must never target that.
    r = _run(tmp_path, REPO_SELF + GIT_MANAGER)
    assert r.returncode == 0, r.stderr
    install_lines = [l for l in _uv_log(tmp_path) if l.startswith("pip install")]
    assert len(install_lines) == 1
    assert install_lines[0].startswith(
        "pip install --python " + str(tmp_path / "toolchain-venv" / "bin" / "python")
    )
    assert "--editable=/repo/gitman" in install_lines[0]


def test_machine_records_toolchain_manifest(tmp_path):
    r = _run(tmp_path, REPO_SELF + GIT_MANAGER)
    assert r.returncode == 0, r.stderr
    manifest = tmp_path / "toolchain-venv" / "repoman-toolchain.toml"
    assert manifest.exists()
    text = manifest.read_text()
    assert text.startswith("# synced from " + str(tmp_path / "repoman.lock"))
    # the recorded manifest is the verbatim machine lock, round-trippable
    data = tomllib.loads(text.split("\n", 1)[1])
    assert data["managers"]["git"]["package"] == "gitman"
    assert "test" not in data.get("managers", {})


def test_machine_wheel_guard_still_aborts(tmp_path):
    # regression on the reused guard in machine mode.
    r = _run(
        tmp_path,
        REPO_SELF + GIT_MANAGER + GIT_PYJUTSU_WHEEL,
        managers="git",
        find_links=None,
    )
    assert r.returncode == 2
    assert "UV_FIND_LINKS is unset" in r.stderr


def test_machine_missing_lock_exits_2(tmp_path):
    r = _run(tmp_path, None)  # no lock anywhere → REPOMAN_ROOT pointer
    assert r.returncode == 2
    assert "REPOMAN_ROOT" in r.stderr


def test_machine_respects_REPOMAN_ROOT(tmp_path):
    lock_dir = tmp_path / "somewhere-else"
    lock_dir.mkdir()
    r = _run(
        tmp_path,
        REPO_SELF + GIT_MANAGER,
        lock_dir=lock_dir,
        root_env=str(lock_dir),
    )
    assert r.returncode == 0, r.stderr
    manifest = tmp_path / "toolchain-venv" / "repoman-toolchain.toml"
    assert manifest.read_text().startswith("# synced from " + str(lock_dir / "repoman.lock"))


# ---------------------------------------------------------------- consumer mode


def test_consumer_installs_nothing(tmp_path):
    toolchain_venv = str(tmp_path / "toolchain-venv")
    _stub_bin(tmp_path, uv_log=tmp_path / "uv.log", toolchain_venv=toolchain_venv)
    repoman = Path(toolchain_venv) / "bin" / "repoman"
    repoman.write_text("")
    repoman.chmod(0o755)  # consumer mode's gate is -x on the shared repoman
    r = _run(tmp_path, REPO_SELF, mode="consumer", toolchain_venv=toolchain_venv)
    assert r.returncode == 0, r.stderr
    assert _uv_log(tmp_path) == []  # consumer mode never invokes uv
    assert "install-skills" in (tmp_path / "repoman.log").read_text()
    assert "shared toolchain →" in r.stdout


def test_consumer_fails_without_shared_venv(tmp_path):
    r = _run(tmp_path, REPO_SELF, mode="consumer")
    assert r.returncode == 2
    assert "repoman-sync --machine" in r.stderr
    assert _uv_log(tmp_path) == []


def test_consumer_warns_on_orphan_lock(tmp_path):
    toolchain_venv = str(tmp_path / "toolchain-venv")
    _stub_bin(tmp_path, uv_log=tmp_path / "uv.log", toolchain_venv=toolchain_venv)
    repoman = Path(toolchain_venv) / "bin" / "repoman"
    repoman.write_text("")
    repoman.chmod(0o755)
    r = _run(tmp_path, REPO_SELF, mode="consumer", toolchain_venv=toolchain_venv)
    assert r.returncode == 0, r.stderr
    assert "ORPHAN" in r.stderr


def test_unknown_argument_exits_2(tmp_path):
    r = _run(tmp_path, REPO_SELF, argv=["--wat"])
    assert r.returncode == 2
    assert "unknown argument" in r.stderr
