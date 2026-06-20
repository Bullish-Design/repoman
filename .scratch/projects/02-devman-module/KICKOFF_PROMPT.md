# Kickoff prompt — implement the devman subsystem

Paste the block below into a fresh session in the `repoman` repo to begin.

---

You are implementing **devman** — the devenv-literacy layer — as a **subsystem of the repoman
repo** (`/home/andrew/Documents/Projects/repoman`). devman ships agent **skills**, a distilled
**docs export**, and **articles** that make Claude Code agents use `devenv.sh`-managed repos
correctly. It is installed by `repoman-sync` and lint-checked by `repoman doctor` — there is **no
separate repo, input, or CLI**.

## Read first (the design is settled)

1. `.scratch/projects/02-devman-module/README.md` — why devman lives in this repo.
2. `.scratch/projects/02-devman-module/CONCEPT.md` — what it is + how it wires in.
3. `.scratch/projects/02-devman-module/CONTENT_INVENTORY.md` — the skills/docs/articles to ship.
4. `.scratch/projects/02-devman-module/01-devman-implementation.md` — the detailed, code-grounded
   guide. Implement to it. If reality differs, fix the code and note the discrepancy in the guide.
5. `docs/SKILLS.md` — the skill trigger/deferral discipline devman skills must follow.

## Environment rules (hard requirements)

- This repo uses **devenv**. Run every in-repo command inside it: `devenv shell -- <cmd>`.
  **Never** run bare `uv`/`python`/`pytest`. (devman exists to enforce exactly this.)
- Verify in `tests/consumer-example/`; force a rebuild with `rm -f devenv.lock && rm -rf .devenv`
  when module/env changes aren't picked up. Background heavy steps and poll the log.
- Do **not** add AI-attribution trailers to commits/PRs.
- Commit on a branch (e.g. `devman-subsystem`); don't push unless asked.

## Order of work

1. Asset scaffold under `src/repoman/devman/assets/` + `pyproject.toml` package-data + **one
   complete skill** (`devenv-run-commands`) → package imports, assets resolve.
2. `devman/assets.py` + `devman/install.py` (+ manifest) + `tests/test_devman.py` → `pytest` green.
3. Wire `install-skills` to also install devman; add `REPOMAN_DOCS_DIR` → green.
4. `devman/check.py` (`devman_checks`) + wire into `doctor()`; extend `tests/test_checks.py` → green.
5. `modules/devenv.nix` — add `docsDir` option + `env.REPOMAN_DOCS_DIR` (confirm repoman-sync
   needs no change).
6. Author the remaining skills + docs + articles per the inventory (start with the lock/cache pair).
7. Verify end to end in `tests/consumer-example` (see the guide's Verification section).

## Definition of done

- `devenv shell -- pytest` green; new tests cover `devman` install + self-check + the CLI wiring.
- In `tests/consumer-example`: `repoman-sync` installs the entrypoint **and** devman skills +
  docs; `ls .claude/skills` and `ls .agents/devenv` show them.
- `repoman doctor` shows `devman:skills` / `devman:docs` / `devman:current` checks; removing an
  installed devman skill makes `devman:skills` WARN.
- Every devman skill triggers on mechanics keywords and carries the *"see the `repoman` skill"*
  deferral footer.
- CONCEPT.md / CONTENT_INVENTORY.md asset paths corrected to `src/repoman/devman/assets/`.

## Guardrails

- Assets are **Python package-data under `src/repoman/devman/assets/`** (like `templates/`), not
  under `modules/` — the installed `repoman` package lays them down.
- Reuse the existing seams: `install_entrypoint` (skills.py), `SelfCheck`/`self_check_exit`
  (checks.py), the `install-skills` + `doctor` CLI commands. Don't add a `devman` binary.
- Keep the layer discipline: skills imperative+short, docs factual+grep-able, articles
  explanatory; never repeat a fact across layers — link.
- The enforcement hook and the generated-docs pipeline are explicit follow-ups, not this project.
