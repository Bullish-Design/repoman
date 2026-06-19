# Guide 3 — `repoman doctor` self-check (preflight)

**Goal:** give `repoman doctor` value beyond pass-through. Today it only runs each
manager's own doctor. Add a **RepoMan self-check** that runs *first* and validates the
conductor's own wiring: lock ↔ managers ↔ installed CLIs ↔ skills. This catches the class
of problem the spike hit (a manager selected but not installed, a lock/manager mismatch)
before the sub-doctors even run.

## Scope

- **In:** Python-detectable preflight — `repoman.lock` integrity, lock↔`managers`
  consistency, each enabled manager's CLI on PATH, entrypoint skill present, (optional)
  sub-skill deferral-footer discipline.
- **Out:** nix-level consumer misconfig (e.g. the `languages.python.version` pin needing
  `nixpkgs-python`). That's a Nix-eval concern, not visible from Python — note it as a
  future nix-side check, don't fake it here.

## Levels & exit mapping

| Level | Meaning | Exit contribution |
|---|---|---|
| `ok` | fine | 0 |
| `warn` | non-fatal (e.g. entrypoint skill missing) | 0 |
| `fail` | broken wiring (e.g. selected manager not installed) | 2 (infra/config) |

The self-check's contribution is merged with the sub-doctors' `worst_exit` (guide reuses
`aggregate.worst_exit`).

## Changes

### 1. New module `src/repoman/checks.py`

```python
"""RepoMan self-check (preflight) for `repoman doctor`.

Validates the conductor's own wiring before delegating to manager doctors:
the lock, the lock↔managers consistency, installed manager CLIs, and skills.
"""
from __future__ import annotations

import os
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .registry import Manager

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

    skill = Path(repo_root) / skills_dir / "repoman" / "SKILL.md"
    out.append(
        SelfCheck("skill:entrypoint", "ok" if skill.exists() else "warn",
                  str(skill) if skill.exists() else "missing — run `repoman install-skills`")
    )
    return out


def self_check_exit(checks: list[SelfCheck]) -> int:
    return max((_LEVELS.get(c.level, 2) for c in checks), default=0)


def format_self_check(checks: list[SelfCheck]) -> str:
    mark = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}
    return "\n".join(
        f"{mark.get(c.level, '?')} {c.name}" + (f" — {c.detail}" if c.detail else "")
        for c in checks
    )
```

### 2. Wire into `repoman doctor` — `src/repoman/cli.py`

```python
from .checks import run_self_check, self_check_exit, format_self_check

@app.command()
def doctor() -> None:
    """Self-check the RepoMan wiring, then run every enabled manager's doctor."""
    managers = _enabled()
    skills_dir = os.environ.get("REPOMAN_SKILLS_DIR", ".claude/skills")
    repo_root = os.environ.get("DEVENV_ROOT", os.getcwd())

    typer.echo("=== repoman (self-check) ===")
    self_checks = run_self_check(managers, repo_root, skills_dir)
    typer.echo(format_self_check(self_checks))
    self_code = self_check_exit(self_checks)

    results = []
    for manager in managers:
        if manager.doctor is None:
            typer.echo(f"\n=== {manager.key} ({manager.command}) — no doctor, skipped ===")
            continue
        typer.echo(f"\n=== {manager.key} ({manager.command}) ===")
        results.append(run_sub(manager, manager.doctor))

    raise typer.Exit(code=max(self_code, worst_exit(results)))
```

> Optional flag: `repoman doctor --self-only` to run just the preflight (fast; no shelling
> out to manager doctors). Handy in CI and for the skill linter below.

### 3. (Optional) skill-footer discipline check

Extend `run_self_check` to verify each enabled manager's *own* skill (if present under
`skills_dir/<skill>/SKILL.md`) carries the deferral footer that makes the merge coherent
(see `docs/SKILLS.md` §"contract"). Keep it `warn` (sub-skills are owned by each manager
and may not be installed yet):

```python
    for m in managers:
        sub = Path(repo_root) / skills_dir / m.skill / "SKILL.md"
        if not sub.exists():
            continue  # not installed; not our artifact
        text = sub.read_text()
        ok = "repoman` skill" in text or "repoman skill" in text
        out.append(SelfCheck(f"skill:{m.key}:defers", "ok" if ok else "warn",
                             "" if ok else "missing deferral to the repoman entrypoint"))
```

## Verification

```bash
cd tests/consumer-example
# healthy case (after a normal repoman-sync):
devenv shell -- bash -c 'repoman doctor; echo exit=$?'
#   → self-check all OK, manager doctors run, exit 0

# break it on purpose:
devenv shell -- bash -c 'REPOMAN_MANAGERS="copy test session" repoman doctor; echo exit=$?'
#   → installed:session FAIL (zelligate not on PATH), lock:session FAIL, exit 2
```

Add a unit test (extends guide 2's `tests/test_checks.py`):

```python
from repoman.checks import run_self_check, self_check_exit
from repoman.registry import REGISTRY

def test_missing_lock_fails(tmp_path):
    checks = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert any(c.name == "lock" and c.level == "fail" for c in checks)
    assert self_check_exit(checks) == 2

def test_selected_manager_absent_from_lock_fails(tmp_path):
    (tmp_path / "repoman.lock").write_text('[repoman]\npackage="repoman"\nsource="path:/x"\n')
    checks = run_self_check([REGISTRY["test"]], str(tmp_path), ".claude/skills")
    assert any(c.name == "lock:test" and c.level == "fail" for c in checks)
```

## Risks

| Risk | Mitigation |
|---|---|
| `DEVENV_ROOT` unset when run outside devenv | Falls back to `os.getcwd()`; the lock check then just reports relative to cwd. |
| PATH check false-negative before first sync | That's the point — it tells the agent to run `repoman-sync`. It's `fail` (exit 2 = infra), which is correct. |
| Native pseudo-entries (`git-pyjutsu`) flagged as "absent" | The `split("-", 1)[0]` tolerance (shown) maps them to their base manager. |
| Skill-footer check noisy | Keep it `warn`, and only when the sub-skill file actually exists. |

## Outcome

`repoman doctor` becomes a genuine preflight: it tells an agent *why* the toolchain isn't
ready (lock vs managers vs PATH vs skills) instead of just forwarding sub-tool output. This
is the conductor earning its keep beyond pass-through — and it pairs naturally with guide 1
(catches a selected-but-unbuilt gitman) and guide 2 (the checks are pure and unit-tested).
