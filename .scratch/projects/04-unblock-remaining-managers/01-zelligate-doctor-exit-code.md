# Guide 01 — Make `zelligate doctor` honour the family exit contract

**Target repo: `zelligate` (`/home/andrew/Documents/Projects/zelligate`).** This is an upstream fix,
not a repoman edit. Copy this guide into zelligate's scratch (e.g.
`.scratch/projects/04-doctor-exit-code/`) and implement against the live `src/zelligate/cli.py`.

**Goal:** make `zelligate doctor` (and `zelligate doctor --json`) **exit non-zero when the session
surface is degraded**, under the `*man`-family `0/1/2/3` contract — so RepoMan's `repoman doctor`,
which calls the default `["doctor"]`, stops reporting a broken surface as green.

## The bug (verified against the live code)

`src/zelligate/cli.py`, `def doctor(...)` (≈L461). Three output paths, only one of which exits:

```python
    if quick:
        if not config.workspace_dir.exists():
            sys.exit(1)
        critical = [i for i in result.issues if i.severity == "error"]
        if critical:
            sys.exit(1)
        sys.exit(0)                      # --quick: honours 0/1 ✓

    if json_output:
        report = _build_doctor_json(config, result, daemon_running)
        print(json.dumps(report, indent=2))
        return                           # --json: ALWAYS exit 0  ✗

    # ── Rich formatted output ──
    console.print("[bold]Zelligate doctor[/bold]")
    ...
    # falls off the end                  # full report: ALWAYS exit 0  ✗
```

- `result` is a `DiscoveryResult` (`src/zelligate/discovery.py`); `result.issues` is
  `list[DiscoveryIssue]` and `DiscoveryIssue.severity: Literal["warning", "error"]` (L24–28).
  Workspace-missing and validation failures are already emitted as `severity="error"` issues
  (e.g. L67–80), so "an `error` issue exists" is the canonical "surface is broken" signal.
- The rich path also computes **state writability** inline (L499–508: `state_ok`) — a real failure
  mode that isn't a discovery issue, so the exit logic must check it too.
- RepoMan calls the **default** `["doctor"]` (registry `session` entry), i.e. the *rich* path — the
  one that never exits. That's why a degraded session reports green (`03-remaining-managers/
  01-session-zelligate.md` §Risks).

## Target layout (zelligate only)

```
zelligate/
  src/zelligate/cli.py        # (edit) add _doctor_exit_code() + _state_writable(); exit on all 3 paths
  tests/test_cli.py           # (edit) update the 2 --quick exit assertions; add 2 full/json exit tests
```

No new files, no dependency changes — pure CLI behaviour.

## The exit-code mapping (family `0/1/2/3`)

| Condition | Exit | Why |
|---|---|---|
| workspace dir missing / not a dir | `2` | infra/config — the surface can't function |
| state dir not creatable / not writable | `2` | infra/config |
| any `result.issues` with `severity == "error"` | `2` | infra/config (manifest/validation/discovery failure) |
| only `warning`-severity issues, or clean | `0` | informational — warnings don't fail the contract |

zelligate's doctor never makes a *domain* decision, so it never emits `1`; `3` is Typer's own usage
error. Environment/config faults all map to **`2`**, consistent with how the docman/alliman doctors
map "assets not installed" → `2` (their `02-cli-conductor-alignment` guides).

## Step 1 — factor out the state-writable check (one source of truth)

The rich path inlines state writability at L499–508. Pull it into a helper so the exit logic and the
report agree:

```python
def _state_writable(config: WorkbenchConfig) -> bool:
    """True if the state dir exists-and-is-writable, or can be created."""
    if not config.state_dir.exists():
        try:
            config.state_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        return True
    return os.access(config.state_dir, os.W_OK)
```

Then in the rich path replace the inline block with `state_ok = _state_writable(config)` (keep the
existing `state_icon`/`console.print` lines).

## Step 2 — add the exit-code helper

Place it next to `doctor` (after `_daemon_freshness`, before `def doctor`):

```python
def _doctor_exit_code(config: WorkbenchConfig, result: DiscoveryResult) -> int:
    """Worst-case exit code for a doctor run, under the *man family 0/1/2/3
    contract. Environment/config faults → 2 (infra); a clean or warning-only
    surface → 0. zelligate's doctor never emits a domain `1`.
    """
    if not (config.workspace_dir.exists() and config.workspace_dir.is_dir()):
        return 2
    if not _state_writable(config):
        return 2
    if any(issue.severity == "error" for issue in result.issues):
        return 2
    return 0
```

This is a strict superset of the current `--quick` logic (workspace + error issues) plus the
state-writability fault the rich path already surfaces but `--quick` ignored.

## Step 3 — exit on all three paths

Rewrite the top of `doctor` to compute the code once and apply it everywhere:

```python
    config = _get_config()
    result = discover(config)
    daemon_running = _is_daemon_running(config)
    exit_code = _doctor_exit_code(config, result)

    if quick:
        raise typer.Exit(exit_code)          # was: sys.exit(0/1)

    if json_output:
        report = _build_doctor_json(config, result, daemon_running)
        print(json.dumps(report, indent=2))
        raise typer.Exit(exit_code)          # was: return (always 0)
```

…and at the **very end** of the rich path (after the Tailscale suggestions block):

```python
    raise typer.Exit(exit_code)              # was: fell off the end (always 0)
```

`raise typer.Exit(0)` is a clean no-op success, so the happy path is unchanged for callers. (Use
`typer.Exit` rather than `sys.exit` to match the rest of the family's CLIs; `sys.exit(exit_code)`
also works if you prefer to minimise the diff.)

> **Optional (machine consumers):** add `"exit_code": _doctor_exit_code(config, result)` to the dict
> built in `_build_doctor_json` (≈L599) so `--json` consumers can read the verdict without re-deriving
> it. Not required for the RepoMan contract.

## Step 4 — tests (`tests/test_cli.py`)

The file already has a rich doctor suite. Two existing assertions change because the contract moved
from `1` to `2`, and the report paths now exit on errors:

1. **`test_doctor_quick_fails_on_critical_issues`** (≈L858) — docstring says "exits 1"; assert the
   new contract value:
   ```python
   assert result.exit_code == 2          # was: == 1  (infra/config, not a domain finding)
   ```
   Update the docstring to "exits 2".
2. **`test_doctor_quick_fails_on_missing_workspace`** (≈L543) — if it asserts `== 1`, change to
   `== 2`; if it asserts `!= 0`, it still passes (leave it).
3. **`test_doctor_shows_issues`** (≈L620) — this seeds `error`-severity discovery issues and runs the
   **full** (non-`--quick`) report. It currently passes only because the full path always exited 0;
   after the fix it exits **2**. Update its exit assertion to `== 2` (keep the stdout assertions that
   verify the issues are printed — the report still renders before exit).

Add two tests for the previously-unguarded paths (mirror the env/`runner` setup of the neighbouring
doctor tests):

```python
def test_doctor_full_exits_2_on_error_issue(self, runner, tmp_path, monkeypatch):
    """The full report path exits 2 (not 0) when an error-severity issue exists."""
    # ...same seeding as test_doctor_shows_issues...
    result = runner.invoke(app, ["doctor"], env=env)
    assert result.exit_code == 2
    assert "ERROR" in result.stdout              # report still rendered

def test_doctor_json_exits_2_on_error_issue(self, runner, tmp_path, monkeypatch):
    """--json exits 2 when an error-severity issue exists, and still prints JSON."""
    result = runner.invoke(app, ["doctor", "--json"], env=env)
    assert result.exit_code == 2
    json.loads(result.stdout)                    # still valid JSON
```

Leave the happy-path tests (`test_doctor_full_format`, `test_doctor_json`,
`test_doctor_quick_passes`, the warning-only tests) asserting `exit_code == 0` — warnings and a valid
workspace must stay green. Audit any other `["doctor"...]` test that seeds an error/missing-workspace
and currently relies on exit 0.

Run: `devenv shell -- pytest tests/test_cli.py` (zelligate is a devenv repo — use its shell).

## Verification

```bash
cd /home/andrew/Documents/Projects/zelligate
# Degraded: point at a workspace that doesn't exist → expect exit 2 on all paths.
devenv shell -- bash -c 'ZELLIGATE_WORKSPACE_DIR=/nonexistent zelligate doctor; echo exit=$?'        # exit=2
devenv shell -- bash -c 'ZELLIGATE_WORKSPACE_DIR=/nonexistent zelligate doctor --json; echo exit=$?' # exit=2
devenv shell -- bash -c 'ZELLIGATE_WORKSPACE_DIR=/nonexistent zelligate doctor --quick; echo exit=$?'# exit=2
# Healthy: a real, writable workspace with no error issues → exit 0 on all paths.
devenv shell -- bash -c 'mkdir -p /tmp/ws && ZELLIGATE_WORKSPACE_DIR=/tmp/ws zelligate doctor; echo exit=$?' # exit=0
```

The bar: the report still prints in full on the degraded run (it's a report, not a hard error), but
the **exit code is now `2`** instead of `0`.

## Downstream (RepoMan) — no code change, one doc touch-up

- RepoMan needs **no edit**: `REGISTRY["session"].doctor` defaults to `["doctor"]`, and
  `aggregate.run_sub` / `aggregate.worst_exit` already propagate whatever the sub-doctor returns.
  Once this lands, a degraded session correctly drives `repoman doctor`'s aggregate to `2`.
- The optional mitigation in `03-remaining-managers/01-session-zelligate.md` §Risks
  (`doctor=["doctor", "--quick"]`) is now **unnecessary** — keep the readable default `["doctor"]`.
- Re-run that guide's consumer-example verification with `ZELLIGATE_WORKSPACE_DIR` pointed at a
  missing dir to confirm `repoman doctor` surfaces `exit=2` for the session section. Then strike the
  "always exits 0" line from guide 01's Risks table (gap closed).

## Risks

| Risk | Mitigation |
|---|---|
| **`--quick` exit changes `1 → 2`** on failure — anything scripting `zelligate doctor --quick` and matching exactly `1` would break. | Deliberate: `2` is the family's infra/config code and `--quick` should agree with the report paths. Callers should test `!= 0`, not `== 1`. Call this out in the zelligate changelog. |
| Happy path accidentally exits non-zero (e.g. `typer.Exit(0)` misread) | `typer.Exit(0)` is a success no-op; the happy-path tests (`test_doctor_*` valid-setup) guard it. |
| A legitimately empty workspace (`No enabled repos`) wrongly fails | "No enabled repos" is a `warning`, not an `error`, and the workspace dir still exists → `_doctor_exit_code` returns `0`. Verified: warnings never escalate. |
| State-dir check has a side effect (creates the dir) | Pre-existing behaviour — the rich path already `mkdir`s it (L501–502); the helper just centralises it. No new side effect. |
| Other doctor tests silently depended on "always 0" | Step 4 names the three that change; audit the rest of the `doctor` suite for any that seed an error/missing workspace and assert `== 0`. |
