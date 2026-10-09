{ pkgs, config, ... }:
let
  # Testee v0.5.0, the fleet's private-repo pin form (gh credential route; the
  # anonymous `github:` shorthand 404s — see the fleet migration guide). One
  # pinned source supplies BOTH the wrapper package and the manifest module.
  testeeFlake =
    builtins.getFlake "git+https://github.com/Bullish-Design/testee?ref=refs/tags/v0.5.0";
in
{
  imports = [ testeeFlake.devenvModules.default ];

  # Testee v2 gate; whole-tree checks mirror the v0.4 built-in tool set. The
  # wrapper package here backs the module; the HOST also runs the same tagged
  # wrapper from `nix profile` (fleet v2 pattern).
  testee.package = testeeFlake.packages.${pkgs.stdenv.hostPlatform.system}.testee;
  testee.checks = {
    ruff = {
      argv = [ "${pkgs.bash}/bin/bash" "-c" "uv run --no-sync ruff check . --output-format json" ];
      profiles = [ "quick" "full" ];
      structured = { parser = "ruff-json"; file = "ruff.stdout.log"; };
    };
    ruff-format = {
      argv = [ "${pkgs.bash}/bin/bash" "-c" "uv run --no-sync ruff format --check ." ];
      profiles = [ "quick" "full" ];
    };
    ty = {
      argv = [ "${pkgs.bash}/bin/bash" "-c" "uv run --no-sync ty check ." ];
      profiles = [ "full" ];
    };
    pytest = {
      argv = [ "${pkgs.bash}/bin/bash" "-c" ''uv run --no-sync pytest -q --junitxml="$TESTEE_RUN_DIR/pytest.junit.xml"'' ];
      profiles = [ "full" ];
      structured = { parser = "junit-xml"; file = "pytest.junit.xml"; };
    };
  };

  env = {
    DEVENV_PROJECT = "repoman";
  };

  packages = with pkgs; [
    git
    curl
    jq
  ];

  # Self-hosting (project 14 seam): this shell is a real managed repo with the full roster
  # wired — copy/git/test/doc. The host profile puts copyroom, gitman and docman on PATH, so
  # `copyroom new <target> --answers … --trust` can birth new repos from this checkout's
  # shell (no host-repo trick). `repoman` itself resolves to this checkout's editable venv
  # install, so an edit here is never tested against the last release. The meta-module
  # (devenv.yaml `imports: [repoman]`) owns the `repoman-sync` script.
  repoman = {
    enable = true;
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
    echo "  0. Install the router skill: repoman-sync"
    echo "  1. Install dependencies: uv sync --all-extras"
    echo "  2. Run tests: test"
    echo ""
  '';

  # Re-lock devenv.lock from the FLEET shape: the published tags in devenv.yaml,
  # not the machine-local urls in devenv.local.yaml.
  #
  # `devenv shell` rewrites devenv.lock in place, so any shell taken with the overlay
  # active re-locks the overlaid inputs at their local paths. That is fine while you
  # work and wrong the moment it leaves this machine, so the `gate` script blocks it
  # and this script is the fix it names.
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

  # The release gate. Native `jj git push` runs no hook, so nothing stops a bad push or
  # tag unless the author runs this first. It checks the lock, then runs the full
  # Testee gate. Run `gate` before `jj git push` and before `gh release create`.
  scripts.gate = {
    description = "Release gate: refuse a local-path lock, then run testee verify --full.";
    exec = ''
      set -euo pipefail
      cd "''${DEVENV_ROOT:-$PWD}"
      # Check the lock committed at HEAD (the parent of the working copy), not the working
      # tree: entering this shell rewrote the working-tree lock before this line ran.
      python3 scripts/check-fleet-lock.py --rev HEAD
      testee verify --full
    '';
  };

  # https://devenv.sh/tasks/
  #
  # The two task names the `base` group calls (groups/base/README.md). devenv
  # owns each implementation; Dagu owns the composition (§6).
  #
  # `base:test` forwards to `repoman:test` — the repository's own gate, defined
  # by the testee manager module (`testee verify`); duplicating it
  # would be a second implementation (PROPOSAL.md §6 rule 6). `base:check` is
  # the fast one: ruff over the repo's own `src` scope (`uv run --group dev`
  # because the venv bin is not on the task runner's PATH).
  tasks = {
    "repoman:lint".exec = "uv run --group dev ruff check src";
    "base:check".after = [ "repoman:lint" ];
    "base:test".after = [ "repoman:test" ];
  };
}
