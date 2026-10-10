import tomllib
from pathlib import Path

MODULES = Path(__file__).resolve().parents[1] / "modules"


def test_manager_tasks_use_the_host_profile():
    users = {p.name for p in (MODULES / "managers").glob("*.nix") if "venvBin" in p.read_text()}
    assert users == set()
    testee = (MODULES / "managers" / "testee.nix").read_text()
    assert "REPOMAN_TESTEE_HOST_BIN" in testee
    assert 'lib.removePrefix "testee-" config.testee.package.name' in testee


def test_test_manager_sets_no_enter_test():
    # Testee's own module sets `enterTest` to the full gate. devenv joins every
    # value, so a second one in RepoMan would run the full gate twice.
    text = (MODULES / "managers" / "testee.nix").read_text()
    assert not any(line.lstrip().startswith("enterTest") for line in text.splitlines())
    assert '"repoman:test".exec' in text
    assert '"repoman:test:ci".exec' in text


def test_host_managers_run_by_name_from_path():
    # gitman.nix runs no task: gitman 0.12 has one command, `work`.
    for name, command in (("copyroom.nix", "copyroom status"), ("docman.nix", "docman doctor")):
        text = (MODULES / "managers" / name).read_text()
        assert f"&& {command}" in text
        assert "toolchainBin" not in text and "REPOMAN_TOOLCHAIN" not in text


def test_meta_module_does_not_eval_getenv():
    assert "builtins.getEnv" not in (MODULES / "devenv.nix").read_text()


def test_meta_module_keeps_the_consumer_venv_on_path_and_reads_no_closure():
    text = (MODULES / "devenv.nix").read_text()
    assert "export REPOMAN_TESTEE_HOST_BIN=" in text
    assert '$(dirname "$REPOMAN_TESTEE_HOST_BIN")' in text
    assert '"${config.devenv.state}/venv/bin:' in text
    for retired in ("REPOMAN_TOOLCHAIN_BIN", "toolchainBin", "storeBinExpr", "REPOMAN_TOOLCHAIN_MANIFEST"):
        assert retired not in text


def test_manifest_is_the_only_roster_configuration():
    text = (MODULES / "devenv.nix").read_text()
    assert 'manifestKnownFields = [ "schema" "managers" "cliProvider" ];' in text
    assert "managers = lib.mkOption" not in text
    assert "REPOMAN_CLI_PROVIDER" not in text


def test_manager_modules_receive_the_manifest_roster():
    text = (MODULES / "devenv.nix").read_text()
    assert "_module.args.repomanManagers = managerRoster;" in text
    for name in ("gitman.nix", "copyroom.nix", "docman.nix", "testee.nix"):
        assert "repomanManagers" in (MODULES / "managers" / name).read_text()


def test_repoman_dev_shell_self_imports_the_meta_module():
    root = Path(__file__).resolve().parents[1]
    yaml = (root / "devenv.yaml").read_text()
    assert "repoman:" in yaml and "?dir=modules" in yaml
    assert "docman:" not in yaml
    assert "imports:" in yaml and "- repoman" in yaml


def test_repoman_dev_shell_uses_the_tracked_full_roster():
    root = Path(__file__).resolve().parents[1]
    assert 'managers = ["copy", "git", "test"]' in (root / ".repoman/project.toml").read_text()
    assert "managers =" not in (root / "devenv.nix").read_text()


def test_repoman_dev_shell_does_not_shadow_repoman_sync():
    root = Path(__file__).resolve().parents[1]
    assert "repoman-sync = {" not in (root / "devenv.nix").read_text()


def test_repoman_dev_shell_pins_testee_in_nix():
    root = Path(__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text()
    groups = tomllib.loads(pyproject)["dependency-groups"]["dev"]
    assert not any(spec == "testee" or spec.startswith("testee") for spec in groups)
    assert (
        'builtins.getFlake "git+https://github.com/Bullish-Design/testee?ref=refs/tags/v0.5.1"'
        in (root / "devenv.nix").read_text()
    )
    assert "testee.package = testeeFlake.packages." in (root / "devenv.nix").read_text()
    assert 'requires-python = ">=3.13"' in pyproject
