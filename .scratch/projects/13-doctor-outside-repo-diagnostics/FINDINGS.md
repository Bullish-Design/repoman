# Project 13 — `repoman doctor` outside a managed repo gives misleading diagnostics

**Status:** implemented 2026-08-06 (repoman 0.6.0) · discovered 2026-08-06 while bootstrapping `talkee`
(the first consumer of the project-12 toolchain split).

## 1. The issue, observed

Running `repoman doctor --self-only` from a directory that is **not** a managed
repo (here: the bare `~/Documents/Projects` root, no devenv shell) does not say
"you're not in a managed repo". Instead it reports a pile of plausible-looking
failures:

```
=== repoman (self-check) ===
FAIL lock — missing: /home/andrew/Documents/Projects/repoman.lock
FAIL installed:copy — copyroom not on PATH — run repoman-sync
FAIL installed:git — gitman not on PATH — run repoman-sync
FAIL installed:test — testee not on PATH — run repoman-sync
WARN skill:entrypoint — missing — run `repoman install-skills`
WARN devman:skills — missing ['devenv-authoring', …] — run `repoman install-skills`
WARN devman:docs — missing 7 doc(s) — run `repoman install-skills`
```

Every row is a red herring in this context:

- `FAIL lock — missing: <cwd>/repoman.lock` — the project-12 split (repoman
  README: "A consumer repo has no `repoman.lock`") removed the per-repo lock
  from modern consumers; even inside a correctly-managed repo this path does
  not exist, yet as a standalone row it reads like a missing file that should
  exist.
- `FAIL installed:copy/git — not on PATH — run repoman-sync` — the toolchain is
  intentionally NOT on a bare PATH; it is wired onto PATH **inside** a managed
  repo's devenv shell by the repoman module. "run repoman-sync" cannot succeed
  from this directory either (no repo to sync, and the command isn't on PATH).
- The `skill:*`/`devman:*` WARNs are all consequences of the same missing
  context.

The real diagnosis — "you are not inside a repoman-managed repo's devenv shell;
run me from there (e.g. `cd <repo> && devenv shell -- repoman doctor`)" — is
nowhere in the output. An agent or new user reads six failures, tries `run
repoman-sync`, gets a command-not-found, and has no idea the premise was wrong.

## 2. Root cause

`doctor` runs its row checks unconditionally; the "am I standing in a managed
repo / toolchain-on-PATH context" preflight either doesn't exist or doesn't
short-circuit. With no repo markers (`.gitman/`, `gitman.toml`, wired
`devenv.nix`, `REPOMAN_*` env from the shell) it still evaluates every
`lock:*`, `installed:*`, and `skill:*` check against a context that was never
established — producing per-row false FAILs instead of one true statement about
the context.

## 3. Impact

- **Wasted diagnosis cycles** — the exact failure mode that cost the `talkee`
  bootstrap a round-trip: reading FAILs, chasing a non-existent `repoman.lock`,
  before noticing the premise (wrong directory, no shell) was the bug.
- **Misleading docs/FAQ material** — future "why is doctor red" answers will
  copy these rows as if they were real conditions.
- Compounds with project 14 (no documented bootstrap entrypoint): a user who
  followed the docs into `repoman doctor` from the wrong place has no error
  message pointing them somewhere correct.

## 4. Fix options

| # | Option | Pros | Cons |
|---|--------|------|------|
| A | **Context preflight + short-circuit.** Detect managed-repo context (markers: `gitman.toml` / `.gitman/`, a wired `devenv.nix` importing the repoman module, or `REPOMAN_*` env set by the shell) and shell context (toolchain bin on PATH). If not in a managed repo: print one clear block — "not a managed repo — run me inside one: `cd <repo> && devenv shell -- repoman doctor`" — exit `2` (infra/config), skip row checks. | One true message; kills the red-herring class; simple. | Needs a reliable marker set (see §5). |
| B | **Repair the specific red herrings.** Drop/relabel the `lock` row (per-repo `repoman.lock` no longer exists for modern consumers), and make `installed:*` failures say "run inside the repo's devenv shell (the toolchain venv is wired onto PATH there)". | Fixes the two most misleading rows wherever doctor runs. | Doesn't fix the fundamental wrong-context problem; more strings to maintain. |
| C | A+B. | Complete. | Slightly more surface. |

**Recommendation: A, with B's relabel folded in** — the preflight makes the
rows moot outside a repo, and inside a repo the `lock` row should still not
imply a per-repo file (rename to reflect it checks the toolchain manifest
entries, matching the `toolchain:lock` naming used in-repo).

## 5. Design constraints for option A

- Marker set must be **conservative**: prefer unambiguous signals (e.g. env the
  repoman devenv module exports, like `REPOMAN_TOOLCHAIN_VENV`, plus
  `gitman.toml` presence) over grepping `devenv.nix`. Document the chosen
  precedence in the plan.
- `doctor --self-only` and full `doctor` both short-circuit identically.
- Exit codes per family contract: context failure = `2` (infra/config), not `1`
  (domain decision) — doctor currently returns the worst of its sub-checks;
  preflight should dominate.
- Keep the in-repo output byte-for-byte identical (green repos stay green;
  don't renumber rows that consumers may parse).
- `--json` must carry the new context error as a structured field, not just
  stderr prose.

## 6. Acceptance criteria

1. `repoman doctor` (and `--self-only`) from a non-repo directory prints
   exactly one clear message (what's wrong + the correct invocation) and exits
   `2`; no `lock:`/`installed:`/`skill:` rows.
2. From inside a managed repo's `devenv shell`: output unchanged (the `talkee`
   green run is the regression baseline).
3. From inside a managed repo but a bare shell (no devenv): still the
   toolchain-on-PATH guidance, not the not-a-repo message (distinguish the two
   contexts).
4. `--json` includes a parseable context error in all three cases.
5. Existing doctor tests updated; new tests cover the three contexts above.

## 7. Evidence / reference

- Reproduction: `cd /home/andrew/Documents/Projects && repoman doctor --self-only` (2026-08-06, repoman 0.4.0) — output quoted in §1.
- The repoman module wires the toolchain venv onto PATH inside consumer shells: `modules/devenv.nix` (toolchainVenvExpr, `REPOMAN_TOOLCHAIN_VENV`, PATH lines ~86–134).
- Project-12 split (no per-repo `repoman.lock` for consumers): repoman README "Two install models"; `.scratch/projects/12-toolchain-single-instance/`.
- In-repo green baseline: `cd talkee && devenv shell -- repoman doctor` (2026-08-06).
