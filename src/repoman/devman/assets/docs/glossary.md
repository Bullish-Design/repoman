# glossary — devenv terms an agent will hit

- **`DEVENV_ROOT`** — absolute path to the repo root (the directory containing `devenv.nix`). Many
  tools (including `repoman`) read this to locate the repo.
- **`DEVENV_STATE`** — the `.devenv/state` directory: scratch/state for the environment.
- **`.devenv/`** — the build output + **eval cache** directory. `rm -rf .devenv` forces a full
  re-evaluation. See `lock-and-cache.md`.
- **`devenv.nix`** — the environment definition (packages, languages, scripts, tasks, processes,
  env). Edited locally; eval-cached.
- **`devenv.yaml`** — inputs + imports. See `inputs-and-imports.md`.
- **`devenv.lock`** — pins every input to an exact revision. Re-lock with `rm -f devenv.lock` or
  `devenv update`.
- **eval cache** — devenv's memoised evaluation of the `.nix` files. Stale cache = "my edit did
  nothing." Refresh with `--refresh-eval-cache`.
- **`enterShell`** — shell-entry hook. Guard echoes with `if [ -t 1 ]`.
- **`enterTest`** — hook run by `devenv test`.
- **`scripts` / `tasks` / `processes`** — the three execution surfaces. See
  `scripts-tasks-processes.md`.
- **`devenv up`** — starts `processes` (daemons/servers), supervised, non-blocking.
- **`flake: false`** — marks an input as a plain source tree (a devenv module), not a flake. See
  `inputs-and-imports.md`.
- **`nixpkgs-python`** — the input required to pin `languages.python.version`.
- **exit contract** — `0` ok · `1` decision/finding · `2` infra/config · `3` usage.
