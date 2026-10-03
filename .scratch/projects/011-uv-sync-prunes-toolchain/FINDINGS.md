# Findings — `uv sync` prunes the repoman manager toolchain out of the shared devenv venv

**Status:** investigation + plan only — no `src/`, `modules/`, or `tests/` edits made this pass.
**Reproduced:** 2026-08-03, consumer = `../image-gen-pipeline` (repoman-enabled Python devenv).

## Progress log

- [x] Read the four required in-repo docs (`CONCEPT.md`, `SPIKE.md`, `modules/devenv.nix`, `modules/scripts/repoman-sync.sh`)
- [x] Read `src/repoman/devman/assets/docs/languages-python.md` (the distributed skill asset) and its installed copies
- [x] Read the consumer (`../image-gen-pipeline`): `pyproject.toml`, `devenv.nix`, `devenv.yaml`, `repoman.lock`, `.gitignore`
- [x] **Reproduced the prune** in the consumer: `devenv shell -- uv sync --dry-run --all-extras` → "Would uninstall 33 packages" (exact list captured)
- [x] Confirmed `UV_PROJECT_ENVIRONMENT` = shared venv in the shell (generated `.devenv/shell-*.sh`), and `uv sync` targets `.devenv/state/venv`
- [x] Mapped the venv contents: toolchain closure vs app-dep graph (52 pkgs; 33 pruned / 19 app-dep remainder)
- [x] Tested `uv sync --inexact` (safe-ish: no prune, but still writes `uv.lock`)
- [x] Audited uv's whole sync surface: **no "protect these packages" primitive** (no keep-list, no `[tool.uv]` key, no env var — `--inexact` is the only escape)
- [x] Audited every `uv sync` site in repoman's shipped assets, own `devenv.nix`, test fixtures, and ecosystem docs
- [x] Checked the doctor (`checks.py`) for a pruned-toolchain detector — none dedicated; and `repoman` itself is in the prune set, so a venv-side doctor can't run post-prune
- [x] Wrote this findings doc

---

## 1. Confirmed model — the venv has two co-managers that don't know about each other

### 1.1 The shared venv and why `uv sync` aims at it

- The venv is `.devenv/state/venv`, created by devenv `languages.python.venv.enable` (consumer `devenv.nix`), Python 3.14.6.
- devenv's generated shell script exports `UV_PROJECT_ENVIRONMENT='<repo>/.devenv/state/venv'` (verified in the consumer's `.devenv/shell-*.sh` **and** in repoman's own `.devenv/shell-*.sh`). `uv sync` therefore resolves the **project environment** to the shared devenv venv (dry-run: `Would use project environment at: .devenv/state/venv`).
- The venv is **co-managed** by two mechanisms that never read each other's manifests:

| Mechanism | Manifest it reads | Install style | What it knows about the other? |
|---|---|---|---|
| **Toolchain** — `repoman-sync` (devenv `scripts.*` → `modules/scripts/repoman-sync.sh`) | `repoman.lock` (`[repoman]` + `[managers.*]` + pseudo-entries like `git-pyjutsu`) | `uv pip install "${targets[@]}"` — **add-only**, pip-style | Nothing about `pyproject.toml`/`uv.lock` |
| **App deps** — the consumer's project | `pyproject.toml` `[project.dependencies]` + `[project.optional-dependencies] migrate` | `uv sync` (prunes to the uv lockfile graph) or `uv pip install -e .` (add-only) | Nothing about `repoman.lock` |

- `uv sync`'s contract is "make the target environment match the lockfile exactly" → it removes every package not in the uv dependency graph → **the whole repoman toolchain**, which lives in `repoman.lock` (a file `uv sync` never reads).
- The consumer currently has **no `uv.lock`**; `uv sync` would create one (`Would create lockfile at: uv.lock`) — a second, competing source of truth for an environment the repoman ecosystem deliberately manages pip-style. `.gitignore` does not exclude `uv.lock` (it is a commit-worthy artifact for uv projects).

### 1.2 The exact pruning set (reproduced, `devenv shell -- uv sync --dry-run --all-extras`)

```
Would use project environment at: .devenv/state/venv
Would create lockfile at: uv.lock
Resolved 21 packages in 466ms
Would uninstall 33 packages
 - annotated-doc==0.0.5        - markdown-it-py==4.2.0     - pytest==9.1.1
 - colorama==0.4.6             - mdurl==0.1.2              - pytest-json-report==1.5.0
 - copier==9.17.0              - packaging==26.2           - pytest-metadata==3.1.1
 - copyroom==0.5.0 (editable)  - pathspec==1.1.1           - questionary==2.1.1
 - dunamai==1.26.2             - platformdirs==4.11.0      - repoman==0.3.0 (editable)
 - funcy==2.0                  - pluggy==1.6.0             - rich==15.0.0
 - gitman==0.4.2 (editable)    - plumbum==2.0.2            - ruff==0.16.1
 - iniconfig==2.3.0            - prompt-toolkit==3.0.53    - shellingham==1.5.4
 - jinja2==3.1.6               - pygments==2.20.0          - testee==0.2.0 (editable)
 - jinja2-ansible-filters==1.3.2 - pyjutsu==0.15.0         - tomlkit==0.15.1
                                                          - ty==0.0.65
                                                          - typer==0.27.1
                                                          - wcwidth==0.8.2
```

- That's **every toolchain package that is not also an app dependency**: the five managers (copyroom, gitman, testee, repoman itself, + the git-pyjutsu wheel) **and their entire transitive closure** (pytest/ruff/ty/typer/jinja2/copier/…). Note `--all-extras` does **not** help — extras only add app groups, they don't protect anything.
- The 19 packages that survive are exactly the app-dep graph: the project itself, pydantic stack, dbos stack (psycopg, sqlalchemy, greenlet, click, websockets, python-dateutil/pyyaml/six), and the `migrate` extra (alembic, mako, markupsafe). pydantic survives only because it's *also* an app dep — the toolchain loses its own copy of shared packages' consumers.

### 1.3 Critical consequences discovered

1. **`repoman` itself is in the prune set** (`repoman==0.3.0`). After a real `uv sync`, `repoman` is not on PATH — so **`repoman doctor` cannot run to detect or explain the prune**. Any doctor-side safety net must live **nix-side** (a devenv script/enterShell hook), not in the Python conductor.
2. **`repoman-sync` survives** — it is a devenv `scripts.*` entry (bash, executed via `pkgs.bash` from the nix store), not a venv package, and `uv` itself is a devenv package. `repoman-sync` re-installs the toolchain first and then runs `repoman install-skills`, so the heal path is exactly "re-run `repoman-sync`" — no other recovery exists or is documented.
3. **The doctor's current `installed:<key>` checks (`shutil.which`) only partially cover this** and only from inside the shell, and only if `repoman` is still alive. There is no dedicated pruned-toolchain detection anywhere.

---

## 2. `uv sync` guidance audit — the blast radius

Every site in repoman's shipped/owned surface that tells a user to run `uv sync`, with a safety verdict. All grep runs done from the repoman repo root (and the consumer).

### 2.1 Unsafe — recommends plain sync / `--all-extras` in a repoman-managed repo

| # | File | Line | Content | Verdict |
|---|---|---|---|---|
| 1 | `src/repoman/devman/assets/docs/languages-python.md` | 17 | `devenv shell -- uv sync --all-extras   # install deps into the venv` | **UNSAFE** — the distributed skill (installed into every consumer's `.agents/devenv/`) that pulls the trigger |
| 2 | `src/repoman/devman/assets/skills/devenv-python-venv/SKILL.md` | 16 | `devenv shell -- uv sync --all-extras   # generic` | **UNSAFE** — same command, different asset; also this skill's `auto_trigger` keywords include `"uv sync"`, so it fires *on* the dangerous term and then recommends it |
| 3 | `src/repoman/devman/assets/skills/devenv-troubleshoot/SKILL.md` | 13 | fix column: `uv sync` / `repoman-sync` → `devenv-python-venv` | **UNSAFE** — bare `uv sync` |
| 4 | `src/repoman/devman/assets/articles/command-not-found-in-shell.md` | 25 | `devenv shell -- uv sync --all-extras` or `repoman-sync` | **UNSAFE** |
| 5 | `tests/consumer-example/.agents/devenv/languages-python.md` | 17 | fixture copy of #1 | **UNSAFE** — regenerated artifact (`repoman install-skills`), fixed by fixing the source asset + regenerating |
| 6 | `tests/consumer-example/.claude/skills/devenv-python-venv/SKILL.md` | 16 | fixture copy of #2 | **UNSAFE** — same |
| 7 | `tests/consumer-example/.claude/skills/devenv-troubleshoot/SKILL.md` | 13 | fixture copy of #3 | **UNSAFE** — same |
| 8 | `tests/consumer-example/.agents/devenv/articles/command-not-found-in-shell.md` | 25 | fixture copy of #4 | **UNSAFE** — same |

### 2.2 Safe — repoman-aware or add-only installs (keep as-is)

| # | File | Line | Content | Verdict |
|---|---|---|---|---|
| 9 | `src/repoman/devman/assets/docs/languages-python.md` | 18 | `devenv shell -- uv pip install -e .   # editable install of the project itself` | **SAFE** (add-only, no prune, no lockfile) — but it does **not** install extras (the consumer's `migrate` → alembic would be missed; see §3.1 for the corrected command) |
| 10 | `src/repoman/devman/assets/skills/devenv-python-venv/SKILL.md` | 17 | `devenv shell -- repoman-sync` (repoman-wired repos) | **SAFE** — the intended toolchain installer |
| 11 | `src/repoman/devman/assets/articles/adopting-the-man-family.md` | 26–27 | `devenv shell -- repoman-sync` | **SAFE** |
| 12 | `src/repoman/devman/assets/articles/authoring-a-manager-module.md` | 29–30 | describes `repoman-sync`'s `uv pip install` | **SAFE** (describes the mechanism, doesn't advise consumers to run sync) |
| 13 | `src/repoman/devman/assets/articles/ci-inside-devenv.md` | 11 | CI: `devenv shell -- repoman-sync` | **SAFE** |
| 14 | `devenv.nix` (repoman's **own** repo) | 59 | enterShell: `1. Install dependencies: uv sync --all-extras` | **SAFE in-repo but a bad model.** repoman's own repo has `venv.enable` + `uv.enable` and **no** `repoman.enable`/`repoman.lock` — its venv is purely uv-managed, so `uv sync` is correct there. It stays safe only because repoman doesn't dogfood its own meta-module. It is the pattern consumers copy; qualify it or point it at the safe command so the two cases don't blur. |

### 2.3 Ecosystem-adjacent (not shipped by repoman; awareness only)

| # | File | Line | Content | Verdict |
|---|---|---|---|---|
| 15 | `../copyroom/docs/user/getting-started.md` | 25 | `uv sync   # install dependencies` (copyroom's own dev repo) | Not repoman guidance; copyroom's own repo is not repoman-managed. Note only — no action in this pass. |
| 16 | `.scratch/projects/02-devman-module/CONTENT_INVENTORY.md`, `CONCEPT.md` | | `uv sync` mentions | Historical planning docs, not shipped. No action. |
| 17 | `../KICKOFF_PROMPT-template-py-fixes.md` | | template-fix planning (sibling dir) | Not shipped. Awareness: the copyroom `template-py` genome and consumer plans mirror "`uv pip install -e .` (or `uv sync`)" — the parenthetical is the footgun that #1–#4 make look sanctioned. |
| 18 | consumer repo docs/plans (`../image-gen-pipeline`) | | current README/PLAN have no `uv sync` | Nothing to strike in the consumer itself this pass; the fix is in the shipped assets + a safety net. |

**Blast radius summary:** 4 source assets (#1–#4) × their regenerated fixtures (#5–#8) in every repoman-managed consumer, plus repoman's own `devenv.nix` as the modeled pattern. That is the complete set — no other shipped doc/skill/article/template (`docs/SKILLS.md`, `src/repoman/templates/entrypoint.SKILL.md.j2`, `src/repoman/*.py`) recommends `uv sync`.

---

## 3. Option evaluation against the constraints

Constraints restated: (a) never break the toolchain under any documented command; (b) keep the two-source-of-truth split (app deps never in `repoman.lock`, toolchain never in `pyproject.toml`/`uv.lock`); (c) `devenv shell -- <cmd>` stays the front door, everything through the devenv-managed uv; (d) `repoman-sync` stays the toolchain installer (add-only semantics are load-bearing).

### A. Docs-only — strike/qualify every `uv sync`

- **Change surface:** #1–#4 source assets, repoman's own `devenv.nix:59` wording, regenerate `tests/consumer-example` fixtures (#5–#8). No module logic changes.
- **The corrected safe command** (verified): `devenv shell -- uv pip install --all-extras -e .` — `uv pip install` supports `--all-extras` (confirmed on uv 0.11.28), is add-only, never prunes, never writes `uv.lock`, and installs extras (so `migrate` → alembic lands). This is strictly better than today's line 18 (which misses extras) and fully safe.
- **When a lockfile is genuinely wanted:** `uv lock` writes `uv.lock` without touching the environment (no pruning); `uv sync --inexact` is the "sync but don't prune" escape (verified: `Would make no changes` — **but it still writes `uv.lock`**). Document both with the one-line caveat.
- **Residual footguns:** anyone who runs plain `uv sync` (muscle memory, other tooling, or a future doc that regresses) still prunes 33 packages with no warning; nothing protects them. This is the whole argument for adding D.
- **Migration cost:** trivial (text edits + fixture regen). Cheapest option.

### B. Make the toolchain uv-sync-compatible

- **Investigated as required:** does uv support "protect these packages" semantics at all? **No.** Full `uv sync --help` audit + `uv help settings`: there is no keep-list, no pruning-exclusion config, no `[tool.uv]` key, no env var. `--inexact` (CLI-only) is the *only* mechanism to prevent pruning; `--no-install-package` is the opposite (excludes from *installation*).
- The only real route would be folding the toolchain into the uv graph: a dependency group in `pyproject.toml` + `[tool.uv.sources]` mirroring `repoman.lock` (`path:`, `wheel:`, `git+…@ref`), so `uv sync`'s graph includes the managers.
- **Costs / violations:**
  - Directly breaks constraint (b): the toolchain moves into `pyproject.toml`/`uv.lock`, and `uv.lock` becomes the toolchain lockfile — every toolchain bump becomes an app-PR + lockfile diff in every consumer, and fleet upgrades stop being "re-run `repoman-sync`".
  - `repoman-sync` (or the consumer) must maintain duplicative entries in two manifests → drift risk, merge conflicts in the consumer's `pyproject.toml`, and it makes the toolchain visible in a file that is the app's own.
  - `wheel:` sources still need `UV_FIND_LINKS` at *resolve* time — now baked into every consumer's lockfile flow instead of just `repoman-sync`.
  - Even then, there is no "add-only" guarantee: uv would *own* the toolchain and could re-resolve it differently than `repoman.lock` pins.
- **Verdict:** reject as the primary fix. **B-lite** (worth keeping in the back pocket): a devenv `scripts.uv` shim in the meta-module that injects `--inexact` into `uv sync` for repoman-enabled repos (protect-by-default, aligns with "run everything through the devenv-managed uv"). Cost: shadows the uv binary in the shell; behavior change is global to the shell and slightly magical. Optional hardening only.

### C. Separate venvs (toolchain venv vs app venv)

- **Change surface:** `repoman-sync` install target, every manager CLI invocation, PATH assembly, `devenv shell` front-door behavior, and — decisively — **testee**. testee's entire job is running pytest/ruff/ty *against the project*, which lives in the app venv; moving testee to a separate venv breaks its core loop or forces interpreter/venv redirection on every invocation. gitman/copyroom are standalone CLIs (would survive), but the family contract is `repoman doctor`/`repoman status` aggregating all managers, and CONCEPT §6 states the design: "manager CLIs must land in the devenv venv."
- **Verdict:** highest cost, violates the "one venv, `devenv shell` is the front door" design, and breaks testee's model. **Reject.**

### D. Doctor-side safety net

- **Key constraint discovered (§1.3):** `repoman` itself is in the prune set, so a Python-side doctor **cannot** detect the prune (it's dead). The net must be nix-side.
- **Viable shape (recommended):** an `enterShell` hook in `modules/devenv.nix` (inside `config = lib.mkIf cfg.enable`, so only repoman-enabled repos get it) that cheaply checks the venv for the toolchain (`test -x .devenv/state/venv/bin/gitman` etc. or the `repoman` console script) and, if missing, prints a one-line warning: `⚠ toolchain pruned from the devenv venv — run: devenv shell -- repoman-sync`. Cost: one shell block; runs on every shell entry (µs-scale `test -x` checks).
- **Timing nuance:** a one-shot `devenv shell -- uv sync --all-extras` prunes at the *end* of that command (its own enterShell hook already ran), so the warning fires on the **next** shell entry — i.e., exactly when the user sits down to work and would first notice `gitman: command not found`. That is the right moment.
- **Optional strengthening:** add an import-based check to `repoman doctor`'s self-check (`checks.py` — today `installed:<key>` is `shutil.which`-only) so a *partial* prune (or a venv whose bin entries survived while packages didn't) is caught while the conductor is still alive; and/or have the enterShell hook suggest the exact command.
- **Migration cost:** one block in `modules/devenv.nix` (+ optional `checks.py` check). Combines cleanly with A.

---

## 4. Recommendation

**Sign off: A + D** — strike/qualify every `uv sync` recommendation in the shipped assets (A), and add a nix-side safety net that detects and points at the heal for anyone who runs `uv sync` anyway (D). Optional B-lite (`scripts.uv` → `--inexact`) only if the owner wants protect-by-default hardening on top.

Rationale: A is the only option that fully satisfies constraint (a) for *documented* commands, costs ~nothing, and keeps both sources of truth (constraint b). D is required because A alone leaves a silent footgun (the kickoff's own framing) and because the conductor is itself pruned — the net must be nix-side. B fails constraint (b) and has no uv primitive behind it; C breaks testee and the one-venv design.

### Migration order

1. **Docs (A) — now.**
   - `src/repoman/devman/assets/docs/languages-python.md:17` → replace the `uv sync --all-extras` line with `devenv shell -- uv pip install --all-extras -e .` as the sole documented install mechanism; add a one-line "never plain `uv sync` in a repoman repo (it prunes the manager toolchain); if you need a uv lockfile use `uv lock` or `uv sync --inexact` (still writes `uv.lock`)" note in the "venv gotcha" section.
   - `src/repoman/devman/assets/skills/devenv-python-venv/SKILL.md:16` → same replacement; promote the `repoman-sync` line (17) to the primary fix; keep `"uv sync"` in the trigger keywords but make the body warn.
   - `src/repoman/devman/assets/skills/devenv-troubleshoot/SKILL.md:13` → `uv sync` / `repoman-sync` → `uv pip install --all-extras -e .` / `repoman-sync`.
   - `src/repoman/devman/assets/articles/command-not-found-in-shell.md:25` → same.
   - `devenv.nix:59` (repoman's own) → qualify with a one-line comment that this is safe only because repoman's own venv is uv-only; or point at `uv pip install --all-extras -e .` so the modeled pattern is the safe one.
   - Regenerate the `tests/consumer-example/.agents/…` and `.claude/skills/…` fixtures (#5–#8) by re-running `repoman install-skills` (or update the checked-in copies in the same change — `tests/` is off-limits this pass, flag for the implementer).
2. **Safety net (D) — same change or next.**
   - `modules/devenv.nix`: add the enterShell toolchain-presence check (inside `cfg.enable`).
   - Optional: extend `checks.py` `installed:<key>` with an import/venv-bin check for partial prunes.
3. **Optional hardening (B-lite).** `scripts.uv` shim injecting `--inexact` for `uv sync` — only if the owner wants the default to be safe even for docs-ignorers. Ship as a separate, easily revertible change.
4. **Validate** in `../image-gen-pipeline` per §5.

### Exact files that change (implementation phase)

| File | Change |
|---|---|
| `src/repoman/devman/assets/docs/languages-python.md` | strike `uv sync --all-extras` (L17); safe command + caveat |
| `src/repoman/devman/assets/skills/devenv-python-venv/SKILL.md` | same (L16); repoman-sync becomes primary |
| `src/repoman/devman/assets/skills/devenv-troubleshoot/SKILL.md` | fix column (L13) |
| `src/repoman/devman/assets/articles/command-not-found-in-shell.md` | L25 |
| `modules/devenv.nix` | enterShell toolchain-presence check (D) |
| `devenv.nix` | qualify own-repo `uv sync` wording (optional) |
| `src/repoman/checks.py` | import/venv-bin based `installed:` check (optional D+) |
| `tests/consumer-example/` fixtures | regenerate (5 files) |
| `modules/scripts/repoman-sync.sh` | untouched — stays the add-only toolchain installer |

---

## 5. Validation checklist (implementer runs in `../image-gen-pipeline`)

All commands via `devenv shell -- <cmd>`; the consumer's `devenv.nix` = `repoman.enable = true`, managers `[copy git test]`, `languages.python` on, vendomat `wheel:pyjutsu`.

1. **Clean-venv toolchain install (baseline, unchanged):**
   - `rm -rf .devenv/state/venv` (or fresh clone), then `devenv shell -- repoman-sync`.
   - Assert: `gitman status` works and `testee verify --mode quick` works; `repoman doctor` self-check all-OK.

2. **Documented install path (post-fix):**
   - `devenv shell -- uv pip install --all-extras -e .`
   - Assert: app deps land (**alembic** present — the `migrate` extra must come through `--all-extras`), AND the toolchain survives: `gitman status` + `testee verify --mode quick` still work; `uv pip list` still shows `repoman`, `gitman`, `testee`, `copyroom`, `pyjutsu`, `pytest`, `ruff`, `ty`.
   - Assert: **no `uv.lock` was created** by the pip-style install (`git status` clean of `uv.lock`).

3. **The footgun is now caught, not silent (D):**
   - Run the dangerous command deliberately: `devenv shell -- uv sync --all-extras` (real, destructive).
   - Assert: pruning still happens (33 removed — this is by design until B-lite), then **exit and re-enter the shell** → the new enterShell warning prints the heal one-liner.
   - Run `devenv shell -- repoman-sync` → toolchain restored; `gitman status` + `testee verify --mode quick` work again.

4. **Partial-prune detection (if D+ implemented):**
   - `devenv shell -- uv pip uninstall ty` (simulate partial prune while `repoman` is alive) → `repoman doctor` reports the new check; `repoman-sync` heals.

5. **Lockfile escape hatch:**
   - `devenv shell -- uv lock` → `uv.lock` appears, venv untouched (no uninstalls in output; toolchain still importable).
   - `devenv shell -- uv sync --inexact --dry-run` → `Would make no changes` (no prune) — matches the doc's caveat that `--inexact` still writes `uv.lock`.

6. **Docs are the only trigger (regression sweep):**
   - `rg -n "uv sync" src/ modules/ devenv.nix tests/consumer-example/` → only occurrences left are the *qualified* mentions (with `--inexact`/`uv lock` caveat) and repoman's own-repo comment; no bare `uv sync --all-extras` in any shipped asset.

---

## 6. Addendum (owner question) — single shared toolchain instance, "pulled in" by every repo

Asked after §5: instead of `repoman-sync` copying the toolchain into *each* consumer venv, install it
**once** (repoman owns it) and have every consumer just use that one instance. Verdict: **feasible and
architecturally the strongest fix for the original footgun** — it deletes the two-co-managers problem
by construction (each venv gets exactly one owner). The manager family splits cleanly:

| Class | Members | Consumer-code coupling? | Shareable as one instance? |
|---|---|---|---|
| Pure CLIs | `repoman`, `gitman`, `copyroom`, `docman` (+ lib deps: copier, questionary, typer, jinja2, pyjutsu wheel) | **None** — verified: no `sys.path`/app-import anywhere in their `src/` | **Yes, trivially** — zero code changes |
| Tools-under-test driver | `testee` (the *driver* is a pure CLI too) | Its tools (pytest/ty) run *inside* the consumer codebase and must import the consumer venv | Driver yes; **pytest/ty must stay app-side** (declared dev-deps) |

**The one hard coupling is testee's tools, and testee already has the seam for it.** `TesteeConfig.python`
("Interpreter whose venv bin holds ruff/ty/pytest — override only for non-default venv layouts",
`config.py:91`) is plumbed end-to-end: `core.py:166/264`, `doctor.py:44`, `workflows.py`, and the
adapters' `tool_executable()` resolve each tool next to that interpreter with a **PATH fallback**
(`adapters.py`). So a shared toolchain venv works today if:
1. the consumer declares the tools-under-test as app-graph dev-deps (`[dependency-groups] dev` or an
   extra: `pytest`, `ruff`, `ty`/`pyright`) — `uv sync` then *keeps* them, and
2. testee's interpreter points at the consumer venv (set `python = ".devenv/state/venv/bin/python"` in
   `[tool.testee]` per repo, or — cleaner — have the meta-module inject it / have testee default to
   `$UV_PROJECT_ENVIRONMENT/bin/python`, which devenv already exports). ruff may stay shared (pure
   parser; the PATH fallback finds it), but pytest/ty must be app-side.

**Mechanics (ranked):**
- **Stateful shared venv** at a fixed path (e.g. `~/.local/share/repoman/venv`): the meta-module
  prepends its `bin/` to `env.PATH` in every consumer; `repoman-sync` becomes a machine-level bootstrap
  (`repoman-sync --machine`) that creates/syncs it. The shared venv can be a **fully uv-managed
  project with its own lockfile** — the add-only/pruning dance disappears at the source, and the
  consumer no longer needs `vendor.enable` (pyjutsu is resolved once, machine-side). Cost: **one
  toolchain version machine-wide** (aligned with repoman's "fleet moves in lockstep" convergence
  model, but repos can no longer pin different manager versions).
- **uv tool install** (`uv tool install copyroom gitman testee repoman`): same single-version
  property, least wiring, runs outside devenv (still invoked via `devenv shell -- <cmd>`).
- **Nix flake packaging** of each manager (per-version store paths, deduped across repos, per-repo
  version pins preserved via flake.lock): the heavyweight option; contradicts SPIKE's "heavy lifting
  is a venv sync, not nix inputs" decision, and does not itself solve the testee/tools coupling.

**Consequences worth stating:** with test tools app-side, the consumer venv contains only
app-graph packages, so **plain `uv sync --all-extras` becomes safe and `uv.lock` becomes the correct
single source of truth** — the entire A+D doc-surgery in §2–§4 is moot in the long run. Consumer
`devenv.nix` simplifies (no vendomat import). Migration order: (1) testee interpreter auto-detection
(tiny), (2) `repoman-sync --machine` + meta-module PATH prepend, (3) consumer dev-deps + `[tool.testee]`
config, (4) docs. A+D remains the cheap immediate fix; this is the end-state worth signing off later.

---

## 7. Addendum 2 — the owner's hybrid end-state: system-wide toolchain + per-repo testee (DECISION)

Owner decision after §6: **don't share testee.** The pure-CLI managers install **once system-wide** in a
repoman-owned shared venv; **testee alone is declared as a per-repo dev dependency** in each consumer's
`pyproject.toml` (uv-managed, deliberately visible — the owner wants the fact that testee is used to be
an explicit project declaration, not a hidden venv install). This maps 1:1 onto the two-class split in
§6 and is the cleanest coherent end-state:

| Component | Lives in | Installed by | Managed/pinned by |
|---|---|---|---|
| `repoman`, `gitman`, `copyroom`, `docman` + libs (copier, questionary, typer, jinja2, **pyjutsu** wheel) | system-wide shared venv (e.g. `$XDG_DATA_HOME/repoman/venv`) | `repoman-sync --machine` (repoman-repo command, add-only) | machine-level `repoman.lock` (repoman checkout), copyroom convergence → lockstep |
| **testee** + its tools (pytest, pytest-json-report, ruff, ty, import-linter — all real `dependencies` of testee, verified `testee/pyproject.toml`) | consumer venv (`.devenv/state/venv`) | `uv sync` (dev-group dep + `[tool.uv.sources] testee` fleet ref) | per-repo `uv.lock` |
| app deps | consumer venv | `uv sync` | per-repo `uv.lock` |
| skills / docs | repo files | `repoman install-skills` | per-repo |

**Why this is the cleanest shape (three load-bearing facts):**

1. **Zero testee code changes.** testee runs from the consumer venv, so `sys.executable` = consumer
   python, `tool_executable()` finds pytest/ruff/ty as siblings, and tests import the app from the same
   venv — *exactly* today's behavior. The §6 model's one rough edge (interpreter indirection) vanishes.
2. **The footgun dies by construction.** The consumer venv holds only the uv graph (app deps + testee +
   its transitive tools) → `uv sync` prunes nothing and `uv.lock` becomes the correct single source of
   truth. The shared venv is repoman-owned and only ever touched by `repoman-sync --machine`. No venv
   has two co-managers anymore — the §1 model is eliminated, not patched.
3. **No racing installers.** testee appears in exactly one manifest (pyproject/uv.lock); the shared
   managers appear in exactly one (machine `repoman.lock`). No overlap, no drift.

**Change surface (implementation pass):**
- `modules/scripts/repoman-sync.sh` — `--machine` mode: create/sync the shared venv from the machine
  `repoman.lock` (still add-only `uv pip install`; needs `UV_FIND_LINKS`/vendomat context at bootstrap
  for the pyjutsu wheel); consumer mode shrinks to "ensure shared venv exists + `repoman install-skills`".
- `modules/devenv.nix` — prepend shared-venv `bin/` to `env.PATH`; export `REPOMAN_TOOLCHAIN_VENV`.
- `modules/managers/{gitman,copyroom,docman}.nix` — task execs change `${venvBin}/<manager>` (consumer
  venv abs path) → bare `<manager>` (PATH-resolved to the shared venv). **testee.nix stays as-is**
  (`${venvBin}/testee` remains correct — testee is in the consumer venv).
- `src/repoman/checks.py` — `lock:*` self-checks must treat uv-declared managers (testee) as
  project-managed: check `pyproject.toml` for testee, not `repoman.lock` (else `lock:test` FAILs
  "selected but absent"). `installed:test` (`which`) keeps working via PATH.
- Template (`template-py` `pyproject.toml.jinja` + copyroom in-repo fixture) — render
  `[dependency-groups] dev = ["testee"]` (uv's default-on group; **note: `uv pip install -e .` installs
  neither dev groups nor extras**, so the documented install command must be `uv sync` — which is now
  safe again) + `[tool.uv.sources] testee = { git = …, ref = … }` (dev: path override).
- Consumer `repoman.lock` → no longer needed (toolchain is machine-level; `[managers.test]` removed);
  docs/skills (`languages-python.md`, `devenv-python-venv`, `command-not-found-in-shell.md`) revert the
  §2 doc-surgery — `uv sync --all-extras` becomes the correct recommendation again.

**Caveats (accepted trade-offs):** pyjutsu wheel source is needed once at machine bootstrap (vendomat
or a from-source build at the repoman checkout); two upgrade clocks (testee per-repo vs the rest
machine-wide lockstep); a consumer cannot pin a different gitman/copyroom version than the machine;
consumer `repoman-sync` semantics change (it no longer installs the toolchain into the consumer venv).
Migration order: (1) `--machine` + shared venv + PATH prepend, (2) manager nix-task PATH fixes,
(3) `checks.py` uv-managed awareness, (4) template renders testee dev-dep + source, (5) consumers add
testee dev-dep + `uv sync`, (6) docs revert. Validation = §5 checklist with one change: step 3's
"deliberate `uv sync`" should now show **zero uninstalls** (not a 33-package prune + warn).
