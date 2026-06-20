# RepoMan manager wiring: zelligate (live terminal / session surface — Zellij).
#
# Imported unconditionally by ../devenv.nix; activates only when "session" is in
# `repoman.managers`. The `zelligate` console script is pure-Python and installed into
# the venv by repoman-sync; this module additionally provisions the Zellij binary the
# session surface drives (gated on "session", so repos without it never pull Zellij —
# the same discipline gitman uses for the Rust toolchain).
{ pkgs, lib, config, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "session" cfg.managers;
  venvBin = "${config.devenv.state}/venv/bin";
in
{
  config = lib.mkIf enabled {
    # System dependency: Zellij. zelligate shells out to `zellij` for session ops; its
    # doctor reports `zellij` not-found rather than failing, but the surface is unusable
    # without it, so provision it whenever "session" is selected.
    packages = [ pkgs.zellij ];

    tasks = {
      # zelligate owns its own report; `repoman status`/`doctor` aggregate via the CLI.
      "repoman:session:status".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/zelligate list'';
      "repoman:session:doctor".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/zelligate doctor'';
    };
  };
}
