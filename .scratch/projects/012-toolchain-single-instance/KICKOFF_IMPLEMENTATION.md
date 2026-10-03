# Kickoff prompt — IMPLEMENT the shared-toolchain + per-repo-testee refactor

Companion to `KICKOFF_PROMPT.md` (which commissioned the plan). That session was planning-only; **this
one implements.** Paste the block below into a **fresh session in the `repoman` repo**.

**Before pasting:** commit or stash the working tree. `git status` currently carries in-flight roster
deletions (`modules/managers/{alliman,mypi,zelligate}.nix`), a `registry.py` edit, and test edits —
start this refactor from a clean tree so its diff is legible.

**One caveat to carry in:** the planning session delivered `IMPLEMENTATION_GUIDE.md` from a full
read-only audit of the code, but it did **not** run the §3.0 scratch experiments that kickoff asked for
(the `/tmp` `uv sync` dev-group proof, the `.devenv/shell-*.sh` PATH-precedent inspection, the
`ls <venv>/bin` collision diff). Those claims are inherited from CONCEPT/FINDINGS, not re-measured.
Step 0 below closes that gap first — it is cheap and it de-risks everything after it.

---

You are implementing **project 12 — toolchain single instance** in **repoman**
(`/home/andrew/Documents/Projects/repoman`), the devenv meta-module that composes the `*man` manager
family. This is a real refactor across nix modules, Python, tests, shipped docs, and fixtures. Edit
`src/`, `modules/`, `tests/`, docs, and fixtures freely; the plan is already signed off.

## 1. The change in one paragraph

The manager family splits along the only seam that matters — *does the tool import the consumer's
code?* **Pure-CLI managers** (`repoman`, `gitman`, `copyroom`, `docman` + libs, incl. the `pyjutsu`
wheel) are installed **once, system-wide** in a repoman-owned venv at `$XDG_DATA_HOME/repoman/venv`
(`REPOMAN_TOOLCHAIN_VENV`), populated by `repoman-sync --machine` from a **machine `repoman.lock` at
the repoman checkout root**. **testee** — whose tools (pytest/ruff/ty/import-linter) execute inside the
consumer's codebase — becomes a **per-repo uv dev dependency** declared in each consumer's
`pyproject.toml`. Consequence, by construction rather than by documentation: the consumer venv holds
only the uv graph, so `uv sync` prunes nothing and project 11's footgun is dead — not patched.

## 2. Read these first, in this order

1. **`.scratch/projects/12-toolchain-single-instance/IMPLEMENTATION_GUIDE.md`** — **the authoritative,
   step-by-step guide. Follow it.** It carries the decisions (§0), the work breakdown and PR slicing
   (§1), steps 1–12 with concrete diffs and full code (the rewritten `repoman-sync.sh`, the nix option
   and task-exec forms, drop-in `checks.py` functions, the registry diff), a ~30-test plan, the fixture
   rewrite, the validation checklist (§12c), and the known sharp edges (§13).
2. `.scratch/projects/12-toolchain-single-instance/CONCEPT.md` — the owner-approved blueprint the guide
   implements. Where the two differ, **the guide wins**: §0 records exactly which CONCEPT points were
   superseded and why (notably §5.1's "warn", §5.2's bare-name task execs, and §11's five open
   questions, plus two questions CONCEPT didn't ask).
3. `.scratch/projects/11-uv-sync-prunes-toolchain/FINDINGS.md` §1 (the 33-package prune set) and §6–§7
   (why this hybrid is the owner's decision). Background only — do not re-open options A–D.
4. The code you will change: `modules/devenv.nix`, `modules/scripts/repoman-sync.sh`,
   `modules/managers/{gitman,copyroom,docman}.nix`, `src/repoman/{registry,checks}.py`,
   `tests/{test_repoman_sync,test_checks,test_cli,test_registry}.py`, `tests/consumer-example/`,
   `src/repoman/devman/assets/{docs,skills,articles}/**`.

## 3. Execution order

### Step 0 — close the unverified-mechanics gap (30 min, read-only + `/tmp` only)

Prove the three inherited claims before writing code. Record each result in `PROGRESS.md`; if one
fails, **stop and report** — it invalidates part of the plan rather than merely inconveniencing it.

- **testee-as-dev-group actually pulls the verify stack.** In `/tmp/repoman-12-scratch`, write a
  `pyproject.toml` with `[project]` name/version/`requires-python = ">=3.13"`,
  `[dependency-groups] dev = ["testee"]`, and
  `[tool.uv.sources] testee = { path = "/home/andrew/Documents/Projects/testee" }`. With
  `UV_PROJECT_ENVIRONMENT=/tmp/repoman-12-scratch/.venv`, run `uv sync` and confirm testee **plus**
  pytest / pytest-json-report / ruff / ty / import-linter all land, and that `uv.lock` is written. Then
  `uv pip install six` into that venv and re-run `uv sync` — six must be pruned while testee survives.
  That is the whole thesis in one experiment.
- **PATH precedent (decision D1).** Inspect a consumer's generated `.devenv/shell-*.sh` (or
  `devenv shell -- sh -c 'echo $PATH'`) and confirm the venv PATH prepend is a *runtime* export, not a
  nix-eval-time absolute path. Separately confirm the sharper half: **`devenv tasks run <task>` does not
  source `enterShell`** — this is exactly why the guide uses `"${cfg.toolchainBin}"/gitman` in task
  execs instead of CONCEPT §5.2's bare `gitman`.
- **No name collisions.** `ls .devenv/state/venv/bin` in a consumer vs. `repoman gitman copyroom docman`
  — the sets must be disjoint once migrated. Expect `pytest`/`ruff`/`ty` in the consumer venv (testee's
  deps); confirm none of them belong to the shared venv's install set.

### Steps 1–12 — the four PR slices (guide §1)

Commit at each boundary so a bisect lands on a green tree:

- **PR-A — steps 1–3.** Machine `repoman.lock` at the checkout root; the two-mode `repoman-sync.sh`;
  repoman's own `devenv.yaml`/`devenv.nix` gain the `vendomat` input, `vendor.enable`, and a
  `repoman-sync` script. Purely additive — nothing observes the shared venv yet. **End this slice by
  bootstrapping for real** (`devenv shell -- repoman-sync --machine`) and pasting the resulting
  `ls ~/.local/share/repoman/venv/bin` into `PROGRESS.md`; every later slice assumes it exists.
- **PR-B — steps 4–8.** Meta-module `toolchainBin` option + `enterShell` export/PATH prepend; the three
  manager task execs; `Manager.install`/`package`; the `checks.py` rewrite; the full test delta. This is
  the semantic switch and the only slice that can break a consumer.
- **PR-C — steps 9–11.** Shipped devman docs/skills revert to `uv sync --all-extras`; consumer-example
  fixtures regenerate. copyroom and `template-py` are **separate repos** — do not edit them from this
  session; write up the sibling-PR diffs in `PROGRESS.md` instead.
- **PR-D — step 12.** Dogfood in `../image-gen-pipeline`, then a copyroom-born repo; run the §12c
  validation table and record every row's real output.

## 4. Constraints — the ones that will actually bite

1. **`modules/managers/testee.nix` does not change.** `${venvBin}/testee` is still correct — testee
   lives in the consumer venv. A diff to that file is a bug.
2. **No `builtins.getEnv` in nix** (D1). The toolchain path is a *shell expression* expanded at runtime;
   task execs use `"${cfg.toolchainBin}"/<manager>`, never a bare PATH-resolved name (CONCEPT §5.2 says
   bare — it is wrong for tasks, which don't source `enterShell`). The new `tests/test_modules_nix.py`
   guards both halves.
3. **`uv pip install --python "$toolchain_venv/bin/python"`** in machine mode. The bootstrap runs from
   inside repoman's *own* devenv venv; without the explicit flag, uv installs the toolchain into the
   wrong venv. Load-bearing — keep the test that asserts it.
4. **Reuse the resolver verbatim.** The embedded TOML resolver, `SOURCE_HANDLERS`, the
   `path:`→`--editable` rule, and the `wheel:`/`UV_FIND_LINKS` guard are proven by existing tests. The
   only resolver change is the `REPOMAN_SYNC_ALL` select-all switch for machine mode.
5. **Consumer mode installs nothing.** No `uv` invocation, no reading of `repoman.lock`. Its entire job:
   verify the shared toolchain, warn about an orphan per-repo lock, run `repoman install-skills`.
6. **Keep the doctor generic** (D5): `Manager.install ∈ {"toolchain","uv"}` selects the check. Do not
   special-case the string `"testee"` anywhere in `checks.py`.
7. **`repoman.managers` no longer gates installation** — only wiring/skills. Fix every comment and
   option description that still claims otherwise (meta-module header, the `managers` option, the devman
   articles).
8. Run all in-repo commands via `devenv shell -- <cmd>`. Keep tests hermetic — no real venv, no network;
   stub `uv` as an argv recorder.

## 5. Definition of done

- `devenv shell -- pytest -q` green, including the new machine-mode, uv-declared-manager, and
  `test_modules_nix.py` suites.
- `rg -n 'venvBin' modules/` → only `modules/managers/testee.nix`.
- `rg -n 'builtins.getEnv' modules/` → nothing.
- `repoman doctor` in a migrated consumer is all-OK, showing `toolchain:venv`, `toolchain:lock`,
  `lock:{copy,git,doc}`, **`uv:test`**, and **no `lock:test` row at all**.
- **The acceptance test:** a second `devenv shell -- uv sync --all-extras --dry-run` in
  `../image-gen-pipeline` reports **zero uninstalls** (project 11 measured 33).
- `devenv tasks run repoman:vc:status` works **without** entering the shell first (proves D1 — the one
  genuinely new risk this refactor introduces).
- No consumer retains a `repoman.lock`; no `[managers.test]` anywhere in the machine lock.

## 6. Deliverable

The implemented refactor, plus **`PROGRESS.md`** in `.scratch/projects/12-toolchain-single-instance/`
containing: the step-0 verification results; a per-step log (step → files touched → the command that
proved it); the filled-in §12c validation table with real output; every deviation from
`IMPLEMENTATION_GUIDE.md` with its rationale; and a "follow-ups / out of scope" list (expected: the
copyroom and `template-py` sibling PRs, and each remaining consumer's migration).

If one of the seven decisions in guide §0 turns out to be wrong once you are in the code, **stop and say
so before working around it** — the rest of the guide hangs on them.
