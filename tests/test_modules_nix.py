# Grep-level guards on the nix layer (project 12). These lock in D1 (runtime shell
# expression, never a nix-eval path) and the install-model split at the module
# surface: the three pure-CLI managers resolve through `cfg.toolchainBin`, only
# testee still touches the consumer venv.
from pathlib import Path

MODULES = Path(__file__).resolve().parents[1] / "modules"


def test_only_testee_uses_the_consumer_venv():
    # project 12: testee lives in the consumer venv (its tools import the app);
    # every other manager runs from the system-wide toolchain venv.
    users = {p.name for p in (MODULES / "managers").glob("*.nix") if "venvBin" in p.read_text()}
    assert users == {"testee.nix"}


def test_shared_managers_resolve_through_the_toolchain_bin():
    # gitman/copyroom/docman task execs interpolate the toolchain bin shell
    # expression — NOT a bare PATH-resolved name (devenv tasks may not carry the
    # shell's PATH prepend) and NOT the consumer venv.
    for name in ("gitman.nix", "copyroom.nix", "docman.nix"):
        assert "cfg.toolchainBin" in (MODULES / "managers" / name).read_text()


def test_meta_module_does_not_eval_getenv():
    # D1: no eval-time HOME reads anywhere — the path is resolved by bash at runtime.
    assert "builtins.getEnv" not in (MODULES / "devenv.nix").read_text()


def test_meta_module_exports_toolchain_venv_in_enter_shell():
    text = (MODULES / "devenv.nix").read_text()
    assert "export REPOMAN_TOOLCHAIN_VENV=" in text
    assert 'export PATH="$REPOMAN_TOOLCHAIN_VENV/bin:$PATH"' in text


def test_toolchain_bin_is_prepended_after_the_consumer_venv_so_it_wins():
    # Both lines PREPEND, so the one written LAST ends up FIRST on PATH. The toolchain
    # must win: otherwise a stale pre-migration manager CLI in .devenv/state/venv/bin
    # shadows the shared toolchain, and `repoman doctor` and `devenv tasks run` resolve
    # different binaries. The bug this guards was exactly these two lines swapped.
    text = (MODULES / "devenv.nix").read_text()
    venv_prepend = text.index('export PATH="${config.devenv.state}/venv/bin:$PATH"')
    toolchain_prepend = text.index('export PATH="$REPOMAN_TOOLCHAIN_VENV/bin:$PATH"')
    assert venv_prepend < toolchain_prepend


def test_meta_module_prepends_consumer_venv_bin_for_tasks():
    # Task-PATH fix (project-12 follow-up): `devenv tasks run` does not prepend the
    # consumer venv bin (the interactive shell does). enterShell runs per task, so
    # the prepend here fixes tasks shelling out to a venv console script (e.g.
    # testee's lint-imports arch test) and is a harmless no-op for the shell.
    text = (MODULES / "devenv.nix").read_text()
    assert 'export PATH="${config.devenv.state}/venv/bin:$PATH"' in text


def test_repoman_dev_shell_self_imports_the_meta_module():
    # Project 14 seam: repoman's OWN devenv shell is a first-class managed repo — it
    # imports the meta-module from ./modules (the same `imports: [repoman]` consumers
    # use) and declares the docman input that approach-B provisioning requires. That
    # makes this checkout the canonical host for `copyroom new <target>` bootstraps,
    # with no dependency on another repo's shell.
    root = Path(__file__).resolve().parents[1]
    yaml = (root / "devenv.yaml").read_text()
    assert "repoman:" in yaml and "url: path:./modules" in yaml
    assert "docman:" in yaml
    assert "imports:" in yaml and "- repoman" in yaml


def test_repoman_dev_shell_enables_the_full_roster():
    # Self-hosting means the full manager suite is wired in the dev shell, not a
    # subset — copy/git/test/doc, mirroring the meta-module's allManagers list.
    root = Path(__file__).resolve().parents[1]
    nix = (root / "devenv.nix").read_text()
    assert "enable = true" in nix
    assert 'managers = [ "copy" "git" "test" "doc" ]' in nix


def test_repoman_dev_shell_does_not_shadow_the_meta_repoman_sync_script():
    # The dev shell used to define its own repoman-sync wrapper (REPOMAN_ROOT=…); the
    # meta-module owns `scripts.repoman-sync` now. Two definitions of the same script
    # name would make devenv fail the eval with a merge conflict.
    root = Path(__file__).resolve().parents[1]
    nix = (root / "devenv.nix").read_text()
    assert "repoman-sync = {" not in nix


def test_repoman_dev_shell_declares_testee_for_the_test_manager():
    # The "test" manager's tasks exec the consumer venv's testee console script
    # (modules/managers/testee.nix) and `repoman doctor` requires the uv:test
    # declaration — both green only when testee is a declared dev dependency.
    root = Path(__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text()
    assert 'dev = ["testee"]' in pyproject
    assert 'testee = { path = "../testee" }' in pyproject
    # testee 0.2.0 requires Python >=3.13 — repoman aligns (family + machine venv are 3.13).
    assert 'requires-python = ">=3.13"' in pyproject
