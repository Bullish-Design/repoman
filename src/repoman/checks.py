"""RepoMan self-check (preflight) for `repoman doctor`.

Validates the conductor's own wiring before delegating to manager doctors:
the lock, the lock↔managers consistency, installed manager CLIs, and skills.
This catches the class of problem the spike hit — a manager selected but not
installed, or a lock/manager mismatch — before the sub-doctors even run.
"""

from __future__ import annotations

import os
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .registry import Manager

# A self-check level maps to an exit-code contribution. "warn" is non-fatal (0);
# "fail" is broken wiring → 2 (infra/config), merged with the sub-doctors' worst.
_LEVELS = {"ok": 0, "warn": 0, "fail": 2}


@dataclass
class SelfCheck:
    name: str
    level: str   # "ok" | "warn" | "fail"
    detail: str = ""


def _load_lock(repo_root: str) -> tuple[dict | None, SelfCheck]:
    lock_path = Path(repo_root) / "repoman.lock"
    if not lock_path.exists():
        return None, SelfCheck("lock", "fail", f"missing: {lock_path}")
    try:
        with open(lock_path, "rb") as fh:
            return tomllib.load(fh), SelfCheck("lock", "ok", str(lock_path))
    except tomllib.TOMLDecodeError as exc:
        return None, SelfCheck("lock", "fail", f"unparseable: {exc}")


def run_self_check(managers: list[Manager], repo_root: str, skills_dir: str) -> list[SelfCheck]:
    """Validate the conductor's own wiring for the enabled ``managers``."""

    out: list[SelfCheck] = []
    data, lock_check = _load_lock(repo_root)
    out.append(lock_check)

    if data is not None:
        if "repoman" not in data:
            out.append(SelfCheck("lock:self", "warn", "no [repoman] self entry"))
        lock_keys = set(data.get("managers", {}))
        for m in managers:
            # tolerate native-dep pseudo-entries like "git-pyjutsu" (guide 1)
            has = m.key in lock_keys or any(k.split("-", 1)[0] == m.key for k in lock_keys)
            out.append(
                SelfCheck(f"lock:{m.key}", "ok" if has else "fail",
                          "" if has else "selected but absent from repoman.lock")
            )

    for m in managers:
        present = shutil.which(m.command) is not None
        out.append(
            SelfCheck(f"installed:{m.key}", "ok" if present else "fail",
                      m.command if present else f"{m.command} not on PATH — run repoman-sync")
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
