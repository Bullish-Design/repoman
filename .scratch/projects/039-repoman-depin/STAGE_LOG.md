# Project 039 — repoman half: stage log

Scope for this session: Phase 0, Phase 1, Phase 2 only, confined to this
repository. No other repository touched. No `nixos-rebuild switch` run.

## Stage 1 — Phase 0: the fixture experiment

Built a throwaway fixture under `/tmp/repoman-039-fixture/`:

- `shellij_stub/modules/devenv.nix` — a stand-in shellij module that sets
  `env.SHELLIJ_MARKER = "present"`.
- `repoman_module.nix` — a copy of the trap: `{ lib, inputs ? {}, ... }:` with
  `imports = lib.optional (inputs ? shellij) (inputs.shellij + "/modules/devenv.nix");`
- `eval.nix` — `lib.evalModules` with `specialArgs.inputs.shellij` set, and
  `repoman_module.nix` referenced **by absolute path** in the `modules` list
  (not through a `devenv.yaml` import name) — this is the shape the central
  overlay uses (`/run/current-system/sw/share/repoman/module/devenv.nix`).

Result:

```
$ nix-instantiate --eval --strict --expr '(import /tmp/repoman-039-fixture/eval.nix).config.env'
{ SHELLIJ_MARKER = "present"; }
```

**Trap 3.1 does not fire.** `specialArgs` is set once for the whole
`evalModules` call (devenv sets `specialArgs.inputs` from the consumer's own
`devenv.yaml` inputs for the entire module evaluation), so a module reached by
absolute machine path sees the same `inputs` as one reached through a
`devenv.yaml` import name. The `shellij` and `docman` transitive imports in
`modules/devenv.nix:76` and `modules/managers/docman.nix:29` need no change and
no prerequisite phase. Phase 1 proceeds unmodified.

## Stage 2 — Phase 1: package and install the module

See `flake.nix` — `packages.<system>.repoman-module` installs `modules/` to
`$out/share/repoman/module/`, `nixosModules.default` wires
`repoman.installConsumerModule` and `environment.pathsToLink = [ "/share/repoman" ]`,
and `checks.<system>.repoman-consumer-module` evaluates the module against a
fixture with no `.repoman/project.toml` and asserts the default roster.

Machine boundary (installing to `/run/current-system/sw/share/repoman`,
bumping `nix-meta`, `nixos-rebuild switch`) is **out of scope for this
session** per the vendomat half's precedent (Stage 1: "this session runs as
uid 1000 and has no sudo"). Not attempted here either.

## Stage 3 — Phase 2: manifest-driven module

`.repoman/project.toml` (schema 1, `managers` field) is now read by
`modules/devenv.nix` under `${config.devenv.root}/.repoman/project.toml`, ahead
of the `repoman.managers` option, which stays as a compatibility fallback for
one release. Absent file means the default roster `["copy" "git" "test"]`.

Parsing and validation follow `devman/src/devman_contract/manifest.py`'s
discipline, done in Nix (`builtins.fromTOML`) since this module has no Python
runtime of its own: fixed field set, unknown fields rejected, `managers`
values checked against the same enum the option already uses.

This repository is one of the eight roster exceptions (`[copy git test doc]`),
so `.repoman/project.toml` is committed here rather than left absent. The
existing explicit `repoman.managers = [ "copy" "git" "test" "doc" ]` in
`devenv.nix` still wins over the manifest (explicit assignment beats a
`mkOption` default) — both agree on the same roster, so this is a no-op in
practice and only a real fixture proves the manifest path independently
(`checks.repoman-consumer-module`).

## Stage 4 — the four dead options, measurement-gated deletion

Grepped the whole tree for `template`, `installSkills`, and `skillsDir` (the
public option surface) before deleting: no manager module, script, or test
referenced any of the three beyond their own declarations and the one
`env.REPOMAN_SKILLS_DIR = cfg.skillsDir` wiring. Deleted:

- `options.repoman.template` — declared, never read anywhere.
- `options.repoman.installSkills` — declared, never read anywhere.
- `options.repoman.skillsDir` — read once, to set `REPOMAN_SKILLS_DIR`; no
  consumer overrode it, so the wiring now hardcodes the same default value
  (`.agents/skills`) directly.

`options.repoman.toolchainBin` is NOT deleted, despite appearing in the same
prompt table row. It carries `internal = true; readOnly = true;` — it was
never public option surface a consumer could set, and every shared manager
module (`gitman.nix`, `copyroom.nix`, `docman.nix`) interpolates
`cfg.toolchainBin` to resolve the shared command closure. Deleting it would
break the store/venv provider seam this module exists to run. The prompt's "0
repos set them" measurement is true of `toolchainBin` for the same reason it
is internal — it does not mean the internal plumbing is dead.

## Gate, run after Stages 1-4

```
nix flake check                                    all checks passed
devenv shell -- true                                clean entry, full roster banner
devenv shell -- testee verify --mode quick          ruff=passed ty=passed pytest=passed
                                                     (ruff-format fails on
                                                     src/repoman/cli.py and
                                                     src/repoman/devman/migrate.py,
                                                     pre-existing, untouched by this
                                                     session)
```

## Out of scope for this session

Per explicit scoping with the user: Phase 1's machine boundary (bumping
`nix-meta`, `nixos-rebuild switch`, proving
`/run/current-system/sw/share/repoman/module/devenv.nix`), Phase 3 (migrating
the 23 consumer repositories), Phase 4 (collapsing the remaining pins), and
Phase 5 (untracking the router skill) were not attempted. This session did not
touch any repository other than `repoman` itself.
