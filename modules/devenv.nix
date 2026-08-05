# The RepoMan meta-module — THE file consumers import.
#
# Usage in a consuming repo's devenv.yaml:
#
#   inputs:
#     repoman:
#       url: path:../repoman/modules        # or github:Bullish-Design/repoman?dir=modules
#       flake: false
#   imports:
#     - repoman
#
# Then in devenv.nix:
#
#   repoman.enable = true;
#   repoman.managers = [ "copy" "git" "test" ];
#
# Each manager's wiring lives in ./managers/<name>.nix and gates itself on
# membership in `repoman.managers`. Imports cannot depend on `config`, so we
# import every manager module statically and let each one decide whether to
# activate — the standard devenv/NixOS module idiom.
#
# `repoman.managers` selects which manager tasks/skills are WIRED — it no longer
# gates toolchain installation (project 12): the pure-CLI managers live in a
# single system-wide toolchain venv ($REPOMAN_TOOLCHAIN_VENV, populated by
# `repoman-sync --machine` from the machine repoman.lock) regardless of any one
# repo's roster. testee is the exception: it runs inside the consumer's code, so
# it is a per-repo uv dev dependency declared in pyproject.toml.
{ pkgs, lib, config, inputs ? {}, ... }:

let
  cfg = config.repoman;

  allManagers = [ "copy" "git" "test" "doc" ];

  # D1: a SHELL expression, expanded by bash at task/shell time — never a nix-eval-time
  # absolute path. Reading $HOME via the nix builtin would bake one user's path into the
  # eval result and yield "/repoman/venv" wherever HOME is unset (CI, nix-daemon).
  toolchainVenvExpr = "\${REPOMAN_TOOLCHAIN_VENV:-\${XDG_DATA_HOME:-$HOME/.local/share}/repoman/venv}";
in
{
  imports = [
    ./managers/testee.nix
    ./managers/copyroom.nix
    ./managers/gitman.nix   # contributes a Rust/maturin toolchain when "git" is selected,
                            # to build the unpublished pyjutsu native extension — see SPIKE.md
    ./managers/docman.nix   # activates when "doc" is selected (pure-Python; toolchain in docman's module)
  ]
  # shellij is NOT a roster manager: no `repoman.managers` entry, no repoman.session.*
  # options, nothing to select. It is installed by default — new-repo templates
  # (copyroom's canonical template) declare the `shellij` input and RepoMan
  # presence-imports shellij's own devenv module (packages: shellij/zellij/yazi,
  # the guarded `shellij open` enterShell hook, and YAZI_CONFIG_HOME pointing at
  # the packaged Yazi assets), so it is wired and auto-configured for use with
  # zero repoman config. Inputs aren't transitive across a remote module import,
  # so a repo that doesn't declare the input simply doesn't get shellij.
  #
  # CAVEAT: `imports` cannot depend on `config`, so this import is gated on the
  # INPUT only — not on `repoman.enable`. A repo that declares the shellij input
  # but sets `repoman.enable = false` still gets shellij's module (the input
  # declaration IS the gate — the module itself is unconditional; it has no
  # `shellij.enable` option). To opt out entirely, drop the input from
  # devenv.yaml.
  ++ lib.optional (inputs ? shellij) (inputs.shellij + "/modules/devenv.nix");

  options.repoman = {
    enable = lib.mkEnableOption "RepoMan: the agentic repo lifecycle conductor";

    managers = lib.mkOption {
      type = lib.types.listOf (lib.types.enum allManagers);
      default = [ "copy" "git" "test" ];
      description = ''
        Which managers' tasks/skills are WIRED into this repo. Does NOT gate
        toolchain installation (project 12): the shared toolchain venv holds every
        pure-CLI manager regardless; testee is a per-repo uv dev dependency.
      '';
    };

    template = lib.mkOption {
      type = lib.types.str;
      default = "gh:Bullish-Design/template-py";
      description = "copyroom's canonical template (the repo 'genome') for new/converge.";
    };

    # D1: shell expression for the system-wide toolchain venv's bin dir. Manager modules
    # interpolate it into task execs: "''${cfg.toolchainBin}"/gitman status. Honours
    # $REPOMAN_TOOLCHAIN_VENV, else $XDG_DATA_HOME/repoman/venv, else ~/.local/share/repoman/venv.
    # Populated by `repoman-sync --machine`. NOT a nix path — bash expands it at runtime.
    toolchainBin = lib.mkOption {
      type = lib.types.str;
      internal = true;
      readOnly = true;
      default = "${toolchainVenvExpr}/bin";
      description = ''
        Shell expression (NOT a nix path) for the system-wide toolchain venv's bin dir.
        Manager modules interpolate it into task execs: "''${cfg.toolchainBin}"/gitman status.
        Honours $REPOMAN_TOOLCHAIN_VENV, else $XDG_DATA_HOME/repoman/venv, else
        ~/.local/share/repoman/venv. Populated by `repoman-sync --machine`.
      '';
    };

    installSkills = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Generate the aggregated RepoMan entrypoint (router) skill at sync time.";
    };

    skillsDir = lib.mkOption {
      type = lib.types.str;
      default = ".agents/skills";
      description = "Directory (relative to repo root) where agent skills are installed (the family's agent-files convention).";
    };
  };

  config = lib.mkIf cfg.enable {
    # Tell the `repoman` CLI which managers are wired in (it reads this to know
    # which sub-doctors / sub-status commands to aggregate) and where skills go.
    env.REPOMAN_MANAGERS = lib.concatStringsSep " " cfg.managers;
    env.REPOMAN_SKILLS_DIR = cfg.skillsDir;

    # Verify the shared toolchain venv, then install this repo's agent skills + devman docs.
    scripts.repoman-sync = {
      description = "Verify the shared toolchain venv, then install this repo's agent skills + devman docs.";
      exec = ''exec ${pkgs.bash}/bin/bash ${./scripts/repoman-sync.sh} "$@"'';
    };

    # (This whole block is inside `config = lib.mkIf cfg.enable`, so no inner
    # enable guard is needed — the optionalString below only pads a constant.)
    enterShell = ''
      export REPOMAN_TOOLCHAIN_VENV="${toolchainVenvExpr}"
      # ORDER IS LOAD-BEARING. Both prepends below are needed, and the toolchain must
      # end up FIRST — the two lines are written in reverse of the PATH order they
      # produce, because each one prepends.
      #
      # 1. Consumer venv bin. devenv's interactive shell prepends this itself, but
      #    `devenv tasks run` does NOT — its PATH lacks the venv, so a task that shells
      #    out to a venv console script (e.g. testee's `lint-imports` arch test) fails.
      #    Tasks DO run this enterShell block (PROGRESS §0.2), so prepending here is a
      #    no-op for the shell and fixes tasks.
      export PATH="${config.devenv.state}/venv/bin:$PATH"
      # 2. D1: runtime shell expression for the SYSTEM-WIDE toolchain bin. This lands
      #    ahead of the consumer venv so a stale pre-migration copy of a manager CLI
      #    left in .devenv/state/venv/bin cannot shadow the shared toolchain. Getting
      #    this backwards is silent: `repoman doctor` and `devenv tasks run` would
      #    resolve different binaries (doctor's installed:<key> flags exactly that).
      export PATH="$REPOMAN_TOOLCHAIN_VENV/bin:$PATH"
      if [ ! -x "$REPOMAN_TOOLCHAIN_VENV/bin/repoman" ]; then
        echo "RepoMan: shared toolchain not bootstrapped ($REPOMAN_TOOLCHAIN_VENV)." >&2
        echo "RepoMan:   cd <repoman checkout> && devenv shell -- repoman-sync --machine" >&2
      fi
      if [ -t 1 ]; then
        echo "RepoMan: managers = ${lib.concatStringsSep " " cfg.managers}"
      fi
    '';
  };
}
