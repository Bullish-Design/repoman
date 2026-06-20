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
{ pkgs, lib, config, ... }:

let
  cfg = config.repoman;

  allManagers = [ "copy" "git" "test" "doc" "session" "agent" "spec" ];
in
{
  imports = [
    ./managers/testee.nix
    ./managers/copyroom.nix
    ./managers/gitman.nix   # contributes a Rust/maturin toolchain when "git" is selected,
                            # to build the unpublished pyjutsu native extension — see SPIKE.md
    ./managers/mypi.nix     # contributes pkgs.secretspec when "agent" is selected
  ];

  options.repoman = {
    enable = lib.mkEnableOption "RepoMan: the agentic repo lifecycle conductor";

    managers = lib.mkOption {
      type = lib.types.listOf (lib.types.enum allManagers);
      default = [ "copy" "git" "test" ];
      description = "Which component managers to wire into this repo.";
    };

    template = lib.mkOption {
      type = lib.types.str;
      default = "gh:Bullish-Design/template-py";
      description = "copyroom's canonical template (the repo 'genome') for new/converge.";
    };

    installSkills = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Install each enabled manager's agent skill plus the aggregated RepoMan skill.";
    };

    skillsDir = lib.mkOption {
      type = lib.types.str;
      default = ".claude/skills";
      description = "Directory (relative to repo root) where agent skills are installed.";
    };
  };

  config = lib.mkIf cfg.enable {
    # Tell the `repoman` CLI which managers are wired in (it reads this to know
    # which sub-doctors / sub-status commands to aggregate) and where skills go.
    env.REPOMAN_MANAGERS = lib.concatStringsSep " " cfg.managers;
    env.REPOMAN_SKILLS_DIR = cfg.skillsDir;

    # Pull the selected managers' Python CLIs into the venv from repoman.lock.
    # (Skill installation is layered on next, after the entrypoint template lands.)
    scripts.repoman-sync = {
      description = "Install the selected managers' CLIs into this repo's venv from repoman.lock.";
      exec = ''exec ${pkgs.bash}/bin/bash ${./scripts/repoman-sync.sh}'';
    };

    enterShell = lib.optionalString cfg.enable ''
      if [ -t 1 ]; then
        echo "RepoMan: managers = ${lib.concatStringsSep " " cfg.managers}"
      fi
    '';
  };
}
