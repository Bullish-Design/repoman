# RepoMan — Deep Code Review

**Date:** 2026-07-02
**Reviewed at:** `main` @ `787c751` (repoman v0.3.0)
**Scope:** the whole system — Python CLI (`src/repoman`, ~620 LOC), the Nix meta-module
(`modules/`, ~515 LOC), `repoman-sync.sh`, the test suite, and fidelity against the
seven sibling `*man` dependencies.
**Method:** core read in full by hand; three parallel subagents audited (a) dependency
interface fidelity against the real sibling repos, (b) the nix/shell layer, (c) the test
suite + coverage. One reviewer disagreement reconciled (see §6).

---

## 1. What the system is

RepoMan is a **pass-through conductor** for devenv.sh repos. It reimplements nothing.
It discovers which sibling `*man` managers a repo wired in (via `REPOMAN_MANAGERS`, set
by the devenv meta-module), then **sequences and aggregates their own CLIs** under one
shared exit-code contract: `0` ok · `1` domain decision · `2` infra/config · `3` invalid
usage.

Three layers:

| Layer | Files | Responsibility |
|---|---|---|
| Python CLI | `registry.py`, `aggregate.py`, `checks.py`, `cli.py`, `skills.py`, `devman/*` | the roster, shell-out + exit-code collapse, self-preflight, skill/doc generation |
| Nix meta-module | `modules/devenv.nix`, `modules/managers/*.nix` | one import consumers use; per-manager wiring, statically imported + presence-gated |
| Sync | `modules/scripts/repoman-sync.sh` | read `repoman.lock`, `uv pip install` the pinned toolchain, regenerate skills |

The roster (`registry.py`) is the single source of truth read by the CLI, the nix module,
and the skill generator alike. Managers: `copy`→copyroom, `git`→gitman, `test`→testee,
`doc`→docman, `session`→zelligate, `agent`→mypi (mypi-agent), `spec`→alliman (allium-env).
Default roster: `copy git test`.

---

## 2. Overall assessment

**This is well-built, carefully-commented code with a coherent architecture.** The
dependency-fidelity audit found **zero hard bugs** — every command and subcommand the
registry declares actually exists in the real siblings, the `0/1/2/3` contract is honored
across all seven managers, and the tricky nix presence-gating idiom is correct and
correctly explained.

The real issues are concentrated in three places:

1. **Staleness in `flake.nix`** — version drift, an old-concept description, and phantom
   dependencies that misrepresent the dependency surface.
2. **Test coverage of the CLI's central logic** — the exit-collapse math that is the
   entire point of the conductor is never exercised; `status` is untested.
3. **Minor smells** — stale comments, a redundant guard, a shadowed name.

None are blocking. Priorities are in §7.

---

## 3. Findings — 🔴 concrete issues (should fix)

### 3.1 `flake.nix` is stale and carries phantom dependencies

Evidence:
- `flake.nix:12` — `version = "0.1.0"`, but `pyproject.toml` is `0.3.0`. The built
  `result` symlink and `SPIKE.md` also report 0.1.0. Version drift; the flake package is
  two minor versions behind the real project.
- `flake.nix:2` — `description = "Repository manager for NixOS configurations"`. This is
  the **old, wiped concept** ("GitHub repo syncer for NixOS configs"), not the current
  devenv lifecycle conductor. Actively misleading to anyone reading the flake first.
- `flake.nix:28-35` — `propagatedBuildInputs` lists `pyyaml`, `tomli`, `aiofiles`. **None**
  of these appear in `pyproject.toml`'s `dependencies` (which is `pydantic`, `typer`,
  `jinja2` only). `tomli` is dead code — `checks.py:13` and `repoman-sync.sh:24` use the
  stdlib `tomllib` (Python 3.11+; the flake pins python312). `pyyaml`/`aiofiles` are
  cargo-culted from a template. All three real deps (`pydantic`/`typer`/`jinja2`) *are*
  present, so this is bloat + misdirection, not a broken build.

**Why it matters:** `flake.nix` is the first file a Nix-oriented reader opens. Right now it
tells three lies (wrong version, wrong purpose, wrong deps). Cheap to fix, high signal.

**Fix:**
```nix
description = "The agentic repo lifecycle conductor for devenv.sh repos — one import that composes the *man manager family.";
# version = "0.3.0";  # or read from pyproject
propagatedBuildInputs = with pkgs.python312Packages; [ pydantic typer jinja2 ];
```
(Consider sourcing `version` from `pyproject.toml` to prevent future drift, or drop the
literal and let `pyproject = true` carry it.)

### 3.2 The CLI's central exit-collapse logic is untested — highest-value gap

`cli.doctor` computes the conductor's whole reason for existing:
```python
raise typer.Exit(code=max(self_code, worst_exit(results)))   # cli.py:79
```
But the only non-`--self-only` doctor test enables `copy`, and `copy` has `doctor=None`
(`registry.py:63`), so the sub-doctor loop is skipped and `results` stays **empty**.
`worst_exit([])` is `0`, so the test never proves the `max()` combines anything.

**A regression that returned only `self_code`, or only `worst_exit(results)`, would pass
the entire suite.** This is the single most important untested behavior in the codebase.

`cli.status` (`cli.py:82-92`) is worse: **zero tests**. The `manager.status is None` skip,
the per-manager echo, and `raise typer.Exit(code=worst_exit(results))` are all unverified.

**Fix — add (at minimum):**
1. Enable a doctor-bearing manager (`test`), monkeypatch `repoman.cli.run_sub` (or
   `aggregate.subprocess.run`) to return a `SubResult` with `exit_code=1`, keep the
   self-check green, invoke `["doctor"]`, assert `exit_code == 1`.
2. Same, but force a self-check FAIL (2) with the sub-doctor at 1 → assert `2` (proves
   `max` picks the self side too).
3. A `status` test: enable `git`+`test`, mock `run_sub` to mixed codes, assert exit ==
   `worst_exit`, and that a `status is None` manager (`doc`) is skipped.
4. A mixed-roster doctor (`copy test`): assert "no doctor, skipped" for `copy` **and** that
   testee's doctor actually ran, in one invocation.

---

## 4. Findings — 🟡 test coverage gaps (lower risk)

Current suite: **66 tests, ~96% line coverage, ~2.2s under devenv.** Genuinely healthy;
`aggregate.py` (worst_exit severity order, `[]→0`, unavailable→2, unrecognized-127→2, and
`run_sub`'s `which→None→127` path with `subprocess.run` mocked) is well covered in
`tests/test_aggregate.py`. Remaining gaps:

| # | Gap | Location | Risk |
|---|---|---|---|
| 1 | `git+https://…@ref` passthrough source kind untested (only `wheel:`/`path:`/guard covered) | `repoman-sync.sh:46` | med — a regression mangling git sources wouldn't be caught |
| 2 | `_enabled()` unknown-key filtering (`if key in REGISTRY`) untested — no proof a garbage `REPOMAN_MANAGERS` entry is dropped vs `KeyError` | `cli.py:34` | low |
| 3 | Negative pseudo-entry: `k.split("-",1)[0] == m.key` tested only positively; `gitx-pyjutsu` must NOT satisfy `git`, but exactness isn't pinned | `checks.py:55` | low |
| 4 | `self_check_exit` / `format_self_check` unknown-level fallback branches | `checks.py:115`, `:120` | low |

The sync test (`test_repoman_sync.py:40-75`) is otherwise a **strong** test — it drives the
real embedded tomllib resolver via a stubbed `uv`/`repoman` on PATH and covers the
`UV_FIND_LINKS` wheel guard.

**Weak/misleading tests to be aware of (not urgent):**
- `test_cli.py` `test_doctor_skips_managers_without_doctor` asserts `exit_code == 0` with an
  empty `results` list — reads like an aggregation test, validates almost no aggregation.
- `test_checks.py:193` `test_full_roster_self_check_is_green` builds a lock with fictional
  `package="{key}"` values (e.g. `mypi`, not the real `mypi-agent`). It passes only because
  `run_self_check` never validates the `package` field — don't read it as a package-name
  contract.

---

## 5. Findings — ⚪ smells & nits (no behavior change)

| Location | Note | Suggested action |
|---|---|---|
| `registry.py:63` | Comment "copyroom (v0.4) has no doctor verb" is **stale** — copyroom now ships `doctor` (`copyroom/cli.py:965`). `doctor=None` is harmless (RepoMan won't call it) but the rationale is wrong. | Refresh comment; consider enabling copyroom's doctor. |
| `devenv.nix:91` | `enterShell = lib.optionalString cfg.enable …` sits inside `config = lib.mkIf cfg.enable`, so the inner guard is always true. | Drop the inner guard: `enterShell = ''…'';` |
| `cli.py:57` | Local `managers = _enabled()` inside `doctor()` shadows the module-level `managers` Typer command (`cli.py:38`). Harmless, mildly confusing. | Rename local to `enabled`. |
| `docman.nix:16`, `mypi.nix:20`, `alliman.nix:16` | Destructure `{ inputs, … }` with no default. | `{ inputs ? {}, … }` for defensiveness if a consumer's devenv never passes `inputs`. |
| `flake.nix` root `devenv.nix` | repoman builds itself with a plain-Python devenv and does **not** import its own meta-module; the module path is exercised only by the `gitman-rust-gate` eval check. | Intentional (per-repo tooling isn't self-hosted). Just worth knowing the meta-module's runtime surface isn't dogfooded here. |

---

## 6. Reviewer disagreement — reconciled

The dependency-fidelity subagent reported the `REPOMAN_PROVISIONED_{DOC,AGENT,SPEC}` signal
that `checks.py:80` looks for is **never emitted**, concluding `provisioned:*` would always
warn. The nix-layer subagent reported the opposite — that it **is** emitted with matching
keys.

**Resolution: the nix reviewer is correct.** The fidelity agent looked in the *sibling*
repos' own modules (`docman/modules/docman.nix`, etc.), which indeed only set their native
`DOCMAN_*`/`MYPI_*`/`ALLIUM_*` env. But the signal is emitted by **repoman's own wrapper
modules**, gated on `hasInput && enabled`:
- `modules/managers/docman.nix:44` → `env.REPOMAN_PROVISIONED_DOC = "1";`
- `modules/managers/mypi.nix:55` → `env.REPOMAN_PROVISIONED_AGENT = "1";`
- `modules/managers/alliman.nix:39` → `env.REPOMAN_PROVISIONED_SPEC = "1";`

Keys (`DOC`/`AGENT`/`SPEC` = manager-key uppercased) match `checks.py:80`
(`REPOMAN_PROVISIONED_{m.key.upper()}`) exactly. **The signal works; not a bug.**

---

## 7. Dependency fidelity — summary

All seven sibling repos exist and ship real CLIs (no empty template-py stubs). Every
`command`, `doctor`/`status` subcommand, `skill` dir, and `nix_input` in the registry was
verified against the real repos:

| manager | command | doctor/status subcmds | skill dir | nix module | verdict |
|---|---|---|---|---|---|
| copy | `copyroom` ✓ | `status` ✓ (doctor=None; copyroom now HAS doctor — stale comment) | copyroom | — | ✓ |
| git | `gitman` ✓ | `doctor`,`status` ✓ | gitman | Rust gated behind `nativeBuild` | ✓ |
| test | `testee` ✓ | `doctor`,`list-runs` ✓ | testee | — | ✓ |
| doc | `docman` ✓ | `doctor` ✓ | docman | `docman` input; provisioned signal ✓ | ✓ |
| session | `zelligate` ✓ | `doctor`,`list` ✓ | zelligate | Docker-first defaults overridden ✓ | ✓ |
| agent | `mypi` ✓ (repo mypi-agent) | `doctor`,`paths` ✓ | mypi | `mypi-agent` input; safe-bridge; provisioned ✓ | ✓ |
| spec | `alliman` ✓ (repo allium-env) | `doctor` ✓ | `allium-entrypoint` ✓ | `allium-env` input; provisioned ✓ | ✓ |

No "command not found" or contract mismatch will occur. Repo-name indirections
(`mypi`→mypi-agent, `alliman`→allium-env) and the `alliman` vs 3rd-party `allium`-binary
distinction are all correct.

---

## 8. Strengths worth preserving

- **`repoman-sync.sh` fully complies with the no-silent-failure rule.** `set -euo pipefail`;
  `resolved="$(…)" || exit $?` correctly uses command-substitution (not process-substitution)
  so the resolver's `sys.exit(2)` wheel-guard propagates and aborts the sync; zero-target
  handled cleanly; no `|| true` anywhere; the inline comment even explains *why* it's
  command-substitution.
- **`flake.nix`'s `gitman-rust-gate`** is a genuinely good hermetic eval test — it evaluates
  the module twice under stub options and asserts Rust is provisioned **only** under
  `nativeBuild = true`, so the zero-Rust default can't silently regress.
- **The presence-gating idiom is correct and well-documented.** `optionalAttrs hasInput`
  (depends on `inputs`) wrapping `mkIf enabled` (depends on `config`) is the right ordering
  to avoid "option does not exist" under strict eval.
- **Consistency holds across the three sources of truth:** `allManagers` (`devenv.nix:26`) ==
  `REGISTRY` keys == the option `enum`; `DEFAULT_MANAGERS` == the option default.

---

## 9. Recommended priority order

1. **Fix `flake.nix`** (§3.1) — version → 0.3.0, rewrite description, drop
   `pyyaml`/`tomli`/`aiofiles`. Fast; removes actively-misleading state.
2. **Add the CLI exit-collapse + status tests** (§3.2) — covers the conductor's core
   contract; a broken `max()` currently passes CI.
3. Fill the smaller test gaps (§4: git+ source, unknown-key filter, negative pseudo-entry,
   unknown-level fallback).
4. Refresh stale comments/nits (§5: `registry.py:63`, `devenv.nix:91`, the `managers` shadow).

Suggested first commit: bundle #1 + #2 — quick, and together they fix the two highest-signal
problems (misleading metadata + untested core logic).
