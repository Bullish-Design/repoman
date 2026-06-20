# RepoMan manager wiring: docman (docs build/check).
#
# Imported unconditionally by ../devenv.nix; activates only when "doc" is in
# `repoman.managers`. The `docman` console script (added by docman's CLI-alignment
# project) is pure-Python and installed into the venv by repoman-sync. The docs
# TOOLCHAIN (zensical/lychee/…) ships through docman's own devenv module, NOT here —
# this module only namespaces the repoman:docs:* tasks, so a repo selecting "doc" for
# the CLI surface isn't forced to pull the full mkdocs/lychee stack unless it also
# imports docman's module. repoman drives the CLI, not the toolchain.
{ lib, config, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "doc" cfg.managers;
  venvBin = "${config.devenv.state}/venv/bin";
in
{
  config = lib.mkIf enabled {
    tasks = {
      # docman owns its own report; `repoman doctor` aggregates via the CLI.
      "repoman:docs:doctor".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/docman doctor'';
      "repoman:docs:build".exec  = ''cd "$DEVENV_ROOT" && ${venvBin}/docman build'';
    };
  };
}
