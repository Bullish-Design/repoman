# RepoMan manager wiring: mypi-agent (coding-agent runtime + per-repo secrets — Pi).
#
# Imported unconditionally by ../devenv.nix; activates only when "agent" is in
# `repoman.managers`. The `mypi` console script is pure-Python and installed into the venv
# by repoman-sync; this module additionally provisions `secretspec` (the binary mypi's
# secrets verbs drive). DELIBERATELY minimal: it does NOT replicate mypi-agent's own
# pi-agent.nix shell-entry bootstrap (mypi sync / secretspec-setup) — repoman is pass-through
# and lets the user drive `mypi sync` when they want the runtime. Gated on "agent", so repos
# without it never pull secretspec.
{ pkgs, lib, config, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "agent" cfg.managers;
  venvBin = "${config.devenv.state}/venv/bin";
in
{
  config = lib.mkIf enabled {
    packages = [ pkgs.secretspec ];

    tasks = {
      # cd into the project root so mypi's Paths.discover() finds devenv.nix.
      # mypi owns its own report; `repoman status`/`doctor` aggregate via the CLI.
      "repoman:agent:status".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/mypi paths'';
      "repoman:agent:doctor".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/mypi doctor'';
    };
  };
}
