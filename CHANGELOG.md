# Changelog

## Unreleased — align with work-only gitman 0.12.0, adopt the `0/1/2` exit contract

gitman 0.12.0 has one command, `gitman work`. Native `jj` and `gh` replace the other
verbs. RepoMan stops describing `integrate` as gitman verbs.

### Changed (breaking)

- **RepoMan runs its managers by name from `PATH`.** The host profile installs `copyroom`,
  `gitman` and `docman`. RepoMan no longer reads Vendomat's closure or manifest. This is
  step 3 of Vendomat's V4 removal backlog (V4 is removed; V5 gives no backward
  compatibility). RepoMan removes:
  - `REPOMAN_TOOLCHAIN_BIN` and `REPOMAN_TOOLCHAIN_MANIFEST`,
  - the `repoman.toolchainBin` option, and the `:?` guard it carried,
  - the `toolchain:store`, `toolchain:self`, `lock:<key>` and `version:<key>` doctor rows,
  - the closure `PATH` export in `enterShell`, and the manifest read in `repoman-sync`,
  - `vendomat.toml` in this repository.
  `Manager.install` is now `"path"` (was `"toolchain"`) or `"uv"`. `installed:<key>` fails
  for a host manager that is not on `PATH`. The `cliProvider` manifest key is still
  accepted and ignored.
- **Exit codes follow the shared `0/1/2` contract.** A failed `doctor` row exits `1`
  (was `2`). A bad `install-skills` target exits `2` (was `3`). A wrong context still
  exits `2`. Exit `3` is retired.
- **The `git` manager is work-only.** `registry.py` drops its `doctor` and `status`
  commands. Its route names `gitman work`, native `jj` and `gh`.
- **`integrate` means native jj.** It is `jj describe`, a bookmark, `jj git push`, then
  a `gh` pull request. The router laws no longer name `land` or `push`.
- **Bare-shell detection reads `.repoman/project.toml`.** It no longer reads
  `gitman.toml` or `.gitman/`. gitman 0.12 writes neither.
- **`gitman.nix` adds `git` and nothing else.** It removes `repoman:vc:status`, which ran
  `gitman status`. It also removes the `repoman.nativeBuild` option, which provisioned
  Rust and maturin to build pyjutsu. gitman 0.12 does not use pyjutsu, and a fleet search
  found no repo that set the option. The flake check `gitman-rust-gate` becomes
  `gitman-adds-git-only`.
- **One gitman mode, no `gitmanVersion`.** The unreleased opt-in (`gitmanVersion` in
  `.repoman/project.toml`, `REPOMAN_GITMAN_VERSION`, `manager_for`, a `gitman-v2` skill)
  is removed before any release. The fleet cuts over to work-only gitman 0.12 in one step.
- **`repoman doctor` adds `interface:git`.** It fails when `gitman` is not the work-only
  tool or when `jj` is older than 0.46.0, which `gitman work` needs.
- **A `gate` script replaces the v1 push and release gate.** `gitman.toml`
  `[publish].verify` and the pyjutsu pre-push hook (`.pyjutsu-hooks.toml`) no longer run,
  because native `jj git push` fires no hook. Both files are deleted. Run `gate` before
  you push or tag. It runs `scripts/check-fleet-lock.py`, then `testee verify --mode ci`.
- **Fixture articles use the `0/1/2` contract.**

## 0.10.0 — drop the aggregating CLI, retire the lock files, realign the docs

This repo removes the two lock files of the retired virtual environment (venv) toolchain.
The fleet also retired the `my-ai` personal layer, so the doctor stops expecting its
skill. A survey of every sibling tool then corrected the documents that described their
old surfaces.

### Changed

- **The doctor expects only the shared `writing` skill.** `PERSONAL_LAYER_SKILLS` becomes
  `SHARED_GUIDANCE_SKILLS = ("writing",)`. `skill:tool-shipped` no longer warns about a
  missing `my-ai` link.
- **`AGENTS.md` and `docs/AGENT-FILES.md` stop naming `my-ai`.** `AGENTS.md` points at the
  `writing` skill for style rules.
- **README removes two stale claims.** It no longer compares `devenv.local.yaml` to the
  lock pair. It now says that a pre-push hook guards `devenv.lock`, not
  `tests/test_fleet_shape.py`. The adoption snippet pins `v0.9.2`.
- **`devenv.lock` names published tags again.** A shell with the overlay active had
  re-locked it at local paths.
- **`CONCEPT.md` and `SPIKE.md` describe today's design.** Both still documented
  `repoman-sync --machine`, the lock overlay, and the removed `managers`,
  `installSkills`, `skillsDir` and `template` options.
- **gitman needs no Rust toolchain.** gitman pins a prebuilt pyjutsu wheel by URL in its
  own `[tool.uv.sources]`, and uv carries that pin into a consumer's lock. The
  `repoman.nativeBuild` option stays, as opt-in, for a platform the wheel does not
  cover. Its comments called it an opt-out and cited jj-lib 0.38; it is opt-in and
  jj-lib is 0.44.0.
- **copyroom is not the genome.** The genome is the base template, such as `template-py`.
  copyroom converges layers inside one repo and has no cross-repo command. Toolchain
  versions reach a repo through the genome's pins or Vendomat's flake pins.
- **`AGENTS.md` states who writes agent skills.** copyroom ships none and the genome
  ships none. devman's overlay owns `.agents/`, a person writes each pool link by hand,
  and RepoMan writes only the router.
- **README states how a repo reaches devman.** devman walks no disk. The link plane
  needs one `devman-link reconcile`, and the workflow plane needs one
  `vendomat plane update devman`.
- **README states what the manager status commands can and cannot tell you.**
  `copyroom status` reports version lag, not drift, and exits 1 without an answers file.
  `testee list-runs` always exits 0. `gitman status` is not read-only.
- **`copyroom adopt` does not write the `devenv` blocks.** Only `copyroom new` renders
  them, through the genome. `adopt` is report-only.
- **The skill lint derives from the roster.** It expected seven skills for every roster.
  It now expects `writing` always, each enabled manager's skill, and `copyroom-adopt` and
  `copyroom-template-edit` only when `copy` is enabled. devman requires exactly one
  universal skill, `writing`, and refuses to universalise `gitman` and `copyroom`. The new
  public function `expected_skills(enabled)` computes the set. The rows stay `ok` or
  `warn`, and never gate.
- **The lifecycle spine is three ordered phases plus two activities.** The phases are
  `change`, `verify`, and `integrate`. The activities are `birth / converge` (copyroom)
  and `docs` (docman), and they have no order. The old spine was
  `scaffold → change → verify → save → docs`. `save` was a hidden, deprecated alias for
  gitman's `describe`. The real sequence is `describe`, `land`, `push`. `scaffold` happens
  before the repository exists, so it is not a phase. The two laws are: verify before you
  integrate, and never integrate on red.
- **The router orders managers spine-first.** A roster of `copy git test doc` renders as
  `test git copy doc`.
- **The `git` routing row names real verbs.** It reads "start, describe, sync, publish,
  land, push, undo, repair, or release a change".
- **`repoman doctor --json` prints pure JSON.** It used to print sub-doctor text before
  the document. The exit code is now the self-check exit.
- **README, `CONCEPT.md`, `docs/SKILLS.md`, and `AGENTS.md` describe the four-command
  CLI.** `CONCEPT.md` §5 no longer calls the CLI "pass-through plus aggregate". RepoMan
  owns the lifecycle order and generates one file. It aggregates nothing at runtime.
  The unbuilt `repoman verify`, `save`, and `release` verbs are abandoned, because the
  router states the order.
- **The pre-push hook does not fire on `gitman release`.** It fires on `push`,
  `publish`, and the lane-branch delete-pushes. `release` pushes only a tag.

### Removed

- **`repoman status`.** It mutated version-control state through `gitman status`, which
  snapshots `@`, mirrors refs, and writes `.gitman/markdown`. It carried no verdict,
  because `testee list-runs` always exits 0. It failed in any repo without a Copier
  answers file, because `copyroom status` exits 1 there.
- **The sub-doctor loop in `repoman doctor`, and the `--self-only` flag.** Doctor now
  checks RepoMan's own wiring only. The loop merged six incompatible exit-code dialects
  into one number that carried less information than any single input. Measured on
  2026-10-06: gitman's doctor returns only 0 or 2, copyroom returns 1 for infrastructure
  faults, docman returns 0 or 2 and reports a broken link as 2, linkman uses 10 to 13,
  and loci-core returns 1 for everything. `worst_exit` mapped any code outside 0 to 3
  to 2. The router skill is the aggregation. It aggregates knowledge, which loses
  nothing. Run each manager's own `doctor` and read its report.
- **`repoman new` and `repoman adopt`.** They hid which tool owns birth, had no timeout,
  and their `--help` never reached copyroom. Run `copyroom new` and `copyroom adopt`.
- **`repoman devman status` and `repoman devman migrate`, and `devman/migrate.py`.**
  devman deleted the `devman = {...}` devenv option that they parse on 2026-09-19.
  `migrate` raised `MigrationError` on this repo. devman writes no manifests by design.
  A person maintains `.devman/project.toml`, and the template seeds it.
- **`src/repoman/aggregate.py`.** This removes `run_sub`, `SubResult`, `worst_exit`,
  `resolve`, and the `REPOMAN_SUB_TIMEOUT` variable. The CLI shrinks from 387 to 259
  lines. The CLI now has four commands: `managers`, `doctor`, `install-skills`, and
  `--version`.
- **`repoman.lock` and `repoman.local.lock`.** Both files described the venv toolchain
  that 0.9.1 retired.
- **`.copier-answers.my-ai.yml`.** The repo detaches from the `my-ai` personal layer.
- **The `shellij` input in `devenv.yaml`.** That input made the meta-module import
  shellij's devenv module in this dev shell.

## 0.9.2 — legacy manifest compatibility

The consumer module accepts and validates the legacy `cliProvider` field in
`.repoman/project.toml`. The field does not select manager binaries; Vendomat
continues to provide the shared CLI toolchain.

## 0.9.1 — retire the provider seam

Vendomat's store closure is now the only source of the shared manager commands.
`REPOMAN_TOOLCHAIN_BIN` names its `bin` directory. `share/vendomat/toolchain.json` is the
store manifest, and it records provenance. RepoMan installs no packages. The suite shrinks
from 257 to 137 tests, because the venv provider and its tests no longer exist.

### Changed

- **`repoman-sync` only verifies.** It checks the closure at `REPOMAN_TOOLCHAIN_BIN`,
  prints the store manifest, and runs `repoman install-skills`. The script shrinks from
  618 to 69 lines. `REPOMAN_TOOLCHAIN_MANIFEST` overrides the manifest path.
- **The doctor lints the full expected skill-link set.** It checked only copyroom's
  canonical set before. It now covers the four manager skills that the router needs
  (`copyroom`, `gitman`, `testee`, `docman`). It also covers the personal layer (`my-ai`,
  `writing`). A missing link stays a warning and exits `0`. The message now points at the
  devman pool.
- **Doctor rows read the store manifest.** `toolchain:store` replaces `toolchain:venv` and
  `toolchain:lock`. `lock:<key>` and `version:<key>` read the store manifest.
- **The roster comes only from `.repoman/project.toml`.** The `repoman.managers` option no
  longer exists.
- **The docs describe the central pool model.** `docs/AGENT-FILES.md` and `docs/SKILLS.md`
  explain it. README removes the machine bootstrap and lock overlay sections.

### Removed

- **The venv provider.** `repoman.cliProvider`, `REPOMAN_CLI_PROVIDER`,
  `REPOMAN_TOOLCHAIN_VENV`, and the venv `PATH` setup no longer exist.
- **`repoman-sync --machine`.** The flag now exits `2` and says that Vendomat owns the
  closure. `--no-local`, `REPOMAN_LOCK`, `REPOMAN_LOCAL_LOCK`, and `REPOMAN_ROOT` go with
  it.
- **The lock model that 0.7.2 added.** This repo no longer parses `repoman.lock` or
  `repoman.local.lock`. The recorded `repoman-toolchain.toml` manifest and its
  `[toolchain].synced_from` field no longer exist.
- **Four doctor rows.** `toolchain:venv`, `toolchain:lock`, `lock:orphan`, and
  `deps:toolchain` no longer exist.
- **The `cliProvider` manifest key.** 0.9.2 accepts it again as a legacy key.

## 0.9.0 — repoman new and repoman adopt

`repoman new` and `repoman adopt` pass through to `copyroom new` and `copyroom adopt`.
RepoMan is now the single front door. Callers no longer need to know that copyroom owns
birth and adoption.

### Added

- **`repoman new` and `repoman adopt`.** Each command runs the copyroom command with the
  same arguments and returns its exit code unchanged. A missing `copyroom` exits `2`.

### Changed

- **README separates birth, adoption, and re-sync.** It now states what `adopt` does.
  `adopt` only reports unless you pass `--write`. `copyroom layer add` still places the
  template's files. README also says that `repoman devman migrate` needs no registration
  step, because devman finds `.devman/project.toml` on its own.
- **This repo removes its vendomat input and import.** The vendomat module now arrives
  from the system profile through the central `devenv.local.nix`. The settings from
  `devenv.nix` move to `vendomat.toml`.
- **`repoman.lock` pins gitman v0.8.0 and pyjutsu v0.22.0 together.** gitman pins pyjutsu
  by direct reference. uv rejects two direct references for one package.

## 0.8.2 — cliProvider in the manifest (project 039)

`.repoman/project.toml` accepts a `cliProvider` key (`venv` or `store`). Ten repos decline
the store toolchain through the `repoman.cliProvider` option, which the project planned to
remove. Without a manifest key, removal would move all ten onto a store closure that they
never imported. The manifest validator and the option enum share one list, so neither
accepts a value that the other rejects. The `repoman-consumer-module` flake check now
evaluates the module against two fixture roots, one with a manifest and one without.

## 0.8.1 — repoman.enable defaults to true (project 039)

`repoman.enable` now defaults to `true`. The module is present only when a consumer's
central `devenv.local.nix` imports it, so the import itself is the enable signal. Set
`repoman.enable = false;` to opt a repo out while it keeps the import.

## 0.8.0 — manifest-driven roster (project 039)

Project 039 stops every consumer from pinning RepoMan. The roster moves from a Nix option
into a tracked manifest. The flake packages the module, so one machine can pin it once.

### Added

- **`.repoman/project.toml`.** A tracked manifest holds the roster: `schema = 1` and
  `managers = [...]`. The module rejects an unknown field, a missing or unsupported
  `schema`, and an unknown manager. A repo without the file gets the default roster `copy
  git test`. The `repoman.managers` option stays as a compatibility fallback.
- **Flake `packages.repoman-module`.** It installs the whole `modules/` tree under
  `$out/share/repoman/module/`.
- **Flake `nixosModules.default`.** Its `repoman.installConsumerModule` option (default
  `true`) installs that package and links `/share/repoman` into the system profile. A
  consumer's `devenv.local.nix` can then import the module without its own pin.
- **A `repoman-consumer-module` flake check.** It evaluates the real module against a
  fixture root.
- **`repoman devman status` and `repoman devman migrate`.** `status` reports whether a
  repo needs the Devman manifest. `migrate` proposes one, and `--apply` writes
  `.devman/project.toml` only.
- **The router lists only present skills.** The routing table names a manager only when
  `<skills_dir>/<command>/SKILL.md` exists.

### Fixed

- **`repoman.lock` named stale releases.** `[repoman]` said v0.7.1 against a 0.7.5
  checkout. `[managers.git-vendomat]` said v0.3.2 against 0.3.6. The doctor reported both
  as stale recorded metadata. Both pins now name current releases.

### Changed

- **`repoman.cliProvider` defaults to `store`.** The `venv` default gave templateer two
  owners: the shelf venv inside a devenv and the store closure outside it. `PATH` order
  decided which one a command got.
- **This repo takes its agent surface from the central link plane.** It stops tracking
  `.agents/skills/*` and the `.loci` vault. Links into the central overlay replace them.
- **The devman consumer integration leaves this repo.** The `devman` input, the
  `devman/modules` import, and the `devman` option block no longer exist.
  `.devman/project.toml` is the registration now.

### Removed

- **The options `repoman.template`, `repoman.installSkills`, and `repoman.skillsDir`.** A
  2026-09-15 measurement of 23 importing repos found that none set `installSkills` or
  `skillsDir`. The skills directory is now fixed at `.agents/skills`.

## 0.7.5 — derived version, gated releases

`repoman 0.7.4` reported `repoman 0.7.3`. `src/repoman/__init__.py` kept a hand-written
copy of the version, and `gitman version bump` edits only `pyproject.toml` and `uv.lock`.
A test asserted that the two matched, but nothing ran it before the tag.

### Added

- **A verify gate on publish and release.** `gitman.toml` sets `[publish].verify` to
  `testee verify --mode ci` inside `devenv shell`. `release` inherits it. The suite now
  runs before a tag exists.

### Fixed

- **`__version__` reads the installed distribution.** There is one version now, and
  nothing to keep in step. A source tree that was never installed reports `0+unknown`.

## 0.7.4 — fleet-lock gate

`devenv.lock` must not name one machine's working trees. Before this release a unit test
enforced that rule, and ordinary work turned the suite red. The check now runs at push.

### Added

- **A pre-push gate for `devenv.lock`.** A new `.pyjutsu-hooks.toml` runs
  `scripts/check-fleet-lock.py` before `gitman push`. The script blocks the push when any
  lock node names a local path. gitman pushes through pyjutsu, which never runs git hooks,
  and `[publish].verify` does not cover `push`. A pyjutsu hook is the one seam that covers
  push, publish, and release.
- **`relock`.** The script re-locks `devenv.lock` from the published tags. It moves the
  overlay aside inside the repo, not into `/tmp`, so an interrupted run leaves it easy to
  find. A trap restores the overlay on any exit.

### Fixed

- **The committed `devenv.lock` named local checkouts.** It pinned vendomat, docman, and
  shellij at `file:///home/...`, because a shell with the overlay active had re-locked it.
  Each node now names its published tag.
- **The store `bin` expression is shell-safe.** Its `:?` message held a quoted word and an
  apostrophe. Every manager task exec puts the expression inside double quotes. The quote
  and the apostrophe broke that shell string. Every store-mode task then failed with
  `unexpected EOF while looking for matching`. A new guard unescapes the Nix string before
  it checks it.

### Changed

- **`tests/test_fleet_shape.py` stops checking `devenv.lock`.** devenv rewrites the lock
  on every shell entry. The test keeps the checks on hand-edited files and guards that the
  gate stays wired.
- **The gate covers every lock node.** The exemption for transitive nodes no longer
  exists. A consumer inherits all nodes, and Vendomat v0.3.3 pins every input to a
  published tag.
- **vendomat moves to v0.3.4 in editable mode.** Vendomat v0.3.4 delivers the shared
  command closure by default, and this repo builds one command in it.
  `vendor.toolchain.mode = "editable"` keeps a tagged `repoman` from coming before this
  checkout on `PATH`.

## 0.7.3 — vendomat v0.3.3

`devenv.yaml` pins vendomat v0.3.3, and the release re-locks `devenv.lock` to match. The
re-locked file still named local checkouts. 0.7.4 fixes that.

## 0.7.2 — coherent machine toolchain and fleet-shape inputs (projects 18 and 023)

Project 18 fixes `repoman-sync --machine`. Project 023 commits the fleet shape and adds a
store provider. 0.9.1 later retired the venv toolchain, the lock model, and `--machine`.

`repoman-sync --machine` could report success for a shared venv that no installed manager
supported. A `path:` manager installs with `--editable`. Its code follows the checkout,
but its recorded metadata stays at the last sync. On one machine gitman's code was 0.6.0
(`pyjutsu>=0.20.0`) and its metadata said 0.4.2 (`pyjutsu>=0.15.0`). So pyjutsu 0.15.0
passed the resolver, `uv pip check`, and `repoman doctor`. Then `gitman status` failed
with `AttributeError: 'Workspace' object has no attribute 'git'`.

`repoman.lock` used to commit the dev shape: five managers as `path:` entries under one
user's home. A vendomat hook rewrote the sources into the portable shape at push time.
That reversed the normal order: the repo kept the machine-specific fact under version
control and derived the portable one. The rewrite matched literal text, so it could not
express a pin update. It also left origin permanently divergent. The lock now commits the
fleet shape, and each machine overrides it locally.

### Added

- **`repoman.cliProvider`, the store/venv seam.** The option takes `venv` or `store` and
  defaults to `venv`. Under `store`, an unset `REPOMAN_TOOLCHAIN_BIN` fails the task and
  never falls back silently. The module also exports `REPOMAN_CLI_PROVIDER`, so `repoman`
  resolves commands the way the Nix tasks do.
- **A store provider for `repoman-sync`.** Under `store`, the script installs no packages.
  It verifies the closure at `REPOMAN_TOOLCHAIN_BIN`, prints the store manifest that
  Vendomat writes, and installs the skills. A surviving `repoman.lock` is a hard error
  there, because Vendomat's `flake.lock` alone is authoritative.
- **A fleet-shape `devenv.yaml`.** Every first-party input names a published tag. The
  untracked `devenv.local.yaml` overlay points the same inputs at local checkouts, and
  devenv merges it over the committed file. The `repoman` self-input stays
  `path:./modules`, because a git input copies only tracked files.
  `tests/test_fleet_shape.py` guards the committed shape.
- **`deps:toolchain` doctor rows.** `version:<entry>` compares the venv against the lock.
  These rows compare it against the managers. A loose pseudo-entry (`wheel:pyjutsu>=0.8`)
  can satisfy the lock and still leave a version that no manager supports.
- **A `url:` source in `repoman.lock`.** It names one published artifact by direct
  reference, so it needs no wheelhouse and no `UV_FIND_LINKS`. The pyjutsu entry uses it.
- **templateer on the machine toolchain shelf.** `repoman.lock` pins it to `v0.4.0`.
  Devman's changelog workflow runs it as a command.

### Fixed

- **`repoman-sync --machine` rebuilds every editable manager.** Each `path:` entry gets
  `--reinstall-package=<name>`, so the resolver reads the checkout's current requirements.
- **`repoman-sync --machine` verifies the result, not the command.** After the install, it
  checks that each `path:` manager's installed version matches its checkout. It also
  checks that every installed distribution's own `Requires-Dist` holds. A finding names
  the package, the constraint, and the installed version. The sync then exits `2` and
  records no manifest.
- **A failed resolution exits `2`.** An unsatisfiable constraint set is an infra/config
  error, not the domain decision that `1` implies.
- **`version:<key>` catches stale editable metadata.** It read a `path:` source as "always
  current", so it reported `OK gitman 0.4.2` for a checkout that ran 0.6.0. It now
  compares the installed version with the checkout's `[project].version`.

### Changed

- **`repoman.lock` commits the fleet shape.** repoman, copyroom, gitman, docman, and
  vendomat move from `path:` to `git+https://…@vX.Y.Z`. `repoman-sync --machine` now works
  on a clone with no working trees beside it. A fresh clone confirmed this with
  `--no-local` and `UV_FIND_LINKS` unset.
- **`repoman.local.lock` is the machine overlay.** Git ignores it, it uses the lock's
  schema, and it needs only `source`. It changes where a package comes from, never what
  the toolchain contains. An overlay key that the lock does not declare is a hard error
  that names the key. A missing overlay is normal and silent. `REPOMAN_LOCAL_LOCK`
  overrides the path, and `--no-local` skips the overlay.
- **The recorded manifest holds the merged shape.** `<venv>/repoman-toolchain.toml` was a
  verbatim copy of the lock. It now holds the lock with the overlay merged in. `checks.py`
  compares installed packages against this manifest. A copy of the committed lock would
  compare an editable install with a git pin. That would report a false version conflict.
- **The manifest records its origin as data.** A new `[toolchain].synced_from` field
  replaces two guesses. One was the `# synced from` comment. The other was the test in
  `_is_machine_lock` that `[repoman].source` is a `path:` that resolves to the repo root.
  That test breaks once the lock has the fleet shape: a fleet machine would warn "orphan"
  against its own lock.
- **gitman moves to `v0.6.1`.** The retired `vendomat.toml` named `v0.6.0`, but nothing
  ever installed that pin. `v0.6.0` pins pyjutsu by direct reference at v0.20.0. uv
  rejects two direct references for one package.
- **docman moves to `v0.2.0`.** The retired `vendomat.toml` named `v0.1.0`. That tag
  predates docman as a Python package and has no `pyproject.toml`.
- **`pyproject.toml` pins testee by git tag.** The retired `vendomat.toml` rewrote `testee
  = { path = "../testee" }` to a git tag on push. Without the tag, `uv sync` fails on any
  clone with no testee checkout beside it. No overlay is possible here, because uv refuses
  a `sources` table in `uv.toml`. To test against a local testee, run `uv run
  --with-editable ../testee testee verify`.
- **The flake builds on Python 3.13.** pyjutsu ships `cp313-abi3`, which cannot load on
  3.12. `AGENTS.md` records the 3.13 baseline.
- **`gitman.toml` loses its `[version]` table.** gitman ignores it and warns about it on
  every command. gitman 0.7.0 rejects it.
- **README gains "Where the local paths go".** The adoption snippet now pins a tag and
  uses `git+https://`. The `github:` shorthand cannot fetch the private repos in this
  family.

### Removed

- **The vendomat publish path for this repo.** `vendomat.toml`, `.pyjutsu-hooks.toml`, the
  installed `.git/hooks/pre-push`, and `refs/vendomat/published/origin/main` no longer
  exist. Vendomat's hermetic native wheel build and release upload stay as they were.
  `[managers.git-vendomat]` stays on the shelf for them.

## 0.7.1 — CopyRoom management

This repo joins the CopyRoom-managed fleet and the devman automation plane.

### Added

- **CopyRoom management.** The repo gains the `my-ai` personal layer
  (`.copier-answers.my-ai.yml`) and copyroom's canonical skills (`copyroom`,
  `copyroom-adopt`, `copyroom-template-edit`) under `.agents/skills/`. A seed `AGENTS.md`
  and the `CLAUDE.md` symlink come with them. `.gitignore` tracks `.agents/skills/` and
  ignores the rest of `.agents/`. This needs copyroom 0.7.4 or later.
- **The devman automation plane.** `devenv.yaml` declares the `devman` input, and
  `devenv.nix` enables it with the `base` group. `base:check` runs ruff over `src`, and
  `base:test` forwards to `repoman:test`.
- **The `shellij` input.** The meta-module imports shellij's devenv module when the input
  exists, so the dev shell gets shellij and zellij.
- **`gitman.toml`.** It names `main` as trunk.

### Changed

- **`docs/AGENT-FILES.md` names a fifth owner, the personal layer.** It also states that
  RepoMan generates the router per repo and never ships it as a static copy.

## 0.7.0 — doctor context preflight (project 13)

First release carrying the project-13 preflight (the 0.6.0 intermediate was never
released; 0.5.x/0.6.0 changelog history below describes the unreleased hardening
and self-hosting passes). Tagged `v0.7.0`.

`repoman doctor` no longer answers the wrong question. It classifies where it's
running *before* it runs any row check — a managed repo's devenv shell
(`REPOMAN_MANAGERS` set), a managed repo in a bare shell (`gitman.toml`/`.gitman`
present), or no managed repo at all. The two wrong contexts short-circuit with one
true statement plus the correct invocation (`cd <repo> && devenv shell -- repoman
doctor`) and exit `2` — instead of a pile of plausible-looking FAILs from a context
that was never established.

### Added

- **Context preflight (`checks.detect_context`).** `REPOMAN_MANAGERS` (exported
  only by the meta-module's `config.env`) proves a managed-repo shell — even the
  empty string, matching `_enabled()`'s unset-vs-empty distinction; `gitman.toml` /
  `.gitman/` in the cwd or an ancestor proves a managed repo in a bare shell;
  `DEVENV_*` / `REPOMAN_TOOLCHAIN_VENV` alone are explicitly NOT signals. `doctor`
  and `doctor --self-only` short-circuit identically with exit `2` and zero rows.
- **`repoman doctor --json`.** The context verdict + self-check rows as one JSON
  document — `{"context": {"ok","kind","detail","hint"}, "checks":
  [{"name","ok","detail","warn_only"}], "exit"}` — matching copyroom's doctor
  row shape, with `exit` repeating the process's exit code. Sub-manager reports
  still stream plain (composing sub JSON is a noted follow-up).
- **Project-14 seam.** The `not-a-repo` message will point at the bootstrap
  ceremony doc once it exists (guarded constant; inert today).

### Fixed

- **`lock:<key>` fail detail no longer implies a per-repo file.** Modern consumers
  have no `repoman.lock` (project 12); the row now names the recorded toolchain
  manifest it actually checks (`<venv>/repoman-toolchain.toml`) and re-runs
  `repoman-sync --machine`.

### Changed

- README: the `lock:<key>` / `toolchain:lock` row table names the recorded
  toolchain manifest explicitly; the Commands list gains `--json`; new "Running
  `repoman doctor` outside a repo" note.

## 0.5.1 — self-hosting dev shell (project 14 seam)

Repoman's own devenv shell is now a first-class managed repo. Before, the shared
machine toolchain was only on PATH inside *some* managed repo's shell, so birthing a
new repo required the undocumented host-repo trick (`cd copyroom && devenv shell --
copyroom new …`). Now the meta-module is imported into repoman's own shell
(`devenv.yaml` → `imports: [repoman]`) with the full roster wired
(`repoman.managers = ["copy" "git" "test" "doc"]`), so `copyroom new <target>` runs
directly from this checkout — the canonical bootstrap host for project 14's ceremony.

### Added

- **`devenv.yaml`: self-import the meta-module** (`repoman: url: path:./modules`,
  `flake: false`) + the `docman` input that approach-B provisioning requires.
  `copyroom`/`gitman`/`docman` are on PATH inside `cd repoman && devenv shell`;
  `REPOMAN_MANAGERS`/`REPOMAN_TOOLCHAIN_VENV`/`REPOMAN_SKILLS_DIR` are set.
- **Full roster in the dev shell** — `repoman.managers = [copy git test doc]`, so
  the shell doubles as a reference consumer of the whole suite.
- **testee declared as a per-repo uv dev dependency** (`[dependency-groups] dev` +
  `[tool.uv.sources]`), required for the `test` manager to be functional and for
  `repoman doctor` to stay green in-repo (`uv:test`).
- `.agents/skills/` gitignored — generated by `repoman install-skills` / consumer
  `repoman-sync`; AGENTS.md/CLAUDE.md remain committed by design.
- Guard tests locking in the self-import (imports, roster, no script shadowing,
  testee declaration).

### Fixed

- **The machine lock is no longer called an orphan.** Both `repoman doctor`
  (`lock:orphan`) and consumer-mode `repoman-sync` warned to "delete" a repo-root
  `repoman.lock` — which, in the repoman checkout itself, is the very manifest the
  toolchain synced from. The venv's recorded manifest pins its origin (`# synced from
  <lock>` / `[repoman].source`); matching fingerprints suppress the warning, consumer
  orphan locks still warn.

### Changed

- The dev shell's local `repoman-sync` wrapper was removed — the meta-module owns
  the script now (its two modes already default `REPOMAN_ROOT`/the lock to
  `DEVENV_ROOT`). Two definitions of the same script name would fail the eval.

## 0.5.0 — hardening pass

The theme: the diagnostic layer used to trust its environment more than the thing it
was diagnosing. It parsed without guarding, resolved binaries via `PATH` while
executing absolute paths, checked presence instead of currency, and computed
information it never printed.

### Fixed — correctness

- **`repoman doctor` no longer crashes on the inputs it exists to diagnose.** Only
  `TOMLDecodeError` was caught, so an unreadable/directory `pyproject.toml`, a
  permission-denied toolchain manifest, or a non-UTF-8 `SKILL.md` escaped as a
  traceback. All filesystem reads are guarded and reported as findings.
- **A crashed conductor exits `2` (infra/config), not `1`.** Under the shared
  contract `1` means "a domain decision is needed"; an unhandled traceback used to
  masquerade as one. `main()` now maps unexpected exceptions to `2` and
  `KeyboardInterrupt` to `130`.
- **`installed:<key>` validates the binary the nix tasks actually exec** — the
  absolute path under the toolchain (or consumer) venv — instead of trusting a `PATH`
  hit. When `PATH` resolves a *different* copy, that shadowing is reported.
- **PATH order in `modules/devenv.nix` corrected.** The consumer venv was prepended
  *after* the toolchain, so it won — exactly defeating the comment above it. A stale
  pre-migration manager CLI in `.devenv/state/venv/bin` could shadow the shared
  toolchain, leaving `doctor` green while `devenv tasks run` used another binary.
- **`repoman-sync` (consumer mode) runs the `repoman` it verified.** It gated on
  `-x "$toolchain_venv/bin/repoman"` and then invoked bare `repoman`.
- **Stale toolchains are now detected.** New `version:<entry>` rows compare what is
  installed in the shared venv against what the lock pins. `lock:<key>` only ever
  proved a key was *present* in the manifest.
- **`repoman-sync --machine` passes `--upgrade`.** Without it a range pin such as
  `wheel:pyjutsu>=0.8` counts as already satisfied, so re-syncing after a toolchain
  bump silently installed nothing.
- **`repoman.managers = [ ]` means "wire nothing".** An empty `REPOMAN_MANAGERS`
  fell through to the three core defaults.
- **A malformed `repoman.lock` produces a message, not a traceback** (missing
  `source`, non-table entry, invalid TOML, empty source) — and exits `2`.
- **The resolver→bash protocol is NUL-delimited.** A newline inside a lock `source`
  could inject an extra argument into `uv pip install` — relevant now that
  `REPOMAN_LOCK` invites machine-generated fleet locks.
- **Duplicate roster entries are collapsed**, so `REPOMAN_MANAGERS="git git"` no
  longer runs gitman's doctor twice or duplicates routing rows.
- **`REPOMAN_SKILLS_DIR` must be repo-relative.** An absolute value made
  `install-skills` write outside the repo entirely; `..` traversal is rejected too.

### Fixed — reporting

- **An unavailable manager explains itself.** `repoman status` printed a bare header
  and exited `2` in silence; `SubResult.available` was computed and never rendered.
  Results now carry a `reason` the CLI prints.
- **Sub-managers have a timeout** (`REPOMAN_SUB_TIMEOUT`, default 900s, `0` to
  disable) so a hung manager can't hang the conductor forever.
- The generated routing table follows the lifecycle spine rather than the order the
  roster happened to be written in.

### Added

- `repoman --version`.
- `README.md`, `LICENSE`, this changelog; `readme`/`license`/`authors` in
  `pyproject.toml`.
- `tests/conftest.py` isolates every test from an ambient devenv shell — previously a
  test could read, and one did *execute*, the real machine toolchain.

### Changed

- `install-skills` writes atomically (temp file + `os.replace`); a partial write left
  a truncated `SKILL.md` that the next `doctor` reported as healthy.
- `repoman-sync --machine` writes its manifest atomically, rejects trailing
  arguments, checks that `uv` is on `PATH`, and `--help` no longer spills into the
  script body.
- Dead code removed: the resolver's unreachable `REPOMAN_MANAGERS` selection branch
  (machine mode always installs the whole lock).

## 0.4.0 and earlier

See `.scratch/projects/` for the project-by-project history.
