# Kickoff prompt — implement project 12's follow-ups: sibling PRs, fleet migration, leftovers

Paste the block below into a **fresh session in the `repoman` repo** to begin. This session
**implements** the follow-up work that project 12 (toolchain single instance) deliberately deferred.
The refactor itself is done and validated; everything here is the remaining 15% that spans other
repos and the rest of the fleet.

**Before pasting:** commit or stash the working tree (`git status` in
`/home/andrew/Documents/Projects/repoman` must be clean at `6cedd67`). The sibling repos
(`copyroom`, `template-py`) and every consumer are **separate repos with their own work-in-flight** —
start from a clean, current state and make surgical edits.

---

You are implementing the **project 12 follow-ups** in the Bullish-Design fleet. Context: project 12
split the `*man` manager family by install model — pure-CLI managers (repoman/gitman/copyroom/docman
+ pyjutsu) install once, system-wide, in `$REPOMAN_TOOLCHAIN_VENV` (bootstrapped by
`repoman-sync --machine` from the machine `repoman.lock` at the repoman checkout); **testee** is a
per-repo uv dev dependency declared in each consumer's `pyproject.toml`. The refactor landed in the
repoman repo (4 commits) and was validated in `image-gen-pipeline`: second `uv sync --all-extras
--dry-run` = **"Would make no changes"** (was 33 uninstalls). What remains, in priority order:

1. **WS-1 — the sibling PRs (the real unlock).** The copyroom repo's in-repo template fixture and
   the template-py **genome** still ship the OLD shape: a per-repo `repoman.lock.jinja`, the
   `vendomat` input, `vendor.enable`, and a `pyproject.toml.jinja` that tells agents "pytest/ruff/ty
   are installed by repoman-sync". Every repo born from these templates gets the pre-refactor shape
   and needs manual edits — validation row 6 (copyroom-born repo passes with zero manual edits) is
   the one project-12 acceptance row that cannot pass from inside the repoman repo.
2. **WS-2 — fleet migration.** ~15 consumers still run the old per-repo model (each holds a
   `repoman.lock`). The old model still works — nothing forces the move — but every consumer with a
   `repoman.lock` still has the project-11 footgun latent (anyone running `uv sync` prunes the
   toolchain from their venv).
3. **WS-3 — fleet lock shape decision.** The machine `repoman.lock` uses `path:` dev sources; the
   fleet form is `git+https@ref`. Decide and (if the owner wants it) add the small override flag.
4. **WS-4 — in-repo leftovers.** A stale comment in `testee.nix` (forbidden to touch during the
   refactor), the devenv task-PATH quirk discovered during validation, and a repoman release tag so
   consumers can `devenv update repoman`.

## 1. Read these first, in order

1. `.scratch/projects/12-toolchain-single-instance/PROGRESS.md` — **the authoritative handoff.**
   Contains the §12c validation table with real output, the 12 documented deviations (several bite
   hard: the jj-repo gotcha, the `uv pip install --all-extras` uv quirk, the task-PATH quirk, the
   one-time `uv lock --upgrade-package` anomaly), and the follow-ups section you are implementing.
2. `.scratch/projects/12-toolchain-single-instance/IMPLEMENTATION_GUIDE.md` — §11 (the exact
   template changes for copyroom + template-py, including the "update the fixture's expected-output
   assertions" note) and §12b/§12c (the per-consumer migration procedure and validation rows).
3. `.scratch/projects/12-toolchain-single-instance/KICKOFF_IMPLEMENTATION.md` — the project-12
   implementation kickoff; §1/§4 restate the end-state and the constraints that still hold.
4. The repoman code you just shipped (quick re-orientation): `repoman.lock`,
   `modules/scripts/repoman-sync.sh`, `modules/devenv.nix`, `src/repoman/checks.py`,
   `src/repoman/registry.py`.
5. The external repos you will edit:
   - `/home/andrew/Documents/Projects/copyroom/demo/fixtures/minimal-python-package/template/pyproject.toml.jinja`
     (currently `[project.optional-dependencies] dev` with pytest/ruff — the project-11-era shape)
   - `/home/andrew/Documents/Projects/template-py/` — the genome: `template/pyproject.toml.jinja`,
     `template/repoman.lock.jinja` (**the whole file is obsolete**), `template/devenv.yaml.jinja`
     (declares `vendomat` + `vendomat/modules` import), `template/devenv.nix.jinja`
     (`vendor.enable = true;`), plus `golden/`, `generated/`, `scenarios/` (template test
     artifacts that will need regeneration), and any README that says `uv sync` is unsafe.
6. A consumer or two for ground truth: `image-gen-pipeline` (already migrated in the working tree —
   **but its `devenv.yaml`/`devenv.nix` edits were reverted by a jj snapshot**; see §2.2) and any one
   unmigrated consumer from §2.1's list.

## 2. Step 0 — re-baseline (a fresh session can't assume machine state)

Verify before writing code; record each result in `PROGRESS.md` §2:

- The shared toolchain venv exists: `ls ~/.local/share/repoman/venv/bin` → repoman/gitman/copyroom/
  docman; `~/.local/share/repoman/venv/repoman-toolchain.toml` present. If missing, bootstrap once:
  `cd ~/Documents/Projects/repoman && devenv shell -- repoman-sync --machine`.
- The acceptance test still holds in the migrated consumer: `cd ../image-gen-pipeline && devenv shell
  -- uv sync --all-extras --dry-run` → "Would make no changes". (The consumer's working tree has
  in-flight Phase-1 work — do not touch it beyond the jj-side cleanup in §2.2.)
- Determine each candidate consumer's **VCS** (jj vs git): `jj root` / `ls .jj` vs `git rev-parse`.
  This decides how `repoman.lock` gets deleted (§3.2). **The jj gotcha:** on jj repos, `git rm`
  (and even `git`-level edits to tracked files) are silently reverted by the next jj snapshot/export
  — the deletion and the devenv edits must be made as **jj operations** (`jj file untrack` /
  `jj restore`-equivalent or a `jj new` change), never plain git.

### 2.2 Finish image-gen-pipeline's jj-side cleanup (it's the reference consumer)

Its venv is migrated and validated, but the jj snapshot reverted three things. Fix them **as a jj
change** (or document them as the owner's to-do if the implementer shouldn't touch the WIP tree):
1. `devenv.yaml` — remove the `vendomat` input + `vendomat/modules` import (the diff is in
   `PROGRESS.md` §deviations 7).
2. `devenv.nix` — remove `vendor.enable = true;` + its comment.
3. Delete `repoman.lock` via jj (the `lock:orphan` doctor row currently warns about it — a live demo
   of the check; after deletion the doctor should show no `lock:orphan`).
4. Decide `uv.lock` (untracked, new): per uv convention it is commit-worthy for apps — commit it with
   the migration or hand it to the owner explicitly.

## 3. WS-1 — sibling PRs (copyroom + template-py) — do this first

Both are separate repos; land each as its own PR. They are the only work that makes *new* repos
correct, so they gate validation row 6.

### 3.1 copyroom — `demo/fixtures/minimal-python-package/template/pyproject.toml.jinja`

Replace the `[project.optional-dependencies] dev = ["pytest…", "ruff…"]` block with:

```jinja
[dependency-groups]
# testee is a per-repo uv dev dependency (project 12): its tools (pytest/ruff/ty)
# run inside THIS codebase. The pure-CLI managers come from the system-wide
# toolchain venv instead.
dev = ["testee"]

[tool.uv.sources]
# fleet: testee = { git = "https://github.com/Bullish-Design/testee", ref = "vX.Y.Z" }
testee = { path = "{{ testee_dev_root }}/testee" }
```

- Check the fixture's expected-output assertions (the guide's §11 says they exist) and update them.
- **Do not** leave pytest/ruff in the project: they come transitively with testee.

### 3.2 template-py (the genome) — the bigger of the two

1. `template/pyproject.toml.jinja` — same change as copyroom (its current comment block says
   "installed into the venv by `repoman-sync`" — that's the project-11 doc-surgery text; replace it).
2. **Delete `template/repoman.lock.jinja`** — the per-repo lock is obsolete. Check `copier.yml` /
   `copyroom.yml` / any scenario or golden file that references it and remove those references.
3. `template/devenv.yaml.jinja` — drop the `vendomat` input + `vendomat/modules` import.
4. `template/devenv.nix.jinja` — drop `vendor.enable = true;`.
5. Regenerate/update `golden/`, `generated/`, `scenarios/` artifacts so the template's own tests
   pass with the new shape.
6. Any README/docs line that says `uv sync` is unsafe or that a new repo needs a `repoman.lock` —
   revert it (`uv sync --all-extras` is the safe one-liner again).
7. The genome's `.agents/devenv/**` (devenv-literacy docs that ship with the template) — revert the
   project-11 doc surgery the same way the repoman fixture docs were reverted in PR-C: `uv sync
   --all-extras` is the recommended install; `gitman/copyroom/docman: command not found` →
   `repoman-sync --machine`; adoption steps describe the machine bootstrap + testee declaration.

### 3.3 Row-6 validation (the point of WS-1)

From the updated copyroom fixture, birth a fresh repo (`copyroom new` on the fixture) and run the
migration's rows 2–4 **with zero manual edits**: `uv sync --all-extras`, `testee verify --mode
quick`, `gitman status`, `repoman doctor --self-only` all green; second `uv sync --all-extras
--dry-run` = no changes. The born repo must NOT contain `repoman.lock`, vendomat, or `vendor.enable`.

## 4. WS-2 — fleet migration (per consumer, mechanical, dry-run first)

Candidate consumers (discovered by `grep repoman */devenv.yaml`, **verify each**; `fleetman` is a
false positive — it is itself a `*man` tool, not a consumer):

```
argentic  flora  flora-core  foreman  forgelab  image-gen-pipeline (done, see §2.2)
inferference  loci.nvim  lodestar  nix-desktop  nix-nvim  nix-paseo
nix-secrets  poddantic  shellij
```

Per consumer, in this order (the guide §12b procedure, VCS-aware):

1. `pyproject.toml` — **surgical append only**: add `[dependency-groups] dev = ["testee"]` +
   `[tool.uv.sources] testee = { path = "<testee checkout>", or git ref for fleet }`. Preserve every
   existing extra/group verbatim (several consumers have in-flight work; do not reformat). Only
   declare testee if `"test"` is in `repoman.managers` (a pure copy/git consumer doesn't need it).
2. `devenv.yaml` — drop the `vendomat` input + import (with its comment block).
3. `devenv.nix` — drop `vendor.enable` / `vendor.libs` (with comments). Keep everything else.
4. Delete `repoman.lock` — **jj-aware** (§2): `jj` on jj repos, `git rm` on git repos.
5. `devenv shell -- uv sync --all-extras --dry-run` FIRST — the uninstall set must be exactly the
   old toolchain closure (repoman/gitman/copyroom/pyjutsu/copier/…), never app deps. Then the real
   sync. This is the ex-footgun becoming the migration step, by design.
6. `devenv shell -- repoman-sync` (consumer mode: verify toolchain + install entrypoint skill).
7. `devenv shell -- repoman doctor --self-only` — all-OK rows: `toolchain:venv`, `toolchain:lock`,
   `lock:<toolchain managers>`, `uv:test`, no `lock:test`, no `lock:orphan`.
8. Acceptance per consumer: second `uv sync --all-extras --dry-run` → "Would make no changes".
9. Commit: the pyproject/devenv edits, the lock deletion, and `uv.lock` (new, commit-worthy) +
   `.agents/skills/repoman/SKILL.md` if the repo tracks generated skills.

**Watch-outs (all in PROGRESS.md):** eval-cache staleness after the meta-module changed
(`rm -rf .devenv/nix-eval-cache.db*` or `devenv update repoman` — see deviations 6); consumers with
an existing `dev` EXTRA can coexist with the `dev` GROUP (verified — both land in the lock), but
double-check any consumer whose in-flight work collides; `uv pip install --all-extras -e .` errors
on uv 0.11.28 (use `uv sync --all-extras`); do NOT run a real sync until the dry-run uninstall set
is exactly the toolchain closure.

## 5. WS-3 — fleet lock shape (decision, then at most a tiny flag)

- **Restate the constraint (D2 + guide §1):** machine locks are per-machine by design; do NOT try to
  make one `repoman.lock` serve both dev (`path:`) and fleet (`git+https@ref`). The committed lock
  at the repoman checkout is the dev shape for this machine.
- **Decision for the owner** (recommend in your report, don't unilaterally re-lock): keep the dev
  lock; document the fleet form (swap each `path:` to
  `git+https://github.com/Bullish-Design/<repo>@vX.Y.Z` — the resolver passes git sources verbatim,
  proven by `test_git_https_source_passes_through_verbatim`). Where should that doc live?
  `CONCEPT.md` or the lock's own header comment.
- **Optional, only if the owner wants CI convenience:** add `REPOMAN_LOCK` (or `--machine --lock
  <path>`) to `repoman-sync.sh` so a CI runner can point at a fleet-shaped lock without editing the
  checkout. Keep it a pure env-var override of the existing `lock=` resolution; add one test.

## 6. WS-4 — in-repo leftovers (small, in the repoman repo)

1. **`modules/managers/testee.nix` comment** — line 5 says the testee console script is "installed
   by repoman-sync". That is false post-refactor (testee is a uv dev dependency). Fix the comment
   only; the wiring (`${venvBin}/testee`) stays. (Project 12's constraint forbade touching the file;
   it no longer applies.)
2. **devenv task-PATH quirk** — `devenv tasks run` does NOT put the consumer venv bin on PATH (the
   interactive shell does; tasks don't), so a task that shells out to a venv console script (e.g.
   the app's `lint-imports` arch test) fails under `devenv tasks run`. Pre-existing, unrelated to the
   toolchain move, but now documented. **Investigate + decide:** fix candidate — prepend the consumer
   venv bin (`${config.devenv.state}/venv/bin`) to PATH in the meta-module's `enterShell` (tasks DO
   receive enterShell exports — proven in PROGRESS.md §0.2), which is harmless for the shell (already
   prepended there) and fixes tasks; OR document the quirk in `docs/SKILLS.md`/the devenv skills and
   leave code alone. If you implement the fix, add a `test_modules_nix.py` guard and validate with
   `devenv tasks run repoman:test` in a consumer whose arch test shells to a venv script.
3. **Release tag** — bump `pyproject.toml` version `0.3.0` → `0.4.0` (the meta-module contract
   changed: `repoman.managers` no longer gates install, task execs resolve through the toolchain
   bin, doctor keys changed). Tag it. Note for consumers: `devenv update repoman` + the eval-cache
   refresh (§4 watch-outs) is the pickup path.
4. **The one-time `uv lock --upgrade-package testee` anomaly** (PROGRESS.md §deviations 9) — no code;
   if it recurs during WS-2, record the reproduction and file against uv. `repoman doctor`'s
   `installed:test` is the safety net.

## 7. Constraints — the ones that will actually bite

1. **Never break a working consumer.** Every consumer is in use with in-flight work. The dry-run-
   before-real-sync discipline (§4.5) is mandatory; if a dry-run shows anything outside the toolchain
   closure, stop and report.
2. **jj awareness.** On jj repos, git-level mutations to tracked files get reverted. Verify each
   consumer's VCS before deleting `repoman.lock` or editing `devenv.*`; prefer jj operations there.
3. **testee's per-repo visibility is a requirement**, not a suggestion — the templates and every
   migrated consumer declare it in `pyproject.toml`; nothing hides it.
4. **`repoman-sync` stays add-only** and consumer mode installs nothing — do not reintroduce installs
   into consumer mode while adding the WS-3 flag.
5. **The end-state is decided** (project 12 CONCEPT §1/§7). WS-1/WS-2 execute it; do not re-open
   options A–D.
6. Sibling repos are **separate PRs** — do not mix copyroom/template-py changes into the repoman PR
   or a consumer's PR.
7. Run all in-repo commands via `devenv shell -- <cmd>`; keep tests hermetic (no real venv, no
   network) in the repoman repo.

## 8. Deliverable

1. **Two sibling PRs** (copyroom, template-py) with their test updates, plus the row-6 copyroom-born
   repo validation result.
2. **A migration log** — one entry per migrated consumer: VCS, files touched, the dry-run uninstall
   count vs the real sync, doctor rows, acceptance line. Consumers left unmigrated (if any) with the
   reason.
3. **WS-3 decision note** (fleet lock shape) + the flag if approved.
4. **WS-4 changes** in the repoman repo (comment fix, task-PATH decision + fix or doc, version bump +
   tag), committed separately.
5. **`PROGRESS.md`** (in `.scratch/projects/12-toolchain-single-instance/`) updated with a new
   section: re-baseline results, the migration log, the sibling-PR diffs as built, every deviation
   from this kickoff with rationale, and the remaining-follow-ups list.
6. A short **owner summary**: what landed, what each PR/commit is, and the one-line pickup path for
   any consumer not yet migrated.

Tick a progress log at the top of `PROGRESS.md` as you go. If any PROGRESS.md finding turns out
wrong once you are in the code, **stop and say so before working around it** — the migration
procedure hangs on those findings.
