# SEED — issue + feature creation workflow helpers (new `*man`-family repos)

> Raw ask, captured before brainstorming. Open questions resolved in the
> AskUserQuestion round are appended below as the brainstorm anchor.

## The verbatim ask

> "I want to add specific repos for issue + feature creation workflow helpers,
> and add them to the repoman library family. I want to initially just make
> these agent skills, but it will give us the ability to add
> scripts/workflows/helpers/etc later on down the line."

## What this means (initial read)

- New sibling repo(s) under `~/Documents/Projects`, members of the `*man` /
  repoman family (naming + role conventions per the workspace `AGENTS.md`).
- Domain: helping with **issue creation** and **feature creation** workflows.
- **Phase 1 = agent skills only.** The repo scaffold is chosen so that
  scripts / workflows / a CLI / a devenv module can be added later without
  re-homing anything.

## Resolved decisions (clarifying rounds, 2026-06-30)

1. **One repo, two skills** (REVISED — see CONCEPT.md §1). Initially scoped as
   two repos; the design work showed the two helpers are ~90% one shared engine
   differing only by *profile*, and two repos would have needed a *third* shared-
   core lib. Collapsed to a single `*man` manager (**`foreman`**) exposing two
   agent skills (`issue` + `feature`) + `promote` over one package core.
2. **Full `*man` managers** — end-state is registry-wired into repoman like
   `copy`/`git`/`test` (devenv module + Typer CLI + skill). **Phase 1 ships
   agent skills only**; the rest is added later.
3. **Backends (both repos target all three):**
   - **Local task system** — `taskman` / tasknotes / taskdantic.
   - **Allium specs** — `allium-env` spec-driven agent workflow.
   - **Numbered project dirs** — the `.scratch/projects/NN-name` KICKOFF-packet
     convention (this very directory is an instance).
   - **Explicitly NOT GitHub Issues.**
   The issue-vs-feature distinction is **granularity / ceremony**, not which
   backend they write to (issue = small/reactive; feature = large/proactive).
4. **Composition, not reimplementation** — the new helpers are a thin
   workflow/orchestration layer ON TOP OF the existing siblings (`taskman`,
   `allium-env`, `fleetman`, `gitman`). The siblings do the actual writes;
   the new repos own the authoring UX (the interview, the packet shape).
5. **Scope: both** — per-repo by default (matches repoman's per-repo conductor),
   with a fleet-wide mode (matches `fleetman`).

## Central tension to resolve in brainstorming

Both repos hit all three backends and differ only by granularity/ceremony.
So: what is the genuinely-shared core vs. the genuinely-distinct surface, and
does "two repos" mean two thin skins over one shared library, or two fully
independent managers? (See brainstorm notes.)

## Naming — LOCKED

- **`foreman`** — the single work-item authoring manager (umbrella over issues +
  features), exposing the `issue` and `feature` skills + `promote`.

Collision-checked clean against `registry.json` via `check-name.py` (2026-06-30);
resolves to family `*man`, layer `tool`. (`issueman`/`featman` were the earlier
two-repo names, superseded by the single-repo decision.)

→ Design settled in [`CONCEPT.md`](CONCEPT.md). Next: the Phase-1 (skills-only)
KICKOFF.
