# KICKOFF — repo-set sync (fleet mode) for repoman

> Extend **repoman** with the v1-out-of-scope **fleet feature**: a `repos.toml`-driven
> command that idempotently clones/fetches a declared set of repos into
> `~/Documents/Projects` on BOTH machines (GitHub canonical). Folds INTO repoman's
> existing Python-CLI + devenv-module structure — it is NOT a new repo and NOT a new
> entry in the `*man` manager registry.

You are starting a FRESH session working in `/home/andrew/Documents/Projects/repoman`.
Read this packet, then `CONTEXT.md` (a map of repoman's current command/manager flow),
then propose a step-by-step plan for approval before writing any code.

---

## Role & where this fits

- **Master plan:** `/home/andrew/.dotfiles/.scratch/projects/37-tower-dotfiles/PLAN.md`
- **Phase:** **Phase 5 — Local CI** (PLAN.md §8). The last checkbox of Phase 5:
  > *repo-set sync in `repoman` (`repos.toml` + multi-repo clone/fetch) on both machines → `~/Documents/Projects`.*
- **Spec source:** PLAN.md §7 ("repo-set sync (in `repoman`)") and §4 repo map row
  *"Repo-set sync (`Projects` on both) → `repoman` (v2 fleet feature) — EXTEND."*
- **Decision log:** `/home/andrew/.claude/projects/-home-andrew--dotfiles/memory/tower-dotfiles-project.md`
  - Round-4 repoman note: *"repoman = per-repo conductor; composes *man tools … Fleet/multi-repo
    EXPLICITLY out of scope v1. REUSE as-is; repo-set sync is a v2 candidate."*
  - FINAL REPO PLAN: *"Repo-set sync folds INTO `repoman` (new manager/command, v2 fleet feature
    — `repos.toml` + multi-repo clone/fetch; NOT a standalone repo)."*

repoman's own CONCEPT.md §2 states fleet/workspace management was out of scope for v1.
This packet is the v2 reversal of exactly that line, scoped to the GitHub-canonical
two-machine (framework laptop + tower) model.

---

## The shape this must take (grounded in repoman's actual code)

repoman has TWO layers (CONCEPT.md §6): a **Nix meta-module** (`modules/devenv.nix` +
`modules/managers/*.nix`) and a **thin Python conductor** (`src/repoman/`). The fleet
feature must extend BOTH, the same way the rest of repoman is built.

Crucial structural distinction observed in the code — DO NOT get this wrong:

- The `*man` **managers** (`copy`/`git`/`test`/`doc`/`session`/`agent`/`spec`) are
  EXTERNAL tools. They live in `src/repoman/registry.py:REGISTRY`, each maps to a
  console script repoman shells out to (`aggregate.run_sub`), and each has a thin
  wiring module in `modules/managers/<name>.nix`. **Repo-set sync is NOT one of these.**
  It is logic repoman *implements itself*, not an external CLI it aggregates.
- The right precedent is **`src/repoman/devman/`** — a self-contained **subsystem**
  folded into repoman with no registry entry: its own subpackage
  (`devman/__init__.py` docstring: *"shipped as a subsystem of repoman … It has no
  CLI of its own"*), its own `check.py` contributing `SelfCheck`s into `repoman doctor`
  (wired at `cli.py:65` via `devman_checks(...)`), and its own `install.py`.
  **Model the fleet feature on `devman/`, not on the manager roster.**

So: a new **`src/repoman/fleet/`** subpackage + a new **CLI subcommand** in
`cli.py` + a new **`modules/managers/fleet.nix`** wiring module + (optionally) a
self-check folded into `repoman doctor`.

---

## Work items (target paths in repoman)

### 1. `repos.toml` schema (the fleet manifest)
Define the manifest the command reads. Per PLAN.md §7 the fields are **name / url / path**.
Proposed shape (confirm during planning):

```toml
# repos.toml — the Projects fleet manifest
[defaults]
root = "~/Documents/Projects"   # base dir; overridable per-machine (see open questions)

[[repos]]
name = "nixos-core"
url  = "https://github.com/Bullish-Design/nixos-core.git"   # GitHub canonical
# path optional; defaults to <root>/<name>
[[repos]]
name = "nix-terminal"
url  = "https://github.com/Bullish-Design/nix-terminal.git"
[[repos]]
name = "nix-meta"
url  = "https://github.com/Bullish-Design/nix-meta.git"
# … nix-nvim, nix-desktop, nix-cache, nix-secrets, nix-ci, repoman, gitman, devman, nixbuild, etc.
```

- Parse with `tomllib` (already the repo's pattern — see `checks.py:13`,
  `repoman-sync.sh`). No new dependency.
- `path` defaults to `<root>/<name>`; expand `~`. `url` is the **GitHub canonical**
  remote — both machines clone from GitHub (PLAN.md §1, §4; decision log round-2:
  *"Both machines clone from GitHub (repoman/gitman)"*).

### 2. The fleet subpackage — `src/repoman/fleet/`
Mirror `src/repoman/devman/` layout:
- `fleet/__init__.py` — subsystem docstring (NOT a manager; no registry entry).
- `fleet/manifest.py` — load + validate `repos.toml` into a small dataclass/Pydantic
  model (`pydantic` is already a dep, pyproject.toml). Resolve `root`/`path`/`~`.
- `fleet/sync.py` — the **idempotent clone-or-fetch engine** (semantics below). Shell
  out to `git` via `subprocess`, mirroring `aggregate.run_sub`'s subprocess style and
  the `0/1/2/3` exit-code contract (CONCEPT.md §1; `aggregate.worst_exit`).
- `fleet/check.py` *(optional but recommended)* — a `devman`-style
  `fleet_checks(...) -> list[SelfCheck]` that reports whether `repos.toml` exists and
  parses, folded into `repoman doctor` next to `devman_checks` at `cli.py:65`.

### 3. Idempotent clone-or-fetch semantics (`fleet/sync.py`)
Per-repo, re-runnable with no side effects when up to date:
- **Absent** (`<path>` has no `.git`) → `git clone <url> <path>`.
- **Present & clean** → `git fetch` then fast-forward only (`git merge --ff-only` /
  `git pull --ff-only`). Never merge-commit, never rebase silently.
- **Present & dirty** (uncommitted changes, or not fast-forwardable) → **SKIP with a
  warning**, do not touch the working tree. Report it; don't fail the whole run for one
  dirty repo (collect per-repo outcomes, return the worst exit code).
- **Wrong/missing remote** → warn (don't silently rewrite `origin`); surface as a
  decision-needed (exit 1) rather than clobbering.
- Final exit follows the `0/1/2/3` contract (`aggregate.worst_exit` pattern):
  `0` all ok/up-to-date, `1` a repo needs a human decision (dirty/diverged), `2`
  infra (git missing, network/auth), `3` invalid usage (bad `repos.toml`).

### 4. CLI subcommand — `src/repoman/cli.py`
Add ONE subcommand to the existing Typer `app` (alongside `managers` / `doctor` /
`status` / `install-skills`). Suggested name **`repoman fleet-sync`** (or a `fleet`
sub-app with `fleet sync` / `fleet status`). It should:
- Resolve the manifest path (`--manifest`, default `$DEVENV_ROOT/repos.toml` then a
  machine/XDG location — see open questions), call `fleet.sync.run(...)`, print a
  per-repo report, `raise typer.Exit(code=worst)`.
- Keep `cli.py` thin (it imports from subpackages — see the `from .devman.* import …`
  lines at `cli.py:16-17`); put logic in `fleet/`.

### 5. Nix wiring — `modules/managers/fleet.nix` + `modules/devenv.nix`
- New module `modules/managers/fleet.nix`, imported (unconditionally, gated internally)
  from `modules/devenv.nix`'s `imports` list, EXACTLY like `gitman.nix`/`docman.nix`.
  It is pure-Python (no native toolchain), so model it on the **simple `gitman.nix`
  task-wiring shape**, minus the Rust/maturin block:
  - gate on `cfg.enable && builtins.elem "fleet" cfg.managers`;
  - contribute a task, e.g. `"repoman:fleet:sync".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/repoman fleet-sync'';`
    (`venvBin = "${config.devenv.state}/venv/bin"`, per gitman.nix:14).
- In `modules/devenv.nix`: add `"fleet"` to the `allManagers` list (line 26) and the
  `repoman.managers` enum so consumers can select it, and add `./managers/fleet.nix`
  to `imports` (line 29).
- **DECISION TO MAKE (note in plan):** is "fleet" a selectable *manager* in
  `repoman.managers`, or always-available like devman? Recommendation: treat it like a
  manager key for the nix gating (so a repo opts in), but the *logic* stays a repoman
  subsystem (`fleet/`), NOT a `registry.py` entry — because repoman runs it itself, it
  isn't an external `*man` CLI to aggregate. If you add a registry entry at all, it
  would only be to surface it in `repoman managers`; if so, it needs no `doctor`/`status`
  console-script (it's repoman's own subcommand, not a separate binary).

### 6. The existing `repoman-sync.sh` — EXTENDS, does NOT supersede
**Important finding / naming hazard:** `modules/scripts/repoman-sync.sh` ALREADY EXISTS
but does something COMPLETELY DIFFERENT from repo-set sync. It reads `repoman.lock`
and `uv pip install`s the selected managers' Python packages **into the devenv venv**
(toolchain sync), then runs `repoman install-skills`. It does NOT clone repos.
- The new feature is **additive and orthogonal** — it neither extends nor supersedes
  `repoman-sync.sh`. Keep them separate.
- **Avoid the name `repoman sync` / `repoman-sync` for the fleet command** — it collides
  conceptually with the existing toolchain sync. Use `fleet-sync` / `repoman fleet …`.

---

## Acceptance criteria

Done when:
1. `repoman fleet-sync` reads a `repos.toml` and, on a **fresh machine**, idempotently
   **clones** the declared Projects repo set into `~/Documents/Projects` from the
   GitHub-canonical URLs.
2. Re-running when everything is up to date is a **no-op** (fetch + already-ff; no
   working-tree changes, exit 0).
3. A repo that is present and behind is **fast-forwarded**; a **dirty** repo is
   **skipped with a warning** (working tree untouched) and surfaced in the report.
4. It runs the SAME on **both machines** (framework laptop + tower) — no machine-specific
   branch in the logic; only the manifest/root may differ per machine.
5. Exit code follows the `0/1/2/3` contract via the `worst_exit` aggregation pattern.
6. `modules/managers/fleet.nix` wires a `repoman:fleet:sync` task, gated on
   `"fleet" ∈ repoman.managers`; selecting it in a consumer devenv exposes the command.
7. `repoman.lock` already pins repoman itself, so the fleet code ships with repoman —
   no new pinned manager is required for the fleet command to be available.
8. Tests under `tests/` cover clone (absent), ff (behind), no-op (current), and
   skip-dirty, matching repoman's existing pytest setup (pyproject.toml `[tool.pytest]`).

---

## Dependencies & integration

- **Runs on BOTH machines** (framework + tower) — pairs with the GitHub-canonical model
  where laptop and tower both clone from GitHub (PLAN.md §1/§4; decision log round-2).
  The tower is a rebuildable executor, NOT canonical (PLAN.md §11) — fleet sync is how it
  (re)materializes the Projects set.
- **Composes with `gitman` per-repo:** fleet sync gets the repos *onto disk*; `gitman`
  (the `git` manager) then owns per-repo VC inside each. Fleet does coarse clone/ff only;
  it must not fight gitman's jujutsu/colocated-git working state (hence skip-dirty).
- **Fits the `repoman.managers` / devenv-module pattern:** opt-in via the manager list,
  task-wired through `modules/managers/fleet.nix`, logic in `src/repoman/fleet/`.
- **No new Python deps:** `tomllib` (stdlib), `pydantic`, `typer`, `subprocess` — all
  already present (pyproject.toml).

---

## Open questions (surface, don't block)

1. **Where does `repos.toml` live?** Ambiguous in the source material. Candidates:
   - in `repoman` itself (a checked-in fleet manifest) — but repoman is per-repo, and the
     Projects set spans repos;
   - in **`nix-meta`** (the orchestrator that already knows both machines) — likely best
     home, generated/owned there and pointed at via `--manifest`/env;
   - per-machine (different roots/subsets on laptop vs tower).
   Recommendation: support a `--manifest` flag + an env/default search
   (`$DEVENV_ROOT/repos.toml`, then an XDG/machine path), and DECIDE the canonical home
   with the nix-meta work. Flag it; don't hardcode.
2. **Auth for private repos.** Cloning private GitHub repos on a fresh machine (esp. the
   headless tower) needs credentials. PLAN.md §7 lists *"GitHub access (deploy key/PAT)"*
   among the `nix-secrets` (sops) secrets. The fleet command should rely on ambient git
   auth (ssh `git@github.com:` URLs + a deploy key, or a PAT credential helper) provisioned
   by **`nix-secrets`** — do NOT handle secrets in repoman. Note: prefer `git@github.com:`
   SSH URLs in `repos.toml` if deploy-key auth is the model. Confirm against `nix-secrets`.
3. **`repos.toml` ↔ `repoman.lock` relationship.** They are unrelated files with similar
   names (`repoman.lock` = venv toolchain pins; `repos.toml` = fleet manifest). Keep the
   distinction explicit in docs to avoid confusion.
4. **Manager vs subsystem registry placement** (see Work item 5) — decide whether "fleet"
   gets a `registry.py` surface for `repoman managers` listing, or stays purely a
   subcommand + subsystem like devman.

---

## Source material (cite when implementing)

- Master plan: `/home/andrew/.dotfiles/.scratch/projects/37-tower-dotfiles/PLAN.md` (§1, §4, §7, §8 Phase 5).
- Decision log: `/home/andrew/.claude/projects/-home-andrew--dotfiles/memory/tower-dotfiles-project.md` (rounds 2 & 4, FINAL REPO PLAN).
- repoman `CONCEPT.md` (§1 contract, §2 v1 out-of-scope fleet line, §6 two-layer composition, §7 layout).
- `src/repoman/cli.py` — Typer app + where to add the subcommand; `devman_checks` wiring at line 65.
- `src/repoman/registry.py` — the `*man` roster (what fleet is NOT).
- `src/repoman/aggregate.py` — subprocess + `worst_exit` (the `0/1/2/3` pattern to reuse).
- `src/repoman/devman/{__init__,check}.py` — the subsystem precedent to mirror.
- `src/repoman/checks.py` — `SelfCheck` + `tomllib` usage.
- `modules/devenv.nix` — `allManagers`, the enum, the `imports` list.
- `modules/managers/gitman.nix` — the simple task-wiring shape to copy (drop the Rust block).
- `modules/scripts/repoman-sync.sh` — the EXISTING (unrelated) toolchain sync; the naming hazard.

## Guardrails

- Implement ONLY the fleet feature; do not restructure repoman or touch the `*man`
  managers' wiring beyond adding `"fleet"` to the enum + the new module import.
- All in-repo commands run inside the devenv shell (`devenv shell -- …`).
- Do not commit/push without being asked.
