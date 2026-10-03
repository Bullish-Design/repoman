# 01 — Phase 1 implementation guide: birth `foreman` + author its skills

Self-contained, code-grounded guide for the skills-only phase. Read
[`KICKOFF.md`](KICKOFF.md) first for scope/guardrails. All file:line citations are
to the live sibling repos under `~/Documents/Projects/`.

---

## Step A — Birth the `foreman` repo (`new-project`)

Follow `/.agents/skills/new-project/SKILL.md`. Concretely:

```bash
cd ~/Documents/Projects

# A1. Re-confirm the name is collision-free (stdlib-only; exit 0 = clear)
python3 .agents/skills/new-project/scripts/check-name.py foreman --root .
# expect: family *man · layer tool · collision: none

# A2. Scaffold from the canonical genome via copyroom (run inside a devenv that
#     has copyroom — e.g. repoman's or copyroom's). Prefer a non-interactive
#     answers file. Target dir must not exist yet.
#     copier questions (template-py/copier.yml:13-49): project_name, package_name,
#     description, author_name, author_email, project_version, repoman_dev_root.
cat > /tmp/foreman-answers.yml <<'YAML'
project_name: foreman
package_name: foreman
description: "Work-item authoring for the fleet — issues (leaves) & features (trees) across TaskNotes, Allium specs, and numbered packets."
author_name: "Bullish Design"
author_email: "090l060@gmail.com"
project_version: "0.0.1"
repoman_dev_root: "/home/andrew/Documents/Projects"
YAML
# (run copyroom from a shell that provides it)
copyroom new gh:Bullish-Design/template-py ./foreman --answers /tmp/foreman-answers.yml --trust

# A3. First devenv build (visible; this is the slow step)
cd ~/Documents/Projects/foreman
devenv shell -- true        # or: devenv shell, then exit

# A4. Lane first, then commit the scaffold (gitman is wired via template-py)
devenv shell -- gitman <new-lane>      # consult gitman's help for the lane verb
devenv shell -- gitman save -m "scaffold foreman from template-py"

# A5. Re-index the fleet so foreman is registered
(cd ~/Documents/Projects/fleetman && devenv shell -- fleetman index --root ..)
fleetman query foreman                 # expect family man, layer tool
```

**What you get** (template-py `template/` tree): `src/foreman/__init__.py` (just a
docstring + `__version__`), `pyproject.toml` (hatchling, `pydantic>=2`,
`requires-python>=3.13`), `devenv.nix` (`repoman.enable = true;
repoman.managers = [ "copy" "git" "test" ];`), `devenv.yaml`, `repoman.lock`,
`README.md`, `tests/`, `.copier-answers.yml`. **No `cli.py`, no `skills/`** — you
add the skills dir next. Leave `src/foreman/` untouched (Phase 2 owns it).

---

## Step B — The Phase-1 skill home

template-py ships no skills dir, so create one. Phase-1 source of truth:

```
foreman/
  skills/
    foreman-issue/SKILL.md       ← Step C
    foreman-feature/SKILL.md     ← Step D
    foreman-promote/SKILL.md     ← Step E (stretch)
    shared/
      tasknotes-template.md      ← the canonical leaf frontmatter (Step F)
      slug-and-paths.md          ← slug + repo-namespacing rules (Step F)
      vault-discovery.md         ← vault resolution order (Step F)
```

Each `SKILL.md` carries YAML frontmatter (`name`, `description`,
`auto_trigger`/trigger phrases) + a procedure. Keep the procedures
**confirm-before-write** and **report-paths-after**. Cross-reference the `shared/`
files so the issue and feature skills don't duplicate the schema.

---

## Step C — The `issue` skill (L0 leaf)

**Trigger:** "create an issue", "log a task/todo", "I need to track X", "add a task
for this repo".

**Procedure the SKILL.md encodes:**

1. **Resolve context** — current repo (the cwd's git/devenv root → its basename is
   the `<repo>` namespace; if not in a repo, ask or use `fleet`). Resolve the vault
   (Step F).
2. **Light interview** — title (the actionable item, imperative), priority
   (`none|low|normal|high`), optional `due`/`scheduled`, optional `contexts`
   (`@…`), and: *does this belong to an existing feature?* (if yes → its
   `[[<repo>/<slug>]]`). Keep it to ≤4 quick questions.
3. **Optional research** — if the item is vague ("figure out how to…"), spawn an
   `Explore`-style pass to ground it before writing; fold findings into the body.
4. **Size check / promotion offer** — if the item clearly needs phasing (multiple
   deliverables, a contract, a plan), say so and offer `feature`/`promote` instead.
5. **Author the leaf** — write ONE markdown note into the vault tasks folder using
   `shared/tasknotes-template.md`. Filename = `slugify(title).md` with the
   `-2/-3` collision loop (muse `workflows.py:110-124`). Confirm the rendered
   frontmatter with the user *before* writing.
6. **Report** — print the absolute path written and the slug.

**The leaf frontmatter** (`shared/tasknotes-template.md`, grounded in
`tasknotes.nvim/lua/tasknotes/config.lua:29-66` + `knappy/src/knappy/task.py`):

```yaml
---
id: task-<UTC YYYYMMDDhhmmss>-<slug>
title: <imperative title>
status: open                 # open | in-progress | done   (none also valid)
priority: normal             # none | low | normal | high
due:                         # YYYY-MM-DD (omit if none)
scheduled:                   # YYYY-MM-DD (omit if none)
contexts: []                 # ["@repo", "@deep-work"]
projects: []                 # ["[[<repo>/<feature-slug>]]"]  when attached
tags: [task]                 # REQUIRED marker — the scanner needs `task`
blockedBy: []                # dependency task ids/paths
dateCreated: <UTC ISO-8601 with T, e.g. 2026-06-30T14:05:00Z>
dateModified: <same>
---

<one-paragraph context; acceptance bullets; links back to repo/spec if relevant>
```

> camelCase keys (`dateCreated`/`dateModified`/`blockedBy`) and `T`-bearing
> ISO-8601 UTC datetimes are TaskNotes convention — knappy emits exactly these
> (`knappy/src/knappy/frontmatter.py:32-36`). Phase 2 swaps this hand-write for
> `Task(...).save()` (`knappy/demos/06_create_tasks.py`).

---

## Step D — The `feature` skill (L2 tree)

**Trigger:** "create a feature", "plan/scope a new capability", "spec out X".

**Procedure the SKILL.md encodes** — materialize the four facets and link them
(CONCEPT §4):

1. **Resolve context** — `<repo>` namespace + vault (Step F). Pick the slug:
   `slugify(title)`, repo-namespaced as `<repo>/<slug>` for the wikilink/project
   note; `fleet/<slug>` for cross-repo features.
2. **Deep interview + research** — reuse Allium's `elicit` discovery patterns
   (`allium-env/.vendor/allium/skills/elicit/SKILL.md`): scope, entities, surfaces,
   rules/acceptance, open questions. Spawn `Explore` research sub-agents to ground
   "how best to do X" before authoring. (This is the same interview→research loop
   that built *this* packet.)
3. **Facet 1 — spec (contract), repo-side.** If allium-env is set up in the repo,
   drive the `elicit` skill / `allium-01-elicit-spec.md` prompt to write
   `.scratch/specs/allium/<slug>.allium`; else author a minimal `-- allium: 3`
   spec directly per the `allium` skill syntax. Add a scope comment
   `-- Packet: .scratch/projects/NN-<slug>/`.
4. **Facet 2 — packet (plan), repo-side.** Create `.scratch/projects/NN-<slug>/`
   (NN = next free number in *this* repo's `.scratch/projects/`) with a `README.md`
   (overview + Read-list + Status) and `KICKOFF.md` carrying the recurring sections
   (title+scope · role/where-it-fits · read-first · environment rules · order of
   work · definition of done · guardrails), mirroring the sibling packets. Link the
   spec path and the vault project note.
5. **Facet 3 — leaf tasks, vault-side.** One TaskNotes note per phase/leaf (Step C
   template), each carrying `projects: ["[[<repo>/<slug>]]"]` and, where ordered,
   `blockedBy` links. These roll up under the project note natively.
6. **Facet 4 — the feature project note, vault-side.** Write
   `<vault>/Projects/<repo>/<slug>.md` (no fleet precedent — this is our template):

   ```yaml
   ---
   title: <feature title>
   tags: [project]
   repo: <repo>
   spec: .scratch/specs/allium/<slug>.allium
   packet: .scratch/projects/NN-<slug>/
   status: active            # active | done | archived (derived; see below)
   dateCreated: <UTC ISO-8601 T>
   dateModified: <same>
   ---

   # <feature title>

   > <one-line intent>

   **Repo:** <repo> · **Spec:** [[…]] · **Packet:** `.scratch/projects/NN-<slug>/`

   ## Leaves
   <task rollup — TaskNotes shows tasks whose `projects` link here; list them>
   ```

7. **The join — `feature.toml`, repo-side** (the self-describing mirror, CONCEPT
   §4):

   ```toml
   slug    = "<slug>"
   title   = "<feature title>"
   status  = "active"
   repo    = "<repo>"
   spec    = ".scratch/specs/allium/<slug>.allium"
   packet  = ".scratch/projects/NN-<slug>/"
   project_note = "Projects/<repo>/<slug>.md"   # vault-relative
   tasks   = [ "<task-id-1>", "<task-id-2>" ]    # the leaf ids
   ```
   Place it at `.scratch/projects/NN-<slug>/feature.toml`.

8. **Confirm + report** — show the user the plan (all paths) *before* writing;
   afterward report every path created and the wikilink slug.

**Field ownership (do not violate):** spec + packet live in git (repo owns them);
task status/scheduling live in the vault (TaskNotes owns them); the feature↔leaf
edges are the `projects` wikilinks (vault); the cross pointers are write-once and
mirrored in both `feature.toml` and the project-note frontmatter. **Feature status
is derived** (all leaves `done` + spec has no open questions ⇒ `done`), cached in
both faces; never hand-authored except as an explicit override.

---

## Step E — The `promote` skill (stretch)

**Trigger:** "promote <slug> to a feature", "this issue is bigger than a task".

**Procedure:** find the existing L0 leaf by its slug / `id` in the vault tasks
folder (`adopt` semantics — `loci-core/.../vault/gateway.py:265-295`: if it already
carries the feature wikilink, no-op that edge). Then run the `feature` materializer
(Step D facets 1, 2, 4, 7) *around* the existing leaf, adding
`projects: ["[[<repo>/<slug>]]"]` to it so it becomes leaf #1. **Nothing
re-created.** Report what was added vs adopted.

---

## Step F — Shared assets

**`shared/slug-and-paths.md`** — the slug + routing rules (muse precedent):
- `slugify(title)`: lowercase, `[^a-z0-9]+ → -`, strip leading/trailing `-`, cap 80
  on a word boundary (`muse/src/muse/workflows.py:50-56`).
- Collision loop: `<slug>.md`, `<slug>-2.md`, … (`muse/.../workflows.py:110-124`).
- Repo namespace: project note `Projects/<repo>/<slug>.md`; wikilink
  `[[<repo>/<slug>]]`; cross-repo features use `fleet/`.
- Wikilink form: `f"[[{target.stem}]]"` (`muse/.../workflows.py:91,228-234`).

**`shared/vault-discovery.md`** — resolution order (lean on env for Phase 1):
1. `$FOREMAN_VAULT` if set → its tasks folder is `<vault>/<tasksFolder>`.
2. else read `<vault>/.obsidian/plugins/tasknotes/data.json` → `tasksFolder`
   (default `Tasks/`) (`tasknotes.nvim/lua/tasknotes/obsidian_importer.lua:37-38`).
3. else **ask the user** for the vault root. Never hardcode.

**`shared/tasknotes-template.md`** — the leaf frontmatter block from Step C
(single source the issue/feature/promote skills all reference).

---

## Verification (dry-run, throwaway slug)

Run each skill end-to-end against a disposable slug (e.g. `foreman-selftest`) in a
scratch repo + a scratch vault dir, then inspect:

1. **issue:** exactly one note in `<vault tasks>/`, frontmatter valid
   (`tags:[task]`, `status: open`, ISO-8601 `T` dates), filename = slug.
2. **feature:** `.scratch/specs/allium/foreman-selftest.allium`,
   `.scratch/projects/NN-foreman-selftest/{README,KICKOFF}.md` + `feature.toml`,
   leaf notes carrying `projects: ["[[<repo>/foreman-selftest]]"]`, and
   `<vault>/Projects/<repo>/foreman-selftest.md`. Confirm the wikilink resolves
   (the project-note stem matches the leaves' `projects` target).
3. **field ownership:** the spec/packet are in the repo; the task status is only in
   the vault; pointers match between `feature.toml` and the project note.
4. Delete the self-test artifacts. Commit the skills (gitman lane). **Do not push.**

---

## Risks / notes

- **Hand-written frontmatter drift** — Phase 1 authors markdown by hand, so the
  template MUST match TaskNotes exactly (camelCase, `T` datetimes, `tags:[task]`).
  This is deliberately the thing Phase-2 knappy removes; keep the template in ONE
  shared file to limit blast radius.
- **Allium availability** — `elicit` only exists where allium-env is installed. The
  `feature` skill must degrade gracefully (author a minimal `.allium` directly) and
  say so, rather than failing.
- **Vault writes are real** — always confirm before writing into the user's actual
  vault; default to a dry-run plan first.
- **Packet numbering races** — NN is "next free in this repo"; compute it at write
  time, don't assume.
- **Don't over-reach into Phase 2** — no `src/foreman/` engine, no repoman registry
  edits. If the skills feel like they want a real library, that's the signal Phase
  2 is ready, not license to start it here.
