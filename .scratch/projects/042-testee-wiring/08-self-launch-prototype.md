# 08 Self-launch prototype: Testee launches its own pin

Labels: `verified` (command output), `inferred`, `unknown`.
Host: devenv 2.4.0, Nix 2.34.7, NixOS, x86_64-linux. Work dir: `/tmp/tw-launch/` (logs kept in `logs/`).
Base: `git archive v0.5.1`. Patched build is labeled `0.5.1+selflaunch`. Scratch projects: `proj-pin051`, `proj-pin050`, `proj-patched`, `proj-loop`, `proj-nomodule`, `proj-broken`, `proj-badfail`, `proj-badoffline`, `proj-slow`, `proj-cold`.
Every run below calls Testee by absolute store path (`$HOST` = patched build, `$UNP` = unpatched 0.5.1), never bare `testee`.

## Rule violations and suspect results

1. `verified` My first dev-checkout test ran `uv run --offline testee ...` from the Testee source. That installed the patched source into the live repoman venv (`.devenv/state/venv`). The coordinator found it. I did not touch that venv again and did not uninstall.
2. Suspect result: test 4, first run only (the `uv run` line "not a Nix store build ..."). I redid test 4 with an isolated venv (`/tmp/tw-launch/venv`, `env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT`). The redo gives the same output. All other timings and results used absolute store paths, so the repoman venv `testee` did not affect them.
3. `verified` I ran `ssh -o StrictHostKeyChecking=no localhost true` to probe key login. It added `localhost` to `~/.ssh/known_hosts` ("Permanently added"). Login failed (`Permission denied (publickey)`). I did not set up ssh. The known_hosts line is a side effect outside `/tmp`; remove it if unwanted.

## Result in one paragraph

Self-launch works with unchanged 0.5.0 and 0.5.1 pins. The launcher needs one `devenv eval` call that returns `outPath`, `drvPath` and `manifestJson` together. When the pin equals the running build, the call replaces the manifest eval: zero extra evals. When the pin differs, the cost is about +0.3 s warm and about +2 s cold. The launcher runs before `.testee/` and before the lock. Runtime GC roots protect the pin during the run. Two real design points need a decision: the `report` command (section 4) and the dev-checkout line (section 3).

## 1. The patch

Three files. `testee-package.nix` exports `TESTEE_SELF_OUT=$out` from the wrapper script. `cli.py` gains `_eval_attrs`, `_launch`, and two message helpers. `main` calls `_launch` right after `project_root`.

Design choices in the patch:
- One `devenv eval` call with several attributes. `_eval_attrs` keeps results in a module cache. `_manifest` reads its value from that cache and pops it, so a second `_manifest` call (tests) evaluates again.
- Self path comes from `TESTEE_SELF_OUT`, set by the package wrapper. No wrapper means a dev checkout.
- Loop guard: `TESTEE_LAUNCHED` holds a colon list of launched targets. If the pin is already in the list, exit 2.
- Escape hatch: `TESTEE_NO_LAUNCH=1` skips everything, silently. `TESTEE_LAUNCH_VERBOSE=1` prints one line before the exec.
- `report`: launch is best effort. A launch failure prints one warning and `report` reads the saved report with the running version.
- `__version__` is `0.5.1+selflaunch` only so tests can tell builds apart. A real release bumps it. That breaks `tests/test_runner_shell_guard.py::test_version_is_one_value_everywhere` until `pyproject.toml` and the package name match (verified: the only failing test; 61 pass).

```diff
diff -u a/nix/testee-package.nix b/nix/testee-package.nix
--- a/nix/testee-package.nix
+++ b/nix/testee-package.nix
@@ -3,13 +3,14 @@
 let
   python = pkgs.python3.withPackages (ps: [ ps.pydantic ]);
 in
-pkgs.runCommand "testee-0.5.1" { } ''
+pkgs.runCommand "testee-0.5.1-selflaunch" { } ''
   mkdir -p "$out/bin"
-  cat > "$out/bin/testee" <<'EOF'
+  cat > "$out/bin/testee" <<EOF
 #!${pkgs.runtimeShell}
+export TESTEE_SELF_OUT=$out
 export PYTHONPATH=${../src}
-export PATH=${pkgs.lib.makeBinPath [ python pkgs.git ]}:$PATH
-exec ${python}/bin/python -m testee.runner.cli "$@"
+export PATH=${pkgs.lib.makeBinPath [ python pkgs.git ]}:\$PATH
+exec ${python}/bin/python -m testee.runner.cli "\$@"
 EOF
   chmod 755 "$out/bin/testee"
 ''
diff -u a/src/testee/__init__.py b/src/testee/__init__.py
--- a/src/testee/__init__.py
+++ b/src/testee/__init__.py
@@ -1,3 +1,3 @@
 """Testee 0.5 verification runner."""
 
-__version__ = "0.5.1"
+__version__ = "0.5.1+selflaunch"
diff -u a/src/testee/runner/cli.py b/src/testee/runner/cli.py
--- a/src/testee/runner/cli.py
+++ b/src/testee/runner/cli.py
@@ -5,6 +5,8 @@
 import argparse
 import hashlib
 import json
+import os
+import re
 import secrets
 import subprocess
 import sys
@@ -65,23 +67,100 @@
     raise CliError("No devenv.nix found above the current directory")
 
 
+_MODULE_FIX = "if the attribute is missing, import the Testee devenv module and set testee.package in devenv.nix"
+_PACKAGE_OUT = "testee.package.outPath"
+_PACKAGE_DRV = "testee.package.drvPath"
+_MANIFEST = "testee.manifestJson"
+_EVAL_CACHE: dict[str, object] = {}
+
+
+def _reason(stderr: str) -> str:
+    """Pick the line that names the cause out of long Nix or devenv output."""
+    lines = [line.strip() for line in re.sub(r"\x1b\[[0-9;]*m", "", stderr).splitlines() if line.strip()]
+    causes = [line for line in lines if "error:" in line or "Failed to get attribute" in line]
+    return (causes or lines or ["no output"])[-1][:300]
+
+
+def _build_reason(stderr: str) -> str:
+    """Summarize a failed `nix-store --realise`: first error, first reason, last two log lines."""
+    lines = [line.strip() for line in re.sub(r"\x1b\[[0-9;]*m", "", stderr).splitlines() if line.strip()]
+    errors = [line for line in lines if line.startswith("error:")][:1]
+    reasons = [line for line in lines if line.startswith("Reason:")][:1]
+    logs = [line for line in lines if line.startswith(">")][-2:]
+    return " | ".join([*errors, *reasons, *logs] or lines[-2:] or ["no output"])[:500]
+
+
+def _eval_attrs(root: Path, attrs: list[str], what: str) -> dict[str, object]:
+    """Evaluate devenv attributes in one `devenv eval` call. Reuse values from earlier calls."""
+    missing = [attr for attr in attrs if attr not in _EVAL_CACHE]
+    if missing:
+        try:
+            result = subprocess.run(
+                ["devenv", "eval", *missing],
+                cwd=root,
+                env=devenv_environment(),
+                capture_output=True,
+                text=True,
+                timeout=120,
+                check=False,
+            )
+        except (OSError, subprocess.TimeoutExpired) as exc:
+            raise CliError(f"Cannot evaluate {what} in {root}: {exc}; install devenv") from exc
+        if result.returncode:
+            raise CliError(
+                f"Cannot evaluate {what} in {root}: {_reason(result.stderr)}. "
+                f"Fix: run `devenv eval {missing[0]}` in {root} for the full error; {_MODULE_FIX}"
+            )
+        try:
+            _EVAL_CACHE.update(json.loads(result.stdout))
+        except ValueError as exc:
+            raise CliError(f"Cannot read `devenv eval {' '.join(missing)}` output in {root}: {exc}") from exc
+    return {attr: _EVAL_CACHE.get(attr) for attr in attrs}
+
+
+def _launch(root: Path, argv: list[str], *, with_manifest: bool) -> None:
+    """Re-exec into the Testee package that the project pins. Return when this process is that package."""
+    if os.environ.get("TESTEE_NO_LAUNCH"):
+        return
+    own = os.environ.get("TESTEE_SELF_OUT")
+    if not own:
+        print("testee: not a Nix store build; using this checkout, not the project's pin", file=sys.stderr)
+        return
+    attrs = [_PACKAGE_OUT, _PACKAGE_DRV, *([_MANIFEST] if with_manifest else [])]
+    values = _eval_attrs(root, attrs, f"{_PACKAGE_OUT} (the pinned Testee package)")
+    out, drv = values[_PACKAGE_OUT], values[_PACKAGE_DRV]
+    if not isinstance(out, str) or not isinstance(drv, str):
+        raise CliError(f"{_PACKAGE_OUT} in {root} is not a package; set testee.package in devenv.nix")
+    if out == own:
+        return
+    visited = [part for part in os.environ.get("TESTEE_LAUNCHED", "").split(":") if part]
+    if out in visited:
+        raise CliError(f"Launch loop in {root}: {out} was already launched ({' -> '.join(visited)}); fix {_PACKAGE_OUT}")
+    target = Path(out) / "bin" / "testee"
+    if not target.exists():
+        try:
+            built = subprocess.run(["nix-store", "--realise", drv], capture_output=True, text=True, check=False)
+        except OSError as exc:
+            raise CliError(f"Cannot realise {drv}: {exc}; install Nix") from exc
+        if built.returncode or not target.exists():
+            raise CliError(
+                f"Cannot build the Testee package {_PACKAGE_OUT} = {out} for {root}: "
+                f"{_build_reason(built.stderr)}. Fix: run `nix-store --realise {drv}`; "
+                f"if the build is not possible, change the testee.package pin in {root}/devenv.nix"
+            )
+    if os.environ.get("TESTEE_LAUNCH_VERBOSE"):
+        print(f"testee: launching the pinned package {out}", file=sys.stderr)
+    sys.stdout.flush()
+    sys.stderr.flush()
+    os.environ["TESTEE_LAUNCHED"] = ":".join([*visited, out])
+    os.execv(target, [str(target), *argv])
+
+
 def _manifest(root: Path) -> tuple[Manifest, str]:
+    values = _eval_attrs(root, [_MANIFEST], "Testee manifest")
+    _EVAL_CACHE.pop(_MANIFEST, None)  # use the prefetched value once
     try:
-        result = subprocess.run(
-            ["devenv", "eval", "testee.manifestJson"],
-            cwd=root,
-            env=devenv_environment(),
-            capture_output=True,
-            text=True,
-            timeout=120,
-            check=False,
-        )
-    except (OSError, subprocess.TimeoutExpired) as exc:
-        raise CliError(f"Cannot evaluate Testee manifest: {exc}") from exc
-    if result.returncode:
-        raise CliError(f"Cannot evaluate Testee manifest: {result.stderr.strip()[:400]}")
-    try:
-        raw = json.loads(result.stdout)["testee.manifestJson"]
+        raw = values[_MANIFEST]
         if not isinstance(raw, str):
             raise ValueError("manifestJson is not a string")
         manifest = Manifest.model_validate_json(raw)
@@ -238,6 +317,12 @@
     args = parser.parse_args(argv)
     try:
         root = project_root(args.root)
+        try:
+            _launch(root, sys.argv[1:] if argv is None else argv, with_manifest=args.command != "report")
+        except CliError as exc:
+            if args.command != "report":
+                raise
+            print(f"testee: no launch, reading the saved report with this version: {exc}", file=sys.stderr)
         if args.command == "verify":
             return _run(root, "full" if args.full else "quick", [])
         if args.command == "check":
```

## 2. Can one `devenv eval` return several attributes?

- `verified` `devenv eval testee.package.outPath testee.package.drvPath testee.manifestJson` returns one JSON object with all three keys.
- `verified` The eval cache keys on the attribute set, not on each attribute. After a `devenv.nix` edit, a new set costs a cold eval (1.4 to 2.7 s). The same set again costs 0.07 to 0.10 s.
- Warm timings (4 runs each): one attribute 0.07 to 0.10 s; three attributes 0.08 to 0.10 s; two package attributes 0.07 to 0.09 s. `verified`
- `verified` Call log with a `devenv` shim, patched host, project pins the patched build:
  `eval testee.package.outPath testee.package.drvPath testee.manifestJson`, `eval shell.drvPath`, `shell --clean ...`. That is the same count as the unpatched host (`eval testee.manifestJson`, `eval shell.drvPath`, `shell --clean ...`). Zero extra evals.
- `verified` Project pins 0.5.1: the host does the three-attribute eval, then the pin does `eval testee.manifestJson`, `eval shell.drvPath`, `shell`. That is one extra eval, a different attribute set, so it is cold the first time after any `devenv.nix` change.
- A patched pin evaluates the same three-attribute set, so after one host run its eval is warm. `inferred` (same code path, same set).

## 3. Test results

Test 1, host patched, project pins unpatched 0.5.1 and 0.5.0. `verified`
- `TESTEE_LAUNCH_VERBOSE=1 $HOST doctor` in `proj-pin051` printed `testee: launching the pinned package /nix/store/w4xf...-testee-0.5.1` then `Testee 0.5.1; root: ...`.
- Same in `proj-pin050`: `Testee 0.5.0; root: ...`. `verify --full` passed in both (exit 0, report written, containment strong).
- The pin's own source runs the worker: the shim log shows `PYTHONPATH=<pin src>` differs from the patched host's `src`. `verified`
- `$HOST --version` prints `testee 0.5.1+selflaunch` in every project. `--version` stops in argparse before any launch. An agent cannot learn the pinned version from `--version`; `doctor` prints it. `verified`

Test 2, project pins the patched build. `verified`
- No `launching` line. The call log has no extra eval (section 2). Warm `verify --full`: 1.08 to 1.42 s (5 runs; one 1.42 outlier). The unpatched host on the same fixture type: 1.07 to 1.15 s. `TESTEE_NO_LAUNCH=1` on a launch-needing project: 0.98 to 1.14 s. The difference is inside the noise.

Test 3, loop guard. `verified`
- `proj-loop` pins a forwarding package whose `bin/testee` is `exec <real patched>/bin/testee "$@"`. The real build sees a pin that is not itself, launches the forwarder, and the forwarder returns to the real build. Without a guard this loops forever (`inferred`; I did not run an unguarded build).
- With the guard: exit 2 after one hop: `Testee infrastructure error: Launch loop in /tmp/tw-launch/proj-loop: /nix/store/...-testee-fwd was already launched (/nix/store/...-testee-fwd); fix testee.package.outPath`.
- My first guard stored the launcher's own path, not the target. It did not stop this loop. I found it by running this case and fixed it to store the target.
- A leaked unrelated `TESTEE_LAUNCHED=/nix/store/zzz-other` does not block a launch (verified). A leaked value that equals the true target would raise a false loop error when the running build is not the target (`inferred`; rare).

Test 4, dev checkout. `verified` (isolated venv)
- `venv/bin/testee doctor` in `proj-pin051` prints `testee: not a Nix store build; using this checkout, not the project's pin` on stderr, then runs with the checkout code.
- `TESTEE_NO_LAUNCH=1` removes the line. Verdict: print the line, because a silent skip would hide a version mismatch from an agent. The cost is one stderr line on every dev run. `inferred` judgment.
- `main(argv)` is also called by tests with an explicit list. Those calls also print the line and do not launch (no `TESTEE_SELF_OUT`). The test suite still passes (61 of 62). `verified`

## 4. Failure messages (exit 2, no `.testee/` created)

All printed after the prefix `Testee infrastructure error:`. `verified` unless noted. Exit code 2 and no `.testee/` directory in every case (`ls -a` checked for nomodule, broken, badfail, badoffline).

a. Project without the Testee module (attribute missing):
`Cannot evaluate testee.package.outPath (the pinned Testee package) in /tmp/tw-launch/proj-nomodule: x Failed to get attribute 'devenv.config.testee.package.outPath': attribute `devenv.config.testee.package.outPath` not found. Fix: run `devenv eval testee.package.outPath` in /tmp/tw-launch/proj-nomodule for the full error; if the attribute is missing, import the Testee devenv module and set testee.package in devenv.nix`
Judgment: an agent knows the project, the attribute and the fix. Good.

b. Broken `devenv.nix` (syntax error):
`Cannot evaluate testee.package.outPath (the pinned Testee package) in /tmp/tw-launch/proj-broken: error: syntax error, unexpected end of file, expecting 'inherit'. Fix: run `devenv eval testee.package.outPath` in /tmp/tw-launch/proj-broken for the full error; if the attribute is missing, ...`
Judgment: the cause is visible. The "attribute is missing" clause is noise here. Raw devenv stderr was 26 KB with ANSI codes and the cause on the last line. The first version of the patch cut it at 400 characters and lost the cause; `_reason` fixes that (strip ANSI, pick the last `error:` line).

c. Realise fails (builder exits 1):
`Cannot build the Testee package testee.package.outPath = /nix/store/ra91...-testee-bad for /tmp/tw-launch/proj-badfail: error: Cannot build '/nix/store/8m86...-testee-bad.drv'. | Reason: builder failed with exit code 1. | > boom-from-builder. Fix: run `nix-store --realise /nix/store/8m86...-testee-bad.drv`; if the build is not possible, change the testee.package pin in /tmp/tw-launch/proj-badfail/devenv.nix`

d. Offline simulation (pin depends on a fixed-output fetch from `127.0.0.1:9`):
`... error: cannot download testee.tar from any mirror | Reason: builder failed with exit code 1. | > curl: (7) Failed to connect to 127.0.0.1 port 9 ... | > error: cannot download testee.tar from any mirror. Fix: run `nix-store --realise ...drv`; ...`
Judgment: the agent sees the network cause. The command took 11 s (curl retries). A real offline Testee pin is a flake input fetched by `devenv eval`, so it fails in step (b) instead. `inferred`, not tested (no network manipulation).

e. `devenv` not on PATH: `Cannot evaluate testee.package.outPath (...) in <root>: [Errno 2] No such file or directory: 'devenv'; install devenv`. `verified`

f. A bogus `.drv` path: not tested separately. `devenv eval` always returns a real drv, so a bogus one needs a hand-edited eval. Case (c) covers the same `nix-store --realise` failure path. `inferred`

Regression found: the unpatched host runs `testee report` with a broken `devenv.nix` (it never evaluates). A launcher that always evaluates would break `report` there. The patch makes launch best effort for `report`: it prints `testee: no launch, reading the saved report with this version: <reason>` and reads the saved report. `verified` (broken and nomodule projects show the warning, then `Testee has no state directory` because those projects never ran). Decision for the design: keep best effort, or skip launch for `report`.

## 5. Timing

Warm, 5 runs, `verify --full`, `proj-pin051` (seconds):
| Case | Times |
|---|---|
| unpatched host (no launch exists) | 1.07 1.15 1.13 1.07 1.12 |
| patched host exec into pin 0.5.1 | 1.44 1.42 1.44 1.50 1.32 |
| patched host, `TESTEE_NO_LAUNCH=1` | 0.98 1.06 1.11 1.14 0.99 |
| patched host, project pins patched build | 1.12 1.42 1.14 1.08 (first run 10.3 s: new fixture, cold eval) |
| `--version` unpatched / patched | 0.19 to 0.22 / 0.20 to 0.23 |
| `doctor` unpatched / patched exec | 0.47 to 0.51 / 0.78 to 0.86 |

`verified`. Warm exec cost: about +0.3 s. It is one extra Python start (about 0.2 s with the pydantic import) plus one extra warm eval (0.08 s). `inferred` split; a lazy import of pydantic before the launch point would cut most of the 0.2 s. `unknown`: not tried.

Cold (fresh package name each run so it was never built, `devenv.nix` changed, 2 runs each, `logs/cold.txt`):
- patched host, pin 0.5.1 never built: 13.0 s and 12.6 s.
- unpatched host, same setup: 10.8 s and 10.4 s.
- Cold overhead: about +2.2 s. `inferred` split: the launcher's own three-attribute eval is cold (it replaces nothing when the pin differs), the pin's `manifestJson` eval is cold again, and `nix-store --realise` takes about 0.9 s for a trivial package. I did not measure each part.
- I did not run `nix-store --delete` on any existing path. Fresh names gave the cold case without deleting anything.

Does the realise duplicate work that `devenv shell` does? `inferred`: no. The project module puts the pin in `packages`, so the inner `devenv shell --clean` build needs the same output. The launcher builds it first, and the shell then finds it. `verified` that the shell closure contains the pin: `nix-store -q --requisites .devenv/gc/shell | grep -c testee-0.5.1-slow` returned 1. The saving or cost split was not measured.

## 6. GC safety

- `verified` `nix-store --realise` printed `warning: you did not specify '--add-root'; the result might be removed by the garbage collector`. The launcher adds no root.
- `verified` During a run (`proj-slow`, a 25 s `sleep` check, pin 0.5.1 unpatched), `nix-store --gc --print-roots` listed the pin as a runtime root three times, all `/proc/<pid>/environ`. A second run named the variable: the pinned CLI process holds it in `TESTEE_LAUNCHED` (set by the launcher); the worker and the `sleep` check hold it in `PATH` (the devenv shell puts the pin's `bin` on PATH). A GC during the run keeps the pin. No real GC was run.
- `inferred` Only the `TESTEE_LAUNCHED` root is the launcher's own. It lasts while the pinned CLI process lives, which spans the whole run (the wrapper waits for the worker).
- `verified` After the shell started, `.devenv/gc/shell` also roots the pin, because `packages = [ package ]` puts it in the shell closure (`nix-store -q --roots <pin>` lists `.devenv/gc/shell`).
- Gap, `inferred`: between `nix-store --realise` and the exec (milliseconds) nothing roots the pin. A GC in that window makes the exec fail with a clear OS error; the next run realises again. A fix is `nix-store --realise --add-root <root>/.devenv/gc/testee-pin --indirect`. Not implemented.
- A first launch writes no gcroot until the shell is built. A later `nix-collect-garbage` between runs can remove the pin if `.devenv/gc/shell` is gone or stale. The next run rebuilds it (seconds, local). `inferred`

## 7. Entry points (test 8)

| Entry | Result |
|---|---|
| host shell, `$HOST verify --full` | works (sections 3, 5) |
| inside `devenv shell` of a project pinning 0.5.0: bare `testee` | resolves to the pin `/nix/store/pnsc...-testee-0.5.0/bin/testee` (devenv `packages` is first on PATH, ahead of the profile). Prints `Testee 0.5.0`. `verified` |
| same shell, call `$HOST doctor` | `$HOST` relaunches into the 0.5.0 pin (`launching the pinned package ...`). `verified` |
| inside `devenv shell` of the patched project: bare `testee` | patched pin, no re-exec, prints `Testee 0.5.1+selflaunch`. `verified` |
| `devenv tasks run --no-tui testee:verify` (pin 0.5.0 and patched) | passes, 1.03 s and 1.04 s. The task calls `<pin>/bin/testee` by store path, so no host and no launch. `verified` |
| `devenv test --no-tui` (pin 0.5.0 and patched) | passes, report written. Same reason. `verified` |
| stdin is a socket (Python `socketpair`) | host-to-pin 0.5.1 and host-to-pin 0.5.0 both pass, exit 0, launch line printed. `verified` |
| `ssh localhost` | not tested: keys do not work non-interactively (`Permission denied (publickey)`). I did not set up ssh. |
| no host testee at all | `devenv tasks run` and `devenv test` work with no host binary (rows above). `verified` |

`devenv test` and the task path never reach the launcher in practice. They run the pin directly. So the launcher matters only for host and PATH entry. `inferred`

## 8. Open points for the design

1. Module cache in the patch is module-level state. The patch pops the manifest entry after use to keep tests green. A cleaner form passes the prefetched values as arguments. `inferred`
2. `report` behavior (best effort vs skip). See section 4.
3. The first rollout still needs a manual host install of one patched build; every 0.5.x host lacks the launcher. `inferred` (prior memo 06 said the same).
4. Warm +0.3 s and cold +2 s on every call where host and pin differ. The cost is zero when they match.
5. Not tested: macOS, aarch64, real offline eval of a tag-pinned flake input, `--add-root`, a GC during the exec window, ssh.
6. `TESTEE_LAUNCHED` stays in the pinned CLI's environment. `devenv_environment()` strips `TESTEE_*` for `devenv` subprocesses, so the worker and the checks do not see it (`verified`: the worker and check roots came from `PATH`, not from a `TESTEE_*` variable). A nested host call from a check would therefore not inherit the loop list. `inferred`.
