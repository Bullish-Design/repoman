# OPTIONS — how far to take the loci integration

**Status:** decision pending. Nothing is implemented.
**Date:** 2026-08-19.
**Decides:** whether, and how far, to act on
[`../16-loci-plan-manager/CONCEPT.md`](../16-loci-plan-manager/CONCEPT.md).
**Evidence:** [`../16-loci-plan-manager/SPIKES.md`](../16-loci-plan-manager/SPIKES.md)
— nine measurements. Every claim below traces to one of them or to a cited file.

Project 16 asked *how* loci-core could fill RepoMan's missing `plan` phase, and
answered it. This document asks *whether to*, and at what depth. It presents five
bundles (§3), four independent sub-decisions (§4), a comparison (§5), and a
recommendation (§6).

---

## 1. The fork underneath all of it

loci gives you a **data model, not a workflow.**

`workspaces/put` is a roster editor. A workspace manifest holds a name, an optional
project, ordered document refs, linked file paths, and an `archived` flag. That is
the whole surface. There is no "start work", no "what is in flight", no "close this
out", and no `current` — deliberately, and stated as a design decision in
`docs/USER.md` §10: *"There is no `current`, no activation, no editor state in
core. A host opens a workspace and owns an ephemeral session."*

So the question is not "do we adopt loci." It is:

> **Who supplies the planning workflow, and how thick is it?**

Three answers exist, and they are what separates the options below:

| Answer | Thickness | Option |
|---|---|---|
| Nobody — record the gap only | none | B |
| RepoMan, thinly: a `plan` pass-through plus session state | ~200 lines | C, D |
| foreman, richly: work items, status, cross-repo rollup | a new tool | E |

## 2. What is already settled

The options are read against this. None of it is in dispute; all of it is measured
or read from source.

**loci fits a code repo by design.** Its default discovery policy excludes `.git`,
`.jj`, `.venv`, `.devenv`, `node_modules`, `dist`, `build`, and `result*`, under
the comment *"a vault is often also a code repository (M3)"*
(`vault/manifest.py:32`). `docs/USER.md` §9: *"Git is an opportunity, never a
dependency."* It will not fight gitman.

**The committed footprint is two files.** `loci init` writes `.loci/vault.toml`.
`workspaces/put` writes `.loci/workspaces/<name>.yaml`. Cache and lock live in
`~/.cache/loci/`, keyed by vault id and canonical root. Nothing needs gitignoring.

**Three contract gaps, all small.** No `doctor` (the raw material — `graph/*`,
`maintenance/refresh`, `VaultNotInitialized` — is complete). Exit codes are
`0/1/2` where RepoMan's contract is `0/1/2/3`, so `worst_exit` would misreport
severity. `init` is not idempotent. Together: two to three days upstream.

**`status` is solved, with a caveat.** `workspaces/list` takes zero arguments and
exits 0 on a fresh vault. It must be called with `--consistency indexed`: SP-9
measured 1.51 s versus 0.17 s on the live repoman vault, because `current`
re-stats all 19 800 files on disk regardless of the 97 indexed.

**The plan travels with the lane.** SP-6: a workspace manifest is a tracked file,
so it belongs to the change that created it. On a sibling lane, `workspaces/list`
returns `[]` and the adopted documents have no `loci:` region. Good — the plan
lands with the code. Also structural — **no single worktree can answer "what is in
flight across this repo"**, and loci cannot answer it either, because the fact is
not in the vault.

**Dual adoption is the one hazard.** Two lanes adopting the same document mint two
uuid7 ids and conflict in frontmatter on merge, leaving one workspace with a
dangling ref. loci degrades honestly throughout — a conflicted file reads back as
`unmanaged`, a dangling ref as `missing`, nothing crashes. The rule that follows:
**adopt on trunk, plan on the lane.**

**Adoption has no CLI reverse.** The states are `unmanaged` / `managed` /
`invalid_managed` (`docs/USER.md` §3). To un-adopt, hand-delete the `loci:` block —
which works, because files are authority, but there is no verb. Every option that
adopts documents carries this soft lock-in.

**Skills cannot be exported as-is.** SP-7: loci-core ships seven skills.
`loci-verify` triggers on `"run the tests"` and `"pytest"` — testee's phase.
`loci-importer` triggers on bare `"migrate"` and documents `tools/importer/`,
which is not in the wheel. The `loci` router names five sub-skills, so copying it
yields four dangling routes. Ship `loci-cli` and a **rendered** router.

**`install="nix"` does not exist.** `registry.py:55` accepts only `"toolchain"`
and `"uv"`; `checks.py:146` branches on the same two. Any nix-provisioned manager
needs a third model. About a day.

---

## 3. The five options

### Option A — Stop here

Close the project. Keep 16's CONCEPT and SPIKES as the record of why.

**Effort:** zero.

**Pros.**
- No new dependency in any repo.
- No pre-1.0 engine with three schema versions entering the fleet.
- The analysis is banked. It stays valid until loci's command surface changes.

**Cons.**
- The lifecycle gap stays undocumented in code. It exists only in a scratch
  directory, where the next person will not find it.
- This has already been re-derived once from a dead API. Stopping guarantees it
  happens again.

**Implications.**
- foreman stays a scaffold indefinitely, and D1 goes unanswered by default.
- Planning stays in context windows. Every session re-derives what a change is for.

**Opportunities.**
- The three upstream loci fixes are worth doing regardless. `loci doctor`, a
  correct exit map, and idempotent `init` are hygiene, not integration work.
- The `COMPILER_SCHEMA` bug SP-2 found still needs reporting.

**What would change my mind:** evidence that nobody will read a workspace
manifest. That is exactly what SP-8 tests, and it cannot be read yet.

**Reversal cost:** none. Every other option stays open.

---

### Option B — Spine step only

Add `("plan", "plan")` to `SPINE` in `src/repoman/registry.py`. `build_spine`
renders only steps whose manager is enabled, so no repo's lifecycle changes today.

**Effort:** hours. One line, one test, one line in `CONCEPT.md`'s roster table.

**Pros.**
- Records the gap in code rather than in a scratch document.
- Zero fleet impact, zero dependency, zero risk.
- The generated entrypoint gains the phase the moment anything fills it — no
  second change needed later.
- Trivially reversible.

**Cons.**
- Delivers no capability. Nobody can plan anything with it.
- A phase with no owner may read as an oversight rather than a placeholder, unless
  the registry comment says so explicitly.

**Implications.**
- Commits to the *shape* — planning is a lifecycle phase, ordered after scaffold —
  without committing to the *filler*.
- Keeps A, C, D, and E all open.

**Opportunities.**
- Cheapest way to make the gap visible to every agent that reads the router. That
  visibility may itself surface how people want it filled, which is better
  evidence than speculation.

**What would change my mind:** nothing. B is cheap enough to be correct under
almost any answer to the larger question.

**Reversal cost:** one commit.

---

### Option C — loci as an opt-in `plan` manager

The full conductor integration, opt-in per repo. Repos enable it with
`repoman.managers = [ … "plan" ]`.

**Effort: ~1.5–2 weeks.**

| Work | Estimate |
|---|---|
| Upstream: `loci doctor`, `0/1/2/3` exit map, `init --if-missing`, tag | 2–3 days |
| `install="nix"` third install model in registry + checks | 1 day |
| Registry row + `SPINE` entry + tests | half a day |
| `modules/managers/loci.nix`: presence-gated input, two tasks, guarded init, session state | 1–2 days |
| Skill split, keyword narrowing, rendered router | 2 days |
| Tests, docs, `CONCEPT.md` roster row | 2 days |

**Pros.**
- Full conductor integration. `repoman doctor` aggregates it, `repoman status`
  reports it, the router routes to it, `repoman managers` lists it.
- Blast radius is one repo at a time. Nothing changes for a repo that does not
  opt in.
- The workflow layer stays thin, and sits exactly where loci left room for it: a
  `repoman plan` pass-through plus current-workspace state under `$DEVENV_STATE`.
  RepoMan does not reimplement anything loci owns.
- Every piece is reversible in one or two commits.

**Cons.**
- You are building a workflow on a roster editor. If planning turns out to need
  dependencies, status transitions, or cross-repo rollup, you will extend RepoMan
  into foreman's territory one ad-hoc verb at a time — and RepoMan's whole design
  law is that it reimplements nothing.
- SP-6's lane isolation means `repoman status` is structurally partial. It reports
  this lane's workspaces and cannot see others. That is not a bug to fix later; it
  follows from the manifest being a tracked file.
- Adoption's missing reverse means every planning document you adopt keeps its
  frontmatter unless hand-edited.

**Implications.**
- RepoMan gains a fourth manager and a pre-1.0 dependency carrying three schema
  versions (`vault.toml` `schema`, the owned region `schema`, workspace `schema`).
  Unknown or newer schemas block rewrite rather than coercing — correct behavior,
  and also a hard stop when versions drift.
- loci-core becomes both a RepoMan consumer and a RepoMan manager. That is a fleet
  cycle. Survivable — gitman/pyjutsu has the same shape — but a loci schema bump
  can red-line loci-core's own bootstrap.
- The `adopt on trunk, plan on the lane` rule has to be taught somewhere an agent
  will read it. The `plan` skill row is the natural place.

**Opportunities.** Three real byproducts, each worth something independent of this
project:

1. **`install="nix"` unblocks shellij.** shellij is kept out of the roster today
   partly because no install model fits a flake-provisioned tool
   (`CONCEPT.md` §4). One day of work fixes two problems.
2. **The rendered-router pattern generalizes.** copyroom has the same
   tool-shipped-skills problem, and `docs/SKILLS.md` lists conflict precedence as
   a standing open question. SP-7 forces a real answer, reusable by every manager
   that ships skills.
3. **`files:` binds prose to code.** Once vaults exist, `graph/backlinks` answers
   "which documents describe this module?" That is a docman opportunity as much as
   a planning one, and it costs nothing extra.

**What would change my mind:** SP-8 reading negative after step 3, or the D1
answer landing on foreman.

**Reversal cost:** low. Remove the registry row, the nix module, and the lock or
input entry. Vaults left behind in opted-in repos are inert — two files and some
frontmatter.

---

### Option D — loci as a default `plan` manager

Option C, then flip both defaults and converge the fleet.

**Effort:** C, plus roughly a week of convergence and fallout across ~60 repos.

Note there are **two** defaults, and only flipping both keeps the truth consistent:

- `src/repoman/registry.py:110` — `DEFAULT_MANAGERS`, read by `cli.py:68` only
  when `REPOMAN_MANAGERS` is unset, which means *outside* a managed shell.
- `modules/devenv.nix:70` — the nix option default, which sets `REPOMAN_MANAGERS`
  and therefore wins *inside* every managed shell.

Flipping one makes `repoman doctor` report a different roster in a bare shell than
in `devenv shell`.

**Pros.**
- Planning is on everywhere. That is the original ask.
- New repos get it from copyroom's canonical template with no per-repo decision.
- The fleet gets one planning convention instead of sixty improvisations.

**Cons.**
- The moment `plan` is default, every existing repo fails `lock:plan` /
  `installed:plan` and `repoman doctor` exits 2 until its lock gains the entry and
  `repoman-sync` runs. That is the lock↔manager check working exactly as designed.
  It is still sixty red doctors until convergence lands.
- A loci schema bump can then red-line the entire fleet at once, including
  loci-core's own bootstrap through the cycle.
- Repos that will never hold a planning note still carry `.loci/` and the
  dependency.

**Implications.**
- Reversing this is a second fleet-wide convergence, not a revert.
- The rollout must be sequenced: template lock and input first, then the flip, then
  `copyroom converge`. A silent default flip breaks every repo before the template
  can fix it.

**Opportunities.**
- **This is the option that unlocks a fleet vault later at zero migration cost.**
  SP-4 established that ids live in files and nested vaults are safe: a parent
  vault reads a child's ids and refuses to re-adopt (`already_managed`). Once every
  repo has adopted documents, a vault over `~/Documents/Projects` inherits the
  whole graph. Cross-repo planning becomes a discovery question rather than a
  migration.

**What would change my mind:** SP-8 reading positive across three repos over four
weeks. Without that, D is a fleet-wide commitment with no evidence behind it.

**Reversal cost:** high. A second convergence, plus inert `.loci/` directories in
every repo.

---

### Option E — Build foreman on loci; foreman owns `plan`

loci becomes the substrate. foreman supplies the workflow: work-item authoring,
status vocabulary, cross-repo rollup through fleetman.

**Effort:** C, plus building foreman. Weeks to months — it is a scaffold with one
dependency (pydantic) today.

**Pros.**
- The workflow layer lives where it was designed to live, not smeared into
  RepoMan. This preserves RepoMan's law: it sequences and aggregates, and
  reimplements nothing.
- Answers the two questions loci structurally cannot: what is in flight across
  lanes, and across repos.
- Resolves D1 by construction rather than by default.

**Cons.**
- By far the most work, and the longest time to first value.
- **foreman's own CONCEPT is built on a stale premise.** It cites
  `loci-core/src/loci_core/domain/schema.py:82-86` as strategic validation for
  "loci deliberately excludes tasks/ and issues/". That file belonged to the
  pre-blue-sky-v2 engine and no longer exists. The knappy-versus-loci substrate
  question needs re-deciding before a line is written.
- Two managers in the roster where one phase exists, unless foreman fully absorbs
  the loci surface and RepoMan routes only to foreman.

**Implications.**
- The routing chain becomes RepoMan → foreman → loci. Each hop must justify itself.
- foreman inherits every constraint in §2, plus its own.

**Opportunities.**
- The only option that reaches TaskNotes and Allium.
- The only one where `documents/set_status` — loci's single shared-property
  writer — becomes a real status machine instead of a curiosity.
- The only one that makes `.scratch/projects/NN/` records into first-class loci
  projects, with `graph/project_members` giving reverse membership for free.

**What would change my mind:** evidence that thin planning is enough. C running
successfully for a month would be exactly that.

**Reversal cost:** highest. A built tool is hard to un-build.

---

## 4. The four independent sub-decisions

These are orthogonal to the bundle. Answer them separately.

### D2 — the directory convention

Every repo in the fleet keeps project records in `.scratch/projects/NN-name/`.
loci-core alone uses `.loci/projects/`, and un-excludes `.loci/**` from discovery
so prose there is searchable. Its own `.loci/README.md` calls that double meaning
*"the most likely way to misread this codebase."*

| Option | Pros | Cons |
|---|---|---|
| **Keep separate** — `.loci/` is manifests only | one meaning per directory; simplest | project records stay outside the graph |
| **Unify on `.loci/`** — fleet adopts loci-core's convention | records become adoptable, searchable, linkable | spreads the ambiguity to sixty repos |
| **Vault discovers `.scratch/**`** — `.loci/` stays manifests only | one meaning per directory **and** records in the graph | one extra line of discovery policy per vault |

**Recommend the third.** It gets the upside of unification without the naming
collision, and it is the cheapest to reverse.

### D3 — distribution

loci-core's remote is private, so a `git+https://` lock entry will not resolve
headless.

| Option | Pros | Cons |
|---|---|---|
| **Publish the repo** | simplest possible lock entry | a policy decision, not an engineering one |
| **ssh lock entry** | works on dev machines today | CI needs keys |
| **vendomat wheel** | the proven fleet pattern (`git-pyjutsu`) | adds a build and publish step |
| **flake input** (shellij/docman pattern) | no packaging work; loci-core already ships `packages.loci-core`, and the binary is already in the system profile | needs `install="nix"`; not on `PATH` in a bare shell |

**Recommend the flake input,** with the vendomat wheel as fallback if bare-shell
`PATH` resolution proves necessary. It sidesteps the private-repo problem instead
of working around it, and `install="nix"` is work you want anyway (see C's
opportunity 1).

### D4 — vault granularity

A workspace references documents by id **within one vault**. Per-repo vaults make
sixty islands.

| Option | Works today | Cons |
|---|---|---|
| **Per-repo** | yes, defaults unchanged | no cross-repo planning |
| **One fleet vault** | **no** — SP-5: default excludes are root-anchored, so it indexes every nested repo's `node_modules/` and `.devenv/` | needs custom discovery patterns; unclear what gets committed |
| **Both** | yes; SP-4 proved identity is shared | two indexes and two caches over the same files |

**Recommend per-repo now.** SP-4 established that nothing is lost by waiting: ids
live in the files, so a fleet vault added later inherits the graph at no migration
cost. SP-5 is the reason not to start there.

Worth raising upstream regardless: the shipped exclude defaults would be strictly
better `**/`-prefixed.

### Cross-lane visibility (new, from SP-6)

`repoman status` on one lane cannot see another lane's workspaces.

| Option | Pros | Cons |
|---|---|---|
| **Accept partial status** | honest; costs nothing | "what is in flight" is unanswerable from one worktree |
| **Read other lanes** (`jj file show <rev> .loci/workspaces/`) | complete answer | RepoMan parses loci's format out of band — breaks the pass-through law |
| **Adopt on trunk, plan on the lane** | removes the dual-adoption hazard; keeps ids stable | does not by itself restore cross-lane visibility |

**Recommend the third plus the first.** Adopt on trunk to kill the id conflict,
and accept that status is per-lane. If cross-lane rollup turns out to matter, that
is evidence for Option E, not for teaching RepoMan to read YAML.

---

## 5. Comparison

| | A stop | B spine | C opt-in | D default | E foreman |
|---|---|---|---|---|---|
| Effort | 0 | hours | 1.5–2 wk | +1 wk | months |
| Delivers capability | no | no | yes, per repo | yes, everywhere | yes, richest |
| Fleet blast radius | none | none | opted-in repos | **all repos** | all repos |
| New dependency | none | none | pre-1.0 loci | pre-1.0 loci | loci + foreman |
| Reversal cost | none | 1 commit | low | high | highest |
| Answers "in flight across repo" | no | no | **no** | no | yes |
| Answers "in flight across fleet" | no | no | no | later, free | yes |
| Forecloses | nothing | nothing | nothing | E gets harder | nothing |
| Evidence behind it | n/a | n/a | SP-1…SP-9 | **none yet** | none yet |

Two rows carry most of the weight. **"Evidence behind it"** — D is the only option
committing the whole fleet, and it is the option with no supporting evidence.
**"Forecloses"** — C forecloses nothing, which is what makes it a safe next step
rather than a bet.

---

## 6. Recommendation

**B now. C next. D only after evidence. E stays open.**

**Why B now.** Hours of work, records the gap where it belongs, and keeps every
other option open. There is no argument against it.

**Why C next.** The work is bounded and each piece stands alone. The three
upstream loci fixes are hygiene. `install="nix"` pays for itself by unblocking
shellij. The registry row and nix module are one commit each to revert. And C is
the only way to make SP-8 a valid test — without the router row, nothing points an
agent at `.loci/workspaces/`, so a negative reading today would prove only that
the pointer is missing.

**Why not D yet.** D commits sixty repos to a pre-1.0 engine on the strength of a
hypothesis. Run C, dogfood for four weeks in three repos, then decide. The dogfood
question and its signals are in
[`../16-loci-plan-manager/CONCEPT.md`](../16-loci-plan-manager/CONCEPT.md) §12.

**Why E stays open.** E is the better end state *if* planning needs real workflow.
Committing now means months before anything works, on a CONCEPT that needs
re-verification first. C does not foreclose it: if foreman gets built, it takes the
`plan` row and loci moves underneath it. C's thin workflow layer is then either
absorbed or deleted — a few hundred lines either way.

### The sequence

| Step | Work | Gate |
|---|---|---|
| 1 | Fix project 15 R1 — `doctor` remediation for partially-adopted repos | project 15 blocker closed |
| 2 | **Option B** — `SPINE` entry, no manager | tests green |
| 3 | Answer D2, D3, D4, cross-lane | recorded in §8 below |
| 4 | Upstream loci: `doctor`, exit map, `init --if-missing`; tag | `loci doctor` green on a fresh vault |
| 5 | `install="nix"` in registry + checks | shellij could use it too |
| 6 | Registry row + nix module + rendered skill subset | `repoman doctor` aggregates loci in an opt-in repo |
| 7 | **SP-8 becomes valid.** Dogfood in 3 repos, 4 weeks | see CONCEPT §12 |
| 8 | Decide D — flip both defaults, converge — or stop at C | fleet doctor green, or a recorded "no" |

Steps 2, 5, and 6 are each reversible in one or two commits. Step 8 is not.

## 7. Do these regardless of the answer

1. **Fix project 15 R1.** `repoman doctor` currently tells users to run
   `repoman-sync` in repos where that script cannot exist. Adding a manager on top
   multiplies the failure. This is step 1 for a reason.
2. **Report the `COMPILER_SCHEMA` bug.** loci-core's working tree adds an
   `observed_kind` column without bumping `COMPILER_SCHEMA` from `7`. Every warm
   cache raises `OperationalError` until wiped, and the error escapes loci's own
   boundary contract — `sqlite3.OperationalError` is not a `LociError`. See
   SPIKES SP-2.
3. **Fix `flake.nix`.** It still builds against `python312Packages` while
   `pyproject.toml`, `devenv.nix`, and the toolchain venv are all 3.13.
4. **Re-verify foreman's CONCEPT** before anyone relies on it. Its strategic
   validation cites a file that no longer exists.
5. **Raise the discovery-default patch upstream** — `**/`-prefixed excludes, so the
   nested-repo case works out of the box (SPIKES SP-5).

## 8. Decision record

Fill in when decided. Cite the reason, not just the choice.

| Decision | Options | Chosen | Date | Why |
|---|---|---|---|---|
| **Bundle** | A / B / C / D / E | | | |
| **D1 — who owns `plan`** | loci / foreman on loci / both / nobody | | | |
| **D2 — directory** | separate / unify on `.loci/` / discover `.scratch/**` | | | |
| **D3 — distribution** | publish / ssh / wheel / flake input | | | |
| **D4 — granularity** | per-repo / fleet / both | **per-repo** | 2026-08-25 | owner decision — see below |
| **Cross-lane** | accept partial / read lanes / adopt-on-trunk | | | |

### D4 — per-repo, permanently

Decided by the owner, 2026-08-25, in
`~/Documents/Projects/.scratch/projects/021-local-first-plane/` (**D-07**).

**This is stronger than §4's recommendation.** §4 recommended "per-repo **now**",
resting on SP-4: ids live in files, so a fleet vault added later inherits the
graph at no migration cost. The owner's decision keeps the per-repo answer and
**removes the later**. A fleet vault is ruled out, not deferred.

**Reason.** Cross-repo needs are routed to tools that already own that domain —
**fleetman** (what exists and how it integrates), **vendomat** (shared build
outputs), **devman** (what runs, when, across repos). loci keeps one job: what a
change is for, inside one repo.

**Consequences for this project:**

- **SP-5 is demoted.** The `**/`-prefixed exclude-default patch was the gate on a
  fleet vault. With no fleet vault, it is upstream hygiene. Still worth raising
  (§7.5); no longer blocking anything.
- **Option D's headline opportunity is void.** §3's Option D was recommended in
  part because it "unlocks a fleet vault later at zero migration cost". That
  benefit no longer counts toward D. Re-weigh D against C on its remaining
  merits — fleet-wide default, one convention, sixty red doctors until
  convergence — before choosing a bundle.
- **The cross-lane sub-decision is unchanged.** SP-6's lane isolation and the
  "adopt on trunk, plan on the lane" rule are per-repo facts. They do not depend
  on granularity.
- **§5's comparison row "Answers 'in flight across fleet'"** now reads *no* for
  every option including D, where it read "later, free". Only E answers it, and
  only by building foreman.

**Unaffected:** D1, D2, D3, and the bundle choice all remain open.

## 9. References

- [`../16-loci-plan-manager/CONCEPT.md`](../16-loci-plan-manager/CONCEPT.md) — the
  proposal: what loci is, the seam, the contract gaps, the four paths
- [`../16-loci-plan-manager/SPIKES.md`](../16-loci-plan-manager/SPIKES.md) — nine
  measurements and the six rules they produce
- [`../15-loci-core-adoption-issues/ISSUES.md`](../15-loci-core-adoption-issues/ISSUES.md)
  — R1, the blocker that comes first
- [`../08-issue-feature-workflow-helpers/CONCEPT.md`](../08-issue-feature-workflow-helpers/CONCEPT.md)
  — foreman's scope, and the stale citation Option E must re-verify
- `src/repoman/registry.py` — `SPINE`, `DEFAULT_MANAGERS`, the install models
- `src/repoman/aggregate.py:94` — `worst_exit` and the `0/1/2/3` contract
- `modules/devenv.nix:70` — the second default
- `modules/managers/docman.nix` — the presence-gated approach-B pattern
- `docs/SKILLS.md` — skill ownership, and the conflict-precedence open question
- `loci-core/docs/USER.md` §§3, 9, 10 — management states, git, sessions
