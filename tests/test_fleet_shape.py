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


def test_devenv_lock_pins_our_own_inputs_in_the_fleet_shape():
    # Scoped to the inputs THIS repo declares. Transitive nodes are exempt: vendomat
    # v0.3.2 publishes a flake.lock that pins pyjutsu at file:///home/... , so its
    # leak arrives through the fleet url and repoman cannot fix it from here.
    lock = json.loads((ROOT / "devenv.lock").read_text())
    # No yaml dependency: input names are the only 2-space keys under `inputs:`.
    body = (ROOT / "devenv.yaml").read_text().split("inputs:", 1)[1].split("\nimports:", 1)[0]
    declared = set(re.findall(r"^  ([A-Za-z0-9._-]+):", body, re.M))
    bad = {}
    for name in sorted(declared & set(lock["nodes"])):
        locked = lock["nodes"][name].get("locked", {})
        target = str(locked.get("url") or locked.get("path") or "")
        if LOCAL_PATH.search(target):
            bad[name] = target
    assert not bad, (
        "devenv.lock was re-locked with the local overlay active: "
        f"{bad}\n"
        "Re-lock without it: mv devenv.local.yaml /tmp/ && devenv update && mv /tmp/devenv.local.yaml ."
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
