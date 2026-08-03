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

Two install classes (project 12), picked by the `Manager.install` field in `repoman/registry.py`:

- **`"toolchain"` — the system-wide shared venv.** A pure-CLI manager (repoman/gitman/copyroom/
  docman) that never imports the consumer's code: pinned in the machine `repoman.lock` at the
  repoman checkout, installed once per machine by `repoman-sync --machine` into
  `$REPOMAN_TOOLCHAIN_VENV`, and prepended to every consumer's PATH. Local checkouts install
  `--editable` so code edits are picked up live.
- **`"uv"` — the consumer's uv graph.** A manager whose tools run *inside* the consumer's codebase
  (today: testee — pytest/ruff/ty import the app): declared in the consumer's `pyproject.toml`
  (`[dependency-groups] dev` + `[tool.uv.sources]`) and installed by `uv sync`. `repoman doctor`
  validates it with `uv:<key>`; the other class gets `lock:<key>`.

Either way the console script lands on PATH; the split is *where* it is installed and *who* the
doctor asks about it.

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

- **A `"toolchain"` manager** → add it to the MACHINE `repoman.lock` at the repoman checkout (not
  the consumer's) and set `install = "toolchain"` (the default). `repoman doctor` validates it
  with `lock:<key>` against the recorded manifest; a selected-but-absent manager is a self-check
  FAIL.
- **A `"uv"` manager** → declare it in each consumer's `pyproject.toml` and set
  `install = "uv"`; the doctor checks `uv:<key>` instead.

For where a new manager sits in the lifecycle, see the `repoman` skill and
`adopting-the-man-family.md`.
