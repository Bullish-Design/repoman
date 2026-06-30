# CONTEXT — the three backends, as a composer sees them

Durable reference for the two new helpers. Verified against the live sibling
repos (file:line in the source repos). The key fact: **none of these three
backends gives us a clean in-process "create" API — each is driven differently**,
which shapes how we compose them.

## Backend 1 — local tasks = **Obsidian TaskNotes** (NOT Taskwarrior)

> **CORRECTION (2026-06-30):** task tracking is **Obsidian TaskNotes**, not
> Taskwarrior. `taskman`/`taskdantic` are Taskwarrior-only and are therefore
> **NOT** our task backend. `tasknotes.nvim` is the only sibling with TaskNotes
> support, but it's a **Neovim Lua API, no CLI** — so we don't compose it.

- **A task IS a markdown note** (one file) with YAML frontmatter, living flat in
  the vault's tasks folder (`<vault>/<tasksFolder>`, default `Tasks/`; or
  `~/notes/tasks`). Schema from `tasknotes.nvim/lua/tasknotes/config.lua:29-66`.
- **Frontmatter fields:** `id` (zettel `task-YYYYMMDDhhmmss-<slug>`), `title`,
  `status`, `priority`, `due`, `scheduled`, `contexts[]` (`@ctx`), **`projects[]`
  (Obsidian `[[wikilinks]]`)**, `tags[]` (**must include `task`** — the scanner's
  marker), `timeEstimate`, `timeEntries[]`, `blockedBy[]` (deps: task ids/paths),
  `completedDate`, `dateCreated`/`dateModified` (ISO-8601 UTC), `archived`.
- **Vocab** (configurable, but defaults): `status ∈ none|open|in-progress|done`
  (`done`=completed); `priority ∈ none|low|normal|high`.
- **Hierarchy/links are NATIVE markdown:** a task attaches to a project by a
  `projects: ["[[<project-note>]]"]` **wikilink**; dependencies via `blockedBy`.
  No dedicated parent/subtask field — the **wikilink graph is the join**.
- **CREATION = `knappy`** (the resolved leaf backend — see below). `knappy` is a
  TaskNotes-aware, typed, data-lossless vault I/O library (`Note`/`Task` Pydantic
  models, atomic `save()`). `Task(title=…, status="open", priority="high",
  tags=["task"], projects=["[[…]]"], …).save(path)` IS "create a TaskNotes task"
  (`knappy/demos/06_create_tasks.py`). Use knappy, **not** taskman and **not**
  raw file-writes / obsidian-ops.
- **Vault config:** tasks folder derivable from the Obsidian plugin's
  `data.json` (`tasksFolder`), or set directly. Vault root is per-user config,
  not committed here (placeholders `~/sync/vault`, `~/notes/tasks`).

## Backend 2 — specs = `allium-env` / `alliman`

- A **spec** is a *behavioural* spec in the Allium language (`.allium`,
  `-- allium: 3` marker): `entity` / `rule` / `surface` / `invariant` / etc.
  Describes **what a system does**, not how. Lives in `allium.specsDir`
  (default `.scratch/specs/allium`).
- **Authoring is skill/prompt-driven, NOT a Python API.** The `alliman` CLI only
  does `install-skills` / `doctor` / `init` — no spec scaffolding. To create a
  spec you drive an agent through the **`elicit` skill** + the prompt pipeline.
- **There is already a 6-stage pipeline** in `.agents/prompts/`:
  `01-elicit-spec → 02-review → 03-tend → 04-implementation-guide → 05-execute →
  06-git-tag`. Stage 04 emits a **phased implementation guide** (Phases with
  "What to build" / "Acceptance criteria" / "Depends on") — i.e. allium ALREADY
  turns a feature into a work breakdown.
- Skills shipped: `allium` (lang ref), **`elicit`** (interview→spec — the
  authoring brain), `distill` (spec from code), `tend` (edit/fix), `weed`
  (spec↔code drift), `propagate` (tests from spec).
- Console script `alliman`; devenv present.

## Backend 3 — numbered project packets = `.scratch/projects/NN-name/`

- A convention, not a tool. De-facto template: `NN-kebab-name/` containing
  `README.md` (overview + Read-list + Status), optional `CONCEPT.md` (settled
  design), `CONTEXT.md` (map of the existing system), `KICKOFF.md`/
  `KICKOFF_PROMPT.md` (paste-into-fresh-session prompt), and one `NN-*.md`
  code-grounded guide per work item.
- Lifecycle: `SEED.md` (raw) → `README`+`CONCEPT` (brainstorm) → `KICKOFF` +
  numbered guides (ready). This very directory is an instance.
- Recurring KICKOFF sections: title+scope · role/where-it-fits · "Read first
  (design settled)" · environment rules (devenv-only) · order of work ·
  definition of done · guardrails · (open questions / source material).

## The manager-wiring seams (end-state, when these become full `*man`)

External-tool path, 4 seams (+ tests + consumer-example verify):
1. `src/repoman/registry.py` — a `Manager(key, command, tier, doctor, status,
   summary, skill, route_when, nix_input)` entry.
2. `modules/devenv.nix` — add key to `allManagers` (drives the enum) + add
   `./managers/<key>.nix` to `imports`.
3. `modules/managers/<key>.nix` — pure-Python task-wiring (model on `testee.nix`):
   gate on `cfg.enable && elem "<key>" cfg.managers`, expose `repoman:<domain>:…`
   tasks shelling `${venvBin}/<command>`.
4. `tests/consumer-example/repoman.lock` — `[managers.<key>]` block.
- Born via the `new-project` skill: name collision-check (`check-name.py` vs
  `registry.json`) → `copyroom new gh:Bullish-Design/template-py` → wire repoman →
  `fleetman index`. template-py scaffolds NO cli.py and NO skills dir — both are
  hand-authored; skills install at runtime.
- CLI contract (per docman/alliman): module docstring + exit codes
  `0 ok · 1 domain finding · 2 infra/config · 3 invalid usage`; `doctor`
  (`--json`/`--repo-root`, exit 0/2); `init`; optional status verb / `install-skills`.

## The two findings that reshape the design

1. **The three backends form a natural hierarchy, not three equal targets:**
   - a **task** is a *leaf* (one actionable item, = a TaskNotes markdown note),
   - a **spec** is a *behavioural contract* (what a capability does),
   - a **packet** is an *implementation plan* (phased guide to build it).
   A feature naturally OWNS all three (contract + plan + leaves, linked); an issue
   is usually just a leaf. The fan-out is the decomposition of a feature.
2. **allium-env already overlaps the "feature" job** (elicit→spec→impl-guide), and
   the impl-guide overlaps the numbered packet. So the feature helper is best
   framed as a **front door / orchestrator** over existing engines (esp. allium's
   `elicit` + the packet convention), NOT a new authoring engine. This is exactly
   the repoman "compose, don't reimplement" ethos.
3. **`knappy` is the leaf backend** — a TaskNotes-aware, typed, data-lossless
   vault I/O **library** (`Note`/`Task` Pydantic models, atomic permission-
   preserving `save()`, camelCase TaskNotes keys, ISO-8601 `T` datetimes,
   `[[wikilink]]` projects, `task`-tag promotion). No CLI — composed as a Python
   dep. **Prior art:** `muse` ("opinionated content engine on top of knappy") and
   `loci-core` already wrap it — mirror their pattern, don't reimplement vault I/O.
   knappy deliberately **defers** exactly the things OUR shared core must own:
   (a) **slug/filename/directory policy** (knappy needs an explicit existing
   path), (b) **status/priority enum enforcement** (open strings today), and
   (c) **typed `blockedBy`/`projects` wikilink helpers** (untyped `properties`
   today). That gap IS the issue/feature core's job.

## Resolved composition stack

| Facet | Backend (composed) | How |
|---|---|---|
| leaf task / project note | **knappy** | `Task(...).save()` / `Note(...).save()` into the vault |
| spec (contract) | **allium-env** | drive the `elicit` skill → `.allium` |
| packet (plan) | **numbered-dir convention** | template file-writes (README/KICKOFF/guides) |
| version control | **gitman** | per-repo VC (specs/packets are git-tracked) |
| fleet scope | **fleetman** | cross-repo discovery/indexing |

The shared core (issue/feature engine) = `interview ⇄ research → render → dispatch`
on top of these, owning the slugging/status/templating/linking opinions knappy
and allium leave to consumers.
