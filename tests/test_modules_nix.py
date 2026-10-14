import tomllib
from pathlib import Path

MODULES = Path(__file__).resolve().parents[1] / "modules"


def test_manager_tasks_use_the_host_profile():
    users = {p.name for p in (MODULES / "managers").glob("*.nix") if "venvBin" in p.read_text()}
    assert users == set()


def test_test_manager_has_no_nix_module():
    # The `test` manager is uniform with copy and git: a bare command on PATH.
    # The machine supplies the Testee module. The project keeps its checks in nix/testee.nix. The host `testee` runs them.
    assert not (MODULES / "managers" / "testee.nix").exists()
    text = (MODULES / "devenv.nix").read_text()
    assert "managers/testee.nix" not in text
    for retired in ("REPOMAN_TESTEE_HOST_BIN", "REPOMAN_TESTEE_VERSION", "repoman:test"):
        assert retired not in text


def test_host_managers_run_by_name_from_path():
    # gitman.nix runs no task: gitman 0.12 has one command, `work`.
    text = (MODULES / "managers" / "copyroom.nix").read_text()
    assert "&& copyroom status" in text
    assert "toolchainBin" not in text and "REPOMAN_TOOLCHAIN" not in text


def test_meta_module_does_not_eval_getenv():
    assert "builtins.getEnv" not in (MODULES / "devenv.nix").read_text()


def test_meta_module_keeps_the_consumer_venv_on_path_and_reads_no_closure():
    text = (MODULES / "devenv.nix").read_text()
    assert '"${config.devenv.state}/venv/bin:' in text
    assert "nix-profile" not in text
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
    for name in ("gitman.nix", "copyroom.nix"):
        assert "repomanManagers" in (MODULES / "managers" / name).read_text()


def test_meta_module_imports_no_module_but_its_own_managers():
    # RepoMan once presence-imported shellij's devenv module from a consumer input.
    text = (MODULES / "devenv.nix").read_text()
    assert "shellij" not in text
    assert "inputs ?" not in text and "inputs." not in text


def test_the_doc_manager_module_is_gone_and_its_key_is_tolerated():
    assert not (MODULES / "managers" / "docman.nix").exists()
    text = (MODULES / "devenv.nix").read_text()
    assert "managers/docman.nix" not in text
    assert 'allManagers = [ "copy" "git" "test" ];' in text
    # A manifest that still lists `doc` must evaluate; the doctor warns about it.
    assert 'removedManagers = [ "doc" ];' in text
    assert "allManagers ++ removedManagers" in text


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


def test_repoman_dev_shell_keeps_testee_checks_in_nix_testee():
    root = Path(__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text()
    groups = tomllib.loads(pyproject)["dependency-groups"]["dev"]
    assert not any(spec == "testee" or spec.startswith("testee") for spec in groups)
    yaml = (root / "devenv.yaml").read_text()
    assert "testee" not in yaml
    nix = (root / "devenv.nix").read_text()
    assert "imports = [ ./nix/testee.nix ];" in nix
    assert "testee.checks" not in nix
    assert "getFlake" not in nix
    assert "testee.package" not in nix
    testee_nix = (root / "nix" / "testee.nix").read_text()
    assert 'testee.prepare = [ [ "uv" "sync" "--locked" "--all-extras" ] ];' in testee_nix
    assert "testee.checks = {" in testee_nix
    assert 'requires-python = ">=3.13"' in pyproject


def test_repoman_dev_shell_runs_testee_verify_as_base_test():
    nix = (Path(__file__).resolve().parents[1] / "devenv.nix").read_text()
    assert "\"base:test\".exec = ''cd \"$DEVENV_ROOT\" && testee verify'';" in nix
    assert "repoman:test" not in nix and "testee:verify" not in nix
    assert "--full" not in nix
