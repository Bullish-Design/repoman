#!/usr/bin/env bash
# repoman-sync — install the pinned toolchain into the devenv venv.
#
# Reads $DEVENV_ROOT/repoman.lock, resolves the [repoman] self entry plus every
# manager listed in $REPOMAN_MANAGERS, and `uv pip install`s them into the active
# devenv venv. Idempotent: re-running just re-resolves the same pins.
set -euo pipefail

root="${DEVENV_ROOT:-$PWD}"
lock="$root/repoman.lock"
managers="${REPOMAN_MANAGERS:-}"

if [ ! -f "$lock" ]; then
  echo "repoman-sync: no repoman.lock found at $lock" >&2
  echo "repoman-sync: create one (see CONCEPT.md) to pin this repo's toolchain." >&2
  exit 2
fi

# Resolve install targets from the lock (tomllib ships with Python 3.11+). Uses a command
# substitution (not process substitution) so the resolver's exit code propagates: the
# wheel:/UV_FIND_LINKS guard below aborts the whole sync, which `< <(…)` would have swallowed.
resolved="$(
  REPOMAN_LOCK="$lock" REPOMAN_MANAGERS="$managers" python3 - <<'PY'
import os, sys, tomllib

with open(os.environ["REPOMAN_LOCK"], "rb") as fh:
    data = tomllib.load(fh)

managers = os.environ.get("REPOMAN_MANAGERS", "").split()

# Open source-kind vocabulary (DESIGN §4.1): prefix -> handler. A new kind ("bin:",
# "closure:") is one more entry here, not a new branch — vendomat's `wheel:` is the first.
SOURCE_HANDLERS = {
    # Local checkout: install editable so code edits are picked up live.
    "path:": lambda rest: f"--editable={rest}",
    # Vendored wheel: a bare requirement (e.g. "pyjutsu>=0.8") that uv resolves from
    # vendomat's UV_FIND_LINKS wheelhouse — a prebuilt wheel, never compiled from source.
    "wheel:": lambda rest: rest,
}


def target(source: str) -> str:
    for prefix, handler in SOURCE_HANDLERS.items():
        if source.startswith(prefix):
            return handler(source[len(prefix):])
    return source  # git+https://...@ref — uv resolves the name itself


# Install each selected manager plus any native-dep pseudo-entries keyed off it
# (e.g. "git-pyjutsu" for the "git" manager — see guide 01). A pseudo-entry's base
# is the part before the first "-"; uv resolves a manager + its native deps together
# in one install so sources like pyjutsu satisfy the manager's requirement.
entries = []
if "repoman" in data:
    entries.append(data["repoman"])
selected = set(managers)
for key, entry in data.get("managers", {}).items():
    base = key.split("-", 1)[0]
    if base in selected:
        entries.append(entry)

# Guard (issue #1): a wheel: source only resolves because vendomat's module exported
# UV_FIND_LINKS. Selected but no wheelhouse → uv would silently hit PyPI (no personal
# pyjutsu there) and fail confusingly. Fail early with a pointer instead.
wheel_sources = [e["source"] for e in entries if e["source"].startswith("wheel:")]
if wheel_sources and not os.environ.get("UV_FIND_LINKS"):
    sys.stderr.write(
        "repoman-sync: wheel: source(s) selected but UV_FIND_LINKS is unset:\n"
        + "".join(f"    {s}\n" for s in wheel_sources)
        + "\nA wheel: source installs a prebuilt wheel from vendomat's wheelhouse.\n"
        "Import and enable vendomat's devenv module so it exports UV_FIND_LINKS:\n"
        "  devenv.yaml:  inputs.vendomat: { url: path:/…/vendomat }  +  imports: [ vendomat/modules ]\n"
        "  devenv.nix:   vendor.enable = true;\n"
    )
    sys.exit(2)

print("\n".join(target(e["source"]) for e in entries))
PY
)" || exit $?

# Drop the lone empty line a zero-target resolution yields, so the count check below holds.
targets=()
while IFS= read -r line; do
  [ -n "$line" ] && targets+=("$line")
done <<< "$resolved"

if [ "${#targets[@]}" -eq 0 ]; then
  echo "repoman-sync: nothing to install (managers: '${managers:-none}')"
  exit 0
fi

echo "repoman-sync: installing ${#targets[@]} package(s) for managers [${managers:-none}]:"
printf '  - %s\n' "${targets[@]}"
uv pip install "${targets[@]}"

# Generate the RepoMan entrypoint (router) skill from the enabled roster.
repoman install-skills

echo "repoman-sync: done."
