# Kickoff prompt — `uv sync` prunes the repoman manager toolchain out of the shared devenv venv

Paste the block below into a **fresh session in the `repoman` repo** to begin. This session's job is
**investigation + a written plan only — do NOT implement.** Produce the findings doc; do not edit
`src/`, `modules/`, or `tests/` this pass.

---

You are investigating a **self-inflicted footgun** in **repoman** (`/home/andrew/Documents/Projects/repoman`),
the devenv meta-module that composes the `*man` manager family. The short version: **`uv sync` — a
command repoman's own distributed docs recommend — deletes repoman's manager toolchain from the
shared devenv venv**, because the toolchain is installed add-only (pip-style) while `uv sync`
prunes to match a uv lockfile that knows nothing about it.

## 1. The issue — symptom, mechanism, evidence

**Symptom.** In any repoman-managed consumer repo (e.g. `../image-gen-pipeline`), running the
recommended
`devenv shell -- uv sync --all-extras` (or plain `uv sync`) uninstalls `gitman`, `testee`,
`copyroom`, `repoman`, `pyjutsu`, `pytest`, `ruff`, `ty`, `pyright`, `copier`, etc. from the venv.
The manager toolchain stops working until `repoman-sync` is re-run.

**Mechanism.** The devenv venv (`.devenv/state/venv`, targeted via `UV_PROJECT_ENVIRONMENT`) is
**co-managed** by two mechanisms that don't know about each other:

1. **Toolchain** — `repoman-sync` (`modules/scripts/repoman-sync.sh`) installs the manager tools
   from `repoman.lock` with `uv pip install "${targets[@]}"` — **add-only**, nothing about this
   install is visible to uv's project machinery.
2. **App deps** — the consumer's `pyproject.toml` `[project.dependencies]` (+ optional extras).

`uv sync`'s contract is "make the target environment match the uv lockfile exactly". It therefore
**removes every package not in the project's dependency graph** — i.e., the entire repoman
toolchain, which lives in `repoman.lock`, a file `uv sync` never reads.

**Evidence (reproduced 2026-08-03 in `../image-gen-pipeline`):**

```
$ devenv shell -- uv sync --dry-run --all-extras
Would use project environment at: .devenv/state/venv
Would create lockfile at: uv.lock
Resolved 21 packages in 122ms
Would uninstall 33 packages
 - annotated-doc==0.0.5
 - copier==9.17.0
 - gitman==...  pyjutsu==0.15.0  pytest==9.1.1  repoman==0.3.0
 - ruff==0.16.1  testee==0.2.0  ty==0.0.65  ... (33 total)
```

Note it also wants to **create `uv.lock`** — a second, competing source of truth for an environment
the repoman ecosystem deliberately manages pip-style (app deps never go in `repoman.lock`; the
toolchain never goes in `pyproject.toml`).

**Why this is repoman's problem (not just a consumer's):** repoman ships the guidance that pulls the
trigger:

- `src/repoman/devman/assets/docs/languages-python.md:17` — the **first-party** devenv skill
  distributed into every consumer's `.agents/devenv/` says:
  `devenv shell -- uv sync --all-extras   # install deps into the venv`
- Consumer plans mirror it ("`uv pip install -e .` (or `uv sync`)").
- `repoman doctor` has no check that detects a pruned toolchain (a `repoman-sync`-only reinstall
  heals it, but nothing tells the user).

The `uv sync --inexact` flag exists as an escape hatch (it skips pruning), but it is not documented
anywhere in repoman's guidance, and `uv sync` still introduces a `uv.lock`.

## 2. Read these first, in order

1. `CONCEPT.md` — the two-layer model (Python/venv layer vs nix layer) and where the venv fits.
2. `SPIKE.md` — what was validated about the venv/toolchain bootstrap.
3. `modules/devenv.nix` — `scripts.repoman-sync`, how the venv is wired (`languages.python`,
   `venv.enable`, `UV_PROJECT_ENVIRONMENT`).
4. `modules/scripts/repoman-sync.sh` — the add-only install (`uv pip install "${targets[@]}"`).
5. `src/repoman/devman/assets/docs/languages-python.md` — the distributed skill recommending
   `uv sync --all-extras` (line 17) alongside `uv pip install -e .` (line 18).
6. A consumer repo for reproduction: `../image-gen-pipeline/pyproject.toml` (declared deps:
   `dbos`, `sqlalchemy[asyncio]`, `alembic` → `.migrate`) and its `devenv.nix` (`repoman.enable`,
   `repoman.managers`, `languages.python`).

## 3. Investigation tasks

1. **Confirm the model.** Map exactly which packages end up in the shared venv from `repoman.lock`
   vs from the consumer's `pyproject.toml`; confirm `UV_PROJECT_ENVIRONMENT` makes `uv sync` target
   the shared venv; confirm the 33-package pruning set in a consumer (`--dry-run`). Record the
   precise contract each lockfile has (`repoman.lock` = toolchain, `pyproject.toml`/`uv.lock` =
   app deps).

2. **Audit every place the ecosystem tells users to run `uv sync`.** Search repoman's own docs,
   skills, devman assets, templates, and the consumer-facing `languages-python.md` for `uv sync`
   recommendations. For each: is it the plain command (unsafe), `--inexact` (safe-ish), or
   `--all-extras` (unsafe — extras don't protect the toolchain)? This is the "blast radius" of the
   guidance.

3. **Evaluate the fix options against the constraints (§4).** For each, state the change surface,
   migration cost, and residual footguns:
   - **A. Docs-only:** keep `uv pip install -e .` as the sole documented install mechanism;
     strike/qualify every `uv sync` recommendation (add `--inexact` where sync is wanted for
     lockfile creation). Cheapest; leaves `uv sync` as a silent footgun for anyone who doesn't read
     the docs.
   - **B. Make the toolchain uv-sync-compatible:** give `uv sync` a way to keep the toolchain —
     e.g. a `[tool.uv]`-level config, a workspace/extra that consumes `repoman.lock`, or a
     `repoman-sync`-owned marker that `uv sync`'s pruning must respect. Investigate whether uv
     supports "protect these packages" semantics at all before spending effort here.
   - **C. Separate venvs:** toolchain in a repoman-owned venv, app deps in the project venv, so
     `uv sync` only ever touches the app venv. Highest cost: every manager CLI invocation, PATH,
     and `repoman-sync` changes; assess against the "one venv, `devenv shell` is the front door"
     design.
   - **D. Doctor-side safety net:** add a `repoman doctor` check that detects a pruned toolchain
     (e.g. `gitman`/`testee` importable?) and either auto-heals via `repoman-sync` or tells the
     user the one-liner; combine with any of A–C.

4. **Recommend.** Pick the option (or combination) you'd sign off as owner; give the migration
   order (docs first, then any mechanism), and specify exactly which files change.

5. **Validation sketch.** In a consumer repo, for the recommended option: run the documented install
   path from a clean venv, then assert `gitman status` and `testee verify --mode quick` still work,
   and that the pruning set is gone (or protected) — i.e. the toolchain survives whatever the docs
   now tell users to run.

## 4. Constraints

- **Never break the toolchain:** `gitman`/`testee`/`copyroom`/`repoman` must survive every command
  the docs recommend.
- **Keep the two-source-of-truth split:** app deps never go in `repoman.lock`; the toolchain never
  goes in `pyproject.toml`/`uv.lock`. Don't propose collapsing them without strong justification.
- Preserve the "`devenv shell -- <cmd>` is the front door" and "run everything through the
  devenv-managed uv" conventions.
- `repoman-sync` stays the toolchain installer (its add-only semantics are load-bearing); only add
  to it if an option requires it.
- Investigation + plan only: **do not edit `src/`, `modules/`, or `tests/`** this pass.

## 5. Deliverable

A `FINDINGS.md` in this directory with: (1) confirmed two-mechanism venv model + the exact pruning
set; (2) the `uv sync` guidance audit (every site, safety verdict); (3) options A–D evaluated
against the constraints with a recommendation and migration order; (4) a validation checklist the
implementer will run in a consumer repo. Tick a progress log at the top as you go.

Run all in-repo commands via `devenv shell -- <cmd>`.
