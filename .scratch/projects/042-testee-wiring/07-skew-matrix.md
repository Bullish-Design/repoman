# 07 Skew matrix: host wrapper versus project pin

Labels: `verified` = command output in a log. `inferred` = reasoned from code or output. `unknown` = not measured.
Logs: `/tmp/tw-skew/logs/<cell>.log` (command, exit code, first 20 lines, report summary). Scripts: `/tmp/tw-skew/scripts`.
Setup: NixOS host, devenv 2.4.0. Hosts built with `nix build "path:/tmp/tw-skew/src-<tag>#testee"` from `git archive` sources of v0.5.0 and v0.5.1. Out-links `/tmp/tw-skew/host-v0.5.x` were removed at cleanup; the store paths remain until garbage collection.
Projects: `/tmp/tw-skew/proj-*`. Each imports the module and package from the matching extracted source by absolute path. Checks: `ok` = `true`, `bad` = `false`, `haspath` = `bash -c 'command -v hello'` (`hello` comes from the devenv `packages`).
"Pin" means module and package from the same tag. "Socket stdin" means a Python `socketpair` end as stdin (what an agent harness or `ssh host testee` gives).
Every host run used `cd <project> && <host>/bin/testee ...` (no `--root`).

## Result table

| # | Host | Project pin | Command | Exit | report.json | Result |
|---|---|---|---|---|---|---|
| 1a | 0.5.0 | 0.5.1 | `check ok bad haspath` | 1 | written, `failed` | Works. Only `bad` fails (expected). verified |
| 1b | 0.5.0 | 0.5.1 | same, socket stdin | 1 | written, `failed` | `haspath` passes. The 0.5.1 module fixes the 0.5.0 host. verified |
| 1c | 0.5.0 | 0.5.1 | `doctor` | 0 | none (not a run) | Prints `Testee 0.5.0`. No "shell guard" line. verified |
| 2a | 0.5.1 | 0.5.0 | `check ok bad haspath` | 1 | written, `failed` | Works. verified |
| 2b | 0.5.1 | 0.5.0 | same, socket stdin | 1 | written, `failed` | `haspath` passes. The 0.5.1 host fixes the 0.5.0 module. verified |
| 2c | 0.5.1 | 0.5.0 | `doctor` | 0 | none | Prints `Testee 0.5.1` and `shell guard: ok`. The host version shows, not the pin. verified |
| 3 | 0.5.1 | 0.4.0 | `check ok`, `doctor` | 2 | none | `Testee infrastructure error: Cannot evaluate Testee manifest: ... attribute 'devenv.config.testee.manifestJson' not found`. verified |
| 4a | 0.5.1 | 0.5.1 module + 1 extra manifest field | `check ok` | 2 | none | `Invalid Testee manifest: 1 validation error for Manifest / testee_version / Extra inputs are not permitted`. verified |
| 4b | 0.5.1 | same, pinned in-shell runner | `devenv tasks run --no-tui testee:verify` | 1 | none | Same message. devenv maps exit 2 to 1. verified |
| 4c | 0.5.1 | 0.5.1 module + extra option outside the manifest | `check ok` | 0 | written, `passed` | Host ignores the extra option. `devenv eval testee.requiredHostVersion` returns it. verified |
| 5a | none | any | RepoMan `repoman:test` command, fake `HOME`, plain shell | 127 | none | `bash: line 1: /tmp/tw-skew/fakehome/.nix-profile/bin/testee: No such file or directory`. verified |
| 5b | none | any | same string as `devenv tasks run --no-tui repoman:test` | 1 | none | `.../repoman-test: line 3: .../.nix-profile/bin/testee: No such file or directory`, then `Some tasks failed`. verified |
| 5c | `REPOMAN_TESTEE_HOST_BIN` set to a missing path | any | same string | 127 | none | `bash: line 1: <path>: No such file or directory`. verified |
| 5d | 0.5.0 via `REPOMAN_TESTEE_HOST_BIN` | 0.5.1 | `devenv tasks run --no-tui repoman:test` | 0 | not checked | Silent skew. The task never compares versions. verified |
| 6a | 0.5.0 | 0.5.0 | `verify --full`, socket stdin, `haspath` required | 1 | written, `failed` | `FAIL haspath [exit_nonzero]`. The only bad pairing. verified |
| 6b | 0.5.1 | 0.5.0 | same | 0 | written, `passed` | Pass. verified |
| 6c | 0.5.0 | 0.5.1 | same | 0 | written, `passed` | Pass. verified |
| 6d | pinned 0.5.0 runner (`devenv tasks run --no-tui testee:verify`) | 0.5.0 | same project as 6b | 1 | written, `failed` | Fails on the same project and stdin that 6b passes. verified |
| 6e | pinned 0.5.1 runner | 0.5.1 | same | 0 | written, `passed` | Pass. verified |

Log names: `cell1-*`, `cell2-*`, `cell3-*`, `cell4-*`, `cell4b-*`, `cell5-install-skew`, `c6-*`, `base-*` (same-version baselines). The baseline `base-050-050-sock` shows the 0.5.0 bug: `haspath` fails with `exit_nonzero` under socket stdin. `base-051-051-sock` passes.

## Findings

1. Schema skew fails loud, early, and without a report. `verified` (3, 4a, 4b). The message names the field but not the versions. It does not say "host too old".
2. A failed manifest still leaves `.testee/lock` and `.testee/runs/` behind. `verified` (cell 3 log, `ls` output; cell 4a log, same).
3. The 0.4.0 module evaluates, but it has no `testee.package` and no `manifestJson`. A 0.4.0 pin gives exit 2 on any 0.5.x host. `verified`. The 0.4.0 CLI is a different tool. Skew with 0.4.0 is a migration, not a patch skew.
4. 0.5.0 versus 0.5.1 patch skew changes nothing today, for the one real behaviour change. `verified` (1b, 2b, 6b, 6c). The `__NIXOS_SET_ENVIRONMENT_DONE` marker is set twice: by the 0.5.1 module (devenv `env`) and by the 0.5.1 host (`_worker_command`). Either side is enough. Only 0.5.0 on both sides breaks (6a).
5. The two runners disagree on one project. `verified` (6b versus 6d). Project pin 0.5.0, socket stdin: host 0.5.1 passes the full gate, and the pinned in-shell 0.5.0 runner (`testee:verify`, `devenv test`) fails it. The gate result depends on the entry point. This is the cost of "the host is the runner".
6. 0.5.0 on the host with a 0.5.1 pin is a lucky pairing. `inferred`. The fix happens to live in the module. A future change that lives only in host code would not reach a stale host. Only a stale host plus a stale pin could not be told apart from a good run.
7. No saved file records the Testee version. `verified`: `run.json` and `report.json` keys hold no version field; grep for `0.5.0` and `0.5.1` in a run directory finds nothing. A report cannot show which runner made it. `testee doctor` prints the host version only.
8. RepoMan's `repoman:test` task does not compare versions. `verified` (5d). RepoMan trunk has a version check in `checks.py` (`_version_check`), but only in the `doctor` path. Run directly: host 0.5.0 against `REPOMAN_TESTEE_VERSION=0.5.1` gives `level='fail'`; host 0.5.1 gives `ok`; a missing binary gives `fail` (`logs/cell5-doctor-version-check.log`). The check is exact string equality, so a patch bump fails it.
9. The install-location message is the shell's `No such file or directory` with the full path. `verified` (5a, 5b). It does not say "install Testee", does not name the pin, and the task path adds no hint. In the task path the exit is 1, in a plain shell 127.
10. A new manifest field is not a safe place for a handshake. `verified` (4a). A separate module option is safe for old hosts (4c). `inferred`: only a new host would read it; no host reads it today.
11. `REPOMAN_TESTEE_VERSION` in this session's shell reads `0.5.1`, from the repoman devenv. My shell also had `REPOMAN_TESTEE_HOST_BIN` set, so cell 5 unset it first. `verified` (env listing).

## Not measured

- Non-NixOS hosts. The 0.5.1 fix is inert there, so skew would not show. `unknown`.
- Host 0.5.0 against a pin that adds a required new manifest field the host lacks (missing field rather than extra field). `unknown`. Pydantic would report a missing field; the wording was not checked.
- A real RepoMan-generated devenv. Cell 5 used a scratch task with the same exec string as `modules/managers/testee.nix`. `verified` for the string; `inferred` for the rest.
- Cold Nix cache and offline behaviour. `unknown`.
