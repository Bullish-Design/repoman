# The committed devenv files must be PORTABLE: they may not name any one machine's
# working trees. devenv.yaml is committed in its FLEET shape (published tags); the
# machine-local urls live in the untracked devenv.local.yaml overlay, which devenv
# merges over devenv.yaml.
#
# devenv.lock is NOT checked here. devenv rewrites it on every shell entry, so a shell
# taken with the overlay active re-locks the overlaid inputs at their local paths —
# ordinary work would turn this suite red and tell you to re-lock before you had
# anything to publish. That gate belongs at the boundary that matters, so it is a
# step of the `gate` script (devenv.nix -> scripts/check-fleet-lock.py) and
# `relock` is the fix. What IS checked here is that the gate stays wired.
#
# devenv.yaml and .gitignore are hand-edited and never rewritten, so they stay tests.
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


def test_the_local_overlay_is_never_tracked():
    # A tracked overlay would defeat the whole split.
    tracked = (ROOT / ".gitignore").read_text()
    assert "devenv.local.yaml" in tracked


def test_the_self_input_is_a_path_not_a_git_url():
    # A git input copies TRACKED files only, so a brand-new modules/*.nix would be
    # invisible to nix until `git add`. A path input reads the directory literally.
    text = (ROOT / "devenv.yaml").read_text()
    assert 'url: "path:./modules"' in text


def test_the_lock_gate_is_wired_into_the_gate_script():
    # Native `jj git push` runs no git hook, and gitman 0.12 gates nothing. The `gate`
    # script is the one place that covers push and release, so this checks the wiring
    # rather than re-implementing the check. The author runs `gate` before pushing.
    nix = (ROOT / "devenv.nix").read_text()
    assert "scripts.gate = {" in nix
    assert "scripts/check-fleet-lock.py" in nix
    assert "testee verify --mode ci" in nix
    assert (ROOT / "scripts" / "check-fleet-lock.py").exists()


def test_no_gitman_v1_gate_files_remain():
    # gitman 0.12 reads neither file; a stale copy would claim a gate that never runs.
    assert not (ROOT / "gitman.toml").exists()
    assert not (ROOT / ".pyjutsu-hooks.toml").exists()


def test_the_relock_script_exists_and_is_what_the_gate_names():
    # A gate that names a fix the repo does not ship is worse than no gate.
    nix = (ROOT / "devenv.nix").read_text()
    assert "scripts.relock = {" in nix
    assert "relock" in (ROOT / "scripts" / "check-fleet-lock.py").read_text()


def test_the_relock_stash_is_never_tracked():
    # `relock` parks the overlay in the repo so an interrupted run leaves it findable.
    # Tracked, it would be committed and defeat the split it exists to protect.
    assert ".devenv.local.yaml.relock" in (ROOT / ".gitignore").read_text()
