"""RepoMan self-check (preflight) for `repoman doctor`.

Validates the conductor's own wiring before delegating to manager doctors:
Vendomat's store toolchain, its provenance manifest, installed manager CLIs,
and skills. This catches the class of problem the spike hit — a manager
selected but not installed, or a provider mismatch — before sub-doctors run.

Project 12: the manager family splits by install model. Pure-CLI managers
(`install == "toolchain"`) live in one system-wide shared venv, validated
against the manifest `repoman-sync` recorded inside it. uv-declared
managers (`install == "uv"`, today: testee) live in the consumer's uv graph,
validated against `pyproject.toml`.

Two disciplines this module holds to, because it is the *diagnostic* layer:

* **Never crash on the inputs it exists to diagnose.** Every filesystem read is
  guarded (`OSError`, decode errors, malformed TOML). A doctor that raises is
  strictly worse than one that reports ``fail``.
* **Validate the binary that actually runs.** The nix tasks exec absolute paths
  (``"$toolchainBin"/gitman``), so ``installed:<key>`` resolves the same absolute
  path rather than trusting ``PATH`` — and flags the case where ``PATH`` would
  hand you a *different* copy.
"""

from __future__ import annotations

import json
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
      environment (``gitman.toml`` / ``.gitman`` markers present).
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
    2. ``gitman.toml`` or ``.gitman/`` in ``start`` or any ancestor means a
       managed repo in a **bare shell**. gitman init/seed creates these, so every
       real consumer has one. Absence does not prove not-a-repo (a freshly
       rendered, not-yet-inited repo has none) — accepted limitation; the message
       still names the right invocation.
    3. Neither → ``not-a-repo``.

    Explicitly NOT signals: ``DEVENV_ROOT`` / ``DEVENV_STATE`` /
    ``REPOMAN_TOOLCHAIN_BIN`` alone. Plenty of devenv projects don't use repoman;
    only ``REPOMAN_MANAGERS`` proves a repoman-managed shell.

    Walks ``start`` → root and stops at the first match, so a repo nested under
    another repo resolves to the nearest one.
    """

    if "REPOMAN_MANAGERS" in os.environ:
        root = os.environ.get("DEVENV_ROOT") or start
        return Context("managed-repo-shell", root, "inside a RepoMan-managed devenv shell")
    current = Path(start).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "gitman.toml").exists() or (candidate / ".gitman").is_dir():
            return Context(
                "managed-repo-bare-shell",
                str(candidate),
                "inside a RepoMan-managed repo, but not its devenv shell",
            )
    return Context("not-a-repo", start, "not inside a repoman-managed repo")


def _normalize(name: str) -> str:
    """PEP 503 name normalisation."""

    return re.sub(r"[-_.]+", "-", name).lower()


def consumer_venv_bin() -> Path | None:
    """The consumer devenv venv's bin dir — where a uv-declared manager lands.

    Mirrors ``modules/managers/testee.nix``, which execs ``${config.devenv.state}/venv/bin/testee``.
    ``DEVENV_STATE`` is exported by devenv; fall back to the conventional layout
    under ``DEVENV_ROOT`` so the check still works outside a devenv shell.
    """

    state = os.environ.get("DEVENV_STATE")
    if state:
        return Path(state) / "venv" / "bin"
    root = os.environ.get("DEVENV_ROOT")
    if root:
        return Path(root) / ".devenv" / "state" / "venv" / "bin"
    return None


def toolchain_bin() -> Path | None:
    """The Nix store bin dir exported by Vendomat, if the shell provides it."""

    env = os.environ.get("REPOMAN_TOOLCHAIN_BIN")
    return Path(env) if env else None


def manager_binary(manager: Manager) -> Path | None:
    """The absolute path the nix tasks actually exec for ``manager``, if knowable.

    ``None`` means "no absolute path is derivable here" — the caller falls back to
    a ``PATH`` lookup.
    """

    if manager.install == "toolchain":
        bin_dir = toolchain_bin()
        return bin_dir / manager.command if bin_dir else None
    bin_dir = consumer_venv_bin()
    return bin_dir / manager.command if bin_dir else None


def _read_toml(path: Path) -> tuple[dict | None, str | None]:
    """``(data, error)`` — never raises. ``error`` is a human-readable reason."""

    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh), None
    except tomllib.TOMLDecodeError as exc:
        return None, f"unparseable: {exc}"
    except OSError as exc:
        return None, f"unreadable: {exc.strerror or exc}"


def _load_toolchain_manifest(bin_dir: Path) -> tuple[dict | None, SelfCheck]:
    """Read Vendomat's provenance manifest for the materialized store closure."""

    configured = os.environ.get("REPOMAN_TOOLCHAIN_MANIFEST")
    path = Path(configured) if configured else bin_dir.parent / "share" / "vendomat" / "toolchain.json"
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return None, SelfCheck("toolchain:store", "fail", f"unreadable store manifest {path}: {exc}")
    if not isinstance(data, dict) or not isinstance(data.get("tools"), dict):
        return None, SelfCheck("toolchain:store", "fail", f"invalid store manifest {path}")
    return data, SelfCheck("toolchain:store", "ok", str(path))


def _requirement_name(req: str) -> str:
    """'testee>=0.3 ; python_version>"3.12"' -> 'testee' (PEP 508 head, normalized)."""

    head = re.split(r"[\s\[<>=!~;@()]", req.strip(), maxsplit=1)[0]
    return _normalize(head)


def uv_declared_in(pyproject: dict, package: str) -> str | None:
    """Which pyproject table declares ``package``, or None. Generic over any uv manager (D5)."""

    target = _normalize(package)
    project = pyproject.get("project") or {}
    tables: list[tuple[str, list]] = [("[project.dependencies]", project.get("dependencies") or [])]
    for extra, reqs in (project.get("optional-dependencies") or {}).items():
        tables.append((f"[project.optional-dependencies] {extra}", reqs or []))
    for group, reqs in (pyproject.get("dependency-groups") or {}).items():
        tables.append((f"[dependency-groups] {group}", reqs or []))
    for label, reqs in tables:
        # A malformed table may not be a list at all; and dependency-groups entries
        # may be {include-group = "..."} dicts — skip anything that isn't a string.
        if not isinstance(reqs, list):
            continue
        if any(isinstance(r, str) and _requirement_name(r) == target for r in reqs):
            return label
    return None


def _load_pyproject(repo_root: str) -> tuple[dict | None, str | None]:
    """``(data, error)`` for ``<repo_root>/pyproject.toml`` — never raises."""

    path = Path(repo_root) / "pyproject.toml"
    if not path.exists():
        return None, None  # genuinely absent, not broken
    return _read_toml(path)


# ------------------------------------------------------------------ self-check


def _installed_check(manager: Manager) -> SelfCheck:
    """Validate the exact binary the nix tasks exec, not merely a PATH hit.

    The manager tasks run absolute paths (``"$toolchainBin"/gitman``), so a green
    ``PATH`` lookup can coexist with a task that dies on no-such-file. When both
    exist but differ, that shadowing IS the finding — report it.
    """

    heal = "run `repoman-sync`" if manager.install == "toolchain" else "run `uv sync`"
    expected = manager_binary(manager)
    on_path = shutil.which(manager.command)

    if expected is None:
        # No absolute path is derivable (uv manager outside a devenv shell) — PATH is
        # the best available signal.
        return SelfCheck(
            f"installed:{manager.key}",
            "ok" if on_path else "fail",
            on_path or f"{manager.command} not on PATH — {heal}",
        )

    if not expected.exists():
        detail = f"{expected} missing — {heal}"
        if on_path:
            detail += f" (a different {manager.command} is on PATH at {on_path})"
        return SelfCheck(f"installed:{manager.key}", "fail", detail)

    if on_path:
        try:
            shadowed = Path(on_path).resolve() != expected.resolve()
        except OSError:
            shadowed = False
        if shadowed:
            return SelfCheck(
                f"installed:{manager.key}",
                "warn",
                f"{expected} is what the tasks run, but PATH resolves {manager.command}"
                f" to {on_path} — the two can disagree",
            )
    return SelfCheck(f"installed:{manager.key}", "ok", str(expected))


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

    # --- toolchain: the Vendomat store closure -------------------------------
    bin_dir = toolchain_bin()
    have_toolchain = bin_dir is not None and (bin_dir / "repoman").exists()
    out.append(
        SelfCheck(
            "toolchain:store",
            "ok" if have_toolchain else "fail",
            str(bin_dir)
            if have_toolchain
            else "REPOMAN_TOOLCHAIN_BIN is unset or has no repoman — import Vendomat's consumer module",
        )
    )

    data = None
    if have_toolchain and bin_dir is not None:
        assert bin_dir is not None
        data, manifest_check = _load_toolchain_manifest(bin_dir)
        out.append(manifest_check)
        if data is not None and "repoman" not in (data.get("tools") or {}):
            out.append(SelfCheck("toolchain:self", "fail", "store manifest has no repoman entry"))

    pyproject, pyproject_error = _load_pyproject(repo_root)
    if pyproject_error is not None:
        out.append(SelfCheck("pyproject", "fail", f"{repo_root}/pyproject.toml {pyproject_error}"))
    toolchain_tools = (data or {}).get("tools", {})

    for m in managers:
        if m.install == "uv":
            where = uv_declared_in(pyproject, m.package) if pyproject else None
            out.append(
                SelfCheck(
                    f"uv:{m.key}",
                    "ok" if where else "fail",
                    f"uv-declared — {where}"
                    if where
                    else f"{m.package} not declared in pyproject.toml — add it to "
                    f"[dependency-groups] dev (+ [tool.uv.sources]) and run `uv sync`",
                )
            )
            continue
        if data is None:
            continue  # toolchain:store/manifest already reports the root failure
        tool = toolchain_tools.get(m.command)
        has = isinstance(tool, dict)
        out.append(
            SelfCheck(
                f"lock:{m.key}",
                "ok" if has else "fail",
                "" if has else ("selected but absent from Vendomat's store manifest"),
            )
        )
        if has and isinstance(tool.get("version"), str):
            out.append(SelfCheck(f"version:{m.key}", "ok", f"{m.package} {tool['version']} (Nix store)"))

    # --- installed:<key> (the exact binary the tasks exec) ----------------------
    for m in managers:
        out.append(_installed_check(m))

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
        out.append(
            SelfCheck(
                f"provisioned:{m.key}",
                "ok" if signalled else "warn",
                ""
                if signalled
                else f"{m.key} selected but its nix module isn't imported — add the "
                f"'{m.nix_input}' input to devenv.yaml, then `devenv update` + repoman-sync",
            )
        )

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


def self_check_exit(checks: list[SelfCheck]) -> int:
    """Worst exit contribution across the self-checks (0 if none)."""

    return max((_LEVELS.get(c.level, 2) for c in checks), default=0)


def format_self_check(checks: list[SelfCheck]) -> str:
    mark = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}
    return "\n".join(f"{mark.get(c.level, '?')} {c.name}" + (f" — {c.detail}" if c.detail else "") for c in checks)
