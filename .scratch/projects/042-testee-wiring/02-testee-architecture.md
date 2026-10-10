# Testee 0.5.1 architecture: wrapper, module, package, manifest

Snapshot: /tmp/tw-trunk/testee (main@origin 1c139ecb, v0.5.1). Paths below are relative to it.
History came from /home/andrew/Documents/Projects/testee (read-only).
Labels: verified = read in code or docs; inferred = reasoned from code; unknown = not shown by any source.

## 1. Pieces and who owns what

- Package `nix/testee-package.nix:6-14` builds `testee-0.5.1`. Its `bin/testee` sets `PYTHONPATH=${../src}`, puts a Python (with pydantic) and git on PATH, and runs `python -m testee.runner.cli`. verified
- The package holds the whole runner source (`../src`) and its own Python. It is the wrapper AND the worker code. verified
- `flake.nix:12-16` exports `devenvModules.default = ./nix/testee.nix` and `packages.<system>.testee`/`default`. Only x86_64-linux and aarch64-linux (`flake.nix:8`). verified
- Module `nix/testee.nix` declares `testee.package` (required, no default, :49), `testee.checks` (:50), `testee.services` (:51), `testee.manifestJson` (read-only string, :52). verified
- The module does NOT build or default the package. The consumer must set `testee.package` (README.md:26; devenv.nix:5 imports it from the same checkout). verified
- Module config (`nix/testee.nix:55-68`):
  - `manifestJson = builtins.toJSON { schema = "testee.manifest.v1"; sources = [ ]; checks; services; }` (:56-60). verified
  - `env.__NIXOS_SET_ENVIRONMENT_DONE = lib.mkDefault "1"` (:64). verified
  - `packages = [ package ]` (:65): the pinned Testee goes on PATH inside the shell. verified
  - `tasks."testee:verify".exec = "${package}/bin/testee verify --full"` (:66). verified
  - `enterTest = "${package}/bin/testee verify --full >&2"` (:67). verified
- Version value: one `__version__ = "0.5.1"` (`src/testee/__init__.py:3`). A test ties pyproject, the package name, and the flake description to it (`tests/test_runner_shell_guard.py:88-92`). The test does NOT cover the manifest, `nix/testee.nix`, or README. verified

## 2. Life cycle of one `testee verify --full` (host command)

Host side (outside any clean shell), `src/testee/runner/cli.py`:

1. `main` parses argv; `project_root` walks up from cwd (or `--root`) to the nearest `devenv.nix` (:55-65, :240). It never reads `DEVENV_ROOT`. verified (test: `tests/test_runner_cli.py:21`)
2. `_run` makes `.testee/` and `.testee/runs/`, refuses symlinks (:123-135), picks a run ID, and takes the lock (:138-142). verified
3. `RunLock` is a non-blocking `flock` on `.testee/lock` (`lock.py:29-48`). A second run gets `BusyError` and exit 2 (cli.py:248-250). The lock file holds `testee.lock.v1` JSON with run ID and pid (`lock.py:53-59`). verified
4. `_manifest` (cli.py:68-101) runs `devenv eval testee.manifestJson` from the project root. env = `devenv_environment()`, timeout 120 s. verified
5. `devenv_environment` strips every `DEVENV_*`, `TESTEE_*`, `GIT_*` variable (`provenance.py:61-63`). verified
6. `_manifest` parses stdout JSON, takes key `testee.manifestJson` (a string), validates it with `Manifest.model_validate_json` (strict, extra=forbid) (cli.py:84-89). verified
7. Extra manifest checks: at least one check; unique check IDs; unique service IDs; every `needs` names a service (cli.py:90-100). `_selection` needs at least one required check (:104-120). verified
8. The manifest hash is sha256 of the raw JSON string (cli.py:101). It goes to `run.json` as `manifest_sha256` (:165). verified
9. Provenance on the host (cli.py:148-149): `source_identity` hashes the work tree through a temporary Git index (`provenance.py:66-110`). `environment_identity` runs `devenv eval shell.drvPath` and records the `.drv` path plus the `devenv.lock` hash and its Git-ignore state (`provenance.py:126-140`). verified
10. Containment is chosen (PID namespace, then user scope, then subreaper, then groups) (`containment.py:58-84`). verified
11. The wrapper writes `run.json` (`testee.run.v1`) with the selected `CheckSpec`s and `ServiceSpec`s embedded (cli.py:155-177). verified
12. The wrapper launches `[containment prefix] devenv shell --clean -- env __NIXOS_SET_ENVIRONMENT_DONE=1 PYTHONPATH=<host src> <host sys.executable> -m testee.runner.worker STATE RUN_ID ROOT` (cli.py:40-52, 178-187; `provenance.py:179-186`; `lifecycle.py:94`). Popen: cwd=root, `start_new_session=True`, stdout/stderr to `worker.log`, env = `devenv_environment()` plus `TESTEE_RUN_TOKEN` (`lifecycle.py:98-112`). verified
13. After the worker exits, the host re-hashes the tree and the lock, writes `finish.json`, runs `Collector().collect`, then `seal` (`lifecycle.py:157-181`). The host prints a summary and returns `report.exit_code` (cli.py:189-190). verified

Inside the clean shell, `src/testee/runner/worker.py` and `supervisor.py`:

14. `worker.main` takes `STATE RUN_ID ROOT` from argv and calls `supervise` (`worker.py:11-15`). verified
15. The supervisor reads `run.json` from disk, checks `schema == testee.run.v1` and the run ID (`supervisor.py:51-53`), and takes the token from `run.json` (:62). verified
16. For each selected check it starts a new session, with env = shell env minus `TESTEE_*` and `PYTHONPATH`, plus `TESTEE_RUN_TOKEN`, `TESTEE_CHECK_TAG`, `TESTEE_RUN_DIR` (`supervisor.py:163-171`). It writes `<id>.start.json` and `<id>.result.json` and the logs. verified
17. The supervisor never reads `devenv`, the manifest, or `nix/testee.nix`. It reads only `run.json`. verified (grep: no `devenv` call in supervisor.py)

## 3. What crosses the host/shell boundary

| Channel | Content | Direction | Status |
|---|---|---|---|
| argv | `STATE RUN_ID ROOT` (cli.py:49-51) | host to worker | verified |
| env, set inside the shell by `env` | `__NIXOS_SET_ENVIRONMENT_DONE=1`, `PYTHONPATH=<host src>` (cli.py:44-45) | host to worker | verified |
| env on the `devenv` process | `TESTEE_RUN_TOKEN`, scope bus vars (`lifecycle.py:99-101`). `--clean` strips the token; the worker reads the token from `run.json`. | host to devenv | verified (token in env), inferred (stripped by `--clean`) |
| files | `run.json`, `finish.json`, `*.start.json`, `*.result.json`, logs, `worker.log`, `report.json`, `sealed.json`, `.testee/latest` symlink | both ways, all under `.testee/runs/<id>/` | verified |
| manifest JSON | crosses once: `devenv eval` stdout to host `Manifest`. It is copied into `run.json`. The worker never sees the raw manifest. | module to host | verified |
| interpreter | `sys.executable` of the HOST wrapper (a Nix store path) runs the worker inside the shell (cli.py:46) | host to shell | verified |
| code | `PYTHONPATH=Path(__file__).resolve().parents[2]` = the host package's `src` (cli.py:178) | host to shell | verified |
| signals | host forwards INT/TERM/HUP to the worker process group; kills after 10 s (`lifecycle.py:115-139`) | host to shell | verified |

Consequence: the worker, supervisor, and collector in the shell are the HOST package's code, not the pinned package's. verified (cli.py:46, 178)
The pinned `testee.package` is put on the shell PATH and used only by `testee:verify` and `enterTest`. Those entry points start a new wrapper from the pinned package (see section 7). verified

Checks lose `PYTHONPATH` on purpose: the first v2 gate leaked it into `ty` (`docs/research/testee-v2/2026-10-09-phase-5-dogfood.md`, last paragraph). verified

## 4. Manifest and report protocol; what the wrapper validates

Records are strict Pydantic models (`models.py:15-17`, `extra="forbid", strict=True`). verified
Schema tags (Literal): `testee.manifest.v1`, `testee.run.v1`, `testee.start.v1`, `testee.result.v1`, `testee.finish.v1`, `testee.report.v1` (`models.py:52,59,82,90,110,171`). Also untyped `testee.lock.v1`, `testee.seal.v1`, `testee.supervisor.v1`. verified
JSON Schemas are in `schema/testee-v2/{manifest,run,start,result,finish,report}.schema.json`. These are generated documentation; no code loads them. inferred (no `schema/` reference in `src`)

Manifest validation (host only, cli.py:83-100):
- `schema` must equal `testee.manifest.v1` (`models.py:52`). verified
- `extra=forbid` on every nested model: a field the host does not know is an error (`Invalid Testee manifest`, exit 2). verified
- A missing required field (`sources`, `checks`, `argv`, `ready`) is an error. Defaults exist for `services`, `cwd`, `timeout_s`, `required`, `profiles`, `needs`, `structured`. verified
- Check IDs match `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`. verified (`models.py:9`)

Version comparison: NONE. verified by grep over `src`, `schema`, `nix`, `flake.nix`, `pyproject.toml`, `devenv.nix` for version, `__version__`, schema, protocol:
- `__version__` is used only for `--version` (cli.py:229) and `doctor` output (cli.py:212). verified
- The manifest carries `schema`, `sources` (always `[]`), `checks`, `services`. No package version, no store path. verified (`nix/testee.nix:56-60`)
- `run.json` and `report.json` carry no Testee version and no package path. They carry `manifest_sha256`, `env_drv`, `source_tree_*`, `lock_sha256_*`. verified (`models.py:58-78, 170-196`)
- `schema` is the only coupling between module and wrapper. Skew shows up only as a strict-parse failure. A module that drops, adds, or renames a field fails; a module that changes the meaning of a field does not. inferred
- Skew case: pinned module and package newer than the host wrapper. The module is read by the host. If it keeps `testee.manifest.v1` with the same fields, the host runs with no warning, while `testee:verify` runs the pinned (newer) code. inferred
- `sources` is an unused slot. The decision memo planned "Manifest sources differ from disk (stale shell or edited module) -> 2" (memo, section 9). Nothing in `src` reads `manifest.sources`. verified by grep
- `doctor` prints the host version only; it does not print or compare the pinned version (cli.py:207-223). verified
- How the host wrapper sees the pinned package version: unknown. It could run `devenv eval testee.package` or `devenv shell -- testee --version`; neither is done. (The shell derivation path `env_drv` changes when the pinned package changes. inferred)

## 5. The shell guard and the 0.5.1 PATH change

- Name/value: `__NIXOS_SET_ENVIRONMENT_DONE=1` (`provenance.py:21-22`). verified
- Cause (comment `provenance.py:16-20`, commit 1c139ec message): NixOS bash sources `/etc/bashrc` and `/etc/profile` when it thinks sshd started it. Signs: stdin is a connected socket, or `SSH_CLIENT` is set. NixOS `set-environment` then replaces PATH. `devenv shell --clean` strips the marker that normally stops this. Result: `uv: command not found`, ruff-format exit 127, `infra_error`. verified (source text)
- 0.5.1 fix, three parts (commit 1c139ec; I read the code for each):
  1. Module sets `env.__NIXOS_SET_ENVIRONMENT_DONE = lib.mkDefault "1"` (`nix/testee.nix:61-64`). Covers `devenv test`/tasks. verified
  2. The worker command passes it via `env VAR=1 ...` inside the shell (cli.py:44). This covers a host run with an old module pin. The commit says "host runs need no re-pin". verified
  3. `testee doctor` runs `shell_path_probe`: bash with a socketpair stdin, env = marker PATH + guard. It exits 2 when PATH changes (`provenance.py:143-176`; cli.py:218-221). verified
- The guard is inert on non-NixOS hosts (`README.md:39`). verified (claim in README); not tested here: unknown
- The guard is NOT a "nested devenv" guard. It has nothing to do with detecting a devenv shell. verified

## 6. Running `testee` inside a devenv shell (nested)

- No code detects a surrounding devenv shell. Grep finds `DEVENV_` only in `devenv_environment()` (strip) and one test. verified
- Nested run: `project_root` uses cwd (not `DEVENV_ROOT`). `devenv eval` and the launch get a `DEVENV_*`-free env (provenance.py:63). The launch is still `devenv shell --clean`, so a second shell opens inside the first. inferred
- Which `testee` runs: inside the shell, `packages = [ package ]` puts the pinned package on PATH. Whether it shadows the profile `testee` depends on devenv's PATH order. Unknown (not tested in repo).
- So inside a devenv shell, `testee verify` normally runs the pinned wrapper, which then runs `devenv eval` and `devenv shell --clean` again. Host version = pinned version in that case. inferred
- Memo (section 8, line 187) calls `devenv shell -- testee verify` an optional entry point. A `kill -9` on that wrapper "leaves orphans until the next run kills them by tag" (the wrapper would be inside the shell). verified (memo text)
- Is there a test of nested `devenv shell` or `devenv test` calling `testee`? Phase 6 ran `devenv test --no-tui` and it passed (`2026-10-09-phase-6-validation.md:36`). That path runs `${package}/bin/testee verify --full` inside devenv's process, so it IS a nested launch. verified (docs claim), inferred (nesting)
- Cost of the nested route: unknown beyond the phase 6 timing table (~1.1 s warm).

## 7. Why the wrapper starts before devenv; why the module supplies the same version

ADR `docs/adr/2026-10-09-testee-v2-implementation.md:15-17` (commit 9ca4d9b):
> "Install Testee as a user-level Nix package so `testee` runs before it enters devenv. The devenv module must supply the same Testee version inside the shell. Test the package route before depending on it for the runner."

Memo `docs/research/testee-v2/2026-10-08-decision-memo.md` on branch `v2-synthesis` (commit 4e64b11; the ADR cites it at line 6):
- Line 102: "The wrapper is the only place that always runs after a failure, so it owns the exit code (A, C, H)."
- Line 78: the diagram labels it "testee (wrapper, outside the check environment)".
- Line 11: "A small stdlib Python program owns each run from start to exit code. Devenv supplies the pinned environment, the tools, and a generated manifest."
- Line 272 (open point 1): "The wrapper must run before the first `devenv shell`. Options: a user-level Nix package ..., or `nix run` from a pinned input. ... Recommended: user-level package, with the devenv module also providing the same version inside the shell for `devenv shell -- testee ...`."
- Line 94 role table: the devenv module owns "Pinned tools, environment, generated manifest, packaging of `testee`".
- Line 184: "It never reads `DEVENV_ROOT` or other ambient variables. Spike H touched the wrong repository because it did."

Reading: "same version" has one stated purpose: `devenv shell -- testee ...` and the module's own entry points should run the same code as the profile wrapper. verified (memo line 272). No document says how sameness is enforced. verified (none found). The enforcement today is by convention (README.md:20 "The package and `nix/testee.nix` both use Testee 0.5.1") and by the consumer importing the module and package from one source (README.md:35). verified

Other docs: README.md:9 "The wrapper starts before devenv. It records the working tree, evaluates the shell, takes a run lock, then launches one `devenv shell --clean`." AGENTS.md:3 "puts `testee` on `PATH` before devenv starts." Phase 4 note: "The same package is added by `nix/testee-v2.nix` inside devenv" (name is stale; file is now `nix/testee.nix`). verified

Host-wrapper reasons from the memo: the wrapper must outlive failures and interrupts (exit code 2 and sealed partial reports on SIGTERM); the container ladder needs the outer process because "Inside `devenv shell --clean` there is no bus, so only the outer wrapper can make a scope". verified (memo line 292, one-line table; phase 6 matrix rows for SIGTERM/SIGKILL)

History: 4e64b11 (memo), 9ca4d9b (ADR), b6115ee "Add v2 package module and CLI", 25c0ca2 "Migrate Testee to the v2 gate", 171b979/9b728a2 (validation, "default user Nix profile now contains the package from `v2/integration`"), 1c139ec (0.5.1). Tags v0.5.0, v0.5.1 exist. verified

## 8. Exit codes and report

- 0 = all selected checks passed; 1 = a check failed; 2 = incomplete run or environment/infra failure (README.md:5-7). verified
- Collector (`collector.py:251-262`): any error-severity run problem, any `infra_error` check, or any `not_run` check gives `status=infra_error, exit_code=2`. Else any `failed` gives `failed`/1. Else `passed`/0. verified
- `is_full_gate` needs mode full, selected == required, `source_stable`, no errors, no infra, no not_run (collector.py:263-271). A quick or named pass is labeled "PASS (PARTIAL ...)" (`render.py:15-16`). verified
- Check status values: `passed`, `failed`, `infra_error`, `not_run` (`models.py:12`). verified
- `failed` reasons: `exit_nonzero`, `case_failed`, `diagnostics_reported` (collector.py:340-344). verified
- `infra_error` reasons include: `start_missing`, `result_stale`, `log_missing`, `spawn_error`, `service_unavailable`, `interrupted`, `timeout`, `signal`, `exit_missing`, `structured_path_unsafe`, `structured_missing`, `structured_malformed`, `parser_crashed` (collector.py:289-338). verified
- Rules (ADR :22-31): exit 0 with error diagnostics = failed; malformed structured file = infra even when the command failed; leftovers = warning; source change = exit 2; weak containment may pass a full gate. verified
- Wrapper failures (`BusyError`, `CliError`, `ProvenanceError`, `OSError`, `ValueError`, `ValidationError`) print "Testee infrastructure error: ..." to stderr and return 2 with NO report (cli.py:248-250). Manifest failure, missing devenv, lock busy: no `report.json`. verified
- `report` returns the saved report's own `exit_code` (cli.py:204). argparse usage errors also exit 2. verified
- Report file: `.testee/runs/<run-id>/report.json`; `.testee/latest` symlink; protocol `testee.report.v1` (`models.py:170-196`; `collector.py:128-165`). No Testee version field. verified
- If the worker crashes or `run.json` is bad, the collector writes a skeleton report with `collector_crash` or `run_malformed` and exit 2 (collector.py:119-126, 180-190). verified
- A later run seals earlier unsealed runs and kills tagged leftovers (`lifecycle.py:33-62`). verified

## 9. How users are told to install and run

- README.md:11-18: `nix profile add .#testee` then `testee --version`. This installs the user-level wrapper. verified
- README.md:20-33: import `./nix/testee.nix` and set `testee.package = import ./nix/testee-package.nix { inherit pkgs; };` in `devenv.nix`. README.md:35: for another repo, "pin a Testee source and import its module and package from the same source". verified
- README.md:43: keep `devenv.lock` tracked; Git working tree and an explicit Git-ignored `.testee` are required. verified
- README.md:47-58: commands, `--root PATH` before the command, plus `devenv test --no-tui` and `devenv tasks run --no-tui testee:verify` as alternate entry points. verified
- README does NOT say how to update the profile when the project pin moves, nor what happens if versions differ. verified (absence)
- AGENTS.md:7-10: run `testee verify --full`; do not call pytest, ruff, ty separately; use `--no-tui` with every devenv command that may open the TUI; other commands via `devenv shell -- bash -c '...'`. "The Testee wrapper itself starts before devenv and owns its clean shell." verified

## 10. Gaps for the RepoMan `test` manager design

1. No host-vs-pinned version check anywhere. The host wrapper's code runs the worker in the shell; the pinned package's code runs only for `testee:verify` and `enterTest`. verified
2. Manifest and report carry no Testee version or store path, so a RepoMan manager cannot learn the pinned version from them. verified
3. The only skew detector is the strict Pydantic parse of `testee.manifest.v1` (extra=forbid). verified
4. A RepoMan check for sameness must compare externally: `testee --version` (host), `devenv eval testee.package` or the shell derivation (pinned). Neither command exists today. inferred
5. Nested behavior with the profile `testee` vs the shell `testee` (PATH order) is untested in the repo. unknown
6. A wrapper failure (exit 2 with no `report.json`) leaves `testee report` showing the previous run. inferred from cli.py:195-204 and :248-250
