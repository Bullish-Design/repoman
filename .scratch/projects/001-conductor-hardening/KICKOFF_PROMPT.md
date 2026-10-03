# Kickoff prompt — 01 Conductor hardening

Paste the block below into a fresh session in the `repoman` repo to begin implementation.

---

You are implementing project **01 — Conductor hardening** in the `repoman` repo
(`/home/andrew/Documents/Projects/repoman`). RepoMan is an agentic repo-lifecycle
**conductor**: a devenv.sh meta-module that composes a family of `*man` managers
(copyroom, gitman, testee, …) and a thin pass-through CLI that aggregates their own CLIs.

## Read first (do not re-derive — the design is settled)

In order:
1. `CONCEPT.md` — what RepoMan is and the decisions behind it.
2. `SPIKE.md` — the composition spike, what's proven, and findings.
3. `docs/SKILLS.md` — the entrypoint/router skill design.
4. `.scratch/projects/01-conductor-hardening/README.md` — this project's overview.
5. The three guides in that directory — your specs:
   - `01-gitman-native-toolchain.md`
   - `02-repoman-unit-tests.md`
   - `03-doctor-self-check.md`

The guides are detailed and code-grounded. Implement to them; if reality differs from a
guide, fix the code and **note the discrepancy in the guide**.

## Environment rules (hard requirements)

- This repo (and the consumer fixture) use **devenv**. Run every in-repo command inside it:
  `devenv shell -- <cmd>`. **Never** run bare `uv`/`python`/`pytest`.
- Verify behaviour in the throwaway consumer at `tests/consumer-example/`. When module or
  env (`env.*`) changes aren't picked up, force a rebuild: `rm -f devenv.lock && rm -rf
  .devenv` (its `devenv.lock` pins the `repoman` module input). Heavy rebuilds: run them
  **in the background** and poll the log, so they don't stall.
- Do **not** add AI-attribution trailers to commits/PRs.

## Order of work (recommended)

0. **Commit the current state first.** It's verified but uncommitted on `main`. Create a
   branch (e.g. `conductor-hardening`) and commit the existing pivot + spike before
   changing anything, so there's a clean baseline. Do not push unless asked.
1. **Guide 2 — unit tests.** Pure-Python, fast feedback, establishes a safety net before
   the bigger changes. End green: `devenv shell -- pytest`.
2. **Guide 3 — doctor self-check.** Pure functions + CLI wiring; unit-tested via guide 2's
   patterns. End green.
3. **Guide 1 — gitman + native toolchain.** Heaviest (native pyjutsu build via Rust/maturin).
   Do it last, with tests + self-check already in place to validate the wiring. The
   self-check from guide 3 will flag a selected-but-unbuilt gitman.

(The README lists them 1→2→3 by topic; this is the execution order — tests/self-check first
because they're cheap and harden the conductor that the gitman change then stresses.)

## Definition of done

- All three guides implemented; `devenv shell -- pytest` green; new tests cover
  `registry`/`aggregate`/`skills`/`cli`/`checks`.
- In `tests/consumer-example` with `managers = [ "copy" "git" "test" ]`:
  - `devenv shell -- repoman-sync` installs the toolchain (incl. native pyjutsu) and
    generates the entrypoint skill;
  - `devenv shell -- repoman managers` lists copy/git/test;
  - `devenv shell -- repoman doctor` runs the self-check **then** gitman's + testee's
    doctors and returns a sane aggregated exit code;
  - a deliberately broken selection (e.g. add `session`) makes the self-check `FAIL` with a
    clear reason and exit 2.
- Docs updated to reflect reality: `SPIKE.md` (mark "gitman / native toolchains" done),
  `CONCEPT.md §6` (managers may contribute nix-level provisioning, not just venv installs),
  and any guide that diverged from implementation.

## Guardrails

- Keep the conductor **tolerant of heterogeneity** — managers differ (missing verbs, native
  deps); never assume a uniform contract. (`doctor=None` stays a valid registry state.)
- Don't touch the component manager repos (gitman/copyroom/etc.) from here — RepoMan only
  *wires and installs* them. (copyroom's `doctor` is a separate effort with its own guide in
  the copyroom repo.)
- Match the family's conventions: Typer CLI, Pydantic models, the `0/1/2/3` exit contract.

## First action

Confirm you can enter the dev shell and that the baseline is green/known, then branch and
commit the current state:

```bash
devenv shell -- pytest -q || true        # capture the current baseline (may be ~no tests yet)
git status --short                        # review the uncommitted pivot + spike
```

Then proceed with step 0 (branch + commit) and work the guides in the order above, ending
each step green.
