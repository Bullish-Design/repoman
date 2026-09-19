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
# The manifest roster selects which manager tasks/skills are WIRED — it no longer
# gates toolchain installation (project 12): the pure-CLI managers live in a
# single Vendomat store closure ($REPOMAN_TOOLCHAIN_BIN) regardless of any one
# repo's roster. testee is the exception: it runs inside the consumer's code, so
# it is a per-repo uv dev dependency declared in pyproject.toml.
{ pkgs, lib, config, inputs ? {}, ... }:

let
  cfg = config.repoman;

  allManagers = [ "copy" "git" "test" "doc" ];

  # Project 039: the roster moves from a devenv.nix option to a tracked repo
  # manifest, `.repoman/project.toml`, modelled on
  # `devman/src/devman_contract/manifest.py`'s discipline — fixed field set,
  # unknown fields rejected outright, values checked against the same grammar
  # the option already enforces. Absent file means the default roster, so 15 of
  # 23 known consumers need no file at all.
  manifestPath = "${config.devenv.root}/.repoman/project.toml";
  manifestKnownFields = [ "schema" "managers" ];
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
    else
      rawManifest;

  managerRoster = if manifest ? managers then manifest.managers else [ "copy" "git" "test" ];

  # Face D seam. The commands are a Nix closure and Vendomat exports its
  # bin dir; there is no path to guess, so an unset variable must FAIL the task rather
  # than expand to "" and exec "/gitman" — a confident wrong answer. `:?` says so at the
  # point of use, which is the only place that knows which command was wanted.
  # The message is deliberately free of quotes and apostrophes. It is interpolated into a
  # task exec INSIDE double quotes ("''${cfg.toolchainBin}"/copyroom status), so a `"` ends
  # that string early and a `'` opens an unterminated one — the generated script then dies
  # with `unexpected EOF while looking for matching`, naming neither the task nor the cause.
  # An end-to-end fixture caught this; no grep-level test could.
  storeBinExpr = "\${REPOMAN_TOOLCHAIN_BIN:?repoman: REPOMAN_TOOLCHAIN_BIN is unset - import the vendomat toolchain module}";
in
{
  imports = [
    ./managers/testee.nix
    ./managers/copyroom.nix
    ./managers/gitman.nix   # contributes a Rust/maturin toolchain when "git" is selected,
                            # to build the unpublished pyjutsu native extension — see SPIKE.md
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

    # D1: shell expression for the store closure's bin dir. Manager modules
    # interpolate it into task execs: "''${cfg.toolchainBin}"/gitman status.
    toolchainBin = lib.mkOption {
      type = lib.types.str;
      internal = true;
      readOnly = true;
      description = ''
        Shell expression (NOT a nix path) for the bin dir holding the shared manager
        commands. Manager modules interpolate it into task execs:
        "''${cfg.toolchainBin}"/gitman status.

        It is $REPOMAN_TOOLCHAIN_BIN, and an unset value fails the task.
      '';
      default = storeBinExpr;
    };

  };

  config = lib.mkMerge [
    { _module.args.repomanManagers = managerRoster; }
    (lib.mkIf cfg.enable {
    # Tell the `repoman` CLI which managers are wired in (it reads this to know
    # which sub-doctors / sub-status commands to aggregate) and where skills go.
    env.REPOMAN_MANAGERS = lib.concatStringsSep " " managerRoster;
    # Project 039: `skillsDir` and `installSkills` were dead option surface — the
    # 2026-09-15 measurement found zero of twenty-three importing repositories set
    # either. The path itself stays the family's agent-files convention.
    env.REPOMAN_SKILLS_DIR = ".agents/skills";

    # Verify the shared toolchain, then generate this repo's lifecycle router skill.
    scripts.repoman-sync = {
      description = "Verify the shared toolchain, then generate this repo's lifecycle router skill.";
      exec = ''exec ${pkgs.bash}/bin/bash ${./scripts/repoman-sync.sh} "$@"'';
    };

    enterShell = ''
      # Consumer venv bin. devenv's interactive shell prepends this itself, but
      # `devenv tasks run` does NOT — its PATH lacks the venv, so a task that shells
      # out to a venv console script (e.g. testee's `lint-imports` arch test) fails.
      # Tasks DO run this enterShell block (PROGRESS §0.2), so prepending here is a
      # no-op for the shell and fixes tasks. testee stays a per-repo uv dependency.
      export PATH="${config.devenv.state}/venv/bin:$PATH"
      # Vendomat exports the store closure. Report a
      # missing or empty closure, never abort — nothing in the closure may sit on the
      # shell-entry critical path without a degrade (gitman project 32 / G3: a broken
      # vendor-status took loci-core's devenv shell down entirely). Tasks still fail
      # actionably at the point of use, via the `:?` in `repoman.toolchainBin`.
      if [ -n "''${REPOMAN_TOOLCHAIN_BIN:-}" ]; then
        export PATH="$REPOMAN_TOOLCHAIN_BIN:$PATH"
        if [ ! -x "$REPOMAN_TOOLCHAIN_BIN/repoman" ]; then
          echo "RepoMan: shared command closure has no repoman ($REPOMAN_TOOLCHAIN_BIN)." >&2
        fi
      else
        echo "RepoMan: REPOMAN_TOOLCHAIN_BIN is unset; import vendomat's toolchain module." >&2
      fi
      if [ -t 1 ]; then
        echo "RepoMan: managers = ${lib.concatStringsSep " " managerRoster}"
      fi
    '';
    })
  ];
}
