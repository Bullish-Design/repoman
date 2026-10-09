import re
import tomllib
from pathlib import Path

MODULES = Path(__file__).resolve().parents[1] / "modules"


def test_only_testee_uses_the_consumer_venv():
    users = {p.name for p in (MODULES / "managers").glob("*.nix") if "venvBin" in p.read_text()}
    assert users == {"testee.nix"}


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
    assert 'export PATH="${config.devenv.state}/venv/bin:$PATH"' in text
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
    """testee is in the dev group, whatever else the group carries.

    Asserted by parsing the group, not by pinning the literal line: the group
    legitimately grows (pytest-cov is required by `addopts`), and a literal match
    turns any addition into a failure that says nothing about testee.
    """

    root = Path(__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text()
    groups = tomllib.loads(pyproject)["dependency-groups"]["dev"]
    assert any(spec == "testee" or spec.startswith("testee") for spec in groups)
    source = re.search(r"^testee = \{(.*)\}$", pyproject, re.MULTILINE)
    assert source is not None and "git =" in source.group(1)
    assert 'requires-python = ">=3.13"' in pyproject
