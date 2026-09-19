#!/usr/bin/env bash
# repoman-sync — verify Vendomat's toolchain closure and generate the router.
#
# The manager commands are supplied by Vendomat. This script never installs a
# package and has no machine or virtual-environment mode.
set -euo pipefail

case "${1:-}" in
  "") ;;
  -h|--help)
    sed -n '2,7p' "$0"
    exit 0
    ;;
  --machine)
    echo "repoman-sync: --machine is retired; Vendomat owns the toolchain closure." >&2
    exit 2
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
toolchain_bin="${REPOMAN_TOOLCHAIN_BIN:-}"
if [ -z "$toolchain_bin" ]; then
  echo "repoman-sync: REPOMAN_TOOLCHAIN_BIN is unset." >&2
  echo "repoman-sync: import Vendomat's consumer module with vendor.toolchain.enable = true." >&2
  exit 2
fi
if [ ! -x "$toolchain_bin/repoman" ]; then
  echo "repoman-sync: shared command closure has no repoman: $toolchain_bin" >&2
  echo "repoman-sync: rebuild the Vendomat toolchain closure and check its consumer module." >&2
  exit 2
fi

# RepoMan itself keeps the machine lock that describes its development inputs.
# Every consumer must remove that obsolete per-repo provider declaration.
if [ -f "$root/repoman.lock" ] \
   && ! grep -q '^[[:space:]]*name[[:space:]]*=[[:space:]]*"repoman"' "$root/pyproject.toml" 2>/dev/null; then
  echo "repoman-sync: $root/repoman.lock is obsolete in a consumer repo." >&2
  echo "repoman-sync: Vendomat's flake.lock is authoritative for the toolchain." >&2
  exit 2
fi

manifest="${REPOMAN_TOOLCHAIN_MANIFEST:-$toolchain_bin/../share/vendomat/toolchain.json}"
echo "repoman-sync: shared command closure -> $toolchain_bin"
if [ -r "$manifest" ]; then
  python3 - "$manifest" <<'MANIFEST'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)
print(f"repoman-sync:   roster {data['roster']}, python {data['python']}")
for name, tool in sorted(data["tools"].items()):
    print(f"repoman-sync:   {name} {tool['version']} -> {tool['store']}")
MANIFEST
else
  echo "repoman-sync: warning: no provenance manifest at $manifest" >&2
fi

"$toolchain_bin/repoman" install-skills
echo "repoman-sync: done (router skill; toolchain is a pinned Vendomat closure)."
