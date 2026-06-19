# RepoMan composition spike

**Goal:** prove the "one import" mechanism — a consumer adds a single `devenv.yaml`
input + import and gets RepoMan's options and per-manager wiring — before building
the full roster.

## What the spike contains

```
modules/
  devenv.nix              # the meta-module: options.repoman.* + static imports of managers
  managers/
    testee.nix            # one manager, gated on `builtins.elem "test" repoman.managers`
tests/consumer-example/
  devenv.yaml             # imports the meta-module by local path (path:../../modules)
  devenv.nix              # repoman.enable = true; repoman.managers = [ "test" ];
```

## The mechanism (proven by construction, mirrors existing libs)

1. **Remote/path module import** — identical to zelligate's `modules/devenv.nix`
   imported via a `flake:false` path input. A consumer's `imports: [ repoman ]`
   resolves to `<input>/devenv.nix`.
2. **Options + gated config** — identical to allium-env's `options.allium.*` +
   `config = lib.mkIf cfg.enable {...}`. RepoMan adds `options.repoman.{enable,
   managers, template, installSkills, skillsDir}`.
3. **Conditional managers without conditional imports** — `imports` can't depend on
   `config`, so the meta-module imports *every* manager module statically and each
   one self-gates on membership in `repoman.managers`. This is the standard module
   idiom; `managers/testee.nix` demonstrates it.
4. **CLI ↔ module handshake** — the module exports `env.REPOMAN_MANAGERS`; the
   `repoman` Python CLI reads it to know which sub-doctors / sub-status commands to
   aggregate. No duplicated source of truth.

## Finding: transitive *nix inputs* are mostly not needed

The original open question was whether an imported remote devenv module can carry
its own nix `inputs` transitively. For this family it largely doesn't matter:

- The **nix module** only contributes `tasks` / `scripts` / `env` / skills wiring —
  it needs only the consumer's existing `nixpkgs`.
- The **manager tools** (copyroom, gitman, testee, …) are **Python packages** that
  land in the devenv **venv**, not nix inputs. They arrive via `repoman-sync`
  (the allium-env "sync script" pattern), which `uv pip install`s the selected
  managers and installs their skills.

So RepoMan stays a single, light input; the heavy lifting is a venv sync, exactly
like the rest of the family.

### Decision: `repoman.lock` manifest

`repoman-sync` reads a single `repoman.lock` (TOML) that pins RepoMan itself plus
every manager, so a repo's whole toolchain moves in lockstep (matches copyroom's
convergence model). `source` is either `path:/abs` (dev) or
`git+https://…@vX.Y.Z` (fleet). The script resolves the `[repoman]` self entry plus
the entries for the managers in `$REPOMAN_MANAGERS` and `uv pip install`s them.

## `repoman-sync` is real — ✅ verified

`devenv shell -- repoman-sync` installed the pinned toolchain into the venv:

```
+ repoman==0.1.0 (from file:///…/repoman)
+ testee==0.1.0  (from file:///…/testee)
+ ruff==0.15.18  + ty==0.0.51  + pytest==9.1.1   (testee's bundled tools)
repoman-sync: done.
```

Then the conductor drives the **real** managers:

```
$ repoman managers
test     testee     [core       ] Verification (pytest / ruff / ty)

$ repoman doctor          # → runs the real `testee doctor`, aggregates exit code
OK  devenv shell · OK tool: ruff · OK tool: ty · OK tool: pytest · OK config …
repoman-doctor-exit=0
```

End to end: one import → `repoman-sync` (from `repoman.lock`) → `repoman` drives the
real manager CLIs with an aggregated `0/1/2/3` exit code.

### Gotcha worth knowing

A consumer's `devenv.lock` pins the `repoman` module input, so edits to `modules/`
aren't seen until `devenv update repoman` (or clearing the lock) — relevant for the
eventual `repoman-sync` self-update flow.

## Result — ✅ verified

Run from `tests/consumer-example/`:

```bash
devenv shell -- bash -c 'echo "MANAGERS=$REPOMAN_MANAGERS"; devenv tasks list | grep repoman; repoman-sync'
```

Output:

```
MANAGERS=test
├── repoman:test
└── repoman:test:ci
repoman-sync: would install managers [test]
repoman-sync: skills target = .claude/skills; template = gh:Bullish-Design/template-py
```

This confirms, from a single `repoman` input + `repoman.enable`/`repoman.managers`:

- the `env.REPOMAN_MANAGERS` handshake reaches the shell,
- the testee manager module activated **only** because `"test"` was selected (gated
  import), contributing its tasks,
- the `repoman-sync` script is wired with the right managers/skills/template.

### One fix found

The consumer's `languages.python.version` pin requires a `nixpkgs-python` input.
Dropped the pin in the spike (unrelated to RepoMan wiring); a real consumer either
declares that input or omits the version. Worth surfacing in `repoman doctor`.

## Second manager (copyroom) — N=2 verified ✅

Adding copyroom (`managers = [ "copy" "test" ]`, one extra `repoman.lock` entry, one
`./managers/copyroom.nix`) proves the roster generalizes past one manager:

```
$ repoman managers
copy     copyroom   [core]  Templating / scaffolding / convergence (Copier)
test     testee     [core]  Verification (pytest / ruff / ty)

$ repoman doctor
=== copy (copyroom) — no doctor, skipped ===
=== test (testee) ===   OK ruff · OK ty · OK pytest · …   →  doctor-exit=0

$ repoman status        # drives BOTH real CLIs, collapses exit codes
=== copy (copyroom) === Error: No CopyRoom project or workshop found here.
=== test (testee) ===   No runs found.
status-exit=1           # worst sub-exit (copyroom's), aggregation works
```

Findings:

- **Managers don't all implement every verb.** copyroom (v0.4) has no `doctor`
  (`new/update/inspect/status` only). The registry models this (`doctor=None`) and
  `repoman doctor` skips it rather than failing. The conductor must treat the verb
  set as per-manager, not assume the full contract.
- **Editable installs for `path:` sources.** `repoman-sync` installs local checkouts
  with `--editable`, so manager/RepoMan code edits are picked up without reinstalling.
  (git refs install normally.)
- **gitman + native toolchains — ✅ done** (project 01, guide 1). gitman depends on
  `pyjutsu`, an unpublished native (Rust/maturin) extension built from `../Pyjutsu`. A
  plain `uv pip install` can't satisfy it, so two pieces were added:
  - `modules/managers/gitman.nix` contributes the **system toolchain** — `pkgs.maturin`
    + `languages.rust.enable` — gated on `"git" ∈ managers`, so only repos that select
    gitman pull Rust. This proves the meta-module can provision **nix-level system
    toolchains**, not just venv pip installs.
  - pyjutsu gets its own `repoman.lock` pseudo-entry (`[managers.git-pyjutsu]`) because
    `uv pip install` ignores gitman's `[tool.uv.sources]`. `repoman-sync` installs any
    `<manager>-*` pseudo-entry alongside its manager, so uv builds both editable in one
    resolve and satisfies gitman's `pyjutsu` requirement from the local build.

  Verified end to end in `tests/consumer-example` with `managers = [ copy git test ]`:
  `repoman-sync` compiled pyjutsu (≈7.5 min native build, first run only) and installed
  the toolchain; `repoman managers` lists all three; `repoman doctor` runs the self-check
  then gitman's + testee's doctors. (gitman's doctor reports exit 2 in the bare consumer —
  "not a colocated jj repo" — which is the expected uninitialized state, not a wiring
  failure; we don't `jj git init` the throwaway consumer.)

  Two notes vs. the original concerns:
  - **Python 3.13:** gitman requires `>=3.13`. The consumer's rolling nixpkgs already
    provides 3.13.13, so no version pin (and no `nixpkgs-python` input) was needed — the
    earlier "One fix found" worry below didn't bite here.
