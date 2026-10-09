# RepoMan — Concept

> **One devenv import that turns a repo into a managed agentic repo.**
> Import the module and name your managers in `.repoman/project.toml`. RepoMan wires
> their tasks, generates one router skill, and checks its own wiring with `repoman doctor`.
> RepoMan installs no manager commands. Vendomat supplies them, except testee, which the
> repo declares.

RepoMan is the **conductor** for the `*man` family. It is a per-repo lifecycle front
door. It *composes* the individual managers and does not replace them.

This document describes RepoMan 0.9.2. Blocks that start with **Superseded** record
design history.

---

## 1. The family it belongs to

RepoMan does not invent a new architecture. It composes an existing one. Every
`*man` tool is the same pattern applied to a different domain.

| Manager | Roster key | Domain it owns | Wraps |
| --- | --- | --- | --- |
| **copyroom** | `copy` | templating / scaffolding / project lifecycle / convergence | Copier |
| **gitman** | `git` | version control | native jj and `gh`; gitman opens workspaces |
| **testee** | `test` | verification (test / lint / typecheck / format) | pytest, ruff, ty |
| **docman** | `doc` | docs (build / lint / check) | zensical |

The lifecycle roster is exactly these four. Three neighbors are not lifecycle managers:

- **devman** is the automation plane. Its central overlay owns `.agents/` in every repo.
- **Vendomat** is the Nix layer. It builds the store closure that holds the manager
  commands.
- **shellij** is the terminal: durable remote workbenches on Zellij and Yazi. RepoMan
  imports shellij's own devenv module when a repo declares a `shellij` input (see §4).

The managers share a contract:

- **Single interface** — the agent stops running raw tools ad hoc and asks one command.
- **Pydantic-normalized output** → a compact, structured, actionable report.
- **Typer command-line interface (CLI)** with a `doctor` command.
- **Runs inside `devenv shell`** as its execution boundary.
- **A `0/1/2` exit-code contract**: clean / act-on-findings / tool-could-not-run.
- **Distributed as a devenv module** that a repo imports.

The four lifecycle managers share the family pattern. RepoMan is the conductor.

---

## 2. What RepoMan is (decisions)

Brainstorming settled four decisions. The code still follows them.

- **Scope: per-repo conductor.** RepoMan lives inside one repo and orchestrates the
  `*man` tools for the agent. Fleet and workspace management is out of scope by design.
  shellij's project registry already covers per-project session discovery.
- **Primary form: a devenv meta-module.** RepoMan is *mainly* one devenv module. The
  module wires the managers in the repo's roster. The Python side is a thin conductor.
- **Agent surface: pass-through, one router.** Each manager keeps its own report and
  its own skill. RepoMan owns the lifecycle order and generates one file, the router
  skill. It aggregates nothing at runtime and does **not** re-model their reports.
- **copyroom is the core pillar.** It is the *convergence engine*. It births repos with
  the right managers pre-wired, adopts existing repos, and converges the template layers
  inside one repo. It has no cross-repo command. The other managers are organs. The
  *genome* is the base template that copyroom renders, `template-py` or `template-nix`.

Later projects settled two more decisions (see §6):

- **RepoMan installs no manager commands.** Vendomat's store closure supplies them for
  `copy`, `git`, and `doc`. testee is the one per-repo dependency.
- **RepoMan writes one file in normal operation.** It is the router skill. devman links
  every other skill.

---

## 3. The consumer experience (the whole point)

A repo gets the module in one of two ways. First, devman's central overlay imports it.
The overlay's `devenv.local.nix` imports
`/run/current-system/sw/share/repoman/module/devenv.nix` from the machine profile.
Second, the repo imports the module itself from `devenv.yaml`. RepoMan's own repo and
`tests/consumer-example` do so:

```yaml
# devenv.yaml — only when the repo imports the module itself
inputs:
  repoman:
    url: "git+https://github.com/Bullish-Design/repoman?dir=modules&ref=refs/tags/vX.Y.Z"
    flake: false
imports:
  - repoman
```

Importing the module enables RepoMan. `repoman.enable` defaults to true, so a repo needs
no line for it. Two small declarations complete the setup. `.repoman/project.toml` is
optional. It replaces the default roster, `copy git test` (see §4). `pyproject.toml`
declares testee under `[dependency-groups] dev`, because `test` is in the default roster
(see §6).

Then run `devenv shell` and `repoman-sync`. The repo now has the roster's manager tasks
and the router skill under `.agents/skills/repoman/`. The manager commands are on `PATH`,
from Vendomat's closure. A top-level `repoman doctor` checks RepoMan's own wiring. Each
manager's own `doctor` checks that manager. Vendomat's consumer module exports the closure's location. A repo
imports that module next to RepoMan's.

---

## 4. Module options and the roster manifest

```nix
repoman.enable = true;    # default; importing the module is the enable signal
```

The former `repoman.nativeBuild` option is removed. It added `maturin` and Rust so a
consumer could build pyjutsu from source. gitman 0.12 does not use pyjutsu, and a fleet
search on 2026-10-06 found no repo that set the option to `true`.

A second option, `repoman.toolchainBin`, is internal and read-only. It holds the shell
expression for `$REPOMAN_TOOLCHAIN_BIN`. Manager modules interpolate it into task
commands. A repo can set `repoman.enable = false` to keep the import and run no RepoMan.
The skills directory is not an option: the module sets `REPOMAN_SKILLS_DIR` to
`.agents/skills`.

**The roster is not a Nix option.** It lives in the tracked file `.repoman/project.toml`:

```toml
schema = 1                           # required; the only supported value is 1
managers = ["copy", "git", "test"]   # optional; any of copy, git, test, doc
cliProvider = "store"                # legacy; validated, then ignored
```

The module parses and validates the file in Nix (`modules/devenv.nix`). It rejects
unknown fields, a missing `schema`, and any `schema` other than 1. It rejects an unknown
manager name and a `cliProvider` other than `store` or `venv`. An absent file means the
default roster. `cliProvider` has no effect. It is a legacy key that Vendomat's consumer
config owns.

Manager roster, in default tiers:

- **Core (default on):** `copy` (copyroom), `git` (gitman), `test` (testee).
- **Publish:** `doc` (docman). It is never in the default roster.

The roster leaves Nix by two channels. The module passes it to the manager modules as
the module argument `repomanManagers`. It exports it to the shell as `REPOMAN_MANAGERS`,
space-joined. The Python side reads only the variable. Unset means the default roster.
Empty means wire nothing.

> **Superseded by project 039 (manifest-driven roster).** Earlier versions declared four
> Nix options: `repoman.managers`, `repoman.template`, `repoman.installSkills`, and
> `repoman.skillsDir`. Project 039 removed the last three and moved the roster into
> `.repoman/project.toml`. Release 0.9.1 removed `repoman.managers`. This section also once
> sketched a `repoman.<manager>.*` pass-through for component options. No such options
> exist.

**shellij is not in the roster.** RepoMan has no `repoman.session.*` config and no roster
entry for it. RepoMan presence-imports shellij's own devenv module with
`lib.optional (inputs ? shellij)`. A repo that declares the `shellij` input gets the module.
That module installs shellij, Zellij, and Yazi, adds a guarded `shellij open` hook to
`enterShell`, and sets `YAZI_CONFIG_HOME`. The gate is the input alone, so
`repoman.enable = false` does not remove the module. This repo declares no `shellij` input.

---

## 5. The thin `repoman` CLI

RepoMan owns the lifecycle order and generates one file. It aggregates nothing at runtime.
The CLI has four commands:

```text
repoman managers        # list the managers in the roster: key, command, tier, summary
repoman doctor [--json] # self-check of RepoMan's own wiring
repoman install-skills  # generate the router skill from the roster
repoman --version
```

`repoman doctor` checks its context first. Outside a managed repo's `devenv shell`, it
prints one message and exits `2`. Inside, it runs the self-check rows and the skill rows.
It runs no manager. With `--json`, it prints one JSON document and nothing else.

The skill rows are roster-derived. The lint expects `writing` always, each enabled
manager's skill, and copyroom's two sub-skills only when `copy` is enabled. devman
requires exactly one universal skill, `writing`, and refuses to universalise `gitman` and
`copyroom`. The rows are `ok` or `warn`. They never gate.

**The lifecycle spine.** The router states the order. It has three ordered phases:
`change → verify → integrate`. `integrate` is native jj: `jj describe`, a bookmark, `jj git push`, then a `gh`
pull request. Two activities have no order: `birth / converge` (copyroom) and `docs` (docman).
Two laws apply: verify before you integrate, and never integrate on red.

To check a manager, run that manager's own `doctor` and read its report. To birth or
adopt a repo, run `copyroom new` or `copyroom adopt`.

> **Superseded by project 040 (the family contract): the aggregating CLI.** Earlier
> versions ran the managers and merged their results. RepoMan removed these:
>
> - `repoman status`. It mutated version-control state through `gitman status`, which
>   snapshots `@`, mirrors refs, and writes `.gitman/markdown`. It carried no verdict,
>   because `testee list-runs` always exits `0`. It failed in any repo with no Copier
>   answers file, because `copyroom status` exits `1` there.
> - The sub-doctor loop in `repoman doctor`, and the `--self-only` flag. Doctor now checks
>   RepoMan's own wiring only, so `doctor --json` is pure JSON. The loop merged six
>   incompatible exit-code dialects into one number. gitman's doctor returns only `0` or
>   `2`. copyroom returns `1` for infrastructure faults. docman returns `0` or `2`, and `2`
>   for a broken link. linkman uses `10` to `13`. loci-core returns `1` for everything.
>   `worst_exit` mapped any code outside `0` to `3` to `2`, so distinct failure classes
>   collapsed. The router skill is the aggregation. It aggregates knowledge, which loses
>   nothing. Exit-code aggregation loses by construction.
> - `repoman new` and `repoman adopt`. They hid which tool owns birth, had no timeout,
>   and their `--help` never reached copyroom. Call `copyroom new` and `copyroom adopt`.
> - `repoman devman status` and `repoman devman migrate`. devman deleted the
>   `devman = {...}` devenv option that they parse on 2026-09-19. `migrate` raises
>   `MigrationError` on this repo. devman writes no manifests by design. A person
>   maintains `.devman/project.toml` by hand, and the template seeds it.
> - `REPOMAN_SUB_TIMEOUT`. It governed only the sub-manager calls.

> **Superseded by project 040: the spine `scaffold → change → verify → save → docs`.**
> `save` was a hidden, deprecated alias for gitman's `describe`. The real sequence is
> `describe`, then `land`, then `push`. `scaffold` happens before the repository exists,
> so it cannot be a phase of it. `docs` has no place in the order. The spine is now three
> phases, and the two activities sit outside it.

**Abandoned.** Earlier text proposed three gated lifecycle verbs:

- `repoman verify` would run testee.
- `repoman save -m` would run testee verify, then gitman describe, gated on green.
- `repoman release` would run testee ci, gitman release, then docman.

`cli.py` has none of them, and the project abandoned them. The router skill states the
order instead.

---

## 6. How composition works

Three layers cooperate. RepoMan owns the first two. Vendomat owns the third.

1. **Nix layer (the meta-module).** `modules/devenv.nix` declares `options.repoman.*`
   and reads the roster. It statically imports one thin wiring module per manager from
   `modules/managers/`. Imports cannot depend on `config`. So the meta-module imports
   every manager module, and each one gates its own `config` on roster membership. This
   is the standard module-system idiom. A manager module contributes that manager's
   tasks, and sometimes packages.

   The meta-module also exports `REPOMAN_MANAGERS` and `REPOMAN_SKILLS_DIR`. It puts the
   closure's bin directory first on `PATH` and defines `repoman-sync`.

2. **Python/CLI layer (the conductor).** The `repoman` CLI reads `REPOMAN_MANAGERS`.
   It lists the managers, self-checks the wiring, and generates the router. It runs no
   manager. The variable is the only channel. The CLI never reads `.repoman/project.toml`.
   One list feeds the Nix modules, the CLI, and the router skill, so the three cannot drift.

3. **The toolchain (Vendomat's store closure).** Vendomat builds the manager commands
   once, in one pinned Nix store closure. Vendomat's `flake.lock` is authoritative for
   their versions. RepoMan finds the closure by environment variable only.
   `REPOMAN_TOOLCHAIN_BIN` names the bin directory. `REPOMAN_TOOLCHAIN_MANIFEST` names
   the provenance manifest, which defaults to `share/vendomat/toolchain.json` in the closure.
   Vendomat exports both, so RepoMan guesses no path.

A missing closure fails at the point of use: a manager task stops and names
`REPOMAN_TOOLCHAIN_BIN`. Shell entry only warns, so a broken closure never blocks the shell.

**Toolchain versions reach a repo in two ways.** The genome pins published tags in its
`copier.yml`, and `copyroom update` applies those pins to one repo at a time. Vendomat's
`flake.lock` pins the closure that supplies the manager commands. copyroom has no
cross-repo command: it converges the template layers of one repo. A past fleet rollout
ran from a scratch script that no longer exists.

**Two install models.** The family splits on one question: does the tool import the
consumer's own code?

- **Toolchain managers** (`copy`, `git`, `doc`): the command comes from Vendomat's
  closure.
- **uv manager** (`test`): the command comes from the repo's own virtual environment
  (venv). `pyproject.toml` declares testee under `[dependency-groups] dev`. testee's
  tools (pytest, ruff, and ty) import the consumer's package, so they must run in that venv.

The toolchain managers live outside the repo's venv, so `uv sync` prunes nothing of
theirs. `Manager.install` in `src/repoman/registry.py` encodes the split. `repoman doctor`
checks a toolchain manager against Vendomat's manifest. It checks a uv manager against
`pyproject.toml`.

**`repoman-sync` installs nothing.** It checks that the closure exists and holds
`repoman`. It prints the closure's provenance from `toolchain.json`. Then it runs
`repoman install-skills`. It exits `2` when the closure is missing or incomplete, and for
the retired `--machine` flag. It also exits `2` in a consumer repo that still has a
`repoman.lock`, because that file is obsolete there.

**One generated file.** RepoMan writes `<DEVENV_ROOT>/.agents/skills/repoman/SKILL.md`, the
router skill. `repoman install-skills` renders it from
`src/repoman/templates/entrypoint.SKILL.md.j2` and the roster.

devman's central overlay (`~/.config/devman`) owns `.agents/`. The overlay holds one
hand-authored relative symlink per skill, each into a shared skill pool.
`devman-link reconcile` creates only the machine-local views, such as `.agents`. No repo
tracks skills, and copyroom does not write them. RepoMan writes no other file. See
`docs/SKILLS.md` and `docs/AGENT-FILES.md`.

**Managers may contribute nix-level provisioning, not only commands.** A manager module
may add system `packages` and language toolchains (`languages.*`) to the consumer devenv.
It does so only when the manager is in the roster.

`modules/managers/gitman.nix` adds `git` and nothing else. `copyroom.nix` adds `git` and `gnupatch`. `docman.nix` imports docman's own
devenv module when the repo declares a `docman` input.

> **Superseded by gitman's project 32 (the pyjutsu wheel pin).** Project 01 first showed
> this pattern with gitman's Rust need. The need was real when project 01 measured it. A
> plain `uv pip install` could not satisfy pyjutsu, so the spike built it from a sibling
> checkout. Every repo that selected `git` then pulled `maturin` and Rust.
>
> That need has ended. gitman 0.12 is work-only and standard-library only. It needs no
> Rust and no pyjutsu, so the `repoman.nativeBuild` option is removed. Only pyjutsu's own
> repo needs Rust in its dev shell, and it does not import RepoMan's module.

**De-risking note.** The original open question was whether devenv supports transitive
Nix *inputs* from an imported remote module. It does not. The manager commands arrive in
Vendomat's closure, so RepoMan needs no extra input for them. docman's and shellij's own
modules need inputs that the repo declares itself. RepoMan imports each one only when the
input exists, as in `lib.optional (inputs ? docman)`. The spike proved this (see
`SPIKE.md`).

> **Superseded by project 12, then by project 031 (how the commands reached a repo).**
> Two earlier mechanisms installed the manager commands. RepoMan retired both.
>
> 1. *Per-repo install.* `repoman-sync` installed the manager commands into each consumer's
>    venv from a per-repo `repoman.lock`. Project 11 measured the flaw. `uv sync` pruned 33
>    of 52 packages, because the project's own lock did not name them.
> 2. *Machine venv (project 12).* The pure-CLI managers moved to one system-wide venv.
>    `repoman-sync --machine` installed them from a machine `repoman.lock`. Project 12 also
>    drew the install-model split that this section still describes.
>
> Project 031 adopted Vendomat's store closure. Release 0.9.1 then removed the venv
> provider, `repoman-sync --machine`, and the lock model. Vendomat's `flake.lock` now
> carries the goal that the lock files served: one toolchain that moves in lockstep.
> RepoMan retired these names:
>
> - `repoman-sync --machine`
> - `repoman.lock`, `repoman.local.lock`, and the `[managers.<m>-<dep>]` lock entries
> - the lock overlay and the fleet-shape versus dev-shape lock split
> - `REPOMAN_LOCK`, `REPOMAN_LOCAL_LOCK`, and `--no-local`
> - `REPOMAN_TOOLCHAIN_VENV` and `REPOMAN_CLI_PROVIDER`
> - per-repo venv installs of manager commands
> - `cliProvider` as a binary selector

---

## 7. Repo layout for RepoMan itself

```text
repoman/
  devenv.yaml          # RepoMan's own dev shell inputs (it imports its own module)
  devenv.nix           # RepoMan's own dev shell (working ON repoman)
  flake.nix            # packages the module for the machine profile
  .repoman/project.toml  # this repo's roster: copy git test doc
  modules/
    devenv.nix         # ← THE meta-module consumers import (options + roster + wiring)
    managers/          # copyroom.nix, gitman.nix, testee.nix, docman.nix
                       #   per-manager wiring, gated on membership in the roster
    scripts/
      repoman-sync.sh  # verify the closure, then generate the router skill
  src/repoman/
    cli.py             # thin Typer CLI: managers, doctor, install-skills
    registry.py        # the manager roster + tiers + command mapping + install model
    checks.py          # the doctor self-check
    skills.py          # the router skill generator (template in templates/)
    devman/            # skill-link lint
  tests/
    consumer-example/  # throwaway repo that imports the meta-module (the spike)
  docs/                # SKILLS.md, AGENT-FILES.md
  CONCEPT.md
  SPIKE.md
```

The center of gravity is **Nix** (`modules/devenv.nix` + `managers/`). The Python is a
slim conductor.

---

## 8. Open questions / next steps

Each item shows its status: **done**, **abandoned**, or **open**.

- ~~**`repoman-sync` resolution**~~ — **abandoned.** The single `repoman.lock` design
  shipped and worked. Vendomat's store closure replaced it. `repoman-sync` installs
  nothing. See §6.
- ~~**`repoman new`**~~ — **abandoned.** `repoman new` and `repoman adopt` were thin
  pass-throughs. RepoMan removed them. Call `copyroom new` and `copyroom adopt` (see §5).
- ~~**Skill merge narrative**~~ — **done.** `repoman install-skills` generates the router
  skill from the roster, and `repoman-sync` runs it. `docs/SKILLS.md` has the design.
  The three follow-ups ended differently:
  - Installing sub-skills — **abandoned.** devman links the manager skills from a shared
    pool. RepoMan generates the router only (`docs/AGENT-FILES.md`).
  - `doctor` as a skill linter — **partly done.** `repoman doctor` lints the skill link set
    (`skill:tool-shipped`, `skill:genome-overlay`). It checks that each manager skill defers
    to the router (`skill:<key>:defers`, warn only). A check for colliding triggers is
    **open**.
  - Conflict-precedence table — **open.** `docs/SKILLS.md` lists it as an open question.
- ~~**gitman & native toolchains**~~ — **done** (project 01, guide 1).
  `modules/managers/gitman.nix` proved that the meta-module can provision nix-level
  toolchains, not only commands. The proof used gitman's Rust need, which has since ended
  (see §6). gitman 0.12 needs no Rust, and `repoman.nativeBuild` is removed. See §4, §6,
  and `SPIKE.md`.
- ~~**Lifecycle verbs**~~ (`repoman verify`, `save`, `release`) — **abandoned.** The
  router states the order instead (see §5).
