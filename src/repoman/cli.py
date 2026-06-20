"""RepoMan — the agentic repo lifecycle conductor (pass-through + aggregate).

RepoMan does not re-implement any manager. It discovers which managers this repo
wired in (via ``REPOMAN_MANAGERS``, set by the devenv meta-module), then sequences
and aggregates their own CLIs. Each manager keeps its own report and its own skill.
"""

from __future__ import annotations

import os

import typer

from .aggregate import run_sub, worst_exit
from .checks import format_self_check, run_self_check, self_check_exit
from .devman.check import devman_checks
from .devman.install import install_devman
from .registry import DEFAULT_MANAGERS, REGISTRY, Manager
from .skills import install_entrypoint

_DEFAULT_DOCS_DIR = ".agents/devenv"

app = typer.Typer(
    help="RepoMan - the single agentic front door to a devenv.sh repo's lifecycle.",
    no_args_is_help=True,
)


def _enabled() -> list[Manager]:
    """Managers wired into this repo, from ``REPOMAN_MANAGERS`` or the core default."""

    raw = os.environ.get("REPOMAN_MANAGERS", "").split()
    keys = raw or DEFAULT_MANAGERS
    return [REGISTRY[key] for key in keys if key in REGISTRY]


@app.command()
def managers() -> None:
    """List the managers wired into this repo."""

    for manager in _enabled():
        typer.echo(f"{manager.key:8} {manager.command:10} [{manager.tier:11}] {manager.summary}")


@app.command()
def doctor(
    self_only: bool = typer.Option(
        False, "--self-only", help="Run only the RepoMan preflight; skip the manager doctors."
    ),
) -> None:
    """Self-check the RepoMan wiring, then run every enabled manager's doctor.

    Exit = worst of the self-check contribution and the sub-doctors' worst exit
    code, under the shared 0/1/2/3 contract.
    """

    managers = _enabled()
    skills_dir = os.environ.get("REPOMAN_SKILLS_DIR", ".claude/skills")
    repo_root = os.environ.get("DEVENV_ROOT", os.getcwd())

    docs_dir = os.environ.get("REPOMAN_DOCS_DIR", _DEFAULT_DOCS_DIR)

    typer.echo("=== repoman (self-check) ===")
    self_checks = run_self_check(managers, repo_root, skills_dir)
    self_checks += devman_checks(repo_root, skills_dir, docs_dir)
    typer.echo(format_self_check(self_checks))
    self_code = self_check_exit(self_checks)

    if self_only:
        raise typer.Exit(code=self_code)

    results = []
    for manager in managers:
        if manager.doctor is None:
            typer.echo(f"\n=== {manager.key} ({manager.command}) — no doctor, skipped ===")
            continue
        typer.echo(f"\n=== {manager.key} ({manager.command}) ===")
        results.append(run_sub(manager, manager.doctor))
    raise typer.Exit(code=max(self_code, worst_exit(results)))


@app.command()
def status() -> None:
    """Show each manager's status side by side; exit = worst sub-exit."""

    results = []
    for manager in _enabled():
        if manager.status is None:
            continue
        typer.echo(f"\n=== {manager.key} ({manager.command}) ===")
        results.append(run_sub(manager, manager.status))
    raise typer.Exit(code=worst_exit(results))


@app.command("install-skills")
def install_skills() -> None:
    """Generate the entrypoint skill and install devman's devenv-literacy assets."""

    skills_dir = os.environ.get("REPOMAN_SKILLS_DIR", ".claude/skills")
    docs_dir = os.environ.get("REPOMAN_DOCS_DIR", _DEFAULT_DOCS_DIR)
    repo_root = os.environ.get("DEVENV_ROOT", os.getcwd())
    dest = install_entrypoint(_enabled(), skills_dir, repo_root)
    typer.echo(f"repoman: wrote entrypoint skill → {dest}")
    written = install_devman(skills_dir, docs_dir, repo_root)
    typer.echo(f"repoman: installed devman assets ({len(written)} files) → {skills_dir}, {docs_dir}")


def main() -> None:
    """Entry point for the repoman CLI."""

    app()


if __name__ == "__main__":
    main()
