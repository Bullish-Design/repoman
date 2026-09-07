# The committed devenv files must be PORTABLE: they may not name any one machine's
# working trees. devenv.yaml is committed in its FLEET shape (published tags); the
# machine-local urls live in the untracked devenv.local.yaml overlay, which devenv
# merges over devenv.yaml. Same rule as repoman.lock / repoman.local.lock.
#
# devenv rewrites devenv.lock in place, so a `devenv shell` taken WITH the overlay
# active re-locks the inputs at the local paths. These tests turn that silent leak
# into a loud failure: re-lock without the overlay before you commit.
#
#   mv devenv.local.yaml /tmp/ && devenv update && mv /tmp/devenv.local.yaml .
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# An absolute path under a user's home directory, in a url or on its own.
LOCAL_PATH = re.compile(r"(?:file://)?/(?:home|Users)/[A-Za-z0-9._-]+/")


def _offending_lines(path: Path) -> list[str]:
    return [line for line in path.read_text().splitlines() if LOCAL_PATH.search(line)]


def test_devenv_yaml_is_committed_in_the_fleet_shape():
    bad = _offending_lines(ROOT / "devenv.yaml")
    assert not bad, "devenv.yaml names a local checkout - move it to devenv.local.yaml:\n" + "\n".join(bad)


def test_devenv_lock_is_portable_all_the_way_down():
    # NO transitive exemption. It was scoped to declared inputs while vendomat v0.3.2
    # published a flake.lock pinning pyjutsu at file:///home/... — a leak that arrived
    # through the fleet url and could not be fixed from here. Vendomat v0.3.3 pins every
    # input to a published tag, so the whole chain is portable and the exemption is gone.
    #
    # This matters more than it looks: a consumer inherits every node, not just the ones
    # this repo names. Re-scoping the check to declared inputs would hide the next leak.
    lock = json.loads((ROOT / "devenv.lock").read_text())
    bad = {}
    for name, node in lock["nodes"].items():
        locked = node.get("locked", {})
        target = str(locked.get("url") or locked.get("path") or "")
        if LOCAL_PATH.search(target):
            bad[name] = target
    assert not bad, (
        "devenv.lock names local checkouts: "
        f"{bad}\n"
        "If these are inputs this repo declares, it was re-locked with the overlay active — "
        "re-lock without it: mv devenv.local.yaml /tmp/ && devenv update && mv /tmp/devenv.local.yaml .\n"
        "If they are transitive, the leak is in that input's own committed lock; fix it there."
    )


def test_the_local_overlay_is_never_tracked():
    # A tracked overlay would defeat the whole split.
    tracked = (ROOT / ".gitignore").read_text()
    assert "devenv.local.yaml" in tracked


def test_the_self_input_is_a_path_not_a_git_url():
    # A git input copies TRACKED files only, so a brand-new modules/*.nix would be
    # invisible to nix until `git add`. A path input reads the directory literally.
    text = (ROOT / "devenv.yaml").read_text()
    assert 'url: "path:./modules"' in text
