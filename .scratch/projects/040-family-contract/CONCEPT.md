# Project 040 — the family contract

> **Status:** design, 2026-10-06. Approved in concept; the API below is the
> proposal, not yet built. This document is fleet-wide. It will move into the
> new library's own repository once that repository exists.

## 1. The problem

The `*man` family invented its own four-code contract: `0` ok, `1` a domain
decision is needed, `2` infra or config, `3` invalid usage. Seven
implementations exist. Measured 2026-10-06:

| tool | what it really returns |
|---|---|
| gitman | `0/1/2/3`; 158 `GitmanError` sites — 58 at `1`, 43 at `2`, 83 at `3` |
| testee | `0/1/2` in `verify`; `3` hand-rolled at four sites |
| copyroom | 36 `sys.exit(1)` sites mixing findings and infra; `3` at four sites; `2` at one |
| docman | Python layer is `0/2`; its shell children invert it (see below) |
| linkman | `0/1/10/11/12/13`; `2` reserved for Click |
| devman | `0/1/2` in most paths; `agent.py` alone implements `0/1/2/3` |
| loci-core | `0/1/2`; **every** error is `1`, including `InfrastructureError` |

Four faults are shared by nearly every tool:

1. **Click's `2` leaks for usage errors.** No tool remaps it, because Click
   exits before the tool sees it.
2. **An uncaught exception exits `1`.** gitman catches only its own two
   exception types; testee's and docman's script target is the Typer `app`
   object itself, with no wrapper at all.
3. **The code is chosen at the raise site, not derived from the fault.** 158
   chances to drift in gitman. testee has no custom exception at all — the
   *same* `ValueError` becomes `3` in `verify` and `2` in `report`.
4. **Findings and faults are conflated.** copyroom returns `1` both for
   "`registry validate` found problems" (a finding) and for "git is not
   installed" (a fault). docman's `docs-lint` collapses every nonzero to `1`,
   hiding a missing tool. `docs-check` is inverted outright: lychee returns
   **`2` for a broken link** — a finding — and `1` for a runtime error.

Fault 4 is the important one. It is also the one the custom contract caused: a
four-way split invited each tool to classify by *cause* rather than by *whether
the tool did its job*.

## 1a. The industry already settled this

The dominant convention — grep, ripgrep, diff, ruff, mypy, shellcheck,
terraform `-detailed-exitcode` — is three codes:

```
0   the tool ran, and there is nothing to report
1   the tool ran, and found something the caller must act on
2   the tool could not do its job
```

GNU grep states it directly: "the exit status is 0 if a line is selected, 1 if
no lines were selected, and 2 if an error occurred". The reason this shape won
is operational: **a CI step can swallow findings without swallowing a crash.**

The code describes **the tool's own success, not the nature of what it found.**
ruff finds code problems and returns `1`; it does not return a
"code-problem-class" code. That single rule resolves every classification
argument below.

The surrounding numbers are not free either. Bash reserves `2`, `126` and
`127`; `128+N` is a signal, so SIGINT is `130`. `sysexits.h` (64–78) is a real
standard, but it is sendmail-era and now cited far more than used. The usable
application range is effectively `1`, and `2` as the catch-all fault.

**Decision: adopt `0/1/2` plus `130`. Drop `3`.**

Dropping `3` loses nothing a caller uses. No shell script branches on "you
typed it wrong" versus "your config is wrong" — both mean "I cannot proceed,
and retrying will not help". The *reason* belongs in the report, which every
tool is getting anyway.

RepoMan then aggregates these with `worst_exit`, which maps anything outside
`{0,1,2,3}` to `2`. So linkman's five failure classes collapse to one, and a
copyroom infra fault surfaces as a domain decision. **RepoMan's aggregate exit
code carries less information than any single input it consumes.**

The contract lives in six prose documents. Prose cannot be executed, so six
tools drifted six ways.

## 2. The second problem

RepoMan hardcodes facts its siblings own. `src/repoman/registry.py` holds
RepoMan's guess at four siblings' commands, status verbs, skill names and route
text. `src/repoman/devman/check.py` holds RepoMan's guess at devman's skill
policy.

Every drift item found in the 2026-10-06 survey is one instance of that single
mistake:

- `docman` recorded as a skeleton; it ships.
- `copyroom status` assumed to report drift; it reports version lag, and exits
  `1` in a repo with no answers file.
- `testee list-runs` assumed to carry a verdict; it always exits `0`.
- devman assumed to curate seven skills; it requires one, and refuses to
  universalise the rest.
- gitman assumed to need Rust; it pins a prebuilt wheel.
- `save` assumed to be a gitman verb; it is a deprecated alias.

RepoMan cannot fix this by being careful. It asserts facts it does not own, so
it is structurally positioned to go stale.

## 3. The decision

Three moves.

1. **State the contract as code**, in one shared library every tool depends on.
2. **Invert the knowledge flow.** Each tool publishes its own capability
   manifest. RepoMan reads them.
3. **Shrink RepoMan to lifecycle order only.** Delete both aggregations.

## 4. The library

Proposed repository `man-core`, package `mancore`, after the `loci-core`
precedent. **The name is open** — it is cheap to change now and expensive
later.

The model is linkman. It already has Pydantic result models, a
`schema_version`, `--json` on every command and golden tests. This library
extracts linkman's shape rather than inventing one.

```
mancore/
  exits.py       # the four codes, named
  errors.py      # the exception hierarchy that selects them
  cli.py         # the Typer app factory and the main() wrapper
  report.py      # Level, Row, Report — one envelope
  doctor.py      # the row collector and the exit rule
  repo.py        # root discovery, devenv guard
  capability.py  # the capability manifest and its `capability` command
```

### 4.1 Exit codes come from exception types, never from call sites

This is the rule that stops the drift. Today each tool scatters
`raise typer.Exit(2)` across dozens of sites, and each site is a chance to pick
the wrong number.

```python
CLEAN = 0      # the tool ran; nothing to report
FINDING = 1    # the tool ran; it found something the caller must act on
FAULT = 2      # the tool could not do its job
INTERRUPT = 130

class ManError(Exception):
    """A fault. The tool could not do its job."""
    exit_code: ClassVar[int] = FAULT

    def __init__(self, message, *, subject=None, remedies=()):
        ...

class UsageFault(ManError): ...    # the invocation is wrong
class ConfigFault(ManError): ...   # the configuration is wrong
class EnvFault(ManError): ...      # the environment is wrong
```

All three subclasses carry `FAULT`. They exist for the **message and the
remedy**, not for the code — a caller cannot act differently on them, but a
human can. This is the shape the grep convention implies: one fault code, many
fault explanations.

`subject` and `remedies` come straight from gitman's `GitmanError`, which
already carries both and renders them as a refusal with next steps. They are
why gitman's errors are actionable, so the library keeps them.

**A finding is a return value, not an exception.** This is the second half of
the rule. `FINDING` never comes from a raise; it comes from a command that
completed and has something to report. So a command returns its report, and the
library derives the code:

```python
def exit_for(report: Report) -> int:
    return FINDING if report.has_findings else CLEAN
```

That removes the whole class of bug where a tool raises for a finding and
thereby reports a fault. copyroom does this today at 36 sites.

Against gitman's design: gitman passes `exit_code` as a constructor argument,
so each of its 158 raise sites picks a number. Here the raise site picks only
the message, and a finding is not a raise at all. gitman's 83 sites at `3`
become `UsageFault`, its 43 at `2` become the right fault subclass, and its 58
at `1` need triage — some are genuine findings that should become return
values, and some are refusals, which are also findings.

**An uncaught exception is `INFRA`, never `DECISION`.** A crash means the tool
is broken, which is an environment fault. `1` must mean "the tool ran and is
asking you something". RepoMan already does this; gitman and loci-core exit `1`
on a crash and must change.

### 4.2 Every command spans the same three codes

The four-code contract implied a per-command taxonomy, and the false
expectation it created is why gitman's "doctor never returns 1 or 3" looked
like a defect. Under `0/1/2` the question disappears. Every command answers the
same three things: nothing to report, something to report, or I could not run.

What changes per command is only **what counts as a finding**:

| command | a finding is | a fault is |
|---|---|---|
| `doctor` | a failed check | the doctor cannot run — wrong directory, no config |
| `verify` | a red tool | a missing tool, an unreadable config |
| `status` | drift, an off-canonical repo, an update available | not a managed repo |
| `check` (linkman) | a link needing change, or a refusal | an unreadable declaration |
| `land` | a refusal, a conflict | no remote, a contended lock |

**This changes `doctor` across the whole family, and for the better.** Every
tool returns `2` for a failed check today. Under the grep convention a failed
check is a *finding* — the doctor did its job and found the problem — so it
returns `1`. `2` is reserved for "the doctor could not run".

devman's doctor already works this way (`1 if rep.findings else 0`). It was the
odd one out; it turns out to have been right.

The practical gain is a distinction RepoMan cannot currently express. Today
`repoman doctor` returns `2` both when a manager is missing and when you ran it
outside a devenv shell. Those are entirely different situations, and a caller
cannot tell them apart. Under `0/1/2`: missing manager is `1`, wrong context is
`2`.

### 4.3 The wrapper gets much smaller

The custom `3` forced an awkward lever: `app(standalone_mode=False)` to
intercept Click's usage exit and remap it. That was the sharpest edge in the
whole design, because the flag also changes `--help` and `--version` handling
and makes Click return the command's value instead of exiting.

**Adopting `0/1/2` deletes that problem.** Click's defaults are already
correct for two of the three codes:

| Click behaviour | code | correct under `0/1/2`? |
|---|---|---|
| `UsageError` — bad flag, unknown command, missing arg | 2 | yes |
| `typer.BadParameter` (a `UsageError`) | 2 | yes |
| `Abort` / `KeyboardInterrupt` | 130 via Typer | yes |
| uncaught exception | 1 + traceback | **no — must become 2** |
| `ClickException` | 1 | **no — must become 2** |

So the wrapper only fixes the crash case, in standalone mode, with no lever:

```python
def run(app: typer.Typer) -> NoReturn:
    try:
        app()                       # standalone: Click handles usage and --help
    except SystemExit:
        raise                       # Click already chose 0, 2 or 130
    except ManError as e:
        _render(e)
        sys.exit(e.exit_code)       # always FAULT
    except Exception as e:
        _render_unexpected(e)       # a crash is a fault, not a finding
        sys.exit(FAULT)
```

Four lines of real logic. No `standalone_mode=False`, no `click.exceptions.Exit`
ordering hazard, no per-tool `--help` test.

Tools must stop raising `ClickException` for faults — it exits `1`. None of the
six does today, so this is a rule for new code rather than a migration.

### 4.4 One report envelope

Three dialects exist today:

- `{level, name, detail}` — gitman
- `{name, ok, detail, warn_only}` — copyroom, repoman
- `{name, ok, detail}` — docman, no warn at all

The `level` form wins. Two booleans encode three states and admit a nonsense
fourth: RepoMan's own JSON sets `ok=false, warn_only=false` for a fail row, so
a consumer must infer the level rather than read it.

```python
Level = Literal["ok", "warn", "fail"]

class Row(BaseModel):
    level: Level
    name: str
    detail: str = ""

class Report(BaseModel):
    schema_version: Literal[1] = 1
    tool: str
    tool_version: str
    command: str
    exit_code: int
    rows: list[Row] = []
    notes: list[str] = []
```

`exit_code` appears inside the payload as well as on the process, so a caller
reading piped JSON needs no second channel. gitman already does this.

### 4.5 The doctor exit rule, stated once

```python
@property
def exit_code(self) -> int:
    return FINDING if any(r.level == "fail" for r in self.rows) else CLEAN
```

A `warn` never gates. A `fail` is a finding, not a fault — see §4.2. The doctor
raises `ManError` only when it cannot run at all, and the wrapper turns that
into `2`.

This is written six times today, each returning `2` where it should return `1`.
It becomes one line in one place.

### 4.6 The capability manifest — the inversion

```python
class Capability(BaseModel):
    schema_version: Literal[1] = 1
    key: str                              # "git"
    command: str                          # "gitman"
    phase: Phase | None                   # see §5
    skill: str                            # pool skill name
    install: Literal["toolchain", "uv"]
    route_when: str                       # one imperative line
    doctor: list[str] | None              # argv suffix
    status: list[str] | None
```

Each tool declares its own, in its own repository. `mancore` gives every tool a
free `capability` subcommand that prints it as JSON, and a build helper so
Vendomat can bake every capability into its closure manifest. RepoMan prefers
the closure manifest, and falls back to one subprocess per manager.

This deletes `registry.py`'s hardcoded table and the duplicated roster.

**Consequence for the Nix layer.** Nix validates
`.repoman/project.toml` today against a static `allManagers` list
(`modules/devenv.nix:51-69`). It cannot read the closure manifest at eval time,
because the manifest path arrives in an environment variable and the module is
forbidden from `builtins.getEnv`. So **roster validation moves out of Nix into
Python.** Nix passes the roster through; `repoman doctor` validates it against
discovered capabilities. This is better than the status quo: the error can say
"this repo selects `doc`, and the closure ships no docman", which Nix cannot
say. It also deletes the duplicated key list.

### 4.7 Shared repo discovery

`find_repo_root(markers=...)` and `require_devenv()`. Markers differ per tool
today — gitman uses `.jj` and `.git`, loci-core uses `.loci/vault.toml`,
linkman takes a five-marker list, RepoMan uses `gitman.toml` and `.gitman`. The
shared function takes markers as a parameter. `require_devenv()` raises
`InfraError` with one standard message.

## 5. The spine, corrected

The current spine is `scaffold → change → verify → save → docs`. Two steps are
fictions:

- `save` names a deprecated gitman alias. The real sequence is
  `describe → land → push`.
- `scaffold` happens before the repository exists, so it cannot be a phase of
  that repository.

And `docs` is not ordered — it runs on its own cadence.

The honest model is three phases and two activities:

```
         change → verify → integrate
            ↑________________|
```

| phase | owner | means |
|---|---|---|
| `change` | the agent or the user | edit |
| `verify` | testee | `testee verify --mode quick` in the loop, `--mode ci` at the gate |
| `integrate` | gitman | `describe` → `land` → `push` |

| activity | owner | cadence |
|---|---|---|
| `birth` / `converge` | copyroom | once at creation, then when the template moves |
| `docs` | docman | any time |

RepoMan's whole policy is two laws: **verify before integrate**, and **never
integrate on red**. Both are true. The current five-step spine states one law
using a verb that does not exist.

## 6. What RepoMan becomes

```
src/repoman/
  capability.py   # RepoMan's own Capability — it is a tool too
  discover.py     # read capabilities from the closure, else by subprocess
  spine.py        # the ordering. This is the product.
  router.py       # render the router from spine + capabilities + on-disk skills
  selfcheck.py    # doctor: RepoMan's own wiring, nothing else
  cli.py          # doctor, managers, install-skills
```

Deleted outright:

- `aggregate.py` — `run_sub`, `SubResult`, `worst_exit`, the timeout machinery.
- `registry.py` — replaced by discovery.
- `devman/` — `migrate` has had no input since devman deleted the option on
  2026-09-19, and the hardcoded skill set becomes a capability join.
- `repoman status` — it mutated VCS state through `gitman status`, and carried
  no verdict because `testee list-runs` always exits `0`.
- the `doctor` sub-doctor loop — the router tells an agent to run each
  manager's own doctor, which reports more than the collapsed number did.
- `repoman new` and `repoman adopt` — typing conveniences that hid which tool
  owns birth, and whose `--help` never reached copyroom.

Kept, because both work:

- the Nix meta-module (`modules/`), minus the roster validation that moves to
  Python.
- the router generator, now fed by discovery instead of a hardcoded table.

Estimate: about 350 lines of Python, down from 1,383.

**The router is the aggregation.** It aggregates knowledge, and knowledge
aggregation loses nothing. Exit-code aggregation loses by construction.

## 7. Migration, per tool

Build `mancore` with its own suite first, no consumer. Then, in this order —
cheapest and least risky first, so the library is proven before it meets the
hard cases.

**1. testee.** Nearly a no-op, which is the point: it proves the library
changes no behaviour. `verify` is already `0/1/2`. Four hand-rolled
`typer.Exit(3)` sites become `typer.BadParameter`, which Click already exits
`2`. Doctor's fail moves `2` → `1`. Six CLI exit assertions to update.

**2. linkman.** The `Exit` enum collapses, and every value has an obvious home
because linkman already carries the reason in its report:

| was | becomes | why |
|---|---|---|
| `DRIFT = 1` | `1` | unchanged |
| `REFUSAL = 11` | `1` | a refusal is something the caller must act on |
| `PARTIAL = 13` | `1` | some links applied, some did not |
| `CONFIG = 10` | `2` | the declaration is unreadable |
| `OS = 12` | `2` | the filesystem said no |

`RefusalReason` already distinguishes the eight refusal causes in the payload,
so nothing is lost. Also fixes a live bug: `_emit` catches only
`(LinkmanError, OSError)`, so any other exception escapes as exit `1` and
collides with `DRIFT`. The wrapper closes that.

**3. loci-core.** The largest correctness win for the smallest diff. Today
*every* error is `1`, so a broken vault, a bad request and a successful query
with findings are indistinguishable. `InfrastructureError`,
`VaultNotInitialized`, `CacheCatchUpError`, `InvalidRequestError` and the
reference errors all become `2`. Its existing usage `2` is already right. About
40 exit assertions across its CLI tests.

**4. gitman.** Mechanical but wide. 83 sites at `3` become `UsageFault`. 43 at
`2` become the matching fault subclass, unchanged in code. The 58 at `1` need
triage — a refusal or a conflict stays a finding, but anything that is really a
fault moves to `2`. Doctor's fail moves `2` → `1`. Add the wrapper, which gives
it an `except Exception` for the first time. 219 exit assertions across 48 test
files is the checklist.

Drop `map_pyjutsu_error`'s substring matching for transport faults
(`core.py:95-123`) if pyjutsu can be taught typed errors; otherwise keep it,
since under `0/1/2` it only decides finding-versus-fault and the stakes fall.

**5. copyroom.** The hardest, because findings and faults are interleaved
across 36 `sys.exit(1)` sites and one undifferentiated exception class.

- Genuine findings, keep `1`: `registry validate` found problems (`cli.py:673`),
  `golden` has diffs (`:778`), `release-check` failed (`:794`), `template-test`
  not ok (`:440`).
- Faults, move to `2`: every `CopyRoomError` catch whose cause is git missing,
  clone failed, YAML unreadable, copier failed, source unreachable.
- The four `sys.exit(3)` sites and the `typer.Exit(2)` at `:899` all become `2`.
- **Conditions that exit `0` today but are findings, and should become `1`:**
  `update` completing with conflicts or rejects (`:287-294`), `update
  --all-layers` with captured conflicts (`:319-324`), `template-preview` with
  conflicts (`:470-473`), `adopt` reporting drift (`:546-557`), `update-test`
  reporting issues (`:825-833`), and `status` with `update_available`. This is a
  real behaviour fix — `copyroom adopt` currently reports drift and exits `0`,
  so a caller cannot see it.
- The 56 `CopyRoomError` raise sites get fault subclasses. Prefer editing the
  raise sites over the 18 catch sites: the raise site knows the cause.
- `_cmd_layer_list` (`:604`) has no `try`/`except` at all; the wrapper covers it.

No existing copyroom test asserts `1`, `2` or `3` by value, so the suite does
not resist this.

**6. docman.** Its Python layer is already fine. **The faults are in the shell
children**, and one is fully inverted:

| script | now | should be |
|---|---|---|
| `docs-check` (lychee) broken link | `2` | `1` — it is a finding |
| `docs-check` runtime or missing input | `1` | `2` |
| `docs-lint` any nonzero | `1` | `1` for findings, `2` for a missing tool (`127`) or `typos` usage (`64`) |
| `docs-new` page exists | `1` | `2` — a usage fault |
| `docs-doctor.sh` any FAIL | `1` | `1` — the script was right; the Python port's `2` was wrong |

So `_run_script` must stop passing child codes through verbatim and map them
instead. That breaks `tests/test_cli.py:69`, which pins `returncode=7` →
`exit_code 7`; that test encodes the behaviour being removed.

Also resolve two open items the recon surfaced: `docs-serve` may not be on PATH
at all (it is declared as a devenv `process`, not a `script`), and
`docs-init.sh`'s `${DOCMAN_TEMPLATE_DIR:?}` aborts with `127`.

**7. devman.** Mostly already right. Its doctor's `1 if findings else 0` is the
target shape. `..` ("the check could not run") becomes `2`. `agent.py`'s `3`
becomes `2`. The leaked linkman `11`/`13` in `cli.py:446-448` follow linkman's
collapse.

**8.** Add a `Capability` to every tool; teach Vendomat to bake them into the
closure manifest.

**9.** Shrink RepoMan.

**10.** shellij adopts the library when convenient. Vendomat adopts it inside
the V4 rewrite, not before.

## 8. Known hazards

- **Version strings do not identify behaviour.** copyroom `0.7.7` is two
  different binaries, one with `agent-files` and one without. docman `0.2.1` is
  two behaviours. gitman `0.11.0` is the tag or trunk plus nine commits. A Nix
  closure cannot pin against that. Every tool must bump on a behaviour change
  before step 3, or the migration cannot be verified.
- **Changing an exit code is a breaking change for callers.** `gitman.toml`
  `[publish] verify`, CI, and `.pyjutsu-hooks.toml` all read exit codes. Audit
  each before a tool's codes move.
- **`gitman.toml` `[publish] verify` reads an exit code**, and it runs
  `testee verify --mode ci`. testee's `verify` codes do not move, so the gate is
  safe. But audit `[land.pre_hook]`, `.pyjutsu-hooks.toml` and any CI step
  before a tool's codes change — several treat "nonzero" as fatal, which stays
  correct, while any that test `== 1` or `== 2` will break.
- **Doctor's fail moving `2` → `1` is the widest behaviour change**, touching
  five tools. Anything that currently treats `doctor` nonzero as fatal keeps
  working. Anything that tests for `2` specifically does not.
- Six tools' test suites assert specific codes. Those assertions are the
  migration's checklist, not an obstacle. Measured: gitman has 219 `exit_code`
  lines across 48 of its 100 test files (`== 1` ×61, `== 3` ×60, `== 0` ×60,
  `== 2` ×16); testee has only 6 CLI exit assertions.
- **testee's models set `extra="forbid"`.** A reader with an older schema
  rejects any new field, raising `ValueError`, which becomes exit `2` in
  `report` and `triage`. Adding a field to a shared report model is therefore
  a breaking read. 16 fixture files under `testee/tests/fixtures/output/` pin
  `Failure`'s field names.
- **Renaming gitman's `Check`, `DoctorReport`, `OK`, `WARN` or `FAIL` breaks
  about six test files**, which import them directly. gitman's levels are plain
  module-level `str` constants, not an enum.
- **`gitman doctor` can emit two different JSON shapes.** Its doctor payload is
  built inline at `cli.py:166-170` with no model, but an invalid config raises
  `GitmanError` from `config.py:233`, so `main()` renders the *`IntentResult`*
  shape instead. One command, two schemas. The library fixes this for free.
- **testee validates config before it guards devenv** (`core.py:153` before
  `:154`), so a bad config outside a devenv shell exits `3` rather than `2`.
  Guard order is part of the contract and belongs in the library.
- **gitman classifies transport faults by substring**
  (`map_pyjutsu_error`, `core.py:95-123`: "connection refused", "could not
  resolve", "authentication", "timed out" → `2`, any other `GitError` → `1`).
  Its own comment flags this as fragile. The real fix is typed transport errors
  from pyjutsu; until then the library should not pretend to classify them.
- **gitman's `require_devenv` has no callers** (`core.py:132-137`). The devenv
  boundary is reported by `doctor` and enforced nowhere. Adopting
  `require_devenv()` from the library is a behaviour change for every verb.

## 9. Open questions

- **The library's name.** `man-core` / `mancore` is a placeholder.
- **Where a capability is published.** The closure manifest plus a `capability`
  subcommand is the proposal. Vendomat's V4 Q-SURFACE decision may change where
  the manifest lives.
- **Does `.repoman/project.toml` become the composition record** V4-OWN-013
  refers to? It holds a roster today, not a composition. If composition stays
  with RepoMan, RepoMan must say what that record is.
- **Does a non-blocking "gap"** — V4's term for a reported finding that does not
  block — need a code, or is it a `warn` row with exit `0`? The proposal says
  the latter. Under `0/1/2` this is now a clean fit: `warn` is a row the caller
  may read and the exit code ignores, which is exactly what "reported but not
  blocking" means.
- **Should a query report findings?** `testee list-runs` exits `0` even when the
  last run failed, and `repoman status` inherited that blindness. Under the
  convention, "the last run failed" is a finding, so `list-runs` arguably owes a
  `1`. Counter-argument: a listing command reports what exists, and the verdict
  belongs to `verify`. Unresolved; it decides whether a `status`-shaped command
  can ever carry a verdict.
- **Where do findings and faults coexist?** A `verify` run where one tool failed
  (finding) and another was missing (fault) must pick one code. Proposal: the
  fault wins, because the report is incomplete and the caller cannot trust the
  finding set. testee's `overall_status` already resolves it this way —
  `infra_error` beats `failed`.
