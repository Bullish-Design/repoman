# 13 Stale environment: Testee as the pin of the tree it verifies

Labels: `verified` (command output seen), `inferred`, `unknown`.
Host: devenv 2.4.0, Nix 2.34.7, NixOS x86_64. Work dir: `/tmp/tw-w4b/` (logs in `logs/`). Every command ran through `env -i ... bash` (`clean.sh`).
I touched no file outside `/tmp/tw-w4b` except this note. I did not run `uv`, ssh, git or jj in a real repo.

## Setup

Scratch project `/tmp/tw-w4b/proj`. `setpin.sh PROJ FLAVOR` rewrites `devenv.nix` to pin one flavor:

| Flavor | Build | Notes |
|---|---|---|
| `a` | 0.6.0a | patched; launcher before argparse; exec |
| `b` | 0.6.0b | same as `a`, plus a new verb `frobnicate` |
| `r` | 0.6.0r | same as `a`, but refuses instead of exec |
| `u` | 0.5.1u | unpatched 0.5.1 source (no launcher) |

Every patched build also writes `runs/<id>/worker-id.txt` (version and file path) from the worker. This is my proof of which code ran the checks.
The launcher still lives in `cli.py`, so pydantic loads before it runs. It is not the stdlib-only module of DESIGN F1.

## 1. Stale env, patched A to patched B

Command: `devenv shell -- bash s1.sh` (`DEVENV_ROOT` set, `DIRENV_DIR` unset). The script runs inside the shell, edits `devenv.nix` from pin A to pin B, and does not re-enter.

- `verified` `command -v testee` before and after the edit: `/nix/store/n2f0...-testee-0.6.0a/bin/testee`. The env stays on A.
- `verified` Stale `testee doctor` prints `Testee 0.6.0b; ... code: /nix/store/6rbj...-b/testee/runner/cli.py`.
- `verified` Stale `testee verify --full` exits 0. The worker wrote `worker testee 0.6.0b /nix/store/6rbj...-b/testee/runner/worker.py`. B's worker ran the checks.
- `verified` Stale `testee frobnicate` (a verb only B defines) prints `frobnicate: handled by testee 0.6.0b code`.
- Timing, 5 interleaved warm runs, pin = B, absolute paths (`logs/timing-b.log`):

| Command | A binary (stale, exec to B) | B binary (current) | Added |
|---|---|---|---|
| `doctor` | 774 807 797 850 800, median 800 ms | 498 509 497 502 516, median 502 ms | +298 ms |
| `verify --full` | 1688 1642 1550 1502 1549, median 1550 ms | 1291 1175 1242 1173 1130, median 1175 ms | +375 ms |

- `verified` Cold, never-built pin, 2 runs (`logs/cold.log`): stale exec 7.16 s and 7.02 s. Unpatched 0.5.1 on the same kind of tree (silent stale run): 5.17 s and 5.28 s. Cold added about +1.9 s.
  The alternative, re-entering with `devenv shell -- testee doctor`, took 11.3 s and 11.2 s.
- `inferred` The warm +0.3 s is a second Python start with the pydantic import, plus a second warm eval. `python -c pass` took 23 to 37 ms and `import pydantic` took 68 to 119 ms. A stdlib-only launcher would cut part of it. `unknown`: not built.

## 2. Mixed pairs, unpatched and patched

| Stale env testee | New pin | Result | Label |
|---|---|---|---|
| unpatched 0.5.1 | patched A | Silent stale run. `doctor` prints `Testee 0.5.1`, `verify --full` exits 0. No warning. No `worker-id.txt` (A's worker did not run). | `verified` (`logs/s2-u-a.log`) |
| unpatched 0.5.1 | patched B | Same silent stale run. `testee frobnicate` exits 2: `invalid choice: 'frobnicate'`. | `verified` (`logs/s2-u-b.log`) |
| patched A | unpatched 0.5.1 | A execs into 0.5.1. `doctor` prints `Testee 0.5.1` (no `code:` field), `verify --full` exits 0, no `worker-id.txt`. | `verified` (`logs/s2-a-u.log`) |

- `verified` A stale unpatched env cannot tell it is stale. The fix needs the launcher in the env's testee, so a pre-launcher env stays exposed until the session restarts. The design cannot repair that.
- `inferred` The silent run is harmless only while the manifest format is the same. A pin that changes the manifest would fail in the stale 0.5.1 with the opaque Pydantic error (see 07).

## 3. No-op case: env is current

Pin = B, warm, 5 interleaved runs, median (`logs/timing-b.log`):

| Variant | `doctor` | `verify --full` |
|---|---|---|
| B with identity check (the patch) | 502 ms | 1175 ms |
| B with `TESTEE_NO_LAUNCH=1` | 501 ms | 1148 ms |
| unpatched 0.5.1 on the same tree | 500 ms | 1224 ms |

`verified` The identity check costs zero to 27 ms, inside the noise. The 3-attribute eval replaces the manifest eval, so there is no extra eval.

## 4. "Refuse instead of exec"

Build `r`. It runs the same eval and compares. On a mismatch it exits 2. `--version`, `-h` and `report` follow the same rules as the exec build.

Message, `verified` (`logs/s4.log`, exit 2, 0.34 s warm):

```
Testee infrastructure error: running testee-0.6.0r (/nix/store/8vwl...-testee-0.6.0r), but this tree pins testee-0.6.0b (/nix/store/jcc5...-testee-0.6.0b). Run `devenv shell -- testee ...` or reload the environment (direnv reload / re-enter devenv shell)
```

- `verified` Following the message works: `devenv shell -- testee doctor` prints `Testee 0.6.0b ...`, 6.4 s warm-ish (11.2 s cold, section 1).
- `verified` Refuse blocks `doctor`, `verify` and `frobnicate` alike. `report` prints one warning, then reads the saved report with the running version.
- Code size, `verified` by `diff` and function line counts: the exec `_launch` is 36 non-blank lines plus `_build_reason` (7). The refuse `_launch` is 20. Exec-only code is about 23 lines of about 120 added lines (`diff` of 121 vs 105 added lines against v0.5.1). Eval, scan, error and `report` plumbing stay in both.
  Refuse drops: realise, loop guard (`TESTEE_LAUNCHED`), `_build_reason`, the exec, and the GC window between realise and exec. It also drops the realise failure modes.
- Behaviour:

| Aspect | Exec | Refuse |
|---|---|---|
| Stale session | works, +0.3 s | every call fails until the agent prefixes `devenv shell --` |
| Recovery cost per call | none | one shell evaluation, 6 to 11 s |
| New pin has a new verb | reachable | refused |
| Silent verdict from the wrong code | no | no |
| Failure modes | loop, build failure, GC window | none new |
| Host install outside a shell | follows the pin | always refuses on mismatch |

Pick: exec. An agent cannot reload the env of a running session, so refuse turns every call into a 6 to 11 s retry. The added exec cost is 0.3 s, and only while stale. Refuse is safe but only moves the work to the agent. Add one rule to exec: print one stderr line on every exec (`testee: env runs X, tree pins Y; using Y`). That removes the "silent switch" worry. This is `inferred`; I did not build the line.
Keep the refuse code as the fallback for `TESTEE_SELF_OUT` unset or for a failed realise. `inferred`.

## 5. Launcher placement

- `verified` The prototype calls `_launch` inside `main()` after `parser.parse_args` (`/tmp/tw-launch/testee-src/src/testee/runner/cli.py`, the diff in note 08 §1). It does not run before argparse. The reviewer is right.
- `verified` With the prototype build on a tree that pins B: `testee frobnicate` exits 2 with `invalid choice: 'frobnicate'`.
- My copy (`srcs/a/.../cli.py`): `main` calls `_early(raw)` first. `_scan` reads only an exact `--root X` or `--root=X`, the first bare word (the command, to keep `report` best effort), and returns None for `-h`, `--help`, `--version` (the running build answers). Then it calls the old `_launch`.
- `verified` Stale A (no `frobnicate` in its parser) running `testee frobnicate` reaches B: `frobnicate: handled by testee 0.6.0b code`, exit 0. Same with `--root X` and `--root=X` from another cwd.
- `verified` Edge: `--ro X` (argparse abbreviation) from another cwd fails safely: `No devenv.nix found above the current directory`. `inferred`: from inside a different devenv tree it would launch that tree's pin. Set `allow_abbrev=False` (DESIGN item 4) and the gap closes.
- `verified` Side effect: `testee --version` and `-h` in a stale env show the stale version. `doctor` shows the real one.
- `verified` No args: argparse error, no launch.

## Results the design should take

1. Stale env with a launcher-capable testee: exec reaches the pin. Proven by `worker-id.txt` (section 1).
2. Stale env with unpatched 0.5.x: silent stale run. No design fix. State it in the 0.6.0 release notes.
3. Move the launcher before argparse (section 5). Freeze `--root` as the only option it reads.
4. Pick exec with a stderr notice. Cost: +0.3 s warm, +1.9 s cold, zero when current.
5. `--version` cannot show the pin. Document that `doctor` does.
