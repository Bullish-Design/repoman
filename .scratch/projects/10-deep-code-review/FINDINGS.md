# RepoMan Review — Actionable Findings Checklist

Companion to `REVIEW.md`. One checkbox per fix, ordered by priority. `file:line` refs are
against `main` @ `787c751` (v0.3.0).

## P1 — should fix now

- [ ] **flake.nix staleness** (`flake.nix:2,12,28-35`)
  - [ ] `description` → the devenv-conductor blurb (currently the old "NixOS configs" concept)
  - [ ] `version` `0.1.0` → `0.3.0` (or source from pyproject to stop drift)
  - [ ] drop phantom deps `pyyaml`, `tomli`, `aiofiles`; keep `pydantic typer jinja2`
- [ ] **CLI exit-collapse test** (`cli.py:79`) — mock `run_sub`→`SubResult(exit_code=1)` with a
      doctor-bearing manager (`test`), assert `doctor` exits `1`; second case: self-check FAIL
      + sub 1 → exit `2` (proves `max` picks both sides)
- [ ] **`status` command tests** (`cli.py:82-92`) — none exist today; assert `worst_exit` exit +
      `status is None` skip (e.g. `doc`)

## P2 — coverage gaps

- [ ] `git+https://…@ref` source passthrough (`repoman-sync.sh:46`) — lock fixture asserts it's
      emitted verbatim (no prefix strip, no `--editable`)
- [ ] `_enabled()` drops unknown keys (`cli.py:34`) — `REPOMAN_MANAGERS="test bogus"` → only testee
- [ ] negative pseudo-entry (`checks.py:55`) — `[managers.gitx-pyjutsu]` must NOT satisfy `git`
- [ ] `self_check_exit`/`format_self_check` unknown-level fallback (`checks.py:115,120`)
- [ ] mixed-roster doctor (`copy test`) — assert copy "skipped" AND testee doctor ran in one call

## P3 — smells / nits

- [ ] `registry.py:63` — stale comment: copyroom now HAS a `doctor` verb; refresh (and consider
      flipping `doctor=None`)
- [ ] `devenv.nix:91` — drop redundant inner `lib.optionalString cfg.enable` (already under `mkIf`)
- [ ] `cli.py:57` — rename local `managers` (shadows the `managers` Typer command)
- [ ] `docman.nix:16` / `mypi.nix:20` / `alliman.nix:16` — `{ inputs ? {}, … }` for defensiveness

## Verified NON-issues (do not "fix")

- ✅ `REPOMAN_PROVISIONED_*` signal DOES fire — from repoman's wrapper modules
  (`docman.nix:44`, `mypi.nix:55`, `alliman.nix:39`), keys match `checks.py:80`. The siblings'
  own modules don't emit it, and don't need to.
- ✅ All 7 sibling CLIs, subcommands, skill dirs, and nix inputs match the registry — no
  command-not-found risk.
- ✅ `repoman-sync.sh` obeys the no-silent-failure rule end to end.
- ✅ registry ↔ `allManagers` ↔ option `enum` ↔ `DEFAULT_MANAGERS` are all consistent.

## Snapshot at review time

- Tests: 66 pass, ~96% line coverage, ~2.2s under devenv.
- Hard bugs found: **0**. Issues are staleness + test-coverage + cosmetics.
