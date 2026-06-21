# RepoMan manager wiring: alliman (spec-driven agent assets — Allium).
#
# Imported unconditionally by ../devenv.nix; activates only when "spec" is in
# `repoman.managers`. alliman is an APPROACH-B manager: the `alliman` CLI's doctor /
# install-skills need nix-layer provisioning — the `allium-install-codex-skills`
# installer script, the `ALLIUM_*` env, and Allium's vendored asset trees — which
# live in allium-env's OWN reusable, enable-gated module (`<allium-env>/modules/allium.nix`).
# Rather than re-declare that (a fetched-binary derivation + a script + asset sourcing),
# we presence-import allium-env's module and activate it gated on roster membership.
#
# devenv `imports` can't depend on `config` (only `inputs`), so the import is gated on
# the consumer having declared the `allium-env` input; activation (`allium.enable`) is
# gated on "spec" also being selected. The third-party `allium` binary is NOT needed by
# the `alliman` CLI (doctor/install-skills never call it), so `allium.cli.enable` defaults
# OFF here — no heavy juxt/allium-tools fetch unless a consumer opts in.
{ inputs, lib, config, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "spec" cfg.managers;
  venvBin = "${config.devenv.state}/venv/bin";
  hasInput = inputs ? allium-env;
in
{
  imports = lib.optional hasInput (inputs.allium-env + "/modules/allium.nix");

  config = lib.mkMerge [
    # Activate allium-env's gated module (installer + env + assets) when "spec" is
    # selected AND its provisioning is available. `optionalAttrs hasInput` (not `mkIf`)
    # so the `allium.*` references vanish entirely when the input is absent — else a
    # strict eval throws "option `allium' does not exist".
    (lib.optionalAttrs hasInput {
      allium.enable = lib.mkIf enabled true;
      # alliman doesn't need the third-party `allium` binary; skip the fetch by default
      # (also dodges the darwin placeholder hashes). A consumer wanting the spec tool
      # itself can override allium.cli.enable = true.
      allium.cli.enable = lib.mkDefault false;
    })
    # The doctor task wires whenever "spec" is selected — `repoman doctor` calls the venv
    # `alliman` CLI (installed by repoman-sync) regardless; if provisioning is absent its
    # own doctor reports the gap.
    (lib.mkIf enabled {
      tasks = {
        "repoman:spec:doctor".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/alliman doctor'';
      };
    })
  ];
}
