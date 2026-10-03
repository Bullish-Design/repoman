# 03 — Implementation guides for RepoMan's four remaining managers

> **STATUS: CLOSED (2026-06-25).** All four guides below were implemented and
> verified; the current roster wires all seven keys (see `04-unblock-remaining-managers/`
> for the closure summary). This directory remains the historical per-manager
> implementation guides.

RepoMan wires three managers today (`copy`→copyroom, `git`→gitman, `test`→testee) and the devman
literacy subsystem is complete. **Four keys remain** in the registry with no manager module and no
lock entry: `session`, `agent`, `doc`, `spec`. This directory holds one self-contained,
independently-actionable implementation guide per manager — each implemented *later*, by editing
**only repoman**.

These guides were authored by reading the live conductor seams and **verifying each sibling repo's
CLI against its source** (not the kickoff's hearsay). Drift from the kickoff findings is noted below
and in each guide.

## The verified readiness triage

| Key | Lib (sibling repo) | Registry `command` | Verbs repoman calls | CLI today | System deps | Status |
|---|---|---|---|---|---|---|
| `session` | `zelligate` | `zelligate` ✓ | `doctor`, `status=["list"]` | **Real CLI** — `src/zelligate/cli.py`: `doctor` (`--quick`/`--json`, exit 0/2) + `list` (`--json`) | `pkgs.zellij` | **DONE ✅** — wired; doctor exit-code gap closed (zelligate `eae7ac4`), verified 2026-06-25 |
| `agent` | `mypi-agent` | `mypi` ✓ | `doctor`, `status=["paths"]` | **Real CLI** — `src/mypi_agent/cli.py`: `doctor` (`--json`, exit 0/1) + `paths` (`--json`) | `pkgs.secretspec` | **DONE ✅** — wired; verified 2026-06-25 (guide 02) |
| `doc` | `docman` | `docman` ✓ | `doctor` (no status) | **Real CLI** — `src/docman/cli.py`: `docman doctor` (Pydantic report, `--json`, exit 0/2) wrapping the `docs-*.sh` engine | docs toolchain (already in docman's module) | **DONE ✅** — wired `57d6fe7`, verified end-to-end 2026-06-25 |
| `spec` | `allium-env` | `alliman` ✓ | `doctor` (no status) | **Real CLI** — `src/alliman/cli.py`: `alliman doctor` (Pydantic report, `--json`, exit 0/2) + `install-skills` + `init` | the `alliman` CLI (the `allium` *binary* is third-party `juxt/allium-tools`, already on PATH) | **DONE ✅** — landed `e0a0d5f`; registry command/skill fix applied, verified 2026-06-25 |

### Drift from the kickoff findings (confirmed against the live repos)

- **There is only one lock file.** `tests/consumer-example/repoman.lock` is the *only* `repoman.lock`
  in the repo — there is no top-level lock. Lock edits in every guide target the consumer-example
  lock (and any future fleet lock follows the same block shape).
- **`session` / `agent` are pure-Python** (`pydantic`+`typer`(+`rich`)). Neither needs a native build,
  so **neither needs a `git-pyjutsu`-style native-dep pseudo-entry** — unlike gitman. Each is a single
  plain `[managers.<key>]` lock block.
- **`session` doctor exit-code gap (verified):** `zelligate doctor` honors `0/1` **only** under
  `--quick`; the full report path (`zelligate doctor` and `zelligate doctor --json`) **always exits
  0**, even with `severity == "error"` issues. RepoMan calls the default `["doctor"]`, so a broken
  session surface still reports green. Non-blocking for wiring; the fix belongs in zelligate. See
  guide 01 §Risks.
- **`agent` doctor is binary 0/1, not 0/1/2/3** — `DoctorResult.exit_code = 1 if errors else 0`
  (`src/mypi_agent/doctor.py`). That maps cleanly onto the contract (`1` = domain finding) and is
  surfaced faithfully by `aggregate.worst_exit`; no upstream change required.
- **`agent` paths/doctor require a devenv-managed project** — `Paths.discover()` walks for
  `devenv.nix`/`devenv.yaml` (or `MYPI_PROJECT_ROOT`). Satisfied in any consumer repo; repoman runs
  the manager from `DEVENV_ROOT`.
- **`doc` (docman) has no `pyproject.toml`** — it is purely a devenv module + `docs-*.sh` scripts plus
  a shipped skill set (`skills/docman-{setup,reference,authoring}`). The alignment project adds the
  whole Python package. Registry `command="docman"` is already correct (just no command on PATH yet).
- **`spec` registry `command` is wrong** — `command="allium"` would make the conductor shell out to
  the third-party `allium` binary, which has no `doctor` verb. allium-env's alignment plan recommends
  **`alliman`**; the registry must change to match. Guide 04 carries the exact edit.
- Neither READY lib ships an *installed* `<skills_dir>/<skill>/SKILL.md`, so the
  `skill:<key>:defers` self-check is **skipped** (not WARN) — `checks.run_self_check` `continue`s when
  the sub-skill file is absent. Sub-skill install remains the open question from `docs/SKILLS.md`.

## The shared wiring pattern (every guide repeats it, standalone)

Each manager is wired into repoman by the same nine moves — the seams are already settled, so a new
manager is pure composition:

1. **Manager module** — `modules/managers/<lib>.nix`, gated on
   `cfg.enable && builtins.elem "<key>" cfg.managers`, mirroring `modules/managers/testee.nix`
   (pure-Python) or `gitman.nix` (when a system toolchain is needed). Exposes `repoman:<domain>:…`
   tasks; adds `packages`/`languages` only when the lib needs a non-venv tool.
2. **Register the import** — add `./managers/<lib>.nix` to `imports` in `modules/devenv.nix`. It
   self-gates, so listing it unconditionally is correct (the standard module idiom).
3. **Lock entry** — a `[managers.<key>]` block in `tests/consumer-example/repoman.lock` (plus any
   `[managers.<key>-<dep>]` native pseudo-entry, per the gitman/pyjutsu rule — *not needed* for any
   of these four).
4. **Registry correctness** — confirm/repair `REGISTRY[<key>]` (`command`, `tier`, `summary`,
   `doctor`, `status`, `route_when`, `skill`). Only `spec` needs a change (`command`).
5. **CLI conformance** — confirm the lib's `doctor`/`status` verb exists, prints a report, and honors
   `0/1/2/3`. Name the exact invocation repoman runs and any upstream gap.
6. **Sub-skill** — note whether the lib ships a `SKILL.md` and whether it carries the deferral footer
   the self-check lints. (Install path is the open question in `docs/SKILLS.md`; the self-check only
   lints a skill that is *already installed*.)
7. **Tests** — extend `tests/test_registry.py`, `tests/test_checks.py`, `tests/test_cli.py` so the new
   manager's wiring is covered.
8. **Verification in `tests/consumer-example/`** — add the key to `repoman.managers`,
   `rm -f devenv.lock && rm -rf .devenv`, `devenv shell -- repoman-sync`, then `repoman doctor` with
   the manager's `lock:`/`installed:` rows green. Run heavy steps in the background; poll the log.
9. **Blocked managers only** — a *Prerequisite / blocked-on* section naming the sibling alignment
   project, the exact command/contract it must expose, and a one-paragraph "once it lands, do X".

RepoMan stays **pass-through**: it invokes each manager's own CLI and never models the report. If a
lib's CLI doesn't conform, the fix lives in that lib's alignment project, never in repoman.

## The guides + recommended implementation order

Implement the **READY** managers first (they need no upstream work), then the blocked pair as their
sibling alignment projects land.

| Order | Guide | Key | Status | Gating prerequisite |
|---|---|---|---|---|
| 1 | [`01-session-zelligate.md`](01-session-zelligate.md) | `session` | **READY** | none — implementable now |
| 2 | [`02-agent-mypi.md`](02-agent-mypi.md) | `agent` | **READY** | none — implementable now |
| 3 | [`03-doc-docman.md`](03-doc-docman.md) | `doc` | **BLOCKED** | docman ships `src/docman/` + `docman doctor` (its `02-cli-conductor-alignment`) |
| 4 | [`04-spec-allium.md`](04-spec-allium.md) | `spec` | **BLOCKED** | allium-env ships `src/alliman/` + `alliman doctor` (its `02-cli-conductor-alignment`); **registry `command` fix** |

Each guide is code-grounded: a target-layout block, numbered steps with real snippets, a verification
block, and a risks table — matching `.scratch/projects/02-devman-module/01-devman-implementation.md`.
