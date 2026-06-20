# devman — Content inventory (brainstorm)

The concrete first set of assets devman would ship (as a repoman subsystem), across its three
layers. Each is grounded in a real, observed agent failure mode in devenv-managed repos. A
candidate list to prune/prioritize, not a locked spec.

## Layer 1 — Skills (`modules/devman/assets/skills/` → installed to `skillsDir`)

Short, trigger-driven. One job each. Triggers fire on **mechanics** keywords so they don't
collide with RepoMan's entrypoint (lifecycle keywords) or the manager skills (domain keywords).

| Skill | Triggers when… | Core rule it enforces |
|---|---|---|
| `devenv-run-commands` | about to run `pytest`/`python`/`uv`/`ruff`/a build | Never run bare tools; use `devenv shell -- <cmd>` or the repo's scripts/tasks. Why: fresh shells lack the pinned PATH/env/determinism vars. |
| `devenv-module-edits` | editing `modules/`, `devenv.nix`, `env.*` and "nothing changed" | The lock/eval-cache loop: when to `rm -f devenv.lock && rm -rf .devenv`, when `--refresh-eval-cache`, when `devenv update <input>`. |
| `devenv-inputs` | editing `devenv.yaml`, adding an import/input | `flake: false` for module inputs; `nixpkgs-python` for version pins; remote imports merge `devenv.nix` not `devenv.yaml` (declare transitive inputs). |
| `devenv-python-venv` | `ModuleNotFoundError`, fresh venv, "import fails in shell" | venv exists ≠ deps installed; run `uv sync` / the repo's sync script; how `pythonpath`/editable installs resolve. |
| `devenv-processes` | starting a server / long-running task | `processes` + `devenv up` for daemons; don't block the shell; poll logs; background heavy builds rather than piping output out of view. |
| `devenv-authoring` | writing a `scripts`/`tasks`/`processes` entry or a manager module | `scripts` vs `tasks` (deps/ordering) vs `processes`; guard `enterShell` echoes with `if [ -t 1 ]`; the `0/1/2/3` exit contract. |
| `devenv-troubleshoot` | "command not found", shell won't enter, eval errors | A decision tree from symptom → cause → fix, linking into the articles. |

Note: there is **no separate `devenv-entrypoint` skill** — RepoMan's generated entrypoint is the
single front door. Each devman skill carries the standard footer deferring cross-cutting
*ordering* to the `repoman` skill, and triggers on its own mechanics keywords so several don't
fire as "primary" at once (the `docs/SKILLS.md` discipline).

## Layer 2 — Documentation export (`modules/devman/assets/docs/` → installed to `docsDir`)

A distilled, agent-optimized subset of devenv.sh docs — curated, regenerable, noise-stripped.
Foregrounds the agent-relevant facts; drops marketing and human-onboarding prose.

- `shell.md` — entering/using the shell; `devenv shell -- <cmd>`; env/PATH model.
- `languages-python.md` — `enable`/`version`/`venv`/`uv`; the `nixpkgs-python` requirement.
- `scripts-tasks-processes.md` — the three execution surfaces and when to use each.
- `inputs-and-imports.md` — `devenv.yaml`, `flake: false`, remote module imports, transitive inputs.
- `lock-and-cache.md` — `devenv.lock`, the eval cache, `devenv update`, `--refresh-eval-cache`.
- `git-hooks.md` — opt-in hooks, the `git-hooks` input.
- `glossary.md` — terms an agent will hit (DEVENV_ROOT, devenv.state, enterShell/enterTest…).

> Generated from a curated source + a hand-written "agent gotchas" overlay, so it tracks
> devenv.sh releases instead of rotting.

## Layer 3 — Articles / recipes (`modules/devman/assets/articles/`)

Longer "why + worked example" pieces for the recurring hard cases.

- `the-lock-cache-loop.md` — why a module edit didn't take, and the exact recovery, with the
  three distinct situations (consumer pin vs local module vs input update).
- `authoring-a-manager-module.md` — building a `*man`-style module: options + gated config,
  scripts/tasks, putting a CLI on PATH (the pattern behind copyroom/testee/gitman/docman).
- `command-not-found-in-shell.md` — venv vs nix packages vs scripts; how PATH is assembled.
- `ci-inside-devenv.md` — running the verify/test loop in CI through the shell; determinism.
- `background-and-long-running-work.md` — processes, `devenv up`, polling, not blocking.
- `adopting-the-man-family.md` — how devman + RepoMan + the managers fit; what to install first.

## Cross-cutting (folded into RepoMan, not a separate tool)

- **Install** — `repoman-sync` lays down devman's `skills` + `docs` (extends the existing
  `repoman install-skills` step in `src/repoman/skills.py`), writing a manifest (sources +
  repoman version) for drift detection (allium-env `.allium-devenv-source` pattern).
- **Verify** — `repoman doctor` self-check (`src/repoman/checks.py`) gains `devman:skills` /
  `devman:docs` checks (installed? current? devenv rule reachable?) under its existing
  `ok/warn/fail` → exit mapping.
- **Tone** — imperative + short for skills, factual + grep-able for docs, explanatory for
  articles. The same fact is never written twice across layers — skills point at docs, docs
  point at articles.
