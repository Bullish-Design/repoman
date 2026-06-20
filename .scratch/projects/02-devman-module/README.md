# 02 — devman module (devenv-literacy layer)

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

Brainstorm. Scope and form are settling toward "a repoman subsystem"; the content set and the
exact wiring (asset layout, sync step, self-check extension) are the things to lock before an
implementation project.
