# PROGRESS — 12-toolchain-single-instance (implementation)

**Repo:** `/home/andrew/Documents/Projects/repoman` · **Status:** implemented + validated
**Commits:** `448b9cf` PR-A (machine sync) · `4509d1f` lock follow-up · `b6bddce` PR-B (semantic switch) · `fa6d7f5` PR-C (fixture/docs)

---

## Step 0 — unverified-mechanics gap (the kickoff required closing this first)

All three experiments ran in `/tmp` or read-only; results recorded here.

### 0.1 testee-as-dev-group pulls the verify stack — **CONFIRMED**
`/tmp/repoman-12-scratch` with `[project]` + `[dependency-groups] dev = ["testee"]` +
`[tool.uv.sources] testee = { path = "../testee" }`, `UV_PROJECT_ENVIRONMENT=/tmp/.../.venv`:
- `uv sync` → testee **plus** pytest, pytest-json-report, ruff, ty, import-linter land; `uv.lock` written.
- `uv pip install six` into that venv, then `uv sync` again → **six pruned** ("Uninstalled 1 package"),
  testee + tools survive. The whole thesis in one experiment: a graph-declared testee survives
  pruning; a foreign package doesn't.
- Note: `VIRTUAL_ENV` (repoman's own devenv venv) leaks into `uv pip` from the outer shell; the
  experiments used explicit `--python <venv>/bin/python` to stay unambiguous.

### 0.2 PATH precedent (D1) — **CONFIRMED (2a), CORRECTION (2b)**
- **2a:** consumer `.devenv/shell-*.sh` sets `UV_PROJECT_ENVIRONMENT`, `VIRTUAL_ENV`, and the venv
  PATH prepend as **runtime bash exports** (`export PATH='<repo>/.devenv/state/venv/bin:…'`), not
  nix-eval absolute paths. The meta-module's runtime expression is the right precedent.
- **2b (correction):** the kickoff asserted *"`devenv tasks run <task>` does not source
  `enterShell`"*. In devenv 2.1.2, **tasks DO receive enterShell's exports** (a probe task saw
  `PROBE_ENTER_SHELL=yes`; the consumer task env carried `REPOMAN_TOOLCHAIN_VENV`). Each task is an
  isolated process (exports do not flow task→task), but enterShell's block runs per task.
  **Decision D1 is unchanged and strictly safer for it:** `"${cfg.toolchainBin}"/gitman` in task
  execs works whether or not the task environment carries the shell's PATH — the explicit path is
  version-robust. (The same probe also exposed a *separate* pre-existing quirk — see §validation
  row 8 and §deviations 10.)

### 0.3 no name collisions — **CONFIRMED**
- Pre-migration consumer venv (`image-gen-pipeline`) held repoman/gitman/copyroom/testee +
  pytest/ruff/ty. Post-migration the sets are disjoint: consumer venv = uv graph (testee + tools),
  shared venv = repoman/gitman/copyroom/docman + pyjutsu (no testee, no pytest/ruff/ty — verified
  in the machine-lock manifest and the bootstrapped venv).
- pyjutsu ships **no console script** (native lib) — no bin collision at all.

---

## Per-step log (step → files → proof command)

| Step | Files | Proof |
|---|---|---|
| 1 machine lock | `repoman.lock` (new, root) | `tomllib` sanity: `['copy','doc','git','git-pyjutsu']`, no `test` |
| 2 two-mode script | `modules/scripts/repoman-sync.sh` | `devenv shell -- repoman-sync --machine` → venv built; `uv.log` recorder tests green |
| 3 bootstrap ctx | `devenv.yaml`, `devenv.nix` (repoman's) | `UV_FIND_LINKS=/nix/store/…-vendomat-wheelhouse` exported; `--machine` installed 30 pkgs incl. pyjutsu wheel (no Rust) |
| 4 meta-module | `modules/devenv.nix` | generated `.devenv/shell-*.sh` contains the literal runtime expression + PATH prepend; `test_modules_nix.py` green |
| 5 managers | `gitman/copyroom/docman.nix` | `rg venvBin modules/` → only `testee.nix`; `cfg.toolchainBin` in the three |
| 6 registry | `src/repoman/registry.py` | `install`/`package` fields; `test` → `"uv"`; bogus `install` raises |
| 7 doctor | `src/repoman/checks.py` | fixture doctor: `toolchain:*` + `lock:{copy,git,doc}` + `uv:test` all OK, no `lock:test` row |
| 8 tests | `test_repoman_sync.py`, `test_checks.py`, `test_cli.py`, `test_registry.py`, `test_modules_nix.py` | `devenv shell -- pytest -q` → **95 passed** |
| 9 docs/skills | fixture `.agents/devenv/**` + `CONCEPT.md` + `SPIKE.md` | see §deviations 1 (assets moved to genome) |
| 10 fixture | `tests/consumer-example/*` | `devenv shell -- repoman doctor --self-only` → all-OK shape incl. `uv:test` |
| 11 template | (external) | sibling PRs written up — §follow-ups |
| 12 dogfood | `../image-gen-pipeline` | §validation table |

**PR-A bootstrap (real, on this machine):** `devenv shell -- repoman-sync --machine` →
`~/.local/share/repoman/venv/bin` contains `repoman gitman copyroom docman` (python 3.13.13),
`repoman-toolchain.toml` recorded. All later slices assumed it — it exists.

---

## §12c validation table (real output)

| # | Command | Result |
|---|---|---|
| 1 | `repoman-sync --machine`; `gitman status` from consumer | shared venv has the 4 CLIs + pyjutsu; `gitman status` runs from the consumer (exits 1 only because this repo's bookmarks are DESYNCHRONIZED — a repo-state fact, not resolution) |
| 2 | `uv sync --all-extras`; `testee verify --mode quick`; `repoman doctor` | sync migrated (uninstalled exactly the toolchain closure); **`Verification: PASSED` (ruff/ruff-format/ty/pytest)**; doctor rows: `toolchain:venv`, `toolchain:lock`, `lock:copy`, `lock:git`, **`uv:test`**, `lock:doc`-absent (roster is copy/git/test), no `lock:test` |
| 3 | **acceptance** — 2nd `uv sync --all-extras --dry-run` | **`Would make no changes` — zero uninstalls (was 33)** |
| 4 | `uv sync`, `uv sync --all-extras`, `uv pip install -e .` | after each: `gitman status` runs, `repoman managers` lists, testee + pytest/ruff/ty/import-linter survive in the consumer venv (`uv pip install --all-extras -e .` errors on uv 0.11.28 — see deviations 8) |
| 5 | `uv lock --upgrade-package testee`; machine pin bump | uv side: lock stays 42 pkgs, testee intact, `uv sync` no-changes (one-time drop anomaly — deviations 9); machine side: `repoman-sync --machine` re-runs add-only against the shared venv only |
| 6 | copyroom-born repo from updated template | **OUT OF SCOPE** — copyroom + template-py sibling PRs not landed (see follow-ups) |
| 7 | `find . -name repoman.lock`; `rg '\[managers\.test\]'`; `rg 'uv sync' src/ modules/` | fixture: none; machine lock: none; src/modules `uv sync` mentions are all safe recommendations |
| 8 | `devenv tasks run repoman:vc:status` (no shell) | **mechanism proven** via probe tasks: the exact generated exec (`"${cfg.toolchainBin}"/gitman status`) resolves gitman from the shared venv with no shell. Task "failure" = gitman exit 1 on the repo's desync state; `repoman:test`'s failure is `lint-imports: command not found` because the devenv task PATH lacks the consumer venv bin — a pre-existing task-runner quirk (deviations 10) |

## Definition-of-done

- ✅ `devenv shell -- pytest -q` → **95 passed** (machine-mode, uv-declared-manager, `test_modules_nix.py`)
- ✅ `rg -n 'venvBin' modules/` → only `modules/managers/testee.nix`
- ✅ `rg -n 'builtins.getEnv' modules/` → nothing
- ✅ `repoman doctor` in the migrated consumer: `toolchain:venv`/`toolchain:lock`/`lock:{copy,git}`/`uv:test` OK, **no `lock:test` row**
- ✅ acceptance: second `uv sync --all-extras --dry-run` → **zero uninstalls** (was 33)
- ✅/⚠ `devenv tasks run repoman:vc:status` without the shell: runs (proven); exit-1 is repo-state + task-PATH quirks, not toolchain resolution
- ✅/⚠ no consumer retains `repoman.lock` (fixture: deleted; `image-gen-pipeline`: a jj snapshot reverted the `git rm` — the owner deletes via `jj`, deviations 7); machine lock has no `[managers.test]`

---

## Deviations from IMPLEMENTATION_GUIDE.md (with rationale)

1. **Step 9 mostly vanished.** The guide targets `src/repoman/devman/assets/{docs,skills,articles}` —
   that tree was **deleted** by the last two commits before this project (59d4b11 moved devman assets
   into the genome, template-py's `template/.agents/`; install-skills now writes only the entrypoint
   router; the `.devman-source` MANIFEST is retired). In-repo step 9 reduced to: the fixture's
   checked-in `.agents/devenv/**` copies (updated in place — there is nothing to regenerate), root
   `CONCEPT.md` + `SPIKE.md` superseded-notes, and `docs/SKILLS.md` (which needed **no** change — it
   never claimed repoman-sync installs the toolchain). No devman version bump was possible (no
   MANIFEST exists).
2. **`installed:<key>` detail is install-aware** (guide: "unchanged"). The old detail "not on PATH —
   run repoman-sync" is now wrong for both classes: toolchain managers heal via
   `repoman-sync --machine`, uv managers via `uv sync`. Kept the change; tests assert both.
3. **Name-normalisation test uses `TESTEE`** (guide suggested `Testee`/`test_ee`). PEP 503 folds
   `-_.` runs to `-` and lowercases: `"Test_EE"` → `"test-ee"` ≠ `"testee"`. The implementation is
   correct; the guide's example was not a match.
4. **`test_machine_skips_venv_creation_when_present`** needs `chmod +x` on the stub `bin/python` —
   the script's gate is `-x`, and `write_text` creates 0644 files.
5. **Fixture regeneration is manual now.** Guide step 10.5 said re-run `install-skills` to refresh
   `.agents/devenv/**` — install-skills no longer writes those (genome-owned); the doc surgery was
   applied to the checked-in copies directly.
6. **Devenv eval-cache gotcha found empirically.** After editing `modules/`, the consumer's eval
   stayed stale until `rm -rf .devenv/nix-eval-cache.db*` (this is documented devenv behavior in the
   fixture's own `lock-and-cache.md`, but it bit during dogfooding; `devenv update` is the fleet path).
7. **Consumer migration on a jj repo.** `image-gen-pipeline` is jj-managed; `git rm repoman.lock`
   and the devenv.yaml/nix edits were **reverted by a jj snapshot/export** (the file came back
   byte-identical to HEAD). The orphan deletion and migration edits must be a **jj change**, not a
   git operation. The `lock:orphan` doctor check now catches exactly this leftover — a live
   demonstration of its purpose.
8. **`uv pip install --all-extras -e .` does NOT work on uv 0.11.28** — errors "Requesting extras
   requires a `pyproject.toml`…". The FINDINGS' verified command didn't reproduce. `uv pip install
   -e .` works (add-only). The documented install command is `uv sync --all-extras` (now safe), and
   the fixture docs say exactly that; the pip-style line is only mentioned as "installs neither
   groups nor extras".
9. **One-time `uv lock --upgrade-package testee` anomaly.** In the first row-5 run the lock shrank
   42→29 and dropped testee/ty/typer. Could **not** reproduce on the byte-identical lock+pyproject
   afterwards (same command → 42 pkgs, testee intact). Plain `uv lock` restores the group. Recorded
   as a sharp edge: a path-source dev-group can be dropped by a re-resolution; `repoman doctor`'s
   `installed:test` catches the aftermath if a sync then prunes. (The current lock is correct.)
10. **Row-8 task failures are not refactor failures.** (a) `repoman:vc:status` exit-1 is gitman's
    DESYNCHRONIZED status on this repo — the exact exec ran fine in a probe. (b) `repoman:test`
    fails on `lint-imports: command not found` because the **devenv task PATH does not include the
    consumer venv bin** (a pre-existing task-runner quirk: the interactive shell gets the venv
    prepend, tasks don't) — the in-flight architecture test shells out to a venv console script.
    Both predate this refactor and are unrelated to the toolchain move; documented here so the owner
    can decide whether to make task PATH mirror the shell.
11. **`modules/managers/testee.nix` comment** still says "installed by repoman-sync". Left
    untouched — the constraint says *any* diff to that file is a bug. Flagged in follow-ups.
12. **Test-helper refactor folded into PR-A.** The `_run` → `--machine` refactor (guide step 8a)
    landed with PR-A's commit so the tree is green at the PR-A boundary (the old resolver tests
    exercise the script via `--machine` now).

---

## Follow-ups / out of scope

- **copyroom sibling PR** — `demo/fixtures/minimal-python-package/template/pyproject.toml.jinja`:
  render `[dependency-groups] dev = ["testee"]` + `[tool.uv.sources] testee = { git = …, ref = … }`
  (D4), drop the `[project.optional-dependencies] dev` pytest/ruff block; update fixture assertions.
- **template-py sibling PR** — the same `pyproject.toml.jinja` change in the genome, plus any
  README/docs line that says `uv sync` is unsafe or that a new repo needs a `repoman.lock`; and the
  genome's `.agents/devenv/**` doc-surgery revert (uv sync is safe again). A copyroom-born repo
  passing validation rows 2–4 with zero manual edits depends on these.
- **Remaining consumers** — each repoman-enabled repo migrates: declare testee dev-group + sources,
  drop the vendomat input/`vendor.enable`, delete the orphan `repoman.lock` (**via jj on jj repos**),
  `uv sync --all-extras`, `repoman-sync`, `repoman doctor`. `uv.lock` becomes a new commit-worthy
  artifact (the consumer's `.gitignore` doesn't exclude it).
- **testee.nix comment** ("installed by repoman-sync") — worth a one-line correction in a future
  non-project-12 change (constraint forbade it here).
- **devenv task PATH quirk** (deviations 10) — consider making `devenv tasks run` mirror the
  interactive shell's venv PATH, or document that tasks don't see venv console scripts.
- **Row-5 anomaly** (deviations 9) — if it recurs, file against uv; `repoman doctor`'s
  `installed:test` is the safety net.
