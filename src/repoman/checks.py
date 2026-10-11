"""RepoMan self-check (preflight) for `repoman doctor`.

Validates the conductor's own wiring: installed manager commands and skills.
This catches a manager that is selected but not installed, or too old.

Every manager is a host command. The host profile puts it on `PATH`, and RepoMan
runs it by name. A manager with a ``min_version`` also gets a ``version:<key>`` row.
RepoMan reads no Vendomat closure.

Two disciplines this module holds to, because it is the *diagnostic* layer:

* **Never crash on the inputs it exists to diagnose.** Every filesystem read and
  every subprocess call is guarded. A doctor that raises is strictly worse than one
  that reports ``fail``.
* **Validate the binary that actually runs.** That is the first match on ``PATH``.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .registry import REGISTRY, REMOVED_MANAGERS, Manager

# A self-check level maps to an exit-code contribution. "warn" is non-fatal (0);
# "fail" is a finding the caller must act on → 1 (the shared 0/1/2 contract).
_LEVELS = {"ok": 0, "warn": 0, "fail": 1}


@dataclass
class SelfCheck:
    name: str
    level: str  # "ok" | "warn" | "fail"
    detail: str = ""


@dataclass(frozen=True)
class Context:
    """Where ``repoman doctor`` is running, and why (project 13 preflight).

    ``kind`` is one of:

    * ``managed-repo-shell`` — inside a managed repo's devenv shell
      (``REPOMAN_MANAGERS`` exported by the meta-module's ``config.env``).
    * ``managed-repo-bare-shell`` — inside a managed repo, but with no shell
      environment (``.repoman/project.toml`` present).
    * ``not-a-repo`` — neither.

    ``repo_root`` is ``DEVENV_ROOT`` when in-shell, else the detected repo root
    (first marker match walking up from ``start``) or ``start`` itself.
    ``reason`` is one human sentence for the report.
    """

    kind: str
    repo_root: str
    reason: str


def detect_context(start: str) -> Context:
    """Classify the context a ``doctor`` run finds itself in.

    Marker precedence:

    1. ``REPOMAN_MANAGERS`` set in the environment — **even the empty string** —
       means a managed-repo **shell**. The meta-module exports it via
       ``config.env``, so it is present in both ``devenv shell`` and ``devenv
       tasks run``, and nowhere else. Empty = "wire nothing" is still a managed
       repo, mirroring ``_enabled()``'s unset-vs-empty distinction.
    2. ``.repoman/project.toml`` in ``start`` or any ancestor means a managed
       repo in a **bare shell**. It is the roster manifest, so every real consumer
       has one. gitman 0.12 writes no marker file. Absence does not prove
       not-a-repo (a repo that has not written its manifest yet has none) —
       accepted limitation; the message still names the right invocation.
    3. Neither → ``not-a-repo``.

    Explicitly NOT signals: ``DEVENV_ROOT`` / ``DEVENV_STATE`` alone. Plenty of devenv
    projects don't use repoman; only ``REPOMAN_MANAGERS`` proves a repoman-managed shell.

    Walks ``start`` → root and stops at the first match, so a repo nested under
    another repo resolves to the nearest one.
    """

    if "REPOMAN_MANAGERS" in os.environ:
        root = os.environ.get("DEVENV_ROOT") or start
        return Context("managed-repo-shell", root, "inside a RepoMan-managed devenv shell")
    current = Path(start).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".repoman" / "project.toml").is_file():
            return Context(
                "managed-repo-bare-shell",
                str(candidate),
                "inside a RepoMan-managed repo, but not its devenv shell",
            )
    return Context("not-a-repo", start, "not inside a repoman-managed repo")


def manager_binary(manager: Manager) -> Path | None:
    """The absolute path of ``manager.command`` on ``PATH``, or ``None``."""

    found = shutil.which(manager.command)
    return Path(found) if found else None


# ------------------------------------------------------------------ self-check


def _installed_check(manager: Manager) -> SelfCheck:
    """A manager must be an executable file on ``PATH``."""

    name = f"installed:{manager.key}"
    binary = manager_binary(manager)
    if binary is None:
        return SelfCheck(name, "fail", f"{manager.command} not on PATH")
    if not binary.exists() or not os.access(binary, os.X_OK):
        return SelfCheck(name, "fail", f"{binary} missing or not executable")
    return SelfCheck(name, "ok", str(binary))


def _dotted_version(text: str) -> tuple[int, int, int] | None:
    """First ``X.Y.Z`` in ``text`` as a tuple, or ``None``."""

    found = re.search(r"\b(\d+)\.(\d+)\.(\d+)", text)
    return (int(found[1]), int(found[2]), int(found[3])) if found else None


def _version_check(manager: Manager) -> SelfCheck | None:
    """Check that a manager reports at least ``min_version`` for ``--version``."""

    if not manager.min_version:
        return None
    name = f"version:{manager.key}"
    binary = manager_binary(manager)
    if binary is None or not binary.exists() or not os.access(binary, os.X_OK):
        return SelfCheck(name, "fail", f"cannot read version; {binary or manager.command} is missing")
    try:
        result = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return SelfCheck(name, "fail", f"cannot read version from {binary}: {exc}")
    output = (result.stdout or result.stderr).strip()
    if result.returncode != 0:
        return SelfCheck(name, "fail", f"{binary} --version exited {result.returncode}: {output}")
    actual = _dotted_version(output)
    if actual is None:
        return SelfCheck(name, "fail", f"unrecognized version from {binary}: {output!r}")
    needed = _dotted_version(manager.min_version)
    level = "ok" if needed is not None and actual >= needed else "fail"
    shown = ".".join(map(str, actual))
    return SelfCheck(name, level, f"{binary} reports {shown}; needs {manager.min_version} or later")


def _gitman_interface_check(manager: Manager) -> SelfCheck:
    """Check that ``gitman`` is the work-only tool and that ``jj`` is new enough.

    gitman 0.12 has one command, ``work``, and ``work`` needs ``jj workspace add
    --colocate`` (jj 0.46.0 or later). An older gitman answers ``status`` and
    ``land`` with a usage error, so the router would send the agent to commands
    that fail.
    """

    binary = manager_binary(manager)
    if binary is None or not binary.exists():
        return SelfCheck("interface:git", "fail", f"{manager.command} is missing")
    try:
        help_result = subprocess.run([str(binary), "--help"], capture_output=True, text=True, timeout=5, check=False)
        jj_result = subprocess.run(["jj", "version"], capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return SelfCheck("interface:git", "fail", f"cannot check gitman and jj: {exc}")
    if help_result.returncode != 0 or not re.search(r"^usage: gitman .*\{work\}", help_result.stdout, re.M):
        return SelfCheck("interface:git", "fail", f"{binary} is not the work-only gitman (0.12 or later)")
    version = _dotted_version(jj_result.stdout)
    if jj_result.returncode != 0 or version is None or version < (0, 46, 0):
        return SelfCheck("interface:git", "fail", "gitman work needs jj 0.46.0 or later")
    return SelfCheck("interface:git", "ok", f"{binary}; jj {'.'.join(map(str, version))}")


def _skill_defers(path: Path) -> bool | None:
    """Whether a sub-skill defers to the entrypoint; ``None`` if unreadable."""

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return "repoman` skill" in text or "repoman skill" in text


def run_self_check(managers: list[Manager], repo_root: str, skills_dir: str) -> list[SelfCheck]:
    """Validate the conductor's own wiring for the enabled ``managers``."""

    out: list[SelfCheck] = []

    for m in managers:
        out.append(_installed_check(m))
        version_check = _version_check(m)
        if version_check is not None:
            out.append(version_check)
        if m.key == "git":  # gitman has no `--version`, so its floor is an interface probe
            out.append(_gitman_interface_check(m))

    skill = Path(repo_root) / skills_dir / "repoman" / "SKILL.md"
    out.append(
        SelfCheck(
            "skill:entrypoint",
            "ok" if skill.exists() else "warn",
            str(skill) if skill.exists() else "missing — run `repoman install-skills`",
        )
    )

    # Sub-skill discipline: a manager's own skill (if installed here) should defer
    # cross-domain ordering up to the repoman entrypoint (docs/SKILLS.md §contract).
    # warn-only — sub-skills are owned by each manager and may not be installed yet.
    for m in managers:
        sub = Path(repo_root) / skills_dir / m.skill / "SKILL.md"
        if not sub.exists():
            continue  # not installed; not our artifact
        defers = _skill_defers(sub)
        if defers is None:
            out.append(SelfCheck(f"skill:{m.key}:defers", "warn", f"unreadable: {sub}"))
        else:
            out.append(
                SelfCheck(
                    f"skill:{m.key}:defers",
                    "ok" if defers else "warn",
                    "" if defers else "missing deferral to the repoman entrypoint",
                )
            )

    return out


def roster_check(keys: list[str]) -> SelfCheck | None:
    """Warn about roster keys that name no manager; ``None`` when all are known.

    The CLI drops these keys so a stale roster cannot crash it. This row makes the
    stale entry visible. A key that RepoMan removed names the release that removed it.
    """

    notes: list[str] = []
    for key in dict.fromkeys(keys):
        if key in REGISTRY:
            continue
        if key in REMOVED_MANAGERS:
            notes.append(f"'{key}' was removed in {REMOVED_MANAGERS[key]}")
        else:
            notes.append(f"'{key}' is not a RepoMan manager")
    if not notes:
        return None
    return SelfCheck(
        "roster:unknown-manager",
        "warn",
        "; ".join(notes) + " — drop it from .repoman/project.toml",
    )


def self_check_exit(checks: list[SelfCheck]) -> int:
    """Worst exit contribution across the self-checks (0 if none)."""

    return max((_LEVELS.get(c.level, 1) for c in checks), default=0)


def format_self_check(checks: list[SelfCheck]) -> str:
    mark = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}
    return "\n".join(f"{mark.get(c.level, '?')} {c.name}" + (f" — {c.detail}" if c.detail else "") for c in checks)
