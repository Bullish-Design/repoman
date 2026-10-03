# CONCEPT — `foreman` (work-item authoring for the fleet)

> **One `*man`-family tool that turns a rough intent into a coherent work-item —
> a leaf (issue) or a tree (feature) — authored across your real backends
> (Obsidian TaskNotes, Allium specs, numbered project packets) and kept in sync.**
> Exposes two agent skills (`issue`, `feature`) + `promote` over one shared core.

Settled design. Substrate questions are resolved; this is the blueprint the
KICKOFF will turn into work. Companion docs: [`SEED.md`](SEED.md) (raw ask +
decisions), [`CONTEXT.md`](CONTEXT.md) (the backends as a composer sees them).

---

## 1. What `foreman` is

A single thin **orchestration** tool — it authors and reconciles, it doesn't
store. It composes existing siblings; it reimplements neither vault I/O, spec
authoring, nor VC. It owns only the *opinions* the substrates leave out
(slugging, status vocab, templates, linking, drift).

One repo, **two agent skills** (two clear entry points) over one shared core:
- **`issue`** — leaf-first. Captures a single actionable work-item → a TaskNotes
  task. Reactive, low-ceremony (depth **L0**).
- **`feature`** — tree-first. Captures a capability → a contract (spec) + a plan
  (packet) + linked leaves (tasks), kept coherent. Proactive (depth **L2**).
- **`promote`** — grows a leaf into a tree (L0→L2) in place.

> **Why one repo, not two** (reversed from the initial instinct, on evidence):
> the two skills are ~90% the same engine — they differ only by *profile*
> (interview depth, default materialization depth). Two repos would have required
> a *third* shared-core lib (3 repos); one repo makes the shared core just the
> package `src/`, makes **promotion in-process** (it's intrinsically within-system
> — a leaf deepening into a tree), and gives repoman one manager to wire instead
> of three. The leaf↔tree continuum (§2) is literally "one tool, pick your depth."

Ships **as agent skills first** (Phase 1); designed to grow into a full `*man`
manager wired into repoman (devenv module + Typer CLI + registry), like
`copy`/`git`/`test`.

## 2. The core model: leaf vs tree (+ promotion)

The mental model the two skills are profiles over, mapped onto the backends:

| | **Issue** | **Feature** |
|---|---|---|
| shape | a **leaf** (one actionable item) | a **tree** (contract + plan + leaves) |
| backends | a TaskNotes task | spec + packet + tasks, linked |
| posture | reactive / small | proactive / large |
| skill | `foreman issue` (depth **L0**) | `foreman feature` (depth **L2**) |

**Materialization depth** (you pick how much of the tree to create, not à-la-carte
backends):
- **L0 — leaf only** → a task. (`issue` default.)
- **L1 — leaf + packet** → a task plus a lightweight plan, no formal spec.
- **L2 — full tree** → spec + packet + linked tasks. (`feature` default.)

**Promotion** is now trivial: `issue` makes an L0 leaf carrying the work-item slug;
`foreman promote <slug>` grows the packet+spec around it and adopts the existing
task as leaf #1. Same package, same identity scheme — nothing re-created.

## 3. The composition stack (compose, don't reimplement)

| Facet | Composed backend | Mechanism |
|---|---|---|
| leaf task + feature **project note** | **knappy** | `Task(...)`/`Note(...)` subclass → `.save()` into the vault |
| spec (the contract) | **allium-env** | drive the `elicit` skill → `.allium` |
| packet (the plan) | **numbered-dir convention** | template file-writes (README/KICKOFF/guides) |
| version control | **gitman** | specs + packets are git-tracked, per-repo |
| fleet scope | **fleetman** | cross-repo discovery / "all features" rollup |

**Strategic validation:** `loci-core` (a sibling co-owned-markdown engine on
knappy) **deliberately excludes `tasks/` and `issues/`** from its content homes —
its `_TYPE_BY_DIR` leaves them as "adopt-only forward-decls" because *TaskNotes
owns task/issue authoring* (`loci-core/src/loci_core/domain/schema.py:82-86`).
`foreman` fills exactly that acknowledged gap.

## 4. Coherence & the vault↔repo bridge — **decision: (3) field-ownership**

A work-item projects into facets living in two sync domains: the **global Obsidian
vault** (tasks + the feature's project note) and the **per-repo git tree** (spec +
packet). "Kept linked" is handled two ways at once:

- **Leaf↔feature edge = Obsidian-native.** A TaskNotes task carries
  `projects: ["[[<slug>]]"]`; leaves roll up under the feature's project note
  automatically. No manifest needed for this edge.
- **Vault↔repo edge = field ownership** (NOT two-way sync). Each fact has exactly
  one owning side, so reconciliation is a one-way *drift report*, never a merge:

| Fact | Owner |
|---|---|
| spec (`.allium`), packet (README/KICKOFF/guides) | **repo** (git, reviewed, public-OK) |
| leaf tasks + their `status`/`scheduled`/`priority` | **vault** (TaskNotes) |
| feature↔leaf edges | **vault** (wikilink) |
| vault↔repo pointers (repo, spec path, packet path) | **write-once at creation, mirrored** |
| derived feature status | **computed**, cached both sides, never hand-authored |

```
VAULT (global, private)                   REPO (per-project, git, public-OK)
  Tasks/<slug>-wire-config.md               .scratch/specs/allium/<slug>.allium   ← contract
    projects: ["[[muse/oauth-login]]"]      .scratch/projects/NN-<slug>/          ← plan
    tags: [task]                              README.md · KICKOFF.md · NN-*.md
  Projects/muse/oauth-login.md  ◀──────┘      feature.toml (minimal, self-describing)
    frontmatter: repo, spec, packet, status      ↑ mirrors the project-note pointers
       └ tasks roll up here (native)  ──────────►┘
```

`foreman status`/`doctor` reads the vault face (via knappy) and the repo face (via
files) and reports drift — *spec newer than leaves*, *task done but packet stale*,
*vault note missing*, *dangling pointer* — the same convergence ethos as
`repoman doctor`. **Status is derived**, not authored (all leaves `done` + spec
has no open questions ⇒ feature done); a manual override is allowed.

### Decision: (2) slug namespacing — **repo-scoped**
The vault is one global store across ~89 repos, so slugs collide. Namespace by
repo: the project note is `Projects/<repo>/<slug>.md`, the wikilink is
`[[<repo>/<slug>]]`. Fleet-spanning features use a `fleet/` namespace. Mirrors the
`new-project` collision-check ethos.

### Decision: (3) privacy — **spec+packet in git, planning in vault**
Specs and packets are development artifacts and already live in repos by existing
convention — they stay git-tracked (public-OK). The personal planning/scheduling/
status layer lives vault-side in the project note. This *is* the field-ownership
split, so privacy needs no extra mechanism.

## 5. Borrowed conventions (proven by muse + loci-core)

The core reuses patterns already validated in the fleet rather than inventing them.

**From `muse` (wikilink-native vault authoring):**
- **Subclass knappy `Note`/`Task`** for typed models (`muse/src/muse/domain.py`);
  wrap `Vault` with a thin delegating class + a `TypeRegistry` for read-promotion
  (`muse/src/muse/vault.py:26-63`).
- **Central `path_pattern` routing table** — one `SchemaSpec` per type declares its
  folder pattern; `spec_for(model)` is the only lookup (`muse/src/muse/schema.py:70-94`).
- **`slugify`** (lowercase, non-alnum→`-`, cap 80 on word boundary) +
  **`_free_path`** collision loop `<slug>-2/-3.md` (`muse/src/muse/workflows.py:50-56,110-124`).
- **`StrEnum` + `field_serializer` shim** for status/priority — ruamel can't emit a
  StrEnum member, so keep the enum, serialize `.value` (`muse/src/muse/domain.py:80-89`).
- **Wikilinks** as `f"[[{target.path.stem}]]"`, stored in typed
  `list[Annotated[str, Link]]` fields, not body text (`muse/src/muse/domain.py:28-36,102-120`).
- **Vault from env** (`$MUSE_VAULT`-style); subfolders from the pattern table.

**From `loci-core` (the harder machinery — the reconciler especially):**
- **Port/adapter single-seam:** knappy imported in exactly ONE module behind a
  `Protocol` (`loci-core/.../vault/gateway.py:8-20,49-76`) → swappable for an
  Obsidian-live adapter later.
- **`to_frontmatter()` → strict Pydantic boundary**, native `tags` vs `properties`
  catch-all split, **preserve-unknown `patch_frontmatter`** (`gateway.py:163-242`).
- **Two-gate vocab doctrine:** read models are vocab-*tolerant*; the closed vocab
  is enforced only at the **write gate** and the **doctor gate**
  (`loci-core/.../domain/vocab.py`, `domain/doctor.py:161-178`).
- **`adopt` = idempotent identity-upsert** (valid id ⇒ no write) — promotion's
  foundation (`gateway.py:265-295`).
- **`scan → snapshot → plan → apply` reconciler** with drift classification
  `{in_sync, drift, adopt, orphan}`, bumping `updated` only on real change
  (`loci-core/.../domain/reconcile.py:123-287`) — the blueprint for our drift report.

**Divergences we own:** loci links by id not wikilinks and manages its own
`.loci/content/` space (not the user's real Tasks/ folder); neither sibling
authors knappy `Task` objects. So we take muse's *real-vault wikilink authoring* +
loci's *reconciler/adopt/vocab machinery* and combine them. Project-note
templating has no fleet precedent (muse has no MOC) — we author it with ruamel
CommentedMap + `---`-fence assembly (no Jinja, per house style).

## 6. Architecture: one package, two skill profiles

```
foreman/  (one *man repo)
  .agents/skills/
    foreman-issue/SKILL.md      leaf-first profile (L0)
    foreman-feature/SKILL.md    tree-first profile (L2)   ── Phase 1 ships THESE
  src/foreman/                  the shared core (no separate lib needed)
    vault/gateway.py            knappy port/adapter (single seam)
    model.py                    Task/ProjectNote subclasses · status vocab · Link helpers
    slug.py / paths.py          slug + path_pattern routing (repo-namespaced)
    spec.py                     dispatch → allium `elicit`
    packet.py                   numbered-dir renderer
    item.py                     work-item identity · depth L0/L1/L2 · adopt/promote
    reconcile.py                scan→snapshot→plan→apply drift report
    cli.py                      Typer: issue · feature · promote · status · doctor
```

The shared engine (interview ⇄ research → render → dispatch → reconcile) lives
once as the package; `issue`/`feature` are thin profiles over it (interview depth,
default depth, templates). Collapsing to one repo means the "shared core" need not
be its own published lib — it's just `src/foreman/`.

## 7. The skill surface (Phase 1 — what we build first)

Two agent skills, each **interview-led AND research-capable**:
`interview ⇄ research → synthesize artifact → dispatch → confirm`.
- **Interview:** reuse Allium's `elicit` discovery patterns for `feature`; a
  lighter interview for `issue`.
- **Research:** spawn `Explore`-style sub-agents to "figure out how best to do
  something" before authoring (exactly how this packet was built).
- **Dispatch:** author the leaf/project-note via knappy; the spec via `elicit`;
  the packet via the numbered-dir template; link them (repo-namespaced wikilinks).
- **`promote`:** a third skill/verb that runs `adopt` then deepens L0→L2.
- **Scope:** per-repo by default (repoman ethos), fleet-wide mode via `fleetman`.

Phase 1 is **markdown skills only** — zero Python deps; the `src/` engine above is
the Phase-2 target the skills are written to anticipate.

## 8. End-state: one full `*man` manager

When the CLI lands, `foreman` wires into repoman via the standard external-tool
seams (see CONTEXT.md "manager-wiring seams") — **one** of each:
- `registry.py` `Manager(key="work", command="foreman", tier="situational",
  status=[...], skill="foreman", ...)`.
- `allManagers` enum + `./managers/foreman.nix` import in `modules/devenv.nix`.
- a pure-Python `modules/managers/foreman.nix` (model on `testee.nix`) exposing
  `repoman:work:issue|feature|promote|status` tasks.
- a `[managers.work]` block in `repoman.lock`.
Born via the `new-project` skill (`copyroom new gh:Bullish-Design/template-py` →
wire repoman → `fleetman index`). CLI contract per family: `doctor`
(`--json`/`--repo-root`, exit 0/2), `init`, a status verb, `install-skills`; exit
codes `0/1/2/3`. The single manager installs **both** sub-skills.

## 9. Decisions locked

1. **One repo, one `*man` manager**, two agent skills (`issue` + `feature`) +
   `promote`, over one shared core (the package `src/`). **Skills-first.**
2. Name: **`foreman`** (collision-checked clean, 2026-06-30; family `*man`,
   layer `tool`).
3. Boundary model: **leaf vs tree + promotion**; depth levels L0/L1/L2.
4. Backends: **knappy** (tasks/notes) + **allium-env** (specs) + **numbered
   packets** + **gitman/fleetman**. NOT taskman/Taskwarrior, NOT GitHub Issues.
5. Architecture: shared core IS the package (no separate lib); two thin profiles.
6. Coherence: vault↔repo **field-ownership (option 3)**; Obsidian-native leaf
   linking; derived status.
7. Slug namespacing: **repo-scoped** (`[[repo/slug]]`).
8. Privacy: **spec+packet in git, planning in vault** (= the field split).

## 10. Open questions / next steps

- **Project-note template** — no fleet precedent; design the frontmatter + body
  shape (pointers to repo/spec/packet, derived status, task rollup section).
- **`foreman` ↔ loci-core** — both are knappy consumers; define whether they
  coexist (likely orthogonal: loci owns `.loci/content/`, foreman owns real
  vault Tasks/Projects) or share a future gateway lib. Surface, don't block.
- **Vault config discovery** — env (`$VAULT`/TaskNotes `data.json` `tasksFolder`)
  vs a repo `.loci/repository.json`-style config. Lean env for Phase-1 skills.
- **Status vocab** — adopt loci-core's `Literal[...]` set or TaskNotes defaults
  (`open|in-progress|done`); reconcile the two.
- **NEXT:** write the **KICKOFF** (Phase-1 skills-only: birth `foreman` via
  `new-project`, author the `issue` + `feature` skills, no Python lib yet) + a
  `01-*` guide.
