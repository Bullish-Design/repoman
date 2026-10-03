# 09 — repoman review & catch-up: PLAN

> Sequenced plan for the remaining repoman work, grounded in the current tree
> (see `OVERVIEW.md` for the concept-vs-reality table). Ordered so the cheap
> doc-truth step comes first, before any net-new code. (The old fleet-sync
> ownership question is already resolved — see the resolved-decision note below.)
> Nothing here is committed; do not modify source until a step is approved.

Conventions for every step: run in-repo commands via `devenv shell -- …`; route
VC through **gitman** (lane first, commit as you work, **don't push** without an
explicit ask); verify (`pytest` green + `repoman doctor`) **before** any commit;
no AI-authorship trailers.

---

## Step 0 — Reconcile packet status with the code (cheap, do first)

**Why:** the tree is ahead of two packets; readers are being misled.
- **devman (project 02)** is fully built and wired (`src/repoman/devman/*`,
  `cli.py:16,65,104`, `test_devman.py`) but `02-devman-module/README.md:36` still
  says "Brainstorm." Add a short "SHIPPED" note at the top of that README pointing
  at the real files, and resolve or explicitly YAGNI its open questions
  (name kept as `devman`; self-check strictness currently `warn` in `checks.py:21`;
  hook surface deferred).
- Confirm project 05 (nix-provisioning bridge) is marked done (it is) and 03/04
  (remaining-managers) are closed by the current roster.

**Deliverables:** edits to `.scratch/projects/02-devman-module/README.md` (and a
one-line status note in 03/04 READMEs if stale). **No `src/` changes.**
**Acceptance:** each packet's stated status matches the tree.
**Risk:** trivial; docs only.

---

## Resolved decision — fleet-sync ownership (was Step 1)

**Fleet-sync descoped from repoman → owned by fleetman, 2026-07-01.** Project 07
(`repoman fleet-sync`) is retired (see `07-tower-repo-set-sync/SUPERSEDED.md`); it is
no longer an outstanding repoman work item and needs no decision gate. A cross-repo
clone/fetch of the whole `Projects` set is a **fleet** operation, so its home is
**fleetman** (`.scratch/projects/002-fleet-write-ops/`), which already owns the
workspace index + DAG. repoman stays **per-repo by design** (`CONCEPT.md §2`). The
naming hazard is moot: `repoman-sync.sh` is the unrelated venv-toolchain sync, never
a repo-set sync.

---

## Step 2 — `foreman` Phase 1 (skills-only) — the biggest outstanding item

**Why first among net-new work:** design is fully LOCKED
(`08-*/CONCEPT.md` §9, 8 decisions; name collision-checked clean) and Phase 1
touches **no repoman source** — it births a *separate* repo, so it's unblocked and
low-risk to repoman itself.

Follow `08-issue-feature-workflow-helpers/KICKOFF.md` +
`01-phase1-skills-only.md` exactly:
- Birth `foreman` via the workspace **`new-project`** skill
  (`copyroom new gh:Bullish-Design/template-py` → devenv build → wire repoman →
  `fleetman index`).
- Author the agent skills only: `foreman-issue` (L0 leaf → TaskNotes task),
  `foreman-feature` (L2 tree → allium spec + numbered packet + linked tasks +
  vault project note + `feature.toml`), stretch `foreman-promote`; plus the shared
  slug/frontmatter/vault-discovery assets.
- **Scope fence:** no Python engine (leave `src/foreman/` a stub), **no repoman
  registration** (do NOT touch `registry.py` / `modules/devenv.nix` /
  `repoman.lock`), no knappy yet — author markdown directly from the templates.

**Deliverables:** a new `foreman` repo with three skills + shared assets; skills
self-tested against a throwaway slug + scratch vault. **Acceptance:** `issue`
authors a real task; `feature` authors spec+packet+tasks+project-note, all linked,
confirming before write and reporting exact paths. **Risk:** the skills write into
a **real Obsidian vault** — must confirm before writing and self-test on scratch.

---

## Step 3 — `foreman` Phase 2 (Python engine + repoman manager wiring)

**Why after Phase 1:** Phase 2 is where `foreman` finally becomes repoman's **8th
manager**, so it is the concrete repoman catch-up item that closes the largest
concept gap.

- Build `src/foreman/` core (knappy gateway single-seam, slug/paths, spec dispatch
  to allium `elicit`, numbered-packet renderer, item identity L0/L1/L2, the
  `scan→snapshot→plan→apply` reconciler, Typer CLI) per `08-*/CONCEPT.md` §6, with a
  family-standard CLI contract (`doctor --json/--repo-root` exit 0/2, `init`, a
  status verb, `install-skills`, exit `0/1/2/3`).
- **Wire into repoman via the standard external-tool seams** (`08-*/CONCEPT.md` §8):
  1. `src/repoman/registry.py` — `Manager(key="work", command="foreman",
     tier="situational", status=[...], skill="foreman", …)`.
  2. `modules/devenv.nix` — add `"work"` to `allManagers` (`:26`) + the enum, and
     `./managers/foreman.nix` to `imports` (`:29`).
  3. `modules/managers/foreman.nix` — pure-Python task wiring (model on
     `gitman.nix`/`testee.nix`, no native toolchain), gated on
     `"work" ∈ managers`, exposing `repoman:work:issue|feature|promote|status`.
  4. `[managers.work]` block in `repoman.lock`.
- Add tests mirroring the existing pattern (`tests/test_registry.py` picks up the
  new key; a `foreman.nix` consumer-example smoke via the throwaway repo).

**Deliverables:** `foreman` CLI + the four repoman seam edits + tests.
**Acceptance:** `repoman managers` lists `work`; `repoman doctor` aggregates
`foreman doctor` under the 0/2 contract; self-check `installed:work` /
`lock:work` pass; full suite green. **Risk:** first roster change since the bridge
landed — re-run the full-roster consumer-example verify (project 05's capstone) to
confirm no regression in `provisioned:*` / lock-consistency checks.

---

## Step 4 — Lifecycle pass-throughs (`verify` / `save` / `release`)

**Why:** `CONCEPT.md` §5 promises gated lifecycle verbs the CLI doesn't yet expose;
they're the natural conductor surface once the roster is complete.

- Add to `src/repoman/cli.py`, reusing `aggregate.run_sub` + `worst_exit`:
  - `verify` → `test` (testee), exit = its exit.
  - `save -m` → `test` verify, then **gated on green**, `git` (gitman) save.
  - `release` → `test` ci → `git` release → `doc` (docman) — each gated on the
    prior's exit under `0/1/2/3`.
- Keep them thin (sequence + gate only; no re-modelling of manager reports),
  skipping steps whose manager isn't enabled (mirror `SPINE` rendering).

**Deliverables:** three CLI verbs + tests (`tests/test_cli.py`) asserting the
gate-on-exit behavior. **Acceptance:** `save` refuses to call gitman when testee
is non-zero; `release` stops at the first non-zero stage; exit codes correct.
**Risk:** must not run a destructive `git`/`release` step after a failed gate —
test the abort paths explicitly.

---

## Step 5 — Entrypoint-skill polish (optional, low priority)

Close the leftover `CONCEPT.md` §8 skill items: a conflict-precedence table,
installing manager sub-skills (not just the entrypoint), and a `doctor`-as-skill-
linter pass. Extend `docs/SKILLS.md` + `skills.py` + `test_skills.py`.
**Acceptance:** documented precedence + sub-skill install covered by a test.
**Risk:** low; cosmetic relative to Steps 2–4.

---

## Ordering rationale (one line)

Step 0 (doc truth) is a near-free prerequisite (the fleetman-overlap is already
resolved: fleet-sync belongs to fleetman, project 07 retired); then the
highest-value net-new work — **`foreman` Phase 1 → Phase 2** (the biggest gap, and
the only thing that adds a manager) — then the lifecycle verbs, then skill polish.
