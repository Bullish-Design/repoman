# CONCEPT — Toolchain single instance: system-wide shared toolchain + per-repo testee

**Project:** 12-toolchain-single-instance
**Status:** concept / blueprint (no code changed yet)
**Predecessor:** `.scratch/projects/11-uv-sync-prunes-toolchain/FINDINGS.md` — the investigation that
mapped the `uv sync` footgun and the option space. This project implements the **owner-decided hybrid
end-state** (FINDINGS §7).

---

## 1. The decision in one paragraph

The `*man` manager family is split along the only seam that matters — *does the tool import the
consumer's code?* — and each half is given the install model it deserves:

- **Pure-CLI managers** (`repoman`, `gitman`, `copyroom`, `docman` + their libraries, including the
  `pyjutsu` native wheel) never touch a consumer's package. They are installed **once, system-wide**,
  in a repoman-owned shared venv, and every repoman-enabled repo just pulls them onto PATH. One
  instance, one upgrade clock, zero per-repo copies.
- **testee** is the single manager whose tools (pytest / ruff / ty / import-linter) execute *inside*
  the consumer codebase and must import the consumer venv. It is therefore declared **as a per-repo
  dev dependency** in each consumer's `pyproject.toml` — uv-managed, pinned in `uv.lock`, and
  deliberately visible ("don't hide the fact that testee is used").

Consequences, by construction rather than by documentation:

- `uv sync` in a consumer can only ever prune app-graph packages → **the uv-sync footgun is dead**.
- No venv has two co-managers anymore (the 11-project's root cause is eliminated, not patched).
- testee needs **zero code changes** — it lives in the same venv it lives in today.
- Every consumer's `devenv.nix`/`devenv.yaml` simplifies (vendomat import, `vendor.enable`, and the
  per-repo `repoman.lock` all go away).

---

## 2. Background — why this exists

`devenv shell -- uv sync --all-extras` (recommended by repoman's own distributed docs) uninstalled the
entire manager toolchain from the shared devenv venv: `repoman-sync` installs the toolchain add-only
pip-style from `repoman.lock`, while `uv sync` prunes the environment to match `uv.lock` — a file that
knows nothing about `repoman.lock`. Verified in `../image-gen-pipeline`: **52 packages in the venv, 33
pruned, 19 survivors** (the app-dep graph). `repoman` itself was in the prune set, so the conductor
couldn't even run its own doctor to explain.

The options were: A docs-only (cheap, leaves a silent footgun), B make the toolchain uv-sync-compatible
(no uv primitive exists for "protect these packages"; folding everything into the uv graph collapses
the two-source-of-truth split), C separate venvs per repo (breaks testee's project-import model), D a
doctor-side net (can't run — the conductor is pruned). The owner's hybrid is the synthesis: share what
can be shared, declare what must be per-repo. See FINDINGS §6–§7 for the full analysis.

---

## 3. The load-bearing insight — two classes of manager

| Class | Members | Imports consumer code? | Install model |
|---|---|---|---|
| **Pure CLI** | repoman, gitman, copyroom, docman (+ copier, questionary, typer, jinja2, **pyjutsu** wheel) | **Never** — verified: no `sys.path` / app-import anywhere in their `src/`; they shell out (gitman→jj/git, copyroom→copier) and read repo files | One system-wide venv, shared by every repo |
| **Tools-under-test driver** | testee (the driver CLI is pure; **its tools are not**) | Its tools (pytest/ty) run inside the consumer's test suite and import the consumer venv (tests do `import dbos`, `import <app>`) | Per-repo uv dev dependency, declared in `pyproject.toml` |

testee's `pyproject.toml` declares `pytest>=7.0`, `pytest-json-report>=1.5`, `ruff>=0.5.0`,
`ty>=0.0.44`, `import-linter>=2.0` as **real `dependencies`** — so declaring `testee` in a consumer's
dev group pulls the entire verify stack into the uv graph transitively. One declaration, all four
tools, pinned by `uv.lock`, immune to pruning.

---

## 4. Target architecture

### 4.1 The system-wide shared venv

- **Location:** `$XDG_DATA_HOME/repoman/venv` (default `~/.local/share/repoman/venv`), exported to
  the ecosystem as `REPOMAN_TOOLCHAIN_VENV`. A plain venv, not a devenv shell.
- **Python:** the floor that satisfies the pure-CLI managers — gitman requires `>=3.13`; the pyjutsu
  wheel is `cp313-abi3` (runs on 3.13+). **Machine choice: 3.13** (a higher version also works; the
  consumer's Python version is now *irrelevant* to the toolchain — a decoupling the current design
  doesn't have).
- **Manifest:** `repoman.lock` **moves to the repoman checkout root** (the machine-level toolchain
  pin): `[repoman]`, `[managers.copy]`, `[managers.git]`, `[managers.git-pyjutsu]`, `[managers.doc]`.
  **No `[managers.test]`** — testee is no longer toolchain-installed.
- **Installer:** `repoman-sync --machine` — creates/syncs the shared venv from that lock with the
  existing add-only `uv pip install` resolver (the script's resolution logic is unchanged; only the
  target venv and lock path differ). Re-running re-resolves the same pins (idempotent), and because
  it's add-only nothing outside the lock is ever touched.
- **pyjutsu at bootstrap:** the `wheel:pyjutsu` entry needs `UV_FIND_LINKS` (vendomat's wheelhouse)
  only at machine-bootstrap time. The bootstrap runs from a context that exports it — the repoman
  checkout's own devenv gains the `vendomat` input (like consumers have today), or pyjutsu is built
  from source once (maturin; `repoman.nativeBuild = true` stays as the no-wheelhouse escape hatch).
  After bootstrap, the wheel is in the shared venv; consumers never see it.
- **Who maintains it:** copyroom convergence — updating the machine `repoman.lock` + `repoman-sync
  --machine` is how the fleet moves the toolchain in lockstep.

### 4.2 testee as a per-repo uv dev dependency

Consumer `pyproject.toml`:

```toml
[dependency-groups]
dev = ["testee"]

[tool.uv.sources]
testee = { git = "https://github.com/Bullish-Design/testee", ref = "vX.Y.Z" }  # fleet
# dev override: testee = { path = "../testee" }
```

- `uv sync` installs testee + its four tools into the consumer venv and pins them in `uv.lock`.
- **Why zero testee changes:** testee's console script runs with the consumer venv's python, so
  `sys.executable` is the consumer python, `tool_executable()` (`adapters.py`) finds pytest/ruff/ty as
  siblings next to it, and pytest imports the app from the same venv — identical to today.
- **No `[tool.testee] python` override needed** (the `config.py:91` escape hatch is not exercised;
  it remains for non-default venv layouts).
- **Version pinning:** per-repo. A consumer can stay on testee X while another moves to Y — this is
  the *only* per-repo toolchain version knob, and it's the correct one (testee is the only manager
  coupled to the repo's code).

### 4.3 App deps

Unchanged ownership: `[project.dependencies]` + extras in the consumer `pyproject.toml`, installed by
`uv sync`, pinned in `uv.lock`. The consumer venv now contains *only* the uv graph — which is what
makes `uv sync` trivially safe.

### 4.4 Skills & docs

Stay per-repo (they are repo-local files): `repoman install-skills` writes `.claude/skills/` and the
devman docs export to `.agents/devenv/`, exactly as today.

### 4.5 The resulting environment (per consumer shell)

```
PATH (front door: devenv shell):
  <shared venv>/bin      → repoman, gitman, copyroom, docman  (one system-wide instance)
  .devenv/state/venv/bin → python, testee, pytest, ruff, ty, app CLIs  (uv graph)
```

Name collisions: none — the shared venv and the consumer venv share no executable names.

---

## 5. How the pieces wire (module/nix side)

### 5.1 `modules/devenv.nix` (the meta-module)

- `env.PATH` prepend of `${REPOMAN_TOOLCHAIN_VENV}/bin`. The literal path is computed at eval from
  `$XDG_DATA_HOME`/`$HOME` (via `builtins.getEnv`, single-user dev machines) with a documented
  fallback; the same value is exported as `REPOMAN_TOOLCHAIN_VENV` for scripts.
- `scripts.repoman-sync` semantics change: consumer mode no longer installs the toolchain into the
  consumer venv. It becomes "ensure the shared venv exists (warn with the one-liner if missing) +
  `repoman install-skills`". `repoman-sync --machine` remains the toolchain installer.
- `repoman.managers` keeps its meaning for *wiring* (which manager tasks/skills are active) but no
  longer gates the toolchain install — the shared venv holds all pure-CLI managers regardless.

### 5.2 Manager modules (`modules/managers/*.nix`)

- `gitman.nix`, `copyroom.nix`, `docman.nix`: task execs change
  `${venvBin}/<manager>` (consumer-venv absolute path) → bare `<manager>` (PATH-resolved to the shared
  venv). The `venvBin` let-binding can be deleted.
- `testee.nix`: **unchanged** — `${venvBin}/testee` is still correct (testee is in the consumer venv).
- `gitman.nix`: `nativeBuild`/rust/maturin machinery stays (escape hatch for pyjutsu's own repo / a
  wheelhouse-less machine bootstrap) but is no longer exercised by normal consumers. `languages.rust`
  never activates in consumers under the default wheel path — same as today.

### 5.3 `src/repoman/checks.py` (doctor self-check)

- `lock:*` checks must treat **uv-declared managers** (testee) as project-managed: when a manager is
  found in the consumer's `pyproject.toml` (`[dependency-groups]` / `[project.optional-dependencies]`),
  the "selected but absent from repoman.lock" failure is suppressed in favor of an
  "ok — uv-declared" check. Without this, `repoman doctor` FAILs `lock:test` for every consumer.
- `installed:<key>` (`shutil.which`) keeps working unchanged: both venvs are on PATH inside the shell.
- `provisioned:<key>` (REPOMAN_PROVISIONED_* nix-input signals) is unaffected.

### 5.4 `modules/scripts/repoman-sync.sh`

- `--machine`: resolve `repoman.lock` (from `$REPOMAN_ROOT`, defaulting to the repoman checkout) and
  `uv pip install` into `$REPOMAN_TOOLCHAIN_VENV` (create the venv first if absent). The existing
  TOML resolver, `wheel:` guard, and editable-`path:` handling are reused verbatim.
- consumer mode: drop the toolchain install; keep skills/docs install.

---

## 6. Manifest ownership — every package has exactly one home

| Manifest | Owns | Lives at | Updated by |
|---|---|---|---|
| machine `repoman.lock` | repoman, gitman, copyroom, docman, pyjutsu (+ their libs) | repoman checkout root | copyroom convergence → `repoman-sync --machine` |
| consumer `pyproject.toml` + `uv.lock` | app deps, extras, **testee** + pytest/ruff/ty/import-linter | per repo | `uv sync` / `uv lock` |
| devenv-generated | nix packages, tasks, scripts, skills, docs | per repo | `devenv update`, `repoman install-skills` |

No overlap → no racing installers, no drift.

---

## 7. File-by-file change surface

**repoman repo:**
| File | Change |
|---|---|
| `modules/devenv.nix` | PATH prepend shared bin; export `REPOMAN_TOOLCHAIN_VENV`; consumer `repoman-sync` → ensure-shared + install-skills |
| `modules/scripts/repoman-sync.sh` | `--machine` mode (create/sync shared venv from machine lock); consumer mode shrinks |
| `modules/managers/gitman.nix` | `${venvBin}/gitman` → `gitman` (PATH); drop `venvBin` binding |
| `modules/managers/copyroom.nix` | `${venvBin}/copyroom` → `copyroom`; drop `venvBin` binding |
| `modules/managers/docman.nix` | `${venvBin}/docman` → `docman`; drop `venvBin` binding |
| `modules/managers/testee.nix` | **no change** |
| `src/repoman/checks.py` | uv-declared-manager awareness for `lock:*` checks |
| `repoman.lock` (new, checkout root) | machine toolchain manifest — no `[managers.test]` |
| `devenv.yaml` / `devenv.nix` (repoman's own) | add `vendomat` input so `--machine` bootstrap has `UV_FIND_LINKS` (or document the from-source path) |
| `src/repoman/devman/assets/docs/languages-python.md` | revert to `uv sync --all-extras` (now safe); note testee as declared dev dep |
| `src/repoman/devman/assets/skills/devenv-python-venv/SKILL.md`, `devenv-troubleshoot/SKILL.md`, `articles/command-not-found-in-shell.md` | same revert; `repoman-sync` mention → "ensures shared toolchain + skills" |
| `tests/consumer-example/` | fixtures regenerate; drop `vendor.enable`/vendomat; delete its `repoman.lock` |

**copyroom repo (template):**
| File | Change |
|---|---|
| `demo/fixtures/minimal-python-package/template/pyproject.toml.jinja` | render `[dependency-groups] dev = ["testee"]` + `[tool.uv.sources] testee` (fleet git ref) |

**template-py (remote, fleet genome):** same `pyproject.toml.jinja` change; the docs line
`uv sync --all-extras` is correct again.

**Consumers (e.g. `../image-gen-pipeline`):**
| File | Change |
|---|---|
| `pyproject.toml` | add dev-group testee + `[tool.uv.sources]` |
| `devenv.yaml` | drop the `vendomat` input |
| `devenv.nix` | drop `vendor.enable`; `repoman.managers` unchanged |
| `repoman.lock` | **delete** (machine-level now) |

---

## 8. Migration order

1. **Machine side first:** `repoman-sync --machine` + machine `repoman.lock` + `REPOMAN_TOOLCHAIN_VENV`; bootstrap the shared venv once (vendomat wheelhouse context or a one-time from-source build).
2. **Nix wiring:** meta-module PATH prepend; `gitman/copyroom/docman.nix` task execs → PATH-resolved; consumer `repoman-sync` shrinks.
3. **Doctor:** `checks.py` uv-declared-manager awareness.
4. **Template:** `pyproject.toml.jinja` renders testee dev-dep + `[tool.uv.sources]`.
5. **Consumers:** add the testee dev-dep, `uv sync`, drop vendomat, delete `repoman.lock`.
6. **Docs/skills:** revert the 11-project's doc-surgery (the guidance becomes safe again).
7. **Dogfood:** validate in `../image-gen-pipeline` (checklist below), then a copyroom-born repo.

---

## 9. Validation checklist (run in `../image-gen-pipeline`, all via `devenv shell -- <cmd>`)

1. **Machine bootstrap:** `repoman-sync --machine` → shared venv contains `repoman`, `gitman`,
   `copyroom`, `docman`, `pyjutsu`; `gitman status` works from the consumer.
2. **Clean consumer:** `uv sync --all-extras` → app deps + `testee` + `pytest`/`ruff`/`ty` installed
   in the consumer venv; `testee verify --mode quick` green; `gitman status` green (shared);
   `repoman doctor` all-OK — **including `lock:test`** (uv-declared awareness).
3. **Footgun regression:** run `uv sync --all-extras` again → **zero uninstalls** (was 33). The
   11-project's repro is the acceptance test.
4. **Toolchain survives doc-recommended commands:** `uv sync`, `uv sync --all-extras`,
   `uv pip install --all-extras -e .` — after each, `gitman status`, `testee verify --mode quick`,
   and `repoman status` still work.
5. **Upgrade clocks:** bump testee (`uv lock --upgrade-package testee`) moves only testee; bump a
   machine pin + `repoman-sync --machine` moves the rest — both end with a working repo.
6. **Template birth:** `copyroom new` from the updated template renders a repo whose pyproject has
   the testee dev-dep and which passes 2–4 with no manual edits.
7. **No orphan manifests:** no consumer has a `repoman.lock`; no `[managers.test]` anywhere in the
   machine lock; `rg -n "uv sync" src/ modules/` shows only the (now-safe) recommendations.

---

## 10. Trade-offs & accepted constraints

- **Two upgrade clocks.** testee bumps per-repo via uv; the rest move machine-wide in lockstep via
  copyroom convergence. Deliberate: testee is the only manager coupled to the repo's code.
- **One system-wide version for the pure-CLI managers.** A consumer cannot pin a different
  gitman/copyroom than the machine. Accepted — "fleet moves in lockstep" is repoman's convergence
  model anyway.
- **pyjutsu wheel at bootstrap.** Needed once per machine (wheelhouse or a from-source build);
  consumers never see it and no longer import vendomat.
- **`repoman-sync` semantics change** in consumers: it stops installing the toolchain into the
  consumer venv ("ensure shared venv + install skills"). The mental model moves from "sync the
  toolchain into this repo" to "the toolchain is the machine; this repo just declares testee".
- **`uv pip install -e .` installs neither dev groups nor extras** — the documented install command
  must be `uv sync` (now safe), and the 11-project's docs change is reverted to that.
- **`repoman.managers` no longer gates toolchain install** (only wiring/skills). Extra pure-CLI
  managers on PATH are harmless — same as the status quo for a machine that touches several repos.

---

## 11. Open questions / decisions pending

1. **Shared-venv path resolution in nix:** `builtins.getEnv "XDG_DATA_HOME"`/`"HOME"` at eval
   (single-user dev is fine) vs. runtime prepend in `enterShell`/scripts with `env.PATH` set from a
   stable default. Decision needed before `modules/devenv.nix` lands.
2. **Machine-lock location:** repoman checkout root (recommended — it's where convergence points) vs.
   `~/.config/repoman/repoman.lock`. The former keeps the fleet refs in-repo and versioned.
3. **Bootstrap context for the pyjutsu wheel:** repoman's own devenv gains the `vendomat` input
   (smallest diff, matches consumers today) vs. a one-time `maturin build --release` at the repoman
   checkout (no new input, ~7.5 min once). 
4. **`[dependency-groups] dev` vs `[project.optional-dependencies] dev`:** uv-native group (default-on
   for `uv sync`) is recommended; the template fixture currently uses the extras style. The two
   render different install commands — pick one and standardize docs on it.
5. **Doctor UX for uv-declared managers:** `lock:test → ok (uv-declared, pyproject.toml)` — exact
   wording and whether a future non-testee uv-managed manager should be allowed (design the check to
   be generic over a `REPOMAN_UV_MANAGERS`-style marker, or keep it testee-specific for now).
