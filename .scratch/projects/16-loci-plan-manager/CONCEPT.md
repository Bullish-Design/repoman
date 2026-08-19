---
loci:
  schema: 1
  id: 01a01b22-19ef-7000-bb30-335ead87db4c
  projects: []
---
# CONCEPT — loci-core as RepoMan's `plan` phase

> **RepoMan's lifecycle has no step for deciding what to change, and no artifact
> that records why a change exists. loci-core's workspace manifest is that
> artifact. This project adds a `plan` phase to the spine and wires loci-core
> behind it.**

**Status:** proposal. Nothing is implemented.
**Date:** 2026-08-19.
**repoman:** 0.7.0. **loci-core:** v0.4.1 + 23 commits (HEAD).
**Supersedes:** an earlier brainstorm that proposed loci as a default `notes`
manager. That analysis ran against a superseded loci-core API. §13 records the
correction so nobody repeats it.
**Companion:** [`SPIKES.md`](SPIKES.md) — nine measurements taken before
committing to this plan. Five of them changed it, and its "rules these produce"
section is the constraint list the implementation must carry.

---

## 1. The gap this fills

RepoMan's spine is `scaffold → change → verify → save → docs`
(`src/repoman/registry.py:62`). Each step has an owner:

| Step | Manager | Owns |
|---|---|---|
| scaffold | copyroom | the template, and drift from it |
| change | *(human/agent)* | the edit |
| verify | testee | the run |
| save | gitman | the lane |
| docs | docman | the site |

Two things are missing, and they are the same thing seen twice:

1. **No step decides what to change.** The lifecycle starts at "scaffold" and
   jumps straight to "change". The decision that produced the change lives
   nowhere.
2. **No artifact survives the shell.** A unit of work touches some documents and
   some source files. That set exists only in an agent's context window. Close
   the session and it is gone.

Every manager holds durable state for its own phase. The planning phase holds
none, because it does not exist.

## 2. What loci-core is

An **ownership-aware compiler over a directory of Markdown files**. Roughly 9 200
lines across `src/loci_core/` and `apps/`. It is not a note application, not a
task tracker, and not a database.

Four properties define it.

**Files are the only authority.** SQLite is a disposable compiler cache. It lives
in `~/.cache/loci/vaults/<vault-id>-<root-digest>/`, keyed by vault id *and*
canonical root path (`src/loci_core/fs/runtime.py`). It never sits inside the
vault. Delete it and the next fresh query rebuilds an identical revision.

**It owns three keys.** The canonical `loci:` frontmatter region holds `schema`,
`id`, and `projects`. loci may also write one shared property, `status`, when
asked. Every other byte in a document is protected source. There is no `delete`,
no `set_title`, no `set_tags` — their absence is a recorded decision.

**Adoption is demand-driven.** A document gets an id only when an action needs a
durable reference. Unmanaged documents are first-class: `documents/list`,
`search/text`, and the whole graph surface work on files loci has never touched.

**Every mutation is preview-first.** The CLI shows a diff and writes nothing
without `--apply`. One JSON envelope crosses the boundary —
`{ok, value}` / `{ok: false, error: {kind, message}}` — and one projection serves
both hosts (`src/loci_core/protocol/envelope.py`).

It ships two hosts already: `loci` (CLI) and `loci-lsp` (a pygls language server).
loci.nvim is a third-party client over the same wire contract.

### The current command surface

```
init                    documents/adopt      graph/ambiguous_links   relations/add_project
                        documents/create     graph/backlinks         relations/remove_project
                        documents/format_owned  graph/broken_links   search/text
                        documents/get        graph/broken_anchors    workspaces/archive
                        documents/list       graph/missing_attachments  workspaces/get
                        documents/move       graph/neighbors         workspaces/list
                        documents/preview_adoption  graph/orphans    workspaces/put
                        documents/set_status graph/project_members
maintenance/refresh     refactor/rewrite     graph/traversal
```

## 3. The fact that makes this viable

loci-core's default discovery policy excludes `.git/**`, `.jj/**`, `.hg/**`,
`.venv/**`, `.devenv/**`, `.direnv/**`, `.tox/**`, `__pycache__/**`,
`node_modules/**`, `target/**`, `dist/**`, `build/**`, and `result*`. The comment
above that list (`src/loci_core/vault/manifest.py:32`) reads:

> *a "vault" is often also a code repository (M3)*

And `docs/USER.md` §9:

> *Git is an opportunity, never a dependency. loci never requires a repository,
> never fails because one is absent or dirty, and never gates, stashes, or commits
> on your behalf.*

**loci-core was designed for the vault-inside-a-code-repo case.** It will not
fight gitman. This is the single fact that turns "integrate a knowledge engine
into a repo toolchain" from a forced fit into a natural one.

### The committed footprint is one file

Verified in a throwaway git repo:

```
$ loci --json init
{"ok": true, "value": {"root": "/tmp/loci-probe",
                       "manifest": "/tmp/loci-probe/.loci/vault.toml"}}
$ find .loci -type f
.loci/vault.toml
```

Cache and lock live outside the repo. **There is nothing to gitignore.** Any
proposal that asks you to gitignore a derived cache inside the repo is describing
a different engine.

## 4. The real integration surface: the workspace

A workspace manifest (`.loci/workspaces/<name>.yaml`) holds exactly this
(`src/loci_core/vault/workspace.py`):

| Field | Meaning |
|---|---|
| `schema` | manifest schema version (currently `1`) |
| `id` | the workspace id |
| `name` | human name |
| `project` | optional project resource id |
| `documents` | ordered refs **by id**, each with a role — survives every rename |
| `files` | linked **file paths** with roles — code, not documents |
| `archived` | the only lifecycle flag |

Verified against HEAD:

```
$ loci workspaces/put name=project-15 \
      documents=docs/Roadmap.md,docs/Design.md files=devenv.nix --apply
{"ok": true, "value": {"workspace_id": "01a01b09-…",
                       "path": ".loci/workspaces/project-15.yaml",
                       "adopted_members": ["docs/Roadmap.md", "docs/Design.md"], …}}
```

One transaction adopted both documents, stamped their ids, and wrote the
manifest. The result is a durable, source-controlled record that says: *this unit
of work covers these documents and these source files.*

**That is the missing artifact from §1.** It is not a note. It is a unit-of-work
record that binds prose to code and survives renames on the prose side.

## 5. The seam is already cut for a host like RepoMan

`docs/USER.md` §10:

> *There is no `current`, no activation, no editor state in core. A host opens a
> workspace and owns an ephemeral session.*

loci **deliberately refuses to store** the one piece of state RepoMan is best
placed to own. RepoMan's devenv shell is a host in exactly the sense loci means.

The division is clean and has no overlap:

| Fact | Owner | Where it lives |
|---|---|---|
| the roster of a unit of work | loci | `.loci/workspaces/<name>.yaml`, committed |
| document identity, links, graph | loci | frontmatter + disposable cache |
| **which workspace is current** | **RepoMan** | ephemeral, under `$DEVENV_STATE` |
| **where a workspace sits in the lane graph** | **RepoMan** | ephemeral; derived from gitman |
| the lane the work lands on | gitman | `gitman.toml` |
| the verification of the work | testee | its run records |

RepoMan supplies the session; loci supplies the durable roster. Neither
reimplements the other.

The fourth row is a finding, not a design choice. [`SPIKES.md`](SPIKES.md) SP-6
shows a workspace manifest is a tracked file and therefore **travels with the
lane that created it**. On a sibling lane, `workspaces/list` returns `[]` and the
adopted documents have no `loci:` region — correctly, because the adoption was
part of the other lane's change. The plan lands with the code that implements it,
which is the right default. But it means no single worktree can answer "what is in
flight across this repo", and loci is structurally unable to answer it — the fact
is not in the vault. RepoMan is the only component positioned to.

SP-6 also found the hazard this creates. Two lanes adopting the same document mint
two different ids and conflict in frontmatter on merge, after which one workspace
holds a dangling ref. loci degrades honestly throughout — a conflicted file reads
back as `unmanaged`, a dangling ref as `missing`, and nothing crashes — but the
design should avoid the case. **The rule is: adopt on trunk, plan on the lane.**
A `repoman plan` verb can enforce it by adopting before the lane exists.

This also explains why the earlier brainstorm felt wrong. It worked from the
pre-V2 control-plane API, where session state lived *inside* the engine
(`workspace.current`, `start-work`). V2 removed that on purpose and pushed it to
hosts. The rewrite did not rename verbs — it **moved the boundary to exactly
where RepoMan sits**.

## 6. Gaps against the manager contract

Three gaps. All are small, and each improves loci-core independently of RepoMan.

### G1 — no `doctor`

Every roster manager must have one (`src/repoman/registry.py:41`). loci has none.

The raw material is complete and already shipped:

| Signal | Source |
|---|---|
| vault not initialized | `VaultNotInitialized` from `load_vault` |
| broken links | `graph/broken_links` |
| ambiguous links | `graph/ambiguous_links` |
| broken heading/block anchors | `graph/broken_anchors` |
| missing attachments | `graph/missing_attachments` |
| orphaned documents | `graph/orphans` |
| cache health + revision | `maintenance/refresh` |

`loci doctor` is a thin composition over calls that exist. It belongs upstream,
because every other manager owns its own doctor.

### G2 — exit codes disagree

RepoMan's contract is `0/1/2/3` = ok / domain-decision / infra-config /
invalid-usage (`CONCEPT.md:35`).

loci today (`apps/cli/main.py`):

| Case | loci returns | Should return |
|---|---|---|
| success | `0` | `0` |
| any `LociError` — including `VaultNotInitialized`, `InfrastructureError`, `VaultPolicyError` | `1` | `2` for infra/config; `1` only for real decisions |
| unknown command, bad `key=value`, bad `--consistency` | `2` | `3` |

This matters because `repoman doctor` collapses sub-results with `worst_exit`
(`src/repoman/aggregate.py:94`), taking the maximum under severity order
`3 > 2 > 1 > 0`. Under today's mapping an uninitialized vault reports as "a
decision is needed" instead of "the configuration is broken", and a typo in a
command reports as infra failure. **The aggregate would lie.** The fix is roughly
twenty lines at the CLI boundary.

### G3 — `init` is not idempotent

`initialize_vault` uses exclusive-create and raises `FileExistsError`; the CLI
turns that into exit `1` (`apps/cli/main.py:186-188`). A shell hook that runs on every
entry needs either a guard (`[ -f .loci/vault.toml ] || loci init`) or an upstream
`init --if-missing`. Prefer the upstream flag: the guard duplicates knowledge of
the manifest path into a nix file.

### Not a gap — the disposable cache survives a version bump

Checked, because it would have been a fleet-wide risk. `CacheManager.ensure_schema`
compares a stored `compiler_schema` against `COMPILER_SCHEMA` and, on mismatch,
drops every table from `sqlite_master` and recreates the schema. The guard is
correct and its docstring records an earlier partial-drop defect that was already
fixed. Two loci builds sharing one vault is safe. See [`SPIKES.md`](SPIKES.md)
SP-2, which also reports an unrelated bug in loci-core's current working tree.

### Not a gap — `status` already works

`workspaces/list` takes zero arguments. On a fresh vault it returns
`{"workspaces": []}` at exit `0`. Verified. It is the correct `status` verb.

**Call it with `--consistency indexed`.** [`SPIKES.md`](SPIKES.md) SP-9 measured
the live repoman vault: `current` costs 1.5 s because it re-stats all 19 800 files
on disk, while `indexed` costs 0.17 s. Cost tracks files present, not documents
indexed. Staleness is safe here because loci reports the mode on every result and
never hides it. `doctor` keeps `current` — 1–3 s is fine for a health check.

## 7. Distribution

loci-core's remote is `git@github.com:Bullish-Design/loci-core.git` — private.
A `git+https://…` entry in the machine `repoman.lock` will not resolve on a
headless box. Four paths:

| Path | Mechanism | Cost |
|---|---|---|
| **A. Publish** | make the repo public; `git+https://…@vX.Y.Z` in the lock | a policy decision, not an engineering one |
| **B. ssh lock entry** | `git+ssh://git@github.com/…` | works on dev machines; CI needs keys |
| **C. vendomat wheel** | `wheel:loci-core>=0.5` from the wheelhouse | the proven fleet pattern (`git-pyjutsu`); adds a build step |
| **D. nix flake input** | presence-gated devenv module, the shellij pattern | **no packaging work at all** |

**Path D deserves the weight the earlier analysis never gave it.** loci-core
already ships a flake exposing `packages.loci-core` and `packages.loci-lsp`. The
binary is already in the user's system profile
(`/nix/store/…-python3.13-loci-core-0.3.0/bin/loci`). loci.nvim already consumes
it as a flake input over ssh. Path D sidesteps the private-package problem
instead of working around it, and RepoMan already has the mechanism: `docman.nix`
does presence-gated import, and `CONCEPT.md` §4 documents shellij as a
non-roster, input-gated default.

Path D's one weakness: a flake input is not on `PATH` for a bare shell, so
`repoman doctor` outside `devenv shell` cannot find the binary. `checks.py`
already models this case (`provisioned:<key>` warns when the input is absent).

## 8. Where loci does *not* fit

**It is not a "notes" manager, and must not be named one.** Name the roster key
`plan`. Planning is the phase; notes are the substrate. Naming the manager after
its substrate invites every future planning feature to be argued as "out of scope
for notes".

**It does not do tasks, issues, or features.** There is no task vocabulary in the
V2 engine. That scope belongs to foreman (§10).

**It is pre-1.0 with three schema fields.** `vault.toml` `schema = 1`, the owned
region `schema: 1`, and workspace `schema: 1`. Unknown or newer schemas block
rewrite rather than coercing data — the right behavior, and also the reason a
loci bump can hard-stop every repo in the fleet at once. Lockstep pinning is
mandatory, not optional.

**The `.loci/` name is already overloaded.** loci-core's own `.loci/README.md`
calls the double meaning *"the most likely way to misread this codebase"*: in the
product `.loci/` holds manifests, in that repository it also holds the project
record. See §10.

## 9. The four paths forward

| | Path | Fleet impact | Reversible | Delivers |
|---|---|---|---|---|
| **P1** | spine step only, no manager | none | trivially | documentation of the gap |
| **P2** | opt-in `situational` manager | none until opted in | yes | full conductor integration, per repo |
| **P3** | non-roster default (shellij pattern) | new repos only | yes | ambient availability, no conducting |
| **P4** | `core` default manager | every repo's doctor goes red | painful | planning on by default, everywhere |

### P1 — spine step only

Add `("plan", "plan")` to `SPINE`. `build_spine` renders only steps whose manager
is enabled (`src/repoman/skills.py`), so with no manager wired the lifecycle is
unchanged for every repo. Cost: one line plus a test.

**Value:** the generated entrypoint skill gains the phase the moment any repo
enables it, and the gap is recorded in code rather than in a scratch document.

### P2 — opt-in situational manager

1. Registry row: key `plan`, command `loci`, tier `situational`,
   `doctor=["doctor"]`, `status=["workspaces/list"]`,
   `route_when="plan a unit of work, or see what is in flight"`.
2. `modules/managers/loci.nix` — presence-gated input, the two aggregation tasks,
   the guarded init hook, and the current-workspace session state.
3. A `repoman.lock` entry under whichever distribution path §7 chooses.
4. Repos opt in with `repoman.managers = [ … "plan" ]`.

Under the toolchain install model, `checks.py` needs no new check: `lock:plan`,
`installed:plan`, and `skill:plan` fall out of the registry row.

**Under distribution path D it does.** `Manager.__post_init__`
(`src/repoman/registry.py:55`) accepts only `"toolchain"` and `"uv"`, and
`manager_binary` (`src/repoman/checks.py:146`) branches on the same two values.
A nix-provisioned manager lives in neither the toolchain venv nor the consumer
venv. Path D therefore needs a third install model, `install="nix"` — about a
day's work, and reusable, because shellij sits in the same position today. See
[`SPIKES.md`](SPIKES.md) SP-3.

**Requires G1, G2, and G3 first.** Without `doctor` the row cannot be written;
without the exit map the aggregate reports the wrong severity.

### P3 — non-roster default

Not in `repoman.managers` at all. copyroom's canonical template declares the
`loci` flake input; RepoMan presence-imports its module and runs the guarded init
hook. New repos get a vault and the CLI. Existing repos are untouched until they
converge.

**Gains:** no doctor red-line, no lock churn, no private-package problem.
**Loses:** no `repoman doctor` aggregation, no routing-table row, no spine step.
It is ambient, not conducted. shellij took this path deliberately.

P3 is a **delivery mechanism**, not an alternative to P2. The two compose: P3
provisions the binary and the vault; P2 conducts it.

### P4 — core default manager

P2 plus flipping the defaults. Note there are **two** defaults, and the earlier
proposal named only one:

- `src/repoman/registry.py:110` — `DEFAULT_MANAGERS`, consulted by `cli.py:68`
  only when `REPOMAN_MANAGERS` is unset, which means *outside* a managed shell.
- `modules/devenv.nix:70` — the nix option default, which sets
  `REPOMAN_MANAGERS` and therefore wins *inside* every managed shell.

Flipping one splits the truth: `repoman doctor` would report a different roster
in a bare shell than in `devenv shell`. Flip both or neither.

P4's cost is real and unavoidable. The moment `plan` is default, every existing
repo fails `lock:plan` / `installed:plan` and `repoman doctor` exits 2 until its
lock gains the entry and `repoman-sync` runs. That is the lock↔manager check
working correctly. The fix is copyroom convergence, sequenced as a rollout.

## 10. Decisions required before any code

### D1 — foreman's fate

`~/Documents/Projects/foreman` is scaffolded, RepoMan-managed, and empty (one
dependency: pydantic). It was scoped in
[`08-issue-feature-workflow-helpers/CONCEPT.md`](../08-issue-feature-workflow-helpers/CONCEPT.md)
to author work-items across TaskNotes, Allium specs, and numbered packets, over
knappy.

loci covers the substrate. It does not cover tasks or issues. So the two are
complementary in principle — but both claim the `plan` slot in the spine, and
only one can have it.

Note that project 08's CONCEPT cites
`loci-core/src/loci_core/domain/schema.py:82-86` as strategic validation. **That
file no longer exists.** It belonged to the pre-blue-sky-v2 engine. The
"loci deliberately excludes tasks/ and issues/" argument needs re-verification
against V2 before it is relied on again.

Three ways out:

1. **foreman on loci.** foreman becomes the `plan` manager and uses loci as its
   vault substrate instead of knappy. Most work; cleanest end state.
2. **loci is `plan`; foreman is `work`.** Two roster entries, two phases. Risks
   two managers negotiating one lifecycle step.
3. **Retire foreman.** loci takes the slot; work-item authoring stays a skill.
   Least work; loses the TaskNotes/Allium integration foreman was scoped for.

**Do not start P2 until D1 is answered.** Wiring loci as `plan` silently answers
it as (3).

### D2 — the `.loci/` convention collision

Every repo in the fleet keeps project records in `.scratch/projects/NN-name/`.
loci-core alone uses `.loci/projects/`, and un-excludes `.loci/**` from discovery
so that prose there is searchable.

If loci becomes standard, every repo gains a `.loci/` directory holding
manifests. That directory will look like an invitation to put project records in
it. Decide now:

- **Keep them separate.** `.loci/` is manifests only; `.scratch/projects/` stays
  the project record. Simple, and preserves the product meaning of `.loci/`.
- **Unify on `.loci/`.** The fleet adopts loci-core's convention, and project
  records become adoptable, searchable, graph-linked documents. Large upside, and
  it spreads the ambiguity loci-core's own README warns about.
- **Unify on `.scratch/`.** Vault discovery includes `.scratch/**`; `.loci/` stays
  manifests only. Keeps one meaning per directory and still makes the records
  first-class vault documents.

The third option looks best on the evidence, and is the cheapest to reverse.

### D3 — distribution path

§7. Recommend **D (flake input)** for provisioning, with **C (vendomat wheel)**
as the fleet fallback if a bare-shell `PATH` entry proves necessary. Path D costs
a third install model in the registry ([`SPIKES.md`](SPIKES.md) SP-3).

### D4 — vault granularity

Raised by [`SPIKES.md`](SPIKES.md) SP-4 and SP-5, and not considered before them.

A loci workspace references documents by id **within one vault**. Per-repo vaults
therefore make sixty islands: a planning record in repo A cannot name a document
in repo B. That matters, because fleet-wide planning is the scope fleetman and
foreman were both drawn for.

SP-4 shows the choice is **not** either/or. Document identity lives in the file's
frontmatter, not in a vault-local table. A parent vault indexes files inside a
child vault, reads the id already there, and refuses to re-adopt
(`already_managed`). Per-repo vaults and a fleet vault can coexist and share
identity.

| Option | Works today | Cost |
|---|---|---|
| **per-repo vaults only** | yes, with default discovery | no cross-repo planning |
| **one fleet vault** over `~/Documents/Projects` | needs custom discovery patterns (SP-5) | one vault root that is not a repo; unclear what gets committed |
| **both** — per-repo vaults plus a fleet vault | yes; identity is shared | two indexes over the same files; two caches |

SP-5 is the deciding evidence for now: default exclude patterns are anchored at
the vault root, so a fleet vault over `~/Documents/Projects` indexes every repo's
`node_modules/` and `.devenv/`. **Start per-repo.** The fleet vault stays
available later at no migration cost, because the ids are already in the files.

## 11. Recommended sequence

Staged P2 → P4, delivered through P3's mechanism.

| Step | Where | Gate |
|---|---|---|
| **0** | Answer D1, D2, D3, D4 | — |
| **1** | Fix `repoman doctor`'s remediation advice for partially-adopted repos (project 15, R1) | project 15 blocker closed |
| **2** | Upstream in loci-core: `loci doctor` (G1), the `0/1/2/3` exit map (G2), `init --if-missing` (G3). Tag v0.5.0 | `loci doctor` green on a fresh vault; exit codes verified |
| **3** | RepoMan: registry row `plan` + `("plan", "plan")` in `SPINE`. **Not** in defaults | `repoman managers` shows it; entrypoint renders the phase when enabled |
| **4** | `modules/managers/loci.nix`: presence-gated input, two tasks, guarded init, current-workspace session state | `repoman doctor` aggregates loci in an opt-in repo |
| **5** | loci-core exports its own skills via `copyroom agent-files export` | `skill:plan` passes; `docs/SKILLS.md:91` still true |
| **6** | Dogfood in repoman, loci-core, and one more repo | see §12 |
| **7** | copyroom template: flake input, lock entry, `.loci/` convention per D2 | new repos get it; existing repos unaffected |
| **8** | Flip **both** defaults (`registry.py:110` and `modules/devenv.nix:70`); bump the template; converge | fleet doctor green |

Steps 3 and 4 are reversible in one commit each. Step 8 is not.

### Step 5 in detail — skills

`docs/SKILLS.md:91` states the router is *"the only skill RepoMan installs"*, and
`src/repoman/devman/assets.py` and `install.py` are deleted (only stale `.pyc`
files remain). Do not resurrect that mechanism.

loci-core ships **seven** skills under `.agents/skills/`: `loci`, `loci-cli`,
`loci-python`, `loci-dev`, `loci-verify`, `loci-lsp`, `loci-importer`. Exporting
them is not a file copy. [`SPIKES.md`](SPIKES.md) SP-7 found three problems:

- **`loci-verify` collides with testee.** It triggers on `"run the tests"`,
  `"pytest"`, and `"coverage floor"` — the verify phase testee owns. Do not ship.
- **`loci-importer` collides and dangles.** It triggers on bare `"migrate"`,
  `"migration"`, `"dry-run"`, `"rollback"`, and it documents
  `tools/importer/importer.py`, which is not in the wheel
  (`packages = ["src/loci_core", "apps"]`). Do not ship.
- **The `loci` router names five sub-skills.** Copying it into a consumer repo
  produces four dangling routes — the exact failure RepoMan's entrypoint template
  exists to prevent. It must be **rendered from the shipped subset**.

One more fix before shipping: `loci`'s triggers include bare `"adopt"` and
`"adoption"`, which collide with copyroom's `"adopt a repo"` /
`"bring a repo under management"`. In loci, adoption gives a document an id; in
copyroom it brings a repo under a template. Narrow loci's to
`"adopt a document"` / `"adopt a note"`.

**Ship `loci-cli` and a rendered `loci` router.** `loci-python` is optional — the
`plan` phase drives the CLI. RepoMan ships nothing but its own generated routing
row.

## 12. The dogfood test (step 6 gate)

Default-on is justified only if the artifact is used, not merely written. The
gate is one question with an observable answer:

> After four weeks in three repos, are `.loci/workspaces/*.yaml` files **read**
> after they are written — by an agent resuming work, or by a human answering
> "what was this branch for" — or do they rot?

Concrete signals to record:

- number of workspaces created, and how many are later read or updated;
- whether `files:` refs stay accurate as code moves;
- whether an agent resuming a session actually opens the workspace before editing;
- whether anyone archives a workspace, or they accumulate;
- how often a workspace is invisible because it lives on another lane (SP-6).

A one-repo version of this test is already set up. [`SPIKES.md`](SPIKES.md) SP-8
created `.loci/workspaces/16-loci-plan-manager.yaml`, describing this project.
**It is not a valid gate yet:** nothing points an agent at `.loci/workspaces/`
until the router carries a `plan` row, so a negative reading today would prove
only that the pointer is missing. Read it after step 3, not before.

If the answer is "written once, never read", stop at P2 and leave it opt-in. That
is a successful outcome for this project, not a failure.

## 13. Verification log

Everything asserted above was checked against the code on 2026-08-19, not recalled.
Measurements and behavioural probes are in [`SPIKES.md`](SPIKES.md).

| Claim | How verified |
|---|---|
| current command surface | `loci --help` (installed 0.3.0) + `protocol/registry` wire names at HEAD |
| `init` writes one file | `loci init` in a fresh git repo; `find .loci -type f` |
| cache is outside the vault | `src/loci_core/fs/runtime.py`; `ls ~/.cache/loci/vaults/` |
| `workspaces/list` is a valid bare status verb | ran on a fresh vault → `{"workspaces": []}`, exit 0 |
| `workspaces/put` binds docs + files | ran with `--apply` against HEAD; inspected the YAML |
| adoption stamps three keys | inspected `docs/Roadmap.md` after adoption |
| no `doctor` exists | `loci --help`; grep over `apps/cli/main.py` and `protocol/registry.py` |
| exit-code mapping | `apps/cli/main.py:175,188,202,209,241-246` |
| `init` is not idempotent | `initialize_vault` raises `FileExistsError`; CLI returns 1 |
| vault-in-repo is designed for | `src/loci_core/vault/manifest.py:32` |
| git is never a dependency | `docs/USER.md` §9 |
| no session state in core | `docs/USER.md` §10; `.loci/README.md` |
| two independent defaults | `src/repoman/registry.py:110`, `modules/devenv.nix:70`, `src/repoman/cli.py:68` |
| `worst_exit` severity order | `src/repoman/aggregate.py:94-108` |
| RepoMan installs one skill | `docs/SKILLS.md:91`; `devman/assets.py` absent |
| loci-core ships its own skills | `ls loci-core/.agents/skills/` |
| loci-core is 3.13 | `loci-core/pyproject.toml:6` |
| RepoMan is already 3.13 | `pyproject.toml:10`, `devenv.nix:57`, `modules/scripts/repoman-sync.sh:189` |

### Corrections to the earlier brainstorm

The prior analysis proposed a registry row built on `loci doctor`,
`loci workspace.current`, `loci repository.init --vault`, `loci note.create`,
`loci start-work`, and `project.create`. **None of these exist**, in the installed
0.3.0 or at HEAD. They belong to the pre-blue-sky-v2 control-plane engine,
preserved at the tag `pre-blue-sky-v2`.

It also described a vault layout of `.loci/repository.json`,
`.loci/content/{notes,daily,scratch,projects}/`, `.loci/log/events.jsonl`,
`.loci/state/`, and `.loci/derived.sqlite`, and concluded that authoritative state
must be committed while derived caches are gitignored. The real layout is
`.loci/vault.toml` plus `.loci/workspaces/*.yaml`, with all derived state outside
the repo. Nothing needs gitignoring.

Two further claims did not hold: that loci-core depends on knappy (its
dependencies are pydantic, pyyaml, and pygls — the knappy relationship belongs to
foreman), and that adopting loci raises the family's Python floor to 3.13
(RepoMan has required 3.13 since testee 0.2.0; only `flake.nix` still builds
against `python312Packages`, which is a stale leftover worth fixing on its own).

## 14. Loose threads

- **`flake.nix` builds against `python312Packages`** while `pyproject.toml`,
  `devenv.nix`, and the toolchain venv are all 3.13. Unrelated to this project,
  cheap to fix, and it will confuse the next person who reads it.
- **Project 15 R1 is still open.** `repoman doctor` tells users to run
  `repoman-sync` in repos where that script cannot exist. Adding a manager on top
  of a broken adoption path multiplies the failure. This is step 1 for a reason.
- **loci-core is a RepoMan consumer.** Making it a manager creates a fleet cycle:
  `repoman.lock` would pin loci-core, and loci-core's devenv imports
  `repoman/modules`. Survivable — gitman/pyjutsu is the same shape — but it means
  a loci schema bump can red-line every repo including its own bootstrap. Path D
  (flake input) weakens the cycle, because provisioning stops going through the
  lock.

## 15. References

- `src/loci_core/vault/workspace.py` — the workspace manifest model
- `src/loci_core/vault/manifest.py` — `vault.toml`, discovery policy
- `src/loci_core/fs/runtime.py` — where cache and lock live
- `apps/cli/main.py` — the CLI boundary and exit codes
- `loci-core/docs/USER.md` §§8–10 — cache, git, sessions and workspaces
- `loci-core/.loci/README.md` — the two meanings of `.loci/`
- `src/repoman/registry.py` — the roster, `SPINE`, `DEFAULT_MANAGERS`
- `src/repoman/aggregate.py` — `worst_exit` and the `0/1/2/3` contract
- `modules/managers/docman.nix` — the presence-gated approach-B pattern
- `docs/SKILLS.md` — skill ownership, and why RepoMan installs only the router
- [`../15-loci-core-adoption-issues/ISSUES.md`](../15-loci-core-adoption-issues/ISSUES.md)
- [`../08-issue-feature-workflow-helpers/CONCEPT.md`](../08-issue-feature-workflow-helpers/CONCEPT.md)
