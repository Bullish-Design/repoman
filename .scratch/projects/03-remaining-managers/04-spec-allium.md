# Guide 04 — Wire the `spec` manager (allium-env / alliman) — **BLOCKED**

**Status: BLOCKED on allium-env's `02-cli-conductor-alignment` project, and carries a required
registry fix.** Unlike the other three, `spec` has a **wrong `command` in the registry today**
(`allium`, which collides with a third-party binary). This guide writes the repoman side in full,
names the prerequisite, and carries the exact registry command-name edit.

## Prerequisite / blocked-on (read this first)

**Sibling project:** `allium-env/.scratch/projects/02-cli-conductor-alignment/`
(`/home/andrew/Documents/Projects/allium-env/.scratch/projects/02-cli-conductor-alignment/README.md`
+ `01-alliman-cli.md`).

**Verified current state of allium-env** (`/home/andrew/Documents/Projects/allium-env`):

- **`pyproject.toml` is still the stub** — `name = "template-py"`; no `src/` package, no console
  script for a manager CLI.
- **`allium` is the third-party binary**, pinned from `juxt/allium-tools` **v3.2.3** and added to
  PATH by allium-env's `devenv.nix` (`alliumCliRelease`, fetched per-platform). It is a *spec* tool
  (`allium check/analyse`), **not** a family-conforming manager CLI and **has no `doctor` verb**.
- The repo already ships Allium's agent assets (`.skills/allium-entrypoint`, `.agents/skills/…`) via
  `scripts/install-codex-assets.sh` / `scripts/check-codex-assets-installed.sh`.

**The collision (why the registry is wrong):** `REGISTRY["spec"].command == "allium"`. If `spec`
were wired today, `repoman doctor` would run `allium doctor` against the **third-party** binary,
which has no such verb → garbage/usage error. The manager command **must** be a distinct name.

**Exact contract the alignment project must expose** (from its README's narrowed scope):

1. Replace the `template-py` stub with `[project.scripts] alliman = "alliman.cli:app"`, package in
   `src/alliman/`, installable into the devenv venv.
2. `alliman doctor` — **NEW** Pydantic `DoctorReport` that verifies **all expected skills + the
   `allium-entrypoint` + manifest + prompts** are installed (porting/strengthening
   `check-codex-assets-installed.sh`); `--json`; exit **`0`** ok / **`2`** infra (assets not
   installed). This is the verb `repoman doctor` calls.
3. `alliman install-skills` (delegates to the existing installer) and `alliman init` — repoman does
   **not** drive these; only `doctor`.
4. `0/1/2/3` contract honored. Allium's *spec* verbs (`allium check/analyse`) stay on the
   third-party binary and are **out of scope** for the manager CLI.

**Recommended command name: `alliman`** (fits the `*man` family, avoids the `allium` collision).
Whatever the alignment project picks, the registry must match it (§Step 4).

> **Do not build the alliman CLI here.** That's the sibling project's job.

## Once it lands, do X (the finish-the-last-mile summary)

When allium-env ships `alliman doctor` (exit 0/2) on PATH:

1. **Apply the registry command fix** (Step 4) — this is the one edit that can't wait and is the
   whole reason `spec` differs from `doc`.
2. Add `modules/managers/alliman.nix` (Step 1) + register it in imports (Step 2).
3. Add the `[managers.spec]` lock block (Step 3).
4. Add tests (Step 6) and run the consumer-example verification (Step 7).

## Target layout (repoman only — applied after the prereq lands)

```
repoman/
  src/repoman/registry.py           # (edit) spec command "allium" → "alliman"  ← REQUIRED
  modules/
    devenv.nix                      # (edit) add ./managers/alliman.nix to imports
    managers/
      alliman.nix                   # (new) gated on "spec"; repoman:spec:* tasks
  tests/
    consumer-example/repoman.lock   # (edit) add [managers.spec]
    test_registry.py                # (edit) assert spec command == "alliman" (regression guard)
    test_checks.py                  # (edit) spec lock/installed rows
    test_cli.py                     # (edit) spec in managers
```

## Step 1 — manager module `modules/managers/alliman.nix`

The third-party `allium` binary already arrives via allium-env's own `devenv.nix`. The `alliman`
console script (the manager CLI) arrives via the venv from the lock. So the repoman manager module
is the **pure-Python** `copyroom.nix`/`testee.nix` shape — no extra `packages`.

```nix
# RepoMan manager wiring: alliman (spec-driven agent assets — Allium).
#
# Imported unconditionally by ../devenv.nix; activates only when "spec" is in
# `repoman.managers`. The `alliman` console script (added by allium-env's CLI-alignment
# project) is installed into the venv by repoman-sync; its `doctor` verifies Allium's
# skill/prompt assets are installed. The third-party `allium` spec binary travels with
# allium-env's own devenv module, NOT here — repoman drives the manager CLI, not the tool.
{ lib, config, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "spec" cfg.managers;
  venvBin = "${config.devenv.state}/venv/bin";
in
{
  config = lib.mkIf enabled {
    tasks = {
      # alliman owns its own report; `repoman doctor` aggregates via the CLI.
      "repoman:spec:doctor".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/alliman doctor'';
    };
  };
}
```

> **Naming.** The module file and task namespace use the manager command (`alliman` / `spec`), not
> the third-party `allium`, to keep the collision impossible to reintroduce. If the alignment project
> chooses a different command name, rename the file, the `venvBin` invocation, and the registry edit
> (Step 4) together.

## Step 2 — register the import in `modules/devenv.nix`

```nix
  imports = [
    ./managers/testee.nix
    ./managers/copyroom.nix
    ./managers/gitman.nix
    ./managers/alliman.nix     # activates when "spec" is selected
  ];
```

`allManagers` already includes `"spec"`. No options change.

## Step 3 — lock entry (`tests/consumer-example/repoman.lock`)

The lock key is the manager key (`spec`); the package is allium-env's new dist name. Confirm the dist
name the alignment project sets in `pyproject.toml` (it replaces `template-py` — likely `alliman`):

```toml
[managers.spec]
package = "alliman"
source = "path:/home/andrew/Documents/Projects/allium-env"
```

Pure-Python ⇒ no native-dep pseudo-entry. (The third-party `allium` binary is provisioned by
allium-env's devenv at the nix layer, **not** via the lock — it is never a manager entry.)

## Step 4 — registry correctness — **REQUIRED EDIT**

This is the one mandatory `src/` change across all four guides. In `src/repoman/registry.py`, change
`spec`'s `command` from the colliding `allium` to the manager command:

```python
    "spec": Manager(
        "spec", "alliman", "situational",          # was: "allium" — collided with the 3rd-party binary
        "Spec-driven agent workflow (Allium)",
        route_when="write or check a behavioural spec",
    ),
```

Effects of the edit (all desirable):
- `aggregate.run_sub` shells out to `alliman doctor`, not the third-party `allium` (which has no
  `doctor`).
- `checks.run_self_check` checks `shutil.which("alliman")` for `installed:spec`.
- `skill` defaults to `command`, so it becomes `"alliman"`; the self-check looks for
  `<skills_dir>/alliman/SKILL.md`. If allium-env installs its manager skill under a different name
  (e.g. `allium-entrypoint`), set `skill="allium-entrypoint"` explicitly so `skill:spec:defers`
  lints the right file.

> Keep this edit **with** the rest of the spec wiring so `command` and the lock/module always change
> together — never land the registry rename ahead of the lib shipping `alliman`, or `installed:spec`
> FAILs for everyone selecting `spec`.

## Step 5 — CLI conformance

| repoman calls | actual invocation (after fix + prereq) | conforms? |
|---|---|---|
| `manager.doctor` | `alliman doctor` | must print a `DoctorReport` and exit `0`/`2` — **delivered by the alignment project** |
| `manager.status` | — | `status=None`; `repoman status` skips `spec` |

Until both the registry fix and the lib land, `alliman` is absent from PATH → `installed:spec` FAIL
and `run_sub` returns 127 → treated as `2`. Correct "blocked" signal.

## Step 6 — sub-skill

allium-env ships a rich skill set, including `allium-entrypoint`. The manager skill the alignment
project installs must carry the deferral footer *"For when to write a spec vs. verify vs. save, see
the `repoman` skill."* Align `REGISTRY["spec"].skill` with whatever dir name gets installed (Step 4
note) so `skill:spec:defers` lints the correct file. Sub-skill install remains the open question in
`docs/SKILLS.md`.

## Step 7 — tests + verification (after the prereq lands)

- **`tests/test_registry.py`** — regression guard for the rename:

  ```python
  def test_spec_command_is_not_the_thirdparty_binary():
      m = REGISTRY["spec"]
      assert m.command == "alliman"     # NOT "allium" (the juxt/allium-tools binary)
      assert m.tier == "situational" and m.status is None
  ```

- **`tests/test_checks.py`** — `spec` lock + installed rows (package `"alliman"`; `which("alliman")`
  stubbed), mirroring guide 01/02.
- **`tests/test_cli.py`** — `managers` lists `alliman`; `status` emits no `spec` section.
- **Verification (consumer-example):**

  ```bash
  cd tests/consumer-example
  #   repoman.managers = [ "copy" "git" "test" "spec" ];
  rm -f devenv.lock && rm -rf .devenv
  devenv shell -- repoman-sync                       # installs alliman into the venv
  devenv shell -- bash -c 'command -v alliman; command -v allium'   # both present, distinct
  devenv shell -- bash -c 'repoman doctor; echo exit=$?'
  #   → OK lock:spec   OK installed:spec   then "=== spec (alliman) ===" + alliman's report
  ```

## Risks

| Risk | Mitigation |
|---|---|
| Landing the registry `command` rename before `alliman` exists | `installed:spec` FAILs and `run_sub` 127s for everyone selecting `spec`. Land the rename **with** the lock + module, only after the lib ships (Step 4 note). |
| Re-introducing the `allium` collision | The module file, task namespace, and registry all use `alliman`; the regression test (Step 7) guards `command != "allium"`. |
| Manager skill installed under a name ≠ `alliman` | Set `REGISTRY["spec"].skill` to the installed dir name (e.g. `"allium-entrypoint"`) so `skill:spec:defers` lints it. |
| Confusing `alliman` (manager CLI) with `allium` (spec tool) in docs/tasks | Keep the split explicit everywhere: `alliman doctor` = asset/install health; `allium check/analyse` = spec work, out of repoman's scope. |
| Alignment project picks a different command name than `alliman` | Single source of truth is `REGISTRY["spec"].command`; rename the module file + lock package + tests to match in one change. |
