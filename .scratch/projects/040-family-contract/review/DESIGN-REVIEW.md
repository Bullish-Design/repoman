# Project 040 — design review: the family contract / man-core

**Review date:** 2026-10-07 (against RepoMan 0.10.0, post-release)
**Status of the design under review:** concept approved 2026-10-06; §9's six open
questions resolved 2026-10-07; `mancore` exists (7 modules, 705 source lines,
82 tests) with **no consumers yet** — per §7's "build with its own suite first."

## Sources reviewed

| Source | Evidence used |
|---|---|
| `.scratch/projects/040-family-contract/CONCEPT.md` | the design being reviewed (617 lines, §9 resolved) |
| `.scratch/projects/040-family-contract/STATUS.md` | rollout state; RepoMan 0.10.0 = migration step 0 |
| `/home/andrew/Documents/Projects/mancore/src/mancore/*.py` | the as-built library the design describes |
| `src/repoman/` — `registry.py`, `skills.py`, `cli.py`, `checks.py` | the code the design deletes or reshapes |
| RepoMan `CHANGELOG.md` 0.9.x–0.10.0 | what the fleet already removed and why |

RepoMan's copy of `CONCEPT.md` is the design record; `mancore`'s copy is
load-bearing. Line references below are to RepoMan's copy and to the current
source files — the migration plan (§7) is future work, so its counts were not
re-measured, only argued with.

---

## 1. Executive summary

The design is **sound and ready for migration**. Its three moves — state the
exit contract as code, invert the knowledge flow via capability manifests,
shrink RepoMan to lifecycle order only — are each independently justified, and
together they eliminate a real, measured defect class: six prose contracts that
drifted six ways (§1's table), and a RepoMan that hardcodes sibling facts and
"cannot fix this by being careful" (§2).

The exit-code decision (`0/1/2` + `130`, drop `3`) is correct and already at the
industry floor; the report envelope, the four-line wrapper, and the refusal to
add a fourth report level are all well-judged restraint. I found no flaw in the
contract itself.

The findings below are about **complexity the design still adds or keeps**, not
errors. Four findings are actionable (F1–F4); two are explicit calls to *stop
before simplifying further* (§5). The single most consequential one: **F1**, the
dual discovery channel, is the only place where the design makes the §2 mistake
structurally rather than accidentally — a permanent second source of the same
fact.

---

## 2. What the design gets right (verified)

These are worth recording, because migrations tend to erode them and future
sessions should defend them:

1. **`0/1/2` + `130` is the floor, not a compromise.** §1a's survey (grep,
   ruff, mypy, terraform) is right that the industry settled on three codes,
   and the "operational" justification — a CI step can swallow findings
   without swallowing a crash — is the correct reason. Dropping `3` loses
   nothing a caller branches on; the *reason* moves into the report.

2. **Exit codes come from exception types, not raise sites** (§4.1). This is
   the load-bearing rule. gitman's 158 raise sites, each picking a number, are
   158 chances to drift; the design moves that choice to class definitions and
   makes "a finding is a return value, never an exception" the second half of
   the rule. This directly kills copyroom's 36-site findings-as-faults bug
   class.

3. **The fault-beats-finding rule was reused, not designed** (§9, decision 6).
   Lifting testee's existing `overall_status` semantics (`infra_error` beats
   `failed`) into `exit_for` unchanged is the cheapest possible correct answer.

4. **Doctor's failed check becomes a finding (`1`), not a fault (`2`)** (§4.2).
   Counter-intuitive but right, and devman was already doing it — the doc
   correctly identified the "odd one out" as "the one that had been right."

5. **`worst_exit` is correctly condemned.** The measured fact — linkman's five
   failure classes collapse to one, a copyroom infra fault surfaces as a
   domain decision; "RepoMan's aggregate exit code carries less information
   than any single input it consumes" — is the strongest single sentence in the
   doc and fully justifies deleting aggregation.

6. **§9's fourth decision refuses a fourth report level**, and the fifth
   distinguishes state-rendering from history-enumeration instead of adding
   mechanism. Both are the design choosing vocabulary over structure.

7. **The migration order is cheapest-first and proof-before-risk** (§7:
   testee's near-no-op proves behaviour-neutrality before gitman's 219
   assertions are touched). RepoMan 0.10.0 is correctly identified as the
   step-0 blocker (Vendomat pinned 0.7.5 with `aggregate.py` still present).

8. **§8 knows its own hazards.** Version strings not identifying behaviour,
   `extra="forbid"` making report-model fields a breaking read, gitman's two
   doctor JSON shapes — the doc does not flatter its migration.

---

## 3. Findings

Severity: **High** = affects a §9 decision before migration starts;
**Medium** = change target designs in §4/§6 before consumers exist;
**Low** = optional, becomes harder to fix later but is cheap now.

### F1 (High) — The dual discovery channel contradicts the design's own thesis

**Where:** §4.6 ("RepoMan prefers the closure manifest, and falls back to one
subprocess per manager") and §9 decision 2 (both channels, manifest preferred,
subprocess fallback).

**The problem.** The doc's §2 thesis is: *every drift item was one instance of
RepoMan asserting facts it does not own*, and the cure is one source per fact.
The dual-channel decision creates **two sources for the same fact**
(each manager's capability) with an unstated consistency rule between them:

- `discover.py` must implement both reads plus a preference rule;
- Vendomat's V4 must implement the bake step and a build helper;
- the two representations must be tested to agree;
- any drift between a baked capability and a tool's live `capability` output is
  a new bug class the design does not name.

And what it buys: discovering 3–5 capabilities by subprocess, **once per
`repoman doctor` or router render**, costs milliseconds. The doc's own words for
the manifest path are "a thin optimization."

**Recommendation.** Amend §9 decision 2 to state the channel lifecycle
explicitly. Either:

- **(a) Pure subprocess** — declare the subprocess path *the* channel. Add the
  manifest only if a measured need appears (there is none visible). Cheapest;
  today's default already works and depends on no Vendomat work; or
- **(b) Replace, don't add** — keep the plan, but commit in writing that when
  Vendomat bakes the manifest, the subprocess path is *deleted in the same
  release*, not retained as a fallback. Two channels coexisting permanently is
  the outcome to forbid; it re-creates §2's disease structurally.

Option (a) is strictly simpler and nothing else in the design depends on (b).

### F2 (Medium) — The `Capability` schema is fatter than its two consumers need

**Where:** §4.6; as-built `mancore/capability.py` (`key`, `command`, `phase`,
`activity`, `skill`, `install`, `route_when`, `doctor`, `status`, `verdict`).

**The problem.** The registry-drift lesson generalizes: *every field a sibling
must maintain is a permanent drift surface, times seven tools.* The current
registry (`src/repoman/registry.py`) shows what the doctor and router actually
consume per manager. Auditing fields against that:

- **`doctor`** is `["doctor"]` for every entry in the registry. If that is a
  fixed point across the family, the field is dead weight: the probe is
  `argv[0] + " doctor"`. If it is not a fixed point for some future tool, add
  the field *then*.
- **`install`** (`"toolchain" | "uv"`) exists so the doctor picks `uv:<key>`
  vs `lock:<key>`. That is **detection, not declaration** — the doctor can
  probe the consumer's `pyproject.toml` and never ask the sibling. Deleting
  the field also deletes a way for a sibling to configure RepoMan's doctor
  by mistake.
- **`verdict`** exists to reconcile `testee list-runs` (exits `0`, correctly,
  per §9's fifth decision) with status-shaped commands that do carry verdicts.
  Reasonable — but note the cheaper shape: `status: None` for testee. If the
  field's only live consumer is one edge case, prefer omitting `status` to
  annotating it.
- **`skill`** defaults to `command` (as-built). Only entries that differ need
  the field; consider whether any do today. If none, delete now and re-add on
  need — `schema_version` exists precisely to make that safe.

**Recommendation.** Before any tool ships a `Capability`, cut the schema to the
fields the router and doctor provably read: `key`, `command`, `phase |
activity`, `route_when`, and at most `status`. Every cut removes §7 migration
toil in the same repository it removes drift from. Revisit after step 8, not
before — once seven tools publish the current shape, every field becomes
load-bearing for compatibility.

### F3 (Medium) — The spine's canonical order lives in three places

**Where:** `mancore/capability.py` (`Phase = Literal["change", "verify",
"integrate"]` — order implied, not stated), each tool's `Capability.phase`
declaration, and RepoMan's planned `spine.py` ("the ordering. This is the
product", §6).

**The problem.** The target state names the phase order in a type literal
(where sequence is convention, not data), in per-tool declarations, and in a
RepoMan module. That is the registry mistake one level up: once capabilities
declare `phase`, RepoMan needs **no ordering table at all**:

- spine = the canonical enumeration of `Phase` *stated once in mancore* (a
  three-element tuple next to the literal), with `change` always rendered for
  every roster;
- activities = declared `activity` values, unordered by construction;
- **`spine.py` as a module may not need to exist** — the ordering collapses to
  "render phases in mancore's canonical order, then activities, filtered by
  roster."

Two corollaries:

- mancore's `Phase` should carry the enumeration as a module-level constant, or
  the "order" of the literal is folklore.
- validation should state (in the `Capability` model, which already enforces
  phase-XOR-activity) whether *two tools may declare the same phase*. If two
  can, the router needs a tiebreak rule that no document currently gives; if
  one cannot, say so in the model now, while no tool has shipped a wrong
  declaration.

**Recommendation.** One source for the order (mancore), one source per
membership claim (each capability), zero ordering tables in RepoMan. Note in
§6 that `spine.py`'s content is two laws in prose plus an import, and delete the
`SPINE`/`ACTIVITIES` tuples from `registry.py` in step 9 without re-embodiment.

### F4 (Medium) — `install-skills` contradicts "RepoMan writes only the router"

**Where:** §6's target module list omits `skills.py`/`install-skills` silently —
it is neither in "kept" nor "deleted." As-built, `src/repoman/skills.py` (117
lines) + `repoman install-skills` + doctor lint still install and check
manager-skill links, while `AGENTS.md` states "RepoMan writes only the router"
and the fleet runs a dedicated link plane (`devman-link reconcile` + linkman)
whose *job* is installing declared links.

**The problem.** The design document deletes eight things by name and keeps two
by name, and leaves the skills seam unsigned. That seam is the last surviving
piece of hard aggregation: RepoMan placing links it believes managers need.
Under the inversion, "which skill a manager has" is already a capability
field, and "installing links" is the link plane's. The doctor's expected-links
lint survives either way — it is a *check*, and checks are supposed to feather
the nest of the capability join (§6 already moves the expected skill set to
"an on-disk join").

**Uncertainty, honestly stated:** I have not verified whether devman-link's
declaration model covers pool-manager skills (the repo's docs say "a person
writes each pool link by hand"). If it does, `install-skills` is duplicate
machinery; if writing links by hand is intentional, then `install-skills`
automating it contradicts that intent *and* is the thing to question. Either
answer simplifies RepoMan; the ambiguity is the defect.

**Recommendation.** Give `install-skills` an explicit verdict in §6 — delete
(move to the link plane), or keep with a one-line rationale ("devman-link
covers pool links only; manager skills are RepoMan's one write"). Do not leave
it unlisted: unsigned seams are how this repo's previous versions accumulated
`aggregate.py`.

### F5 (Low) — The fault subclass triad is presentation-only; accept it, on the record

**Where:** §4.1 — `UsageFault` / `ConfigFault` / `EnvFault` all carry
`FAULT`; the doc itself concedes "a caller cannot act differently on them, but
a human can."

**The problem.** Redundant structure: one `ManError` carrying `remedies`
(the gitman pattern the doc already adopts) plus an optional `kind` tag would
do the same with one class.

**Recommendation.** **Keep it.** The subclasses cost nothing at runtime, they
localize error copy, and — decisively — they make the migration's raise-site
edits mechanical (gitman's 83 sites at `3` become `UsageFault` by search and
replace, not by judgement). This is complexity serving the migration, which is
the only kind of complexity §7 needs. Record the justification in §4.1 so a
future session does not relitigate it.

### F6 (Low) — Report envelope: two fields worth a second look

**Where:** §4.4 — `Report` carries `command` and `notes` alongside
`tool`/`tool_version`/`exit_code`/`rows`.

- `command` is derivable by the caller (it invoked it) and by `mancore`'s
  wrapper; it is a convenience field with no consumer named in the doc.
- `notes` has no rule for what goes in it versus a `Row` with
  `level="warn"` — an escape hatch beside a structured one is how dialects
  start again.

**Recommendation.** Dropping `notes` is probably right: a free-text list with
no rendering rule is the seed of the next report drift. Dropping `command` is
cosmetic; keep if any fleet consumer reads piped JSON blind. Cheap to decide
now; both become compatibility surface the moment testee migrates (step 1).

---

## 4. Hazards (§8) review — three gaps worth closing

The known-hazards list is unusually honest. Three additions, in §8's own style:

1. **Doctor's fail moving `2 → 1` inverts the meaning of "nonzero" for
   existing *gates* silently.** §8 notes callers treating nonzero as fatal
   "keep working" — but `[publish] verify`-style gates that treat nonzero as
   *fatal* will now **stop hard on findings they used to tolerate**, if the
   finding/fault border moved underneath them. The audit §8 prescribes should
   be per-call-site, and the example should say "a gate, not a script."

2. **The subprocess fallback (if F1(b) is kept) hides a *capability schema
   mismatch*.** An older tool's `capability` output missing a newer field
   behaves like `Pydantic ValidationError` → exit `2` → doctor row "fault."
   That is correct §0/1/2 behaviour but will be *read* as "manager broken"
   during rollout, when it means "manager not yet migrated." The migration
   deserves a doctor row that distinguishes "not migrated yet" from "faults"
   — even if the distinguishing rule is just the tool's version.

3. **`extra="forbid"` (§8, testee) plus F2's schema cuts are in tension.** If
   fields are cut *after* tools publish them, older readers hard-reject newer
   manifests. The window to apply F2 is exactly now — before step 1 — and the
   review recommends treating the capability schema as frozen from testee's
   migration onward, additive-only after that.

---

## 5. Where NOT to simplify further (restraint record)

So that the next simplification pass does not relitigate settled ground:

- **The exit contract is at the floor.** `0/1/2` + `130`. No further collapse
  is possible without merging findings into faults, which is the bug being
  fixed.
- **The wrapper is four lines of real logic** (§4.3). Dropping `standalone_mode`
  is already the simplification; do not add a per-tool configuration lever to
  it to serve hypothetical cases — §4.3's table shows Click's defaults are
  already correct for 3 of 5 cases.
- **The migration's breadth is not complexity.** copyroom's 36 sites, gitman's
  58 triage sites, docman's inverted shell children — the plan is long because
  the disease is long. Trimming §7 would only defer, not remove, work each
  tool must do anyway.
- **`schema_version: Literal[1] = 1` on both models** is one field each and is
  the mechanism that makes F2's cuts and all future additive changes safe.
  Keep.

---

## 6. Recommended deltas to §9 (decision changes)

Only decision 2 changes; one gains a clarifying sentence. Regret-minimizing:
all proposed deltas shrink work.

| # | §9 decision | Change |
|---|---|---|
| 1 | Raw subprocess discovery is the channel | **Amend:** the closure-manifest path, if it is ever built, *replaces* the subprocess path in the same release. Two coexisting channels are forbidden (F1). |
| 2 | §6 module list | **Add:** an explicit verdict on `install-skills`/`skills.py` — delete into the link plane, or keep with a one-line reason (F4). |
| 3 | §4.6 `Capability` schema | **Cut before testee migrates:** `doctor` (fixed point: `<command> doctor`), `install` (detection, not declaration), `skill` if no live entry differs from `command`. Freeze the schema additive-only from step 1 (F2, §4 hazard 3). |
| 4 | mancore `capability.py` | **Add:** `PHASE_ORDER: tuple[Phase, ...]` constant beside the literal; state in the model docs whether two tools may share a phase (F3). |

None of these change the migration order, any tool's exit codes, or the
contract. All four are cheaper now than after step 1, and step 0 (this
release) is unaffected.

---

## 7. Verdict

**Approve for migration, with the §6 deltas above applied before step 1
(testee).** The design's diagnosis is measured and correct; its contract is at
the simplicity floor; its hardest call (doctor's fail = finding = `1`) is right.
The findings are all of one kind — places where the cure for stale hardcoded
facts risks re-creating a smaller, distributed version of the same disease —
and all four are fixable with deletions before the first consumer locks them
in. The one sentence I would add to §2, as the design's own enforcement rule:

> Any fact the family shares must have exactly one published source; a second
> source may exist only while replacing the first, never beside it.

— because that sentence, applied consistently, is what F1–F3 all say.
