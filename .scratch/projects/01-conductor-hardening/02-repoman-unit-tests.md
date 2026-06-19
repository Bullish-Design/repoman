# Guide 2 — Unit tests for the `repoman` package

**Goal:** give the `repoman` Python package a real test suite. It currently has **zero**
tests (the old "GitHub syncer" suite was deleted in the pivot), yet every other manager in
the family ships one. The conductor's logic is almost entirely **pure functions**, so this
is cheap, high-value hygiene.

## What's testable (and how hard)

| Module | Surface | Difficulty |
|---|---|---|
| `registry.py` | `REGISTRY`, `Manager.__post_init__`, `DEFAULT_MANAGERS`, `SPINE` | trivial (pure data) |
| `skills.py` | `build_spine`, `render_entrypoint`, `install_entrypoint` | easy (pure + tmp file) |
| `aggregate.py` | `worst_exit`, `run_sub` | easy (`worst_exit` pure; `run_sub` via monkeypatch) |
| `cli.py` | `managers` / `doctor` / `status` / `install-skills` | easy (`typer.testing.CliRunner`) |

## Setup

- Tests live in `tests/` (pyproject already sets `testpaths=["tests"]`,
  `pythonpath=["src"]`, `--cov=repoman`). `tests/consumer-example/` has no `test_*.py`, so
  it won't be collected — leave it.
- Deps already present: `pytest`, `pytest-cov` in `[project.optional-dependencies].dev`.
  `typer.testing.CliRunner` needs nothing extra (ships with typer).
- Run: `devenv shell -- pytest` (or the repo's `test` script).

## Test files

### `tests/test_registry.py`

```python
from repoman.registry import REGISTRY, DEFAULT_MANAGERS, SPINE, Manager

def test_keys_match_their_entry():
    for key, m in REGISTRY.items():
        assert m.key == key

def test_skill_defaults_to_command():
    # Manager.__post_init__ fills skill from command when omitted.
    assert Manager("x", "xcli", "core", "s").skill == "xcli"
    assert Manager("x", "xcli", "core", "s", skill="custom").skill == "custom"

def test_default_managers_are_registered():
    assert set(DEFAULT_MANAGERS) <= set(REGISTRY)

def test_tiers_are_known():
    assert {m.tier for m in REGISTRY.values()} <= {"core", "publish", "situational"}

def test_spine_keys_are_registered_or_none():
    for _label, key in SPINE:
        assert key is None or key in REGISTRY

def test_core_managers_present():
    assert {"copy", "git", "test"} <= set(REGISTRY)
```

### `tests/test_aggregate.py`

```python
import repoman.aggregate as agg
from repoman.aggregate import SubResult, worst_exit
from repoman.registry import REGISTRY

def _r(code, available=True):
    return SubResult("m", ["m"], code, available)

def test_worst_exit_severity_order():
    assert worst_exit([_r(0), _r(1), _r(0)]) == 1
    assert worst_exit([_r(1), _r(2)]) == 2
    assert worst_exit([_r(0), _r(3)]) == 3
    assert worst_exit([]) == 0

def test_unavailable_counts_as_infra():
    assert worst_exit([_r(0, available=False)]) == 2

def test_unknown_code_maps_to_infra():
    assert worst_exit([_r(127)]) == 2

def test_run_sub_missing_command_is_unavailable(monkeypatch):
    monkeypatch.setattr(agg.shutil, "which", lambda _c: None)
    res = agg.run_sub(REGISTRY["test"], ["doctor"])
    assert res.available is False and res.exit_code == 127

def test_run_sub_invokes_present_command(monkeypatch):
    monkeypatch.setattr(agg.shutil, "which", lambda _c: "/usr/bin/" + _c)
    class P: returncode = 1
    monkeypatch.setattr(agg.subprocess, "run", lambda cmd: P())
    res = agg.run_sub(REGISTRY["test"], ["doctor"])
    assert res.available is True and res.exit_code == 1
```

### `tests/test_skills.py`

```python
from repoman.registry import REGISTRY
from repoman.skills import build_spine, render_entrypoint, install_entrypoint

def test_spine_only_enabled_plus_change():
    assert build_spine({"copy", "test"}) == "scaffold → change → verify"
    assert build_spine({"test"}) == "change → verify"
    assert build_spine({"copy", "git", "test"}) == "scaffold → change → verify → save"

def test_change_step_always_present():
    assert "change" in build_spine(set())

def test_render_only_names_enabled_managers():
    out = render_entrypoint([REGISTRY["copy"], REGISTRY["test"]], ".claude/skills")
    assert "copy test" in out               # managers line
    assert "copyroom" in out and "testee" in out
    assert "gitman" not in out              # not enabled → not routed
    assert "{{" not in out                  # StrictUndefined: nothing left unrendered
    assert ".claude/skills" in out

def test_install_writes_to_skills_dir(tmp_path):
    dest = install_entrypoint([REGISTRY["test"]], ".claude/skills", str(tmp_path))
    assert dest == tmp_path / ".claude/skills" / "repoman" / "SKILL.md"
    assert dest.read_text().startswith("---\nname: repoman")
```

### `tests/test_cli.py`

```python
from typer.testing import CliRunner
from repoman.cli import app

runner = CliRunner()

def test_managers_lists_enabled(monkeypatch):
    monkeypatch.setenv("REPOMAN_MANAGERS", "copy test")
    result = runner.invoke(app, ["managers"])
    assert result.exit_code == 0
    assert "copyroom" in result.stdout and "testee" in result.stdout
    assert "gitman" not in result.stdout

def test_doctor_skips_managers_without_doctor(monkeypatch):
    # copy (copyroom) has doctor=None → skipped; with no others installed, exit 0.
    monkeypatch.setenv("REPOMAN_MANAGERS", "copy")
    result = runner.invoke(app, ["doctor"])
    assert "no doctor, skipped" in result.stdout
    assert result.exit_code == 0

def test_install_skills_writes_file(monkeypatch, tmp_path):
    monkeypatch.setenv("REPOMAN_MANAGERS", "copy test")
    monkeypatch.setenv("REPOMAN_SKILLS_DIR", ".claude/skills")
    monkeypatch.setenv("DEVENV_ROOT", str(tmp_path))
    result = runner.invoke(app, ["install-skills"])
    assert result.exit_code == 0
    assert (tmp_path / ".claude/skills/repoman/SKILL.md").exists()
```

> `doctor`/`status` for enabled managers shell out to real CLIs. In unit tests, either
> (a) restrict `REPOMAN_MANAGERS` to managers whose command is absent (so `run_sub` returns
> unavailable deterministically — but that makes exit 2), or (b) monkeypatch
> `repoman.cli.run_sub`. The example above sticks to `copy` (no doctor) to stay
> hermetic. Add a monkeypatched-`run_sub` case if you want to assert aggregation exit math
> through the CLI layer.

## Phases

1. Add `tests/test_registry.py` + `tests/test_aggregate.py` (no I/O) → `pytest` green.
2. Add `tests/test_skills.py` (tmp file) → green.
3. Add `tests/test_cli.py` (CliRunner) → green.
4. Check coverage: `--cov=repoman` is on by default; aim to cover registry/skills/aggregate
   fully and the CLI command bodies. Don't chase coverage on `subprocess.run` real calls.

## Risks

| Risk | Mitigation |
|---|---|
| CLI tests accidentally shell out to real managers | Use `copy` (no doctor) or monkeypatch `run_sub`; never rely on a manager being installed. |
| `build_spine` expected strings drift if `SPINE` changes | These tests are the spec for the spine ordering — update intentionally with any SPINE change. |
| `--cov` failing under-threshold (if a min is added later) | No fail-under is configured today; keep it that way or set a modest floor. |
