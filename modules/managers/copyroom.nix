# RepoMan manager wiring: copyroom (templating / scaffolding / convergence).
#
# Imported unconditionally by ../devenv.nix; activates only when "copy" is in
# `repoman.managers`. copyroom is the core pillar (the repo "genome"): it births
# repos from a template and keeps them converged. The CLI itself is pure-Python
# (Copier), installed into the venv by repoman-sync — but it SHELLS OUT to `git`
# (render/update/simulate/preview; `copyroom doctor` flags it) and to `patch`
# (gnupatch, for patch-type template edits). Neither is a Python dep, so this
# module provisions them at the nix layer, gated on "copy" — the same approach
# gitman uses for its Rust toolchain.
{ pkgs, lib, config, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "copy" cfg.managers;
  venvBin = "${config.devenv.state}/venv/bin";
in
{
  config = lib.mkIf enabled {
    # Runtime binaries the copyroom CLI shells out to. devenv merges `packages`
    # across modules, so re-listing git (often already present via base) is harmless.
    packages = [ pkgs.git pkgs.gnupatch ];

    tasks = {
      "repoman:template:status".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/copyroom status'';
    };
  };
}
