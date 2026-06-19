# Guide 1 — Wire gitman + prove nix-level toolchains in the meta-module

**Goal:** add `git` (gitman) as the third manager, and in doing so prove the meta-module
can contribute a **system toolchain** (Rust + maturin) so a manager whose Python package
needs a native build installs cleanly. Every manager so far (testee, copyroom) was a pure
pip install; gitman is the first that isn't.

## Why gitman is the hard case

- `gitman` depends on **`pyjutsu`**, an unpublished native extension (jj-lib via PyO3),
  built from the sibling checkout `../Pyjutsu` with **maturin + a Rust toolchain**.
- gitman's own `devenv.nix` provides exactly this: `pkgs.git`, `pkgs.uv`, `pkgs.maturin`,
  `languages.rust.enable = true`, python 3.13 venv. (No `jj` CLI — pyjutsu is in-process.)
- gitman's `pyproject.toml` resolves pyjutsu via `[tool.uv.sources] pyjutsu = { path =
  "../Pyjutsu", editable = true }`. **This only works in uv project/workspace mode.**

### The key subtlety

`repoman-sync` installs with `uv pip install --editable <path>` (pip mode), which **ignores
`[tool.uv.sources]`**. So `uv pip install --editable ../gitman` alone will fail to find
`pyjutsu` (it's not on PyPI). Fix: **pyjutsu must be its own `repoman.lock` entry**, so
sync installs both editable in one command and uv satisfies gitman's `pyjutsu` requirement
from the editable build.

## Changes

### 1. New manager module `modules/managers/gitman.nix`

Mirror `testee.nix`/`copyroom.nix`, but this one also contributes the **toolchain**
(`config` keys merge across modules, so adding `languages.rust` / `packages` here is fine):

```nix
# RepoMan manager wiring: gitman (version control: jujutsu via pyjutsu + colocated git).
#
# Imported unconditionally by ../devenv.nix; activates only when "git" is in
# `repoman.managers`. Unlike the pure-Python managers, gitman needs a NATIVE build:
# pyjutsu (jj-lib via PyO3) compiles with maturin + a Rust toolchain, which this module
# contributes to the consumer's devenv so `repoman-sync`'s uv build succeeds.
{ pkgs, lib, config, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "git" cfg.managers;
  venvBin = "${config.devenv.state}/venv/bin";
in
{
  config = lib.mkIf enabled {
    # System toolchain for building pyjutsu's native extension.
    packages = [ pkgs.git pkgs.maturin ];
    languages.rust.enable = true;

    tasks = {
      "repoman:vc:status".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/gitman status'';
    };
  };
}
```

> `git` is likely already present (testee/base), but devenv merges `packages` lists, so
> listing it again is harmless. `languages.rust.enable = true` matches gitman's own
> devenv (rolling nixpkgs' stable rustc satisfies jj-lib 0.38's Rust ≥ 1.89 / edition 2024).

### 2. Register the module — `modules/devenv.nix`

Uncomment the gitman import:

```nix
  imports = [
    ./managers/testee.nix
    ./managers/copyroom.nix
    ./managers/gitman.nix
  ];
```

### 3. Lock entries — `tests/consumer-example/repoman.lock`

Add **both** gitman and pyjutsu (pyjutsu first or second — uv resolves together):

```toml
[managers.git]
package = "gitman"
source = "path:/home/andrew/Documents/Projects/gitman"

# gitman's native dependency. Must be an explicit entry: `uv pip install` ignores
# gitman's [tool.uv.sources], so pyjutsu won't resolve otherwise. Built via maturin
# + the Rust toolchain the gitman manager module adds to the devenv.
[managers.git-pyjutsu]
package = "pyjutsu"
source = "path:/home/andrew/Documents/Projects/Pyjutsu"
```

> **Decision — how to model the native dep.** A `git-pyjutsu` pseudo-entry keyed off the
> manager is the cheapest path and keeps it visible in the lock. Cleaner alternatives,
> pick per taste:
> - a dedicated `[deps.*]` table the sync script always installs alongside its manager, or
> - teach `repoman-sync` that a manager entry may carry `extra_sources = [...]`.
>   If you do this, also teach `src/repoman/registry.py` so `repoman` doesn't try to run
>   a `pyjutsu` "manager". With the `git-pyjutsu` pseudo-entry approach, **only** add it to
>   the lock — do **not** add it to `repoman.managers`, so the CLI never treats it as a
>   manager (the CLI reads `REPOMAN_MANAGERS`, not the lock).

### 4. Enable it — `tests/consumer-example/devenv.nix`

```nix
  repoman.managers = [ "copy" "git" "test" ];
```

### 5. Registry (already correct)

`src/repoman/registry.py` already has the `git` entry with `doctor=["doctor"]`,
`status=["status"]` and a `route_when`. gitman ships a real `doctor`, so nothing to change.

### 6. `repoman-sync` (works as-is, but confirm)

The script reads `managers` from `$REPOMAN_MANAGERS` and pulls the matching `[managers.<key>]`
entries. With the `git-pyjutsu` pseudo-entry, the manager key is `git` — but the lock key is
`git-pyjutsu`. The current `target()` loop iterates `data["managers"][key] for key in
$REPOMAN_MANAGERS`, so it would **miss** `git-pyjutsu`. Two fixes (choose one):

- **Simplest:** in `repoman-sync.sh`, after collecting selected managers, also include any
  lock entry whose key starts with `<selected>-` (e.g. `git-*`). One small change in the
  embedded Python:
  ```python
  for key, entry in data.get("managers", {}).items():
      base = key.split("-", 1)[0]
      if base in managers:
          out.append(target(entry))
  ```
  (replaces the explicit `for key in managers` loop; de-dupe if needed.)
- **Or** adopt the `extra_sources` model from step 3's decision note.

## Verification

```bash
cd tests/consumer-example
rm -f devenv.lock && rm -rf .devenv          # module + env changed (rust toolchain)
devenv shell -- repoman-sync                 # builds pyjutsu (slow: native compile) + gitman
devenv shell -- repoman managers             # lists copy, git, test
devenv shell -- bash -c 'repoman doctor; echo exit=$?'   # runs gitman doctor + testee doctor
devenv shell -- gitman --help                # gitman CLI present
```

Expected: `repoman managers` shows three rows; `repoman doctor` runs gitman's and testee's
doctors (copyroom skipped until guide for copyroom doctor lands) and aggregates the exit code.

> **gitman init caveat.** `gitman status`/full workflow expect an initialized repo
> (`jj git init --colocate` + `gitman init` freezes trunk). For roster wiring we only need
> the CLI present and `gitman doctor` to run. If `gitman doctor` reports "not initialized",
> that's expected in the bare consumer — note it; don't try to fully init gitman here.

## Risks

| Risk | Mitigation |
|---|---|
| pyjutsu native build is slow / first-run heavy | Run `repoman-sync` in the background (see SPIKE.md pattern); document expected build time. |
| Rust toolchain bloats every consumer | It's gated on `"git"` ∈ managers — repos without gitman never pull Rust. This is the whole point: managers contribute their own toolchains, conditionally. |
| `uv pip install` still can't find pyjutsu | Confirm the `git-pyjutsu` lock entry + the sync-loop change (step 6) actually pass `--editable /Pyjutsu`. Check the printed install plan. |
| Pyjutsu path differs on another machine | `path:` sources are dev-only; fleet use switches these to `git+…@ref` (and pyjutsu becomes a published wheel per gitman's roadmap). |

## Implementation notes (verified)

Implemented as written, with these confirmations/divergences:

- **Python 3.13 was free.** gitman requires `>=3.13`; the consumer's rolling nixpkgs
  already resolves Python 3.13.13, so no `languages.python.version` pin (and no
  `nixpkgs-python` input) was needed. The `uv pip install` of gitman succeeded against the
  default interpreter.
- **Sync-loop fix (step 6) — used the "simplest" option.** `repoman-sync.sh` now iterates
  all lock `managers` entries and includes any whose base (`key.split("-",1)[0]`) is in
  `$REPOMAN_MANAGERS`, so `git-pyjutsu` is installed alongside `git`. `git-pyjutsu` is
  **not** in `repoman.managers`, so the CLI never treats it as a manager. The self-check
  (`checks.py`) already tolerates the pseudo-entry via the same `split("-",1)[0]` rule.
- **Native build cost:** first `repoman-sync` compiled pyjutsu in ≈7m26s (uv "Prepared 5
  packages in 7m 26s"); subsequent runs reuse the build. Ran it in the background per the
  SPIKE pattern.
- **`repoman doctor` exit in the bare consumer is 2**, sourced from gitman's *own* doctor
  ("XX colocated — not a colocated jj repo"), not from RepoMan's self-check (all OK). This
  is the documented uninitialized-gitman caveat; the aggregation is correct.

## Outcome / what this proves

The meta-module is not limited to venv pip installs: a manager module can contribute
**system packages and language toolchains** to the consumer devenv, conditionally on being
selected. This is the last unproven architectural axis of the roster. Update
`SPIKE.md` (the "gitman deferred / native toolchains" note) to "done", and `CONCEPT.md §6`
to record that managers may contribute nix-level provisioning, not just venv installs.
