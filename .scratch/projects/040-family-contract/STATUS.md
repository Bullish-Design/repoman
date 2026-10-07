# Project 040 — status

**The library exists.** `CONCEPT.md` in this directory said it would move into
the new library's own repository once that repository existed. It has:

- `/home/andrew/Documents/Projects/mancore/CONCEPT.md` — the design, plus a new
  §10 that re-measures every count in §§1-8 against code as of 2026-10-07.
- `/home/andrew/Documents/Projects/mancore/docs/MIGRATION.md` — the ordered
  rollout, steps 0 through 12.

`mancore` ships §4's seven modules (`exits`, `errors`, `report`, `doctor`,
`repo`, `capability`, `cli`) with 82 tests. `ruff`, `ruff format` and `ty` are
green. It has no consumers yet, per §7's "build `mancore` with its own suite
first".

The copy of `CONCEPT.md` beside this file is the 2026-10-06 original and is kept
only as the design record. Read `mancore`'s copy for anything load-bearing.

## What changed for RepoMan itself

Four items, all in the migration plan's step 10:

- `src/repoman/checks.py:38` — `_LEVELS` `fail: 2` becomes `fail: 1`.
- `src/repoman/cli.py:235` — `Exit(code=3)` becomes `2`.
- `tests/test_cli.py:94` becomes `== 1`; `:276` and `:285` become `== 2`. The
  four context failures at `:178, 194, 215, 230` stay `2`.
- `src/repoman/templates/entrypoint.SKILL.md.j2:12`, `docs/SKILLS.md:19,52`,
  `CONCEPT.md:41`, `src/repoman/cli.py:36` and
  `src/repoman/devman/check.py:37` all state the retired `0/1/2/3` contract.

**Step 0 blocks the rest.** `vendomat/flake.lock` pins repoman v0.7.5, which
still has `aggregate.py`. RepoMan must cut a release with it removed, and
Vendomat must bump to that tag, before any tool's doctor fail code moves.
