#!/usr/bin/env bash
# repoman-sync — generate the lifecycle router skill.
#
# The host profile puts the manager commands on PATH. This script never installs a
# package and reads no toolchain manifest. It runs `repoman install-skills`.
set -euo pipefail

case "${1:-}" in
  "") ;;
  -h|--help)
    sed -n '2,5p' "$0"
    exit 0
    ;;
  *)
    echo "repoman-sync: unknown argument: $1" >&2
    exit 2
    ;;
esac

if [ "$#" -gt 0 ]; then
  echo "repoman-sync: unexpected extra argument(s): $*" >&2
  exit 2
fi

root="${DEVENV_ROOT:-$PWD}"
if ! command -v repoman >/dev/null 2>&1; then
  echo "repoman-sync: repoman is not on PATH." >&2
  echo "repoman-sync: the host profile must install it, or this repo must declare it." >&2
  exit 2
fi

# A consumer repo must not keep a repoman.lock. The host profile replaced it.
# RepoMan itself is exempt. Its pyproject.toml names the repoman package.
if [ -f "$root/repoman.lock" ] \
   && ! grep -q '^[[:space:]]*name[[:space:]]*=[[:space:]]*"repoman"' "$root/pyproject.toml" 2>/dev/null; then
  echo "repoman-sync: $root/repoman.lock is obsolete in a consumer repo." >&2
  exit 2
fi

repoman install-skills
echo "repoman-sync: done (router skill)."
