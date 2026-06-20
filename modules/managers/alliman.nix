# RepoMan manager wiring: alliman (spec-driven agent assets — Allium).
#
# Imported unconditionally by ../devenv.nix; activates only when "spec" is in
# `repoman.managers`. The `alliman` console script (added by allium-env's CLI-alignment
# project) is pure-Python and installed into the venv by repoman-sync; its `doctor`
# verifies Allium's skill/prompt assets are installed. The third-party `allium` spec
# binary travels with allium-env's own devenv module, NOT here — repoman drives the
# manager CLI (`alliman`), never the tool (`allium`). The module file, task namespace,
# and registry command all use `alliman` so the `allium` collision can't be reintroduced.
{ lib, config, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "spec" cfg.managers;
  venvBin = "${config.devenv.state}/venv/bin";
in
{
  config = lib.mkIf enabled {
    tasks = {
      # alliman owns its own report; `repoman doctor` aggregates via the CLI.
      "repoman:spec:doctor".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/alliman doctor'';
    };
  };
}
