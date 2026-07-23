You are picking up **repoman** — the per-repo agentic lifecycle conductor for the
`*man` family — in a fresh session. You are working from the repo root:
`/home/andrew/Documents/Projects/repoman`.

WHAT REPOMAN IS
repoman is one devenv import that turns a repo into a fully-managed agentic repo:
a **nix meta-module** (`modules/devenv.nix` + `modules/managers/*.nix`) that wires
the selected `*man` managers (copyroom/gitman/testee/docman/zelligate/mypi/allium),
plus a **thin Python conductor** (`src/repoman/`) that sequences and aggregates
their CLIs under a `0/1/2/3` exit contract. It re-models nothing; each manager
keeps its own report and skill. It is **per-repo BY DESIGN** — fleet/workspace
scope belongs to `fleetman`, not repoman.

CURRENT STATE (verified, v0.3.0, 66 tests passing)
- **Manager roster: COMPLETE** — all 7 keys wired in `src/repoman/registry.py` and
  `modules/devenv.nix`, each with a `modules/managers/*.nix` module.
- **nix-provisioning bridge: LANDED** (all 6 phases; native toolchains + approach-B
  `provisioned:<key>` warnings via `REPOMAN_PROVISIONED_*` in `src/repoman/checks.py`).
- **devman subsystem: BUILT** (`src/repoman/devman/*`, wired into `cli.py`) — though
  its packet `.scratch/projects/02-devman-module/` still says "brainstorm".
- **Entrypoint router skill: BUILT** (`src/repoman/skills.py`, `docs/SKILLS.md`).
- **OUTSTANDING:** `foreman` (project 08) — a locked-but-uncoded 8th manager;
  lifecycle pass-throughs (`verify`/`save`/`release`) — described, not built.
  (Fleet-sync, ex-project 07, was descoped to `fleetman` on 2026-07-01 and retired —
  no longer repoman work; see `07-tower-repo-set-sync/SUPERSEDED.md`.)

READ FIRST (in this dir: `.scratch/projects/09-repo-review-and-catch-up/`)
1. `OVERVIEW.md` — what repoman is, where it is now, and the concept-vs-reality
   gap table (cites real files/commands).
2. `PLAN.md` — the sequenced remaining-work plan (Steps 0–5).
Then skim `CONCEPT.md` (§1–6 the design, §2 the per-repo scope line, §5 the
lifecycle verbs), `src/repoman/registry.py`, `src/repoman/cli.py`.

RESOLVED — fleet-sync ownership (no longer a task)
The old "fleet-sync (07) vs fleetman 002" overlap is **settled**: fleet-sync was
descoped from repoman → owned by **fleetman** on 2026-07-01, and project 07 is
retired (`.scratch/projects/07-tower-repo-set-sync/SUPERSEDED.md`). repoman stays
**per-repo by design** (`CONCEPT.md §2`); do not build `src/repoman/fleet/`.

YOUR FIRST CONCRETE TASK
Start with **PLAN.md Step 0** (cheap doc-truth reconciliation), then the
highest-value net-new work: **Step 2 — `foreman` Phase 1 (skills-only)**, the
unblocked biggest outstanding item, which births a separate repo and touches no
repoman source. Follow `08-issue-feature-workflow-helpers/KICKOFF.md` +
`01-phase1-skills-only.md`.

CONVENTIONS (hard rules)
- **Devenv only** for in-repo commands: `devenv shell -- <cmd>`; never bare
  `uv`/`python`/`pytest`/`ruff`.
- **Verify before commit:** `devenv shell -- python -m pytest -q` green AND
  `repoman doctor` clean before any commit. Treat empty/missing output as a
  failure to investigate — no silent failures.
- **Version control via gitman** (jj + colocated git); never raw jj/git. Lane
  (branch) first if on the default branch; commit as you work; **do NOT push**
  without an explicit ask.
- No AI-authorship trailers/attributions in commits, PRs, docs, or skills.
- Do not restructure repoman or touch manager wiring beyond what an approved step
  requires.
