# Guide 01 — Wire the `session` manager (zelligate)

**Status: READY — implementable now.** zelligate ships a conforming CLI today; this is pure
repoman-side composition. **Goal:** make `repoman.managers = [ … "session" ]` install `zelligate`
into the venv, provision Zellij, and have `repoman doctor` / `repoman status` drive
`zelligate doctor` / `zelligate list` under the `0/1/2/3` contract.

Build to the depth/shape of `.scratch/projects/02-devman-module/01-devman-implementation.md`.

## What's already true (verified against the live repo)

`/home/andrew/Documents/Projects/zelligate`:

- **Console script:** `pyproject.toml` → `[project.scripts] zelligate = "zelligate.cli:main"`
  (also `zelligated` for the daemon — not wired here).
- **`zelligate doctor`** (`src/zelligate/cli.py`): `--quick` (exit-code-only health) and `--json`
  (machine report). Prints workspace/state/tools/repos/ports/daemon status.
- **`zelligate list`** (`--json`): lists enabled repos.
- **Pure-Python deps:** `pydantic`, `typer`, `rich` — **no native build** ⇒ no pseudo-entry.
- The registry already maps `session → zelligate` with `doctor=["doctor"]` (default) and
  `status=["list"]`. **No registry change needed.**

> ⚠️ **Verified conformance gap (non-blocking).** The *full* `zelligate doctor` and
> `zelligate doctor --json` paths **always exit 0**; only `zelligate doctor --quick` returns `0/1`
> on `severity == "error"` issues. RepoMan calls the default `["doctor"]`, so a degraded session
> surface still reports green to `repoman doctor`. This is a zelligate bug, not a repoman one — it
> does not block wiring. See §Risks for the upstream fix and the optional repoman-side mitigation.

zelligate's own `modules/devenv.nix` is a **workbench-exposure** module (`zelligate.enable`,
`name`, `port`) — it does *not* install the CLI or Zellij. RepoMan's manager module owns both.

## Target layout (what this guide changes — repoman only)

```
repoman/
  modules/
    devenv.nix                      # (edit) add ./managers/zelligate.nix to imports
    managers/
      zelligate.nix                 # (new) gated on "session"; pkgs.zellij + repoman:session:* tasks
  tests/
    consumer-example/repoman.lock   # (edit) add [managers.session]
    test_registry.py                # (edit) assert session entry shape
    test_checks.py                  # (edit) session lock/installed rows
    test_cli.py                     # (edit) session in managers / status routing
```

## Step 1 — manager module `modules/managers/zelligate.nix`

Mirror `modules/managers/gitman.nix` (it's the precedent for a manager that contributes a **system
package**), but the package is `pkgs.zellij` rather than a Rust toolchain. The `zelligate` console
script itself arrives via the venv (`repoman-sync` installs it from the lock), so the module only
adds the binary the session surface drives and the `repoman:*` task namespace.

```nix
# RepoMan manager wiring: zelligate (live terminal / session surface — Zellij).
#
# Imported unconditionally by ../devenv.nix; activates only when "session" is in
# `repoman.managers`. The `zelligate` console script is pure-Python and installed into
# the venv by repoman-sync; this module additionally provisions the Zellij binary the
# session surface drives (gated on "session", so repos without it never pull Zellij —
# the same discipline gitman uses for the Rust toolchain).
{ pkgs, lib, config, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "session" cfg.managers;
  venvBin = "${config.devenv.state}/venv/bin";
in
{
  config = lib.mkIf enabled {
    # System dependency: Zellij. zelligate shells out to `zellij` for session ops; its
    # doctor reports `zellij` not-found rather than failing, but the surface is unusable
    # without it, so provision it whenever "session" is selected.
    packages = [ pkgs.zellij ];

    tasks = {
      # zelligate owns its own report; `repoman status`/`doctor` aggregate via the CLI.
      "repoman:session:status".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/zelligate list'';
      "repoman:session:doctor".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/zelligate doctor'';
    };
  };
}
```

> **Config note (situational).** `zelligate` reads `ZELLIGATE_WORKSPACE_DIR` (default `/workspaces`)
> via `WorkbenchConfig.from_env()`. With defaults, `zelligate list` returns an empty roster and
> `zelligate doctor` reports the workspace as not-found — both still **exit 0**, so verification
> passes. Do **not** hard-code a workspace in this module; session is situational and the consumer
> sets `ZELLIGATE_WORKSPACE_DIR` (e.g. via `env` in their own `devenv.nix`) when they actually use
> the surface. Adding an opt-in `repoman.session.workspaceDir` option is a possible follow-up, not
> part of this wiring.

## Step 2 — register the import in `modules/devenv.nix`

Add the module to `imports` (it self-gates on `"session"`):

```nix
  imports = [
    ./managers/testee.nix
    ./managers/copyroom.nix
    ./managers/gitman.nix
    ./managers/zelligate.nix   # contributes pkgs.zellij when "session" is selected
  ];
```

`allManagers` in `modules/devenv.nix` already includes `"session"`, so the enum accepts it — no
options change.

## Step 3 — lock entry (`tests/consumer-example/repoman.lock`)

zelligate is pure-Python ⇒ a single plain block, **no native-dep pseudo-entry**:

```toml
[managers.session]
package = "zelligate"
source = "path:/home/andrew/Documents/Projects/zelligate"
```

(Fleet/CI locks use the `git+https://…@vX.Y.Z` source form, per the header comment in that file.)

## Step 4 — registry correctness (confirm, no change)

`REGISTRY["session"]` in `src/repoman/registry.py` is already correct:

```python
"session": Manager(
    "session", "zelligate", "situational",
    "Live terminal / session surface (Zellij)",
    status=["list"],
    route_when="open a live terminal/session for this repo",
),
```

`doctor` defaults to `["doctor"]` (the dataclass default), `skill` defaults to `"zelligate"`.
Nothing to edit — just assert it in tests (Step 7).

## Step 5 — CLI conformance

| repoman calls | actual invocation | conforms? |
|---|---|---|
| `manager.doctor` | `zelligate doctor` | prints a full report; **always exits 0** (gap — see Risks) |
| `manager.status` | `zelligate list` | prints the repo roster; exits 0 |

Both verbs exist, print a report, and run with default env. `aggregate.run_sub` streams their output
through and collapses the exit. The only deviation is the doctor exit-code gap (Risks §1).

## Step 6 — sub-skill

zelligate ships no installed `<skills_dir>/zelligate/SKILL.md` (its `.agents/skills/` holds vendored
Allium/Pi skills, not a session skill). The `skill:session:defers` self-check therefore **does not
fire** — `run_self_check` `continue`s when the sub-skill file is absent. Nothing to do here; if
zelligate later ships a session `SKILL.md`, it must carry the footer *"For when to open a session vs.
verify vs. save, see the `repoman` skill."* (per `docs/SKILLS.md`).

## Step 7 — tests (repoman)

- **`tests/test_registry.py`** — assert the session entry shape:

  ```python
  def test_session_entry_shape():
      m = REGISTRY["session"]
      assert m.command == "zelligate"
      assert m.tier == "situational"
      assert m.doctor == ["doctor"] and m.status == ["list"]
  ```

- **`tests/test_checks.py`** — session lock + installed rows (mirror the existing
  `test_uninstalled_manager_fails` / `test_native_pseudo_entry_satisfies_base_manager`):

  ```python
  def test_session_lock_and_installed_ok(tmp_path, monkeypatch):
      (tmp_path / "repoman.lock").write_text(
          _GOOD_LOCK + '[managers.session]\npackage="zelligate"\nsource="path:/x"\n'
      )
      monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
      result = run_self_check([REGISTRY["session"]], str(tmp_path), ".claude/skills")
      assert _names(result)["lock:session"].level == "ok"
      assert _names(result)["installed:session"].level == "ok"
  ```

- **`tests/test_cli.py`** — `managers` lists it and `status` routes to it (extend `_healthy_repo`,
  which already builds a lock from the manager keys it's given):

  ```python
  def test_managers_lists_session(monkeypatch):
      monkeypatch.setenv("REPOMAN_MANAGERS", "session")
      result = runner.invoke(app, ["managers"])
      assert result.exit_code == 0 and "zelligate" in result.stdout
  ```

Run: `devenv shell -- pytest`.

## Verification (consumer-example)

Heavy steps (`repoman-sync` builds a venv + pulls Zellij) — run them in the background and poll the
log; never block the shell.

```bash
cd tests/consumer-example
# add "session" to repoman.managers in devenv.nix:
#   repoman.managers = [ "copy" "git" "test" "session" ];
rm -f devenv.lock && rm -rf .devenv                 # module/package set changed

devenv shell -- repoman-sync                         # installs zelligate into venv + provisions zellij
devenv shell -- bash -c 'command -v zelligate && command -v zellij'

devenv shell -- bash -c 'repoman doctor; echo exit=$?'
#   → self-check shows: OK lock:session   OK installed:session
#   → "=== session (zelligate) ===" followed by zelligate's own report
devenv shell -- bash -c 'repoman status'             # includes "=== session (zelligate) ===" + repo list
```

`lock:session` and `installed:session` green is the bar for "wired". (The session sub-doctor exiting
0 even when degraded is the known gap, not a verification failure.)

## Risks

| Risk | Mitigation |
|---|---|
| **`zelligate doctor` always exits 0** (full/`--json` paths) — a broken session surface reports green to `repoman doctor`. | Upstream fix in zelligate: make non-`--quick` `doctor` `sys.exit` on the worst issue severity (`error` → `2`, else `0`), matching the family `0/1/2/3` contract. *Optional* repoman-side mitigation until then: set `doctor=["doctor", "--quick"]` in the registry — but that suppresses the report text, so prefer the upstream fix and keep the readable default. Track in zelligate's backlog. |
| Zellij pulled into repos that never open a session | Gated on `elem "session" cfg.managers` (Step 1) — same discipline as gitman's Rust toolchain. |
| `ZELLIGATE_WORKSPACE_DIR` default `/workspaces` confuses a first run | Documented as situational (Step 1 note); `list`/`doctor` still exit 0 with defaults, so verification is unaffected. Consumer sets the env when using the surface. |
| Future zelligate session `SKILL.md` lands without the deferral footer | The self-check lints it the moment it's installed (`skill:session:defers` WARN); fix is the one-line footer per `docs/SKILLS.md`. |
| `zelligated` daemon assumed by `list`/`doctor` | Both verbs fall back to a live `discover()` when no daemon status file is fresh (`_get_repos`), so they run without the daemon; no daemon wiring required. |
