# The RepoMan meta-module — THE file consumers import.
#
# Usage in a consuming repo's devenv.yaml:
#
#   inputs:
#     repoman:
#       url: path:../repoman/modules        # or github:Bullish-Design/repoman?dir=modules
#       flake: false
#   imports:
#     - repoman
#
# Then in devenv.nix:
#
#   repoman.enable = true;
#
# Each manager's wiring lives in ./managers/<name>.nix and gates itself on
# membership in the tracked project manifest. Imports cannot depend on `config`, so we
# import every manager module statically and let each one decide whether to
# activate — the standard devenv/NixOS module idiom.
#
# The manifest roster selects which manager tasks/skills are WIRED. It does not
# install anything. The host profile puts the manager commands (copyroom, gitman,
# and testee) on PATH, and RepoMan runs them by name. Testee starts outside
# devenv and opens a clean shell for the checks. RepoMan reads no Vendomat closure.
{ pkgs, lib, config, inputs ? {}, ... }:

let
  cfg = config.repoman;

  allManagers = [ "copy" "git" "test" ];

  # Keys that RepoMan once shipped. A manifest that still names one is accepted, so
  # a stale repo keeps evaluating. No manager module reads the key, and
  # `repoman doctor` warns about it (`roster:unknown-manager`).
  removedManagers = [ "doc" ];

  # Project 039: the roster moves from a devenv.nix option to a tracked repo
  # manifest, `.repoman/project.toml`, modelled on
  # `devman/src/devman_contract/manifest.py`'s discipline — fixed field set,
  # unknown fields rejected outright, values checked against the same grammar
  # the option already enforces. `cliProvider` is a legacy key owned by the
  # Vendomat consumer config; accept it for compatibility, but do not use it to
  # select RepoMan's manager binaries. Absent file means the default roster, so
  # 15 of 23 known consumers need no file at all.
  manifestPath = "${config.devenv.root}/.repoman/project.toml";
  manifestKnownFields = [ "schema" "managers" "cliProvider" ];
  rawManifest =
    if builtins.pathExists manifestPath then
      builtins.fromTOML (builtins.readFile manifestPath)
    else
      { };
  manifestUnknownFields =
    builtins.filter (name: !(builtins.elem name manifestKnownFields))
      (builtins.attrNames rawManifest);
  manifest =
    if rawManifest == { } then
      { }
    else if manifestUnknownFields != [ ] then
      throw ("repoman: " + manifestPath + " has unknown field(s): "
        + lib.concatStringsSep ", " manifestUnknownFields)
    else if !(rawManifest ? schema) then
      throw ("repoman: " + manifestPath + " is missing the required field 'schema'")
    else if rawManifest.schema != 1 then
      throw ("repoman: " + manifestPath + " field 'schema' has unsupported value "
        + toString rawManifest.schema + "; supported schema is 1")
    else if rawManifest ? managers && !(builtins.all (m: builtins.elem m (allManagers ++ removedManagers)) rawManifest.managers) then
      throw ("repoman: " + manifestPath + " field 'managers' names an unknown manager;"
        + " valid values are " + lib.concatStringsSep ", " allManagers)
    else if rawManifest ? cliProvider && !(builtins.elem rawManifest.cliProvider [ "store" "venv" ]) then
      throw ("repoman: " + manifestPath + " field 'cliProvider' has unsupported value "
        + toString rawManifest.cliProvider + "; supported values are store and venv")
    else
      rawManifest;

  managerRoster = if manifest ? managers then manifest.managers else [ "copy" "git" "test" ];

in
{
  imports = [
    ./managers/testee.nix
    ./managers/copyroom.nix
    ./managers/gitman.nix   # activates when "git" is selected; contributes git only
  ]
  # shellij is NOT a roster manager: no roster entry, no repoman.session.*
  # options, nothing to select. It is installed by default — new-repo templates
  # (copyroom's canonical template) declare the `shellij` input and RepoMan
  # presence-imports shellij's own devenv module (packages: shellij/zellij/yazi,
  # the guarded `shellij open` enterShell hook, and YAZI_CONFIG_HOME pointing at
  # the packaged Yazi assets), so it is wired and auto-configured for use with
  # zero repoman config. Inputs aren't transitive across a remote module import,
  # so a repo that doesn't declare the input simply doesn't get shellij.
  #
  # CAVEAT: `imports` cannot depend on `config`, so this import is gated on the
  # INPUT only — not on `repoman.enable`. A repo that declares the shellij input
  # but sets `repoman.enable = false` still gets shellij's module (the input
  # declaration IS the gate — the module itself is unconditional; it has no
  # `shellij.enable` option). To opt out entirely, drop the input from
  # devenv.yaml.
  ++ lib.optional (inputs ? shellij) (inputs.shellij + "/modules/devenv.nix");

  options.repoman = {
    # Project 039: defaults to true, not `lib.mkEnableOption`'s usual false. Before
    # 039 the module was ALWAYS imported (the per-repo devenv.yaml pin), so an
    # explicit `repoman.enable = true;` was the real signal and false let a repo
    # opt out without removing the pin. Now the module is only present when a
    # consumer's central devenv.local.nix imports it — that import IS the enable
    # signal, the same presence-gated pattern shellij already uses.
    # `repoman.enable = false;` still opts a repo out explicitly if it ever needs
    # to keep the import (e.g. transitively, for shellij) without running repoman.
    enable = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "RepoMan: the agentic repo lifecycle conductor.";
    };

  };

  config = lib.mkMerge [
    { _module.args.repomanManagers = managerRoster; }
    (lib.mkIf cfg.enable {
    # Tell the `repoman` CLI which managers are wired in (it reads this to build
    # the router skill and to pick the expected skill set) and where skills go.
    env.REPOMAN_MANAGERS = lib.concatStringsSep " " managerRoster;
    # Project 039: `skillsDir` and `installSkills` were dead option surface — the
    # 2026-09-15 measurement found zero of twenty-three importing repositories set
    # either. The path itself stays the family's agent-files convention.
    env.REPOMAN_SKILLS_DIR = ".agents/skills";

    # Check that repoman is on PATH, then generate this repo's lifecycle router skill.
    scripts.repoman-sync = {
      description = "Generate this repo's lifecycle router skill.";
      exec = ''exec ${pkgs.bash}/bin/bash ${./scripts/repoman-sync.sh} "$@"'';
    };

    enterShell = ''
      # Tasks run this enterShell block, but do not prepend the consumer venv.
      # Keep app tools available, then put the host Testee profile before packages
      # added by devenv. The doctor and manager task use this same wrapper.
      export REPOMAN_TESTEE_HOST_BIN="''${REPOMAN_TESTEE_HOST_BIN:-$HOME/.nix-profile/bin/testee}"
      export PATH="${config.devenv.state}/venv/bin:$(dirname "$REPOMAN_TESTEE_HOST_BIN"):$PATH"
      if [ -t 1 ]; then
        echo "RepoMan: managers = ${lib.concatStringsSep " " (builtins.filter (m: builtins.elem m allManagers) managerRoster)}"
      fi
    '';
    })
  ];
}
