# 02 — devman module (superseded devenv-literacy integration)

> **STATUS: SUPERSEDED (2026-08-03).** The static asset integration described below
> shipped in `8f95b90`, then was intentionally removed by `59d4b11` when the family
> adopted the agent-files ownership convention. Shared devenv literacy now lives in
> the `template-py` genome and is converged by `copyroom update`; RepoMan generates
> only its lifecycle router and performs ownership linting. The actual devman
> automation plane remains a separate devenv input/module.
>
> The material below is retained as a historical record. Its paths, commands, and
> conclusions describe the former implementation and are not an execution plan.

Brainstorm + plan for **devman**: a subsystem **inside the repoman repo** (not a separate
repo) that ships the devenv-literacy assets — agent **skills**, a distilled **documentation
export**, and **articles/recipes** — that make Claude Code agents use `devenv.sh`-managed repos
correctly.

## Why it lives here

devman and RepoMan are always used together: RepoMan is the conductor that composes the `*man`
doers; devman is the **substrate** that teaches agents how to operate the devenv shell those
doers live in. Folding devman into this repo (rather than a standalone input) means:

- **One import, one sync.** Consumers already import repoman; the devenv-literacy skills install
  alongside the generated entrypoint skill via `repoman-sync` — no second `flake: false` input,
  no second sync script.
- **One lint.** RepoMan's `doctor` self-check (`src/repoman/checks.py`) already verifies installed
  skills and the deferral-footer discipline. devman's "are the literacy skills installed and
  current?" check is a natural extension of it, not a separate `devman doctor`.
- **One narrative seam.** The RepoMan entrypoint skill owns *lifecycle ordering*; the devman
  skills own *devenv mechanics*; they're co-installed and cross-link cleanly.

## The problem in one sentence

Agents dropped into a devenv repo reliably do the wrong thing — run bare `python`/`pytest`/`uv`
instead of `devenv shell -- …`, edit a module and wonder why nothing changed (lock/eval cache),
pin a Python version without the `nixpkgs-python` input, forget `flake: false` on a module
import — and there is **no single place that teaches the rules**. devman is that place.

## Read

1. `CONCEPT.md` — what devman is, its form as a repoman subsystem, and how it wires in.
2. `CONTENT_INVENTORY.md` — the concrete first set of skills, doc exports, and articles to ship.

## Status

**SHIPPED** — see the note at the top of this file for where the code lives and how
it's wired. The original brainstorm questions are resolved (name `devman`, warn-level
self-check, hook surface deferred).
