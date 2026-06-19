"""Run sub-manager commands and aggregate their exit codes.

RepoMan is pass-through: it shells out to each manager's own CLI, lets that CLI
print its own report, and collapses the results into one exit code under the
shared ``0/1/2/3`` contract (ok / domain-decision / infra-config / invalid-usage).
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from .registry import Manager


@dataclass
class SubResult:
    """Outcome of invoking one manager."""

    manager: str
    command: list[str]
    exit_code: int
    available: bool


def run_sub(manager: Manager, args: list[str]) -> SubResult:
    """Invoke ``manager``'s CLI with ``args``, streaming its output through.

    A manager that isn't on PATH yet is reported as unavailable rather than
    raising — RepoMan may be enabled before ``repoman-sync`` has installed it.
    """

    cmd = [manager.command, *args]
    if shutil.which(manager.command) is None:
        return SubResult(manager.key, cmd, exit_code=127, available=False)
    proc = subprocess.run(cmd)  # noqa: S603 - commands come from the trusted roster
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
