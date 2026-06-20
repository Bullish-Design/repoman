# shell — entering and using the devenv shell

## The rule

Every in-repo command runs inside the shell, so it gets the repo's pinned PATH, env vars, and
determinism settings:

    devenv shell -- <command>      # non-interactive, one command
    devenv shell                   # interactive subshell

A bare `python`/`pytest`/`uv`/`ruff` outside the shell uses the system's, not the repo's, tools —
different versions, missing env, non-deterministic. (Enforced by the `devenv-run-commands` skill.)

## The env model

- `DEVENV_ROOT` — absolute path to the repo root (where `devenv.nix` lives).
- `DEVENV_STATE` — `.devenv/state`, scratch/state for the environment.
- PATH is assembled from: nix `packages`, the language venv (e.g. Python), and `scripts`. Order and
  assembly: see `command-not-found-in-shell.md`.
- `env.*` entries in `devenv.nix` are exported into the shell.

## enterShell / enterTest

- `enterShell` runs on shell entry. Guard any echo with `if [ -t 1 ]; then … fi` so captured
  (non-TTY) output isn't polluted.
- `enterTest` runs under `devenv test`.

## Refresh

When a change isn't reflected, the eval cache or lock is stale — `lock-and-cache.md`.
