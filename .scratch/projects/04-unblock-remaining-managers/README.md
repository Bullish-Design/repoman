# 04 — Unblocking RepoMan's remaining managers (upstream follow-ups)

RepoMan now wires seven managers (`copy`, `git`, `test`, **`session`**, **`agent`**, **`doc`**,
**`spec`**) and **all three upstream follow-ups this directory coordinates are DONE** (verified
2026-06-25). The conductor's manager coverage is complete and clean. This directory remains the
historical **coordination hub** for that work: it carried the one guide that didn't exist elsewhere
(the zelligate doctor exit-code fix) and pointed at the two sibling alignment guides that live in
their own repos.

**Closure summary (all verified 2026-06-25):**

- **Item 1 — zelligate doctor exit-code fix:** landed in `zelligate` (`eae7ac4`, v0.3.0). Degraded
  workspace now exits **2** on all three paths (rich / `--json` / `--quick`); happy path stays `0`;
  20 doctor tests pass. `repoman doctor`'s aggregate propagates it (no repoman code change needed).
- **Item 2 — docman family CLI:** docman CLI shipped 2026-06-20; repoman `doc` wired + verified
  end-to-end (see `03-remaining-managers/03-doc-docman.md`).
- **Item 3 — alliman family CLI:** landed in `allium-env` (`e0a0d5f`). `alliman doctor` honours the
  0/2 contract (`typer.Exit(0 if report.ok else 2)`); 16 tests pass. repoman's `spec` registry
  entry carries the command/skill fix (`command="alliman"`, `skill="allium-entrypoint"`). The live
  consumer-example `repoman doctor` runs the `spec` sub-doctor and the aggregate exits **2** when
  alliman's assets aren't installed.

Each item is implemented by editing a **sibling repo**, not repoman. Where repoman itself needs a
finishing edit afterwards, that's the already-written wiring guide in
`03-remaining-managers/` (guides 03 and 04).

## The three follow-ups

| # | Item | Target repo | Guide | Unblocks | Status |
|---|---|---|---|---|---|
| 1 | **zelligate `doctor` exit-code fix** | `zelligate` | [`01-zelligate-doctor-exit-code.md`](01-zelligate-doctor-exit-code.md) **(new, here)** | closes the "degraded session reports green" gap (repoman guide 01 §Risks) | **DONE ✅** — landed `eae7ac4` (v0.3.0); degraded→2 all paths, verified 2026-06-25 |
| 2 | **docman family CLI** (`docman doctor`) | `docman` | `docman/.scratch/projects/02-cli-conductor-alignment/01-docman-cli.md` **(already exists)** | repoman `doc` manager — `03-remaining-managers/03-doc-docman.md` | **DONE ✅** — docman CLI shipped 2026-06-20; repoman `doc` wired + verified end-to-end 2026-06-25 |
| 3 | **alliman family CLI** (`alliman doctor`) | `allium-env` | `allium-env/.scratch/projects/02-cli-conductor-alignment/01-alliman-cli.md` **(already exists)** | repoman `spec` manager — `03-remaining-managers/04-spec-allium.md` (+ registry `command` fix) | **DONE ✅** — landed `e0a0d5f`; 0/2 contract, registry command/skill fix applied, verified 2026-06-25 |

> **Why only one new guide here.** Items 2 and 3 already have detailed, code-grounded
> implementation guides **in their own repos** (`02-cli-conductor-alignment/` in each, with a
> `README.md`, a `01-*-cli.md`, and a `KICKOFF_PROMPT.md`). Re-authoring them here would create a
> second source of truth to reconcile. This README just indexes them so the whole "unblock the
> remaining managers" effort is visible from one place. Item 1 had no guide anywhere — that's the
> gap this directory fills.

## Item 1 — zelligate doctor exit-code fix (this dir)

`session` is already wired and verified, but its sub-doctor has a known gap: `zelligate doctor` and
`zelligate doctor --json` (the report paths RepoMan actually calls) **always exit 0**, even when the
workspace is missing or discovery surfaces `error`-severity issues. Only `zelligate doctor --quick`
honours an exit code today. So a broken session surface still reports **green** to `repoman doctor`.

[`01-zelligate-doctor-exit-code.md`](01-zelligate-doctor-exit-code.md) is the code-grounded fix:
one shared `_doctor_exit_code()` helper applied to all three doctor paths (`--quick`, `--json`,
rich), mapping environment/config failures onto the family `0/1/2/3` contract (`2` = infra/config).
It also unifies `--quick` onto the same helper (a small, deliberate `1 → 2` change — see the guide's
Risks). **Copy it into zelligate's `.scratch/projects/04-doctor-exit-code/` (or wherever you stage
work there) and implement against the live `src/zelligate/cli.py`.**

Once it lands, RepoMan needs **no change** — the registry default `doctor=["doctor"]` simply starts
yielding a real exit code, and the optional `["doctor", "--quick"]` mitigation floated in
`03-remaining-managers/01-session-zelligate.md` §Risks becomes unnecessary (keep the readable
default). Re-running the consumer-example verification with an intentionally-missing workspace should
then show `repoman doctor` surfacing exit `2` for a degraded session.

## Items 2 & 3 — the sibling CLI-alignment projects (already spec'd)

Both follow the same `*man`-family contract (one Typer console script, `init` + `doctor` universal
verbs, a Pydantic `DoctorReport`, the `0/1/2/3` exit contract, still a devenv module). Read each
target repo's own guide:

- **docman** → `docman/.scratch/projects/02-cli-conductor-alignment/` — adds `pyproject.toml`
  (`[project.scripts] docman = "docman.cli:app"`) + `src/docman/`, ports `scripts/docs-doctor.sh`
  to a Pydantic `docman doctor` (exit `0`/`2`), and wraps the existing `docs-*` scripts as
  subcommands. When `docman doctor` is on PATH, finish repoman's side with
  `03-remaining-managers/03-doc-docman.md`.
- **allium-env** → `allium-env/.scratch/projects/02-cli-conductor-alignment/` — replaces the
  `template-py` stub with `src/alliman/`, adds a **new** `alliman doctor` that verifies the
  skills/entrypoint/manifest/prompts are installed (exit `0`/`2`), and `alliman install-skills`.
  When `alliman doctor` is on PATH, finish repoman's side with
  `03-remaining-managers/04-spec-allium.md` — including the **required** registry edit
  (`spec.command "allium" → "alliman"`, the one source change in that guide), which must land
  **together with** the lock + module so `installed:spec` never FAILs for selectors of `spec`.

## Recommended order

1. **zelligate doctor fix** (item 1) — self-contained, no downstream coordination; closes a live gap
   in an already-shipped manager. Do it first.
2. **docman CLI** (item 2) → then repoman guide 03. No registry change.
3. **alliman CLI** (item 3) → then repoman guide 04 + the registry `command` rename.
