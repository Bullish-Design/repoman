---
loci:
  schema: 1
  id: 01a01b22-19f4-7000-a204-356f9228e41c
  projects: []
---
# SPIKES — measurements taken before committing to the plan

Run 2026-08-19 against loci-core HEAD (v0.4.1 + 23 commits) and the installed
profile build (0.3.0). Every temp vault was removed afterwards.

Companion to [`CONCEPT.md`](CONCEPT.md). Findings that change the plan are folded
back into it; this file is the evidence.

**What SP-8 left behind in this repo.** No tracked file was modified. SP-8
created an untracked `.loci/` (the vault manifest plus one workspace manifest)
and stamped a `loci:` frontmatter region into this file and `CONCEPT.md` — both
of which SP-8 itself created. `git status` shows only `?? .loci/` and
`?? .scratch/projects/16-loci-plan-manager/`. To undo: `rm -rf .loci` and delete
the two frontmatter blocks. `loci-core` was read only; its cache
(`~/.cache/loci/`) was wiped once and rebuilt, which is by design.

---

## SP-1 — Cost of a vault in a real repo

**Question.** Can an `enterShell` hook and a `doctor` afford to touch a vault?

**Method.** Copied repoman's tracked files (128 files, 84 Markdown) to a temp
directory, ran `init` then `documents/list` cold and warm. Repeated against
loci-core's own vault (288 documents, 233 managed) after wiping its cache.

| Vault | Cold (full rebuild) | Warm |
|---|---|---|
| repoman-sized, 84 docs | 0.57 s | 0.21 s |
| loci-core, 288 docs / 233 managed | 2.95 s | 0.29 s |

**Finding.** Cost is acceptable. A guarded init hook (`[ -f .loci/vault.toml ]`)
costs nothing. A warm `repoman status` costs ~0.2 s, in line with the other
managers. A `doctor` that forces a full rebuild costs ~3 s on a large vault — so
`loci doctor` should use `current` consistency and not force a rebuild.

**Impact on the plan.** None. Proceed.

## SP-2 — Cache behaviour across engine versions

**Question.** Two loci builds will exist on one machine — the system profile and
whatever a repo pins. What happens when they share a vault?

**Method.** Wrote a cache with the installed 0.3.0, read it with the loci-core
working tree.

**Observed.**

```
$ loci --json documents/list                 # 0.3.0 writes the cache
{"ok": true, …}
$ python -m apps.cli.main --json documents/list   # working tree reads it
{"ok": false, "error": {"kind": "OperationalError",
                        "message": "no such column: observed_kind"}}
exit=1
```

**Finding — the engine is fine; the working tree is not.** `CacheManager.ensure_schema`
in HEAD compares a stored `compiler_schema` against `COMPILER_SCHEMA = 7` and,
on mismatch, calls `_rebuild_locked`, which drops **every** table from
`sqlite_master` and recreates the schema. That is a correct guard, and its
docstring records an earlier partial-drop defect (S2) that was already fixed.

The failure above is not version skew. It comes from **uncommitted changes in the
loci-core working tree** that add an `observed_kind` column *without* bumping
`COMPILER_SCHEMA`. `git show HEAD:…/compiler/index.py` has no `observed_kind`;
the worktree has five references.

**Two consequences.**

1. **For the integration:** no risk. The cross-version story is sound. Do not
   plan around it.
2. **For whoever owns that branch:** bump `COMPILER_SCHEMA` to `8`. Until then
   every warm cache raises `OperationalError` until manually wiped, and the error
   escapes loci's own boundary contract — `sqlite3.OperationalError` is not a
   `LociError`, so it falls through to the generic handler and reports the wrong
   error kind.

**Impact on the plan.** Removes a risk the CONCEPT had not accounted for. Adds an
upstream bug report unrelated to this project.

## SP-3 — Does a nix-provisioned manager fit the registry?

**Question.** The CONCEPT recommends distribution path D (flake input, the
shellij pattern) and claims `checks.py` needs no new check.

**Method.** Read `registry.py:50-56` and `checks.py:146-160`.

**Finding — the claim is wrong.** `Manager.__post_init__` raises on any install
model other than `"toolchain"` or `"uv"`:

```python
if self.install not in {"toolchain", "uv"}:
    raise ValueError(f"{self.key}: unknown install model {self.install!r}")
```

`manager_binary` branches on the same two values: `toolchain` resolves
`<toolchain-venv>/bin/<command>`, anything else resolves the consumer venv's bin.
A nix-provisioned manager is on `PATH` from the flake and lives in neither place.

**Path D therefore needs a third install model,** `install="nix"`:

- accept it in `__post_init__`;
- `manager_binary` returns `None` so `resolve()` falls back to `shutil.which`
  (`aggregate.py:59` already handles `None`);
- the `lock:<key>` check must not demand a `repoman.lock` entry — provisioning
  comes from `devenv.yaml`, not the machine lock;
- `provisioned:<key>` becomes the load-bearing check, as it already is for docman.

Roughly a day of work, not a line. It is also **reusable** — shellij is in the
same position today and is kept out of the roster partly because of it.

**Impact on the plan.** Step 4 grows. Path D is still right; it is not free.

## SP-4 — Nested vaults and document identity

**Question.** If per-repo vaults exist and a fleet-wide vault is ever created over
`~/Documents/Projects`, do they corrupt each other?

**Method.** Built a parent vault containing a child vault, adopted a document in
the child, then tried to adopt the same document from the parent.

**Observed.**

```
child cwd  → documents/list → ['docs/A.md']                     # nearest vault wins
parent cwd → documents/list → ['fleet.md', 'repo-a/docs/A.md']  # parent sees through
parent     → documents/adopt path=repo-a/docs/A.md --apply
             {"ok": false, "error": {"kind": "InvalidRequestError",
                                     "message": "adoption refused: ('already_managed',)"}}
```

**Finding — nesting is safe, and identity is global.** `find_vault_root` walks up
and stops at the nearest `.loci/vault.toml`. A parent vault indexes files inside a
child vault, reads the id already written into the file's frontmatter, and refuses
to re-adopt. Because the id lives in the file rather than in a vault-local table,
per-repo vaults and a fleet vault can coexist and **share document identity**.

**Impact on the plan.** The vault-granularity question (new decision D4) is not
either/or. That materially widens the options.

## SP-5 — Discovery excludes are anchored at the vault root

**Question.** Follows from SP-4. If a fleet vault is viable, what does it index?

**Method.** Put Markdown files in the parent's `.devenv/`, and in the child's
`.devenv/` and `node_modules/`. Listed from the parent.

**Observed.**

```
['fleet.md',
 'repo-a/.devenv/state/junk.md',        ← indexed
 'repo-a/docs/A.md',
 'repo-a/node_modules/pkg/README.md']   ← indexed
# '.devenv/top.md' at the parent root was correctly excluded
```

**Finding.** The default exclude patterns (`.devenv/**`, `node_modules/**`, …)
match only at the vault root. A nested repository's build artifacts are indexed.
This is exactly the failure the `manifest.py:32` comment describes — *"a walk of
this repo alone yields 13 846 tier-2 link targets, 11 627 of them build
artifacts"* — reappearing one directory down.

**Two consequences.**

1. **A fleet-wide vault needs custom discovery patterns** (`**/.devenv/**`,
   `**/node_modules/**`, …). It does not work out of the box.
2. **Per-repo vaults work with the defaults unchanged.** This is a real argument
   for per-repo granularity beyond convenience.

Worth raising upstream: the shipped defaults would be strictly better as `**/`-
prefixed patterns. The cost is a slightly wider match; the benefit is that the
nested-repo case, which the comment shows the author already had in mind, works.

**Impact on the plan.** Feeds decision D4. Does not block anything.

## SP-6 — Workspaces and version-control lanes

**Question.** `.loci/workspaces/*.yaml` is a tracked file. Does a workspace travel
with the lane that created it, or is it repo-wide state? What happens on a merge?

**Method.** Built a colocated jj repo (jujutsu 0.43.0) with a vault and two
documents. Made a base change, then two sibling lanes. Created a workspace on
lane-a, switched to lane-b, observed. Then adopted the *same* document on lane-b
and merged the two lanes.

**Observed — lane isolation is total.**

```
lane-a: workspaces/put name=feature-a documents=docs/Roadmap.md --apply
jj new <base>                       # switch to lane-b

$ ls .loci/workspaces/              → (no workspaces dir)
$ loci workspaces/list              → []
$ head -3 docs/Roadmap.md           → "# Roadmap"      (no loci: region)
```

**Finding 1 — the plan travels with the change.** Both the workspace manifest and
the adoption stamp are tracked-file edits, so they belong to the lane. loci's
cache handled the worktree changing underneath it: `workspaces/list` returned
`[]`, not a stale lane-a answer.

This cuts both ways. A workspace describing a unit of work lands together with the
code that implements it — arguably ideal. But **you cannot see what is in flight
on other lanes.** `repoman status` on lane-b reports zero workspaces while lane-a
has one. "What am I working on across this repo" is unanswerable from one
worktree.

**Observed — the hazard is dual adoption.**

```
lane-a: docs/Roadmap.md  id: 01a01b1f-f8cd-7000-bf99-59bae521fad0
lane-b: docs/Roadmap.md  id: 01a01b20-3ca5-7000-ba4d-e3c885d7abba   # different uuid7
jj new <lane-a> <lane-b>
Warning: There are unresolved conflicts at these paths:
docs/Roadmap.md    2-sided conflict
```

**Finding 2 — two lanes adopting the same document produce two ids and a
frontmatter conflict.** The workspace YAMLs themselves merged cleanly (different
filenames), but they then reference *different* ids for the same document, so
resolving the conflict to one id leaves the other workspace holding a dangling
ref.

**Finding 3 — loci degrades honestly rather than lying.** Checked in the
conflicted worktree:

```
$ loci --json documents/list        exit 0
  docs/Roadmap.md   state=unmanaged  identity=none  id=None    # markers → unparseable → unmanaged
$ loci --json workspaces/get workspace_id=<feature-a>
  "documents": [["01a01b1f-…", "member", null, "missing", ""]]  # dangling ref reported as missing
```

No crash, no stale answer, no invented id. This is the "total parse, never crash"
and "missing refs intact" discipline holding under a case the engine was not
explicitly built for.

**Impact on the plan.** Two changes to §5 of the CONCEPT. First, "which workspace
is current" is not the only host-owned fact — **where a workspace lives in the
lane graph** is a second one, and RepoMan is the only component positioned to
answer it. Second, the design must discourage adopting the same document on two
lanes. The cheapest rule: **adopt on trunk, plan on the lane.** A `repoman plan`
verb can enforce it by adopting before the lane is created.

## SP-7 — Which loci skills may ship to sixty repos

**Question.** loci-core ships skills under `.agents/skills/`. Which are
consumer-facing, and do any collide with the managers already in a RepoMan repo?

**Method.** Read all seven skills' frontmatter (the CONCEPT said six — there is
also `loci-python`). Compared trigger keywords against copyroom's canonical set,
gitman's skill, and RepoMan's generated router. Checked wheel packaging.

| Skill | Lines | Verdict | Why |
|---|---|---|---|
| `loci-cli` | 226 | **ship** | every trigger is namespaced (`documents/adopt`, `loci --vault`, `workspaces/put`). No collisions. This is the skill the `plan` phase needs. |
| `loci` | 73 | **ship, regenerated** | the router. Its route table names five sub-skills that would not be installed — see below. |
| `loci-python` | 252 | **optional** | clean namespaced triggers (`Loci.open`, `AdoptRequest`). Needed only by a repo that drives the kernel from Python; the `plan` phase uses the CLI. |
| `loci-lsp` | 136 | **do not ship** | editor-host operation. Clean triggers, but irrelevant to the lifecycle. |
| `loci-dev` | 210 | **do not ship** | how to change loci-core itself. |
| `loci-verify` | 93 | **do not ship — collides** | triggers on `"run the tests"`, `"pytest"`, `"coverage floor"`. **testee owns verify in a RepoMan repo.** Shipping this puts two skills on the same lifecycle phase. |
| `loci-importer` | 74 | **do not ship — collides and dangles** | triggers on bare `"migrate"`, `"migration"`, `"dry-run"`, `"rollback"` — generic enough to fire on database or template work. It also documents `tools/importer/importer.py`, and `[tool.hatch.build.targets.wheel] packages = ["src/loci_core", "apps"]` — `tools/` is not in the wheel, so the file it describes does not exist in any consumer install. |

**Finding 1 — export is not a file copy.** The `loci` router's route table names
`loci-cli`, `loci-python`, `loci-verify`, `loci-lsp`, `loci-importer`, and
`loci-dev`. Copying it into a consumer repo produces four to five dangling routes.
RepoMan's own entrypoint template exists precisely to avoid this — it renders only
enabled managers, "no dangling routes". The loci router needs the same treatment:
**rendered from the shipped subset, not copied.**

**Finding 2 — one keyword collision in the skill we do want.** `loci`'s triggers
include bare `"adopt"` and `"adoption"`. copyroom's canonical set claims
`"adopt a repo"`, `"adopt this repo"`, and `"bring a repo under management"`.
In loci, adoption means giving a document an id; in copyroom it means bringing a
repo under a template. Bare `"adopt"` is the broader match and will fire on
copyroom's territory. Narrow it to `"adopt a document"` / `"adopt a note"` before
shipping.

**Impact on the plan.** Step 5 is bigger than "loci-core exports its skills." It
is: split the set, narrow two keywords, and render the router from the subset.

## SP-8 — Does an agent read a workspace? (setup)

**Question.** The one assumption the project rests on. §12 of the CONCEPT is the
four-week version; this is the free one-repo version.

**Method.** Initialized a vault in this repo and created a workspace for this
project, adopting only files this session created:

```
$ loci workspaces/put name=16-loci-plan-manager \
    documents=.scratch/projects/16-loci-plan-manager/CONCEPT.md,…/SPIKES.md \
    files=src/repoman/registry.py,src/repoman/checks.py,modules/devenv.nix --apply
workspace: .loci/workspaces/16-loci-plan-manager.yaml
adopted:   ['…/CONCEPT.md', '…/SPIKES.md']
$ git status --short
?? .loci/
?? .scratch/projects/16-loci-plan-manager/
```

**Status: set up, not concluded.** The artifact now exists and describes real
work. The observation belongs to a later session.

**The honest caveat, and it matters.** Nothing yet *points* an agent at
`.loci/workspaces/`. In the real design the router's `plan` row is the discovery
path. So a negative result read today would prove only that the pointer is
missing, not that the artifact is useless. **SP-8 is not a valid gate until step 3
(the registry row) exists** — which reorders the CONCEPT's step 0a.

The observable, for when it is valid: does a session resuming this project open
`16-loci-plan-manager.yaml` before editing, and does the `files:` list stay
accurate as the work moves?

## SP-9 — Consistency mode dominates cost on a real repo

**Question.** SP-1 measured a 128-file copy. What does a live repo cost, with
`.devenv/` and its 19 800 files on disk?

**Method.** Timed the live repoman vault (97 documents indexed, 19 800 files
present) in both consistency modes.

| Query | Mode | Time |
|---|---|---|
| `documents/list`, cold | `current` | 2.27 s |
| `documents/list`, warm | `current` | 1.17 s |
| `documents/list`, warm | `indexed` | **0.18 s** |
| `workspaces/list`, warm | `current` | 1.51 s |
| `workspaces/list`, warm | `indexed` | **0.17 s** |

**Finding.** Cost tracks **files on disk, not documents indexed.** `current`
re-stats the tree on every query, so the excluded 19 700 files are still walked.
`indexed` skips the walk and is 7–9× faster.

**Impact on the plan — a concrete design rule.**

- `repoman status` → `workspaces/list --consistency indexed`. 0.17 s, in line with
  the other managers. Staleness is safe here because loci **reports** the mode and
  never hides it.
- `repoman doctor` → `current` is correct and affordable (1–3 s for a health
  check).

This supersedes SP-1's conclusion that a warm status costs ~0.2 s: that holds only
with `indexed`, or in a repo without a large build directory.

---

## What these change

| | Before | After |
|---|---|---|
| cross-version cache risk | unassessed | none — guard verified (SP-2) |
| `install="nix"` | "no new check needed" | a third install model, ~1 day (SP-3) |
| vault granularity | not considered | new decision **D4**, options widened (SP-4, SP-5) |
| workspace scope | assumed repo-wide | **per-lane** — plan travels with the change (SP-6) |
| cross-lane visibility | assumed free | impossible from one worktree; a new host-owned fact (SP-6) |
| dual adoption | not considered | two lanes → two ids → frontmatter conflict; rule: adopt on trunk (SP-6) |
| skill export | "loci-core exports its skills" | split 7, drop 2 for collisions, **render** the router (SP-7) |
| `repoman status` cost | ~0.2 s | 1.5 s with `current`; **use `indexed`** (SP-9) |
| SP-8 as step 0a | a free pre-gate | invalid until the registry row exists (SP-8) |

## The rules these produce

Design constraints the implementation must carry, each earned by a measurement:

1. **`repoman status` uses `--consistency indexed`; `doctor` uses `current`.** (SP-9)
2. **Adopt on trunk, plan on the lane.** A `repoman plan` verb should adopt
   documents before the lane exists, so two lanes never mint two ids for one
   document. (SP-6)
3. **RepoMan owns two ephemeral facts, not one:** which workspace is current, and
   where it sits in the lane graph. (SP-6)
4. **Ship `loci-cli` plus a rendered `loci` router. Never ship `loci-verify` or
   `loci-importer`.** (SP-7)
5. **`install="nix"` before path D.** (SP-3)
6. **Per-repo vaults, defaults unchanged.** A fleet vault stays available later at
   no migration cost. (SP-4, SP-5)

## What remains open

**SP-8's observation.** Set up, not concluded, and not a valid gate until the
registry row gives an agent a reason to look. Re-sequence: the row (step 3) comes
first, then SP-8 becomes real.

**Cross-lane visibility.** SP-6 showed `repoman status` cannot see other lanes'
workspaces. Is that acceptable, or does RepoMan need to read workspace manifests
out of other lanes (`jj file show <rev> .loci/workspaces/`)? This is a design
question, not a spike — it depends on whether "what is in flight across this repo"
is a question the `plan` phase must answer. Decide it with D1–D4.

**Nothing else blocks step 1.**
