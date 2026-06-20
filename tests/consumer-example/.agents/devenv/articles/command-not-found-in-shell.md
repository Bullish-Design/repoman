# "command not found" inside the devenv shell — how PATH is assembled

You're inside `devenv shell`, you type a command, and it's not found. PATH in a devenv shell is
assembled from three distinct sources; the fix depends on which one *should* provide your command.

## The three sources

1. **Nix `packages`** — tools declared in `devenv.nix` (`packages = [ pkgs.ripgrep ];`) and tools
   contributed by enabled languages/modules. If a system tool is missing, it usually needs to be
   added here, not installed globally.

2. **The language venv** — e.g. Python's `languages.python.venv`. Console scripts from installed
   packages (think `pytest`, your project's own entry points) live here. **They only appear after
   the deps are synced** — a fresh venv has the interpreter but not the packages. See
   `the-lock-cache-loop.md`'s sibling concern in the `languages-python.md` doc.

3. **`scripts`** — every `scripts.<name>` becomes `<name>` on PATH. If you expected a repo command
   (like `repoman-sync`) and it's missing, the script may not be defined, or you're not in the shell.

## Diagnose

- **Not in the shell at all?** A bare command in your outer terminal won't see any of the above.
  Re-run as `devenv shell -- <cmd>` (the `devenv-run-commands` skill).
- **A Python console script (e.g. `pytest`, your CLI) missing?** Deps aren't synced:
  `devenv shell -- uv sync --all-extras` or `repoman-sync` (the `devenv-python-venv` skill).
- **A system tool missing?** Add it to `packages` in `devenv.nix`, then refresh
  (`devenv-module-edits`).
- **A repo `scripts.<name>` missing?** Confirm it's defined in `devenv.nix`; if you just added it,
  the eval cache may be stale → `lock-and-cache.md`.

## Why not just install it globally

A globally-installed tool defeats the point: it isn't pinned, it isn't deterministic, and it won't
exist in CI or on another machine. Put it in `packages` (or the venv) so the environment stays
reproducible — the principle behind `ci-inside-devenv.md`.

For *when* to stop and fix vs. proceed, see the `repoman` skill.
