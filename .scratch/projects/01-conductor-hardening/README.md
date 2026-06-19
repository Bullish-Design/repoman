# 01 — Conductor hardening

Three changes that take RepoMan from "spike proven" to "robust", in recommended order.
Each has its own detailed guide in this directory.

| # | Guide | What it proves / gives | Weight |
|---|---|---|---|
| 1 | [01-gitman-native-toolchain.md](01-gitman-native-toolchain.md) | The meta-module can contribute **nix-level system toolchains** (Rust/maturin), not just venv pip installs. Wires gitman (3rd manager). | Heavy |
| 2 | [02-repoman-unit-tests.md](02-repoman-unit-tests.md) | A real test suite for the `repoman` package (currently **zero** tests). | Light |
| 3 | [03-doctor-self-check.md](03-doctor-self-check.md) | `repoman doctor` gains a preflight self-check (lock ↔ managers ↔ PATH ↔ skills), beyond pass-through. | Medium |

## Current state these build on (verified, in `tests/consumer-example/`)

- Meta-module `modules/devenv.nix` (`options.repoman.{enable,managers,template,installSkills,skillsDir}`) statically imports per-manager modules under `modules/managers/`, each gated on membership in `repoman.managers`.
- `repoman-sync` (`modules/scripts/repoman-sync.sh`) reads `repoman.lock`, `uv pip install`s the `[repoman]` self entry + selected managers (`path:` → `--editable`), then runs `repoman install-skills`.
- The `repoman` CLI (`src/repoman/`) is a pass-through conductor: `managers` / `doctor` / `status` aggregate each manager's own CLI under the `0/1/2/3` exit-code contract (`registry.py`, `aggregate.py`); `install-skills` generates the entrypoint router skill (`skills.py` + `templates/entrypoint.SKILL.md.j2`).
- Managers wired & proven: `test` (testee), `copy` (copyroom). `git` (gitman) is deferred — guide 1.

## Conventions for all three

- Work happens inside the devenv shell: `devenv shell -- <cmd>` (never bare `uv`/`pytest`).
- Verify in the throwaway consumer at `tests/consumer-example/` (rebuild = `rm -f devenv.lock && rm -rf .devenv` when module/env changes aren't picked up — its `devenv.lock` pins the `repoman` input).
- Keep the conductor **tolerant of heterogeneity** (managers differ; don't assume a uniform contract).
- Commit the current verified state on a branch before starting (work is presently uncommitted on `main`).
