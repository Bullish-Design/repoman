# 09 — repoman review & catch-up: OVERVIEW

> A grounded snapshot of **where repoman is vs. where its concept says it should
> end up**, written by reading the code (not the packets). Companion: `PLAN.md`
> (sequenced remaining work) and `KICKOFF_PROMPT.md` (paste-to-start).

All paths relative to `/home/andrew/Documents/Projects/repoman/` unless absolute.

---

## 1. What repoman IS (the desired final concept)

repoman is the **per-repo conductor for the `*man` family** — one devenv import
that turns any repo into a fully-managed agentic repo (`CONCEPT.md` §1–3). It does
not invent an architecture; it *composes* the existing `*man` pattern:

- **Primary form: a devenv meta-module** (`modules/devenv.nix`) — the one-liner a
  consumer imports. Set `repoman.enable = true`, pick `repoman.managers`, and the
  selected managers (copyroom, gitman, testee, docman, zelligate, mypi-agent,
  allium-env) are installed, nix-wired (tasks/scripts, and native toolchains where
  needed), and skilled, with one `repoman doctor` over all of them (`CONCEPT.md`
  §4–6).
- **A thin Python conductor** (`src/repoman/`) — it re-implements nothing. It
  discovers the enabled managers, **sequences and aggregates** their own CLIs, and
  collapses their exit codes under the shared **`0/1/2/3` contract** (ok /
  domain-decision-needed / infra-config / invalid-usage). Each manager keeps its
  own report and its own skill (`CONCEPT.md` §5).
- **It owns lifecycle order**, not domain logic: verify → save, scaffold → change
  (the `SPINE` in `registry.py:48`, rendered into the entrypoint skill).
- **Scope: per-repo BY DESIGN.** Fleet/workspace management is *explicitly out of
  scope* for v1 (`CONCEPT.md` §2: "Fleet/workspace management is explicitly out of
  scope"). copyroom is the convergence pillar (births/adopts/propagates).

Desired end-state = every intended manager wired under the 0/2 doctor contract, the
nix meta-module doing both venv installs *and* nix-level provisioning, a generated
entrypoint skill that routes the agent to the right manager, and the devenv-literacy
substrate (devman) co-installed. **Resolved decision (2026-07-01):** fleet-sync is
descoped from repoman → owned by **fleetman**; repoman stays strictly per-repo
(`CONCEPT.md §2`). See the concept-vs-reality gap (§3).

---

## 2. Where repoman is NOW (verified against the code)

**Version / health.** `pyproject.toml:3` → `version = "0.3.0"`. Test suite green:
`devenv shell -- python -m pytest -q` → **66 passed**, 96% coverage (checks.py,
aggregate.py, registry.py, devman/* all ≥100% or near). Console script
`repoman = "repoman.cli:main"` (`pyproject.toml:22`).

**Registry — manager coverage is COMPLETE.** `src/repoman/registry.py:58` wires all
seven roster keys, each with tier + doctor/status args + a `route_when` cell:

| key | command | tier | doctor | status | nix_input |
|---|---|---|---|---|---|
| `copy` | copyroom | core | none (v0.4 has no doctor) | `status` | — |
| `git` | gitman | core | `doctor` | `status` | — |
| `test` | testee | core | `doctor` | `list-runs` | — |
| `doc` | docman | publish | `doctor` | — | `docman` |
| `session` | zelligate | situational | `doctor` | `list` | — |
| `agent` | mypi | situational | `doctor` | `paths` | `mypi-agent` |
| `spec` | alliman | situational | `doctor` | — | `allium-env` |

`DEFAULT_MANAGERS = ["copy","git","test"]` (`registry.py:108`). Nix side matches:
`modules/devenv.nix:26` `allManagers = [ "copy" "git" "test" "doc" "session"
"agent" "spec" ]`, and every key has a wiring module under `modules/managers/`
(`testee.nix`, `copyroom.nix`, `gitman.nix`, `zelligate.nix`, `mypi.nix`,
`docman.nix`, `alliman.nix`) imported at `modules/devenv.nix:29-38`.

**CLI surface** (`src/repoman/cli.py`): `managers`, `doctor` (with `--self-only`),
`status`, `install-skills`. Aggregation + exit merge in `aggregate.py`
(`run_sub` + `worst_exit`). `doctor` runs the self-check preflight, folds in
`devman_checks`, then each enabled manager's doctor and returns the worst exit
(`cli.py:57-79`).

**Self-check + nix-provisioning bridge — LANDED (all 6 phases).**
`src/repoman/checks.py:run_self_check` validates: `repoman.lock` present/parses,
lock↔managers consistency (tolerating native-dep pseudo-entries like `git-pyjutsu`,
`checks.py:55`), each manager CLI on PATH, the entrypoint skill present, and
sub-skill deferral discipline. It also emits `provisioned:<key>` warnings for
approach-B managers whose nix module didn't import — driven by
`REPOMAN_PROVISIONED_<KEY>=1` (`checks.py:77-87`). Project 05's README confirms
Phases 1–6 done and verified (approach A: copy/session; approach B: doc/spec/agent;
R1 doctor warnings; full-roster consumer-example re-verify, self-check 100%).

**devman subsystem — BUILT (note: packet 02 still reads "brainstorm").** The
concept's INTERNAL-subsystem path is real in the tree: `src/repoman/devman/`
(`__init__.py`, `assets.py`, `check.py`, `install.py`) plus package-data under
`devman/assets/{skills,docs,articles}/`. It is wired into `cli.py`:
`devman_checks(...)` folded into `doctor` (`cli.py:65`) and `install_devman(...)`
called from `install-skills` (`cli.py:104`); the module exposes
`env.REPOMAN_DOCS_DIR` (`modules/devenv.nix:81`). Tests: `tests/test_devman.py`.

**Entrypoint skill generation — BUILT.** `src/repoman/skills.py:install_entrypoint`
renders the roster + `SPINE` into a router skill (`docs/SKILLS.md` documents it);
`tests/test_skills.py` covers it.

---

## 3. Concept-vs-reality gap table (cite real files/commands)

| Concept says (CONCEPT.md / packet) | Reality in the tree | Gap / status |
|---|---|---|
| Compose the full `*man` roster under 0/2 doctor contract | 7 managers in `registry.py:58`; nix modules all present `modules/managers/*.nix`; `worst_exit` in `aggregate.py` | **CLOSED** — coverage complete |
| nix meta-module does venv *and* nix-level provisioning (native toolchains, approach-B inputs) | `gitman.nix` adds Rust/maturin; `provisioned:<key>` warns via `REPOMAN_PROVISIONED_*` (`checks.py:77`); project 05 Phases 1–6 done | **CLOSED** |
| devenv-literacy layer folded in as a subsystem (§ project 02) | `src/repoman/devman/*` built + wired (`cli.py:16,65,104`); `test_devman.py` green | **CLOSED in code** — but packet `02-devman-module/README.md:36` still says "Brainstorm". Doc drift only; reconcile the packet status |
| Generated entrypoint router skill from the roster | `skills.py:install_entrypoint`; `docs/SKILLS.md`; `test_skills.py` | **CLOSED**. Remaining nice-to-haves in `CONCEPT.md` §8: conflict-precedence table, installing sub-skills, doctor-as-skill-linter |
| **`foreman` work-item front door** = an 8th manager (`key="work"`, `command="foreman"`) (project 08) | **No `foreman` repo; no `work` key** in `registry.py`; no `modules/managers/foreman.nix`; no `[managers.work]` in `repoman.lock` | **OPEN — biggest item.** Design fully LOCKED (`08-*/CONCEPT.md` §9, 8 decisions), name collision-checked; Phase 1 (skills-only, birth via `new-project`) READY, Phase 2 (Python engine + repoman wiring) NOT STARTED |
| **Repo-set / fleet sync** (was project 07: `repoman fleet-sync`, `repos.toml`, `src/repoman/fleet/`, `modules/managers/fleet.nix`) | Never built; not repoman's job. `modules/scripts/repoman-sync.sh` exists but is the *unrelated* venv-toolchain sync | **RESOLVED — descoped from repoman → owned by fleetman (2026-07-01).** Consistent with `CONCEPT.md` §2 (fleet out of scope). Project 07 retired (see `07-tower-repo-set-sync/SUPERSEDED.md`); the capability lives in fleetman `002-fleet-write-ops`. Not outstanding repoman work |
| `repoman new` / `repoman adopt` (fleet-less repo birth via copyroom) | Not in `cli.py` | **OPEN (design)** — `CONCEPT.md` §8 open question; today birth/adopt live in the workspace `new-project` / `adopt-project` skills, not repoman itself |
| `repoman verify` / `save` / `release` lifecycle pass-throughs (`CONCEPT.md` §5) | `cli.py` has `managers`/`doctor`/`status`/`install-skills` only | **PARTIAL** — the gated lifecycle verbs (verify→testee; save→testee-then-gitman; release→ci→gitman→docman) are described but not implemented |
| devman **project 02** as a formal implementation project | Code exists; packet is still a brainstorm with open questions (name, self-check strictness warn-vs-fail, hook surface) | **DOC/POLISH** — retro-document what shipped; decide the leftover open questions or close them YAGNI |

---

## 4. One-paragraph verdict

repoman's **core mission is essentially done**: the full manager roster is wired and
green under the 0/2 doctor contract, the nix-provisioning bridge landed end-to-end,
and the devman literacy subsystem + entrypoint-skill generation are built and
tested (66 passing, v0.3.0). What remains is **net-new surface**, not repair: the
locked-but-uncoded **`foreman`** work-item manager (project 08 — the single biggest
outstanding item), the unimplemented lifecycle pass-throughs
(`verify`/`save`/`release`), and doc catch-up where packets lag the code (project 02
devman still labelled "brainstorm"). Fleet-sync (project 07) is **no longer on
repoman's list**: it was descoped to fleetman on 2026-07-01 (retired; see
`07-tower-repo-set-sync/SUPERSEDED.md`), keeping repoman strictly per-repo.
