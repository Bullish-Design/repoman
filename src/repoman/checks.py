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

import os
import re
import shutil
import tomllib
from dataclasses import dataclass
from importlib.metadata import Distribution, DistributionFinder
from pathlib import Path

from .registry import Manager

# A self-check level maps to an exit-code contribution. "warn" is non-fatal (0);
# "fail" is broken wiring → 2 (infra/config), merged with the sub-doctors' worst.
_LEVELS = {"ok": 0, "warn": 0, "fail": 2}

_DEFAULT_TOOLCHAIN = "repoman/venv"


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
    ``REPOMAN_TOOLCHAIN_VENV`` alone. Plenty of devenv projects don't use repoman;
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


def toolchain_venv() -> Path:
    """The system-wide toolchain venv (project 12), mirroring repoman-sync.sh's resolution."""

    env = os.environ.get("REPOMAN_TOOLCHAIN_VENV")
    if env:
        return Path(env)
    data_home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(data_home) / _DEFAULT_TOOLCHAIN


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


def manager_binary(manager: Manager) -> Path | None:
    """The absolute path the nix tasks actually exec for ``manager``, if knowable.

    ``None`` means "no absolute path is derivable here" — the caller falls back to
    a ``PATH`` lookup.
    """

    if manager.install == "toolchain":
        return toolchain_venv() / "bin" / manager.command
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


def _load_toolchain_manifest(venv: Path) -> tuple[dict | None, SelfCheck]:
    """Read the lock `repoman-sync --machine` recorded inside the shared venv (D7)."""

    path = venv / "repoman-toolchain.toml"
    if not path.exists():
        return None, SelfCheck(
            "toolchain:lock",
            "warn",
            f"no manifest at {path} — re-run `repoman-sync --machine` to record one",
        )
    data, error = _read_toml(path)
    if error is not None:
        return None, SelfCheck("toolchain:lock", "warn", error)
    return data, SelfCheck("toolchain:lock", "ok", str(path))


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


# --------------------------------------------------------------------- versions

#: Comparison operators this module evaluates. `~=` is deliberately absent: its
#: PEP 440 semantics need full version parsing, and a wrong answer from the
#: doctor is worse than no answer, so it degrades to "not evaluated".
_SPECIFIER = re.compile(r"(==|!=|>=|<=|>|<)\s*([0-9][^,\s]*)")
_GIT_REF = re.compile(r"@v?([0-9][^@/]*)$")


def _site_packages(venv: Path) -> Path | None:
    try:
        candidates = sorted((venv / "lib").glob("python*/site-packages"))
    except OSError:
        return None
    for path in candidates:
        if path.is_dir():
            return path
    return None


def installed_distributions(venv: Path) -> dict[str, tuple[str, list[str]]] | None:
    """Distribution name → ``(version, Requires-Dist)`` for the packages inside ``venv``.

    Reads the venv's own ``site-packages`` rather than this interpreter's, so the
    answer is right regardless of which python is running ``repoman``. ``None``
    means "couldn't inspect" — the caller then emits no rows at all, because a
    false staleness alarm is worse than a missing check.
    """

    site = _site_packages(venv)
    if site is None:
        return None
    found: dict[str, tuple[str, list[str]]] = {}
    try:
        dists = list(Distribution.discover(context=DistributionFinder.Context(path=[str(site)])))
    except OSError:
        return None
    for dist in dists:
        try:
            name = dist.metadata["Name"]
            version = dist.version
            requires = dist.metadata.get_all("Requires-Dist") or []
        except (OSError, KeyError, ValueError):
            continue
        if name and version:
            found[_normalize(name)] = (version, [str(r) for r in requires])
    return found


def installed_versions(venv: Path) -> dict[str, str] | None:
    """Distribution name → version for the packages inside ``venv``."""

    dists = installed_distributions(venv)
    if dists is None:
        return None
    return {name: version for name, (version, _requires) in dists.items()}


def declared_version(source: str) -> str | None:
    """The ``[project].version`` a ``path:`` lock source's checkout declares.

    ``None`` means "no answer" — not a ``path:`` source, an unreadable checkout, or
    a project that computes its version dynamically. The caller then makes no claim.
    """

    if not source.startswith("path:"):
        return None
    data, error = _read_toml(Path(source[len("path:") :]) / "pyproject.toml")
    if error is not None or data is None:
        return None
    version = (data.get("project") or {}).get("version")
    return version if isinstance(version, str) else None


def _constraints(source: str) -> list[tuple[str, str]]:
    """The version pins a lock ``source`` implies, as ``(operator, version)`` pairs.

    A ``path:`` source pins no *range* — its checkout is the pin, and
    :func:`declared_version` reads it. A ``git+…@vX.Y.Z`` ref is an exact pin.
    """

    if source.startswith("path:"):
        return []
    if source.startswith("wheel:"):
        source = source[len("wheel:") :]
    if source.startswith("git+"):
        ref = _GIT_REF.search(source)
        return [("==", ref.group(1))] if ref else []
    return _SPECIFIER.findall(source)


def _release(version: str) -> tuple[int, ...] | None:
    """Numeric release segments, or ``None`` for anything with pre/post/dev parts.

    Refusing to guess on ``1.0rc1`` keeps this honest: the caller treats ``None``
    as "not evaluated" instead of inventing an ordering.
    """

    core = version.split("+", 1)[0]
    parts = core.split(".")
    out: list[int] = []
    for part in parts:
        if not part.isdigit():
            return None
        out.append(int(part))
    return tuple(out) if out else None


def _satisfies(installed: str, operator: str, wanted: str) -> bool | None:
    """Whether ``installed <operator> wanted`` holds; ``None`` if not evaluable."""

    left, right = _release(installed), _release(wanted)
    if left is None or right is None:
        return None
    width = max(len(left), len(right))
    left += (0,) * (width - len(left))
    right += (0,) * (width - len(right))
    return {
        "==": left == right,
        "!=": left != right,
        ">=": left >= right,
        "<=": left <= right,
        ">": left > right,
        "<": left < right,
    }.get(operator)


def version_checks(venv: Path, manifest: dict, managers: list[Manager]) -> list[SelfCheck]:
    """Compare what's installed in the toolchain venv against what the lock pins.

    This is the check that catches a *stale* toolchain: `lock:<key>` only proves a
    key is present in the recorded manifest, so without this a machine that never
    re-synced reports entirely green.
    """

    versions = installed_versions(venv)
    if versions is None:
        return []  # can't inspect the venv — stay silent rather than cry wolf

    keys = {m.key for m in managers if m.install == "toolchain"}
    entries: dict[str, object] = {}
    if isinstance(manifest.get("repoman"), dict):
        entries["repoman"] = manifest["repoman"]
    managers_table = manifest.get("managers")
    if isinstance(managers_table, dict):
        for key, entry in managers_table.items():
            # native-dep pseudo-entry: "git-pyjutsu" belongs to the "git" manager.
            # Rows are named by TOML path ("managers.git"), matching the lock itself
            # and repoman-sync's error labels — and keeping the [repoman] self entry
            # distinct from a manager that happened to be keyed "repoman".
            if key.split("-", 1)[0] in keys:
                entries[f"managers.{key}"] = entry

    out: list[SelfCheck] = []
    for key, entry in sorted(entries.items()):
        if not isinstance(entry, dict):
            continue  # malformed manifest entry; toolchain:lock shape is not our job
        source = entry.get("source")
        package = entry.get("package") or key
        if not isinstance(source, str) or not isinstance(package, str):
            continue
        installed = versions.get(_normalize(package))
        if installed is None:
            out.append(
                SelfCheck(
                    f"version:{key}",
                    "fail",
                    f"{package} is pinned in the machine lock but is not installed in {venv}"
                    " — run `repoman-sync --machine`",
                )
            )
            continue
        violated = [f"{op}{want}" for op, want in _constraints(source) if _satisfies(installed, op, want) is False]
        if violated:
            out.append(
                SelfCheck(
                    f"version:{key}",
                    "fail",
                    f"{package} {installed} installed but the machine lock pins "
                    f"{','.join(violated)} — re-run `repoman-sync --machine`",
                )
            )
            continue
        # A `path:` manager is installed --editable: its CODE follows the checkout,
        # its METADATA is a snapshot of the last sync. When the two disagree the venv
        # runs new code against the OLD dependency requirements — the failure that
        # made this row lie ("OK gitman 0.4.2") while the checkout ran 0.6.0.
        declared = declared_version(source)
        if declared is not None and _release(declared) != _release(installed) and declared != installed:
            out.append(
                SelfCheck(
                    f"version:{key}",
                    "fail",
                    f"{package} {installed} installed but the checkout at "
                    f"{source[len('path:') :]} declares {declared} — the recorded metadata is "
                    "stale; re-run `repoman-sync --machine`",
                )
            )
            continue
        out.append(SelfCheck(f"version:{key}", "ok", f"{package} {installed}"))
    return out


def _requirement_specifiers(requirement: str) -> list[tuple[str, str]]:
    """The ``(operator, version)`` pairs in one PEP 508 requirement string."""

    return _SPECIFIER.findall(requirement)


def dependency_checks(venv: Path) -> list[SelfCheck]:
    """Verify every installed distribution's own requirements hold inside ``venv``.

    ``version:<entry>`` compares the venv against the LOCK. This compares the venv
    against the MANAGERS: a loose pseudo-entry (``wheel:pyjutsu>=0.8``) can satisfy
    the lock while leaving a version no manager supports, and only the managers'
    own ``Requires-Dist`` metadata says so.

    Requirements carrying an environment marker or an extra are not evaluated —
    this module has no PEP 508 marker parser, and a wrong answer from the doctor is
    worse than no answer.
    """

    dists = installed_distributions(venv)
    if dists is None:
        return []  # can't inspect the venv — stay silent rather than cry wolf

    findings: list[str] = []
    for name, (version, requires) in sorted(dists.items()):
        for raw in requires:
            if ";" in raw:
                continue
            head = _requirement_name(raw)
            if not head:
                continue
            found = dists.get(head)
            if found is None:
                findings.append(f"{name} {version} requires {raw.strip()}, but {head} is not installed")
                continue
            violated = [
                f"{op}{want}" for op, want in _requirement_specifiers(raw) if _satisfies(found[0], op, want) is False
            ]
            if violated:
                findings.append(
                    f"{name} {version} requires {head}{','.join(violated)}, but {head} {found[0]} is installed"
                )
    if not findings:
        return [SelfCheck("deps:toolchain", "ok", f"{len(dists)} package(s) mutually compatible")]
    return [SelfCheck("deps:toolchain", "fail", f) for f in findings]


# ------------------------------------------------------------------ self-check


def _installed_check(manager: Manager) -> SelfCheck:
    """Validate the exact binary the nix tasks exec, not merely a PATH hit.

    The manager tasks run absolute paths (``"$toolchainBin"/gitman``), so a green
    ``PATH`` lookup can coexist with a task that dies on no-such-file. When both
    exist but differ, that shadowing IS the finding — report it.
    """

    heal = "run `repoman-sync --machine`" if manager.install == "toolchain" else "run `uv sync`"
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


def _is_machine_lock(repo_root: str, manifest: dict | None) -> bool:
    """Whether ``<repo_root>/repoman.lock`` is the MACHINE lock, not a consumer orphan.

    The repoman checkout itself keeps its machine manifest (the file `repoman-sync
    --machine` syncs from) at the repo root under the same filename a pre-project-12
    consumer lock would use. The recorded toolchain manifest (inside the venv) pins
    where it was synced from via its `[repoman]` source: a ``path:`` entry pointing at
    this repo root means the file IS the machine lock. Anything else — no recorded
    manifest, no `[repoman]` self entry, a fleet ``git+`` source, a different checkout —
    still warns as an orphan.
    """

    if manifest is None:
        return False
    entry = manifest.get("repoman")
    if not isinstance(entry, dict):
        return False
    source = entry.get("source")
    if not isinstance(source, str) or not source.startswith("path:"):
        return False
    try:
        return Path(source[len("path:") :]).resolve() == Path(repo_root).resolve()
    except OSError:
        return False


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

    # --- toolchain: the system-wide shared venv (project 12) -------------------
    venv = toolchain_venv()
    have_venv = (venv / "bin" / "repoman").exists()
    out.append(
        SelfCheck(
            "toolchain:venv",
            "ok" if have_venv else "fail",
            str(venv)
            if have_venv
            else f"missing or incomplete: {venv} — run `repoman-sync --machine` from the repoman checkout",
        )
    )

    data = None
    if have_venv:
        data, manifest_check = _load_toolchain_manifest(venv)
        out.append(manifest_check)
        if data is not None and "repoman" not in data:
            out.append(SelfCheck("toolchain:self", "warn", "no [repoman] self entry"))

    pyproject, pyproject_error = _load_pyproject(repo_root)
    if pyproject_error is not None:
        out.append(SelfCheck("pyproject", "fail", f"{repo_root}/pyproject.toml {pyproject_error}"))
    lock_keys = set((data or {}).get("managers", {}))

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
            continue  # no manifest to check against; toolchain:venv/lock already reported
        # tolerate native-dep pseudo-entries like "git-pyjutsu" (guide 1)
        has = any(k.split("-", 1)[0] == m.key for k in lock_keys)
        # Never read as "a per-repo repoman.lock file is missing": modern consumers
        # have none (project 12). Name the recorded toolchain manifest this row
        # actually checks — the venv's repoman-toolchain.toml.
        out.append(
            SelfCheck(
                f"lock:{m.key}",
                "ok" if has else "fail",
                ""
                if has
                else (
                    "selected but absent from the recorded toolchain manifest "
                    f"({venv / 'repoman-toolchain.toml'}) — re-run `repoman-sync --machine`"
                ),
            )
        )

    # Currency: the lock says what SHOULD be installed; check what IS. Without this,
    # a machine that never re-synced still reports fully green.
    if data is not None:
        out.extend(version_checks(venv, data, managers))

    # Coherence: the lock can be fully satisfied and the venv still unusable, because a
    # pseudo-entry's floor is not the manager's requirement. Ask the managers themselves.
    if have_venv:
        out.extend(dependency_checks(venv))

    repo_lock = Path(repo_root) / "repoman.lock"
    if repo_lock.exists() and not _is_machine_lock(repo_root, data):
        out.append(
            SelfCheck(
                "lock:orphan",
                "warn",
                "per-repo repoman.lock is obsolete — the toolchain is machine-level; delete this file",
            )
        )

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
