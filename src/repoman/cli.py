# src/repoman/cli.py
"""Command-line interface for repoman."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import typer
import yaml

try:
    import tomli
except ModuleNotFoundError:  # pragma: no cover - tomli is a dependency for Python <3.11
    tomli = None

from pydantic import ValidationError

from repoman.config import RepomanConfig
from repoman.github import GitHubClient
from repoman.manager import RepoManager, SyncResult

app = typer.Typer(help="Repoman - repository manager for NixOS configurations")


def _load_config(config_path: Path) -> RepomanConfig:
    """Load and parse configuration file.

    Supports .yaml, .yml, and .toml files.

    Args:
        config_path: Path to configuration file

    Returns:
        Parsed configuration

    Raises:
        typer.Exit(1): On any error (file not found, parse error, validation error)
    """

    expanded_path = config_path.expanduser()
    if not expanded_path.exists():
        typer.secho(f"Error: Configuration file not found: {expanded_path}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    suffix = expanded_path.suffix.lower()
    try:
        if suffix in {".yaml", ".yml"}:
            data = yaml.safe_load(expanded_path.read_text())
        elif suffix == ".toml":
            if tomli is None:
                raise RuntimeError("tomli is required to load TOML configuration files")
            with expanded_path.open("rb") as handle:
                data = tomli.load(handle)
        else:
            raise ValueError("Configuration file must be .yaml, .yml, or .toml")
    except yaml.YAMLError as exc:
        typer.secho(f"Error parsing YAML configuration: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    except Exception as exc:  # noqa: BLE001 - provide clear error message
        typer.secho(f"Error loading configuration: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    try:
        return RepomanConfig.model_validate(data)
    except ValidationError as exc:
        typer.secho(f"Configuration validation failed: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc


def _progress_callback(message: str, level: str = "info") -> None:
    """Display progress message to terminal.

    Args:
        message: Message to display
        level: Severity level affecting color
    """

    color_map = {
        "info": typer.colors.WHITE,
        "success": typer.colors.GREEN,
        "warning": typer.colors.YELLOW,
        "error": typer.colors.RED,
    }
    typer.secho(message, fg=color_map.get(level, typer.colors.WHITE))


def _summarize(results: list[SyncResult]) -> dict[str, int]:
    summary = {"cloned": 0, "updated": 0, "up-to-date": 0, "error": 0}
    for result in results:
        summary[result.status] += 1
    return summary


@app.command()
def sync(
    config: Path = typer.Option(
        Path("~/.config/repoman/config.yaml"),
        "--config",
        "-c",
        help="Configuration file path",
    ),
    account: str | None = typer.Option(
        None,
        "--account",
        "-a",
        help="Sync only this account",
    ),
    repo: str | None = typer.Option(
        None,
        "--repo",
        "-r",
        help="Sync only this repo (requires --account)",
    ),
    use_https: bool = typer.Option(
        False,
        "--https",
        help="Use HTTPS instead of SSH",
    ),
) -> None:
    """Sync repositories according to configuration.

    Examples:
        repoman sync                              # Sync all
        repoman sync --account username           # Sync one account
        repoman sync --account user --repo proj   # Sync one repo
        repoman sync --https                      # Use HTTPS URLs
    """

    if repo and not account:
        typer.secho("Error: --repo requires --account", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    config_data = _load_config(config)
    github_client = GitHubClient(use_ssh=not use_https)
    manager = RepoManager(config_data, github_client=github_client)

    async def _run_sync() -> list[SyncResult]:
        if account and repo:
            return [await manager.sync_repo(account, repo, progress=_progress_callback)]
        if account:
            return await manager.sync_account(account, progress=_progress_callback)
        return await manager.sync_all(progress=_progress_callback)

    results = asyncio.run(_run_sync())
    summary = _summarize(results)

    typer.echo("Summary:")
    typer.echo(f"  Cloned: {summary['cloned']}")
    typer.echo(f"  Updated: {summary['updated']}")
    typer.echo(f"  Up-to-date: {summary['up-to-date']}")
    typer.echo(f"  Errors: {summary['error']}")

    if summary["error"] > 0:
        raise typer.Exit(code=1)


@app.command("list")
def list_repos(
    config: Path = typer.Option(
        Path("~/.config/repoman/config.yaml"),
        "--config",
        "-c",
        help="Configuration file path",
    )
) -> None:
    """List all configured repositories and their status.

    Shows:
    - Repository name
    - Local path
    - Whether repository exists (✓ or ✗)
    """

    config_data = _load_config(config)
    manager = RepoManager(config_data, github_client=GitHubClient())
    listing = manager.list_repos()
    for account, repos in listing.items():
        typer.echo(f"{account}:")
        for repo_name, path, exists in repos:
            marker = "✓" if exists else "✗"
            typer.echo(f"  {marker} {repo_name}")
            typer.echo(f"    {path}")


@app.command()
def init(
    config: Path = typer.Option(
        Path("~/.config/repoman/config.yaml"),
        "--config",
        "-c",
        help="Configuration file path",
    )
) -> None:
    """Initialize a new repoman configuration file.

    Creates parent directories and writes example configuration.
    Prompts before overwriting existing file.
    """

    config_path = config.expanduser()
    example = """# Repoman configuration file
global:
  base_dir: ~/code
  max_concurrent: 5

accounts:
  - name: your-github-username
    repos:
      - repo1
      - repo2
      - name: repo3
        local_dir: ~/custom/location

  - name: organization-name
    base_dir: ~/work
    repos:
      - project1
      - project2
"""

    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        overwrite = typer.confirm(f"Config file {config_path} exists. Overwrite?", default=False)
        if not overwrite:
            typer.secho("Aborted.", fg=typer.colors.YELLOW)
            raise typer.Exit(code=1)

    config_path.write_text(example)
    typer.secho(f"Created config at {config_path}", fg=typer.colors.GREEN)


def main() -> None:
    """Entry point for repoman CLI."""

    app()


if __name__ == "__main__":
    main()
