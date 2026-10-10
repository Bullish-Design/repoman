# 06 Devil's advocate: RepoMan `test` manager and Testee

Labels: `verified` (code or command cited), `inferred`, `unknown`.
Sources: snapshots in `/tmp/tw-trunk/`. Experiments in `/tmp/da-exp/` (fixture `fx/`, prototype `bin/testee-boot`).
Host for experiments: devenv 2.4.0, Nix 2.34.7, Linux, host `testee 0.5.1`.

## Bottom line

B fixes the wrong thing. The host wrapper is not a front door. It is the runner.
The pinned package inside devenv does not run the checks when you call the host.
So any version gap changes behaviour, and B only polices the gap.
Remove the gap instead: the host launches the pinned runner (option C, built as F1 below).

## 1. Facts that drive everything

1. `verified` The host wrapper's own code runs the checks. `_worker_command` in `src/testee/runner/cli.py` uses `sys.executable` and `PYTHONPATH=<host source>` for the worker. The pinned package is not involved when you call the host.
2. `verified` The pinned package is used only by `enterTest` and the `testee:verify` task (`nix/testee.nix` lines `packages`, `tasks`, `enterTest`). So a project has two runners: the host one and the pinned one. They can differ.
3. `verified` Behaviour lives in host code, not only in the schema. The `__NIXOS_SET_ENVIRONMENT_DONE` guard is set in `cli.py`/`provenance.py` (`SHELL_GUARD_*`, `shell_path_probe`) and in the module. A patch release can change gate results with no schema change.
4. `verified` Testee keeps its version in three places: `pyproject.toml`, `src/testee/__init__.py`, and the derivation name `testee-0.5.1` in `nix/testee-package.nix`. RepoMan reads the third one: `lib.removePrefix "testee-" config.testee.package.name`. Experiment: I renamed the derivation to `testee-0.5.99`. The binary still printed `testee 0.5.1`. So RepoMan's "pinned version" and `--version` have two sources that can drift.
5. `verified` `Manifest` uses `extra="forbid", strict=True` (`models.py`). Schema literal is `testee.manifest.v1`.
6. `verified` `devenv.nix` of consumers pins Testee with `builtins.getFlake "git+https://...?ref=refs/tags/<tag>"` (template-py `template/devenv.nix.jinja`). The golden `devenv.yaml` has no Testee input. So `devenv.lock` does not pin Testee. The tag is the pin.
7. `verified` RepoMan's `enterShell` prepends `dirname $REPOMAN_TESTEE_HOST_BIN` (the whole `~/.nix-profile/bin`) to PATH (`modules/devenv.nix`). This shadows every devenv-provided tool that also exists in the user profile, not only `testee`.
8. `verified` copy and git do not have a minimum-version row. `registry.py` has `version_env` only for `test`. `checks.py` checks gitman by interface (`usage: gitman ... {work}`) and `jj >= 0.46.0`. copy has none. So "uniform with copy/git" means "no version policing". B would add a new concept, not remove one.
9. `verified` template-py tasks already call bare `testee` (`base:check`: `testee check ruff ruff-format ty`). The template does not use `REPOMAN_TESTEE_HOST_BIN`.

## 2. Attack on B

### 2.1 Exact versus compatible
- `inferred` Exact means each Testee patch bump forces `nix profile` work on every machine that opens a repo with the new pin. Fact 3 says exact is the only safe rule for the host-is-runner design. Compatible needs a compat token. The only token that exists is the schema literal, and fact 3 shows the schema does not track behaviour.
- So B has no good setting. Exact is a treadmill. Compatible hides real behaviour change. `inferred`.

### 2.2 Who updates the host
- `verified` `nix profile list` shows the host entry locked to `git+https://github.com/Bullish-Design/testee?ref=refs/tags/v0.5.1&rev=1c139ec...`.
- `inferred` `nix profile upgrade` does nothing for a tag-pinned entry. The user must remove and re-add with the new tag. The wrapper cannot print that command unless it knows the flake URL. The URL is in the project's `devenv.nix` string, not in `testee.package`. An "actionable message" needs a new `testee.source` option.
- `inferred` Agents and CI need a scripted update. No owner exists for that script today.

### 2.3 Several repos, different pins, one machine
- `inferred` Exact B makes the host a global lock. Repo A at 0.5.1 and repo B at 0.5.2 cannot both pass on one profile. Each switch needs a profile change. Agents work in parallel across repos, so this fails often.
- C removes this problem: each repo runs its own pin. `inferred`.

### 2.4 CI
- `inferred` CI needs the host install before any gate, plus a version match per job. With C, CI needs only the small launcher. With D, CI needs nothing but `devenv`.

### 2.5 Old wrapper and a new field
- `verified` Experiment: I added `testee_version = "0.5.99"` to the manifest in a copy of the module. Host `testee 0.5.1 doctor` failed with exit 2:
  `Invalid Testee manifest: 1 validation error for Manifest / testee_version / Extra inputs are not permitted [type=extra_forbidden ...]`.
  The failure is loud but not actionable. It also names no version.
- `verified` The same failure hit the pinned in-shell runner when I ran `devenv tasks run --no-tui testee:verify` (my fixture had the field in the module). Any manifest field addition breaks all older runners.
- So B's field must not go in the manifest. It needs a separate attribute. `inferred`.
- B cannot repair hosts that exist today. Every 0.5.x host lacks the handshake. The first deploy needs a manual update on every machine anyway. `inferred`.

### 2.6 Does the handshake run before the expensive work
- `verified` Order in `_run`/`_run_locked`: `_state(create=True)` makes `.testee/`, then `RunLock`, then `_manifest` (`devenv eval`), then `source_identity` (Git tree hash), then `environment_identity` (second `devenv eval`), then the shell launch.
- A check inside `_manifest` runs after the state directory and lock file exist, but before the Git hash and the shell. The cost is small. The side effect (an empty `.testee/` and a lock file in a repo that never ran) is minor. `verified`.
- `verified` `report` never calls `_manifest`. It would skip the handshake.

### 2.7 Does the wrapper need its own logic at all
- No. `verified` experiment below.

## 3. What "starts before devenv" really requires

- `verified` The ADR gives one sentence: "Install Testee as a user-level Nix package so `testee` runs before it enters devenv." It gives no reason for a profile install. The cited memo (`v2-synthesis:.../decision-memo.md`) is not in the snapshot. Reason: `unknown`.
- `verified` README/phase 3: the wrapper must (a) take the run lock, (b) hash the source tree and `devenv eval shell.drvPath` before the shell, (c) own containment and signals, (d) bring its own Python (non-Python projects). All of these need a process above the checked shell. None needs the binary to come from the user profile.
- `verified` The research notes (phase 4, 5, 6) record that `devenv test --no-tui` and `devenv tasks run --no-tui testee:verify` also passed the full gate with the pinned package. Phase 6 ran 100 pty hangups with `devenv test --no-tui`. I re-ran the task path in my fixture. It works (see 4.4).
- So the real requirement is: the supervisor is not inside the clean shell it launches. `inferred`.
- Host part can be tiny: `verified` prototype `/tmp/da-exp/bin/testee-boot` (about 12 lines of Bash):
  1. Find the nearest `devenv.nix`.
  2. `devenv eval testee.package.outPath testee.package.drvPath`.
  3. If `$out/bin/testee` is missing, run `nix-store --realise <drvPath>`.
  4. `exec $out/bin/testee "$@"`.
- `verified` Eval alone does not build the package. `outPath` is absent after eval; `nix-store --realise <outPath>` fails ("no substituter can build it"). You must realise the `.drv`.
- `verified` That works with the unchanged Testee 0.5.1 code and module. I ran `testee-boot --version` (prints `testee 0.5.1`), then `testee-boot verify` end to end in the fixture. Checks ran in a clean shell and a report was written. The pinned side needs no change.

## 4. Measurements (warm, same fixture, noisy; three runs each)

| Entry | Wall time (s) |
|---|---|
| host `testee verify` | 3.3 (first), 1.9, 1.2 |
| `testee-boot verify` | 1.24, 1.44, 1.30 |
| `devenv tasks run --no-tui testee:verify` | 1.90, 1.87, 1.83 |
| `testee-boot --version` only | 0.40 to 0.44 |

- `verified` The launcher costs roughly 0.1 to 0.4 s over the host. The task path (D) costs roughly 0.6 s more, because devenv builds the full outer shell first.
- `unknown` Behaviour on macOS, on a cold Nix cache, and offline when the tag's fetch TTL expires.

### 4.4 D works mechanically
- `verified` `devenv tasks run --no-tui testee:verify` ran the nested `devenv shell --clean` and wrote a report.
- `inferred` Costs of D: a broken outer shell (package fails to build, `enterShell` error) stops before Testee can seal a report. AGENTS.md demands `--no-tui` on every devenv call; a missing flag opens a full-screen UI. D is not uniform with copy/git, which run from PATH.

## 5. Options nobody listed

Judged on: fewer concepts, one owner per invariant, loud actionable failure, uniformity with copy/git.

- **F1. Re-exec into the pinned store path after eval** (the concrete form of C). Launcher evaluates `testee.package`, realises it, execs it. Concepts: one (the attribute `testee.package`). Owner of "runner equals pin": the launcher, by construction. Failure: eval or build errors, each printable by the launcher. Uniform: yes, RepoMan runs bare `testee` from PATH.
- **F2. `nix run` of the flake input from `devenv.lock`.** Fails fact 6: consumers have no locked Testee input. It would need a template change (input in `devenv.yaml`) and a second pin mechanism. More concepts than F1. `verified` for the blocker, `inferred` for the cost.
- **F3. Wrapper as a devenv task with a flag.** This is D. `testee:verify` exists. It needs one flag per profile (quick/full) and a full outer shell build. Worse failure isolation. See 4.4.
- **F4. Drop the `test` manager.** RepoMan would lose the `verify` phase of the spine (`SPINE` in `registry.py` reads manager key `test`). The router would need a special case. Not recommended. `inferred`.
- **F4b. Keep the registry row, delete both `repoman:test*` tasks.** The tasks only alias Testee. The Testee module can define `testee:quick` next to `testee:verify`. One fewer wrapper layer. `inferred`. Check first: does any consumer call `repoman:test`? `unknown` (the template uses `base:*`, not `repoman:test`).
- **F5. Template and RepoMan call bare `testee`.** Already true in template-py (fact 9). It is the RepoMan-side half of F1. It deletes `REPOMAN_TESTEE_HOST_BIN`, `binary_env`, `version_env`, the PATH rewrite, the shadow check, and the `version:test` row. `verified` list of mechanisms to delete: `modules/managers/testee.nix`, `modules/devenv.nix`, `registry.py`, `checks.py` (`_installed_check`, `_version_check`).
- **F6. Pin through the lock.** Move the Testee input into `devenv.yaml` so `devenv.lock` pins it by revision. A tag in `getFlake` is mutable. `inferred` this also removes the tag-TTL network risk. Separate from the launcher decision; do it later.
- **E. Put the RepoMan integration in Testee's module.** `inferred` it inverts the dependency: Testee would know RepoMan task names. RepoMan's only real need is a registry row. Reject.

## 6. Risks of F1 (honest list)

1. `inferred` The launcher is new code at a trust and eval boundary. It runs `devenv eval` on every call. A broken project eval blocks even `testee doctor`. (The existing wrapper already evals, so the blocker is not new.)
2. `inferred` Two binaries named `testee` (launcher and runner). Needs a loop guard (an env var, or compare `outPath` with own prefix) and a clear `--version` outside a project.
3. `verified` The first rollout still needs a manual host update, because 0.5.x hosts are full runners and have no re-exec. After that, no host update is needed unless the launcher itself changes.
4. `inferred` `nix-store --realise` makes no GC root. A GC can remove the output. The next call realises it again. Cost: seconds, not failure.
5. `inferred` Projects without the Testee module give `attribute not found`. The launcher must turn that into "import the Testee module".

## 7. Ranking

1. **F1 + F5** (C built by eval, RepoMan calls bare `testee`). Runner equals pin by construction. RepoMan drops all policing. Works with unchanged Testee 0.5.1 pins.
2. **B, reworked**: compatible semantics, new attribute (not a manifest field), module-provided source URL. Still two runners, still a host treadmill.
3. **D** (no host; task or `devenv test`). Fewest installs. Slower, weaker failure isolation, TUI hazard, not uniform.
4. **A** (keep and tidy). Works today. Five mechanisms with split ownership. Silent skew possible if `REPOMAN_TESTEE_VERSION` is unset or the name drifts from `__version__`.
5. **F4b** (delete `repoman:test*` only). Small win; combine with F1.
6. **E** (move integration into Testee). Wrong dependency direction.
7. **F2** (`nix run` from lock). Needs a template change and a second pin mechanism.
8. **F4** (drop the `test` manager). Breaks the lifecycle spine.

## 8. Recommendation

Build F1 with F5. Ship a stable launcher as the host `testee`. It evals `testee.package`, realises, and execs. Delete RepoMan's host-binary, version, shadow, and PATH-rewrite code. Add F6 later.

Biggest risk: the one-time rollout. Every existing host holds a full 0.5.x runner with no re-exec. Each machine needs one manual install of the launcher. Until then, A's skew stays.

## 9. Open questions

- `unknown` Why the ADR requires a profile install. Read the missing memo `2026-10-08-decision-memo.md` before the final decision.
- `unknown` Does any consumer call `repoman:test` or `repoman:test:ci`?
- `unknown` Cold-cache, offline, and macOS behaviour of the launcher.
- `unknown` My fixture reported `source_changed` on some runs from caches in the working tree. I did not diagnose it. It is a fixture issue until shown otherwise.
