#!/usr/bin/env bash
# repoman-sync — one script, two modes (project 12).
#
#   repoman-sync --machine    Create/sync the SYSTEM-WIDE toolchain venv from the machine
#                             repoman.lock at the repoman checkout root. Installs EVERY entry
#                             in the lock in ONE `uv pip install --upgrade`, rebuilds every
#                             editable manager, verifies the result is coherent, then records
#                             the lock it synced from inside the venv. Run once per machine,
#                             and again on every toolchain bump.
#
#   repoman-sync              Consumer mode. Installs NO packages: the consumer venv belongs to
#                             `uv sync` alone. Verifies the shared toolchain is present, warns
#                             about orphan per-repo locks, then installs agent skills + devman docs.
set -euo pipefail

mode=consumer
case "${1:-}" in
  --machine)  mode=machine; shift ;;
  -h|--help)  sed -n '2,13p' "$0"; exit 0 ;;
  "")         ;;
  *)          echo "repoman-sync: unknown argument: $1" >&2; exit 2 ;;
esac

# Never ignore trailing arguments: `repoman-sync --machine --dry-run` silently doing a
# real sync is exactly the surprise this guard exists to prevent.
if [ "$#" -gt 0 ]; then
  echo "repoman-sync: unexpected extra argument(s): $*" >&2
  exit 2
fi

# D1: resolved at runtime, never at nix eval.
toolchain_venv="${REPOMAN_TOOLCHAIN_VENV:-${XDG_DATA_HOME:-$HOME/.local/share}/repoman/venv}"
# D7: what the shared venv was last synced from — the consumer doctor reads this.
toolchain_manifest="$toolchain_venv/repoman-toolchain.toml"

bootstrap_hint() {
  echo "repoman-sync: bootstrap the shared toolchain once per machine:" >&2
  echo "    cd <your repoman checkout> && devenv shell -- repoman-sync --machine" >&2
}

# ---------------------------------------------------------------- consumer mode
if [ "$mode" = consumer ]; then
  root="${DEVENV_ROOT:-$PWD}"

  # D6: consumer mode's remaining job IS the shared `repoman` binary — fail, don't limp.
  if [ ! -x "$toolchain_venv/bin/repoman" ]; then
    echo "repoman-sync: shared toolchain venv missing or incomplete: $toolchain_venv" >&2
    bootstrap_hint
    exit 2
  fi
  echo "repoman-sync: shared toolchain → $toolchain_venv"

  # Migration aid (CONCEPT §9.7): per-repo locks are orphans now — UNLESS this IS the
  # machine lock the toolchain was synced from (the repoman checkout keeps its own
  # machine manifest at the repo root). The venv manifest records its origin on the
  # first line (`# synced from <lock>`); same fingerprint as checks.py's lock:orphan.
  if [ -f "$root/repoman.lock" ] \
     && ! grep -qF "# synced from $root/repoman.lock" "$toolchain_manifest" 2>/dev/null; then
    echo "repoman-sync: warning: $root/repoman.lock is an ORPHAN manifest — the toolchain is" >&2
    echo "  machine-level now (see repoman CONCEPT.md §6). Delete it; declare testee in" >&2
    echo "  pyproject.toml under [dependency-groups] dev instead." >&2
  fi

  # Run the binary we just verified, not whatever `repoman` PATH happens to resolve:
  # a consumer venv holding a stale pre-migration repoman would otherwise shadow it,
  # and we'd have checked one copy while running another.
  "$toolchain_venv/bin/repoman" install-skills
  echo "repoman-sync: done (skills + docs; toolchain is machine-level)."
  exit 0
fi

# ---------------------------------------------------------------- machine mode
root="${REPOMAN_ROOT:-${DEVENV_ROOT:-$PWD}}"
# WS-3 (project-12 follow-up): REPOMAN_LOCK overrides the lock path ENTIRELY — a CI
# runner can point at a fleet-shaped lock (git+https@ref sources) without editing
# the checkout. Pure env-var override; unset = current behaviour (the machine lock
# at the repoman checkout root).
lock="${REPOMAN_LOCK:-$root/repoman.lock}"

if [ ! -f "$lock" ]; then
  echo "repoman-sync --machine: no machine repoman.lock at $lock" >&2
  echo "repoman-sync --machine: run this from the repoman checkout, or set REPOMAN_ROOT." >&2
  exit 2
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "repoman-sync --machine: \`uv\` is not on PATH — run this from inside \`devenv shell\`." >&2
  exit 2
fi

# Resolve install targets from the lock (tomllib ships with Python 3.11+). The resolver
# writes NUL-separated targets to a temp file rather than to a command substitution:
# `$(…)` strips NUL bytes, and a newline-delimited protocol lets a stray newline inside
# a lock `source` inject an extra argument into the `uv pip install` argv below.
resolved_file="$(mktemp)"
trap 'rm -f "$resolved_file"' EXIT

REPOMAN_LOCK="$lock" python3 - > "$resolved_file" <<'PY' || exit $?
import os, sys, tomllib

path = os.environ["REPOMAN_LOCK"]


def die(message: str) -> None:
    sys.stderr.write(f"repoman-sync --machine: {path}: {message}\n")
    raise SystemExit(2)


try:
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
except tomllib.TOMLDecodeError as exc:
    die(f"is not valid TOML — {exc}")
except OSError as exc:
    die(f"cannot be read — {exc.strerror or exc}")

# Open source-kind vocabulary (DESIGN §4.1): prefix -> handler. A new kind ("bin:",
# "closure:") is one more entry here, not a new branch — vendomat's `wheel:` is the first.
SOURCE_HANDLERS = {
    "path:": lambda rest: f"--editable={rest}",
    "wheel:": lambda rest: rest,
}


def target(source: str) -> str:
    for prefix, handler in SOURCE_HANDLERS.items():
        if source.startswith(prefix):
            return handler(source[len(prefix):])
    return source  # git+https://...@ref — uv resolves the name itself


def entry_source(label: str, entry: object) -> str:
    """Validate one lock entry and return its source, or die with a usable message."""
    if not isinstance(entry, dict):
        die(f"[{label}] must be a table (got {type(entry).__name__}); expected a section "
            'like [managers.git] with `package` and `source` keys')
    source = entry.get("source")
    if source is None:
        die(f"[{label}] has no `source` key; expected e.g. source = \"path:/abs/path\"")
    if not isinstance(source, str) or not source.strip():
        die(f"[{label}] `source` must be a non-empty string, got {source!r}")
    return source


def entry_package(entry: object) -> str | None:
    """The lock entry's distribution name, or None when it is absent/malformed."""
    if not isinstance(entry, dict):
        return None
    package = entry.get("package")
    if isinstance(package, str) and package.strip():
        return package.strip()
    return None


# Machine mode installs the whole lock: the shared venv holds every pure-CLI manager
# regardless of any single repo's roster (CONCEPT §5.1).
entries: list[tuple[str, str, str | None]] = []
if "repoman" in data:
    entries.append(("repoman", entry_source("repoman", data["repoman"]), entry_package(data["repoman"])))

managers = data.get("managers", {})
if not isinstance(managers, dict):
    die("[managers] must be a table of tables")
for key, entry in managers.items():
    entries.append((f"managers.{key}", entry_source(f"managers.{key}", entry), entry_package(entry)))

# Guard (issue #1): a wheel: source only resolves because vendomat's module exported
# UV_FIND_LINKS. No wheelhouse → uv silently hits PyPI (no personal pyjutsu there) and
# fails confusingly. Fail early with a pointer instead.
wheel_sources = [s for _label, s, _pkg in entries if s.startswith("wheel:")]
if wheel_sources and not os.environ.get("UV_FIND_LINKS"):
    sys.stderr.write(
        "repoman-sync: wheel: source(s) selected but UV_FIND_LINKS is unset:\n"
        + "".join(f"    {s}\n" for s in wheel_sources)
        + "\nA wheel: source installs a prebuilt wheel from vendomat's wheelhouse.\n"
        "Bootstrap from a context that exports it — repoman's own devenv declares the\n"
        "vendomat input and sets `vendor.enable = true` (see repoman devenv.nix), or set\n"
        "`repoman.nativeBuild = true` and build pyjutsu from source.\n"
    )
    sys.exit(2)

# A `path:` entry is installed --editable, so its CODE tracks the checkout while its
# recorded METADATA (version + Requires-Dist) is a snapshot of the last build. Once the
# two disagree, uv resolves the old requirements and the sync reports success against a
# runtime that no manager actually supports — the exact failure this rebuild prevents.
# `--reinstall-package` forces a fresh build, so every sync resolves the CURRENT
# requirements of every editable manager.
rebuild = [
    package for _label, source, package in entries
    if source.startswith("path:") and package
]

for package in sorted(set(rebuild)):
    if "\n" in package or "\0" in package:
        die(f"`package` {package!r} contains an embedded newline or NUL")
    sys.stdout.write("F--reinstall-package=" + package + "\0")

for label, source, _package in entries:
    resolved = target(source)
    if "\n" in resolved or "\0" in resolved:
        die(f"[{label}] `source` contains an embedded newline or NUL — refusing to build an "
            "install command from it")
    sys.stdout.write("T" + resolved + "\0")
PY

# The resolver tags each NUL-separated record: `T` = install target (listed in the
# report), `F` = an extra uv flag (not a package, so it stays out of the count).
targets=()
flags=()
while IFS= read -r -d '' record; do
  case "$record" in
    T?*) targets+=("${record#T}") ;;
    F?*) flags+=("${record#F}") ;;
  esac
done < "$resolved_file"

if [ "${#targets[@]}" -eq 0 ]; then
  echo "repoman-sync --machine: nothing to install (empty lock: $lock)" >&2
  exit 2
fi

py="${REPOMAN_TOOLCHAIN_PYTHON:-3.13}"   # CONCEPT §4.1: gitman >=3.13, pyjutsu cp313-abi3
if [ ! -x "$toolchain_venv/bin/python" ]; then
  echo "repoman-sync --machine: creating shared toolchain venv (python $py) at $toolchain_venv"
  mkdir -p "$(dirname "$toolchain_venv")"
  uv venv --python "$py" "$toolchain_venv"
fi

echo "repoman-sync --machine: installing ${#targets[@]} package(s) into $toolchain_venv:"
printf '  - %s\n' "${targets[@]}"
# --python targets the shared venv explicitly: never inherit an ambient VIRTUAL_ENV
# (the bootstrap runs from inside repoman's OWN devenv venv).
# --upgrade is load-bearing: without it a range pin like `wheel:pyjutsu>=0.8` is already
# "satisfied" by whatever is installed, so re-running after a toolchain bump is a silent
# no-op and `repoman doctor` keeps reporting green against a stale venv.
# uv resolves every target in ONE operation, so a manager's requirement and a loose
# pseudo-entry meet as a single constraint set and the stricter one wins.
if ! uv pip install --upgrade --python "$toolchain_venv/bin/python" \
     ${flags[@]+"${flags[@]}"} "${targets[@]}"; then
  echo "repoman-sync --machine: uv could not install a coherent toolchain from $lock" >&2
  echo "  The constraint set above has no solution. Fix the conflicting requirement in the" >&2
  echo "  manager that declares it, or widen the lock entry, then re-run." >&2
  exit 2   # infra/config, per the exit-code contract — not a domain decision
fi

# Verify the RESULT, not the command. `uv pip install` succeeding proves uv resolved what
# it was asked for; it does not prove the venv now satisfies every manager's real
# requirements (stale editable metadata hides a constraint from the resolver entirely).
# Refuse to record a manifest for an incoherent toolchain.
if ! REPOMAN_LOCK="$lock" REPOMAN_VERIFY_VENV="$toolchain_venv" python3 - <<'PY'; then
import os, re, sys, tomllib
from importlib.metadata import Distribution, DistributionFinder
from pathlib import Path

lock = Path(os.environ["REPOMAN_LOCK"])
venv = Path(os.environ["REPOMAN_VERIFY_VENV"])


def normalize(name: str) -> str:
    """PEP 503 name normalisation."""
    return re.sub(r"[-_.]+", "-", name).lower()


def release(version: str):
    """Numeric release segments, or None for anything with pre/post/dev parts.

    Refusing to guess on `1.0rc1` keeps the check honest: the caller treats None as
    "not evaluated" rather than inventing an ordering.
    """
    out = []
    for part in version.split("+", 1)[0].split("."):
        if not part.isdigit():
            return None
        out.append(int(part))
    return tuple(out) if out else None


def satisfies(installed: str, operator: str, wanted: str):
    """Whether `installed <operator> wanted` holds; None if not evaluable."""
    left, right = release(installed), release(wanted)
    if left is None or right is None:
        return None
    width = max(len(left), len(right))
    left += (0,) * (width - len(left))
    right += (0,) * (width - len(right))
    return {
        "==": left == right, "!=": left != right, ">=": left >= right,
        "<=": left <= right, ">": left > right, "<": left < right,
    }.get(operator)


def site_packages(root: Path):
    try:
        for path in sorted((root / "lib").glob("python*/site-packages")):
            if path.is_dir():
                return path
    except OSError:
        pass
    return None


site = site_packages(venv)
if site is None:
    sys.stderr.write(
        f"repoman-sync --machine: cannot inspect {venv} — dependency verification skipped.\n"
    )
    raise SystemExit(0)

installed: dict[str, tuple[str, list[str]]] = {}
for dist in Distribution.discover(context=DistributionFinder.Context(path=[str(site)])):
    try:
        name, version = dist.metadata["Name"], dist.version
        requires = dist.metadata.get_all("Requires-Dist") or []
    except (OSError, KeyError, ValueError):
        continue
    if name and version:
        installed[normalize(name)] = (version, [str(r) for r in requires])

findings: list[str] = []

# --- 1. editable freshness -------------------------------------------------------
# A `path:` manager's installed metadata must match the version its checkout declares.
# When it does not, every constraint below was read from a stale snapshot.
def lock_entries(data: dict):
    if isinstance(data.get("repoman"), dict):
        yield "repoman", data["repoman"]
    managers = data.get("managers")
    if isinstance(managers, dict):
        for key, entry in managers.items():
            if isinstance(entry, dict):
                yield f"managers.{key}", entry


try:
    with open(lock, "rb") as fh:
        lock_data = tomllib.load(fh)
except (OSError, tomllib.TOMLDecodeError):
    lock_data = {}

for label, entry in lock_entries(lock_data):
    source, package = entry.get("source"), entry.get("package")
    if not isinstance(source, str) or not isinstance(package, str):
        continue
    if not source.startswith("path:"):
        continue
    checkout = Path(source[len("path:"):])
    try:
        with open(checkout / "pyproject.toml", "rb") as fh:
            declared = (tomllib.load(fh).get("project") or {}).get("version")
    except (OSError, tomllib.TOMLDecodeError):
        continue   # unreadable checkout is the installer's problem, not the verifier's
    if not isinstance(declared, str):
        continue   # dynamic or absent version — nothing to compare against
    found = installed.get(normalize(package))
    if found is None:
        findings.append(f"[{label}] {package} is in the lock but is not installed in {venv}")
        continue
    if release(found[0]) != release(declared) and found[0] != declared:
        findings.append(
            f"[{label}] {package} {found[0]} is installed, but the checkout at {checkout} "
            f"declares {declared} — the recorded metadata is stale"
        )

# --- 2. constraint consistency ---------------------------------------------------
# Every installed distribution's own requirements must hold in the installed set. This
# is what stops a loose pseudo-entry (`wheel:pyjutsu>=0.8`) from leaving an old version
# behind when a manager needs a newer one.
SPECIFIER = re.compile(r"(==|!=|>=|<=|>|<)\s*([0-9][^,\s\]]*)")

for name, (version, requires) in sorted(installed.items()):
    for raw in requires:
        if ";" in raw:
            continue   # environment marker or extra — not evaluated (no PEP 508 parser here)
        head = re.split(r"[\s\[<>=!~;@()]", raw.strip(), maxsplit=1)[0]
        if not head:
            continue
        found = installed.get(normalize(head))
        if found is None:
            findings.append(f"{name} {version} requires {raw.strip()}, but {head} is not installed")
            continue
        violated = [
            f"{op}{want}" for op, want in SPECIFIER.findall(raw)
            if satisfies(found[0], op, want) is False
        ]
        if violated:
            findings.append(
                f"{name} {version} requires {head}{','.join(violated)}, "
                f"but {head} {found[0]} is installed"
            )

if findings:
    sys.stderr.write("repoman-sync --machine: the toolchain venv is INCOHERENT after install:\n")
    for finding in findings:
        sys.stderr.write(f"    {finding}\n")
    sys.stderr.write(
        f"\nNo manifest was recorded for {venv}.\n"
        "Align the lock with what the managers actually require, then re-run\n"
        "`repoman-sync --machine`.\n"
    )
    raise SystemExit(2)
PY
  exit 2
fi

# D7: record what this venv was synced from, so a consumer's `repoman doctor` can validate
# the toolchain without knowing where the repoman checkout lives. Written atomically —
# a half-written manifest reads as "unparseable" forever otherwise.
{ printf '# synced from %s\n' "$lock"; cat "$lock"; } > "$toolchain_manifest.tmp"
mv -f "$toolchain_manifest.tmp" "$toolchain_manifest"

echo "repoman-sync --machine: done → $toolchain_venv/bin"
