# Grep-level guards on the nix layer (project 12). These lock in D1 (runtime shell
# expression, never a nix-eval path) and the install-model split at the module
# surface: the three pure-CLI managers resolve through `cfg.toolchainBin`, only
# testee still touches the consumer venv.
import re
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
    # The input is taken by `git+file:` rather than `path:` (commit d84b74f), so
    # match the `?dir=modules` selector, not the old `path:./modules` spelling.
    assert "repoman:" in yaml and "?dir=modules" in yaml
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
    # A [tool.uv.sources] entry, but NOT a particular spelling: testee is not on PyPI, so
    # uv needs a source — and the committed one must be a git tag, because a relative
    # `../testee` resolves beside whatever directory the clone happens to sit in.
    source = re.search(r"^testee = \{(.*)\}$", pyproject, re.MULTILINE)
    assert source is not None, "testee needs a [tool.uv.sources] entry"
    assert "git =" in source.group(1), f"committed testee source must be portable, got: {source.group(0)}"
    # testee 0.2.0 requires Python >=3.13 — repoman aligns (family + machine venv are 3.13).
    assert 'requires-python = ">=3.13"' in pyproject


# ------------------------------------------------- the cliProvider seam (CONCEPT 03 §4.1)


def test_cli_provider_option_exists_and_defaults_to_venv():
    # Phase 0 of the shared-command-closure migration: the seam ships FIRST, with the
    # current behaviour as its default. A default of "store" would migrate every
    # consumer the moment they update the module.
    text = (MODULES / "devenv.nix").read_text()
    option = re.search(r"cliProvider = lib\.mkOption \{(.*?)\n    \};", text, re.DOTALL)
    assert option is not None, "modules/devenv.nix must declare repoman.cliProvider"
    body = option.group(1)
    assert 'lib.types.enum [ "venv" "store" ]' in body
    assert 'default = "venv"' in body


def test_toolchain_bin_resolves_through_the_provider():
    # The three shared managers keep interpolating cfg.toolchainBin; it is the OPTION
    # that becomes provider-aware, so no manager module learns a second path shape.
    text = (MODULES / "devenv.nix").read_text()
    assert 'cliBinExpr = if cfg.cliProvider == "store" then storeBinExpr else "${toolchainVenvExpr}/bin"' in text
    assert "default = cliBinExpr;" in text


def test_store_mode_fails_a_task_rather_than_exec_a_guessed_path():
    # No silent fallback (acceptance criterion). An unset REPOMAN_TOOLCHAIN_BIN must
    # abort the task via `:?`, not expand to "" and exec "/gitman".
    text = (MODULES / "devenv.nix").read_text()
    assert "REPOMAN_TOOLCHAIN_BIN:?repoman:" in text


def test_store_mode_does_not_abort_shell_entry():
    # gitman project 32 / G3: a broken vendor-status took loci-core's devenv down.
    # Nothing in the closure may sit on the shell-entry critical path without a
    # degrade, so enterShell only echoes — it must never use `:?` or `exit`.
    text = (MODULES / "devenv.nix").read_text()
    store_block = text.split('lib.optionalString (cfg.cliProvider == "store")')[1].split("+ ''")[0]
    # Comments may NAME `:?` (they explain where the hard failure does live); only the
    # executable lines matter here.
    code = "\n".join(line for line in store_block.splitlines() if not line.lstrip().startswith("#"))
    assert ":?" not in code
    assert "exit 1" not in code
    assert 'echo "RepoMan: cliProvider is' in store_block


def test_enter_shell_exports_the_provider_for_the_python_cli():
    # checks.py reads REPOMAN_CLI_PROVIDER. If the nix layer did not export it, the
    # doctor and the tasks could resolve commands from different places.
    text = (MODULES / "devenv.nix").read_text()
    assert 'export REPOMAN_CLI_PROVIDER="${cfg.cliProvider}"' in text


def test_venv_provider_still_exports_the_toolchain_venv():
    # Regression guard on the unchanged default: the venv branch keeps both the
    # REPOMAN_TOOLCHAIN_VENV export and its PATH prepend.
    text = (MODULES / "devenv.nix").read_text()
    venv_block = text.split('lib.optionalString (cfg.cliProvider == "venv")')[1].split("+ lib.optionalString")[0]
    assert "export REPOMAN_TOOLCHAIN_VENV=" in venv_block
    assert 'export PATH="$REPOMAN_TOOLCHAIN_VENV/bin:$PATH"' in venv_block
    assert "repoman-sync --machine" in venv_block


def test_consumer_venv_prepend_is_provider_independent():
    # testee stays a per-repo uv dependency under both providers, so its bin dir must
    # be on the task PATH regardless of where the shared managers come from.
    text = (MODULES / "devenv.nix").read_text()
    preamble = text.split("enterShell = ''")[1].split("+ lib.optionalString")[0]
    assert 'export PATH="${config.devenv.state}/venv/bin:$PATH"' in preamble
