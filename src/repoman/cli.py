"""RepoMan — the agentic repo lifecycle conductor (pass-through + aggregate).

RepoMan does not re-implement any manager. It discovers which managers this repo
wired in (via ``REPOMAN_MANAGERS``, set by the devenv meta-module), then sequences
and aggregates their own CLIs. Each manager keeps its own report and its own skill.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import typer

from . import __version__
from .aggregate import SubResult, run_sub, worst_exit
from .checks import (
    Context,
    SelfCheck,
    detect_context,
    format_self_check,
    run_self_check,
    self_check_exit,
)
from .devman.check import skill_ownership_checks
from .registry import DEFAULT_MANAGERS, REGISTRY, Manager
from .skills import SkillsDirError, install_entrypoint

app = typer.Typer(
    help="RepoMan - the single agentic front door to a devenv.sh repo's lifecycle.",
    no_args_is_help=True,
)

#: Exit code for "the conductor itself is broken" under the shared 0/1/2/3 contract.
#: Notably NOT 1 — that means "a domain decision is needed", which is what a caller
#: would otherwise read out of an unhandled traceback.
_INFRA = 2

#: Project-14 seam: once the bootstrap ceremony doc exists, drop its path here and
#: the `not-a-repo` doctor message gains a "bootstrapping a new repo?" pointer to
#: it. Inert while the file is absent — nothing else in this pass depends on it.
_BOOTSTRAP_DOC = "docs/BOOTSTRAP.md"


def _skills_dir() -> str:
    return os.environ.get("REPOMAN_SKILLS_DIR", ".agents/skills")


def _repo_root() -> str:
    return os.environ.get("DEVENV_ROOT", os.getcwd())


def _enabled() -> list[Manager]:
    """Managers wired into this repo, from ``REPOMAN_MANAGERS`` or the core default.

    An *unset* ``REPOMAN_MANAGERS`` means "nobody configured a roster" → the core
    default. An *empty* one means the nix module was given ``managers = [ ]``, i.e.
    wire nothing — which must not silently become the three default managers.

    Unknown keys are dropped (never a KeyError): the registry is the trusted filter
    against a stale or hand-edited env. Duplicates are collapsed, so a roster of
    ``"git git"`` can't run gitman's doctor twice.
    """

    raw = os.environ.get("REPOMAN_MANAGERS")
    keys = raw.split() if raw is not None else DEFAULT_MANAGERS
    enabled: list[Manager] = []
    seen: set[str] = set()
    for key in keys:
        if key in REGISTRY and key not in seen:
            seen.add(key)
            enabled.append(REGISTRY[key])
    return enabled


def _report(result: SubResult) -> SubResult:
    """Echo why a manager produced no report, so the failure isn't a silent header."""

    if not result.available and result.reason:
        typer.echo(f"repoman: {result.reason}", err=True)
    return result


def _context_hint(context: Context) -> str:
    """The invocation that fixes a wrong-context doctor run."""

    if context.kind == "not-a-repo":
        # No repo is detectable, so `<repo>` is honestly a placeholder — the shape
        # of the fix, not a path we can know.
        return "cd <repo> && devenv shell -- repoman doctor"
    return f"cd {context.repo_root} && devenv shell -- repoman doctor"


def format_context_failure(context: Context) -> str:
    """The plain-text report for a doctor run outside a managed-repo shell.

    This IS the report: no ``=== repoman (self-check) ===`` header, no row lines.
    """

    hint = _context_hint(context)
    if context.kind == "not-a-repo":
        lines = [
            "repoman: not inside a repoman-managed repo",
            "",
            "There is no managed repo here (no gitman.toml/.gitman and no REPOMAN_* shell",
            "environment). `repoman doctor` checks a repo's RepoMan wiring; run it from",
            "inside a managed repo's devenv shell:",
            "",
            f"    {hint}",
        ]
        bootstrap = Path(context.repo_root) / _BOOTSTRAP_DOC
        if bootstrap.exists():
            lines += ["", f"(Bootstrapping a brand-new repo? See the bootstrap ceremony: {bootstrap})"]
        return "\n".join(lines)
    return "\n".join([
        "repoman: managed repo found, but not inside its devenv shell",
        "",
        "This looks like a RepoMan-managed repo (gitman.toml/.gitman present), but the",
        "REPOMAN_* shell environment is missing — the manager toolchain is only wired",
        "onto PATH inside the repo's devenv shell.",
        "",
        "Enter the shell, then run:",
        "",
        f"    {hint}",
    ])


def context_json(context: Context, checks: list[SelfCheck], exit_code: int) -> str:
    """The doctor's own output as family-shaped JSON (copyroom's doctor row shape).

    ``checks`` serializes ``{"name", "ok", "detail", "warn_only"}`` — ``ok`` for
    an ``ok`` row, ``warn_only`` for a ``warn`` row, both false for a ``fail``.
    ``exit`` repeats the code the process exits with, so a caller can read the
    verdict without parsing ``$?``. Sub-manager reports are not composed here —
    they stream plain and own their own format (noted follow-up).
    """

    verdict: dict[str, object] = {"ok": context.kind == "managed-repo-shell", "kind": context.kind}
    if context.kind != "managed-repo-shell":
        verdict["detail"] = context.reason
        verdict["hint"] = _context_hint(context)
    return json.dumps(
        {
            "context": verdict,
            "checks": [
                {
                    "name": c.name,
                    "ok": c.level == "ok",
                    "detail": c.detail,
                    "warn_only": c.level == "warn",
                }
                for c in checks
            ],
            "exit": exit_code,
        },
        indent=2,
    )


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"repoman {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show the RepoMan version and exit.",
    ),
) -> None:
    """RepoMan - the single agentic front door to a devenv.sh repo's lifecycle."""


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
    json_out: bool = typer.Option(
        False, "--json", help="Emit the context verdict + self-check rows as one JSON document."
    ),
) -> None:
    """Self-check the RepoMan wiring, then run every enabled manager's doctor.

    Context preflight: doctor only runs its rows inside a managed repo's devenv
    shell (``REPOMAN_MANAGERS`` set). From a bare shell in a managed repo, or
    from a non-repo directory, it short-circuits with one context message and
    exit 2 (infra/config) instead of a pile of misleading per-row failures.

    Exit = worst of the self-check contribution and the sub-doctors' worst exit
    code, under the shared 0/1/2/3 contract. With ``--json``, the context verdict
    and self-check rows are emitted as one JSON document whose ``exit`` repeats
    the process's exit code; sub-manager reports still stream plain.
    """

    context = detect_context(os.getcwd())
    if context.kind != "managed-repo-shell":
        if json_out:
            typer.echo(context_json(context, [], _INFRA))
        else:
            typer.echo(format_context_failure(context))
        raise typer.Exit(code=_INFRA)

    enabled = _enabled()

    self_checks = run_self_check(enabled, _repo_root(), _skills_dir())
    self_checks += skill_ownership_checks(_repo_root(), _skills_dir())
    self_code = self_check_exit(self_checks)

    if self_only:
        if json_out:
            typer.echo(context_json(context, self_checks, self_code))
        else:
            typer.echo("=== repoman (self-check) ===")
            typer.echo(format_self_check(self_checks))
        raise typer.Exit(code=self_code)

    if not json_out:
        typer.echo("=== repoman (self-check) ===")
        typer.echo(format_self_check(self_checks))

    results = []
    for manager in enabled:
        if manager.doctor is None:
            typer.echo(f"\n=== {manager.key} ({manager.command}) — no doctor, skipped ===")
            continue
        typer.echo(f"\n=== {manager.key} ({manager.command}) ===")
        results.append(_report(run_sub(manager, manager.doctor)))

    exit_code = max(self_code, worst_exit(results))
    if json_out:
        # JSON last: `exit` is the TRUE final code (self + sub-doctors composed),
        # so the document never lies about the verdict an agent would get from $?.
        typer.echo(context_json(context, self_checks, exit_code))
    raise typer.Exit(code=exit_code)


@app.command()
def status() -> None:
    """Show each manager's status side by side; exit = worst sub-exit."""

    results = []
    for manager in _enabled():
        if manager.status is None:
            continue
        typer.echo(f"\n=== {manager.key} ({manager.command}) ===")
        results.append(_report(run_sub(manager, manager.status)))
    raise typer.Exit(code=worst_exit(results))


@app.command("install-skills")
def install_skills() -> None:
    """Generate the entrypoint skill (the router) from the enabled roster.

    The router is the only skill RepoMan itself owns: manager sub-skills are
    tool-shipped (copyroom's canonical set via `copyroom agent-files export`)
    or genome-shipped (converged by `copyroom update`).
    """

    try:
        dest = install_entrypoint(_enabled(), _skills_dir(), _repo_root())
    except SkillsDirError as exc:
        typer.echo(f"repoman: {exc}", err=True)
        raise typer.Exit(code=3) from exc  # 3 = invalid usage
    typer.echo(f"repoman: wrote entrypoint skill → {dest}")


def main() -> None:
    """Entry point for the repoman CLI.

    Anything unexpected exits ``2`` (infra/config), never the ``1`` that a bare
    traceback would produce — under the shared contract ``1`` means "a domain
    decision is needed", so a crashed conductor must not masquerade as one.
    """

    try:
        app()
    except (KeyboardInterrupt, BrokenPipeError):
        raise SystemExit(130) from None
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - the conductor must not die with a traceback
        print(f"repoman: internal error: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(_INFRA) from exc


if __name__ == "__main__":
    main()
