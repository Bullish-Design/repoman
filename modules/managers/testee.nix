# RepoMan manager wiring: testee (verification).
#
# Imported unconditionally by ../devenv.nix; activates only when "test" is in
# `repoman.managers`. Mirrors testee's own nix/testee.nix: it assumes the
# `testee` console script is in the consumer venv (project 12 — testee is a
# per-repo uv dev dependency declared in pyproject.toml) and resolves
# ruff/ty/pytest relative to its own interpreter.
{ lib, config, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "test" cfg.managers;
  venvBin = "${config.devenv.state}/venv/bin";
in
{
  config = lib.mkIf enabled {
    # Verification entrypoints, namespaced under repoman:* so the conductor and
    # the underlying tool agree on the surface. testee owns its own report;
    # `repoman doctor` / `repoman status` aggregate via the Python CLI.
    tasks = {
      "repoman:test".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/testee verify --mode quick'';
      "repoman:test:ci".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/testee verify --mode ci'';
    };

    enterTest = ''
      cd "$DEVENV_ROOT" && ${venvBin}/testee verify --mode ci
    '';
  };
}
