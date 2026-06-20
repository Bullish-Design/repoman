# Authoring a manager module — the `*man` pattern

The `*man` family (copyroom, testee, gitman, docman) all share one devenv-module shape: an
options block, a gated `config` block, and a CLI put on PATH. This is the pattern to copy when
building a new manager.

## 1. Declare options, gated on selection

A manager module is imported **statically** (imports can't depend on `config`), so it must gate its
own activation on membership in some selection list:

    { lib, config, pkgs, ... }:
    let cfg = config.repoman; in
    {
      options.mymanager.enable = lib.mkEnableOption "mymanager";

      config = lib.mkIf (builtins.elem "mine" cfg.managers) {
        # …wiring only when this manager is selected…
      };
    }

This is the standard NixOS/devenv idiom: import every manager module, let each decide whether to
activate. (RepoMan's `modules/devenv.nix` imports its managers exactly this way.)

## 2. Put the CLI on PATH

Two routes:

- **From the venv** — the manager is a Python package pinned in `repoman.lock`; `repoman-sync`
  `uv pip install`s it so its console script lands on PATH. Local checkouts install `--editable` so
  code edits are picked up live.
- **From nix `packages`** — for a non-Python tool, add the derivation to `packages`.

## 3. Expose verbs through scripts/tasks, honoring the exit contract

Surface the manager's actions as `scripts` (plain) or `tasks` (ordered) — see
`scripts-tasks-processes.md` — and honor `0/1/2/3` so the conductor can aggregate exit codes
(`devenv-authoring` skill).

## 4. Export what the conductor reads

RepoMan discovers managers via `env.REPOMAN_MANAGERS` and installs skills under
`env.REPOMAN_SKILLS_DIR`. A new manager exports its own env/wiring the same way, and ships a
`SKILL.md` that **defers cross-phase ordering to the `repoman` skill** (the `docs/SKILLS.md`
contract). devman's own assets follow this exact discipline.

## 5. Pin it

Add the manager to `repoman.lock` so `repoman-sync` installs it and `repoman doctor` validates it
(a selected-but-absent manager is a self-check FAIL).

For where a new manager sits in the lifecycle, see the `repoman` skill and
`adopting-the-man-family.md`.
