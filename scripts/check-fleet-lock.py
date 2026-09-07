#!/usr/bin/env python3
"""Refuse to publish a devenv.lock that names one machine's working trees.

This runs as a pyjutsu `pre-push` hook, NOT as a unit test. The distinction is
deliberate. `devenv shell` rewrites devenv.lock in place, so a shell taken with
devenv.local.yaml active re-locks every overlaid input at its local path. That is
normal and harmless while you work — the overlay exists so an edit in a sibling
checkout takes effect on the next shell. It only becomes a defect when it leaves
this machine, because `file:///home/<user>/...` exists on exactly one of them.

A unit test put the gate in the wrong place: it turned red from ordinary work and
told you to re-lock before you had anything to publish. The push is the boundary
that matters, so the check lives there. Run `relock` to fix a finding.

Exit 0 = clean, 1 = a local path would reach the remote, 2 = cannot tell.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "devenv.lock"

# An absolute path under a user's home directory, in a url or on its own.
LOCAL_PATH = re.compile(r"(?:file://)?/(?:home|Users)/[A-Za-z0-9._-]+/")


def main() -> int:
    try:
        nodes = json.loads(LOCK.read_text())["nodes"]
    except OSError as exc:
        print(f"check-fleet-lock: cannot read {LOCK}: {exc}", file=sys.stderr)
        return 2
    except (json.JSONDecodeError, KeyError) as exc:
        print(f"check-fleet-lock: {LOCK} is not a devenv lock: {exc}", file=sys.stderr)
        return 2

    # No transitive exemption: a consumer inherits every node, not only the inputs
    # this repo declares, so a leak anywhere in the chain travels just as far.
    bad = {}
    for name, node in nodes.items():
        locked = node.get("locked", {})
        target = str(locked.get("url") or locked.get("path") or "")
        if LOCAL_PATH.search(target):
            bad[name] = target

    if not bad:
        return 0

    print("check-fleet-lock: devenv.lock names local checkouts, so the push is blocked:", file=sys.stderr)
    for name, target in sorted(bad.items()):
        print(f"  {name}: {target}", file=sys.stderr)
    print("", file=sys.stderr)
    print("These are the machine-local urls from devenv.local.yaml. `devenv shell` wrote", file=sys.stderr)
    print("them into the lock; committing them ships a path no other machine has.", file=sys.stderr)
    print("", file=sys.stderr)
    print("  relock          re-lock from the published tags, then commit devenv.lock", file=sys.stderr)
    print("", file=sys.stderr)
    print("If an input above is NOT in devenv.local.yaml, the leak is in that input's own", file=sys.stderr)
    print("committed lock; fix it in that repo and take a release.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
