# RepoMan manager wiring: copyroom (templating / scaffolding / convergence).
#
# Imported unconditionally by ../devenv.nix; activates only when "copy" is in
# `repoman.managers`. copyroom is the core pillar (the repo "genome"): it births
# repos from a template and keeps them converged. Pure-Python (Copier), installed
# into the venv by repoman-sync.
{ lib, config, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "copy" cfg.managers;
  venvBin = "${config.devenv.state}/venv/bin";
in
{
  config = lib.mkIf enabled {
    tasks = {
      "repoman:template:status".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/copyroom status'';
    };
  };
}
