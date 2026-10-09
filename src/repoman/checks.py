"""RepoMan self-check (preflight) for `repoman doctor`.

Validates the conductor's own wiring: installed manager commands and skills.
This catches a manager that is selected but not installed.

The manager family splits by install model. Host managers (`install == "path"`)
are on `PATH`: the host profile installs them, and RepoMan runs them by name.
The Testee wrapper also runs from the host profile. Its pinned Nix package supplies
the required version, which this module checks. RepoMan reads no Vendomat closure.
An optional uv manager (`install == "uv"`) lives in the consumer's uv graph.

Two disciplines this module holds to, because it is the *diagnostic* layer:

* **Never crash on the inputs it exists to diagnose.** Every filesystem read is
  guarded (`OSError`, decode errors, malformed TOML). A doctor that raises is
  strictly worse than one that reports ``fail``.
* **Validate the binary that actually runs.** A uv manager runs from the consumer
  venv. A path manager runs from ``PATH`` or its explicit binary environment
  variable. The Testee version row checks that binary against the pinned package.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .registry import Manager

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
        if (candidate / ".repoman" / "project.toml").is_file():
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
    """The consumer devenv venv's bin dir for an optional uv-installed manager.

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


def manager_binary(manager: Manager) -> Path | None:
    """The absolute path ``manager`` runs from, if knowable.

    A path manager runs from its configured environment path or ``PATH``. A uv
    manager runs from the consumer venv. ``None`` means no binary was found.
    """

    if manager.install == "path":
        configured = os.environ.get(manager.binary_env) if manager.binary_env else None
        if configured:
            return Path(configured)
        found = shutil.which(manager.command)
        return Path(found) if found else None
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
    """Validate the binary a manager runs from.

    A path manager must match the binary its task uses. A uv manager runs from the
    consumer venv, so a green ``PATH`` lookup can coexist with a missing venv binary.
    """

    if manager.install == "path":
        binary = manager_binary(manager)
        on_path = shutil.which(manager.command)
        if binary is None or not binary.exists() or not os.access(binary, os.X_OK):
            detail = f"{binary} missing or not executable" if binary else f"{manager.command} not on PATH"
            return SelfCheck(f"installed:{manager.key}", "fail", detail)
        if manager.binary_env and not on_path:
            return SelfCheck(
                f"installed:{manager.key}",
                "fail",
                f"{manager.command} is missing from PATH; add {binary.parent}",
            )
        if on_path:
            try:
                shadowed = Path(on_path).resolve() != binary.resolve()
            except OSError:
                shadowed = False
            if shadowed:
                return SelfCheck(
                    f"installed:{manager.key}",
                    "fail",
                    f"tasks use {binary}, but PATH resolves {manager.command} to {on_path}",
                )
        return SelfCheck(
            f"installed:{manager.key}",
            "ok",
            str(binary),
        )

    on_path = shutil.which(manager.command)
    expected = manager_binary(manager)
    if expected is None:
        # No venv path is derivable (outside a devenv shell) — PATH is the best signal.
        return SelfCheck(
            f"installed:{manager.key}",
            "ok" if on_path else "fail",
            on_path or f"{manager.command} not on PATH — run `uv sync`",
        )

    if not expected.exists():
        detail = f"{expected} missing — run `uv sync`"
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


def _version_check(manager: Manager) -> SelfCheck | None:
    """Check a manager version against the value exported by its pinned package."""

    if not manager.version_env:
        return None
    required = os.environ.get(manager.version_env)
    if not required:
        return SelfCheck(
            f"version:{manager.key}",
            "fail",
            f"{manager.version_env} is missing — import the pinned Testee module",
        )
    binary = manager_binary(manager)
    if binary is None or not binary.exists() or not os.access(binary, os.X_OK):
        return SelfCheck(
            f"version:{manager.key}", "fail", f"cannot read version; {binary or manager.command} is missing"
        )
    try:
        result = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return SelfCheck(f"version:{manager.key}", "fail", f"cannot read version from {binary}: {exc}")
    if result.returncode != 0:
        return SelfCheck(
            f"version:{manager.key}",
            "fail",
            f"{binary} --version exited {result.returncode}: {(result.stderr or result.stdout).strip()}",
        )
    output = (result.stdout or result.stderr).strip()
    match = re.fullmatch(r"testee\s+(\S+)", output)
    if match is None:
        return SelfCheck(f"version:{manager.key}", "fail", f"unrecognized version from {binary}: {output!r}")
    actual = match.group(1)
    level = "ok" if actual == required else "fail"
    detail = f"{binary} reports {actual}; pinned package requires {required}"
    return SelfCheck(f"version:{manager.key}", level, detail)


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
    version = re.search(r"\bjj (\d+)\.(\d+)\.(\d+)", jj_result.stdout)
    if jj_result.returncode != 0 or version is None or tuple(map(int, version.groups())) < (0, 46, 0):
        return SelfCheck("interface:git", "fail", "gitman work needs jj 0.46.0 or later")
    return SelfCheck("interface:git", "ok", f"{binary}; {version.group(0)}")


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

    pyproject, pyproject_error = _load_pyproject(repo_root)
    if pyproject_error is not None:
        out.append(SelfCheck("pyproject", "fail", f"{repo_root}/pyproject.toml {pyproject_error}"))

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

    # --- installed:<key> (the binary the manager runs from) ---------------------
    for m in managers:
        out.append(_installed_check(m))
        version_check = _version_check(m)
        if version_check is not None:
            out.append(version_check)
        if m.key == "git":
            out.append(_gitman_interface_check(m))

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

    return max((_LEVELS.get(c.level, 1) for c in checks), default=0)


def format_self_check(checks: list[SelfCheck]) -> str:
    mark = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}
    return "\n".join(f"{mark.get(c.level, '?')} {c.name}" + (f" — {c.detail}" if c.detail else "") for c in checks)
