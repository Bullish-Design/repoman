"""RepoMan self-check (preflight) for `repoman doctor`.

Validates the conductor's own wiring before delegating to manager doctors:
the system-wide toolchain venv, the machine manifest it was synced from, the
lock↔managers consistency, installed manager CLIs, and skills. This catches
the class of problem the spike hit — a manager selected but not installed, or
a lock/manager mismatch — before the sub-doctors even run.

Project 12: the manager family splits by install model. Pure-CLI managers
(`install == "toolchain"`) live in one system-wide shared venv, validated
against the manifest `repoman-sync --machine` recorded inside it. uv-declared
managers (`install == "uv"`, today: testee) live in the consumer's uv graph,
validated against `pyproject.toml`.
"""

from __future__ import annotations

import os
import re
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .registry import Manager

# A self-check level maps to an exit-code contribution. "warn" is non-fatal (0);
# "fail" is broken wiring → 2 (infra/config), merged with the sub-doctors' worst.
_LEVELS = {"ok": 0, "warn": 0, "fail": 2}

_DEFAULT_TOOLCHAIN = "repoman/venv"


@dataclass
class SelfCheck:
    name: str
    level: str   # "ok" | "warn" | "fail"
    detail: str = ""


def toolchain_venv() -> Path:
    """The system-wide toolchain venv (project 12), mirroring repoman-sync.sh's resolution."""

    env = os.environ.get("REPOMAN_TOOLCHAIN_VENV")
    if env:
        return Path(env)
    data_home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(data_home) / _DEFAULT_TOOLCHAIN


def _load_toolchain_manifest(venv: Path) -> tuple[dict | None, SelfCheck]:
    """Read the lock `repoman-sync --machine` recorded inside the shared venv (D7)."""

    path = venv / "repoman-toolchain.toml"
    if not path.exists():
        return None, SelfCheck(
            "toolchain:lock", "warn",
            f"no manifest at {path} — re-run `repoman-sync --machine` to record one",
        )
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh), SelfCheck("toolchain:lock", "ok", str(path))
    except tomllib.TOMLDecodeError as exc:
        return None, SelfCheck("toolchain:lock", "warn", f"unparseable: {exc}")


def _requirement_name(req: str) -> str:
    """'testee>=0.3 ; python_version>"3.12"' -> 'testee' (PEP 508 head, normalized)."""

    head = re.split(r"[\s\[<>=!~;@()]", req.strip(), maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", head).lower()


def uv_declared_in(pyproject: dict, package: str) -> str | None:
    """Which pyproject table declares ``package``, or None. Generic over any uv manager (D5)."""

    target = re.sub(r"[-_.]+", "-", package).lower()
    project = pyproject.get("project") or {}
    tables: list[tuple[str, list]] = [("[project.dependencies]", project.get("dependencies") or [])]
    for extra, reqs in (project.get("optional-dependencies") or {}).items():
        tables.append((f"[project.optional-dependencies] {extra}", reqs or []))
    for group, reqs in (pyproject.get("dependency-groups") or {}).items():
        tables.append((f"[dependency-groups] {group}", reqs or []))
    for label, reqs in tables:
        # dependency-groups entries may be {include-group = "..."} dicts — skip non-strings.
        if any(isinstance(r, str) and _requirement_name(r) == target for r in reqs):
            return label
    return None


def _load_pyproject(repo_root: str) -> dict | None:
    path = Path(repo_root) / "pyproject.toml"
    if not path.exists():
        return None
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError:
        return None


def run_self_check(managers: list[Manager], repo_root: str, skills_dir: str) -> list[SelfCheck]:
    """Validate the conductor's own wiring for the enabled ``managers``."""

    out: list[SelfCheck] = []

    # --- toolchain: the system-wide shared venv (project 12) -------------------
    venv = toolchain_venv()
    have_venv = (venv / "bin" / "repoman").exists()
    out.append(SelfCheck(
        "toolchain:venv", "ok" if have_venv else "fail",
        str(venv) if have_venv
        else f"missing or incomplete: {venv} — run `repoman-sync --machine` from the repoman checkout",
    ))

    data = None
    if have_venv:
        data, manifest_check = _load_toolchain_manifest(venv)
        out.append(manifest_check)
        if data is not None and "repoman" not in data:
            out.append(SelfCheck("toolchain:self", "warn", "no [repoman] self entry"))

    pyproject = _load_pyproject(repo_root)
    lock_keys = set((data or {}).get("managers", {}))

    for m in managers:
        if m.install == "uv":
            where = uv_declared_in(pyproject, m.package) if pyproject else None
            out.append(SelfCheck(
                f"uv:{m.key}", "ok" if where else "fail",
                f"uv-declared — {where}" if where
                else f"{m.package} not declared in pyproject.toml — add it to "
                     f'[dependency-groups] dev (+ [tool.uv.sources]) and run `uv sync`',
            ))
            continue
        if data is None:
            continue  # no manifest to check against; toolchain:venv/lock already reported
        # tolerate native-dep pseudo-entries like "git-pyjutsu" (guide 1)
        has = m.key in lock_keys or any(k.split("-", 1)[0] == m.key for k in lock_keys)
        out.append(SelfCheck(
            f"lock:{m.key}", "ok" if has else "fail",
            "" if has else "selected but absent from the machine repoman.lock",
        ))

    if (Path(repo_root) / "repoman.lock").exists():
        out.append(SelfCheck(
            "lock:orphan", "warn",
            "per-repo repoman.lock is obsolete — the toolchain is machine-level; delete this file",
        ))

    # --- installed:<key> (PATH presence) ---------------------------------------
    for m in managers:
        present = shutil.which(m.command) is not None
        heal = "run `repoman-sync --machine`" if m.install == "toolchain" else "run `uv sync`"
        out.append(
            SelfCheck(f"installed:{m.key}", "ok" if present else "fail",
                      m.command if present else f"{m.command} not on PATH — {heal}")
        )

    # Nix-layer provisioning: an approach-B manager's nix module lives in the
    # manager's own repo and is pulled in by a presence-gated import that only
    # fires when the consumer declares that manager's `devenv.yaml` input (R1 —
    # inputs aren't transitive across a remote module import). checks.py runs
    # *inside* the shell and can't see devenv.yaml, so each such module signals
    # input-presence via `REPOMAN_PROVISIONED_<KEY>=1`. A missing signal means
    # the CLI installed (installed:<key> ok) but its nix module didn't import —
    # warn (non-fatal) so the gap surfaces early instead of as a confusing
    # sub-doctor error. Orthogonal to installed:<key> (the venv CLI).
    for m in managers:
        if not m.nix_input:
            continue
        signalled = os.environ.get(f"REPOMAN_PROVISIONED_{m.key.upper()}") == "1"
        out.append(SelfCheck(
            f"provisioned:{m.key}",
            "ok" if signalled else "warn",
            "" if signalled
            else f"{m.key} selected but its nix module isn't imported — add the "
                 f"'{m.nix_input}' input to devenv.yaml, then `devenv update` + repoman-sync",
        ))

    skill = Path(repo_root) / skills_dir / "repoman" / "SKILL.md"
    out.append(
        SelfCheck("skill:entrypoint", "ok" if skill.exists() else "warn",
                  str(skill) if skill.exists() else "missing — run `repoman install-skills`")
    )

    # Sub-skill discipline: a manager's own skill (if installed here) should defer
    # cross-domain ordering up to the repoman entrypoint (docs/SKILLS.md §contract).
    # warn-only — sub-skills are owned by each manager and may not be installed yet.
    for m in managers:
        sub = Path(repo_root) / skills_dir / m.skill / "SKILL.md"
        if not sub.exists():
            continue  # not installed; not our artifact
        text = sub.read_text()
        defers = "repoman` skill" in text or "repoman skill" in text
        out.append(
            SelfCheck(f"skill:{m.key}:defers", "ok" if defers else "warn",
                      "" if defers else "missing deferral to the repoman entrypoint")
        )

    return out


def self_check_exit(checks: list[SelfCheck]) -> int:
    """Worst exit contribution across the self-checks (0 if none)."""

    return max((_LEVELS.get(c.level, 2) for c in checks), default=0)


def format_self_check(checks: list[SelfCheck]) -> str:
    mark = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}
    return "\n".join(
        f"{mark.get(c.level, '?')} {c.name}" + (f" — {c.detail}" if c.detail else "")
        for c in checks
    )
