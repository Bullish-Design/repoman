"""Run sub-manager commands and aggregate their exit codes.

RepoMan is pass-through: it shells out to each manager's own CLI, lets that CLI
print its own report, and collapses the results into one exit code under the
shared ``0/1/2/3`` contract (ok / domain-decision / infra-config / invalid-usage).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

from .checks import manager_binary
from .registry import Manager

#: Wall-clock ceiling for one sub-manager invocation. A hung manager must not hang
#: the conductor forever; generous enough for a real docs build, overridable for
#: the pathological case.
_DEFAULT_TIMEOUT = 900.0


def _timeout() -> float | None:
    raw = os.environ.get("REPOMAN_SUB_TIMEOUT")
    if raw is None:
        return _DEFAULT_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        return _DEFAULT_TIMEOUT
    return None if value <= 0 else value  # 0 / negative = no timeout, deliberately


@dataclass
class SubResult:
    """Outcome of invoking one manager."""

    manager: str
    command: list[str]
    exit_code: int
    available: bool
    #: Why the invocation didn't produce a real report ("" when it did). Rendered by
    #: the CLI — an unavailable manager used to print a bare header and nothing else.
    reason: str = ""


def resolve(manager: Manager) -> str | None:
    """The executable to invoke for ``manager``, or ``None`` if it isn't installed.

    Prefers the absolute path the nix tasks use, so `repoman doctor` and
    `devenv tasks run` can never disagree about which copy is in play; falls back
    to a PATH lookup when no absolute path is derivable.
    """

    expected = manager_binary(manager)
    if expected is not None and expected.exists():
        return str(expected)
    return shutil.which(manager.command)


def run_sub(manager: Manager, args: list[str]) -> SubResult:
    """Invoke ``manager``'s CLI with ``args``, streaming its output through.

    A manager that isn't installed yet is reported as unavailable rather than
    raising — RepoMan may be enabled before ``repoman-sync`` has installed it.
    """

    cmd = [manager.command, *args]
    executable = resolve(manager)
    if executable is None:
        return SubResult(
            manager.key,
            cmd,
            exit_code=127,
            available=False,
            reason=f"{manager.command} is not installed — "
            + ("run `repoman-sync --machine`" if manager.install == "toolchain" else "run `uv sync`"),
        )
    try:
        proc = subprocess.run([executable, *args], timeout=_timeout())  # noqa: S603 - trusted roster
    except subprocess.TimeoutExpired:
        return SubResult(
            manager.key,
            cmd,
            exit_code=2,
            available=False,
            reason=f"{manager.command} timed out after {_timeout():.0f}s (raise or disable with REPOMAN_SUB_TIMEOUT)",
        )
    except OSError as exc:
        return SubResult(
            manager.key,
            cmd,
            exit_code=2,
            available=False,
            reason=f"{manager.command} could not be executed: {exc.strerror or exc}",
        )
    return SubResult(manager.key, cmd, exit_code=proc.returncode, available=True)


def worst_exit(results: list[SubResult]) -> int:
    """Collapse sub-results into one exit code.

    Severity order: ``3`` (invalid usage) > ``2`` (infra/config) > ``1`` (domain
    decision) > ``0`` (ok). An unavailable manager, or any unrecognized exit code,
    is treated as ``2`` (infra/config) — the toolchain isn't ready.
    """

    worst = 0
    for result in results:
        code = result.exit_code if result.available else 2
        if code not in (0, 1, 2, 3):
            code = 2
        worst = max(worst, code)
    return worst
