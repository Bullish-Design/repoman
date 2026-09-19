import re
from pathlib import Path

MODULES = Path(__file__).resolve().parents[1] / "modules"


def test_only_testee_uses_the_consumer_venv():
    users = {p.name for p in (MODULES / "managers").glob("*.nix") if "venvBin" in p.read_text()}
    assert users == {"testee.nix"}


def test_shared_managers_resolve_through_the_toolchain_bin():
    for name in ("gitman.nix", "copyroom.nix", "docman.nix"):
        assert "cfg.toolchainBin" in (MODULES / "managers" / name).read_text()


def test_meta_module_does_not_eval_getenv():
    assert "builtins.getEnv" not in (MODULES / "devenv.nix").read_text()


def test_meta_module_exports_store_bin_and_keeps_consumer_bin():
    text = (MODULES / "devenv.nix").read_text()
    assert "REPOMAN_TOOLCHAIN_BIN" in text
    assert 'export PATH="$REPOMAN_TOOLCHAIN_BIN:$PATH"' in text
    assert 'export PATH="${config.devenv.state}/venv/bin:$PATH"' in text


def test_store_path_wins_over_consumer_venv():
    text = (MODULES / "devenv.nix").read_text()
    consumer = text.index('export PATH="${config.devenv.state}/venv/bin:$PATH"')
    store = text.index('export PATH="$REPOMAN_TOOLCHAIN_BIN:$PATH"')
    assert consumer < store


def test_manifest_is_the_only_roster_configuration():
    text = (MODULES / "devenv.nix").read_text()
    assert 'manifestKnownFields = [ "schema" "managers" ];' in text
    assert "managers = lib.mkOption" not in text
    assert "cliProvider" not in text
    assert "REPOMAN_CLI_PROVIDER" not in text


def test_toolchain_option_is_store_only():
    text = (MODULES / "devenv.nix").read_text()
    assert "storeBinExpr" in text
    assert "default = storeBinExpr;" in text
    assert "toolchainVenvExpr" not in text
    assert "cliBinExpr" not in text


def test_manager_modules_receive_the_manifest_roster():
    text = (MODULES / "devenv.nix").read_text()
    assert "_module.args.repomanManagers = managerRoster;" in text
    for name in ("gitman.nix", "copyroom.nix", "docman.nix", "testee.nix"):
        assert "repomanManagers" in (MODULES / "managers" / name).read_text()


def test_store_task_failure_is_actionable():
    text = (MODULES / "devenv.nix").read_text()
    assert "REPOMAN_TOOLCHAIN_BIN:?repoman:" in text


def test_store_missing_shell_entry_degrades_without_exit():
    text = (MODULES / "devenv.nix").read_text()
    assert 'echo "RepoMan: REPOMAN_TOOLCHAIN_BIN is unset' in text
    assert "exit 1" not in text


def test_repoman_dev_shell_self_imports_the_meta_module():
    root = Path(__file__).resolve().parents[1]
    yaml = (root / "devenv.yaml").read_text()
    assert "repoman:" in yaml and "?dir=modules" in yaml
    assert "docman:" in yaml
    assert "imports:" in yaml and "- repoman" in yaml


def test_repoman_dev_shell_uses_the_tracked_full_roster():
    root = Path(__file__).resolve().parents[1]
    assert 'managers = ["copy", "git", "test", "doc"]' in (root / ".repoman/project.toml").read_text()
    assert "managers =" not in (root / "devenv.nix").read_text()


def test_repoman_dev_shell_does_not_shadow_repoman_sync():
    root = Path(__file__).resolve().parents[1]
    assert "repoman-sync = {" not in (root / "devenv.nix").read_text()


def test_repoman_dev_shell_declares_testee():
    root = Path(__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text()
    assert 'dev = ["testee"]' in pyproject
    source = re.search(r"^testee = \{(.*)\}$", pyproject, re.MULTILINE)
    assert source is not None and "git =" in source.group(1)
    assert 'requires-python = ">=3.13"' in pyproject


def test_store_bin_expression_is_shell_safe():
    text = (MODULES / "devenv.nix").read_text()
    expr = re.search(r"storeBinExpr = \"(.*)\";", text)
    assert expr is not None
    message = expr.group(1).replace('\\"', '"')
    assert '"' not in message
    assert "'" not in message
