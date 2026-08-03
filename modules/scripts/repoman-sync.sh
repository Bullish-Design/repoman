#!/usr/bin/env bash
# repoman-sync — one script, two modes (project 12).
#
#   repoman-sync --machine    Create/sync the SYSTEM-WIDE toolchain venv from the machine
#                             repoman.lock at the repoman checkout root. Installs EVERY entry
#                             in the lock (add-only `uv pip install`), then records the lock it
#                             synced from inside the venv. Run once per machine, and again on
#                             every toolchain bump.
#
#   repoman-sync              Consumer mode. Installs NO packages: the consumer venv belongs to
#                             `uv sync` alone. Verifies the shared toolchain is present, warns
#                             about orphan per-repo locks, then installs agent skills + devman docs.
set -euo pipefail

mode=consumer
case "${1:-}" in
  --machine)  mode=machine ;;
  -h|--help)  sed -n '2,15p' "$0"; exit 0 ;;
  "")         ;;
  *)          echo "repoman-sync: unknown argument: $1" >&2; exit 2 ;;
esac

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

  # Migration aid (CONCEPT §9.7): per-repo locks are orphans now.
  if [ -f "$root/repoman.lock" ]; then
    echo "repoman-sync: warning: $root/repoman.lock is an ORPHAN manifest — the toolchain is" >&2
    echo "  machine-level now (see repoman CONCEPT.md §6). Delete it; declare testee in" >&2
    echo "  pyproject.toml under [dependency-groups] dev instead." >&2
  fi

  repoman install-skills
  echo "repoman-sync: done (skills + docs; toolchain is machine-level)."
  exit 0
fi

# ---------------------------------------------------------------- machine mode
root="${REPOMAN_ROOT:-${DEVENV_ROOT:-$PWD}}"
lock="$root/repoman.lock"

if [ ! -f "$lock" ]; then
  echo "repoman-sync --machine: no machine repoman.lock at $lock" >&2
  echo "repoman-sync --machine: run this from the repoman checkout, or set REPOMAN_ROOT." >&2
  exit 2
fi

# Resolve install targets from the lock (tomllib ships with Python 3.11+). Command substitution
# (not process substitution) so the resolver's exit code propagates: the wheel:/UV_FIND_LINKS
# guard below must abort the whole sync, which `< <(…)` would have swallowed.
resolved="$(
  REPOMAN_LOCK="$lock" REPOMAN_SYNC_ALL=1 python3 - <<'PY'
import os, sys, tomllib

with open(os.environ["REPOMAN_LOCK"], "rb") as fh:
    data = tomllib.load(fh)

managers = os.environ.get("REPOMAN_MANAGERS", "").split()
# Machine mode installs the whole lock: the shared venv holds every pure-CLI manager
# regardless of any single repo's roster (CONCEPT §5.1).
select_all = os.environ.get("REPOMAN_SYNC_ALL") == "1"

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


entries = []
if "repoman" in data:
    entries.append(data["repoman"])
selected = set(managers)
for key, entry in data.get("managers", {}).items():
    base = key.split("-", 1)[0]          # native-dep pseudo-entry: "git-pyjutsu" -> "git"
    if select_all or base in selected:
        entries.append(entry)

# Guard (issue #1): a wheel: source only resolves because vendomat's module exported
# UV_FIND_LINKS. No wheelhouse → uv silently hits PyPI (no personal pyjutsu there) and
# fails confusingly. Fail early with a pointer instead.
wheel_sources = [e["source"] for e in entries if e["source"].startswith("wheel:")]
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

print("\n".join(target(e["source"]) for e in entries))
PY
)" || exit $?

# Drop the lone empty line a zero-target resolution yields, so the count check below holds.
targets=()
while IFS= read -r line; do
  [ -n "$line" ] && targets+=("$line")
done <<< "$resolved"

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
uv pip install --python "$toolchain_venv/bin/python" "${targets[@]}"

# D7: record what this venv was synced from, so a consumer's `repoman doctor` can validate
# the toolchain without knowing where the repoman checkout lives.
{ printf '# synced from %s\n' "$lock"; cat "$lock"; } > "$toolchain_manifest"

echo "repoman-sync --machine: done → $toolchain_venv/bin"
