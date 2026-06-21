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

    # zelligate's config defaults are Docker-first (workspace=/workspaces,
    # state=/workspaces/.zelligate, docker_mode=1). Outside a container those paths
    # don't exist / aren't writable, so `zelligate doctor` hard-fails (exit 2) on a
    # plain consumer even though the surface is otherwise fine. Point the workspace +
    # state at in-repo, writable locations and turn docker-mode off by default. All
    # `mkDefault` so a consumer actually running the Docker workbench can override.
    env = {
      ZELLIGATE_DOCKER_MODE = lib.mkDefault "0";
      ZELLIGATE_WORKSPACE_DIR = lib.mkDefault config.devenv.root;
      ZELLIGATE_STATE_DIR = lib.mkDefault "${config.devenv.state}/zelligate";
    };

    tasks = {
      # zelligate owns its own report; `repoman status`/`doctor` aggregate via the CLI.
      "repoman:session:status".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/zelligate list'';
      "repoman:session:doctor".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/zelligate doctor'';
    };
  };
}
