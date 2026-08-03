# Kickoff prompt — Refactor: system-wide shared toolchain + per-repo testee (implementation planning)

Paste the block below into a **fresh session in the `repoman` repo** to begin. This session's job is
**implementation planning only — do NOT implement.** Produce the `IMPLEMENTATION_GUIDE.md`; do not
edit `src/`, `modules/`, `tests/`, or the consumer repo this pass. You *may* run read-only commands
and safe experiments in scratch locations (see §3.0) to verify that the plan's mechanics hold.

---

You are planning the **refactor that eliminates the `uv sync` footgun** in **repoman**
(`/home/andrew/Documents/Projects/repoman`), the devenv meta-module composing the `*man` manager
family. The owner has **decided the end-state** (project 12 CONCEPT §1/§7): split the manager family
along the one seam that matters — *does the tool import the consumer's code?* — and give each half
the install model it deserves:

1. **Pure-CLI managers** (`repoman`, `gitman`, `copyroom`, `docman` + their libs, incl. the
   `pyjutsu` wheel) never touch a consumer's package → install **once, system-wide**, in a
   repoman-owned shared venv; every repoman repo pulls them onto PATH. One instance, one upgrade
   clock, zero per-repo copies.
2. **testee** is the only manager whose tools (pytest/ruff/ty/import-linter) execute *inside* the
   consumer codebase and must import the consumer venv → declare it **as a per-repo dev dependency**
   in each consumer's `pyproject.toml` (uv-managed, `uv.lock`-pinned, deliberately visible — the
   owner explicitly wants testee's use to be an explicit project declaration, not a hidden install).

Consequences the plan must deliver, **by construction not by documentation**: `uv sync` in a consumer
can only prune app-graph packages (footgun dead); no venv has two co-managers; **zero testee code
changes** (it lives in the same venv as today); consumers drop `vendomat`, `vendor.enable`, and the
per-repo `repoman.lock`.

## 1. Background you need

- **The footgun (measured):** `devenv shell -- uv sync --all-extras` in `../image-gen-pipeline`
  uninstalled **33 of 52 packages** from `.devenv/state/venv` (the whole toolchain closure incl.
  `repoman` itself — so the conductor couldn't even run its own doctor). Root cause: the venv is
  co-managed by `repoman-sync` (add-only `uv pip install` from `repoman.lock`) and uv's project
  machinery (`uv sync` prunes to `uv.lock`), which never read each other's manifests.
- **The decision history:** project 11's FINDINGS §1 (model + 33-package set), §6–7 (why the shared
  single instance + per-repo testee is the owner-decided hybrid). This project's CONCEPT.md is the
  blueprint; your job is to turn it into a verified, phase-by-phase implementation guide.

## 2. Read these first, in order

1. `.scratch/projects/12-toolchain-single-instance/CONCEPT.md` — the blueprint. **Treat it as a
   hypothesis, not gospel**: every load-bearing claim must be confirmed against the code or marked
   as a correction in your guide.
2. `.scratch/projects/11-uv-sync-prunes-toolchain/FINDINGS.md` — §1 (two-mechanism model, prune set),
   §6–7 (the option analysis and the hybrid decision).
3. `modules/devenv.nix` — options, `scripts.repoman-sync`, `env.*` exports, enterShell.
4. `modules/scripts/repoman-sync.sh` — the resolver (TOML → targets, `path:`/`wheel:`/`git+` kinds),
   the `UV_FIND_LINKS` guard, add-only install, `repoman install-skills` tail.
5. `modules/managers/{gitman,copyroom,docman,testee}.nix` — the `${venvBin}/<m>` absolute-path task
   execs (gitman/copyroom/docman must become PATH-resolved; testee stays), gitman's `nativeBuild`
   escape hatch.
6. `src/repoman/checks.py` — `lock:*` / `installed:*` / `provisioned:*` self-checks; the
   uv-declared-manager awareness the plan needs (else `lock:test` FAILs for every consumer).
7. `../testee/pyproject.toml` (deps that make one dev-group declaration pull the whole verify stack)
   and `../testee/src/testee/adapters.py` `tool_executable()` + `config.py:91` `python` option (the
   interpreter-resolution seam that makes "testee in the consumer venv" work with zero changes).
8. A consumer for verification: `../image-gen-pipeline/pyproject.toml`, `devenv.yaml`,
   `devenv.nix`, `repoman.lock`.
9. `../copyroom/demo/fixtures/minimal-python-package/template/pyproject.toml.jinja` — the template
   fixture the plan must extend (note it currently uses `[project.optional-dependencies] dev`, not
   uv-native `[dependency-groups]`).
10. `devenv.yaml` / `devenv.nix` (repoman's own repo) — for the machine-bootstrap context question
    (vendomat input vs from-source pyjutsu build).

## 3. Planning tasks

### 3.0 Confirm the load-bearing mechanics (read-only / scratch only)

Verify each claim the plan rests on. Where a claim is wrong, record the correction in the guide.
Safe techniques only — do not modify `src/`, `modules/`, `tests/`, or the consumer; do not run a
real (non-dry) `uv sync` against any real repo venv:

- **uv mechanics in a scratch project (safe, /tmp):** create `/tmp/repoman-12-scratch/pyproject.toml`
  with `[project] name/version/requires-python` + `[dependency-groups] dev = ["testee"]` +
  `[tool.uv.sources] testee = { path = "/home/andrew/Documents/Projects/testee" }`, set
  `UV_PROJECT_ENVIRONMENT=/tmp/repoman-12-scratch/.venv`, run `uv sync`, and confirm: testee +
  pytest/ruff/ty/import-linter land in the scratch venv; the install is additive (re-run with an
  unrelated package pre-installed → pruned); `uv.lock` is written. This proves the "testee survives
  pruning because it's in the graph" claim without touching any real repo.
- **PATH precedent:** confirm in the consumer shell that `UV_PROJECT_ENVIRONMENT` and the venv PATH
  prepend are set by devenv's *generated shell script at runtime* (`.devenv/shell-*.sh`) — this is
  the precedent for how the meta-module should prepend the shared venv (runtime, not nix-eval, or
  `builtins.getEnv`-computed — decide and justify; CONCEPT §11.1).
- **No name collisions:** diff `ls <consumer venv>/bin` vs the pure-CLI names (repoman, gitman,
  copyroom, docman) — the PATH-precedence claim must be exact. Note: `ruff`/`ty`/`pytest` will exist
  in the consumer venv (testee's deps) — confirm they're absent from the shared-venv plan.
- **doctor reachability:** confirm `repoman doctor` (from the shared venv, once moved) can resolve
  `testee` on PATH when the consumer venv is active, and that `installed:test` (`shutil.which`)
  keeps working.

### 3.1 Resolve the CONCEPT open questions (CONCEPT §11) — pick a default for each, with justification

1. Shared-venv path resolution in nix (runtime prepend vs `builtins.getEnv "HOME"`/`"XDG_DATA_HOME"`
   at eval). Recommend the mechanism `modules/devenv.nix` will use; note single-user vs multi-user.
2. Machine-lock location (repoman checkout root — recommended — vs `~/.config/repoman/repoman.lock`).
3. pyjutsu wheel bootstrap context (repoman's own devenv gains the `vendomat` input vs one-time
   from-source `maturin` build). State the recommended default and the fallback.
4. `[dependency-groups] dev` vs `[project.optional-dependencies] dev` in the template (uv-native
   group is default-on for `uv sync`; `uv pip install -e .` installs neither — pick one and make the
   docs agree).
5. Doctor UX for uv-declared managers — design the `checks.py` change to be testee-specific now or
   generic over a marker (e.g. `REPOMAN_UV_MANAGERS`). Recommend the generic shape; it costs
   nothing extra.

### 3.2 Produce the phase-by-phase implementation plan

Order for lowest risk — each phase lands independently and leaves the ecosystem functional (machine
side first, consumers migrate explicitly):

- **Phase 1 — machine toolchain:** `repoman-sync --machine` (CLI contract below) + machine
  `repoman.lock` at the repoman checkout + `REPOMAN_TOOLCHAIN_VENV` convention + one-time bootstrap
  of the shared venv. Existing consumers keep working untouched (repoman-sync still installs
  per-repo in this phase).
- **Phase 2 — meta-module wiring:** PATH prepend + env exports; `gitman/copyroom/docman.nix` task
  execs → PATH-resolved; consumer-mode `repoman-sync` shrinks to "ensure shared venv exists + skills
  + docs". Specify the first-run UX when the shared venv is missing (warn + one-liner, or auto-run —
  pick and justify).
- **Phase 3 — doctor:** `checks.py` uv-declared-manager awareness (generic marker), exact check
  semantics and wording.
- **Phase 4 — template:** copyroom fixture `pyproject.toml.jinja` renders the testee dev group +
  `[tool.uv.sources]` (fleet git ref, dev path override). Note the remote `template-py` needs the
  same change (can't be edited from this session — flag it as an external dependency).
- **Phase 5 — consumers:** the exact edit list for `../image-gen-pipeline` (pyproject dev group,
  drop vendomat input + `vendor.enable`, delete `repoman.lock`).
- **Phase 6 — docs/skills:** revert the 11-project's doc-surgery in
  `src/repoman/devman/assets/{docs,skills,articles}` (the guidance becomes safe again); specify the
  new wording, including the note that testee is a declared dev dep.

For **every phase**: the exact files touched, a description of each edit (not full diffs), the
per-phase acceptance check, and the rollback (what it looks like to undo just that phase).

### 3.3 Specify the `repoman-sync --machine` contract precisely

Flags (`--machine`, maybe `--check`), env vars read (`REPOMAN_TOOLCHAIN_VENV`, `REPOMAN_ROOT`,
`UV_FIND_LINKS`), what it creates (venv + lock-resolved install), idempotency, exit codes (0/2
consistent with the family), the missing-lock and missing-wheelhouse failure modes, and how the
existing TOML resolver / `wheel:` guard are reused. Also state what consumer-mode `repoman-sync`
does after Phase 2 (ensure shared venv + `repoman install-skills`), and how `repoman doctor`'s
heal message changes.

### 3.4 Validation checklist

Refine CONCEPT §9 into per-phase acceptance tests plus the end-to-end checklist, all runnable via
`devenv shell -- <cmd>` in `../image-gen-pipeline` (and one copyroom-born repo). The acceptance
test that defines "done": after the full migration, `devenv shell -- uv sync --all-extras` in the
consumer shows **zero uninstalls** (was 33), `gitman status` + `testee verify --mode quick` +
`repoman doctor` all work, and a `copyroom new` birth from the updated template passes the same
checks with no manual edits.

### 3.5 Risk register

Surface risks the CONCEPT may under-weight: first-run UX when the shared venv is absent; the
`repoman.managers` semantic drift (no longer gates install — only wiring/skills); stale per-repo
`repoman.lock` files left behind by older consumers (are they harmless? do we delete or ignore?);
`repoman doctor`'s `provisioned:*` nix-input signals if a consumer keeps a stale `[managers.test]`
entry; multi-user machines; and any dependency on the remote `template-py` being updated in lockstep.

## 4. Constraints

- **Planning only:** do not edit `src/`, `modules/`, `tests/`, the consumer, or the copyroom
  fixture this pass. Experiments confined to `/tmp` scratch projects and read-only/dry-run commands.
- **The end-state is decided** (CONCEPT §1/§7): pure-CLI managers system-wide single instance;
  testee per-repo as a declared dev dependency. Do not re-open options A–D; the plan executes the
  decision.
- **Never break the toolchain:** every documented command must leave `gitman`/`testee`/`copyroom`/
  `repoman` working.
- **`repoman-sync` stays add-only** (its semantics are load-bearing) — the `--machine` mode reuses
  the existing resolver; nothing is removed from the script, only added + re-pointed.
- Preserve the "`devenv shell -- <cmd>` is the front door" and "run everything through the
  devenv-managed uv" conventions.
- **testee's per-repo visibility is a requirement**, not a suggestion: the template and consumer
  edits must declare it in `pyproject.toml`, not hide it.

## 5. Deliverable

`IMPLEMENTATION_GUIDE.md` in `.scratch/projects/12-toolchain-single-instance/` containing:
(1) confirmed mechanics — what held from CONCEPT, what needed correcting, with evidence;
(2) resolved open questions (CONCEPT §11) with decisions; (3) the phase-by-phase plan with
file-level edit descriptions, per-phase acceptance, and rollback per phase; (4) the
`repoman-sync --machine` CLI contract; (5) the validation checklist; (6) the risk register. Tick a
progress log at the top as you go.

Run all in-repo commands via `devenv shell -- <cmd>`.
