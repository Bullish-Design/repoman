# RepoMan manager wiring: copyroom (templating / scaffolding / convergence).
#
# Imported unconditionally by ../devenv.nix; activates only when "copy" is in
# the project manifest roster. copyroom is the core pillar. It births a repo from the
# genome (the base template, such as template-py) and converges the repo's template layers.
# The CLI itself is pure-Python (Copier). It comes from Vendomat's closure through
# $REPOMAN_TOOLCHAIN_BIN, and repoman-sync installs nothing. The CLI also SHELLS OUT to
# `git` (render/update/simulate/preview; `copyroom doctor` flags it) and to `patch`
# (gnupatch, for patch-type template edits). Neither is a Python dep, so this
# module provisions them at the nix layer, gated on "copy". gitman.nix gates its
# opt-in Rust toolchain the same way.
{ pkgs, lib, config, repomanManagers, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "copy" repomanManagers;
in
{
  config = lib.mkIf enabled {
    # Runtime binaries the copyroom CLI shells out to. devenv merges `packages`
    # across modules, so re-listing git (often already present via base) is harmless.
    packages = [ pkgs.git pkgs.gnupatch ];

    tasks = {
      # copyroom lives in Vendomat's shared store closure, resolved at runtime.
      "repoman:template:status".exec = ''cd "$DEVENV_ROOT" && "${cfg.toolchainBin}"/copyroom status'';
    };
  };
}
