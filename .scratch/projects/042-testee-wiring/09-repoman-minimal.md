# 09 RepoMan minimal: `test` manager uniform with `copy` and `git`

Labels: `verified` = command output or file cited. `inferred` = my reasoning. `unknown` = not established.
Working copy: `/tmp/tw-rm/repoman` (from trunk snapshot `/tmp/tw-trunk/repoman`, efa1e92c).
Logs: `/tmp/tw-logs/` (patches, probe scripts). The live repo was not touched (verified: `git status` shows only `.scratch/projects/042-testee-wiring/`).

## Summary

- Trunk baseline: 129 tests pass. (verified: `pytest` run in a copy of trunk)
- Target drafted: 129 tests pass, `ruff check`, `ruff format --check`, `ty check src` clean. (verified)
- Non-test change: +43 / -122 lines in 6 files, one file deleted (`modules/managers/testee.nix`, 38 lines). Test change: +28 / -42 in 4 files. (verified: `diff`)
- I chose `min_version = "0.5.0"`, not `0.6.0`. The pinned Testee is 0.5.1, so `>= 0.6.0` would make `version:test` fail on every current repo. (verified: `devenv.nix:8`, `testee --version` prints `testee 0.5.1`)
- Biggest behavior change: inside a devenv shell that imports the Testee module, `testee` is always the pinned store package. Host-vs-pin drift is no longer detected in the shell. (verified, see section 3)

## 1. The change (draft)

What it does:

- `Manager.binary_env` and `Manager.version_env` become one field, `min_version`. (verified: diff)
- `manager_binary` uses `shutil.which` only. `_installed_check` for path managers loses the "missing from PATH; add" and shadow branches. (verified: diff)
- `_version_check` is generic: run `<bin> --version`, take the first `X.Y.Z`, compare as a tuple with `min_version`. The `testee\s+` regex and the Testee-only message are gone. (verified: diff)
- The jj minimum in `_gitman_interface_check` reuses the same `_dotted_version` helper. (verified: diff) This shares a parser. It does not move the jj minimum into the registry, because jj is not a manager and gitman has no `--version`. A single registry field cannot cover jj. (inferred) A `companions` field would be needed.
- `modules/managers/testee.nix` is deleted. The import in `modules/devenv.nix` is removed. `repoman:test`, `repoman:test:ci`, `REPOMAN_TESTEE_VERSION` and the `config.testee.package` coupling are gone. (verified: diff)
- `enterShell` keeps only the venv prepend. I removed the `REPOMAN_TESTEE_HOST_BIN` export and the `dirname` PATH entry. (verified: diff)
- `base:test` now waits on `testee:verify` (Testee's own task). (verified: `devenv tasks list` shows `base:test -> testee:verify`)

Open points on this change:

- The venv-bin half of the PATH line stays. Its comment says tasks need it. I did not test removal. (unknown) Dropping it is a separate question.
- A consumer with `test` on the roster and no Testee module no longer gets a Nix evaluation error. It gets `FAIL installed:test` only when no `testee` is on `PATH`. (inferred: the only reader of `config.testee.package` was the deleted file; not run)
- The version check in a shell now tests the pinned package against 0.5.0, so it is nearly vacuous there. It still bites outside a shell (bare `repoman doctor`). (inferred from section 3)
- Template-py (outside this repo) asserts RepoMan supplies `repoman:test` and forbids a consumer `enterTest`. `copyroom.yml:28` and `README.md:82-90` there need an edit. (verified earlier in 01 report)

### Unified diff (`diff -ru` trunk vs copy, paths trimmed)

```diff
diff AGENTS.md
--- trunk/AGENTS.md
+++ rm/AGENTS.md
@@ -33,7 +33,7 @@
 devenv shell                     # enter the pinned environment
 repoman-sync                     # generate the router skill
 devenv tasks run -v base:check   # repoman:lint — must be green before a PR
-devenv tasks run -v base:test    # repoman:test
+devenv tasks run -v base:test    # testee:verify
 ```
 
 ## Where things live
diff devenv.nix
--- trunk/devenv.nix
+++ rm/devenv.nix
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
diff modules/devenv.nix
--- trunk/modules/devenv.nix
+++ rm/modules/devenv.nix
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
diff modules/managers/testee.nix
--- trunk/modules/managers/testee.nix
+++ rm/modules/managers/testee.nix
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
diff src/repoman/checks.py
--- trunk/src/repoman/checks.py
+++ rm/src/repoman/checks.py
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
@@ -197,38 +194,16 @@
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
@@ -261,41 +236,36 @@
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
-        return SelfCheck(
-            f"version:{manager.key}", "fail", f"cannot read version; {binary or manager.command} is missing"
-        )
+        return SelfCheck(name, "fail", f"cannot read version; {binary or manager.command} is missing")
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
+    return SelfCheck(name, level, f"{binary} reports {shown}; needs {manager.min_version} or later")
 
 
 def _gitman_interface_check(manager: Manager) -> SelfCheck:
@@ -317,10 +287,10 @@
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
diff src/repoman/registry.py
--- trunk/src/repoman/registry.py
+++ rm/src/repoman/registry.py
@@ -33,9 +33,8 @@
             ``uv sync`` (its ``doctor`` check is ``uv:<key>``, not ``lock:<key>``).
         package: Distribution name on the index; defaults to ``command``. Used to
             find the manager in ``pyproject.toml`` for uv-declared managers.
-        binary_env: Environment variable with the canonical executable path, when
-            PATH lookup could select a different install.
-        version_env: Environment variable with the version the executable must report.
+        min_version: Oldest version the command may report for ``--version``;
+            ``""`` skips the version check.
     """
 
     key: str
@@ -50,8 +49,7 @@
     install: str = "path"  # "path" = the host puts the command on PATH;
     # "uv" = declared in the consumer's pyproject.toml, installed by uv sync
     package: str = ""  # distribution name; defaults to `command`
-    binary_env: str = ""  # override PATH with the exact executable the module runs
-    version_env: str = ""  # required version supplied by the pinned Nix package
+    min_version: str = ""  # oldest `<command> --version` RepoMan accepts; "" = unchecked
 
     def __post_init__(self) -> None:
         if not self.skill:
@@ -103,10 +101,7 @@
         "Verification (pytest / ruff / ty)",
         status=["report"],
         route_when="verify code health and review the latest report",
-        # The v2 wrapper starts outside devenv. The project declares the check tools;
-        # this manager invokes the host-profile wrapper pinned by the Testee module.
-        binary_env="REPOMAN_TESTEE_HOST_BIN",
-        version_env="REPOMAN_TESTEE_VERSION",
+        min_version="0.5.0",  # the host-wrapper model; see CHANGELOG 0.12.0
     ),
 }
 
diff tests/test_checks.py
--- trunk/tests/test_checks.py
+++ rm/tests/test_checks.py
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
diff tests/test_cli.py
--- trunk/tests/test_cli.py
+++ rm/tests/test_cli.py
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
 
 
diff tests/test_modules_nix.py
--- trunk/tests/test_modules_nix.py
+++ rm/tests/test_modules_nix.py
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
 
 
diff tests/test_registry.py
--- trunk/tests/test_registry.py
+++ rm/tests/test_registry.py
@@ -78,10 +78,10 @@
         assert REGISTRY[key].install == "path"
 
 
-def test_testee_uses_the_host_binary_and_pinned_version():
+def test_testee_has_a_minimum_version_and_copy_git_have_none():
     testee = REGISTRY["test"]
-    assert testee.binary_env == "REPOMAN_TESTEE_HOST_BIN"
-    assert testee.version_env == "REPOMAN_TESTEE_VERSION"
+    assert testee.min_version == "0.5.0"
+    assert REGISTRY["copy"].min_version == REGISTRY["git"].min_version == ""
     assert testee.status == ["report"]
 
 
```

### Dead registry fields (separate, optional patch)

`Manager.doctor` and `Manager.status` have no reader in `src/`. Only two test asserts read them. (verified: `grep -rnE "\.doctor|\.status" src tests`) I removed them in a scratch copy: 129 tests pass, ruff clean. Not applied to the main copy.
Not safe to remove: `nix_input` (read by `checks.py` `provisioned:` loop, tests cover it), `package` and `install="uv"` (the `uv:` rows and tests use them). (verified)

```diff
diff -ruN -x __pycache__ -x .pytest_cache -x .coverage /tmp/tw-rm/repoman/src/repoman/registry.py /tmp/tw-dead/src/repoman/registry.py
--- rm/src/repoman/registry.py
+++ /tmp/tw-dead/src/repoman/registry.py	2026-10-10 17:42:46.907117253 -0400
@@ -1,14 +1,13 @@
 """The RepoMan manager roster.
 
 Maps each manager key (used in the project manifest) to the console script that
-implements it, its tier, and the sub-commands RepoMan calls when aggregating
-``doctor`` / ``status``. RepoMan never models a manager's report — it only knows
+implements it and its tier. RepoMan never models a manager's report — it only knows
 *how to invoke* each one.
 """
 
 from __future__ import annotations
 
-from dataclasses import dataclass, field
+from dataclasses import dataclass
 
 
 @dataclass(frozen=True)
@@ -21,8 +20,6 @@
             the roster from ``REPOMAN_MANAGERS``, which the nix module exports.
         command: Console script name on PATH (e.g. ``"testee"``).
         tier: ``"core"`` | ``"publish"`` | ``"situational"``.
-        doctor: Args for this manager's doctor (every manager has one).
-        status: Args for a status-like read, or ``None`` if it has none.
         summary: One-line description for ``repoman managers``.
         nix_input: For an approach-B manager, the ``devenv.yaml`` input its nix
             module needs (presence-gated import); ``""`` for approach-A /
@@ -41,8 +38,6 @@
     command: str
     tier: str
     summary: str
-    doctor: list[str] | None = field(default_factory=lambda: ["doctor"])
-    status: list[str] | None = None
     skill: str = ""  # sub-skill name the entrypoint routes to (default: command)
     route_when: str = ""  # "when you want to…" cell in the routing table
     nix_input: str = ""  # devenv.yaml input the manager's approach-B nix module needs; "" = none
@@ -82,8 +77,6 @@
         "copyroom",
         "core",
         "Templating / scaffolding / convergence (Copier)",
-        doctor=["doctor"],  # copyroom 0.6+ ships `doctor` (rows: copier, git, cache, template-source)
-        status=["status"],
         route_when="scaffold a repo, pull template updates, or check template drift",
     ),
     "git": Manager(
@@ -91,7 +84,6 @@
         "gitman",
         "core",
         "Version control (native jj and gh; gitman opens workspaces)",
-        doctor=None,  # gitman 0.12 is work-only: its one command is `work`
         route_when="open a workspace with `gitman work`; use native jj and `gh` to describe, bookmark, push, and open a PR",
     ),
     "test": Manager(
@@ -99,7 +91,6 @@
         "testee",
         "core",
         "Verification (pytest / ruff / ty)",
-        status=["report"],
         route_when="verify code health and review the latest report",
         min_version="0.5.0",  # the host-wrapper model; see CHANGELOG 0.12.0
     ),
diff -ruN -x __pycache__ -x .pytest_cache -x .coverage /tmp/tw-rm/repoman/tests/test_registry.py /tmp/tw-dead/tests/test_registry.py
--- rm/tests/test_registry.py
+++ /tmp/tw-dead/tests/test_registry.py	2026-10-10 17:42:46.907507332 -0400
@@ -47,7 +47,6 @@
     git = REGISTRY["git"]
     assert "gitman work" in git.route_when
     assert "jj" in git.route_when and "gh" in git.route_when
-    assert git.doctor is None and git.status is None  # gitman 0.12 has only `work`
     for retired in ("land", "sync", "repair", "release", "undo"):
         assert retired not in git.route_when
 
@@ -82,7 +81,6 @@
     testee = REGISTRY["test"]
     assert testee.min_version == "0.5.0"
     assert REGISTRY["copy"].min_version == REGISTRY["git"].min_version == ""
-    assert testee.status == ["report"]
 
 
 def test_package_defaults_to_command():
```

## 2. Tests

How I ran them: `uv run --no-project --python 3.13 --with pytest --with pytest-cov --with pydantic --with typer --with jinja2 pytest -q` inside the copy. No devenv shell needed. (verified)

| State | Result |
|---|---|
| Trunk | 129 passed (verified) |
| Target code with trunk tests | 8 failed, 121 passed (verified) |
| Target code with fixed tests | 129 passed (verified) |

The 8 failures with old tests, and why (verified):

1. `test_checks::test_testee_path_must_match_the_host_binary`: the shadow check is gone.
2. `test_checks::test_testee_requires_a_pinned_version`: `REPOMAN_TESTEE_VERSION` is gone.
3. `test_cli::test_doctor_fails_when_testee_version_does_not_match`: message is now "needs 0.5.0 or later".
4. `test_modules_nix::test_manager_tasks_use_the_host_profile`: reads the deleted `testee.nix`.
5. `test_modules_nix::test_test_manager_sets_no_enter_test`: reads the deleted `testee.nix`.
6. `test_modules_nix::test_meta_module_keeps_the_consumer_venv_on_path_and_reads_no_closure`: asserts the removed export and `dirname`.
7. `test_modules_nix::test_manager_modules_receive_the_manifest_roster`: loops over `testee.nix`.
8. `test_registry::test_testee_uses_the_host_binary_and_pinned_version`: asserts removed fields.

Test diff size: +28 / -42 lines across `test_checks.py` (+12/-19), `test_cli.py` (+3/-7), `test_modules_nix.py` (+10/-13), `test_registry.py` (+3/-3). I added two cases (newer-than-minimum passes, unrecognized output fails). The "no `enterTest` in RepoMan" regression guard now holds by absence of the file. (verified: diff above)

Coverage gap that remains: no test runs Nix, so the Nix side was checked only by `devenv shell` and `devenv tasks list` below. (verified)

## 3. Shell PATH, with and without the rewrite

Method: `env -i` clean environment (the calling shell was inside the live repoman devenv shell and leaked `REPOMAN_TESTEE_*` and the live venv; the first runs were contaminated and discarded). PATH outside: `~/.nix-profile/bin:/etc/profiles/per-user/andrew/bin:/run/current-system/sw/bin`. Then `devenv shell -- bash /tmp/tw-logs/tw-probe2.sh`. Host profile holds `testee -> /nix/store/rs4i9...-testee-0.5.1/bin/testee`. (verified: `ls -l ~/.nix-profile/bin/testee`) Doctor ran via `uv run` with the shell PATH.

| Case | `which -a testee` (deduplicated) | `type testee` | `testee --version` | doctor rows |
|---|---|---|---|---|
| A. Trunk (rewrite), repoman root | `~/.nix-profile/bin/testee`, then `/nix/store/rs4i9...-testee-0.5.1/bin/testee` | `~/.nix-profile/bin/testee` | `testee 0.5.1` | `installed:test` OK; `version:test` OK (0.5.1 = 0.5.1) |
| B. Target (no rewrite), repoman root | store path first, then `~/.nix-profile/bin/testee` | store path | `testee 0.5.1` | `installed:test` OK (store path); `version:test` OK (needs 0.5.0 or later) |
| A'. Trunk, `tests/consumer-example` | same as A | same as A | `testee 0.5.1` | same as A |
| B'. Target, `tests/consumer-example` | same as B | same as B | `testee 0.5.1` | same as B |

PATH order (verified, repoman root):

- Trunk: `venv/bin`, `venv/bin`, `~/.nix-profile/bin`, devenv script dirs, `testee-0.5.1/bin`, git, patch, ...
- Target: `venv/bin`, `venv/bin`, devenv script dirs, `testee-0.5.1/bin`, git, patch, ... (`~/.nix-profile/bin` now sits at the tail, from the outer PATH)

Both cases print 0.5.1, because the host profile and the pin are the same store path. They are the same file. (verified)

Drift test (fake host `testee` that prints `testee 0.4.0`, first on the outer PATH):

- Trunk, `REPOMAN_TESTEE_HOST_BIN` pointed at the fake: `testee --version` = `testee 0.4.0`; doctor `FAIL version:test ... reports 0.4.0; pinned package requires 0.5.1`. The rewrite lets the host copy win. (verified)
- Target: `testee --version` = `testee 0.5.1`. The pinned store package wins over the fake host. Doctor says OK. (verified)

Reading:

- Without the rewrite, devenv `packages` (Testee's `packages = [ package ]`) beat the host profile. This matches the task note. (verified)
- Under the target, a host profile that is older or newer than the pin is invisible inside the shell. The shell always runs the pin. This is arguably the correct behavior for a project gate. (inferred) It removes the only host-vs-pin check. (verified)
- Outside a shell, the host profile is used and `min_version` checks it. (inferred; the code path is the same `shutil.which`)
- `devenv tasks list` target: `base:check -> repoman:lint`, `base:test -> testee:verify`; no `repoman:test`. Trunk lists `repoman:test:ci` and `testee:verify`. (verified)
- I did not run `testee verify --full` through `base:test`. (unknown) Testee's task runs the full gate, not the quick gate that `repoman:test` ran.

Note: the consumer fixture needs a sibling `../../../shellij` path input. I copied shellij to a temp dir for the run and removed it. (verified)

## 4. Doc and text changes needed

I drafted none of these except `AGENTS.md`. Each line is a change the target would need. (inferred from grep)

- `CHANGELOG.md`: add a new breaking entry (0.14.0). Note the removed env vars and tasks, the `min_version` field, and that 0.12.0 and 0.12.1 entries now read as history.
- `README.md:13`: no change.
- `README.md:144-148`: no change (`gate` still runs `testee verify --full`).
- `README.md:160-169` "Manager installation": drop "The Nix module and package use the same pinned Testee source", drop the `REPOMAN_TESTEE_HOST_BIN` sentence, say doctor checks `testee --version` against a minimum.
- `README.md:189`: replace "(the `repoman:test` task)" with "(or `testee:verify` from the Testee module)".
- `README.md:227` doctor table: `version:test` now means "the Testee on `PATH` reports the registry minimum or later".
- `CONCEPT.md:6-7`, `:98-100`, `:358`: already stale. Fix while here (testee is host-installed; the `dev` group has no testee; no closure).
- `CONCEPT.md:265-273` "One wrapper install model": rewrite. Remove "checks that the host wrapper reports the pinned package version".
- `CONCEPT.md:355`: `managers/` lists `testee.nix`. Remove it.
- `docs/SKILLS.md:90`: route text already differs from the registry. Align it.
- `docs/AGENT-FILES.md`: no change.
- `AGENTS.md:36`: done in the copy (`# testee:verify`).
- Router template `src/repoman/templates/entrypoint.SKILL.md.j2`: no change. It names no command. (verified)
- Registry `route_when` / `summary` for `test`: no change.
- `modules/devenv.nix` header comment: done in the copy.
- `devenv.nix:12-14` comment ("the HOST also runs the same tagged wrapper"): optional rewording.
- `tests/consumer-example/devenv.nix` comment "Testee's wrapper comes from the host": now wrong in-shell. Reword.
- Outside this repo: `template-py/README.md:82-90` and `template-py/copyroom.yml:28`.
- `SPIKE.md`: history. Leave it.

## 5. `base:test` in RepoMan's own `devenv.nix`

It should call Testee's own task: `"base:test".after = [ "testee:verify" ];` (done in the copy). (verified: task graph)

- Source: Testee's module defines `tasks."testee:verify".exec = "${package}/bin/testee verify --full"`. (verified: `git show 1c139ecb:nix/testee.nix`)
- Behavior change: `repoman:test` ran the quick profile (`testee verify`). `testee:verify` runs `--full`. `base:test` becomes the full gate. (verified)
- Alternative if the quick gate is wanted: define `"base:test".exec = "testee verify";` in `devenv.nix`. The task would then use the shell PATH, which resolves the pinned package. (inferred)
- Recommendation: use `testee:verify`. It adds no second implementation and matches `gate`.
