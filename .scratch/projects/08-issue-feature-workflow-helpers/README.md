# 08 — `foreman`: issue + feature creation workflow helpers

A new `*man`-family tool, **`foreman`**, that turns a rough intent into a coherent
work-item and authors it across the user's real backends. It is the work-item
**front door** for the fleet: capture a half-formed idea, interview + research it,
and materialize either a **leaf** (an issue → a TaskNotes task) or a **tree** (a
feature → an Allium spec + a numbered project packet + linked tasks), kept in sync.

## Why it lives here

`foreman` is a per-repo + fleet authoring tool in the `*man` family that repoman
will eventually compose (one manager, `key="work"`, `command="foreman"`). This
packet is its design home, following repoman's `.scratch/projects/NN-*` convention.

## The problem in one sentence

There is no single front door for "I want to start some work" — issues, feature
specs, and project plans are authored ad hoc across three different backends with
nothing keeping them linked; `foreman` is that front door.

## Read (in order)

1. **[`SEED.md`](SEED.md)** — the raw ask + the full decision trail.
2. **[`CONTEXT.md`](CONTEXT.md)** — the three backends (TaskNotes, Allium, numbered
   packets) as a composer sees them, the knappy substrate, and the manager seams.
3. **[`CONCEPT.md`](CONCEPT.md)** — the settled design (leaf-vs-tree + promotion,
   composition stack, vault↔repo field-ownership coherence, borrowed muse/loci-core
   conventions, one-package/two-profile architecture). §9 = locked decisions.
4. **[`KICKOFF.md`](KICKOFF.md)** — the paste-into-fresh-session prompt for **Phase
   1 (skills-only)**.
5. **[`01-phase1-skills-only.md`](01-phase1-skills-only.md)** — the code-grounded
   implementation guide for Phase 1.

## Status

- **Design: DONE.** All eight decisions locked (CONCEPT §9); name `foreman`
  collision-checked clean.
- **Phase 1 (skills-only): READY to implement** — birth `foreman` via
  `new-project`, author the `issue` + `feature` (+ stretch `promote`) skills, no
  Python lib and no repoman registration yet. See `KICKOFF.md` + `01-*`.
- **Phase 2 (Python engine + repoman manager wiring): NOT STARTED** — the
  `src/foreman/` core (knappy gateway, slug/path policy, reconciler) and the
  registry/module/lock seams (CONTEXT "manager-wiring seams", CONCEPT §8).
