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

# Resolve install targets from the lock (tomllib ships with Python 3.11+).
mapfile -t targets < <(
  REPOMAN_LOCK="$lock" REPOMAN_MANAGERS="$managers" python3 - <<'PY'
import os, tomllib

with open(os.environ["REPOMAN_LOCK"], "rb") as fh:
    data = tomllib.load(fh)

managers = os.environ.get("REPOMAN_MANAGERS", "").split()


def target(entry: dict) -> str:
    source = entry["source"]
    if source.startswith("path:"):
        # Local checkouts install editable so code edits are picked up live.
        return f"--editable={source[len('path:'):]}"
    return source  # git+https://...@ref — uv resolves the name itself


out = []
if "repoman" in data:
    out.append(target(data["repoman"]))

# Install each selected manager plus any native-dep pseudo-entries keyed off it
# (e.g. "git-pyjutsu" for the "git" manager — see guide 01). A pseudo-entry's base
# is the part before the first "-"; uv resolves a manager + its native deps together
# in one install so editable sources like pyjutsu satisfy the manager's requirement.
selected = set(managers)
for key, entry in data.get("managers", {}).items():
    base = key.split("-", 1)[0]
    if base in selected:
        out.append(target(entry))
print("\n".join(out))
PY
)

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
