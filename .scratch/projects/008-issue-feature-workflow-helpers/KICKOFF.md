# KICKOFF — `foreman` Phase 1 (skills-only)

> **Birth the `foreman` repo and author its two agent skills (`issue` + `feature`,
> plus a stretch `promote`) — the work-item authoring front door for the fleet.
> NO Python library and NO repoman manager-registration yet: Phase 1 is the
> markdown skills only.** The skills do the work the future `src/foreman/` engine
> will later automate: interview ⇄ research → author a leaf (TaskNotes task) or a
> tree (spec + packet + linked tasks) → keep them linked.

You are starting a FRESH session. Work happens in TWO places: the brand-new
`/home/andrew/Documents/Projects/foreman` repo (you create it), and the design
packet at `/home/andrew/Documents/Projects/repoman/.scratch/projects/08-issue-feature-workflow-helpers/`
(you read it). Read this packet, then propose a step-by-step plan for approval
before scaffolding anything.

---

## Read first (the design is settled — do not re-derive)

In order:
1. **[`CONCEPT.md`](CONCEPT.md)** — the settled design. `foreman` = one `*man`
   tool, two skills, leaf-vs-tree + promotion, the composition stack, vault↔repo
   field-ownership coherence, borrowed muse/loci-core conventions. §9 = locked
   decisions; §7 = the Phase-1 skill surface you are building.
2. **[`CONTEXT.md`](CONTEXT.md)** — the backends as a composer sees them. The
   **TaskNotes frontmatter schema** (Backend 1), the **Allium spec/elicit**
   lifecycle (Backend 2), the **numbered-packet convention** (Backend 3), and the
   manager-wiring seams (Phase 2, not now).
3. **[`SEED.md`](SEED.md)** — the raw ask + decision trail.
4. The `new-project` skill: `/home/andrew/Documents/Projects/.agents/skills/new-project/SKILL.md`
   (+ `references/naming-families.md`, `scripts/check-name.py`).

## Environment rules (hard requirements)

- **Devenv only.** Every in-repo command runs inside the devenv:
  `devenv shell -- <cmd>` (or `devenv tasks`). Never bare `uv`/`python`/`pytest`.
- **Version control through gitman.** The new `foreman` repo is born from
  `template-py`, whose devenv enables `repoman.managers = [ "copy" "git" "test" ]`
  — so **gitman is wired in `foreman`**. Use `devenv shell -- gitman …` there;
  never raw jj/git. Lane first (don't commit on the default branch). **Commit as
  you work; do NOT push** (gated).
- **No AI-authorship trailers/attributions** anywhere (commits, docs, skills).
- **No silent failures** — check exit codes; if a step's output is empty/missing,
  treat it as a failure to investigate.
- Run long/opaque steps (copyroom scaffold, devenv build) **visibly**; don't pipe
  to files or hide them.

## Scope fence (what Phase 1 is NOT)

- **NOT** a Python package implementation — `src/foreman/` stays the template-py
  stub. The engine modules in CONCEPT §6 are the Phase-2 target.
- **NOT** repoman manager-registration — do **not** touch repoman's
  `registry.py` / `modules/devenv.nix` / `repoman.lock`. (That's the Phase-2 seams
  in CONTEXT.) The `new-project` "wire repoman" step only makes `foreman` itself a
  *managed* repo, not a *registered manager*.
- **NOT** knappy-backed yet — Phase-1 skills author markdown **directly** from the
  documented templates. knappy is the Phase-2 replacement; write the skills so that
  swap is obvious (CONTEXT Backend 1 has the exact frontmatter).

---

## Order of work (each step ends green)

Detailed, code-grounded steps are in **[`01-phase1-skills-only.md`](01-phase1-skills-only.md)**.
Summary:

1. **Birth `foreman`** via the `new-project` skill: re-confirm the name is clean
   (`check-name.py foreman`), `copyroom new gh:Bullish-Design/template-py
   ../foreman --answers …`, enter, `devenv shell` (first build), wire repoman,
   `fleetman index`. Commit the scaffold on a lane.
2. **Add the Phase-1 skill home** — create `skills/` in `foreman` with three skill
   dirs (`foreman-issue/`, `foreman-feature/`, stretch `foreman-promote/`).
   template-py ships no skills dir; you create it. Each is a `SKILL.md`.
3. **Author the `issue` skill** (L0 leaf) — interview → optional research → write a
   TaskNotes task note into the vault, repo-namespaced, with a promotion offer.
4. **Author the `feature` skill** (L2 tree) — deeper interview + research →
   materialize spec (allium) + packet (numbered dir) + leaf tasks + the vault
   project note + `feature.toml`, all cross-linked per the field-ownership model.
5. **(Stretch) the `promote` skill** — adopt an existing L0 leaf and grow it L0→L2.
6. **Vault discovery** — a small, documented resolution order the skills share.
7. **Self-test** — dry-run each skill against a throwaway slug; confirm the files
   land in the right places with valid frontmatter and resolve as wikilinks.
8. **Commit** each coherent step on the lane (gitman). Report.

## Definition of done

1. `foreman` exists at `~/Documents/Projects/foreman`, scaffolded from
   `template-py`, its devenv builds, and `fleetman query foreman` resolves it
   (family `man`, layer `tool`).
2. `foreman/skills/foreman-issue/SKILL.md` and `…/foreman-feature/SKILL.md` exist
   and are self-contained: each encodes the interview, the research step, the exact
   author targets/templates, the slug + repo-namespacing rules, the linking, and a
   confirm-before-write gate.
3. The `issue` skill, run end-to-end on a test slug, produces ONE valid TaskNotes
   task note (correct frontmatter: `tags:[task]`, `status: open`, repo-namespaced
   `projects` wikilink when attached) in the vault's tasks folder.
4. The `feature` skill, run on a test slug, produces the full tree —
   `.scratch/specs/allium/<slug>.allium`, `.scratch/projects/NN-<slug>/`
   (README+KICKOFF), leaf task notes linked via `[[<repo>/<slug>]]`, the vault
   project note `Projects/<repo>/<slug>.md`, and `feature.toml` — all cross-linked
   per CONCEPT §4.
5. Vault location is resolved by the shared, documented order (no hardcoded path).
6. Everything committed on a lane via gitman; nothing pushed; no AI attributions.

## Guardrails

- Build ONLY Phase 1. Do not start the Python engine or the repoman seams.
- Reuse fleet conventions verbatim where they exist (TaskNotes frontmatter,
  numbered-packet sections, allium `elicit`, muse slug/path rules) — cite them in
  the skills so Phase 2 can mechanize them.
- The skills must **confirm with the user before writing** and **report exactly
  what was created** (paths) — they are authoring real artifacts in a real vault.
- Keep `src/foreman/` the untouched template stub.

## Source material (cite when implementing)

- This packet: `CONCEPT.md` (§4 coherence, §6 architecture, §7 skill surface),
  `CONTEXT.md` (all three backend schemas + the seams).
- `new-project` skill + `check-name.py` + `references/naming-families.md`.
- TaskNotes schema: `tasknotes.nvim/lua/tasknotes/config.lua:29-66`.
- knappy authoring (Phase-2 target): `knappy/demos/06_create_tasks.py`,
  `knappy/src/knappy/{note,task}.py`.
- muse conventions: `muse/src/muse/{workflows.py:50-124, schema.py:70-94, domain.py:28-120, vault.py:26-63}`.
- loci-core machinery: `loci-core/src/loci_core/{vault/gateway.py, domain/{vocab,reconcile,schema}.py}`.
- allium elicit: `allium-env/.vendor/allium/skills/elicit/SKILL.md`,
  `allium-env/.agents/prompts/allium-01-elicit-spec.md`.
- numbered-packet convention: the sibling dirs in
  `repoman/.scratch/projects/` (esp. `07-*/KICKOFF.md`, `02-*/README.md`).

## Open questions (surface, don't block)

- **Project-note template** has no fleet precedent — design it (frontmatter
  pointers + a task-rollup body). Propose; don't agonize.
- **Vault discovery** — settle the resolution order (env → TaskNotes `data.json`
  `tasksFolder` → ask). Lean on env for Phase 1.
- **Status vocab** — TaskNotes defaults (`open|in-progress|done`) vs loci-core's
  wider `Literal[...]`. Phase 1: use TaskNotes defaults; note the reconcile.
- **Skill install path** — Phase 1 skills live in `foreman/skills/`; how they get
  *installed* into a working repo (`.claude/skills/`) is the Phase-2
  `install-skills` job. For now, document manual use.
