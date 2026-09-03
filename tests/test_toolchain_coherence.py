# Regression cover for the incoherent machine toolchain (project 18).
#
# The failure this file pins down: `repoman-sync --machine` reported success while the
# shared venv still ran a dependency version no installed manager supports.
#
#   * gitman's editable CODE was 0.6.0 (`pyjutsu>=0.20.0`);
#   * gitman's installed METADATA was 0.4.2 (`pyjutsu>=0.15.0`);
#   * the lock's pseudo-entry said `wheel:pyjutsu>=0.8`;
#   * so pyjutsu 0.15.0 satisfied every constraint uv could see, and
#     `ws.git.remotes()` — added in pyjutsu 0.20 — died with AttributeError.
#
# Two layers of cover:
#
#   * contract tests drive the script with a stubbed `uv` and a hand-built venv, so they
#     assert what the script does about a given installed state, whatever uv's version
#     happens to resolve;
#   * integration tests drive the script with the REAL uv against fixture packages, so
#     they assert the end state of a genuine sync.
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest
from test_repoman_sync import GIT_MANAGER, GIT_PYJUTSU_WHEEL, REPO_SELF, SCRIPT, _run, _uv_log

# ---------------------------------------------------------------- fake installed venvs

WHEEL_TAG = "Wheel-Version: 1.0\nGenerator: repoman-tests\nRoot-Is-Purelib: true\nTag: py3-none-any\n"


def _site_packages(venv) -> Path:
    site = Path(venv) / "lib" / "python3.13" / "site-packages"
    site.mkdir(parents=True, exist_ok=True)
    return site


def _install_fake(venv, name, version, requires=()):
    """Write a dist-info for ``name`` into ``venv``'s site-packages.

    Enough metadata for `importlib.metadata` to report a version and its
    requirements — which is all the coherence check reads.
    """
    dist_info = _site_packages(venv) / f"{name}-{version}.dist-info"
    dist_info.mkdir(parents=True, exist_ok=True)
    lines = ["Metadata-Version: 2.1", f"Name: {name}", f"Version: {version}"]
    lines += [f"Requires-Dist: {r}" for r in requires]
    (dist_info / "METADATA").write_text("\n".join(lines) + "\n")
    (dist_info / "WHEEL").write_text(WHEEL_TAG)
    (dist_info / "RECORD").write_text("")


def _checkout(tmp_path, name, version, dependencies=()):
    """A `path:` source checkout whose pyproject declares ``version``."""
    root = tmp_path / "checkouts" / name
    (root / "src" / name).mkdir(parents=True, exist_ok=True)
    deps = ", ".join(f'"{d}"' for d in dependencies)
    (root / "pyproject.toml").write_text(
        "[build-system]\n"
        "requires = []\n"
        'build-backend = "zzbackend"\n'
        'backend-path = ["."]\n'
        "\n"
        "[project]\n"
        f'name = "{name}"\n'
        f'version = "{version}"\n'
        f"dependencies = [{deps}]\n"
    )
    (root / "src" / name / "__init__.py").write_text(f'VERSION = "{version}"\n')
    shutil.copyfile(Path(__file__).with_name("zzbackend.py"), root / "zzbackend.py")
    return root


# ------------------------------------------------------------------- contract: rebuild


def test_every_editable_entry_is_rebuilt_on_sync(tmp_path):
    # A `path:` manager's metadata is a build-time snapshot; without a forced rebuild
    # the resolver reads LAST sync's requirements and never sees the current ones.
    r = _run(tmp_path, REPO_SELF + GIT_MANAGER)
    assert r.returncode == 0, r.stderr
    install = [line for line in _uv_log(tmp_path) if line.startswith("pip install")][0]
    assert "--reinstall-package=gitman" in install
    assert "--reinstall-package=repoman" in install


def test_only_path_entries_are_force_rebuilt(tmp_path):
    # A wheel: or git+ entry is already an immutable artefact — rebuilding it is waste,
    # and the fleet shape must keep resolving exactly as before.
    lock = (
        REPO_SELF
        + '[managers.git]\npackage = "gitman"\nsource = "git+https://github.com/Bullish-Design/gitman@v0.6.0"\n'
        + GIT_PYJUTSU_WHEEL
    )
    r = _run(tmp_path, lock, find_links=str(tmp_path / "wh"))
    assert r.returncode == 0, r.stderr
    install = [line for line in _uv_log(tmp_path) if line.startswith("pip install")][0]
    assert "--reinstall-package=repoman" in install  # the one path: entry
    assert "--reinstall-package=gitman" not in install
    assert "--reinstall-package=pyjutsu" not in install
    # the fleet source itself still reaches uv verbatim
    assert "git+https://github.com/Bullish-Design/gitman@v0.6.0" in install


def test_rebuild_flags_are_not_counted_as_packages(tmp_path):
    # The report counts packages, not uv flags.
    r = _run(tmp_path, REPO_SELF + GIT_MANAGER)
    assert "installing 2 package(s)" in r.stdout
    assert "--reinstall-package" not in r.stdout


# ----------------------------------------------------------------- contract: coherence


def _coherence_run(tmp_path, *, gitman_installed, pyjutsu_installed, gitman_requires, gitman_declared="0.6.0"):
    """Sync a lock whose gitman is a `path:` checkout, against a hand-built venv."""
    venv = tmp_path / "toolchain-venv"
    (venv / "bin").mkdir(parents=True, exist_ok=True)
    python = venv / "bin" / "python"
    python.write_text("")
    python.chmod(0o755)
    _install_fake(venv, "gitman", gitman_installed, requires=gitman_requires)
    _install_fake(venv, "pyjutsu", pyjutsu_installed)

    checkout = _checkout(tmp_path, "gitman", gitman_declared, dependencies=["pyjutsu>=0.20.0"])
    lock = f'[managers.git]\npackage = "gitman"\nsource = "path:{checkout}"\n' + GIT_PYJUTSU_WHEEL
    r = _run(tmp_path, lock, find_links=str(tmp_path / "wh"), toolchain_venv=str(venv))
    return r, venv


def test_stale_editable_metadata_fails_the_sync(tmp_path):
    # The observed machine state. Every constraint uv could see was satisfied
    # (`pyjutsu 0.15.0` vs the SNAPSHOT `pyjutsu>=0.15.0`), so the install "succeeded" —
    # while the code that actually ran needed 0.20.0.
    r, venv = _coherence_run(
        tmp_path,
        gitman_installed="0.4.2",
        pyjutsu_installed="0.15.0",
        gitman_requires=["pyjutsu>=0.15.0"],
        gitman_declared="0.6.0",
    )
    assert r.returncode == 2
    assert "INCOHERENT" in r.stderr
    assert "gitman 0.4.2" in r.stderr
    assert "declares 0.6.0" in r.stderr
    # A manifest is a claim that the venv matches the lock — never record one for a
    # venv that does not.
    assert not (venv / "repoman-toolchain.toml").exists()


def test_a_loose_pseudo_entry_cannot_weaken_a_managers_requirement(tmp_path):
    # gitman's metadata is current, so its real floor (>=0.20.0) is visible — but the
    # lock's `wheel:pyjutsu>=0.8` still accepts 0.15.0. The stricter one must win.
    r, venv = _coherence_run(
        tmp_path,
        gitman_installed="0.6.0",
        pyjutsu_installed="0.15.0",
        gitman_requires=["pyjutsu>=0.20.0"],
    )
    assert r.returncode == 2
    assert "pyjutsu>=0.20.0" in r.stderr  # names the constraint
    assert "pyjutsu 0.15.0 is installed" in r.stderr  # names the offending version
    assert not (venv / "repoman-toolchain.toml").exists()


def test_a_missing_dependency_fails_the_sync(tmp_path):
    venv = tmp_path / "toolchain-venv"
    (venv / "bin").mkdir(parents=True, exist_ok=True)
    (venv / "bin" / "python").write_text("")
    (venv / "bin" / "python").chmod(0o755)
    _install_fake(venv, "gitman", "0.6.0", requires=["pyjutsu>=0.20.0"])
    checkout = _checkout(tmp_path, "gitman", "0.6.0", dependencies=["pyjutsu>=0.20.0"])
    lock = f'[managers.git]\npackage = "gitman"\nsource = "path:{checkout}"\n'
    r = _run(tmp_path, lock, toolchain_venv=str(venv))
    assert r.returncode == 2
    assert "pyjutsu is not installed" in r.stderr


def test_a_coherent_result_records_the_manifest(tmp_path):
    r, venv = _coherence_run(
        tmp_path,
        gitman_installed="0.6.0",
        pyjutsu_installed="0.20.0",
        gitman_requires=["pyjutsu>=0.20.0"],
    )
    assert r.returncode == 0, r.stderr
    assert (venv / "repoman-toolchain.toml").exists()


def test_extras_and_markers_are_not_evaluated(tmp_path):
    # `pygithub>=2.3; extra == 'github'` is not installed and must not be a finding —
    # a wrong answer from the checker is worse than a narrower one.
    r, venv = _coherence_run(
        tmp_path,
        gitman_installed="0.6.0",
        pyjutsu_installed="0.20.0",
        gitman_requires=["pyjutsu>=0.20.0", "pygithub>=2.3; extra == 'github'"],
    )
    assert r.returncode == 0, r.stderr
    assert (venv / "repoman-toolchain.toml").exists()


def test_dynamic_version_checkout_is_not_a_finding(tmp_path):
    # A checkout that computes its version has no `[project].version` to compare.
    venv = tmp_path / "toolchain-venv"
    (venv / "bin").mkdir(parents=True, exist_ok=True)
    (venv / "bin" / "python").write_text("")
    (venv / "bin" / "python").chmod(0o755)
    _install_fake(venv, "gitman", "0.4.2")
    checkout = tmp_path / "checkouts" / "gitman"
    checkout.mkdir(parents=True)
    (checkout / "pyproject.toml").write_text('[project]\nname = "gitman"\ndynamic = ["version"]\n')
    lock = f'[managers.git]\npackage = "gitman"\nsource = "path:{checkout}"\n'
    r = _run(tmp_path, lock, toolchain_venv=str(venv))
    assert r.returncode == 0, r.stderr


def test_an_uninspectable_venv_warns_instead_of_claiming_success(tmp_path):
    # No site-packages to read (the stubbed-uv suites): say so rather than pass silently.
    r = _run(tmp_path, REPO_SELF + GIT_MANAGER)
    assert r.returncode == 0, r.stderr
    assert "dependency verification skipped" in r.stderr


# ------------------------------------------------------------------------ integration

uv_required = pytest.mark.skipif(shutil.which("uv") is None, reason="needs uv on PATH")


def _write_wheel(wheelhouse: Path, name: str, version: str, requires=()) -> Path:
    """A minimal valid pure-python wheel — no build backend, no network."""
    wheelhouse.mkdir(parents=True, exist_ok=True)
    dist = f"{name}-{version}"
    path = wheelhouse / f"{dist}-py3-none-any.whl"
    lines = ["Metadata-Version: 2.1", f"Name: {name}", f"Version: {version}"]
    lines += [f"Requires-Dist: {r}" for r in requires]
    records: list[str] = []
    with zipfile.ZipFile(path, "w") as zf:

        def add(arc: str, text: str) -> None:
            zf.writestr(arc, text)
            records.append(arc)

        add(f"{name}/__init__.py", f'VERSION = "{version}"\n')
        add(f"{dist}.dist-info/METADATA", "\n".join(lines) + "\n")
        add(f"{dist}.dist-info/WHEEL", WHEEL_TAG)
        zf.writestr(
            f"{dist}.dist-info/RECORD",
            "".join(f"{a},,\n" for a in records) + f"{dist}.dist-info/RECORD,,\n",
        )
    return path


def _real_sync(tmp_path, *, wheelhouse, venv):
    """Run the script with the REAL uv. Hermetic: the fixtures exist only in the wheelhouse."""
    env = dict(os.environ)
    env["DEVENV_ROOT"] = str(tmp_path)
    env["REPOMAN_TOOLCHAIN_VENV"] = str(venv)
    env["UV_FIND_LINKS"] = str(wheelhouse)
    env["UV_NO_INDEX"] = "1"  # never reach a real index for a fixture name
    env.pop("VIRTUAL_ENV", None)
    return subprocess.run(["bash", str(SCRIPT), "--machine"], env=env, capture_output=True, text=True)


def _installed(venv: Path) -> dict[str, str]:
    """The fixture packages installed in ``venv``, name → version.

    Filtered to the `zz*` fixtures on purpose: an ambient PYTHONPATH (devenv exports
    one) leaks unrelated distributions into the venv's view, and they are not what
    these assertions are about.
    """
    out = subprocess.run(
        [
            str(venv / "bin" / "python"),
            "-c",
            "import importlib.metadata as m, json;"
            "print(json.dumps({d.metadata['Name']: d.version for d in m.distributions()"
            " if d.metadata['Name'].startswith('zz')}))",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    import json

    return json.loads(out.stdout)


def _lab(tmp_path, manager_version, manager_requires, wheel_versions, pseudo="zzlibx>=1.0.0"):
    wheelhouse = tmp_path / "wheelhouse"
    for version in wheel_versions:
        _write_wheel(wheelhouse, "zzlibx", version)
    checkout = _checkout(tmp_path, "zzmgrx", manager_version, dependencies=manager_requires)
    (tmp_path / "repoman.lock").write_text(
        f'[managers.x]\npackage = "zzmgrx"\nsource = "path:{checkout}"\n\n'
        f'[managers.x-zzlibx]\npackage = "zzlibx"\nsource = "wheel:{pseudo}"\n'
    )
    return wheelhouse, checkout


@uv_required
def test_sync_upgrades_a_stale_dependency_and_refreshes_editable_metadata(tmp_path):
    # Stage 1: the only zzlibx anywhere is 1.0.0, and the manager is happy with it.
    venv = tmp_path / "toolchain-venv"
    wheelhouse, checkout = _lab(tmp_path, "0.1.0", ["zzlibx>=1.0.0"], ["1.0.0"])
    first = _real_sync(tmp_path, wheelhouse=wheelhouse, venv=venv)
    assert first.returncode == 0, first.stderr
    assert _installed(venv) == {"zzmgrx": "0.1.0", "zzlibx": "1.0.0"}

    # Stage 2: the manager's checkout advances past its installed metadata, and a newer
    # dependency appears. The lock's pseudo-entry still says `>=1.0.0`.
    _checkout(tmp_path, "zzmgrx", "0.2.0", dependencies=["zzlibx>=2.0.0"])
    _write_wheel(wheelhouse, "zzlibx", "2.0.0")

    second = _real_sync(tmp_path, wheelhouse=wheelhouse, venv=venv)
    assert second.returncode == 0, second.stderr
    # 1. the manager's stricter constraint beat the looser pseudo-entry;
    # 2. the stale dependency upgraded;
    # 3. the editable metadata matches the checkout again.
    assert _installed(venv) == {"zzmgrx": "0.2.0", "zzlibx": "2.0.0"}
    assert (venv / "repoman-toolchain.toml").exists()
    assert str(checkout) in (venv / "repoman-toolchain.toml").read_text()


@uv_required
def test_a_second_sync_changes_nothing(tmp_path):
    venv = tmp_path / "toolchain-venv"
    wheelhouse, _ = _lab(tmp_path, "0.2.0", ["zzlibx>=2.0.0"], ["1.0.0", "2.0.0"])
    first = _real_sync(tmp_path, wheelhouse=wheelhouse, venv=venv)
    assert first.returncode == 0, first.stderr
    before = _installed(venv)
    manifest = (venv / "repoman-toolchain.toml").read_text()

    second = _real_sync(tmp_path, wheelhouse=wheelhouse, venv=venv)
    assert second.returncode == 0, second.stderr
    assert _installed(venv) == before == {"zzmgrx": "0.2.0", "zzlibx": "2.0.0"}
    assert (venv / "repoman-toolchain.toml").read_text() == manifest


@uv_required
def test_an_unsatisfiable_constraint_set_exits_2_and_names_the_package(tmp_path):
    # The manager needs zzlibx 2.0.0; the wheelhouse has only 1.0.0. No solution exists,
    # so the sync must stop at infra/config (2) — never install half a toolchain.
    venv = tmp_path / "toolchain-venv"
    wheelhouse, _ = _lab(tmp_path, "0.2.0", ["zzlibx>=2.0.0"], ["1.0.0"])
    r = _real_sync(tmp_path, wheelhouse=wheelhouse, venv=venv)
    assert r.returncode == 2
    assert "coherent toolchain" in r.stderr
    assert "zzlibx" in r.stderr  # names the package
    assert "2.0.0" in r.stderr  # names the constraint it could not meet
    assert not (venv / "repoman-toolchain.toml").exists()
