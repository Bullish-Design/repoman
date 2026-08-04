# PROGRESS — 12-toolchain-single-instance (implementation)

**Repo:** `/home/andrew/Documents/Projects/repoman` · **Status:** implemented + validated + follow-ups in progress
**Commits:** `448b9cf` PR-A (machine sync) · `4509d1f` lock follow-up · `b6bddce` PR-B (semantic switch) · `fa6d7f5` PR-C (fixture/docs)

---

# Follow-ups log (kickoff session)

## Re-baseline (kickoff §2) — all green

- **Shared toolchain venv:** present — `~/.local/share/repoman/venv/bin` has `repoman gitman copyroom docman`
  (+ pyjutsu wheel), `repoman-toolchain.toml` present.
- **Acceptance test (reference consumer):** `image-gen-pipeline` → `devenv shell -- uv sync --all-extras --dry-run`
  = **"Would make no changes"** (42 packages), held at session start and after the jj cleanup.
- **VCS per consumer (decides `repoman.lock` deletion):** jj = argentic, flora, foreman, forgelab, image-gen-pipeline,
  inferference, lodestar, nix-paseo, shellij; git = flora-core, loci.nvim, nix-desktop, nix-nvim, nix-secrets, poddantic.
  `fleetman` = false positive (a `*man` tool itself — no `repoman.lock`). All 15 candidates hold a `repoman.lock`.
- **Ambient pollution found:** `/tmp/pyproject.toml` (a boomtube scratch) carried `--cov` addopts that broke pytest
  runs in `/tmp`-born repos (`pytest: unrecognized arguments: --cov=boomtube`). Moved to `/tmp/pyproject.toml.boomtube-scratch.bak`.

## §2.2 image-gen-pipeline jj-side cleanup — DONE (jj change `owpzkyrt`)

Committed as a jj change on top of `main*` (WIP Phase-1 untouched):
1. `devenv.yaml` — vendomat input + `vendomat/modules` import removed.
2. `devenv.nix` — `vendor.enable = true` + comment removed; venv comment updated (hosts app + testee).
3. `repoman.lock` deleted via jj (plain `rm` — jj snapshots the deletion; never `git rm`).
4. `uv.lock` **committed** (42 pkgs, testee group intact — no row-9 anomaly).
Post: `repoman doctor --self-only` has **no `lock:orphan` row**; all `toolchain:*`/`lock:*`/`uv:test` OK;
acceptance dry-run still "Would make no changes".

## WS-1 — sibling PRs — DONE, both validated

### copyroom PR (branch `project-12-sibling-template`, commit `0ace576`)
`demo/fixtures/minimal-python-package/template/pyproject.toml.jinja`: `[project.optional-dependencies] dev
= [pytest, ruff]` → `[dependency-groups] dev = ["testee"]` + `[tool.uv.sources] testee = { path =
"{{ testee_dev_root }}/testee" }`. Added the `testee_dev_root` copier question (default
`/home/andrew/Documents/Projects`) + demo-answers entry — the fixture had no dev-root variable.
**Observation (deviation):** the guide's §11 "fixture expected-output assertions" do NOT exist for the copyroom
demo fixture (no test references it; only stale `.devenv` shell files). The real assertions are template-py's
`golden/`, refreshed below.

### template-py PR (branch `feat/verify-agent-files`, commits `6826bb1` + `4b1f132`, tag `v0.1.6`)
- `template/pyproject.toml.jinja` — same change as copyroom; reused the existing `repoman_dev_root` scenario
  variable (no new question needed — deviation from the kickoff's `testee_dev_root`, same effect).
- **deleted `template/repoman.lock.jinja`**; dropped the `test -f repoman.lock` check from `copyroom.yml`.
- `template/devenv.yaml.jinja` — vendomat input + import removed.
- `template/devenv.nix.jinja` — `vendor.enable` removed; venv comment updated.
- `.agents/devenv/**` — 5 files (adopting-the-man-family, authoring-a-manager-module, ci-inside-devenv,
  command-not-found-in-shell, languages-python) replaced with the canonical post-project-12 text from the
  repoman fixture (byte-identical base, only the doc-surgery regions differed). `devenv-python-venv` +
  `devenv-troubleshoot` skills fixed (uv sync = recommended; manager CLIs → `repoman-sync --machine`).
- `AGENTS.md`, `README.md`, born-repo `README.md.jinja` — no per-repo lock; `uv sync --all-extras` safe again.
- `golden/py/basic` refreshed at v0.1.6 (workshop flow: feat commit → tag → `golden --refresh`); `repoman.lock`
  deleted from golden. `copyroom golden py basic` = clean. `release-check` matrix/worktree pass; probe-scenario
  golden "diffs" is pre-existing (probe has no golden by design, checks are advisory in v0.x).

### Row-6 validation — **PASSED (zero manual edits)**
1. **copyroom-born** (`copyroom new` on the fixture): `uv sync --all-extras` ✓, `testee verify --mode quick`
   PASSED ✓, `gitman status` ✓ (after `gitman init --colocate`, the born-repo bootstrap), `repoman doctor
   --self-only` exit 0 ✓, dry-run = no changes ✓. Born repo: no `repoman.lock`/vendomat/`vendor.enable`.
   (The minimal fixture has no devenv, so `DEVENV_ROOT` + `--allow-outside-devenv` substituted for the devenv
   shell's env — noted; the real row-6 target is the genome, below.)
2. **genome-born** (`copyroom new` on template-py @ v0.1.6 with `--trust`): `devenv shell -- uv sync
   --all-extras` ✓, `testee verify --mode quick` all-passed ✓, `gitman status` clean ✓, `repoman doctor
   --self-only` **all-OK including `skill:entrypoint`/`tool-shipped`** ✓, acceptance dry-run = "Would make no
   changes" ✓. Born repo has no `repoman.lock`, no vendomat, no `vendor.enable`.

## WS-2 — fleet migration — DONE (12/14 committed; flora unmigrated, forgelab partial)

**Migration log** (VCS → files → dry-run uninstall count vs real sync → doctor → acceptance):

| Consumer | VCS | Committed (sha) | Files touched | Dry-run uninstall | Real sync | Doctor | Acceptance |
|---|---|---|---|---|---|---|---|
| image-gen-pipeline | jj | `owpzkyrt` (§2.2) | devenv.yaml, devenv.nix, repoman.lock del, uv.lock | n/a (pre-session) | ✓ | all OK | Would make no changes |
| argentic | jj | `wxwlnpqp` | pyproject, devenv.yaml, devenv.nix, devenv.lock, repoman.lock del, uv.lock, .agents/skills/repoman | 17 (toolchain closure) | ✓ | all OK | Would make no changes |
| flora-core | git | `2862ad5` | pyproject, devenv.yaml, devenv.nix, .gitignore (un-ignore uv.lock), uv.lock, repoman.lock del, .agents/skills/repoman | 0 (venv empty) | ✓ | all OK | Would make no changes |
| foreman | jj | `tllkqpyz` | pyproject, devenv.yaml, devenv.nix, devenv.lock, repoman.lock del, uv.lock, .agents/skills/repoman | 20 (toolchain closure) | ✓ | all OK | Would make no changes |
| forgelab | jj | `mpsvnnnt` | devenv.yaml, devenv.nix, devenv.lock, repoman.lock del, .agents/skills/repoman | 13 BUT **app closure** (fornix + deps) — uv sync NOT run | — | toolchain OK | n/a (no uv graph) |
| inferference | jj | `qllttmup` | pyproject, devenv.yaml, devenv.nix, devenv.lock, repoman.lock del, uv.lock, .agents/skills/repoman | 18 (toolchain closure) | ✓ (needs NIXPKGS_ALLOW_UNFREE=1) | all OK | Would make no changes |
| loci.nvim | git | `e9e6863` | devenv.nix, repoman.lock del | n/a (no pyproject) | n/a | toolchain OK | n/a |
| lodestar | jj | `mynppsqw` | pyproject (testee appended to existing dev group), devenv.yaml, devenv.nix, devenv.lock, repoman.lock del, uv.lock, .agents/skills/repoman | 0 (venv empty) | ✓ | all OK | Would make no changes |
| nix-desktop | git | `b188ad5` | devenv.nix, repoman.lock del | n/a | n/a | toolchain OK | n/a |
| nix-nvim | git | `a369b66` | devenv.nix, repoman.lock del | n/a | n/a | toolchain OK | n/a |
| nix-paseo | jj | `qoozvzzx` | devenv.yaml, devenv.nix, devenv.lock, repoman.lock del, .agents/skills/repoman | n/a | n/a | toolchain OK | n/a |
| nix-secrets | git | `14f5223` | devenv.nix, repoman.lock del | n/a | n/a | toolchain OK | n/a |
| poddantic | git | `9ad60a5` | pyproject, devenv.yaml, devenv.nix, devenv.lock, repoman.lock del, uv.lock, .agents/skills/repoman | 0 (venv empty) | ✓ | all OK | Would make no changes |
| shellij | jj | `zpvsvtvs` | pyproject, devenv.yaml, devenv.nix, devenv.lock, repoman.lock del, uv.lock, .agents/skills/repoman | 0 (venv empty) | ✓ | all OK | Would make no changes |
| **flora** | jj | **UNMIGRATED** | — | 53 BUT **app closure** (flora-qc + QC stack via venv.requirements) — uv sync NOT run | — | — | — |

**Left unmigrated / partial, with reason:**
- **flora** — the venv is `venv.requirements`-managed (QC stack `-e .[qc,qc-embed,matte]` +
  import-linter installed ADDITIVELY outside the uv graph; the devenv.nix comment says exactly
  "uv sync would PRUNE every package outside uv.lock"). A dry-run uninstalls 53 pkgs incl.
  flora-qc + the QC deps — app closure, NOT the toolchain closure. Its WIP (feat(089) phase 3)
  was committed by another session mid-migration; tree left clean + untouched. Owner decision:
  convert the QC stack to uv extras/groups (then `uv sync --all-extras` is safe) or keep
  venv.requirements and skip uv sync. The pre-existing footgun stays live by design.
- **forgelab** — same venv.requirements class (its app dep fornix is an editable outside the uv
  graph). The devenv/lock split + orphan deletion ARE committed (the committed state is
  consistent: no vendomat anywhere); `uv sync` deliberately NOT run (would prune fornix). The
  venv stays venv.requirements-managed. Also: `devenv.nix` carries the in-flight FORNIX
  mkForce edit from the working copy (same file — noted in the commit message).

**Procedure notes (VCS-aware, jj):** on jj repos, `jj commit <paths...>` puts only the selected
paths into the commit and moves the rest to a new working copy — used to keep owner WIP
(skills/, .scratch/, src/) separate from migration commits (foreman, lodestar, argentic,
forgelab). When devenv.yaml changes, `devenv.update` regens devenv.lock and that MUST be folded
into the migration commit or the committed state is inconsistent (lodestar: folded via
`jj edit` + `jj restore devenv.lock --from <wc>` + `jj squash --into <mig>` + re-describe —
`jj squash --into` replaces the destination description with the source's). In argentic a 1-line
pyproject description change was swept into the migration commit (content preserved; noted
here).

## WS-3 — fleet lock shape — DECISION + flag

- **Decision (kept):** the committed `repoman.lock` at the checkout stays the DEV shape
  (`path:` sources, `--editable`). One lock does NOT serve both dev and fleet — machine locks
  are per-machine by design (D2 + guide §1).
- **Fleet form:** swap each `path:` for `git+https://github.com/Bullish-Design/<repo>@vX.Y.Z`
  (resolver passes git sources verbatim — `test_git_https_source_passes_through_verbatim`).
  Documented in `repoman.lock`'s header + `CONCEPT.md` §6.
- **Flag (implemented, e0689c1):** `REPOMAN_LOCK` env override — `repoman-sync --machine` uses
  it instead of `$REPOMAN_ROOT/repoman.lock`, so a CI runner can point at a fleet-shaped lock
  without editing the checkout. Pure env-var override (unset = current behaviour), add-only,
  two tests. **Flagged for owner acknowledgement** — the kickoff marked it "only if the owner
  wants CI convenience"; implemented per its full spec since it is inert + additive, and
trivially revertible (revert e0689c1).

## WS-4 — in-repo leftovers — DONE (committed separately)

1. **testee.nix comment** — 5207977: "installed by repoman-sync" → "per-repo uv dev dependency
   (project 12)". Comment only; `${venvBin}/testee` wiring unchanged.
2. **Task-PATH quirk — FIXED** (5207977): `devenv tasks run` doesn't prepend the consumer venv
   bin; enterShell runs per task, so `export PATH="${config.devenv.state}/venv/bin:$PATH"` in
   the meta-module's enterShell fixes tasks and is a no-op for the shell. Guarded by
   `test_meta_module_prepends_consumer_venv_bin_for_tasks`; validated with `devenv tasks run
   repoman:test` in image-gen-pipeline — previously `FileNotFoundError: lint-imports` (the arch
   test), now passes.
3. **Release tag** — 382c717: version 0.3.0 → 0.4.0 (meta-module contract changed), tagged
   `v0.4.0`; `repoman-sync --machine` re-run upgrades the shared venv to 0.4.0 (verified
   `repoman.__version__` = 0.4.0). Consumer pickup: `devenv update repoman` + eval-cache refresh.
4. **Row-9 anomaly** — no code; not observed during WS-2 (all lock writes kept testee intact).

## Deviations from the kickoff (with rationale)

1. **copyroom fixture has no expected-output assertions** — guide §11's "update the fixture's
   expected-output assertions" doesn't apply to `demo/fixtures/minimal-python-package` (no test
   references it). The real assertions are template-py's `golden/`, refreshed at v0.1.6.
2. **template-py uses `repoman_dev_root`** (its existing scenario variable) for the testee uv
   source, not the kickoff's `testee_dev_root` — same effect, zero new scenario churn. The
   copyroom fixture got a NEW `testee_dev_root` copier question (it had no dev-root variable).
3. **flora + forgelab are venv.requirements-managed** — not uv-graph-managed; `uv sync` would
   prune the APP closure (flora-qc / fornix), violating the dry-run rule. flora left unmigrated;
   forgelab committed the safe split only. Both documented for the owner.
4. **WS-3 flag implemented** although gated "if the owner wants it" — see WS-3 note above.
5. **jj working-copy WIP handling** — path-scoped `jj commit` + the squash dance above; a 1-line
   description (argentic) and 2-line FORNIX env edit (forgelab) were swept into migration
   commits (content preserved, noted in messages/log).
6. **`devenv.lock` must ride with the migration** — `devenv update` after the devenv.yaml edit
   regenerates it; the committed devenv.yaml/lock pair must be consistent (lodestar case).
7. **inferference eval needs `NIXPKGS_ALLOW_UNFREE=1`** (CUDA/llama.cpp deps) — pre-existing
   repo requirement, not migration-related; recorded so future shells know.
8. **image-gen-pipeline's tree is live** — a parallel session added phase-2 WIP to the working
   copy after §2.2; my §2.2 change is committed and untouched.
9. **flora-core un-ignored uv.lock** — the .gitignore line "uv lockfile (project uses devenv +
   repoman, not raw uv)" was project-11 doc surgery; uv.lock is now commit-worthy.

## Remaining follow-ups

- **flora** — owner decides venv.requirements vs uv-graph (or keeps old model); then the
  migration + the stale "repoman-sync installs the manager CLIs" comment in its venv.requirements
  block.
- **forgelab** — owner decides the fornix venv.requirements arrangement before any `uv sync`.
- **Sibling PRs** — copyroom `project-12-sibling-template` (0ace576), template-py
  `feat/verify-agent-files` (6826bb1 + 4b1f132, tag v0.1.6) need review + merge + push.
- **repoman v0.4.0** — tag is local; consumers pick it up via `devenv update repoman` (+ the
  eval-cache refresh, deviation 6).
- **The fleet-form lock** — build one (`git+https@ref` sources) when a non-dev machine or CI
  needs it; `REPOMAN_LOCK` already points at it.

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
