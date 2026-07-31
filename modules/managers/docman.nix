# RepoMan manager wiring: docman (docs build/check).
#
# Imported unconditionally by ../devenv.nix; activates only when "doc" is in
# `repoman.managers`. docman is an APPROACH-B manager: its docs toolchain
# (zensical + lychee/markdownlint/typos/…) and its `enterShell` config seeding live
# in docman's OWN reusable, enable-gated module (`<docman>/modules/docman.nix`,
# `options.docman.*`, whole `config` behind `mkIf cfg.enable`). Rather than
# re-declare that toolchain here (it wouldn't fit a few `pkgs.*` and would drift),
# we pull docman's module through and gate its activation on roster membership.
#
# Because devenv `imports` cannot depend on `config` (only on `inputs`), the import
# is gated on the consumer having declared the `docman` input, and the module is
# *activated* (`docman.enable = true`) only when "doc" is also selected. A consumer
# that selects "doc" but hasn't declared the input still gets the doctor task wired;
# `repoman doctor` warns that the nix provisioning is absent (see checks.py).
{ inputs ? {}, lib, config, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "doc" cfg.managers;
  venvBin = "${config.devenv.state}/venv/bin";
  # Did the consumer declare the docman input? (Approach-B managers require it —
  # devenv.yaml inputs are not transitive across a remote module import.)
  hasInput = inputs ? docman;
in
{
  # Presence-gated static import: pulled in only when the input exists, so consumers
  # that don't use docman never need to declare it. `inputs` is available at
  # import-resolution time (unlike `config`), which is what makes this legal.
  imports = lib.optional hasInput (inputs.docman + "/modules/docman.nix");

  config = lib.mkMerge [
    # Activate docman's own gated module (toolchain + enterShell config seeding) when
    # "doc" is selected AND its provisioning is available. Gated with `optionalAttrs
    # hasInput` (depends on `inputs`, not `config`) so that when the docman input is
    # absent the `docman.enable` reference vanishes entirely — `mkIf` alone still
    # places a definition for the then-undeclared `docman` option, which throws
    # "option `docman' does not exist" under a strict full-config eval.
    (lib.optionalAttrs hasInput (lib.mkIf enabled {
      docman.enable = true;
      # Signal to `repoman doctor` (checks.py) that docman's nix module is imported
      # AND active — provisioned:doc is OK. Without the input this whole block (and
      # the env) vanishes, so the check warns. See run_self_check().
      env.REPOMAN_PROVISIONED_DOC = "1";
    }))
    # The aggregation tasks wire whenever "doc" is selected — `repoman doctor` calls
    # the venv `docman` CLI (installed by repoman-sync) regardless of provisioning;
    # if the toolchain is absent its own doctor reports the gap.
    (lib.mkIf enabled {
      tasks = {
        "repoman:docs:doctor".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/docman doctor'';
        "repoman:docs:build".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/docman build'';
      };
    })
  ];
}
