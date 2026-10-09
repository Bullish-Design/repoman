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
# install anything. The host profile puts the pure-CLI managers (copyroom, gitman,
# docman) on PATH, and RepoMan runs them by name. RepoMan reads no Vendomat closure
# and no manifest. testee is the exception: it runs inside the consumer's code, so
# it is a per-repo uv dev dependency declared in pyproject.toml.
{ pkgs, lib, config, inputs ? {}, ... }:

let
  cfg = config.repoman;

  allManagers = [ "copy" "git" "test" "doc" ];

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
    else if rawManifest ? managers && !(builtins.all (m: builtins.elem m allManagers) rawManifest.managers) then
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
    ./managers/docman.nix   # activates when "doc" is selected (pure-Python; toolchain in docman's module)
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
    # signal, the same presence-gated pattern shellij and docman already use.
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
      # Consumer venv bin. devenv's interactive shell prepends this itself, but
      # `devenv tasks run` does NOT — its PATH lacks the venv, so a task that shells
      # out to a venv console script (e.g. testee's `lint-imports` arch test) fails.
      # Tasks DO run this enterShell block (PROGRESS §0.2), so prepending here is a
      # no-op for the shell and fixes tasks. testee stays a per-repo uv dependency.
      export PATH="${config.devenv.state}/venv/bin:$PATH"
      if [ -t 1 ]; then
        echo "RepoMan: managers = ${lib.concatStringsSep " " managerRoster}"
      fi
    '';
    })
  ];
}
