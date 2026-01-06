from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from repoman import cli


runner = CliRunner()


def test_load_config_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """global:\n  base_dir: ~/code\n  max_concurrent: 5\n\naccounts:\n  - name: acct\n    repos:\n      - repo1\n"""
    )
    config = cli._load_config(config_file)
    assert config.accounts[0].name == "acct"


def test_load_config_toml(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """[global]\nbase_dir = "~/code"\nmax_concurrent = 5\n\n[[accounts]]\nname = "acct"\nrepos = ["repo1"]\n"""
    )
    config = cli._load_config(config_file)
    assert config.accounts[0].name == "acct"


def test_sync_requires_account_for_repo() -> None:
    result = runner.invoke(cli.app, ["sync", "--repo", "repo1"])
    assert result.exit_code == 1


def test_sync_missing_config_file(tmp_path: Path) -> None:
    missing_config = tmp_path / "missing.yaml"
    result = runner.invoke(cli.app, ["sync", "--config", str(missing_config)])
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "no such file" in result.output.lower()


def test_sync_invalid_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("global:\n  base_dir: [unclosed\n")
    result = runner.invoke(cli.app, ["sync", "--config", str(config_file)])
    assert result.exit_code != 0
    output = result.output.lower()
    assert "yaml" in output or "parse" in output


def test_sync_invalid_timeout(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """global:\n  base_dir: ~/code\n  max_concurrent: 5\n  timeout: 10\n\naccounts:\n  - name: acct\n    repos:\n      - repo1\n"""
    )
    result = runner.invoke(cli.app, ["sync", "--config", str(config_file)])
    assert result.exit_code != 0
    output = result.output.lower()
    assert "timeout" in output and "30" in output


def test_sync_missing_required_fields(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """accounts:\n  - repos:\n      - repo1\n"""
    )
    result = runner.invoke(cli.app, ["sync", "--config", str(config_file)])
    assert result.exit_code != 0
    output = result.output.lower()
    assert "global" in output or "required" in output
