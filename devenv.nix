{ pkgs, config, ... }:
{
  env = {
    DEVENV_PROJECT = "repoman";
  };

  packages = with pkgs; [
    git
    curl
    jq
  ];

  # Machine bootstrap (project 12): export UV_FIND_LINKS at vendomat's prebuilt pyjutsu
  # wheelhouse so `repoman-sync --machine` can resolve the `wheel:pyjutsu` source in the
  # machine repoman.lock. Consumers no longer need the vendomat input (the toolchain is
  # system-wide); repoman's own devenv is the one place that must still resolve wheels.
  vendor.enable = true;
  vendor.libs = [ "pyjutsu" ];

  # Face D, editable mode. Vendomat now delivers the shared command closure by default
  # (vendomat v0.3.4), and this repo BUILDS one of the commands in it. Store mode would
  # put a tagged `repoman` ahead of this checkout on PATH, so every edit here would be
  # tested against the last release instead of the working tree. Editable mode delivers
  # nothing and leaves `repoman.cliProvider` alone: the machine venv still resolves the
  # other managers, and this tree resolves itself.
  #
  # Every tool in the roster needs this line in its own repo — copyroom, docman, gitman.
  vendor.toolchain.mode = "editable";

  # Self-hosting (project 14 seam): this shell is a real managed repo with the full roster
  # wired — copy/git/test/doc — so the shared toolchain (copyroom, gitman, docman) is on
  # PATH here and `copyroom new <target> --answers … --trust` can birth new repos from this
  # checkout's shell (no host-repo trick). The meta-module (devenv.yaml `imports: [repoman]`)
  # owns the `repoman-sync` script now — consumer mode installs skills, `--machine` syncs
  # the shared toolchain; repoman-sync.sh itself defaults REPOMAN_ROOT to DEVENV_ROOT.
  repoman = {
    enable = true;
    managers = [ "copy" "git" "test" "doc" ];
  };

  scripts = {
    test = {
      exec = ''
        pytest "$@"
      '';
      description = "Run tests with pytest";
    };

    format = {
      exec = ''
        ruff format src/ tests/
      '';
      description = "Format code with ruff";
    };

    lint = {
      exec = ''
        ruff check src/ tests/
      '';
      description = "Lint code with ruff";
    };
  };

  languages = {
    python = {
      enable = true;
      version = "3.13";
      venv.enable = true;
      uv.enable = true;
    };
  };

  enterShell = ''
    echo ""
    echo "╔════════════════════════════════════════════╗"
    echo "║             repoman devenv                 ║"
    echo "╚════════════════════════════════════════════╝"
    echo ""
    echo "🐍 Python: $(python --version)"
    echo ""
    echo "Available commands:"
    echo "  test   - Run tests with pytest"
    echo "  format - Format code with ruff"
    echo "  lint   - Lint code with ruff"
    echo ""
    echo "Quick start:"
    echo "  0. Bootstrap the shared toolchain: repoman-sync --machine"
    echo "  1. Install dependencies: uv sync --all-extras"
    echo "  2. Run tests: test"
    echo ""
  '';

  # devman — the automation plane (CONCEPT.md §5). `base` alone: this repository
  # ships no scheduled work and writes none of its own files.
  devman = {
    enable = true;
    project = "repoman";
    groups = [ "base" ];
  };

  # Re-lock devenv.lock from the FLEET shape: the published tags in devenv.yaml,
  # not the machine-local urls in devenv.local.yaml.
  #
  # `devenv shell` rewrites devenv.lock in place, so any shell taken with the overlay
  # active re-locks the overlaid inputs at their local paths. That is fine while you
  # work and wrong the moment it leaves this machine, so the pre-push hook blocks it
  # (.pyjutsu-hooks.toml) and this script is the fix it names.
  #
  # The overlay is moved aside INSIDE the repo, not to /tmp: an interrupted run then
  # leaves it next to where it belongs rather than in a directory you would not think
  # to look. The trap restores it on any exit, including a signal.
  scripts.relock = {
    description = "Re-lock devenv.lock from devenv.yaml's published tags.";
    exec = ''
      set -euo pipefail
      cd "''${DEVENV_ROOT:-$PWD}"

      overlay=devenv.local.yaml
      stash=.devenv.local.yaml.relock

      restore() {
        if [ -e "$stash" ]; then mv -f "$stash" "$overlay"; fi
      }
      trap restore EXIT INT TERM

      if [ -e "$stash" ]; then
        echo "relock: $stash already exists — a previous run was interrupted." >&2
        echo "relock:   check it, then move it back to $overlay by hand." >&2
        exit 2
      fi
      if [ -e "$overlay" ]; then
        mv "$overlay" "$stash"
      fi

      devenv update "$@"

      restore
      trap - EXIT INT TERM

      if python3 scripts/check-fleet-lock.py; then
        echo "relock: devenv.lock is in the fleet shape — commit it."
      fi
    '';
  };

  # https://devenv.sh/tasks/
  #
  # The two task names the `base` group calls (groups/base/README.md). devenv
  # owns each implementation; Dagu owns the composition (§6).
  #
  # `base:test` forwards to `repoman:test` — the repository's own gate, defined
  # by the testee manager module (`testee verify --mode quick`); duplicating it
  # would be a second implementation (PROPOSAL.md §6 rule 6). `base:check` is
  # the fast one: ruff over the repo's own `src` scope (`uv run --group dev`
  # because the venv bin is not on the task runner's PATH).
  tasks = {
    "repoman:lint".exec = "uv run --group dev ruff check src";
    "base:check".after = [ "repoman:lint" ];
    "base:test".after = [ "repoman:test" ];
  };
}
