# RepoMan composition spike

> **Status: historical record.** The spike proved the one-import mechanism. The four
> mechanism points and the Nix-input finding still hold. The way the manager commands
> reached the repo has changed twice since. Blocks that start with **Superseded** record
> that history. `CONCEPT.md` describes the current design (RepoMan 0.9.2).

**Goal:** prove the "one import" mechanism before building the full roster. A consumer
adds a single `devenv.yaml` input + import. It gets RepoMan's options and per-manager
wiring.

## What the spike contains

The spike began with these files:

```text
modules/
  devenv.nix              # the meta-module: options.repoman.* + static imports of managers
  managers/
    testee.nix            # one manager, gated on `builtins.elem "test" repoman.managers`
tests/consumer-example/
  devenv.yaml             # imports the meta-module by local path (path:../../modules)
  devenv.nix              # repoman.enable = true; repoman.managers = [ "test" ];
```

> **Superseded by project 039 (manifest-driven roster).** The option `repoman.managers`
> no longer exists (release 0.9.1 removed it). The roster now lives in
> `.repoman/project.toml`. Manager modules gate on the module argument `repomanManagers`.
> `tests/consumer-example` now has all four managers in its roster.

## The mechanism (proven by construction, mirrors existing libs)

1. **Remote/path module import** — identical to zelligate's `modules/devenv.nix`
   imported via a `flake:false` path input. A consumer's `imports: [ repoman ]`
   resolves to `<input>/devenv.nix`. Machine delivery later imported the same file by
   absolute path from the machine profile. The module sees the same `inputs` either way.
2. **Options + gated config** — identical to allium-env's `options.allium.*` +
   `config = lib.mkIf cfg.enable {...}`. The spike declared
   `options.repoman.{enable, managers, template, installSkills, skillsDir}`. Project 039
   and release 0.9.1 removed all but `enable`. Today `options.repoman` holds `enable` and
   `toolchainBin`. `modules/managers/gitman.nix` adds `nativeBuild`.
3. **Conditional managers without conditional imports** — `imports` can't depend on
   `config`. So the meta-module imports *every* manager module statically, and each one
   self-gates on membership in the roster. This is the standard module idiom;
   `managers/testee.nix` demonstrates it. The spike gated on `repoman.managers`. Today
   the meta-module sets the roster from `.repoman/project.toml` as `repomanManagers`.
4. **Command-line interface (CLI) ↔ module handshake** — the module exports
   `env.REPOMAN_MANAGERS`; the `repoman` Python CLI reads it to know which sub-doctors /
   sub-status commands to aggregate. No duplicated source of truth. Today this variable
   is the only channel. The Python side never reads `.repoman/project.toml`.

## Finding: transitive *nix inputs* are mostly not needed

The original open question was whether an imported remote devenv module can carry
its own nix `inputs` transitively. For this family it largely doesn't matter:

- The **nix module** only contributes `tasks` / `scripts` / `env` wiring — it needs
  only the consumer's existing `nixpkgs`.
- The **manager tools** (copyroom, gitman, testee, …) are not nix inputs of the RepoMan
  module.

> **Superseded by project 12, then by project 031 (how the tools arrive).** The spike
> delivered the tools as Python packages. `repoman-sync` ran `uv pip install` and put
> them in the devenv virtual environment (venv). Today Vendomat's store closure delivers
> copyroom, gitman, and docman. testee is a per-repo uv dev dependency. Both routes keep
> the finding true.

So RepoMan stays a single, light input. Inputs still are not transitive. A repo declares
the docman or shellij input itself, and RepoMan imports that module only when the input
exists.

### Decision: `repoman.lock` manifest

> **Superseded by project 12, then by project 031.** The spike chose one `repoman.lock`
> manifest (TOML). `repoman-sync` read it and ran `uv pip install` for RepoMan and the
> selected managers. The goal was lockstep: a repo's whole toolchain moves together,
> which matches copyroom's convergence model.
>
> Project 12 moved the pure-CLI managers to one machine-wide venv. Project 031 adopted
> Vendomat's store closure, and release 0.9.1 removed the venv provider. Vendomat's
> `flake.lock` now carries the lockstep goal. `repoman-sync` installs nothing, and no repo
> carries a `repoman.lock`. `CONCEPT.md` §6 lists the retired names.

## The conductor drives real managers — verified

The spike installed RepoMan and testee with `repoman-sync` (the retired mechanism). Then
the conductor drove the **real** manager:

```text
$ repoman managers
test     testee     [core       ] Verification (pytest / ruff / ty)

$ repoman doctor          # → runs the real `testee doctor`, aggregates exit code
OK  devenv shell · OK tool: ruff · OK tool: ty · OK tool: pytest · OK config …
repoman-doctor-exit=0
```

End to end: one import → `repoman` drives the real manager CLI with an aggregated
`0/1/2/3` exit code. This output is from the spike. The report layout has changed since.

### Gotcha worth knowing

A repo that imports the module from `devenv.yaml` has a `devenv.lock` that pins the input.
Edits to `modules/` do not show until `devenv update repoman` or a cleared lock. A repo
that uses the machine profile's module sees edits only after the machine rebuilds with a
new release.

The gotcha once mattered for a planned `repoman-sync` self-update flow. That flow is
**abandoned**. `repoman-sync` installs nothing, and Vendomat's flake owns toolchain
updates.

## Result — verified

Run from `tests/consumer-example/`:

```bash
devenv shell -- bash -c 'echo "MANAGERS=$REPOMAN_MANAGERS"; devenv tasks list | grep repoman'
```

Output:

```text
MANAGERS=test
├── repoman:test
└── repoman:test:ci
```

The original run also called `repoman-sync`. It printed two dry-run lines about install
targets and template options. RepoMan retired both mechanisms, so this record omits them.

This confirms, from a single `repoman` input with a roster of `test`:

- the `env.REPOMAN_MANAGERS` handshake reaches the shell,
- the testee manager module activated **only** because the roster named `test` (gated
  import), contributing its tasks,
- RepoMan wired the `repoman-sync` script. Today it verifies the closure and generates
  the router skill.

### One fix found

The consumer's `languages.python.version` pin requires a `nixpkgs-python` input. The spike
dropped the pin, because it is unrelated to RepoMan wiring. The consumer's rolling nixpkgs
already provided Python 3.13, so no pin was needed.

> **Superseded by the Python 3.13 baseline.** `tests/consumer-example` now pins
> `languages.python.version = "3.13"` and declares the `nixpkgs-python` input. docman's
> module also pins the version. The baseline is 3.13 because `pyjutsu` ships a `cp313-abi3`
> wheel, which cannot load on 3.12.

The idea to surface a missing input in `repoman doctor` was not built. It stays unsettled.

## Second manager (copyroom) — verified with two managers

Adding copyroom (roster `copy test`, one `./managers/copyroom.nix`) proves the roster
generalizes past one manager:

```text
$ repoman doctor
=== copy (copyroom) — no doctor, skipped ===
=== test (testee) ===   OK ruff · OK ty · OK pytest · …   →  doctor-exit=0

$ repoman status        # drives BOTH real CLIs, collapses exit codes
=== copy (copyroom) === Error: No CopyRoom project or workshop found here.
=== test (testee) ===   No runs found.
status-exit=1           # worst sub-exit (copyroom's), aggregation works
```

This output is from the spike, with copyroom 0.4. Findings:

- **Managers don't all implement every verb.** copyroom (v0.4) had no `doctor`
  (`new/update/inspect/status` only). The registry models this (`doctor=None`) and
  `repoman doctor` skips it rather than failing. The conductor must treat the verb set as
  per-manager, not assume the full contract. Update: copyroom 0.6 added `doctor`, and
  every manager in the registry has one. The `doctor=None` path stays. `status` is still
  per-manager: `doc` has none, and `repoman status` skips it.
- **gitman and native toolchains — done** (project 01, guide 1). gitman depends on
  `pyjutsu`, a native (Rust/maturin) extension. A plain `uv pip install` could not
  satisfy it, so the spike built it from a sibling checkout. `modules/managers/gitman.nix`
  contributed the **system toolchain**: `pkgs.maturin` and `languages.rust.enable`. It did
  so only when `"git"` was in the roster, so only repos that select gitman pulled Rust.
  This proves the meta-module can provision **nix-level system toolchains**, not only venv
  pip installs.

  The spike verified this end to end in `tests/consumer-example` with the roster
  `copy git test`. The native build took about 7.5 minutes on first run. `gitman doctor`
  exited 2 in the bare consumer ("not a colocated jj repo"). That is the expected
  uninitialized state, not a wiring failure.

  > **Superseded by project 12, then by gitman's project 32 (the pyjutsu wheel pin).**
  > The spike carried pyjutsu in a `repoman.lock` pseudo-entry, `[managers.git-pyjutsu]`,
  > because `uv pip install` ignores gitman's `[tool.uv.sources]`. RepoMan retired that
  > entry. gitman now pins a prebuilt pyjutsu wheel by URL in its own
  > `[tool.uv.sources]`, and uv carries that pin into a consumer's lock. So gitman needs
  > no Rust, and neither does a consumer on x86-64 Linux with glibc 2.39 or newer. The
  > Rust toolchain is opt-in: `repoman.nativeBuild = true` adds `maturin` and
  > `languages.rust.enable`. It is for pyjutsu's own repo, and for a platform the wheel
  > does not cover, where uv builds pyjutsu from its source distribution. The flake
  > check `gitman-rust-gate` guards the default.
