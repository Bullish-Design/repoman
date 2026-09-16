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
#   repoman.managers = [ "copy" "git" "test" ];
#
# Each manager's wiring lives in ./managers/<name>.nix and gates itself on
# membership in `repoman.managers`. Imports cannot depend on `config`, so we
# import every manager module statically and let each one decide whether to
# activate — the standard devenv/NixOS module idiom.
#
# `repoman.managers` selects which manager tasks/skills are WIRED — it no longer
# gates toolchain installation (project 12): the pure-CLI managers live in a
# single system-wide toolchain venv ($REPOMAN_TOOLCHAIN_VENV, populated by
# `repoman-sync --machine` from the machine repoman.lock) regardless of any one
# repo's roster. testee is the exception: it runs inside the consumer's code, so
# it is a per-repo uv dev dependency declared in pyproject.toml.
{ pkgs, lib, config, inputs ? {}, ... }:

let
  cfg = config.repoman;

  allManagers = [ "copy" "git" "test" "doc" ];

  # One list, shared by the manifest validator and the `cliProvider` option's enum,
  # so a value the manifest accepts is never one the option then rejects.
  allCliProviders = [ "venv" "store" ];

  # Project 039: the roster moves from a devenv.nix option to a tracked repo
  # manifest, `.repoman/project.toml`, modelled on
  # `devman/src/devman_contract/manifest.py`'s discipline — fixed field set,
  # unknown fields rejected outright, values checked against the same grammar
  # the option already enforces. Absent file means the default roster, so 15 of
  # 23 known consumers need no file at all.
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
    else if rawManifest ? cliProvider && !(builtins.elem rawManifest.cliProvider allCliProviders) then
      throw ("repoman: " + manifestPath + " field 'cliProvider' has unsupported value "
        + toString rawManifest.cliProvider + "; valid values are "
        + lib.concatStringsSep ", " allCliProviders)
    else
      rawManifest;

  # D1: a SHELL expression, expanded by bash at task/shell time — never a nix-eval-time
  # absolute path. Reading $HOME via the nix builtin would bake one user's path into the
  # eval result and yield "/repoman/venv" wherever HOME is unset (CI, nix-daemon).
  toolchainVenvExpr = "\${REPOMAN_TOOLCHAIN_VENV:-\${XDG_DATA_HOME:-$HOME/.local/share}/repoman/venv}";

  # Face D seam. Under "store" the commands are a Nix closure and Vendomat exports its
  # bin dir; there is no path to guess, so an unset variable must FAIL the task rather
  # than expand to "" and exec "/gitman" — a confident wrong answer. `:?` says so at the
  # point of use, which is the only place that knows which command was wanted.
  # The message is deliberately free of quotes and apostrophes. It is interpolated into a
  # task exec INSIDE double quotes ("''${cfg.toolchainBin}"/copyroom status), so a `"` ends
  # that string early and a `'` opens an unterminated one — the generated script then dies
  # with `unexpected EOF while looking for matching`, naming neither the task nor the cause.
  # An end-to-end fixture caught this; no grep-level test could.
  storeBinExpr = "\${REPOMAN_TOOLCHAIN_BIN:?repoman: cliProvider is store but REPOMAN_TOOLCHAIN_BIN is unset - import the vendomat toolchain module}";

  cliBinExpr = if cfg.cliProvider == "store" then storeBinExpr else "${toolchainVenvExpr}/bin";
in
{
  imports = [
    ./managers/testee.nix
    ./managers/copyroom.nix
    ./managers/gitman.nix   # contributes a Rust/maturin toolchain when "git" is selected,
                            # to build the unpublished pyjutsu native extension — see SPIKE.md
    ./managers/docman.nix   # activates when "doc" is selected (pure-Python; toolchain in docman's module)
  ]
  # shellij is NOT a roster manager: no `repoman.managers` entry, no repoman.session.*
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

    managers = lib.mkOption {
      type = lib.types.listOf (lib.types.enum allManagers);
      # Project 039: the default resolves from `.repoman/project.toml` when that
      # file is present, else the pre-039 default roster. An explicit
      # `repoman.managers = [...]` in a consumer's devenv.nix still wins over
      # both — the option is kept as a compatibility fallback for one release,
      # exactly as `devman/modules/link.nix` keeps `config.devman.project` as a
      # fallback ahead of its own manifest. Do not remove this fallback because
      # one canary repository migrates cleanly.
      default =
        if manifest ? managers then manifest.managers else [ "copy" "git" "test" ];
      description = ''
        Which managers' tasks/skills are WIRED into this repo. Does NOT gate
        toolchain installation (project 12): the shared toolchain venv holds every
        pure-CLI manager regardless; testee is a per-repo uv dev dependency.

        Resolved from `.repoman/project.toml` (`managers = [...]`) when that file
        exists; this option is the pre-039 compatibility fallback, consulted only
        when the manifest is absent or when a consumer sets this explicitly.
      '';
    };

    # CONCEPT 03 4.1: ONE command-resolution contract, so the manager modules never
    # name a venv directly.
    #
    # The default was "venv" until phase 4 of the shared-command-closure migration
    # (devman 023-toolchain), because a default of "store" would have migrated every
    # consumer before the roster was complete. The roster is now complete: repoman,
    # copyroom, docman, gitman and templateer all build as Nix applications at 3.13
    # and compose into repoman-toolchain-core.
    #
    # It is "store" now because a default of "venv" left templateer with TWO owners
    # — the shelf venv inside a devenv, the store closure outside it — and PATH order
    # decided which one a command got. That ambiguity is the defect 023-toolchain
    # exists to remove, so the seam must default to the single owner.
    #
    # "venv" stays first-class, and remains the answer for a consumer that has not
    # imported vendomat's toolchain module: the store branch of `enterShell` below
    # names it in the message it prints when REPOMAN_TOOLCHAIN_BIN is unset.
    # Project 039: like `managers`, this resolves from `.repoman/project.toml` first.
    # It MUST have a manifest home. The ten repositories that decline the store
    # toolchain carry the opt-out as `repoman.cliProvider = "venv"` in devenv.nix,
    # and that option is the compatibility fallback slated for removal. Without a
    # manifest field, removing the fallback would flip all ten onto a store closure
    # they never imported. Measured 2026-09-16: llgym, nix-secrets and
    # image-gen-pipeline already sit in that exact state — `enterShell` warns, the
    # roster still populates, and NO manager command is on PATH. A repo reports
    # healthy while every tool it names is missing, so the fallback needs a
    # successor before it is withdrawn, not after.
    cliProvider = lib.mkOption {
      type = lib.types.enum allCliProviders;
      default =
        if manifest ? cliProvider then manifest.cliProvider else "store";
      description = ''
        How the shared manager commands are materialised.

        Resolved from `.repoman/project.toml` (`cliProvider = "venv"`) when that
        file sets it; this option is the pre-039 compatibility fallback, consulted
        only when the manifest is absent or when a consumer sets this explicitly.

        "store" — a pinned Nix closure built by Vendomat, exported as
                  $REPOMAN_TOOLCHAIN_BIN. The consumer venv holds no manager at all.
                  The default. Requires vendomat's toolchain module.
        "venv"  — the system-wide toolchain venv, filled by `repoman-sync --machine`
                  from the machine repoman.lock. The pre-phase-4 behaviour.
      '';
    };

    # D1: shell expression for the system-wide toolchain venv's bin dir. Manager modules
    # interpolate it into task execs: "''${cfg.toolchainBin}"/gitman status. Honours
    # $REPOMAN_TOOLCHAIN_VENV, else $XDG_DATA_HOME/repoman/venv, else ~/.local/share/repoman/venv.
    # Populated by `repoman-sync --machine`. NOT a nix path — bash expands it at runtime.
    toolchainBin = lib.mkOption {
      type = lib.types.str;
      internal = true;
      readOnly = true;
      default = cliBinExpr;
      description = ''
        Shell expression (NOT a nix path) for the bin dir holding the shared manager
        commands. Manager modules interpolate it into task execs:
        "''${cfg.toolchainBin}"/gitman status.

        Under `cliProvider = "venv"` it honours $REPOMAN_TOOLCHAIN_VENV, else
        $XDG_DATA_HOME/repoman/venv, else ~/.local/share/repoman/venv — populated by
        `repoman-sync --machine`. Under `cliProvider = "store"` it is
        $REPOMAN_TOOLCHAIN_BIN, and an unset value fails the task.
      '';
    };

  };

  config = lib.mkIf cfg.enable {
    # Tell the `repoman` CLI which managers are wired in (it reads this to know
    # which sub-doctors / sub-status commands to aggregate) and where skills go.
    env.REPOMAN_MANAGERS = lib.concatStringsSep " " cfg.managers;
    # Project 039: `skillsDir` and `installSkills` were dead option surface — the
    # 2026-09-15 measurement found zero of twenty-three importing repositories set
    # either. The path itself stays the family's agent-files convention.
    env.REPOMAN_SKILLS_DIR = ".agents/skills";

    # Verify the shared toolchain, then generate this repo's lifecycle router skill.
    scripts.repoman-sync = {
      description = "Verify the shared toolchain, then generate this repo's lifecycle router skill.";
      exec = ''exec ${pkgs.bash}/bin/bash ${./scripts/repoman-sync.sh} "$@"'';
    };

    # (This whole block is inside `config = lib.mkIf cfg.enable`, so no inner
    # enable guard is needed — the optionalString below only pads a constant.)
    enterShell = ''
      # Tell the `repoman` CLI which provider is active, so checks.py resolves commands
      # the same way the nix tasks do. Disagreement here is the failure mode the
      # provider seam exists to remove.
      export REPOMAN_CLI_PROVIDER="${cfg.cliProvider}"
      # Consumer venv bin. devenv's interactive shell prepends this itself, but
      # `devenv tasks run` does NOT — its PATH lacks the venv, so a task that shells
      # out to a venv console script (e.g. testee's `lint-imports` arch test) fails.
      # Tasks DO run this enterShell block (PROGRESS §0.2), so prepending here is a
      # no-op for the shell and fixes tasks. Needed under both providers: testee
      # stays a per-repo uv dependency either way.
      export PATH="${config.devenv.state}/venv/bin:$PATH"
    ''
    + lib.optionalString (cfg.cliProvider == "venv") ''
      export REPOMAN_TOOLCHAIN_VENV="${toolchainVenvExpr}"
      # ORDER IS LOAD-BEARING. This prepend must land AFTER the consumer venv one
      # above, because each line prepends and the toolchain must end up FIRST — a
      # stale pre-migration copy of a manager CLI left in .devenv/state/venv/bin
      # must not shadow the shared toolchain. Getting this backwards is silent:
      # `repoman doctor` and `devenv tasks run` would resolve different binaries
      # (doctor's installed:<key> flags exactly that).
      export PATH="$REPOMAN_TOOLCHAIN_VENV/bin:$PATH"
      if [ ! -x "$REPOMAN_TOOLCHAIN_VENV/bin/repoman" ]; then
        echo "RepoMan: shared toolchain not bootstrapped ($REPOMAN_TOOLCHAIN_VENV)." >&2
        echo "RepoMan:   cd <repoman checkout> && devenv shell -- repoman-sync --machine" >&2
      fi
    ''
    + lib.optionalString (cfg.cliProvider == "store") ''
      # Face D: Vendomat's toolchain module exports REPOMAN_TOOLCHAIN_BIN. REPORT a
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
        echo "RepoMan: cliProvider is \"store\" but REPOMAN_TOOLCHAIN_BIN is unset." >&2
        echo "RepoMan:   import vendomat's toolchain module, or set repoman.cliProvider = \"venv\"." >&2
      fi
    ''
    + ''
      if [ -t 1 ]; then
        echo "RepoMan: managers = ${lib.concatStringsSep " " cfg.managers}"
      fi
    '';
  };
}
