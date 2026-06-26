# CONTEXT — repoman's current command / manager / wiring flow

A map of how repoman is wired today, so the fleet feature slots in correctly. All paths
relative to `/home/andrew/Documents/Projects/repoman/`.

## Two layers (CONCEPT.md §6)

```
Nix meta-module (the consumer-facing surface)        Python conductor (thin)
  modules/devenv.nix      options.repoman.*            src/repoman/cli.py     Typer app
    ├ imports each managers/<m>.nix (gated)            src/repoman/registry.py  *man roster
    ├ env.REPOMAN_MANAGERS = "<keys>"  ───────────────► read by cli._enabled()
    ├ env.REPOMAN_SKILLS_DIR / _DOCS_DIR               src/repoman/aggregate.py subprocess+exit
    └ scripts.repoman-sync → scripts/repoman-sync.sh   src/repoman/checks.py    self-check
  modules/managers/<m>.nix  per-manager task wiring     src/repoman/skills.py    entrypoint skill
  modules/scripts/repoman-sync.sh  venv toolchain sync  src/repoman/devman/      SUBSYSTEM (no CLI)
```

## How a `*man` MANAGER is registered (the EXTERNAL-tool path)

A manager = an external `*man` console script repoman aggregates. Three coordinated touch points:

1. **`src/repoman/registry.py`** — add a `Manager(...)` to `REGISTRY` keyed by short key
   (`"git"`, `"test"`, …): `command` (console script on PATH), `tier`, `doctor`/`status`
   args, `summary`, optional `nix_input`. `DEFAULT_MANAGERS = ["copy","git","test"]`.
2. **`modules/devenv.nix`** — add the key to `allManagers` (line 26, drives the
   `repoman.managers` enum) and add `./managers/<key>.nix` to the `imports` list (line 29).
3. **`modules/managers/<key>.nix`** — wiring module, imported unconditionally, gates its
   `config` on `cfg.enable && builtins.elem "<key>" cfg.managers`; contributes tasks
   (`venvBin = "${config.devenv.state}/venv/bin"`) and, if needed, system packages /
   `languages.*` (gitman adds Rust/maturin) or a presence-gated approach-B import (docman).

At runtime: `cli._enabled()` reads `$REPOMAN_MANAGERS` → looks each up in `REGISTRY` →
`doctor`/`status` shell out per manager via `aggregate.run_sub` → `worst_exit` collapses
to one `0/1/2/3` code.

## How a SUBSYSTEM is folded in (the INTERNAL path — what fleet should follow)

`src/repoman/devman/` is repoman-owned logic with **NO registry entry** and **no external
CLI** (`devman/__init__.py`: *"shipped as a subsystem of repoman … It has no CLI of its own"*).
It plugs in via:
- a subpackage `devman/{__init__,assets,check,install}.py`;
- `cli.py` imports from it (`from .devman.check import devman_checks`, line ~16) and folds
  its `SelfCheck`s into `repoman doctor` (`self_checks += devman_checks(...)`, cli.py:65);
- `install-skills` calls its installer (`install_devman(...)`, cli.py:104).

**Fleet sync is this kind of thing** — repoman runs the git clone/fetch itself; it is not an
external binary to aggregate. So: `src/repoman/fleet/` subpackage + a new `cli.py` subcommand
+ a `modules/managers/fleet.nix` task wire. It may take a `"fleet"` enum key for nix opt-in
gating WITHOUT a `registry.py` entry (decide; see KICKOFF open question 4).

## The two similarly-named, UNRELATED files

| File | What it is |
|---|---|
| `modules/scripts/repoman-sync.sh` | reads **`repoman.lock`**, `uv pip install`s the selected managers' Python pkgs **into the devenv venv**, runs `repoman install-skills`. Toolchain sync. **Not** repo cloning. |
| `repos.toml` (NEW, this project) | the **fleet manifest** (name/url/path) the new `repoman fleet-sync` reads to clone/fetch the Projects repo set. |
| `repoman.lock` | TOML pinning repoman + each manager's pip source (`checks.py:_load_lock`). Unrelated to `repos.toml`. |

Keep the new fleet command named `fleet-sync` (NOT `sync`) to avoid colliding with the
existing `repoman-sync.sh` toolchain sync.

## Exit-code contract (reuse it)

`0` ok · `1` domain decision needed · `2` infra/config · `3` invalid usage. Implemented by
`aggregate.worst_exit` (treats unavailable/unknown as `2`). Fleet sync maps:
clone/ff/no-op → 0, dirty/diverged → 1, git-missing/network/auth → 2, bad `repos.toml` → 3.
