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


def test_meta_module_prepends_consumer_venv_bin_for_tasks():
    # Task-PATH fix (project-12 follow-up): `devenv tasks run` does not prepend the
    # consumer venv bin (the interactive shell does). enterShell runs per task, so
    # the prepend here fixes tasks shelling out to a venv console script (e.g.
    # testee's lint-imports arch test) and is a harmless no-op for the shell.
    text = (MODULES / "devenv.nix").read_text()
    assert 'export PATH="${config.devenv.state}/venv/bin:$PATH"' in text
