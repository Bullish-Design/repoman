# Guide 02 — Wire the `agent` manager (mypi-agent)

**Status: READY — implementable now.** mypi-agent ships a conforming CLI today; this is pure
repoman-side composition. **Goal:** make `repoman.managers = [ … "agent" ]` install `mypi` into the
venv, provision `secretspec`, and have `repoman doctor` / `repoman status` drive `mypi doctor` /
`mypi paths` under the `0/1/2/3` contract.

Build to the depth/shape of `.scratch/projects/02-devman-module/01-devman-implementation.md`.

## What's already true (verified against the live repo)

`/home/andrew/Documents/Projects/mypi-agent`:

- **Console script:** `pyproject.toml` → `[project.scripts] mypi = "mypi_agent.cli:main"`. The
  command is **`mypi`**, not `mypi-agent` — registry already has this right.
- **`mypi doctor`** (`src/mypi_agent/cli.py`): `--json`; `raise typer.Exit(code=result.exit_code)`
  where `DoctorResult.exit_code = 1 if computed_error_count > 0 else 0` (`src/mypi_agent/doctor.py`).
  Binary `0/1`, which maps cleanly onto the contract (`1` = domain finding).
- **`mypi paths`** (`--json`): prints the resolved per-repo paths; exit 0.
- Other verbs (`sync`, `needs-sync`, `agent`, `secretspec-setup`, `secrets …`) exist but are **not**
  driven by repoman — only `doctor`/`paths` are in the registry.
- **Pure-Python deps:** `pydantic`, `typer` — **no native build** ⇒ no pseudo-entry.
- The registry already maps `agent → mypi` with `doctor=["doctor"]` (default) and
  `status=["paths"]`. **No registry change needed.**

> **Project-root requirement (verified).** `mypi doctor`/`paths` call `Paths.discover()`, which walks
> from cwd for `devenv.nix`/`devenv.yaml` (or honors `MYPI_PROJECT_ROOT`); otherwise it raises
> *"mypi must be run inside a devenv-managed project"* and exits 1. RepoMan runs the manager inside
> the consumer's devenv shell, whose root has `devenv.nix` — so this is satisfied. The
> `repoman:agent:*` tasks below `cd "$DEVENV_ROOT"` to guarantee it.

> **First-run behaviour (expected, not a bug).** Until `mypi sync` has installed the Pi runtime,
> `mypi doctor` reports errors and exits **1**, which `repoman doctor` surfaces as exit 1 (domain
> decision: "the agent runtime isn't set up — run `mypi sync`"). That is correct conductor behaviour;
> repoman must **not** auto-run `mypi sync`. See Step 1.

mypi-agent's own `modules/pi-agent.nix` does heavy shell-entry bootstrap (`mypi sync`,
`secretspec-setup`, Telegram install). RepoMan's manager module deliberately does **none** of that —
it only puts `mypi` on PATH (venv) and provisions the `secretspec` binary the secrets verbs need.

## Target layout (repoman only)

```
repoman/
  modules/
    devenv.nix                      # (edit) add ./managers/mypi.nix to imports
    managers/
      mypi.nix                      # (new) gated on "agent"; pkgs.secretspec + repoman:agent:* tasks
  tests/
    consumer-example/repoman.lock   # (edit) add [managers.agent]
    test_registry.py                # (edit) assert agent entry shape
    test_checks.py                  # (edit) agent lock/installed rows
    test_cli.py                     # (edit) agent in managers / status routing
```

## Step 1 — manager module `modules/managers/mypi.nix`

Mirror `gitman.nix` for the system-package shape (here `pkgs.secretspec`), but **keep it minimal** —
no bootstrap, no `enterShell`. The `mypi` console script arrives via the venv from the lock.

```nix
# RepoMan manager wiring: mypi-agent (coding-agent runtime + per-repo secrets — Pi).
#
# Imported unconditionally by ../devenv.nix; activates only when "agent" is in
# `repoman.managers`. The `mypi` console script is pure-Python and installed into the venv
# by repoman-sync; this module additionally provisions `secretspec` (the binary mypi's
# secrets verbs drive). DELIBERATELY minimal: it does NOT replicate mypi-agent's own
# pi-agent.nix shell-entry bootstrap (mypi sync / secretspec-setup) — repoman is pass-through
# and lets the user drive `mypi sync` when they want the runtime. Gated on "agent", so repos
# without it never pull secretspec.
{ pkgs, lib, config, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "agent" cfg.managers;
  venvBin = "${config.devenv.state}/venv/bin";
in
{
  config = lib.mkIf enabled {
    packages = [ pkgs.secretspec ];

    tasks = {
      # cd into the project root so mypi's Paths.discover() finds devenv.nix.
      # mypi owns its own report; `repoman status`/`doctor` aggregate via the CLI.
      "repoman:agent:status".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/mypi paths'';
      "repoman:agent:doctor".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/mypi doctor'';
    };
  };
}
```

> **If `pkgs.secretspec` is unavailable in the consumer's pinned nixpkgs,** treat it like gitman's
> maturin/Rust note: provision it from the input that already ships it (mypi-agent's own devenv pins
> `secretspec`; reuse that source) rather than dropping the dependency. `mypi doctor`/`paths`
> themselves don't require `secretspec` to *run* — only the `secrets` verbs do — so verification
> (Step "Verification") still passes if provisioning slips, but the secrets surface won't work.

## Step 2 — register the import in `modules/devenv.nix`

```nix
  imports = [
    ./managers/testee.nix
    ./managers/copyroom.nix
    ./managers/gitman.nix
    ./managers/mypi.nix        # contributes pkgs.secretspec when "agent" is selected
  ];
```

`allManagers` already includes `"agent"`. No options change.

## Step 3 — lock entry (`tests/consumer-example/repoman.lock`)

Pure-Python ⇒ a single plain block. **Note the key/package mismatch is intentional:** the lock key
is the manager *key* (`agent`), the package is the PyPI/dist name (`mypi-agent`), and the console
script is `mypi`:

```toml
[managers.agent]
package = "mypi-agent"
source = "path:/home/andrew/Documents/Projects/mypi-agent"
```

No native-dep pseudo-entry.

## Step 4 — registry correctness (confirm, no change)

`REGISTRY["agent"]` is already correct:

```python
"agent": Manager(
    "agent", "mypi", "situational",
    "Coding-agent runtime + secrets (Pi)",
    status=["paths"],
    route_when="manage the coding-agent runtime or secrets",
),
```

`command="mypi"` (the console script, **not** the dist name), `doctor=["doctor"]`,
`status=["paths"]`, `skill` defaults to `"mypi"`. Assert it in tests; don't edit.

## Step 5 — CLI conformance

| repoman calls | actual invocation | conforms? |
|---|---|---|
| `manager.doctor` | `mypi doctor` | prints report; exits `0` ok / `1` if errors (`result.exit_code`) ✓ |
| `manager.status` | `mypi paths` | prints resolved paths; exits 0 ✓ |

Both honor the contract end-to-end via `raise typer.Exit(code=…)`. `aggregate.worst_exit` treats the
doctor's `1` as a domain finding, `2`/unavailable as infra — no upstream change needed.

## Step 6 — sub-skill

mypi-agent ships no installed `<skills_dir>/mypi/SKILL.md` (its `.agents/skills/` holds vendored
Allium/Pi skills). The `skill:agent:defers` self-check therefore **does not fire**. If mypi later
ships an agent `SKILL.md`, it must carry the footer *"For when to run the agent vs. verify vs. save,
see the `repoman` skill."*

## Step 7 — tests (repoman)

- **`tests/test_registry.py`**:

  ```python
  def test_agent_entry_shape():
      m = REGISTRY["agent"]
      assert m.command == "mypi"            # console script, not the dist name
      assert m.tier == "situational"
      assert m.doctor == ["doctor"] and m.status == ["paths"]
  ```

- **`tests/test_checks.py`** (mirror the existing lock/installed tests):

  ```python
  def test_agent_lock_and_installed_ok(tmp_path, monkeypatch):
      (tmp_path / "repoman.lock").write_text(
          _GOOD_LOCK + '[managers.agent]\npackage="mypi-agent"\nsource="path:/x"\n'
      )
      monkeypatch.setattr(checks.shutil, "which", lambda c: "/usr/bin/" + c)
      result = run_self_check([REGISTRY["agent"]], str(tmp_path), ".claude/skills")
      assert _names(result)["lock:agent"].level == "ok"
      assert _names(result)["installed:agent"].level == "ok"
  ```

  (Note: `installed:agent` checks `shutil.which("mypi")` — the *command*, not the package name — so
  the `which` stub above resolves it correctly.)

- **`tests/test_cli.py`**:

  ```python
  def test_managers_lists_agent(monkeypatch):
      monkeypatch.setenv("REPOMAN_MANAGERS", "agent")
      result = runner.invoke(app, ["managers"])
      assert result.exit_code == 0 and "mypi" in result.stdout
  ```

Run: `devenv shell -- pytest`.

## Verification (consumer-example)

Heavy steps in the background; poll the log.

```bash
cd tests/consumer-example
# add "agent" to repoman.managers in devenv.nix:
#   repoman.managers = [ "copy" "git" "test" "agent" ];
rm -f devenv.lock && rm -rf .devenv

devenv shell -- repoman-sync                         # installs mypi into venv + provisions secretspec
devenv shell -- bash -c 'command -v mypi && command -v secretspec'

devenv shell -- bash -c 'repoman doctor; echo exit=$?'
#   → self-check: OK lock:agent   OK installed:agent
#   → "=== agent (mypi) ===" then mypi's own doctor report.
#   exit may be 1 if the Pi runtime isn't synced yet (domain finding) — that is EXPECTED;
#   run `devenv shell -- mypi sync` to set the runtime up, after which doctor exits 0.
devenv shell -- bash -c 'repoman status'             # includes "=== agent (mypi) ===" + resolved paths
```

`lock:agent` + `installed:agent` green is the bar for "wired". A doctor exit of `1` on a fresh repo
(runtime not synced) is correct, not a verification failure.

## Risks

| Risk | Mitigation |
|---|---|
| `repoman doctor` exits 1 on a fresh agent repo (Pi not synced) and looks like a failure | Documented as expected (Step 1, Verification): `1` = domain finding "run `mypi sync`". RepoMan must not auto-sync; keep pass-through. |
| `secretspec` missing from the consumer's nixpkgs pin | Provision from the input that ships it (mypi-agent's devenv), per Step 1 note. `doctor`/`paths` still run without it; only the secrets surface degrades. |
| Module accidentally replicates mypi's bootstrap (double `mypi sync` on entry) | The module is intentionally minimal — **no `enterShell`/bootstrap**. Leave runtime setup to the user / mypi's own module if that repo also imports it. |
| `mypi paths`/`doctor` run outside a devenv-managed dir → exit 1 | `repoman:agent:*` tasks `cd "$DEVENV_ROOT"`; `aggregate.run_sub` inherits the devenv shell cwd. Both satisfy `Paths.discover()`. |
| Future agent `SKILL.md` lands without the deferral footer | `skill:agent:defers` WARN fires once it's installed; fix is the one-line footer per `docs/SKILLS.md`. |
