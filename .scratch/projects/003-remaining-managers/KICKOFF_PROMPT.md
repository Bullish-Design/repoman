# Kickoff prompt — write the implementation guides for the remaining managers

Paste the block below into a **fresh session in the `repoman` repo** to begin.

This session's job is to **produce per-manager implementation guides** (one file per manager) that
a later session implements to — the same two-phase shape the devman subsystem used
(`.scratch/projects/02-devman-module/`: brainstorm + `01-devman-implementation.md` guide, then a
kickoff that implemented it). **You are writing the guides, not wiring the managers.** Author
real, code-grounded guides; do not change `src/`, `modules/`, or `tests/` except to correct a
discrepancy you discover and note.

---

You are writing the **implementation guides for RepoMan's four remaining managers**. RepoMan is the
agentic repo-lifecycle conductor for `devenv.sh` repos (`/home/andrew/Documents/Projects/repoman`):
one `devenv.yaml` import that composes the user's `*man` family of manager CLIs, sequences their
`doctor`/`status` under a shared `0/1/2/3` exit contract, and installs a generated entrypoint skill
+ the devman literacy layer. Three managers are wired (`copy`→copyroom, `git`→gitman, `test`→testee)
and devman is complete. **Four remain**, all already present in the registry but with no manager
module and no lock entry: `doc`, `session`, `agent`, `spec`.

## Decisions already made (do not re-litigate)

- **Scope = "wire ready, gate blocked."** Two managers have working CLIs and get **concrete,
  ready-to-implement** repoman-side guides now. Two have no conforming CLI yet — their CLIs are
  planned as separate `02-cli-conductor-alignment` projects **inside their own sibling repos**.
  For those, write the repoman-side guide too, but mark it **blocked** on that sibling project, list
  the exact prerequisite, and specify the registry fixes. Do **not** design or build the sibling
  CLIs here.
- **Delivery = per-manager guides.** One self-contained, independently-actionable guide file per
  manager (four files). A short `README.md` index is fine; keep each guide standalone (some
  repetition of the shared wiring steps is acceptable and expected).

## Read first (the conductor's seams are settled)

1. `src/repoman/registry.py` — the `Manager` dataclass + the `REGISTRY` (all 7 keys already defined)
   + the `SPINE` (lifecycle order: `spec → scaffold → change → verify → save → docs`).
2. `modules/devenv.nix` — the meta-module: `allManagers`, `imports` (only the 3 built managers
   today), `options.repoman.*`, the `env.REPOMAN_*` exports, the `repoman-sync` script wiring.
3. `modules/managers/{testee,copyroom,gitman}.nix` — **the exact pattern each new module copies**:
   `config = lib.mkIf (cfg.enable && elem "<key>" cfg.managers) { tasks = { "repoman:…" = …; }; }`,
   plus optional `packages`/`languages`/`enterTest`. gitman is the precedent for a manager that
   needs a **system toolchain** (it adds Rust+maturin, gated on `git`).
4. `src/repoman/checks.py` — `run_self_check`: a selected manager absent from `repoman.lock` →
   `lock:<key>` **FAIL**; its `command` not on PATH → `installed:<key>` **FAIL**; its installed
   sub-skill missing the "see the `repoman` skill" deferral footer → `skill:<key>:defers` **WARN**.
5. `tests/consumer-example/repoman.lock` — the lock format, incl. the **native-dep pseudo-entry**
   rule (`[managers.git-pyjutsu]`, keyed off `git`; never a real manager).
6. `docs/SKILLS.md` — the entrypoint/sub-skill contract (domain triggers + deferral footer).
7. `.scratch/projects/02-devman-module/01-devman-implementation.md` — match this guide's **depth and
   shape** (target layout, numbered steps with real snippets, verification block, risks table).

## The readiness triage (verify, then build each guide on it)

These findings were gathered this session — **confirm each against the live repos** before relying
on them; note any drift.

| Key | Lib (sibling repo) | Registry `command` | Verbs the registry calls | CLI today | System deps to provision | Status |
|---|---|---|---|---|---|---|
| `session` | `zelligate` | `zelligate` | `doctor`, `status=["list"]` | **Real CLI** — `cli.py` has `doctor` (`--quick`/`--json`) + `list` | `pkgs.zellij` (also socat/docker for some modes) | **READY — concrete guide** |
| `agent` | `mypi-agent` | `mypi` | `doctor`, `status=["paths"]` | **Real CLI** — `cli.py` has `doctor` (`--json`), `paths`, `sync`, `needs-sync`, `agent`, `secretspec-setup` | `pkgs.secretspec`; secrets handling | **READY — concrete guide** |
| `doc` | `docman` | `docman` | `doctor` (no status) | **No CLI** — `modules/docman.nix` + `scripts/docs-*.sh` only | docs toolchain (mkdocs/etc., already in docman's module) | **BLOCKED** on docman's own `02-cli-conductor-alignment` (adds `src/docman/` Typer CLI + Pydantic doctor) |
| `spec` | `allium-env` | `allium` ⚠️ | `doctor` (no status) | **No CLI** — pyproject still `name = "template-py"`; skeleton | the `allium` third-party binary (`juxt/allium-tools`) is added to PATH by allium-env's devenv | **BLOCKED** on allium-env's `02-cli-conductor-alignment`; **registry `command` is wrong** — `allium` is the third-party binary, the manager CLI is recommended `alliman` |

Sibling alignment plans to read (do not implement): docman & allium-env both have
`.scratch/projects/02-cli-conductor-alignment/README.md` describing exactly the CLI each will grow.

## What every per-manager guide must cover (the shared wiring)

Each guide is implemented later by editing **only repoman**. Spell out, with real snippets:

1. **Manager module** — `modules/managers/<lib>.nix`, gated on `cfg.enable && elem "<key>"
   cfg.managers`, mirroring the testee/copyroom/gitman shape. Decide whether it needs `packages` /
   `languages` (zelligate → `pkgs.zellij`; mypi → `pkgs.secretspec`) like gitman's Rust precedent,
   and which `repoman:<domain>:…` tasks to expose.
2. **Register the import** — add the module to `imports` in `modules/devenv.nix` (it self-gates).
3. **Lock entry** — the `[managers.<key>]` block for `repoman.lock` (and the consumer-example lock),
   plus any **native-dep pseudo-entry** (`<key>-<dep>`) the lib needs, per the gitman/pyjutsu rule.
4. **Registry correctness** — confirm/repair the `REGISTRY[key]` fields (`command`, `tier`,
   `summary`, `doctor`, `status`, `route_when`, `skill`). **`spec` must change `command` `allium` →
   the real manager command** so it doesn't collide with the third-party `allium` binary.
5. **CLI conformance check** — does the lib's `doctor`/`status` verb exist, emit a report, and honor
   `0/1/2/3`? Name the exact invocation `repoman` will run and any gap to close upstream.
6. **Sub-skill** — does the lib ship a `SKILL.md`, and does it carry the deferral footer the
   self-check lints? Note what's needed (sub-skill install is an open question in `docs/SKILLS.md`).
7. **Tests** — what to add/extend (`tests/test_registry.py`, `tests/test_checks.py`,
   `tests/test_cli.py`) so the new manager's wiring is covered.
8. **Verification in `tests/consumer-example/`** — the exact steps: add the key to
   `repoman.managers`, `rm -f devenv.lock && rm -rf .devenv`, `devenv shell -- repoman-sync`, then
   `repoman doctor` showing the manager's `lock:`/`installed:`/`skill:` rows green (background heavy
   steps; poll the log).
9. **Blocked managers (doc, spec):** add a **"Prerequisite / blocked-on"** section naming the
   sibling alignment project, the exact command/contract it must expose, and a one-paragraph
   "once it lands, do X" so the repoman side is trivially finishable later.

## Deliverables (this session)

Create under `.scratch/projects/03-remaining-managers/`:

- `README.md` — the readiness triage (verified), the shared wiring pattern, and an index of the
  four guides + their READY/BLOCKED status and recommended implementation order (ready ones first).
- `01-session-zelligate.md`
- `02-agent-mypi.md`
- `03-doc-docman.md`        (blocked-aware)
- `04-spec-allium.md`       (blocked-aware; includes the registry command-name fix)

Each guide: code-grounded, with a target-layout block, numbered steps + real snippets, a
verification block, and a risks table — matching `01-devman-implementation.md`'s depth.

## Environment rules (hard requirements)

- This repo uses **devenv**. Run every in-repo command inside it: `devenv shell -- <cmd>`. Never run
  bare `uv`/`python`/`pytest`. (You may freely **read** the sibling repos under
  `/home/andrew/Documents/Projects/` to verify readiness.)
- Do **not** add AI-attribution trailers to commits/PRs.
- Work on a branch (e.g. `remaining-managers-guides`); commit the guides; don't push unless asked.

## Definition of done (this session)

- The five files above exist; the four guides are concrete, code-grounded, and self-contained.
- The readiness table is **verified against the live repos**, with any drift from the findings above
  noted.
- `session` and `agent` guides are **immediately implementable** against the current libs.
- `doc` and `spec` guides clearly state the **blocking prerequisite** (the sibling alignment
  project), the exact contract to expect, and the registry fix for `spec`'s command name.
- Nothing in `src/`/`modules/`/`tests/` changed except discrepancy fixes, each noted in the guides.

## Guardrails

- Reuse the existing seams: the `modules/managers/<x>.nix` gating idiom, `repoman.lock` + the
  pseudo-entry rule, `registry.py`, the `checks.py` self-check, the `repoman-sync` → `install-skills`
  path. Do **not** add per-manager binaries or a second sync path.
- Keep RepoMan **pass-through**: it invokes each manager's own CLI and never models its report. If a
  lib's CLI doesn't conform, the fix belongs in that lib's alignment project, not in repoman.
- Don't expand scope into building the docman/allium CLIs — they are blocked-on prerequisites here.
