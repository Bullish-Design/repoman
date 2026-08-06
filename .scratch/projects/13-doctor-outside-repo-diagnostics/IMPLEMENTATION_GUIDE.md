# Implementation guide — `repoman doctor` context preflight

**Status:** planning complete · **owner lean:** option A (context preflight + short-circuit),
B's relabel folded in · **Scope:** `repoman doctor` (+ `--self-only`); `status`/`managers`/
`install-skills` are NOT in scope (see §9).

**Implemented 2026-08-06 (repoman 0.6.0):** preflight + `--json` + lock-row detail landed per
this guide; 181 tests green, lint clean, machine toolchain re-synced (stale `repoman 0.4.0`
dist in the shared venv fixed → `0.6.0`).

Verified 2026-08-06 against repoman **0.5.1** (post self-hosting) on this machine.

---

## 1. The bug, verified

`doctor` runs every row check unconditionally. There is no "am I in the right place"
preflight, so the wrong context produces a pile of plausible-looking rows instead of one
true statement.

### 1a. Current output from a non-repo dir (`cd /tmp`, no `REPOMAN_*` env)

```
=== repoman (self-check) ===
OK   toolchain:venv — /home/andrew/.local/share/repoman/venv
OK   toolchain:lock — /home/andrew/.local/share/repoman/venv/repoman-toolchain.toml
OK   lock:copy
OK   lock:git
FAIL uv:test — testee not declared in pyproject.toml — add it to [dependency-groups] dev (+ [tool.uv.sources]) and run `uv sync`
OK   version:managers.copy — copyroom 0.6.1
…
OK   installed:copy — /home/andrew/.local/share/repoman/venv/bin/copyroom
OK   installed:git — /home/andrew/.local/share/repoman/venv/bin/gitman
FAIL installed:test — testee not on PATH — run `uv sync`
WARN skill:entrypoint — missing — run `repoman install-skills`
WARN skill:tool-shipped — .agents/skills missing — run `copyroom agent-files export` + `repoman install-skills`
```
`exit=2`. Every FAIL/WARN is a red herring: `/tmp` has no `pyproject.toml`, no consumer
venv, no repo to install skills into. The real diagnosis — "you're not in a managed repo" —
is nowhere.

### 1b. Current output from a managed repo's **bare shell** (`cd talkee`, env scrubbed)

Same class of bug, one row: `FAIL installed:test — testee not on PATH — run uv sync` —
misleading because in the right context (the repo's devenv shell) testee IS present and
`uv sync` was already run; the bare shell just can't see the venv wiring. (The 0.4.0 rows
quoted in `FINDINGS.md` — `FAIL lock — missing: <cwd>/repoman.lock`, `installed:* not on
PATH — run repoman-sync` — are already fixed in 0.5.x by the project-12 absolute-path
resolution; the *class* of bug persists.)

### 1c. Green baseline (in-shell)

`cd talkee && devenv shell -- repoman doctor` → all rows OK/WARN, `exit=0`. This is the
byte-for-byte regression baseline (acceptance criterion 2).

---

## 2. Context detection — marker set and precedence

New function in `src/repoman/checks.py` (the diagnostic layer's home), consumed by
`cli.py`:

```python
@dataclass(frozen=True)
class Context:
    kind: str          # "managed-repo-shell" | "managed-repo-bare-shell" | "not-a-repo"
    repo_root: str     # DEVENV_ROOT when in-shell, else the detected repo root or cwd
    reason: str        # one human sentence for the message
```

```python
def detect_context(start: str) -> Context
```

### Marker table (precedence top → bottom)

| # | Signal | Means | Why unambiguous |
|---|--------|-------|-----------------|
| 1 | `REPOMAN_MANAGERS` set in env (**even empty string**) | managed-repo **shell** | Exported only by the repoman meta-module (`config.env` in `modules/devenv.nix`); present in both `devenv shell` and `devenv tasks run`. Empty = "wire nothing" is still a managed repo (matches `_enabled()`'s unset-vs-empty distinction). |
| 2 | `gitman.toml` **or** `.gitman/` in `start` or any ancestor | managed repo, **bare shell** | Created by gitman init/seed; present in every real consumer (talkee: both; gitman, nix-nvim, loci.nvim, loci-core, nix-secrets, nix-paseo: `gitman.toml`). Absence ≠ not-a-repo (freshly rendered, not-yet-inited) — accepted limitation, message still names the right invocation. |
| 3 | neither | **not-a-repo** | — |

**Explicitly NOT signals:** `DEVENV_ROOT` / `DEVENV_STATE` / `REPOMAN_TOOLCHAIN_VENV`
alone. Plenty of devenv projects don't use repoman; only `REPOMAN_MANAGERS` proves a
repoman-managed shell. (`REPOMAN_TOOLCHAIN_VENV` corroborates #1 but is not required —
it is exported from `enterShell`, `REPOMAN_MANAGERS` from `config.env`.)

### Resulting decision table

| REPOMAN_MANAGERS | markers in cwd..root | Verdict | Behavior |
|---|---|---|---|
| set (incl. `""`) | — | `managed-repo-shell` | run rows, byte-for-byte as today |
| unset | present | `managed-repo-bare-shell` | short-circuit, "enter the devenv shell" |
| unset | absent | `not-a-repo` | short-circuit, "not a managed repo" |

### Placement

In `cli.py`, at the top of `doctor()` — **before** `_enabled()`, `run_self_check`, and
`skill_ownership_checks`, so the short-circuit emits zero rows and skips both the self-check
and the devman lint:

```python
@app.command()
def doctor(self_only: bool = ..., json_out: bool = ...) -> None:
    context = detect_context(os.getcwd())
    if context.kind != "managed-repo-shell":
        ...  # emit context failure (plain or JSON), raise typer.Exit(code=2)
    ...
```

Notes:
- `start` for the marker walk is `os.getcwd()` (when `DEVENV_ROOT` is unset, `_repo_root()`
  is the cwd anyway; when it is set we're in-shell by rule 1 and markers are irrelevant).
- Walk ancestors with `Path.cwd().resolve()` → `parents` until root; stop at the first
  match (a repo nested under another repo: nearest wins).

---

## 3. Output spec — plain text

Format stays the family contract: parseable plain lines on **stdout** (the doctor's report
is stdout; the context failure IS the report), exit **2** (infra/config — never 1).

### 3a. `not-a-repo`

```
repoman: not inside a repoman-managed repo

There is no managed repo here (no gitman.toml/.gitman and no REPOMAN_* shell
environment). `repoman doctor` checks a repo's RepoMan wiring; run it from
inside a managed repo's devenv shell:

    cd <repo> && devenv shell -- repoman doctor

(Bootstrapping a brand-new repo? See the bootstrap ceremony doc once project 14
lands — §8.)
```

### 3b. `managed-repo-bare-shell`

```
repoman: managed repo found, but not inside its devenv shell

This looks like a RepoMan-managed repo (gitman.toml/.gitman present), but the
REPOMAN_* shell environment is missing — the manager toolchain is only wired
onto PATH inside the repo's devenv shell.

Enter the shell, then run:

    cd <repo> && devenv shell -- repoman doctor
```

Both blocks: **no `=== repoman (self-check) ===` header, no row lines**, exit 2. The
short-circuit applies identically to `doctor` and `doctor --self-only`.

### 3c. In-shell

Byte-for-byte identical to today (the talkee green run is the regression baseline; see
§6 for the one lock-row *detail* change and the row-name decision in §5).

---

## 4. Output spec — `--json`

**Gap found:** repoman currently has **no `--json` flag anywhere**. The family convention
(copyroom `doctor --json` → `{"checks":[{"name","ok","detail","warn_only"}]}`; testee/gitman
have a global `--json`) is the shape to match.

New option on `doctor`:

```python
json_out: bool = typer.Option(False, "--json", help="Emit structured JSON instead of a report.")
```

`--json` switches repoman's OWN output to JSON (context + self-check rows); sub-manager
reports in full `doctor` mode still stream plain (they own their report format — composing
sub-manager JSON is a noted follow-up, §9).

Level → field mapping (matches copyroom):

| level | `ok` | `warn_only` |
|---|---|---|
| `ok` | true | false |
| `warn` | false | true |
| `fail` | false | false |

### Context failure (all three contexts — acceptance criterion 4)

```json
{
  "context": {
    "ok": false,
    "kind": "not-a-repo",
    "detail": "not inside a repoman-managed repo",
    "hint": "cd <repo> && devenv shell -- repoman doctor"
  },
  "checks": [],
  "exit": 2
}
```

### In-shell

```json
{
  "context": {"ok": true, "kind": "managed-repo-shell"},
  "checks": [
    {"name": "toolchain:venv", "ok": true, "detail": "/home/andrew/.local/share/repoman/venv", "warn_only": false},
    {"name": "skill:entrypoint", "ok": false, "detail": "missing — run `repoman install-skills`", "warn_only": true}
  ],
  "exit": 0
}
```

`exit` is the same value the process exits with, so an agent can parse the verdict without
touching `$?`. Rows serialize from the existing `SelfCheck` list (both `run_self_check` and
`skill_ownership_checks`).

---

## 5. The `lock` row relabel

**Current state (0.5.x):** the `missing: <cwd>/repoman.lock` wording from 0.4.0 is already
gone. Rows are `toolchain:lock` (the venv manifest — accurate) and `lock:<key>` whose *fail*
detail reads: `selected but absent from the machine repoman.lock`.

**Decision:** keep the `lock:<key>` **row names**, fix the **fail detail**:

```
selected but absent from the recorded toolchain manifest
(<REPOMAN_TOOLCHAIN_VENV>/repoman-toolchain.toml) — re-run `repoman-sync --machine`
```

Rationale: acceptance criterion 2 demands the in-repo green output stay byte-for-byte
identical, and row names are the parseable surface (README documents `lock:<key>`; the
talkee baseline and any consumer parser key on them). The FINDINGS' "rename to align with
`toolchain:lock`" conflicts with criterion 2 — renaming `lock:<key>` → `toolchain:lock:<key>`
would change every consumer's green output. **Flagged open decision:** if the owner prefers
the rename, it is a one-line change per row but deliberately breaks criterion 2 and the
README table — not recommended this pass.

Also fix the README row-table entry for `lock:<key>`: "this manager is present in that
manifest" → "…present in the recorded toolchain manifest (`repoman-toolchain.toml` in the
shared venv)". Same for `toolchain:lock`.

---

## 6. Phases

### Phase 1 — `detect_context()` in `src/repoman/checks.py`

- `Context` dataclass + `detect_context(start: str) -> Context` (markers: `gitman.toml`,
  `.gitman/`; walk `start` → ancestors; env: `os.environ.get("REPOMAN_MANAGERS")`).
- Unit tests in `tests/test_checks.py` (see §7).

### Phase 2 — `cli.py` preflight + `--json`

- `doctor(self_only, json_out)`; preflight before `_enabled()`/`run_self_check`/
  `skill_ownership_checks`; `raise typer.Exit(code=2)` on non-shell contexts.
- `format_context_failure(context) -> str` (plain) + `context_json(context, checks, exit)`.
- Wire `--json` for the in-shell path too (serialize `self_checks`).
- CLI tests in `tests/test_cli.py` (see §7).

### Phase 3 — lock-row detail + README table

- `src/repoman/checks.py`: `lock:<key>` fail detail per §5.
- `README.md`: row-table wording for `lock:<key>`/`toolchain:lock`; a short "Running
  `repoman doctor` outside a repo" note; `--json` line in the Commands list.

### Phase 4 — project-14 seam (§8) + CHANGELOG

### Phase 5 — verify (commands in §8 of this doc + full suite)

---

## 7. Test matrix

### Unit (`tests/test_checks.py`)

| Test | Setup | Expect |
|---|---|---|
| `detect_shell_when_managers_set` | `REPOMAN_MANAGERS=git copy` | kind `managed-repo-shell` |
| `detect_shell_when_managers_empty_string` | `REPOMAN_MANAGERS=""` | shell (empty ≠ unset) |
| `detect_bare_repo_from_gitman_toml` | no env, `gitman.toml` in dir | `managed-repo-bare-shell` |
| `detect_bare_repo_from_dot_gitman` | no env, `.gitman/` dir | bare-shell |
| `detect_bare_repo_from_parent_marker` | marker in parent of cwd | bare-shell (walk-up) |
| `detect_not_a_repo` | no env, no markers | `not-a-repo` |
| `devenv_vars_alone_are_not_a_repo` | `DEVENV_ROOT`+`DEVENV_STATE` set, no managers, no markers | `not-a-repo` (explicitly NOT signals) |
| `lock_fail_detail_names_the_manifest` | selected manager absent from manifest | detail contains `repoman-toolchain.toml`, not "missing file" |

### CLI (`tests/test_cli.py`) — note the existing `_healthy_repo` helper sets
`REPOMAN_MANAGERS`/`DEVENV_ROOT`/`DEVENV_STATE`/`REPOMAN_TOOLCHAIN_VENV`, so ALL existing
doctor tests already run in the `managed-repo-shell` context and must stay green untouched
(that is itself the regression baseline for "in-shell output unchanged"). New tests must
**del-env** those vars (monkeypatch) + `monkeypatch.chdir` for cwd.

| Test | Setup | Expect |
|---|---|---|
| `doctor_outside_a_repo_short_circuits` | chdir tmp (no markers, no env) | exit 2, "not inside a repoman-managed repo", **zero** `===`/`FAIL`/`skill:` rows |
| `doctor_self_only_short_circuits_identically` | same, `--self-only` | same as above |
| `doctor_bare_shell_in_a_repo_short_circuits` | chdir tmp + `gitman.toml`+`.gitman/`, no env | exit 2, distinct "devenv shell" message |
| `doctor_in_shell_passes_through_unscathed` | `_healthy_repo("copy git test")` | exit 0, rows present (existing tests cover; add explicit assert) |
| `doctor_json_context_error` | not-a-repo + `--json` | exit 2; parse JSON: `context.ok==false`, `kind=="not-a-repo"`, `hint` contains `devenv shell`, `checks==[]` |
| `doctor_json_in_shell` | `_healthy_repo`, `--json` | `context.ok==true`; `checks` has `{"name","ok","detail","warn_only"}` |
| `doctor_json_bare_shell` | bare-repo + `--json` | `kind=="managed-repo-bare-shell"`, exit 2 |

### Regression

Full suite (`pytest`); talkee in-shell green run (§8). `test_modules_nix.py`,
`test_repoman_sync.py` untouched by this pass (no nix/script changes).

---

## 8. Project-14 seam (don't build it)

The `not-a-repo` message should eventually point at the bootstrap ceremony doc (project 14,
option A). Wire the seam now as a guarded constant in `cli.py`:

```python
# Project-14 seam: once the bootstrap ceremony doc exists, drop the path here and
# the not-a-repo message gains a "bootstrapping a new repo?" pointer to it.
_BOOTSTRAP_DOC = "docs/BOOTSTRAP.md"   # placeholder — inert while the file is absent
```

Render the pointer line only `if Path(_BOOTSTRAP_DOC).exists()`. Project 14's doc becomes
the canonical target; nothing else in this pass depends on it.

---

## 9. Out of scope / follow-ups

- `status`, `managers`, `install-skills` do **not** get the preflight this pass (acceptance
  criteria are doctor-only). Note: `install-skills` from a non-repo would still write
  `.agents/skills` into the cwd — a candidate follow-up guard.
- Composing sub-manager `--json` reports inside `repoman doctor --json` (subs stream plain
  today; copyroom's doctor has `--json`, gitman's doesn't — mixed capability).
- `--json` as a global flag (testee/gitman style) rather than doctor-only.
- Renaming `lock:<key>` → `toolchain:lock:<key>` — deliberately deferred (§5).

## 10. Verification commands (implementer)

```bash
# 1. not-a-repo (plain + json + self-only)
cd /tmp && repoman doctor --self-only; echo $?          # exit 2, one block, zero rows
cd /tmp && repoman doctor --json; echo $?               # JSON context error, checks []
# 2. green baseline (regression — must be byte-identical for the rows)
cd talkee && devenv shell -- repoman doctor; echo $?    # exit 0
# 3. bare shell in a repo (use the toolchain repoman; no devenv)
cd talkee && /home/andrew/.local/share/repoman/venv/bin/repoman doctor --self-only; echo $?  # exit 2, "devenv shell" block
# 4. full suite
cd repoman && devenv shell -- test
```
