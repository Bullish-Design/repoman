# 15 RepoMan planes: `plane` field on `Manager`

Labels: `verified` = I ran it and saw the output. `inferred` = my reasoning. `unknown` = not tested.
Work trees (all under `/tmp`, none in a real repo):

- `/tmp/tw-w4d/repoman` = variant A (draft `/tmp/tw-rm` + `plane` + fix text).
- `/tmp/tw-w4d/repoman-b` = variant B (A + environment provenance check).
- `/tmp/tw-w4d/c1` = `tests/consumer-example` with the Testee module. `c2` = the same without it. Both import the copy's `modules/`.
- Every command ran through `env -i HOME USER TERM=dumb PATH=... NIX_PATH` (script `/tmp/tw-w4d-bin/s` and `run`).
  The `PATH` held only the system profile and the per-user profile, plus `~/.nix-profile/bin` where a row says "host profile on PATH".
  The venv lived under each copy's own `.devenv/state/venv`.

## Summary

1. A `plane` field is small: +59/-2 lines on top of the draft (src +24/-2, tests +35). Against trunk the whole draft is +129/-162 lines in 10 files. (verified, `diff -ruN`, blank lines counted)
2. Variant A (fix text only) is nearly cosmetic. When the host profile also has `testee`, a repo whose environment lacks Testee still gets `OK installed:test`. (verified, c2 below)
3. Variant B adds one helper (+22 lines: src +9, tests +13). A project-plane tool must come from `$DEVENV_PROFILE/bin` or the venv bin. It then fails correctly with the project fix text. (verified, c2 below)
4. The "doctor outside the environment" question is moot. `repoman` is not on any host PATH, and doctor refuses to run rows outside the shell (exit 2). (verified)
5. A fake old `testee` earlier on `PATH` does not win inside the environment. devenv puts its own package first. (verified)
6. Tests: 134 pass (A), 135 pass (B), inside and outside the devenv shell. `ruff check`, `ruff format --check`, `ty check src` clean. (verified)
7. The router needs no per-plane text. One clause helps: "From outside the shell, run `devenv shell -- <command>`." (proposal; the command was verified)

## 1. The change

Variant A, delta on the draft (`/tmp/tw-rm` -> `/tmp/tw-w4d/repoman`), +59/-2:

- `registry.py`: field `plane: str = "host"`, validated to `host|project`. `test` sets `plane="project"`. `copy` and `git` use the default. (+8)
- `checks.py`: `_fix_hint(manager)` returns a plane text. The `installed:` and `version:` fail rows append it. (+16/-2)
- Tests: 2 registry tests (+13), 3 check tests (+22).

Fix texts (verified in rows below):

- host: `install it with `nix profile add` in the host profile`
- project: `import the testee devenv module in devenv.nix, then re-enter `devenv shell``

I did not use "add the Testee input to devenv.yaml". The fleet pins Testee with `builtins.getFlake` inside `devenv.nix`, not as a `devenv.yaml` input. (verified: `devenv.nix:8`, `tests/consumer-example/devenv.nix:7`)

Variant B, delta on A, +22/-0:

```diff
--- a/src/repoman/checks.py
+++ b/src/repoman/checks.py
@@ -126,6 +126,13 @@
     return None
 
 
+def _environment_binary(command: str) -> Path | None:
+    """``command`` as the repo's devenv environment supplies it, ignoring the host profile."""
+
+    dirs = [Path(os.environ["DEVENV_PROFILE"]) / "bin", consumer_venv_bin()]
+    return next((d / command for d in dirs if d and (d / command).exists()), None)
+
+
 def manager_binary(manager: Manager) -> Path | None:
     """The absolute path ``manager`` runs from, if knowable.
 
@@ -134,6 +141,8 @@
     """
 
     if manager.install == "path":
+        if manager.plane == "project" and os.environ.get("DEVENV_PROFILE"):
+            return _environment_binary(manager.command)
         found = shutil.which(manager.command)
         return Path(found) if found else None
     bin_dir = consumer_venv_bin()
--- a/tests/conftest.py
+++ b/tests/conftest.py
@@ -16,6 +16,7 @@
     "REPOMAN_PROVISIONED_DOC",
     "DEVENV_ROOT",
     "DEVENV_STATE",
+    "DEVENV_PROFILE",
     "XDG_DATA_HOME",
     "UV_FIND_LINKS",
     "VIRTUAL_ENV",
--- a/tests/test_checks.py
+++ b/tests/test_checks.py
@@ -266,3 +266,15 @@
     testee.chmod(0o755)
     detail = _names(run_self_check([REGISTRY["test"]], ".", ".claude/skills"))["version:test"].detail
     assert "devenv.nix" in detail
+
+
+def test_project_tool_on_the_host_profile_does_not_count(host, tmp_path, monkeypatch):
+    # The host profile has testee, but the repo's environment does not supply it.
+    profile = tmp_path / "profile"
+    (profile / "bin").mkdir(parents=True)
+    monkeypatch.setenv("DEVENV_PROFILE", str(profile))
+    names = _names(run_self_check([REGISTRY["test"]], ".", ".claude/skills"))
+    assert names["installed:test"].level == "fail" and "devenv.nix" in names["installed:test"].detail
+    (profile / "bin" / "testee").write_text('#!/bin/sh\nprintf "testee 0.5.1\\n"\n')
+    (profile / "bin" / "testee").chmod(0o755)
+    assert _names(run_self_check([REGISTRY["test"]], ".", ".claude/skills"))["installed:test"].level == "ok"
```

B reads `DEVENV_PROFILE` and the venv bin only for `plane == "project"`. If `DEVENV_PROFILE` is unset, it falls back to `shutil.which`. The test `conftest.py` must clear `DEVENV_PROFILE`, or seven tests fail inside a devenv shell. (verified: 7 failed before the `conftest.py` line, 0 after)

Open point: the B message for a missing project tool still says `testee not on PATH`. A better text is "not supplied by the environment". (inferred; not changed)

## 2. Doctor outside the environment (task 2)

Decision: do nothing. The question is moot. (verified)

```
$ which repoman                      (scrubbed PATH, host profile on PATH)
which: no repoman in (...)           exit 1; grep -c repoman over both profile bin dirs = 0
$ cd <repo> && .devenv/state/venv/bin/repoman doctor        (outside the shell)
repoman: managed repo found, but not inside its devenv shell
...
    cd /tmp/tw-w4d/repoman && devenv shell -- repoman doctor
exit=2
$ ... doctor --json      -> {"context": {"ok": false, "kind": "managed-repo-bare-shell", ...}, "checks": [], "exit": 2}
$ cd /tmp && venv/bin/repoman doctor   -> "repoman: not inside a repoman-managed repo", exit=2
```

- `repoman` lives only in the repo venv. (verified)
- `detect_context` gates `doctor` on `REPOMAN_MANAGERS`, which only the devenv shell exports. Outside it, doctor prints one context message and exits 2 before any row. (verified; `cli.py:doctor`)
- So doctor never sees "testee not on PATH because we are outside the environment". Neither `skip`, `info` nor a `devenv shell -- testee --version` probe is needed. The levels are only `ok|warn|fail` today. (verified: `checks.py:_LEVELS`)
- One text nit (inferred): the bare-shell message says "the manager commands are only on PATH inside the repo's devenv shell". That is true for project tools and false for host tools.

## 3. Doctor rows inside the shell (task 3)

Entry: `devenv shell -- bash probe.sh` (runs `repoman doctor`). The draft's `enterShell` has no profile-directory rewrite (`PATH` gets only the venv bin). Rows for copy, git, test. I dropped the two `skill:*` warn rows from this table; they only reflect that the copy has no `.agents`. `copyroom` is not installed on this host, so `installed:copy` fails in every run. That shows the host-plane fix text. (verified: `ls ~/.nix-profile/bin /etc/profiles/per-user/$USER/bin | grep copyroom` is empty)

| Scenario | installed:copy | installed:git / interface:git | installed:test | version:test |
|---|---|---|---|---|
| A. repoman copy, host profile on PATH | FAIL not on PATH -- nix profile add | OK gitman (per-user profile); OK jj 0.46.0 | OK `/nix/store/rs4i9...-testee-0.5.1/bin/testee` | OK reports 0.5.1; needs 0.5.0 |
| A. same, fake `testee 0.4.0` first on the outer PATH | same | same | OK same store path (fake loses) | OK reports 0.5.1 |
| A. c1 (module imported), host profile on PATH | same | same | OK store path | OK 0.5.1 |
| A. c2 (NO Testee module), host profile on PATH | same | same | **OK `/home/andrew/.nix-profile/bin/testee`** (host masks the gap) | **OK 0.5.1** |
| A. c2, host profile NOT on PATH | same | same | FAIL `testee not on PATH — import the testee devenv module in devenv.nix, then re-enter devenv shell` | FAIL `cannot read version; testee is missing — import ... ` |
| B. c1, host profile on PATH | same | same | OK `.../devenv-profile/bin/testee` | OK 0.5.1 |
| B. c2, host profile on PATH | same | same | **FAIL** testee not on PATH — import the testee devenv module ... | **FAIL** cannot read version ... |
| B. repoman copy, fake first | same | same | OK `.../devenv-profile/bin/testee` | OK 0.5.1 |

Evidence for the fake: `which -a testee` inside the shell printed the store path first, then `/tmp/tw-w4d-fake/bin/testee`, then `~/.nix-profile/bin/testee`. `testee --version` printed `testee 0.5.1`. (verified)

Findings:

- Inside a shell that imports the Testee module, the pinned package always wins. (verified)
- The host profile stays on `PATH` inside `devenv shell`, so a host `testee` hides a missing environment module under A. (verified, c2). In the draft, `testee` is on the host `PATH` for every user who follows the install line, so A alone almost never shows the project text.
- Missing Testee module does not break Nix evaluation of RepoMan's module: c2 entered the shell and ran doctor. (verified; confirms the inference in 09)
- `DEVENV_PROFILE/bin/testee` exists in c1 and not in c2. (verified: `ls $DEVENV_PROFILE/bin | grep -c testee` gave 1 and 0)
- `devenv tasks run` and `DEVENV_PROFILE`: unknown. B falls back to `which` if the variable is missing, but I did not run doctor from a task.

## 4. Test suite (task 4)

How: `devenv shell`, then `uv sync --all-groups`, `uv pip install ruff`, `python -m pytest -q`. The repo gate is `testee verify --full` (`base:test`), which wraps `uv run pytest`. I ran pytest directly in a scratch venv under `/tmp`, and ran ruff and ty by hand. (verified)

| Tree | Result |
|---|---|
| trunk baseline (from 09) | 129 passed |
| draft + plane (A), outside shell | 134 passed |
| A inside `devenv shell` | 134 passed |
| B inside `devenv shell` | 135 passed; first run 7 failed until `conftest.py` cleared `DEVENV_PROFILE` |
| lint | `ruff check` clean, `ruff format --check` clean (38 files), `ty check src` clean |

Test diff size: the plane delta is +35 lines (A) and +13 more (B). The whole draft vs trunk changes tests by +63/-42 in 4 files. Non-test files change by +66/-120, including the `testee.nix` deletion (-38). (verified, `diff -ruN`)

## 5. Router text (task 5)

Current template line (`templates/entrypoint.SKILL.md.j2:12`):

> Run everything inside `devenv shell`. Exit codes: ...

- The rule already covers project tools and host tools. Host tools remain on `PATH` inside the shell. (verified: gitman found in the shell)
- Rows do not need a plane marker. The agent does not choose a tool by plane; the row names the command and the skill.
- An agent whose shell is outside the environment is the real gap. `devenv shell -- testee --version` from outside printed `testee 0.5.1`, exit 0, with `env -i` and no host profile on `PATH`. (verified, c1)
- Smallest text, one added sentence:

> Run everything inside `devenv shell`. From outside it, prefix one command: `devenv shell -- <command>`.

I did not apply it. It changes generated router files in every repo after `repoman-sync` (inferred). No test pins this line. (verified: `grep -rn "Run everything inside" tests src` finds only the template and a fixture copy)

## 6. Is `plane` worth a field? (task 6)

Keep the field only with variant B. It cannot be derived: no RepoMan Nix module supplies any manager command (`copyroom.nix` adds `git` and `gnupatch`, `gitman.nix` adds `git`, the draft deletes `testee.nix`), and the Python doctor cannot see what Testee's own module adds. At run time, the doctor can see where a binary came from (`DEVENV_PROFILE/bin` or venv bin versus a profile directory), but not where it should come from. Only a declaration states the expectation, so one registry word is the right size. Variant A buys two strings of fix text and is not worth a field on its own: a generic hint, or none, serves as well. Variant B closes a real gap: a host `testee` no longer masks a missing module. It costs about 22 lines. Name caution (inferred): "plane" already means "automation plane" and "link plane" in `CONCEPT.md:33` and `README.md:198`. Consider `source = "host" | "project"` instead.

## Appendix: full diff, trunk `efa1e92c` vs `/tmp/tw-w4d/repoman` (variant A)

Stats: `+129 -162`, 10 files (`diff -ruN`, `CLAUDE.md` symlink and generated files excluded). Raw file: `/tmp/tw-w4d/full.clean.diff`.

```diff
diff a/AGENTS.md b/AGENTS.md
--- a/AGENTS.md
+++ b/AGENTS.md
@@ -33,7 +33,7 @@
 devenv shell                     # enter the pinned environment
 repoman-sync                     # generate the router skill
 devenv tasks run -v base:check   # repoman:lint — must be green before a PR
-devenv tasks run -v base:test    # repoman:test
+devenv tasks run -v base:test    # testee:verify
 ```
 
 ## Where things live
diff a/devenv.nix b/devenv.nix
--- a/devenv.nix
+++ b/devenv.nix
@@ -171,14 +171,14 @@
   # The two task names the `base` group calls (groups/base/README.md). devenv
   # owns each implementation; Dagu owns the composition (§6).
   #
-  # `base:test` forwards to `repoman:test` — the repository's own gate, defined
-  # by the testee manager module (`testee verify`); duplicating it
+  # `base:test` forwards to `testee:verify` — the repository's own gate, defined
+  # by Testee's devenv module (`testee verify --full`); duplicating it
   # would be a second implementation (PROPOSAL.md §6 rule 6). `base:check` is
   # the fast one: ruff over the repo's own `src` scope (`uv run --group dev`
   # because the venv bin is not on the task runner's PATH).
   tasks = {
     "repoman:lint".exec = "uv run --group dev ruff check src";
     "base:check".after = [ "repoman:lint" ];
-    "base:test".after = [ "repoman:test" ];
+    "base:test".after = [ "testee:verify" ];
   };
 }
diff a/modules/devenv.nix b/modules/devenv.nix
--- a/modules/devenv.nix
+++ b/modules/devenv.nix
@@ -13,15 +13,15 @@
 #
 #   repoman.enable = true;
 #
-# Each manager's wiring lives in ./managers/<name>.nix and gates itself on
+# Each manager's wiring lives in ./managers/<name>.nix (copy and git only; the test
+# manager needs none) and gates itself on
 # membership in the tracked project manifest. Imports cannot depend on `config`, so we
 # import every manager module statically and let each one decide whether to
 # activate — the standard devenv/NixOS module idiom.
 #
 # The manifest roster selects which manager tasks/skills are WIRED. It does not
 # install anything. The host profile puts the manager commands (copyroom, gitman,
-# and testee) on PATH, and RepoMan runs them by name. Testee starts outside
-# devenv and opens a clean shell for the checks. RepoMan reads no Vendomat closure.
+# and testee) on PATH, and RepoMan runs them by name. RepoMan reads no Vendomat closure.
 { pkgs, lib, config, inputs ? {}, ... }:
 
 let
@@ -77,7 +77,6 @@
 in
 {
   imports = [
-    ./managers/testee.nix
     ./managers/copyroom.nix
     ./managers/gitman.nix   # activates when "git" is selected; contributes git only
   ]
@@ -134,10 +133,8 @@
 
     enterShell = ''
       # Tasks run this enterShell block, but do not prepend the consumer venv.
-      # Keep app tools available, then put the host Testee profile before packages
-      # added by devenv. The doctor and manager task use this same wrapper.
-      export REPOMAN_TESTEE_HOST_BIN="''${REPOMAN_TESTEE_HOST_BIN:-$HOME/.nix-profile/bin/testee}"
-      export PATH="${config.devenv.state}/venv/bin:$(dirname "$REPOMAN_TESTEE_HOST_BIN"):$PATH"
+      # Keep app tools available.
+      export PATH="${config.devenv.state}/venv/bin:$PATH"
       if [ -t 1 ]; then
         echo "RepoMan: managers = ${lib.concatStringsSep " " (builtins.filter (m: builtins.elem m allManagers) managerRoster)}"
       fi
diff a/modules/managers/testee.nix b/modules/managers/testee.nix
--- a/modules/managers/testee.nix
+++ b/modules/managers/testee.nix
@@ -1,38 +0,0 @@
-# RepoMan manager wiring: testee (verification).
-#
-# Imported unconditionally by ../devenv.nix; activates only when "test" is in
-# the project manifest roster. Testee v2 runs its wrapper from the host profile,
-# then opens one clean devenv shell for the declared checks. The package version
-# comes from the Testee Nix module pinned in the consumer's devenv.
-#
-# RepoMan sets no `enterTest`. Testee's own module sets it to the full gate, and
-# devenv joins every `enterTest` value. A second value here would run the full
-# gate twice under `devenv test`.
-#
-# Consumers must set `testee.package` and declare their own `testee.checks`.
-# RepoMan supplies no default checks. For example:
-#
-#   testee.checks.pytest = {
-#     argv = [ "uv" "run" "pytest" "-q" ];
-#     profiles = [ "quick" "full" ];
-#   };
-{ lib, config, repomanManagers, ... }:
-
-let
-  cfg = config.repoman;
-  enabled = cfg.enable && builtins.elem "test" repomanManagers;
-  testeeBin = ''"''${REPOMAN_TESTEE_HOST_BIN:-$HOME/.nix-profile/bin/testee}"'';
-in
-{
-  config = lib.mkIf enabled {
-    env.REPOMAN_TESTEE_VERSION = lib.removePrefix "testee-" config.testee.package.name;
-
-    # Verification entrypoints, namespaced under repoman:* so the conductor and
-    # the underlying tool agree on the surface. testee owns its own report, and
-    # RepoMan does not aggregate it — run `testee doctor` to check testee.
-    tasks = {
-      "repoman:test".exec = ''cd "$DEVENV_ROOT" && ${testeeBin} verify'';
-      "repoman:test:ci".exec = ''cd "$DEVENV_ROOT" && ${testeeBin} verify --full'';
-    };
-  };
-}
diff a/src/repoman/checks.py b/src/repoman/checks.py
--- a/src/repoman/checks.py
+++ b/src/repoman/checks.py
@@ -5,8 +5,8 @@
 
 The manager family splits by install model. Host managers (`install == "path"`)
 are on `PATH`: the host profile installs them, and RepoMan runs them by name.
-The Testee wrapper also runs from the host profile. Its pinned Nix package supplies
-the required version, which this module checks. RepoMan reads no Vendomat closure.
+A manager with a ``min_version`` also gets a ``version:<key>`` row. RepoMan reads no
+Vendomat closure.
 An optional uv manager (`install == "uv"`) lives in the consumer's uv graph.
 
 Two disciplines this module holds to, because it is the *diagnostic* layer:
@@ -15,8 +15,8 @@
   guarded (`OSError`, decode errors, malformed TOML). A doctor that raises is
   strictly worse than one that reports ``fail``.
 * **Validate the binary that actually runs.** A uv manager runs from the consumer
-  venv. A path manager runs from ``PATH`` or its explicit binary environment
-  variable. The Testee version row checks that binary against the pinned package.
+  venv. A path manager runs from ``PATH``. The version row checks that binary
+  against the registry ``min_version``.
 """
 
 from __future__ import annotations
@@ -129,14 +129,11 @@
 def manager_binary(manager: Manager) -> Path | None:
     """The absolute path ``manager`` runs from, if knowable.
 
-    A path manager runs from its configured environment path or ``PATH``. A uv
-    manager runs from the consumer venv. ``None`` means no binary was found.
+    A path manager runs from ``PATH``. A uv manager runs from the consumer venv.
+    ``None`` means no binary was found.
     """
 
     if manager.install == "path":
-        configured = os.environ.get(manager.binary_env) if manager.binary_env else None
-        if configured:
-            return Path(configured)
         found = shutil.which(manager.command)
         return Path(found) if found else None
     bin_dir = consumer_venv_bin()
@@ -194,41 +191,28 @@
 # ------------------------------------------------------------------ self-check
 
 
+def _fix_hint(manager: Manager) -> str:
+    """The fix text for a missing or old command, by plane."""
+
+    if manager.plane == "project":
+        return f"import the {manager.command} devenv module in devenv.nix, then re-enter `devenv shell`"
+    return "install it with `nix profile add` in the host profile"
+
+
 def _installed_check(manager: Manager) -> SelfCheck:
     """Validate the binary a manager runs from.
 
-    A path manager must match the binary its task uses. A uv manager runs from the
-    consumer venv, so a green ``PATH`` lookup can coexist with a missing venv binary.
+    A path manager must be on ``PATH``. A uv manager runs from the consumer
+    venv, so a green ``PATH`` lookup can coexist with a missing venv binary.
     """
 
     if manager.install == "path":
         binary = manager_binary(manager)
-        on_path = shutil.which(manager.command)
         if binary is None or not binary.exists() or not os.access(binary, os.X_OK):
             detail = f"{binary} missing or not executable" if binary else f"{manager.command} not on PATH"
+            detail += f" — {_fix_hint(manager)}"
             return SelfCheck(f"installed:{manager.key}", "fail", detail)
-        if manager.binary_env and not on_path:
-            return SelfCheck(
-                f"installed:{manager.key}",
-                "fail",
-                f"{manager.command} is missing from PATH; add {binary.parent}",
-            )
-        if on_path:
-            try:
-                shadowed = Path(on_path).resolve() != binary.resolve()
-            except OSError:
-                shadowed = False
-            if shadowed:
-                return SelfCheck(
-                    f"installed:{manager.key}",
-                    "fail",
-                    f"tasks use {binary}, but PATH resolves {manager.command} to {on_path}",
-                )
-        return SelfCheck(
-            f"installed:{manager.key}",
-            "ok",
-            str(binary),
-        )
+        return SelfCheck(f"installed:{manager.key}", "ok", str(binary))
 
     on_path = shutil.which(manager.command)
     expected = manager_binary(manager)
@@ -261,41 +245,41 @@
     return SelfCheck(f"installed:{manager.key}", "ok", str(expected))
 
 
+def _dotted_version(text: str) -> tuple[int, int, int] | None:
+    """First ``X.Y.Z`` in ``text`` as a tuple, or ``None``."""
+
+    found = re.search(r"\b(\d+)\.(\d+)\.(\d+)", text)
+    return (int(found[1]), int(found[2]), int(found[3])) if found else None
+
+
 def _version_check(manager: Manager) -> SelfCheck | None:
-    """Check a manager version against the value exported by its pinned package."""
+    """Check that a manager reports at least ``min_version`` for ``--version``."""
 
-    if not manager.version_env:
+    if not manager.min_version:
         return None
-    required = os.environ.get(manager.version_env)
-    if not required:
-        return SelfCheck(
-            f"version:{manager.key}",
-            "fail",
-            f"{manager.version_env} is missing — import the pinned Testee module",
-        )
+    name = f"version:{manager.key}"
     binary = manager_binary(manager)
     if binary is None or not binary.exists() or not os.access(binary, os.X_OK):
         return SelfCheck(
-            f"version:{manager.key}", "fail", f"cannot read version; {binary or manager.command} is missing"
+            name, "fail", f"cannot read version; {binary or manager.command} is missing — {_fix_hint(manager)}"
         )
     try:
         result = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=10, check=False)
     except (OSError, subprocess.TimeoutExpired) as exc:
-        return SelfCheck(f"version:{manager.key}", "fail", f"cannot read version from {binary}: {exc}")
-    if result.returncode != 0:
-        return SelfCheck(
-            f"version:{manager.key}",
-            "fail",
-            f"{binary} --version exited {result.returncode}: {(result.stderr or result.stdout).strip()}",
-        )
+        return SelfCheck(name, "fail", f"cannot read version from {binary}: {exc}")
     output = (result.stdout or result.stderr).strip()
-    match = re.fullmatch(r"testee\s+(\S+)", output)
-    if match is None:
-        return SelfCheck(f"version:{manager.key}", "fail", f"unrecognized version from {binary}: {output!r}")
-    actual = match.group(1)
-    level = "ok" if actual == required else "fail"
-    detail = f"{binary} reports {actual}; pinned package requires {required}"
-    return SelfCheck(f"version:{manager.key}", level, detail)
+    if result.returncode != 0:
+        return SelfCheck(name, "fail", f"{binary} --version exited {result.returncode}: {output}")
+    actual = _dotted_version(output)
+    if actual is None:
+        return SelfCheck(name, "fail", f"unrecognized version from {binary}: {output!r}")
+    needed = _dotted_version(manager.min_version)
+    level = "ok" if needed is not None and actual >= needed else "fail"
+    shown = ".".join(map(str, actual))
+    detail = f"{binary} reports {shown}; needs {manager.min_version} or later"
+    if level == "fail":
+        detail += f" — {_fix_hint(manager)}"
+    return SelfCheck(name, level, detail)
 
 
 def _gitman_interface_check(manager: Manager) -> SelfCheck:
@@ -317,10 +301,10 @@
         return SelfCheck("interface:git", "fail", f"cannot check gitman and jj: {exc}")
     if help_result.returncode != 0 or not re.search(r"^usage: gitman .*\{work\}", help_result.stdout, re.M):
         return SelfCheck("interface:git", "fail", f"{binary} is not the work-only gitman (0.12 or later)")
-    version = re.search(r"\bjj (\d+)\.(\d+)\.(\d+)", jj_result.stdout)
-    if jj_result.returncode != 0 or version is None or tuple(map(int, version.groups())) < (0, 46, 0):
+    version = _dotted_version(jj_result.stdout)
+    if jj_result.returncode != 0 or version is None or version < (0, 46, 0):
         return SelfCheck("interface:git", "fail", "gitman work needs jj 0.46.0 or later")
-    return SelfCheck("interface:git", "ok", f"{binary}; {version.group(0)}")
+    return SelfCheck("interface:git", "ok", f"{binary}; jj {'.'.join(map(str, version))}")
 
 
 def _skill_defers(path: Path) -> bool | None:
diff a/src/repoman/registry.py b/src/repoman/registry.py
--- a/src/repoman/registry.py
+++ b/src/repoman/registry.py
@@ -33,9 +33,12 @@
             ``uv sync`` (its ``doctor`` check is ``uv:<key>``, not ``lock:<key>``).
         package: Distribution name on the index; defaults to ``command``. Used to
             find the manager in ``pyproject.toml`` for uv-declared managers.
-        binary_env: Environment variable with the canonical executable path, when
-            PATH lookup could select a different install.
-        version_env: Environment variable with the version the executable must report.
+        min_version: Oldest version the command may report for ``--version``;
+            ``""`` skips the version check.
+        plane: Where the command comes from. ``"host"`` tools act on or across
+            repos and come from the user profile. ``"project"`` tools act within
+            one repo and come from the repo's locked devenv environment. The plane
+            only changes the fix text of the doctor rows.
     """
 
     key: str
@@ -50,8 +53,8 @@
     install: str = "path"  # "path" = the host puts the command on PATH;
     # "uv" = declared in the consumer's pyproject.toml, installed by uv sync
     package: str = ""  # distribution name; defaults to `command`
-    binary_env: str = ""  # override PATH with the exact executable the module runs
-    version_env: str = ""  # required version supplied by the pinned Nix package
+    min_version: str = ""  # oldest `<command> --version` RepoMan accepts; "" = unchecked
+    plane: str = "host"  # "host" = user profile; "project" = the repo's devenv environment
 
     def __post_init__(self) -> None:
         if not self.skill:
@@ -60,6 +63,8 @@
             object.__setattr__(self, "package", self.command)
         if self.install not in {"path", "uv"}:
             raise ValueError(f"{self.key}: unknown install model {self.install!r}")
+        if self.plane not in {"host", "project"}:
+            raise ValueError(f"{self.key}: unknown plane {self.plane!r}")
 
 
 # The lifecycle spine: three ordered phases, as (label, manager-key | None). The
@@ -103,10 +108,8 @@
         "Verification (pytest / ruff / ty)",
         status=["report"],
         route_when="verify code health and review the latest report",
-        # The v2 wrapper starts outside devenv. The project declares the check tools;
-        # this manager invokes the host-profile wrapper pinned by the Testee module.
-        binary_env="REPOMAN_TESTEE_HOST_BIN",
-        version_env="REPOMAN_TESTEE_VERSION",
+        min_version="0.5.0",  # the host-wrapper model; see CHANGELOG 0.12.0
+        plane="project",
     ),
 }
 
diff a/tests/test_checks.py b/tests/test_checks.py
--- a/tests/test_checks.py
+++ b/tests/test_checks.py
@@ -39,8 +39,6 @@
     testee.chmod(0o755)
     monkeypatch.delenv("DEVENV_STATE", raising=False)
     monkeypatch.delenv("DEVENV_ROOT", raising=False)
-    monkeypatch.setenv("REPOMAN_TESTEE_HOST_BIN", str(testee))
-    monkeypatch.setenv("REPOMAN_TESTEE_VERSION", "0.5.0")
     monkeypatch.setattr(
         checks.shutil,
         "which",
@@ -150,29 +148,22 @@
     assert "lock:uv-tool" not in names
 
 
-def test_testee_version_matches_the_pinned_package(host):
+def test_testee_version_meets_the_minimum(host):
     names = _names(run_self_check([REGISTRY["test"]], ".", ".claude/skills"))
     assert names["installed:test"].level == "ok"
     assert names["version:test"].level == "ok"
     assert "0.5.0" in names["version:test"].detail
 
 
-def test_testee_path_must_match_the_host_binary(host, tmp_path, monkeypatch):
-    shadow = tmp_path / "shadow" / "testee"
-    shadow.parent.mkdir()
-    shadow.write_text('#!/bin/sh\nprintf "testee 0.5.0\\n"\n')
-    shadow.chmod(0o755)
-    monkeypatch.setattr(
-        checks.shutil,
-        "which",
-        lambda command: str(shadow) if command == "testee" else str(host.bin / command),
-    )
+def test_testee_newer_than_the_minimum_passes(host):
+    testee = host.bin / "testee"
+    testee.write_text('#!/bin/sh\nprintf "testee 0.6.2\\n"\n')
+    testee.chmod(0o755)
     names = _names(run_self_check([REGISTRY["test"]], ".", ".claude/skills"))
-    assert names["installed:test"].level == "fail"
-    assert "tasks use" in names["installed:test"].detail
+    assert names["version:test"].level == "ok"
 
 
-def test_testee_version_mismatch_fails(host):
+def test_testee_older_than_the_minimum_fails(host):
     testee = host.bin / "testee"
     testee.write_text('#!/bin/sh\nprintf "testee 0.4.0\\n"\n')
     testee.chmod(0o755)
@@ -181,11 +172,13 @@
     assert "reports 0.4.0" in names["version:test"].detail
 
 
-def test_testee_requires_a_pinned_version(host, monkeypatch):
-    monkeypatch.delenv("REPOMAN_TESTEE_VERSION")
+def test_unrecognized_version_output_fails(host):
+    testee = host.bin / "testee"
+    testee.write_text('#!/bin/sh\nprintf "no version here\\n"\n')
+    testee.chmod(0o755)
     names = _names(run_self_check([REGISTRY["test"]], ".", ".claude/skills"))
     assert names["version:test"].level == "fail"
-    assert "REPOMAN_TESTEE_VERSION is missing" in names["version:test"].detail
+    assert "unrecognized version" in names["version:test"].detail
 
 
 def test_detect_context_precedence(tmp_path, monkeypatch):
@@ -251,3 +244,25 @@
     )
     sub.write_text("See the repoman skill for ordering.")
     assert _names(run_self_check([REGISTRY["git"]], str(tmp_path), ".claude/skills"))["skill:git:defers"].level == "ok"
+
+
+def test_missing_host_tool_names_the_profile_fix(host):
+    (host.bin / "gitman").unlink()
+    detail = _names(run_self_check([REGISTRY["git"]], ".", ".claude/skills"))["installed:git"].detail
+    assert "nix profile add" in detail
+
+
+def test_missing_project_tool_names_the_environment_fix(host):
+    (host.bin / "testee").unlink()
+    names = _names(run_self_check([REGISTRY["test"]], ".", ".claude/skills"))
+    for row in ("installed:test", "version:test"):
+        assert names[row].level == "fail"
+        assert "devenv.nix" in names[row].detail and "nix profile" not in names[row].detail
+
+
+def test_old_project_tool_names_the_environment_fix(host):
+    testee = host.bin / "testee"
+    testee.write_text('#!/bin/sh\nprintf "testee 0.4.0\\n"\n')
+    testee.chmod(0o755)
+    detail = _names(run_self_check([REGISTRY["test"]], ".", ".claude/skills"))["version:test"].detail
+    assert "devenv.nix" in detail
diff a/tests/test_cli.py b/tests/test_cli.py
--- a/tests/test_cli.py
+++ b/tests/test_cli.py
@@ -64,28 +64,24 @@
     monkeypatch.setenv("DEVENV_STATE", str(state))
     monkeypatch.setenv("REPOMAN_MANAGERS", managers)
     monkeypatch.setenv("DEVENV_ROOT", str(tmp_path))
-    monkeypatch.setenv("REPOMAN_TESTEE_HOST_BIN", str(host_bin / "testee"))
-    monkeypatch.setenv("REPOMAN_TESTEE_VERSION", "0.5.0")
     monkeypatch.setattr("repoman.checks.shutil.which", which)
 
 
-def test_doctor_fails_when_testee_host_binary_is_missing(monkeypatch, tmp_path):
+def test_doctor_fails_when_testee_is_not_on_path(monkeypatch, tmp_path):
     monkeypatch.setenv("REPOMAN_MANAGERS", "test")
     monkeypatch.setenv("DEVENV_ROOT", str(tmp_path))
-    monkeypatch.setenv("REPOMAN_TESTEE_HOST_BIN", str(tmp_path / "missing-testee"))
-    monkeypatch.setenv("REPOMAN_TESTEE_VERSION", "0.5.0")
     monkeypatch.setattr("repoman.checks.shutil.which", lambda _c: None)
     result = runner.invoke(app, ["doctor"])
     assert "FAIL installed:test" in result.stdout
     assert result.exit_code == 1
 
 
-def test_doctor_fails_when_testee_version_does_not_match(monkeypatch, tmp_path):
+def test_doctor_fails_when_testee_is_too_old(monkeypatch, tmp_path):
     _healthy_repo(tmp_path, monkeypatch, "test")
     (tmp_path / "host-bin" / "testee").write_text('#!/bin/sh\nprintf "testee 0.4.0\\n"\n')
     result = runner.invoke(app, ["doctor"])
     assert "FAIL version:test" in result.stdout
-    assert "pinned package requires 0.5.0" in result.stdout
+    assert "needs 0.5.0 or later" in result.stdout
     assert result.exit_code == 1
 
 
diff a/tests/test_modules_nix.py b/tests/test_modules_nix.py
--- a/tests/test_modules_nix.py
+++ b/tests/test_modules_nix.py
@@ -7,18 +7,16 @@
 def test_manager_tasks_use_the_host_profile():
     users = {p.name for p in (MODULES / "managers").glob("*.nix") if "venvBin" in p.read_text()}
     assert users == set()
-    testee = (MODULES / "managers" / "testee.nix").read_text()
-    assert "REPOMAN_TESTEE_HOST_BIN" in testee
-    assert 'lib.removePrefix "testee-" config.testee.package.name' in testee
 
 
-def test_test_manager_sets_no_enter_test():
-    # Testee's own module sets `enterTest` to the full gate. devenv joins every
-    # value, so a second one in RepoMan would run the full gate twice.
-    text = (MODULES / "managers" / "testee.nix").read_text()
-    assert not any(line.lstrip().startswith("enterTest") for line in text.splitlines())
-    assert '"repoman:test".exec' in text
-    assert '"repoman:test:ci".exec' in text
+def test_test_manager_has_no_nix_module():
+    # The `test` manager is uniform with copy and git: a bare command on PATH.
+    # Testee's own module supplies the package, `testee:verify` and `enterTest`.
+    assert not (MODULES / "managers" / "testee.nix").exists()
+    text = (MODULES / "devenv.nix").read_text()
+    assert "managers/testee.nix" not in text
+    for retired in ("REPOMAN_TESTEE_HOST_BIN", "REPOMAN_TESTEE_VERSION", "repoman:test"):
+        assert retired not in text
 
 
 def test_host_managers_run_by_name_from_path():
@@ -34,9 +32,8 @@
 
 def test_meta_module_keeps_the_consumer_venv_on_path_and_reads_no_closure():
     text = (MODULES / "devenv.nix").read_text()
-    assert "export REPOMAN_TESTEE_HOST_BIN=" in text
-    assert '$(dirname "$REPOMAN_TESTEE_HOST_BIN")' in text
     assert '"${config.devenv.state}/venv/bin:' in text
+    assert "nix-profile" not in text
     for retired in ("REPOMAN_TOOLCHAIN_BIN", "toolchainBin", "storeBinExpr", "REPOMAN_TOOLCHAIN_MANIFEST"):
         assert retired not in text
 
@@ -51,7 +48,7 @@
 def test_manager_modules_receive_the_manifest_roster():
     text = (MODULES / "devenv.nix").read_text()
     assert "_module.args.repomanManagers = managerRoster;" in text
-    for name in ("gitman.nix", "copyroom.nix", "testee.nix"):
+    for name in ("gitman.nix", "copyroom.nix"):
         assert "repomanManagers" in (MODULES / "managers" / name).read_text()
 
 
diff a/tests/test_registry.py b/tests/test_registry.py
--- a/tests/test_registry.py
+++ b/tests/test_registry.py
@@ -1,3 +1,5 @@
+import pytest
+
 from repoman.registry import ACTIVITIES, DEFAULT_MANAGERS, REGISTRY, REMOVED_MANAGERS, SPINE, Manager
 
 
@@ -78,10 +80,10 @@
         assert REGISTRY[key].install == "path"
 
 
-def test_testee_uses_the_host_binary_and_pinned_version():
+def test_testee_has_a_minimum_version_and_copy_git_have_none():
     testee = REGISTRY["test"]
-    assert testee.binary_env == "REPOMAN_TESTEE_HOST_BIN"
-    assert testee.version_env == "REPOMAN_TESTEE_VERSION"
+    assert testee.min_version == "0.5.0"
+    assert REGISTRY["copy"].min_version == REGISTRY["git"].min_version == ""
     assert testee.status == ["report"]
 
 
@@ -124,3 +126,14 @@
     # correct code, while a real literal could have sat right beside it.
     source = (Path(__file__).resolve().parents[1] / "src" / "repoman" / "__init__.py").read_text()
     assert 'version("repoman")' in source, "the version must be read from the installed distribution"
+
+
+def test_planes():
+    # Host tools act across repos. The project tool comes from the locked devenv environment.
+    assert REGISTRY["copy"].plane == REGISTRY["git"].plane == "host"
+    assert REGISTRY["test"].plane == "project"
+
+
+def test_plane_is_validated():
+    with pytest.raises(ValueError, match="plane"):
+        Manager("x", "x", "core", "s", plane="cloud")
```
