# AGENTS.md — project instructions

`CLAUDE.md` is a symlink to this canonical instructions file.

## What this project is

RepoMan is the devenv meta-module and router generator for repositories that use
the *man family. It wires three managers — `copy`, `git`, and `test` — and
gives agents one generated front door. The roster stays three: `copy`, `git`,
and `test`. Devman, vendomat, and shellij belong to the automation plane,
Nix layer, and terminal respectively; they are not lifecycle managers.

The manager keys are not phase names. The lifecycle has three ordered phases:
`change`, `verify`, and `integrate`. Birth and convergence (copyroom) are an
unordered activity. Two laws apply: verify before you integrate, and never
integrate on red.

RepoMan writes exactly one file, the router. Devman's central overlay owns
`.agents/`. The per-skill pool links are hand-authored, tracked content in
`~/.config/devman`: one `ln -s` per skill. `devman-link reconcile` creates only
the machine-local views, such as `.agents`.

## Python baseline

**Python baseline: 3.13.** Every first-party CLI, the shared toolchain and every
devenv target CPython 3.13. `pyjutsu` ships `cp313-abi3`, which loads on 3.13 and
forward and **cannot** load on 3.12 — measured:
`ImportError: _pyjutsu.abi3.so: undefined symbol: Py_GetConstantBorrowed`.

## Working here

```bash
devenv shell                     # enter the pinned environment
repoman-sync                     # generate the router skill
devenv tasks run -v base:check   # repoman:lint — must be green before a PR
devenv tasks run -v base:test    # repoman:test
```

## Where things live

- `src/` — the RepoMan Python package: the router generator and the
  three-manager registry.
- `modules/` — the devenv meta-module repositories link in.
- `tests/` — the test suite `base:test` runs.

Deeper detail belongs in `docs/`, not here.

## Writing

Write in Simplified Technical English. See the
[writing skill](.agents/skills/writing/SKILL.md). Keep this file specific to
RepoMan.
