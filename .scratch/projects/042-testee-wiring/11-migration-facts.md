# 11 Migration facts for the self-launcher design

Date: 2026-10-10. Read-only study. Labels: **verified** (read or run), **inferred**, **unknown**.
Paths: `T/` = `/tmp/tw-trunk/repoman` (trunk 0.13.0). `P/` = `/home/andrew/Documents/Projects`.
Scratch repros live under `/tmp/tw-w3/`. Devenv used: 2.4.0+b904dcb.

## 1. Does `repoman doctor` gate anything?

### Answer: no. Doctor runs only when a person or agent types it.

Verified: no gate calls `repoman doctor`.

- **Repoman gate.** `T/devenv.nix:157-166` (`scripts.gate`) runs `check-fleet-lock.py --rev HEAD` and `testee verify --full`. No doctor.
- **Repoman tasks.** `T/devenv.nix:178-183` defines `repoman:lint`, `base:check` and `base:test`. No doctor.
- **RepoMan modules.** `rg doctor T/modules` finds only comments (`modules/devenv.nix:34,138`, `managers/testee.nix:32`). No task, script or `enterTest` runs it. `repoman-sync` does not run it.
- **Git hooks.** `.git/hooks` holds only `*.sample` files in every `P/*` repo (plus a `docs.url` file in agentman and argentic).
- **CI.** Workflows exist only in cairn, docman, siteman. docman runs `docs-doctor`, not `repoman doctor`. None runs `repoman doctor`.
- **Fleet build files.** A grep of `devenv.nix`, `devenv.local.nix`, `devenv.yaml`, `gitman.toml`, `flake.nix`, `justfile`, `Makefile`, `.envrc`, `.github/workflows`, `scripts`, `ci` across all `P/*` finds zero `repoman doctor` or `repoman:doctor`.
- **gitman release gate.** The `gate` script exists only in repoman (`T/devenv.nix:157-166`). It has no doctor. Fleet `gitman.toml` `verify` keys hold `testee verify --full`.

Doctor appears in text that nothing executes:

- 21 `P/*/copyroom.project.yml` files have `commands.check: ["devenv shell -- repoman doctor"]`. That file calls itself "advisory metadata".
  Verified: no code reads `commands.check`. `rg` finds no consumer in `copyroom/src`, `repoman/src`, `devman/src`, `gitman/src`.
  Copyroom code only mentions `copyroom:project inputs` commit messages (`copyroom/src/copyroom/local/workflow.py:751`). So copyroom does not read the key.
- Docs and template articles show `repoman doctor` in a CI example (`P/template-py/template/.agents/devenv/articles/ci-inside-devenv.md:16`). No fleet repo has that workflow.
- Scopeman's `.loci/.../IMPLEMENTATION-GUIDE.md` lists it as a manual step.

### What the skewed row does

Setup: host `testee` 0.6.0, project pin `v0.5.1`, RepoMan 0.12.1 or 0.13.0.

- `_version_check` reads `REPOMAN_TESTEE_VERSION`. It runs `$REPOMAN_TESTEE_HOST_BIN --version`. It sets `level = "fail"` when the two differ (`T/src/repoman/checks.py:296`).
- `v0.12.0`, `v0.12.1` and `v0.13.0` all carry this row. Verified with `git show <tag>:src/repoman/checks.py`.
- `_LEVELS = {"ok": 0, "warn": 0, "fail": 1}` (`checks.py:36`). `self_check_exit` takes the maximum (`checks.py:448-451`). So doctor exits 1.
- The row text reads `.../testee reports 0.6.0; pinned package requires 0.5.1`.
- Effect: a red line and exit 1 when someone runs doctor. It blocks nothing, because nothing runs doctor (above).
- Current host state: `~/.nix-profile/bin/testee` is `testee 0.5.1` (store `rs4i9wy1...`). So there is no skew today. Verified by running `--version`.

### Old RepoMan and the host path

- Old `enterShell` sets the path. `modules/devenv.nix:139-140` at 0.13.0 (line 135-136 at 0.12.0 and 0.12.1):
  `export REPOMAN_TESTEE_HOST_BIN="${REPOMAN_TESTEE_HOST_BIN:-$HOME/.nix-profile/bin/testee}"` and a PATH line that prepends `dirname` of it. Verified.
- `repoman:test` runs `"${REPOMAN_TESTEE_HOST_BIN:-$HOME/.nix-profile/bin/testee}" verify` (`modules/managers/testee.nix:24,34-35`). Verified.
- `registry.py:108-109` binds the `test` manager to `REPOMAN_TESTEE_HOST_BIN` and `REPOMAN_TESTEE_VERSION`. Verified.

If the host `testee` moves to `/etc/profiles/per-user/andrew/bin` and the old default stays:

1. `repoman:test` and `repoman:test:ci` fail with "No such file" (exit 127). Verified by code; not run. This breaks `base:test` in repoman and scopeman.
2. `doctor` rows `installed:test` and `version:test` fail with "missing or not executable". `_installed_check` lines 205-210; `_version_check` lines 279-283. Verified by code.
3. Bare `testee` in tasks (`testee check pytest`) still works. The old PATH line prepends `~/.nix-profile/bin`. That directory then lacks `testee`. A task then resolves `testee` to the pinned package or the host entry later on PATH.
4. Escape hatch: `export REPOMAN_TESTEE_HOST_BIN=/etc/profiles/per-user/andrew/bin/testee` before the shell. The `${VAR:-default}` form honors it. Verified by code.

## 2. Scopeman

- Code: `P/scopeman/devenv.nix:79`: `"base:test".after = [ "repoman:test" ];`. Verified.
- Code comment: `devenv.nix:7-8` says RepoMan wires `repoman:test`, `repoman:test:ci`, `enterTest`. Stale (RepoMan dropped `enterTest` at 0.12.1).
- Docs: `P/scopeman/.loci/projects/037-scopeman/03-detail-design/IMPLEMENTATION-GUIDE.md:361`. A design note, not executed.
- No other code reference in scopeman. `devenv.yaml` pins RepoMan `v0.12.1`. `gitman.toml` holds only `trunk = "main"`. AGENTS.md calls `testee verify --full` directly.
- `base:check` goes through `scopeman:lint` (raw `uv run ruff`), not Testee (`devenv.nix:74-78`).

Hard failure if `repoman:test` vanishes. Verified by repro in `/tmp/tw-w3/missing-after`:

- A `devenv.nix` with `tasks."base:test".after = [ "repoman:test" ]` and no such task gives
  `Task dependencies not found: base:test is depending on non-existent repoman:test`.
- `devenv tasks run base:test`, `devenv shell -- echo ok` and `devenv test` all exit 1 with that message.
- The shell does not start at all. The failure is not limited to `base:test`.

So scopeman and repoman must edit before they take RepoMan 0.14.

Replacement. Pick one:

1. `tasks."base:test".exec = "cd \"$DEVENV_ROOT\" && testee check pytest";` Matches the template shape (`template-py` `devenv.nix.jinja`) and the agentman, inferference, linkman and mancore shape.
2. `exec = "testee verify --full"` as mancore and linkman use for `base:check`.
3. `after = [ "testee:verify" ]`. Testee's module defines this task (`testee/nix/testee.nix:66`). It runs the pinned package, not the host.

Inferred: option 1 fits scopeman, because scopeman wants a pytest verdict and already runs ruff in `scopeman:lint`.
For repoman itself, `T/devenv.nix:182` needs the same swap; its comment at `T/devenv.nix:174-181` needs a rewrite.

## 3. Testee self-hosting with a release-pinned runner

### State today

- `testee/devenv.nix:8`: `testee.package = import ./nix/testee-package.nix { inherit pkgs; };`. This is the working tree build (`PYTHONPATH=${../src}` in `nix/testee-package.nix`).
- The Testee gate does not use that package as the runner. The host `testee` (a release, store path) is the runner. Its worker command uses its own `sys.executable` and `PYTHONPATH=<its own source>` (`src/testee/runner/cli.py:40-53`). Verified.
- The working tree only enters through (a) `packages = [ package ]`, (b) `tasks."testee:verify"` and (c) `enterTest` (`nix/testee.nix:64-67`). Verified.
- Checks run the tree under test with `PYTHONPATH=src` (`devenv.nix:30`). Verified.

So a release-pinned runner is the status quo for `testee verify --full`. The proposal would change it (host 0.6.0 would exec the working tree package).

### What would break if the runner were pinned to the last release tag

Verified by grep and read:

- **No test calls a `testee` binary.** `tests/*.py` never use `PATH` `testee`. They run `sys.executable -c` programs, `git`, `bash`, or monkeypatched `subprocess.run` (`test_runner_cli.py:60-63`). `test_runner_provenance.py:100` only checks a command list string.
- **Version consistency test is file-based.** `test_runner_shell_guard.py:88-92` compares `pyproject.toml`, `testee.__version__` (source via `PYTHONPATH=src`), `nix/testee-package.nix` and `flake.nix` text. It does not read the in-shell binary. A release pin does not change it.
- **No e2e check uses PATH `testee`.** `scripts/validate_v2.py` and `scripts/benchmark_v2.py` take an explicit `--profile` and run `<profile>/bin/testee`. Manual tools, not gates (`validate_v2.py:115,150,189`).
- **No Testee check or task needs the in-shell `testee` to be the tree.** `testee.checks` use `pkgs.ruff`, `pkgs.ty` and `testPython`.

What would change, not break:

1. `testee:verify` and `enterTest` (`devenv test`) would run the release against the tree. That is the intended bootstrap shape.
2. ADR `docs/adr/2026-10-09-testee-v2-implementation.md:16` says the devenv module must supply the same Testee version inside the shell as the host. A release pin differs from the tree after every version bump (inferred). The ADR sentence needs a rewrite.
3. `AGENTS.md:3` and `README.md:14-17` (install by `nix profile add .#testee`, which installs the tree build) stay true. `AGENTS.md:7-10` says to run `testee verify --full`. No line says the in-shell binary is the tree. Verified.
4. The new self-launch code is exercised only by unit tests, not by a gate run. A release runner cannot test its own launcher change (inferred).
5. A broken release would block the gate that must fix it. The escape is the host `nix profile` entry (inferred).
6. The pin needs network and a published tag at eval time (`builtins.getFlake ...ref=refs/tags/...`). The fleet already evaluates this form in every `devenv.nix` (verified), so it is not new.
7. Each release needs a second commit to bump the pin (inferred).

## 4. Fleet edits if the Testee pin stays at v0.5.1 and RepoMan goes to 0.14

Source: `03-fleet-usage.md` plus fresh greps of `P/*/devenv.nix` and `*.md` outside `.scratch`.

### 4a. Edits forced by the removal (2 repos)

| Repo | File:line | Why | Evidence |
|---|---|---|---|
| scopeman | `devenv.nix:79` | `base:test.after = ["repoman:test"]` points at a deleted task. The whole devenv shell fails to start. | verified (repro in 2) |
| repoman | `devenv.nix:182` | same line, same effect | verified |

No other file in any `P/*` repo (outside `.scratch`, `generated`, `golden`, `.copyroom_sim`) defines, depends on, or runs `repoman:test`, `repoman:test:ci`, `REPOMAN_TESTEE_HOST_BIN`, or `REPOMAN_TESTEE_VERSION` in code. `~/.config/devman` has none either. Verified.

### 4b. Behavior change with no edit needed (4 repos plus template)

Repos: agentman, inferference, linkman, mancore. Their `base:check` and `base:test` call bare `testee` (agentman `devenv.nix:73-74`, linkman `:61-62`, mancore `:63-64`, inferference `:136-140`).

- Old RepoMan prepends `~/.nix-profile/bin`. A bare `testee` in a task resolves to the host. Verified by repro: an `enterShell` PATH export wins in `devenv tasks run` and in `devenv shell` (`/tmp/tw-w3/pathprobe`).
- Without that line, a task resolves bare `testee` to the pinned package, because the Testee module adds `packages = [ package ]` (`testee/nix/testee.nix:64`). Verified by repro: the task's first PATH hit is the devenv package.
- With pin v0.5.1, that package is 0.5.1, the same as today's host. Behavior stays the same (inferred).
- If a repo later bumps the pin to 0.6.0, the in-shell `testee` is the pinned 0.6.0 package, not the host self-launcher. The 0.6.0 package must run correctly as that package. Unknown: not tested.
- The venv half of the PATH line stays in 0.14 (`09-repoman-minimal.md:24`). `lint-imports` in agentman (`devenv.nix:73`) keeps working.

### 4c. Stale docs only (no edit forced)

Header comments saying RepoMan wires `repoman:test` (13 `devenv.nix` files; `enterTest` named in 11 of them):

- agentman `:7`, argentic `:7`, flora `:7`, flora-core `:7-8`, flora-qc `:8`, inferference `:6`, linkman `:7`, llgym `:7`, poddantic `:8`, pyllij `:7`, scopeman `:7`, shellij `:7`, talkee `:7`.
- `enterTest` is named in all of them except flora-core (names it as a Testee module trait) and flora-qc (does not name it).
- Both claims (`repoman:test` task, RepoMan wiring `enterTest`) are false after 0.14. The `enterTest` claim has been false since 0.12.1.

Other stale text:

- mancore `devenv.nix:18-19`: "RepoMan reads its name for the doctor check". False after 0.14.
- 14 router skills at `P/<repo>/.agents/skills/repoman/SKILL.md` say "fix lint/format, or rerun failures": linkman, poddantic, talkee, flora-core, siteman, shellij, flora, eventic, argentic, loci-core, repoman, pytuin, pyllij, llgym. `repoman-sync` regenerates them; these are generated, machine-local views.
- scopeman `.loci/.../IMPLEMENTATION-GUIDE.md:361`: design doc.
- template-py: `template/devenv.nix.jinja:7`, `README.md` (the `REPOMAN_TESTEE_HOST_BIN` and `repoman:test` text), `copyroom.yml:28`. The `copyroom.yml` grep (forbids `"repoman:test`) stays valid after 0.14.
- repoman: `README.md:167-169,189`, `AGENTS.md:36`, `CHANGELOG.md` history.
- Central `~/.config/devman/skills/testee/SKILL.md` says "Testee 0.5.0" (already stale; unrelated to 0.14).

Repos without the `test` manager (eventic, forgelab, nix-*, template-nix repos, tyo3, loci.nvim, nix-secrets) need no edit. Repos that do not import RepoMan (fornix, loci-core, pytuin, testee, vendomat) need no edit. vendomat has its own `VENDOMAT_TESTEE_HOST_BIN` and does not use RepoMan's.

## Unknowns

- Whether a task resolves the host `testee` or the pinned one in each of the 4 repos after the change. Inferred from the probe; not run in those repos.
- Whether the 0.6.0 package handles being the pinned in-shell package (self-launch loop guard). Not tested.
- Whether any tool outside the code searched reads `commands.check` in `copyroom.project.yml`.
