# AGENTS.md — project instructions

> **Seed.** The `my-ai` personal layer wrote this file because this repo had
> none. It is now **the repo's** file: edit it freely, and no `my-ai` update will
> ever overwrite it (`_skip_if_exists`). Every agent tool reads it through the
> `CLAUDE.md` symlink.

## What this project is

RepoMan is the devenv meta-module and router generator for repositories that use
the *man family. It wires the four lifecycle phases — `copy`, `git`, `test`, and
`doc` — and gives agents one generated front door. The roster stays four: devman,
vendomat, and shellij belong to the plane, Nix layer, and terminal, not to the
lifecycle roster. RepoMan writes exactly one file, the router; copyroom ships or
the genome converges every other skill.

## Python baseline

**Python baseline: 3.13.** Every first-party CLI, the shared toolchain and every
devenv target CPython 3.13. `pyjutsu` ships `cp313-abi3`, which loads on 3.13 and
forward and **cannot** load on 3.12 — measured:
`ImportError: _pyjutsu.abi3.so: undefined symbol: Py_GetConstantBorrowed`.

## Working here

```bash
devenv shell                     # enter the pinned environment
repoman-sync                     # verify toolchain + install agent skills
```

_Add the build / test / lint commands, and the gate that must be green before a
PR._

## Where things live

_The two or three directories a newcomer actually needs. Deeper detail belongs in
`docs/`, not here._

## The standing configuration

The user's cross-repo law — devenv discipline, the exit-code contract, manager
routing, the agent-files convention — lives in
[`.agents/skills/my-ai/SKILL.md`](.agents/skills/my-ai/SKILL.md), delivered by
the `my-ai` personal layer. **Read it first.** Keep this file for what is true of
*this* project only.

```bash
copyroom layer list              # which template layers manage this repo
copyroom update --layer my-ai    # converge the personal layer
copyroom agent-files check       # conformance report
```
