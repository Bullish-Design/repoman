# Platform investigation — repoman, devman, agentman, and the canonical devenv

**Date:** 2026-09-18
**Repo:** repoman (read-only investigation; nothing in any repo was changed)
**Input:** `canonical-devenv-development-platform-concept.md`

Every claim below carries a `path:line` citation or a recorded measurement. Where
I infer, I write **INFERRED**. Where two sources disagree, I quote both.

---

## 0. The one-paragraph answer

The canonical-devenv concept describes an architecture that repoman **already had**
and is **actively leaving**. `modules/` is a versioned devenv module tree imported
through `devenv.yaml`; that is the concept's core mechanism. Project 039 moved that
module to a machine path, `/run/current-system/sw/share/repoman/module/devenv.nix`,
and twelve repositories have migrated. The concept's §16 argues against exactly that
move. So the decision is not "build a canonical devenv repo". The decision is
**versioned input or machine path**, and the fleet currently answers both at once.
My recommendation: keep the versioned input, delete the machine-path delivery, and
solve the fleet-wide bump problem — the real reason 039 exists — with copyroom,
which is already the convergence engine.

---

## 1. The map

### 1.1 Four planes, not one

The `*man` fleet is not one system. It is four planes that meet in a devenv shell.

```
┌─ PLANE 1 ─ configuration (nix module) ────────────────────────────────┐
│ repoman modules/devenv.nix                                            │
│   options.repoman.{enable,managers,cliProvider,toolchainBin,          │
│                    nativeBuild}                                       │
│   imports managers/{testee,copyroom,gitman,docman}.nix                │
│   contributes tasks repoman:test, repoman:vc:status,                  │
│     repoman:template:status, repoman:docs:{doctor,build}              │
│   contributes packages git, gnupatch, (maturin + rust if nativeBuild) │
│   contributes scripts.repoman-sync, env.REPOMAN_*, enterShell PATH    │
│                                                                       │
│ DELIVERED THREE WAYS — see §2.1                                       │
│   a. devenv.yaml input + `imports: - repoman`      (11 repos)         │
│   b. /run/current-system/sw/share/repoman/module   (12 repos)         │
│   c. path:./modules                                (repoman itself)   │
└───────────────────────────────────────────────────────────────────────┘
                  │ names commands, never ships them
                  ▼
┌─ PLANE 2 ─ toolchain (where the binaries are) ────────────────────────┐
│ cliProvider = "venv"   ~/.local/share/repoman/venv                    │
│                        built by `repoman-sync --machine`              │
│                        from repoman.lock + repoman.local.lock         │
│ cliProvider = "store"  $REPOMAN_TOOLCHAIN_BIN, a vendomat Nix closure │
│                        DEFAULT (modules/devenv.nix:186)               │
│ testee                 NOT here — per-repo uv dev dependency          │
└───────────────────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─ PLANE 3 ─ link overlay (devman) ─────────────────────────────────────┐
│ ~/.config/devman, a git+jj repo, 52 projects                          │
│ /run/current-system/sw/share/devman/link-module.nix declares          │
│   options.devman.link; enterShell runs `devman-link reconcile`        │
│ symlinks INTO each repo:                                              │
│   .envrc            -> common/envrc                                   │
│   devenv.local.nix  -> projects/<p>/devenv.local.nix   (bootstrap)    │
│   .agents           -> projects/<p>/agents                            │
│   .claude/skills    -> projects/<p>/agents/skills                     │
│   .loci             -> ~/Notes/1_Projects/<p>                         │
└───────────────────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─ PLANE 4 ─ convergence (copyroom) ────────────────────────────────────┐
│ `copyroom new` / `adopt` / `update` — the genome                      │
│ `copyroom agent-files export` writes the canonical skill set          │
│   into <repo>/<agent.skills_dir>/  (default .agents/skills)           │
└───────────────────────────────────────────────────────────────────────┘
```

The bootstrap link is circular by construction, and deliberately so.
`devman_link/reconcile.py:34-40` states it: *"the bootstrap link must exist before
the next shell entry can evaluate anything"*. `devenv.local.nix` is a symlink that
devman writes, and devenv then evaluates it to learn which links devman should write.

### 1.2 What a manager is

There is **no written contract**. There is a dataclass and a convention.

`src/repoman/registry.py:14-56` defines `Manager` with fields `key, command, tier,
summary, doctor, status, skill, route_when, nix_input, install, package`.
`install` is validated against `{"toolchain", "uv"}` (`registry.py:50-56`). That
single field is the whole toolchain-vs-uv distinction the brief asks about:

- `install = "toolchain"` — the CLI is pure Python, lives once in the machine
  toolchain, resolved via `checks.manager_binary()` (`checks.py:201-212`).
- `install = "uv"` — the CLI runs inside the consumer's own code and is a per-repo
  uv dev dependency. **testee is the only one** (`registry.py:71-108`).

The roster is four entries: `copy`→copyroom, `git`→gitman, `test`→testee,
`doc`→docman. `DEFAULT_MANAGERS = ["copy","git","test"]` (`registry.py:110`).

`repoman.managers` gates **wiring only** — which tasks and skill rows appear. It has
not gated installation since project 12. `modules/devenv.nix:22-27` says so:
*"`repoman.managers` selects which manager tasks/skills are WIRED — it no longer
gates toolchain installation."* The lock installs every entry regardless
(`repoman.lock`, header).

The closest thing to a written contract is prose in `AGENTS.md:10-16`:
*"RepoMan writes exactly one file, the router; copyroom ships or the genome
converges every other skill."* `registry.py:5-6` adds: *"RepoMan never models a
manager's report — it only knows how to invoke each one."*

**Could devman or agentman satisfy it as-is?** No, and for different reasons.
- **devman** is not a per-repo lifecycle tool. It is a machine plane. It has no
  place in a per-repo roster.
- **agentman** fails every mechanical requirement: no `[project.scripts]` console
  script, no `doctor` subcommand, no `modules/` or `nix/` devenv module, no shipped
  skill (all four confirmed absent in `/home/andrew/Documents/Projects/agentman`).

### 1.3 Fleet inventory

`repoman module (how)`: `input` = pinned in the repo's own `devenv.yaml`;
`MACHINE` = imported from `/run/current-system/sw/share/repoman/module/devenv.nix`
by the central overlay; `-` = not wired.

| repo | repoman module (how) | devman ref | imports `devman/modules` | `.devman/project.toml` | `.repoman/project.toml` | `.agents` |
|---|---|---|---|---|---|---|
| agentman | input `v0.7.1` | v0.7.0 | **yes** | yes | no | link |
| argentic | MACHINE | – | no | yes | yes | link |
| copyroom | – | v0.5.1 | **yes** | no | no | link |
| eventic | MACHINE | – | no | yes | yes | link |
| flora | MACHINE | – | no | yes | yes | link |
| flora-core | input `main&rev=57473ad4` | – | no | yes | no | link |
| flora-qc | MACHINE | – | no | yes | no | link |
| forgelab | input `git+file://…` | v0.4.0 | **yes** | no | no | dir |
| image-gen-pipeline | MACHINE | – | no | yes | yes | link |
| inferference | input `path:/home/andrew/…` | – | no | no | no | dir |
| llgym | MACHINE | – | no | yes | yes | link |
| loci.nvim | MACHINE | – | no | yes | yes | link |
| lodestar | input `path:/home/andrew/…` | v0.5.1 | **yes** | no | no | dir |
| nix-desktop | input `git+file://…` | – | no | yes | no | link |
| nix-nvim | input `main&rev=57473ad4` | – | no | yes | no | link |
| nix-paseo | input `git+file://…` | – | no | yes | no | link |
| nix-secrets | MACHINE | – | no | yes | yes | link |
| paloma-text-pipeline | input `main&rev=57473ad4` | – | no | yes | no | link |
| poddantic | MACHINE | – | no | yes | yes | link |
| pyllij | MACHINE | – | no | yes | yes | link |
| repoman | input `path:./modules` | – | no | yes | yes | link |
| shellij | MACHINE | – | no | yes | yes | link |
| tyo3 | MACHINE | – | no | yes | yes | link |
| *30 further repos* | – | – | no | yes | no | link |

Totals measured in `~/.config/devman`: **52** `projects/*/devenv.local.nix`;
**48** import the machine link module; **12** import the machine repoman module.

### 1.4 Version skew

| tool | machine venv | git HEAD | machine pin (`nix-meta`) | worst fleet pin |
|---|---|---|---|---|
| repoman | 0.8.2 | **v0.9.0** | v0.8.2 (`nix-meta/flake.nix:54`) | v0.7.1 (agentman, `~/.config/devman`) |
| copyroom | 0.7.7 | v0.7.7+1 | – | – |
| gitman | 0.10.3 | v0.10.3 | – | – |
| docman | 0.2.1 | v0.2.1+3 | – | v0.2.0 (`repoman.lock`) |
| vendomat | 0.4.2 | v0.4.2 | – | v0.3.7 (`repoman.lock`) |
| pyjutsu | 0.22.0 | v0.22.0 | – | – |
| devman | pyproject says 0.6.0 | v0.7.0+4 | devman-link 0.6.0 | v0.4.0 (forgelab) |

Deliberate skew: repoman's own `devenv.yaml` commits the **fleet shape** (published
tags) and overrides to local checkouts in the untracked `devenv.local.yaml`. That
split is documented at `devenv.yaml:8-13` and is correct.

Not deliberate: six repos commit a `path:` or `git+file:///home/andrew/...` repoman
pin into a **tracked** `devenv.yaml` — forgelab, lodestar, nix-paseo, nix-desktop,
talkee, inferference. Three more pin a raw branch rev, `main&rev=57473ad4`.

---

## 2. The defects

Each entry names one path or one decision with two owners, and the failure it
causes.

### D1 — repoman's module has two delivery mechanisms

**Owners:** the repo's `devenv.yaml` pin, and the machine profile.

`flake.nix:60-63` states the machine path plainly:

> *"Project 039: the machine module. `repoman.installConsumerModule` (default true)
> installs the `repoman-module` package, so `nix-meta` pins repoman ONCE and every
> consumer imports the module from the stable machine path below **instead of
> pinning `repoman` in its own `devenv.yaml`**."*

`modules/devenv.nix:120-127` makes the import itself the enable signal:

> *"Now the module is only present when a consumer's central `devenv.local.nix`
> imports it — that import IS the enable signal."*

Against that, the concept §16:

> *"### No version relationship — Changing the central file changes all consumers
> immediately. ### Awkward CI — CI needs custom setup before evaluating the
> repository."*

**Failure 1 — the twelve migrated repos cannot evaluate off this machine.** Their
devenv configuration imports an absolute path under `/run/current-system`. A GitHub
runner, a fresh clone, or a second machine has no such path. There is no CI for any
of them, and the concept predicted precisely this.

**Failure 2 — the version relationship is fiction even where the pin exists.**
agentman pins the module at `v0.7.1`, `~/.config/devman/devenv.yaml` pins `v0.7.1`,
three repos pin a bare rev `57473ad4`, `nix-meta/flake.nix:54` pins `v0.8.2`, the
installed CLI is `0.8.2`, and repoman's git HEAD is `v0.9.0`. The module a repo
evaluates and the binary that module puts on PATH are pinned by different files that
no process reconciles.

**Failure 3 — six repos commit an unusable pin.** forgelab, lodestar, nix-paseo,
nix-desktop, talkee and inferference carry `path:` or `git+file:///home/andrew/...`
in a **tracked** `devenv.yaml`. This is worse than the symlink the concept objects
to, because it has the shape of a version pin and none of the properties.

### D2 — `devman.link` is declared by two files, and the trap is latent

**Owners:** devman's `modules/` (via the repo's own `devenv.yaml`) and the machine's
`link-module.nix` (via the central overlay).

This one took three measurements to get right, and the first two were wrong. The
final mechanism is **lazy evaluation**, not deduplication.

**Step 1 — the throw condition.** nixpkgs `lib/modules.nix:1016-1041`
`mergeOptionDecls`:

```nix
if bothHave "default" || bothHave "example" || bothHave "description" || bothHave "apply"
then throw "The option `${showOption loc}' in `${opt._file}' is already declared in ${showFiles res.declarations}."
```

Both declaration sites set `default = { }` **and** `description = "Filesystem links
reconciled at shell entry (§5)."`, so the condition is met in every version.

**Step 2 — deduplication does not save it.** Module dedupe keys on the file path.
Measured: two byte-identical files at different paths copied into the store by
content do collapse to one store path —

```
"${/tmp/nixkeytest/a/link.nix}" -> /nix/store/bd87mmd2…-link.nix
"${/tmp/nixkeytest/b/link.nix}" -> /nix/store/bd87mmd2…-link.nix
```

— but the store name derives from the **basename**, and identical content under a
different basename does not:

```
"${…/a/link.nix}"        -> /nix/store/bd87mmd2…-link.nix
"${…/a/link-module.nix}" -> /nix/store/i5gq916l…-link-module.nix
```

devman's file is `modules/link.nix`; the machine's is `link-module.nix`. Two keys,
always. A direct `lib.evalModules` run over the real v0.7.0 store path
(`/nix/store/9z68gh75…-source/modules/link.nix`, narHash-verified against agentman's
`devenv.lock`) plus the machine module reproduces the error verbatim:

```
error: The option `devman.link' in `/nix/store/9z68gh75…-source/modules/link.nix' is already declared in `/run/current-system/sw/share/devman/link-module.nix'.
```

**Step 3 — but the throw is lazy, and that is the whole story.**
`mergeOptionDecls` runs only when the option is **forced**. Nothing in
`link-module.nix` reads `config.devman.link`: its `enterShell` passes `--root`,
`--overlay` and `--project` to the `devman-link` CLI, which reads the central file at
**runtime**. The central overlay only *defines* a value. A definition is not a read.

So whether the shell builds depends entirely on whether some module reads the option:

| devman version | reads `config.devman.link`? | result |
|---|---|---|
| v0.5.1 | **yes** — `modules/devenv.nix:473` `effectiveLinks = bootstrapLink // cfg.link;`, also `:402`, `:477`, `:887` | forced → **throws** |
| v0.7.0 | **no** — grep for `cfg.link` / `effectiveLinks` / `linkViews` in `modules/devenv.nix` returns nothing | never forced → **builds** |

v0.7.0 removed the read deliberately. `modules/devenv.nix:163-165`: *"The link module
owns the bootstrap link and all link declarations. Workflow projection no longer
copies those declarations into a second plan."*

**This confirms the brief's framing** — v0.5.1 collides, v0.7.0 does not — and it
corrects my own working hypothesis mid-investigation, which was that agentman had to
be broken too. It is not. Corroborating filesystem evidence: agentman's
`.devenv/gc/shell` and `shell-589ad3d7….sh` carry mtimes ~39 s after commit `4114f18`,
and that generated script contains **two** `devman-link reconcile` lines — one from
`link.nix`'s `enterShell`, one from the plane module's own `linkScript`. A shell
script cannot be emitted past a hard eval error, so the build succeeded.

Exactly two repos hold both declaration sites:

| repo | devman pin | imports `devman/modules` | central overlay | forces the option? | state |
|---|---|---|---|---|---|
| copyroom | v0.5.1 | `devenv.yaml:37` | yes | yes | **shell broken** |
| agentman | v0.7.0 | `devenv.yaml:25` | yes | no | **latent** |

forgelab and lodestar import `devman/modules` but have no central overlay
(no `.devman/project.toml`, `.agents` is a real directory), so they hold one
declaration site and are unaffected.

**Failure 1, actual.** copyroom's devenv shell does not evaluate. Its test suite
cannot run, which is why lane `039-remove-agent-files` has never been verified.

**Failure 2, latent — and worse.** agentman is one line away from the same break,
and the line need not be in agentman. Any future devman module that reads
`config.devman.link` — a validator, a doctor check, a second projection — re-arms the
throw for every plane-adopted repo at once. The configuration is already invalid; it
is merely unevaluated. Fixing this by *not reading an option* is not a fix, it is a
constraint nobody has written down.

### D3 — the agent surface is composed unevenly, and each repo's `.gitignore` lies about it

**Revised 2026-09-18.** The original entry read this as an ownership dispute between
three writers and concluded `.agents/` should return to the repo. That conclusion is
withdrawn (§3.2, Q1). The observable failures below are real and unchanged; the cause
is different.

**The architecture is settled and correct:** the central overlay owns `.agents/`.
`~/.config/devman/projects/<p>/agents/skills/<name>` should be a relative symlink
into the shared pool at `~/.config/devman/skills/<name>`, per
`devman/.scratch/projects/025-the-link-plane/CONCEPT.md` §7.2-7.3 — *"one link per
repository, not one per skill."*

**The defect is that the composition was never applied consistently.** Measured:

| project | `projects/<p>/agents/skills/` holds |
|---|---|
| argentic | pool symlinks, e.g. `gitman -> ../../../../skills/gitman` — **correct** |
| gitman | `copyroom`, `gitman`, `my-ai` as **real directories** — copies that will drift |
| repoman | `repoman/` only — **no pool links at all** |
| agentman | seven entries |

The shared pool holds 16 skills. Nothing enforces which of them a project gets, and
`devman_link` performs no composition — `resolve()` is strictly 1:1 view↔canonical
(`paths.py:86-121`), and grep for `merge`/`compose`/`layer`/`pool` in
`src/devman_link/` returns nothing. The pool links are hand-made git-tracked
symlinks, exactly as the concept intends, which is why they drifted.

**Failure 1 — the generated router skill is empty.** Observable: invoking the
`repoman` skill renders a routing table with a header and no rows. `skills.py:75`
emits a row only for a manager whose skill file is present:

```python
present = [m for m in ordered if (skills_root / m.skill / "SKILL.md").is_file()]
```

`m.skill` defaults to `m.command` (`registry.py:51-52`), so the table needs
`copyroom`, `gitman`, `testee`, `docman`. repoman's project dir has none of them, so
`present == []`. The fix is eight `ln -s` into the pool, not an architecture change.

**Failure 2 — every repo's `.gitignore` states the opposite of the design.**
`.gitignore:226-231`:

> *"Agent-files convention (copyroom docs/user/agent-files.md): `.agents/` is
> dual-use. `.agents/skills/` IS tracked, as are AGENTS.md and CLAUDE.md"*
> followed by `.agents/**` / `!.agents/skills/` / `!.agents/skills/**`

`git ls-files .agents` returns **0**. `.agents` is a symlink, git cannot descend it,
and the un-ignore rules are unreachable. Under the settled architecture the correct
statement is that `.agents/` is wholly external and nothing under it is tracked.
`docs/AGENT-FILES.md:54-60` carries the same error in prose, describing copyroom as
owner of an in-repo canonical set.

**Failure 3 — copyroom is a redundant third writer.** `copyroom agent-files export`
(`agent/files.py:209-258`) writes into `<target>/<skills_dir>/`, which now resolves
through the symlink into the central repo. With the pool as the source, that producer
has no job. Lane `039-remove-agent-files` deletes it and is therefore **required** by
this architecture.

**Failure 4 — generated content is tracked in the central repo.**
`projects/<p>/agents/skills/<p>/SKILL.md` is git-tracked there and rewritten by every
`repoman-sync`, producing diff churn in a repo that currently carries five in-flight
lanes.

**The detection already exists and was ignored.** `repoman doctor`'s
`skill:tool-shipped` check (`devman/check.py:75-84`) flags a missing canonical set,
and would have reported repoman's gap. The gap is not detection; it is that nobody
acted on the warning, and nothing fails when a project's link set drifts.

### D4 — the default toolchain provider is not materialised

**Owners:** `repoman.lock` (venv) and vendomat's `flake.lock` (store).

`modules/devenv.nix:183-186` defaults `cliProvider` to `"store"`. On this machine
`REPOMAN_TOOLCHAIN_BIN` is **unset**, and the only `repoman-toolchain-core`
derivations in `/nix/store` are frozen at repoman 0.7.5 / gitman 0.6.1 / copyroom
0.7.4 — roughly two minor generations behind the venv that is actually populated
(repoman 0.8.2, gitman 0.10.3, copyroom 0.7.7, docman 0.2.1).

The repos know. `.repoman/project.toml` in image-gen-pipeline, llgym and nix-secrets
each carries a comment recording the measurement:

> *"cliProvider = "venv" is an opt-OUT of the store toolchain, and it is
> load-bearing. This repository declares no vendomat input, so nothing supplies
> REPOMAN_TOOLCHAIN_BIN. Under the default "store" the shell still enters and
> REPOMAN_MANAGERS still populates, but no manager command reaches PATH — the state
> measured here on 2026-09-16."*

**Failure:** a repo that adopts repoman and writes no manifest reports healthy while
every command it advertises is missing. `enterShell` warns
(`modules/devenv.nix:281-282`) and continues, by design — the degrade rule from
gitman project 32. The warning is correct; the default that triggers it is not.

Note the contrast, because it is the pattern to copy: in **store** mode
`repoman-sync.sh:94-99` refuses outright when a `repoman.lock` is also present,
rather than letting two locks disagree silently. That is two owners handled
correctly. D4 is the same situation handled by a default instead.

### D5 — the roster has two homes, and the fallback cannot be removed

**Owners:** `.repoman/project.toml` and the `repoman.managers` / `repoman.cliProvider`
options.

`modules/devenv.nix:173-182` documents the trap it is stuck in:

> *"It MUST have a manifest home. The ten repositories that decline the store
> toolchain carry the opt-out as `repoman.cliProvider = "venv"` in devenv.nix, and
> that option is the compatibility fallback slated for removal. Without a manifest
> field, removing the fallback would flip all ten onto a store closure they never
> imported."*

**Failure:** a migration that cannot finish. The fallback exists to protect repos
from a default that is wrong (D4). Fix D4 and the fallback becomes removable.

### D6 — devman has two adoption states and no rule saying which

**Owners:** devman's `modules/devenv.nix` (plane) and `modules/link.nix` (link-only).

devman's own docs already call the plane path legacy. `AGENTS_GUIDE.md:71` names
`modules/link.nix` the *"link-only interface"* and the repository-map table calls
`modules/devenv.nix` the *"compatibility workflow interface"*. `USER.md:84`:

> *"These options belong to the compatibility workflow module. The long-term
> link-only path is described below."*

The fleet has already voted: **48 of 52** projects are link-only. Four are
plane-adopted (agentman, copyroom, forgelab, lodestar), and two of those four are
broken by D2.

copyroom's lane `038-devman-consumer-copyroom` performs exactly this migration —
it deletes the `devman` input, the `devman/modules` import and the `devman = {...}`
block, and adds `.devman/project.toml`. Its change record states the result:

> *"refactor: remove Devman consumer integration … Gates pass: base:check and
> base:test pass with 603 tests. Both link canaries pass."*

**Failure:** the lane is **not merged**. `git merge-base --is-ancestor
038-devman-consumer-copyroom main` → false; `main:devenv.yaml:37` still reads
`- devman/modules`. The fix is written, tested, published as a branch, and not
landed, while the defect it fixes blocks a second lane in the same repo.

### D7 — agentman is treated as a `*man` family member that it is not

agentman's `AGENTS.md:10-11` says it *"wires the `*man` toolchain (copyroom, gitman,
testee, docman, repoman)"*, and it adopted the full plane. But it satisfies no part
of the manager contract (§1.2), and its own concept is explicitly hostile to
per-repo devenv integration:

> *"One system daemon, not one per repository"* (`.scratch/CONCEPT.md:68`)
> *"A daemon per devenv shell would mean N Postgres pools … daemons leaking when
> shells close"* (`:68-70`)
> *"No devenv-generated state"* (`:451`)

Its unit of work is also not the fleet's. agentman's workspace is
*"the resolved repository root: `git rev-parse --show-toplevel` … Two git worktrees
of one repository are two workspaces"* (`:49-52`). devman's and repoman's unit is a
**project name** from a manifest, which is stable across worktrees by design
(`devman/modules/link.nix` identity grammar).

**Failure:** agentman took on the plane import (and D2's collision) to gain nothing
it needs. Its transport is a fixed socket at `$XDG_RUNTIME_DIR/agentman.sock`
(`:84-85`) and its settings are global-only (`:142-147`), so a devenv shell needs
only the client binary on PATH.

---

## 3. The recommendation

### 3.1 Is the concept a new repo, or repoman grown up?

**It is repoman's module tree, renamed.** The concept's MVP (§21) asks for a repo
containing `devenv.nix` plus `modules/{tools,shell,vcs,python}/`, imported by a
consumer through `devenv.yaml`. repoman has `modules/devenv.nix` plus
`modules/managers/{copyroom,gitman,testee,docman}.nix`, imported by a consumer
through `devenv.yaml`, contributing packages, tasks, scripts and `enterShell`
behaviour. The mechanism is identical. The decomposition axis differs — repoman
splits by *manager*, the concept splits by *capability* — and the concept's
`dev.tools.vcs` / `dev.features.testing` naming (§17) is a rename of
`repoman.managers = [ "git" "test" ]`, not a new capability.

Do **not** create a `dev-env` repo. It would be a fifth thing that owns shell
configuration, in a fleet whose entire problem is that four already do.

The concept contributes two things repoman lacks, and both are worth taking:
- **§11 `mkDefault` discipline.** repoman's module writes `env.REPOMAN_SKILLS_DIR`
  and `enterShell` PATH entries unconditionally. Shared layers should default, not
  force, so a project keeps autonomy.
- **§19 outputs as a separate boundary.** *"Need one produced tool? → consume an
  output."* repoman already half-does this: `flake.nix:27-29` builds
  `repoman-module`. The correct use of that derivation is as a **package output a
  consumer may pin**, not as a machine path a consumer must find.

### 3.2 The direct contradiction, resolved

The concept's §16 and devman's link overlay cannot both be right about the same
content. They are right about **different** content. The rule that separates them:

> **A repository must evaluate and verify from a clone alone. Anything required to
> do that is a versioned input. Anything not required to do that may be a link.**

Apply it and the split is mechanical:

| content | required to evaluate/verify a clone? | mechanism |
|---|---|---|
| repoman meta-module, manager tasks | yes | versioned input |
| manager CLIs | yes | pinned toolchain (lock or closure) |
| `.agents/skills/` (router + fleet skills) | **no — decided 2026-09-18, see Q1** | link to the central overlay |
| `.envrc` | no — direnv is a local convenience | link |
| `devenv.local.nix` | no — by name and by devenv convention | link |
| `.loci` (notes) | no | link |
| `.claude/skills` (personal) | no | link |

devman keeps everything it is good at: machine-local, developer-local, untracked
state — **including `.agents/`**.

> **Decision, 2026-09-18 (user).** An earlier draft of this section recommended
> moving `.agents/` back into each repo as tracked content. That recommendation is
> **withdrawn**. The central overlay keeps `.agents/`, and the agent surface is
> composed inside `~/.config/devman` as devman's own design already specifies.
> Rationale and the cost accepted are recorded in Q1.

The clone-reproducibility rule still governs everything else in the table. Agent
skills are the one content type deliberately exempted: they are developer-facing
guidance, not an input to evaluating or verifying the repo.

### 3.3 The rules

**R1 — Configuration is a versioned input. One delivery, no alternates.**
A repo's `devenv.yaml` pins `repoman`. Delete the machine-path delivery
(`flake.nix:69-90`, `environment.pathsToLink`) and the twelve central-overlay
imports. *Removes a producer rather than adding an exclusion.*

**R2 — The machine profile ships binaries and machine facts, never a nix module a
repo's evaluation depends on.**
`devman-link` the command: yes. `link-module.nix`: it is imported only from
`devenv.local.nix`, which is itself untracked and local — so it stays, under R4.
`repoman/module/devenv.nix`: no.

**R3 — The agent surface is composed in the central overlay, one link per skill.**
`~/.config/devman/projects/<p>/agents/skills/<name>` is a relative symlink into the
shared pool `~/.config/devman/skills/<name>`. Project-specific skills and the
generated router are the only real entries. This is devman's own design —
`devman/.scratch/projects/025-the-link-plane/CONCEPT.md` §7.2-7.3: *"one link per
repository, not one per skill… adding a skill to a project is one `ln -s` in the
config repository."* Two writers remain, on disjoint paths: devman curates the pool
links, `repoman install-skills` generates `<p>/SKILL.md`. copyroom stays out.

**R4 — The central overlay owns every path git does not track.**
`.envrc`, `devenv.local.nix`, `.loci`, `.claude/skills` **and `.agents`**. Each
repo's `.gitignore` must say so plainly instead of claiming `.agents/skills/` is
tracked.

**R5 — Link-only is the only devman adoption state.**
Identity lives in `.devman/project.toml`. No repo imports `devman/modules`. This
makes D2 unreachable by construction. The alternative is the status quo, where
agentman stays valid only because no module happens to read `config.devman.link` —
an invariant no test asserts and no document states.

**R6 — A default names something that exists.**
`cliProvider` defaults to the provider that is materialised on the machine.

**R7 — Fleet-wide pins are converged, not hand-edited.**
copyroom owns the `repoman` input block in every consumer's `devenv.yaml`. Bumping
the fleet is one template change plus `copyroom update`, which is the workflow
copyroom exists for.

### 3.4 Owner per kind of content

| kind of content | owner | mechanism |
|---|---|---|
| manager tasks, options, shell wiring | **repoman** | `modules/`, pinned in `devenv.yaml` |
| the `repoman` pin itself | **copyroom** | template convergence (R7) |
| manager CLI binaries | **repoman toolchain** | one provider (R6) |
| testee | the repo | uv dev dependency in `pyproject.toml` |
| roster + provider choice | the repo | `.repoman/project.toml` |
| project identity | the repo | `.devman/project.toml` |
| fleet agent skills | **devman** | pool `~/.config/devman/skills/` + per-project `ln -s` |
| project-specific agent skills | **devman** | real content in `projects/<p>/agents/skills/` |
| the router skill | **repoman** | `install-skills` → the linked `.agents/skills/repoman/` |
| `.agents`, `.claude/skills`, `.envrc`, `devenv.local.nix`, `.loci` | **devman** | link |
| machine-local input overrides | the developer | `devenv.local.yaml`, untracked |
| agent runner | **agentman** | machine package; client on PATH |

### 3.5 Three layers, every mechanism placed

| concept layer | mechanism | note |
|---|---|---|
| 1 — platform | repoman `modules/` as a pinned input | the canonical devenv, already built |
| 1 — platform | vendomat toolchain closure / `repoman.lock` | the binaries behind the tasks |
| 1 — platform | copyroom template | writes layers 1-pin and 2-skeleton into each repo |
| 2 — project overlay | `devenv.nix`, `.repoman/project.toml`, `.devman/project.toml`, `pyproject.toml` | tracked, per-repo |
| 3 — local override | `devenv.local.yaml` | untracked input overrides; repoman already models this correctly |
| 3 — local override | devman central overlay + `~/.config/devman` | untracked paths only, after R4 |
| **removed** | machine repoman module | R1 |
| **removed** | devman plane registration | R5 |

### 3.6 agentman's place

**Stay a standalone CLI, delivered as a machine package.** Not a repoman manager,
not a devman group, not a platform devenv module.

Its concept already decided this: one system daemon, a fixed socket path, global-only
settings, *"No devenv-generated state"*. A devenv shell needs the client on PATH,
which `nix-meta` gives it for free — the same way `devman-link` arrives today. There
is nothing for a repoman manager module to wire, no per-repo doctor to aggregate, and
no per-repo service to start.

One caveat to settle before it matters: agentman's workspace is a worktree
(`git rev-parse --show-toplevel`), while devman's and repoman's project is a manifest
name stable across worktrees. Two worktrees of one repo are one project and two
workspaces. That is a defensible difference, but it should be **written down**, not
discovered later when run history splits.

### 3.7 What I am choosing against

Stated plainly, because each of these has an advocate in the current code.

1. ~~**Against the user's stated preference on one path.**~~ **Withdrawn
   2026-09-18.** I recommended `.agents/` return to each repo as tracked content.
   The user reaffirmed the central overlay, and further reading showed the
   composition they described is devman's own specified design
   (`025-the-link-plane/CONCEPT.md` §7.2-7.3) — partly built, unevenly applied. My
   objection rested on a cost that a correct implementation does not incur. See Q1.
2. **Against project 039's machine-module delivery.** It solved a real problem — 23
   pins nobody could bump — with a mechanism that costs CI and portability. R7 keeps
   the benefit and pays a smaller price.
3. **Against a new canonical `dev-env` repo.** §3.1.
4. **Against keeping two toolchain providers.** The seam is well built and carefully
   documented, and it is still two owners for one question.
5. ~~**Against landing copyroom lane `039-remove-agent-files`.**~~ **Withdrawn
   2026-09-18.** Under the settled architecture the central pool is the source of
   agent skills, so copyroom's export is redundant and 039 is required. See Q1, Q8.
6. **Against `repoman.managers` and `repoman.cliProvider` as devenv.nix options.**
   The manifest is the better home; the options should go once D4 unblocks D5.

---

## 4. The migration

Ordered smallest-reversible-first. Each step names the repo, the proof, and the risk.

> ⚠️ marks a step that touches machine-wide state or a repo with in-flight lanes.

### Phase A — unblock, change no architecture

**A1. Land copyroom lane `038-devman-consumer-copyroom`.** *(copyroom)*
The branch exists locally and on origin, and its record claims 603 tests green.
Landing it removes the `devman` input, the `devman/modules` import and the
`devman = {...}` block; `.devman/project.toml` already exists on the branch.
*Proves:* `devenv shell` evaluates in copyroom; `base:check` and `base:test` run.
*Reversible:* revert one merge.
⚠️ copyroom's working copy is detached with lane 039's deletions uncommitted.
Stash or shelve 039 first — do not land 038 on top of a dirty 039 tree.

**A2. Do the same for agentman.** *(agentman)*
Delete the `devman` input and the `devman/modules` import from `devenv.yaml:22-25`;
delete the `devman = {...}` block from `devenv.nix:20-24`. `.devman/project.toml`
already exists and is correct.
*Proves:* `devenv shell` still evaluates, and the generated shell script now has
**one** `devman-link reconcile` line instead of two — the signature that only one
link module is active.
Not urgent by symptom (agentman's shell builds today), urgent by exposure: D2's
latent throw is disarmed only by deleting one of the two declaration sites.

**A3. Fix the provider default.** *(repoman)*
Change `modules/devenv.nix:186` to default `cliProvider = "venv"` — the provider that
is actually populated — or materialise the store closure and pin it. Until one of
those is true, the default is wrong.
*Proves:* a repo with no `.repoman/project.toml` gets manager commands on PATH.
Test in one repo that currently carries the `cliProvider = "venv"` opt-out by
removing the line locally and checking `command -v gitman`.
⚠️ Changes behaviour for every repo without a manifest.

**A4. Compose repoman's agent surface from the pool.** *(`~/.config/devman`)*
Add eight relative symlinks under `projects/repoman/agents/skills/`, matching the
shape `projects/argentic/` already has: `copyroom`, `copyroom-adopt`,
`copyroom-template-edit`, `gitman`, `testee`, `docman`, `my-ai`, `writing`, each
`-> ../../../../skills/<name>`. Leave the generated `repoman/` entry real.
No repo change, no devman change, no migration.
*Proves:* the router skill's routing table renders four rows instead of zero —
directly observable by invoking the `repoman` skill. This is the single
highest-signal step in the plan.
⚠️ Edits `~/.config/devman`, which has five lanes in flight. Make it one commit on
its own lane in that repo.

### Phase B — one delivery for the module

**B1. Give repoman's flake a consumable output.** *(repoman)*
Keep `packages.repoman-module` (`flake.nix:27-29`). Stop installing it into the
system profile: remove `nixosModules.default`'s `environment.systemPackages` and
`pathsToLink` (`flake.nix:86-89`).
*Proves:* `nix build .#repoman-module` still works; `/run/current-system/sw/share/repoman` disappears on the next switch.
⚠️ Machine-wide. Must be sequenced **after** B2, or the twelve repos break at once.

**B2. Migrate the twelve back to a pinned input.** *(each repo + `~/.config/devman`)*
For each of argentic, eventic, flora, flora-qc, image-gen-pipeline, llgym, loci.nvim,
nix-secrets, poddantic, pyllij, shellij, tyo3: add the `repoman` input at the current
release to `devenv.yaml`, add `- repoman` to `imports:`, and delete the
`/run/current-system/sw/share/repoman/module/devenv.nix` line from the central
overlay. Keep `.repoman/project.toml` exactly as is — it is the right mechanism and
survives unchanged.
*Proves:* per repo, `devenv shell` enters and `repoman doctor` reports the same
findings as before the change.
⚠️ Touches `~/.config/devman` twelve times. Do it as one lane there.

**B3. Repair the six unusable pins.** *(forgelab, lodestar, nix-paseo, nix-desktop, talkee, inferference)*
Replace the committed `path:` / `git+file:///home/andrew/...` repoman pin with a
published tag. Move the local checkout override into an untracked
`devenv.local.yaml`, exactly as repoman's own `devenv.yaml:8-13` documents.
*Proves:* `git grep -n 'file:///home/andrew' -- devenv.yaml` is empty fleet-wide.

**B4. Give copyroom the pin.** *(copyroom + template)*
Add the `repoman` input block to the canonical template as converged content, using
copyroom's patch-type template edits. Bump one repo through `copyroom update` to
prove propagation.
*Proves:* changing the tag in the template and running `copyroom update` moves a
consumer's pin. This is R7, and it is what makes B2 sustainable rather than a
one-time chore.

### Phase C — collapse the remaining double owners

**C1. Normalize the agent surface fleet-wide** — repeat A4 for every project once it
has held in repoman, and convert the real-directory copies (e.g.
`projects/gitman/agents/skills/{copyroom,gitman,my-ai}`) into pool symlinks so each
fleet skill exists once. Add a conformance check so drift reports itself; extend
`repoman doctor`'s `skill:tool-shipped` (`devman/check.py:75-84`) to the full
expected link set. Correct each repo's `.gitignore` and `docs/AGENT-FILES.md`, and
gitignore generated routers in the central repo.

**C2. Retire `repoman.managers` / `repoman.cliProvider` as options**, now that D4 no
longer makes the fallback load-bearing (`modules/devenv.nix:173-182`).

**C3. Retire devman's plane module** — with forgelab and lodestar migrated,
`devman/modules/devenv.nix` has no consumers and can be deleted in devman.

**C4. Pick one toolchain provider** and delete the other seam. See §5 Q2.

---

## 5. Open questions

Each needs either a decision from the user or a command I was not allowed to run.

### Q1 — Who owns agent skills? — **ANSWERED 2026-09-18 (user decision)**

**Decision: devman's central overlay owns `.agents/`, and the agent surface is
composed inside `~/.config/devman`.** The repo keeps no tracked agent skills.

I recommended the opposite (`.agents/skills/` tracked in each repo, copyroom and
repoman writing into it). The user reaffirmed the central overlay, and that is the
decision of record. Two things make it the better answer than my recommendation, and
I had missed both:

1. **It is devman's specified design, not an improvisation.**
   `devman/.scratch/projects/025-the-link-plane/CONCEPT.md` §7.2-7.3 states it:
   *"one link per repository, not one per skill… adding a skill to a project is one
   `ln -s` in the config repository."* `projects/argentic/agents/skills/gitman ->
   ../../../../skills/gitman` is that design, working, on disk today.
2. **My objection priced a broken implementation, not the design.** I argued the
   empty router table proved the model wrong. It proves only that
   `projects/repoman/agents/skills/` was never populated — eight symlinks fix it,
   with no architecture change. A correct implementation does not incur the cost I
   named.

**The cost genuinely accepted**, recorded so it is not rediscovered: a fresh clone
and a CI runner have no agent skills. The escape hatch if it ever matters is real —
`~/.config/devman` is a git repo, so CI can clone it and run `devman-link reconcile`,
given the reconciler is available there. Unbuilt, not impossible.

**Consequences** now folded into D3 and §3.3-3.4: copyroom's `agent-files` surface is
redundant, so lane `039-remove-agent-files` is required rather than rejected (Q8);
each repo's `.gitignore` and `docs/AGENT-FILES.md` must stop claiming
`.agents/skills/` is tracked; generated routers should be gitignored in the central
repo; and the per-project link set needs a conformance check so drift reports itself.

### Q2 — Which toolchain provider survives?

`venv` is populated and current. `store` is the default, unmaterialised, and stale.
The store design is better on the merits — one hermetic closure, no editable installs,
`repoman-sync.sh:94-99` already refuses the ambiguous case. But it has not been kept
alive, and `repoman.lock`'s own header records why the venv persists: local editable
checkouts are how the user develops the managers.

- **Option A — venv wins.** Delete `cliProvider`, the store branch, and vendomat's
  toolchain module. Simplest; loses hermeticity.
- **Option B — store wins.** Rebuild the closure at current versions, export
  `REPOMAN_TOOLCHAIN_BIN` machine-wide, delete the venv and `repoman.lock`. Keep a
  `path:` escape for manager development.
- **Option C — keep both.** Status quo; D4 and D5 persist.

**Recommendation: B, but not yet.** Make the default honest first (A3), then rebuild
the closure, then flip. Doing it in the other order is what produced D4.
I could not measure how much work B is without running `nix build`.

### Q3 — Can copyroom actually converge a partial `devenv.yaml`?

R7 depends on it. Evidence it can: `modules/managers/copyroom.nix:8` provisions
`gnupatch` specifically *"for patch-type template edits"*, so partial-file
convergence is a real copyroom capability. Evidence it may not be enough: each
consumer's `devenv.yaml` also carries repo-specific inputs (repoman's own has
`docman` and `shellij`), so a whole-file template would clobber them.

**Unverified.** Settling it needs a `copyroom update` run against a scratch repo,
which this investigation was not permitted to do. If partial convergence does not
work, the fallback is a small generated file — but devenv `inputs:` cannot be split
across files, which is exactly why 039 chose the machine path. **This is the load-
bearing uncertainty in the whole recommendation**, and it should be tested before
Phase B starts, not during it.

### Q4 — Is agentman's workspace identity a problem?

agentman keys on a worktree; devman and repoman key on a manifest project name. Two
worktrees of one repo are one project and two workspaces. I think that is correct
for agentman — run history really is per-worktree — but nothing writes it down.
**Recommendation:** state it in agentman's concept. No code change.

### Q5 — What is `037-central-settings-gate-2` trying to do?

I could not determine the intent. The five lanes in `~/.config/devman` are real
committed branches, and the working copy is an unbookmarked jj change on top of the
gate-2 lane diffing 231 files against it. `037-part-a-lodestar` alone is
+1421/−81232. The repo is jj-colocated and auto-snapshotting, so the numbers move.

**Every migration step that touches `~/.config/devman` (A4, B2) is blocked on this.**
The user should say which of the five lands first, or explicitly park them. I
recommend landing or abandoning all five before Phase B, because B2 edits twelve
files in that repo.

### Q6 — Is the `nix-meta` pin lag deliberate?

repoman HEAD is `v0.9.0`; `nix-meta/flake.nix:54` pins `v0.8.2`; the venv reports
`0.8.2` from an editable install of the `v0.9.0` working tree. The comment at
`nix-meta/flake.nix:50-51` explains why v0.8.2 was chosen (it added
`.repoman/project.toml`'s `cliProvider` field) but not why it has not moved since.
Note the machine module tree and the checkout `modules/` are currently
**byte-identical** (`diff -rq`, exit 0), so nothing is broken by the lag today.
**Recommendation:** confirm it is just an unbumped pin, then let R1 make it moot.

### Q7 — Where does shellij belong?

shellij is installed by default through a presence-gated import
(`modules/devenv.nix:117`) and is explicitly *not* a roster manager
(`CONCEPT.md:§4`). Under the concept's layers it is Layer 1 platform content — a
shared tool every shell gets. It works today and I propose no change. Flagging it
only because the presence-gated-import pattern is the same one R1 removes for
repoman, and the two should not drift apart without a reason.

### Q8 — What happens to copyroom lane `039-remove-agent-files`?

**Answered by Q1: it lands.** With the central pool as the source of agent skills,
copyroom's `agent-files` surface is redundant, so 039 is required by the
architecture rather than something to argue against. It has never run green because
copyroom's shell is broken by D2, so **A1 must land first** — then run 039's suite
to confirm it is sound before landing it.

---

## 6. Confidence

**Measured:** the fleet inventory, the version skew, the `mergeOptionDecls` throw
condition, the content-addressed store-path experiment (identical content dedupes,
differing basenames do not), the `lib.evalModules` reproduction against the real
narHash-verified v0.7.0 store path, the presence/absence of `cfg.link` reads in
devman v0.5.1 vs v0.7.0, agentman's post-commit `.devenv` mtimes and its two-line
generated shell script, the empty router table, `git ls-files .agents` = 0,
`REPOMAN_TOOLCHAIN_BIN` unset, the store closures' stale versions, lane 038 not
merged into copyroom's main, the byte-identity of the machine repoman module and the
checkout.

**Reversed by decision (2026-09-18):** §3.2's content split, R3, R4, the §3.4 owner
table, §3.7(1) and (5), D3, A4, C1, Q1 and Q8 all originally recommended returning
`.agents/` to each repo as tracked content. The user reaffirmed the central overlay,
and subsequent reading of `devman/.scratch/projects/025-the-link-plane/CONCEPT.md`
§7.2-7.3 showed that model is devman's specified design. Those sections now record
the decision; the failures D3 lists are unchanged, but their cause is uneven
composition rather than the architecture.

**Corrected mid-investigation:** I predicted from the throw condition alone that
agentman's shell must also be broken. Filesystem evidence contradicted it, and the
lazy-evaluation mechanism (D2 step 3) explains why the brief's original framing was
right. The corrected finding is stronger than either: the defect is present in
agentman and merely unevaluated.

**Read but not executed:** copyroom lane 039's diff, the central repo's five lanes,
agentman's concept.

**Inferred, flagged in place:** that devman's plane module is being deprecated
(direction is clear in `USER.md:84` and `AGENTS_GUIDE.md:71`; no removal notice
exists); that copyroom can converge a partial `devenv.yaml` (Q3); that the six
committed local-path pins are accidents rather than deliberate machine-local choices.
