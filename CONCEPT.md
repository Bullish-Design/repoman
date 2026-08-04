# RepoMan — Concept

> **One devenv import that turns any repo into a fully-managed agentic repo.**
> Add RepoMan to `devenv.yaml`, set `repoman.enable = true`, pick your managers —
> and copyroom, gitman, testee, docman, … are installed, wired, and
> skilled, with a single `repoman doctor` over all of them.

RepoMan is the **conductor** for the `*man` family: a per-repo lifecycle front door
that *composes* the individual managers rather than replacing them.

---

## 1. The family it belongs to

RepoMan does not invent a new architecture — it composes an existing one. Every
`*man` tool is the same pattern applied to a different domain:

| Manager | Domain it owns | Wraps |
|---|---|---|
| **copyroom** | templating / scaffolding / project lifecycle / convergence | Copier |
| **gitman** | version control | jujutsu + colocated git |
| **testee** | verification (test / lint / typecheck / format) | pytest, ruff, ty |
| **docman** | docs | _(skeleton)_ |
| **shellij** | durable remote workbenches — **installed by default, not a roster manager** | Zellij, Yazi |

shellij is the one non-roster member of the family: RepoMan wires it in by default —
new repos get it without selecting anything, and it is auto-configured for use (see §4).

They share a contract:

- **Single interface** — the agent stops running raw tools ad hoc and asks one command.
- **Pydantic-normalized output** → a compact, structured, actionable report.
- **Typer CLI** with `init` (scaffolds a nix import + an agent skill) and `doctor`.
- **Runs inside `devenv shell`** as its execution boundary.
- **A `0/1/2/3` exit-code contract**: ok / domain-decision-needed / infra-config / invalid-usage.
- **Distributed as a devenv module**, imported via `devenv.yaml`.

The gap: eight instances of one pattern, **no conductor**. RepoMan is the conductor.

---

## 2. What RepoMan is (decisions)

These were settled during brainstorming:

- **Scope: per-repo conductor.** RepoMan lives inside one repo and orchestrates the
  `*man` tools for the agent. Fleet/workspace management is explicitly out of scope
  for v1 (shellij's project registry already covers per-project session discovery if needed later).
- **Primary form: a devenv meta-module.** RepoMan is *mainly* the single one-liner
  `devenv.yaml` import that pulls in and wires up the component managers. The Python
  side is a thin conductor.
- **Agent surface: pass-through + aggregate.** Each manager keeps its own report and
  its own skill. RepoMan sequences them and aggregates `status` / `doctor`; it does
  **not** re-model their reports.
- **copyroom is the core pillar.** It is the *convergence engine*: it births repos
  with the right managers pre-wired, adopts existing repos, and propagates toolchain
  updates across repos. The other managers are organs; copyroom is the genome.

---

## 3. The consumer experience (the whole point)

What a repo adds — the "one-liner":

```yaml
# devenv.yaml
inputs:
  repoman:
    url: github:Bullish-Design/repoman?ref=v0.1.0   # flake:false; points at the module dir
    flake: false
imports:
  - repoman
```

```nix
# devenv.nix
{
  repoman.enable = true;
  repoman.managers = [ "copy" "git" "test" "doc" ];   # pick your toolchain
}
```

`devenv shell` — and now the repo has the selected managers on PATH, each one's nix
wiring (tasks/scripts) active, each one's agent skill installed under `.claude/skills/`,
and a top-level `repoman` command. **No eight separate `init` dances.**

---

## 4. Module options

```nix
repoman.enable        = true;
repoman.managers      = [ "copy" "git" "test" ];          # which managers to wire in
repoman.template      = "gh:Bullish-Design/template-py";  # copyroom's canonical genome
repoman.installSkills = true;                             # aggregated skill + each sub-skill
repoman.skillsDir     = ".claude/skills";

# escape hatch: pass options straight through to a component module
repoman.test.mode     = "ci";
repoman.git.trunk     = "main";
```

Manager roster, in default tiers:

- **Core (default on):** `copy` (copyroom), `git` (gitman), `test` (testee).
- **Publish:** `doc` (docman).

**shellij is not in the roster.** There is no `repoman.session.*` config, no
`repoman.managers` entry, nothing to select or tune. It is **installed by default**:
new-repo templates (copyroom's canonical template) declare the `shellij` input in
`devenv.yaml`, and RepoMan presence-imports shellij's own devenv module — which
installs `shellij` + `zellij` + `yazi` and appends a guarded `shellij open`
enterShell hook — so the durable workbench is wired and auto-configured for use
with zero repoman configuration. A repo that doesn't declare the input simply
doesn't get shellij.

---

## 5. The thin `repoman` CLI (pass-through + aggregate)

It re-implements nothing. It sequences and aggregates:

```
repoman managers   # list enabled managers, command, tier, one-line summary
repoman doctor     # run every enabled manager's doctor; exit = worst sub-exit (0/1/2/3)
repoman status     # gitman status + testee last-run + copyroom drift, side by side
# optional lifecycle pass-throughs (sequence, gate on exit codes):
repoman verify     # → testee
repoman save -m    # → testee verify, then gitman save (gated on green)
repoman release    # → testee ci → gitman release → docman
```

Pass-through means each tool keeps its own report and skill; `repoman` runs them,
prints each result, and returns the worst exit code under the shared `0/1/2/3` contract.

---

## 6. How composition actually works

> **Superseded by project 12 (toolchain single instance).** §6.2 below described a
> per-repo toolchain: `repoman-sync` installing the manager CLIs into *each consumer's*
> devenv venv from a per-repo `repoman.lock` — the mechanism project 11 measured pruning
> 33 packages when `uv sync` ran. Project 12 splits the family by install model: the
> pure-CLI managers (repoman/gitman/copyroom/docman + pyjutsu) live ONCE system-wide in
> `$REPOMAN_TOOLCHAIN_VENV`, installed by `repoman-sync --machine` from a machine
> `repoman.lock` at the repoman checkout; testee is a per-repo uv dev dependency in each
> consumer's `pyproject.toml`. Consumers have no `repoman.lock` and `uv sync` prunes
> nothing. The nix wiring described here is unchanged.
>
> **Lock shape (WS-3, project-12 follow-up):** the committed `repoman.lock` at the
> checkout is the **dev** shape — `path:` sources installed `--editable` for this
> machine. The **fleet** shape swaps each `path:` for
> `git+https://github.com/Bullish-Design/<repo>@vX.Y.Z` (the resolver passes git
> sources verbatim; proven by `test_git_https_source_passes_through_verbatim`). One
> lock does NOT serve both — machine locks are per-machine by design. A CI runner
> can point `repoman-sync --machine` at a fleet-shaped lock with the `REPOMAN_LOCK`
> env override (WS-3 flag) without editing the checkout.

Two layers, mirroring the proven family patterns:

1. **Nix layer (the meta-module).** `modules/devenv.nix` declares `options.repoman.*`
   and statically imports one thin wiring module per manager from `modules/managers/`.
   Each manager module gates its own `config` on membership in `repoman.managers`
   (imports can't depend on `config`, so we import all and gate each — the standard
   module-system idiom). Each manager module contributes that manager's `tasks` /
   `scripts` and registers its skill for installation.

2. **Python/CLI layer (getting the tools into the repo).** The manager CLIs
   (copyroom, gitman, testee, …) are Python packages that must land in the devenv
   venv. The proven family mechanism is a `*-sync` script that installs
   assets into the repo, optionally on `enterShell`. RepoMan generalizes this:
   `repoman-sync` installs the selected managers' Python packages into the venv and
   installs their skills under `skillsDir`.

> **Managers may contribute nix-level provisioning, not just venv installs.** Most
> managers are pure pip installs, but some carry native/system toolchain requirements
> that a venv install alone can't satisfy. A manager module may therefore contribute
> system `packages` and language toolchains (`languages.*`) to the consumer devenv —
> conditionally on being selected — in addition to its tasks/scripts/skills. Proven by
> gitman (project 01, guide 1): its `pyjutsu` dependency is a Rust/maturin native
> extension, so `modules/managers/gitman.nix` adds `pkgs.maturin` +
> `languages.rust.enable`, gated on `"git" ∈ managers` (repos without gitman never pull
> Rust). Native deps that `uv pip install` can't resolve from `[tool.uv.sources]` get an
> explicit `repoman.lock` pseudo-entry (`[managers.<m>-<dep>]`) that `repoman-sync`
> installs alongside the manager. See `SPIKE.md`.

> **De-risking note.** The original open question was "does devenv support transitive
> *nix inputs* from an imported remote module." The spike shows that for Python-based
> managers this is mostly **not needed**: the nix module only wires tasks/scripts/skills,
> and the tools themselves arrive through the venv (pip/uv) via `repoman-sync`. The
> resolution is settled: `repoman-sync` reads a single **`repoman.lock`** manifest
> (TOML) pinning RepoMan + every manager, so the toolchain moves in lockstep. Proven
> end to end — see `SPIKE.md`.

---

## 7. Repo layout for RepoMan itself

```
repoman/
  devenv.yaml          # RepoMan's own dev shell inputs
  devenv.nix           # RepoMan's own dev shell (working ON repoman)
  modules/
    devenv.nix         # ← THE meta-module consumers import (options.repoman.* + wiring)
    managers/
      testee.nix       # per-manager wiring, gated on membership in repoman.managers
      ...              # gitman.nix, copyroom.nix, … (added incrementally)
  src/repoman/
    cli.py             # thin Typer CLI: managers, doctor, status, lifecycle
    aggregate.py       # run sub-commands, merge exit codes (0/1/2/3 contract)
    registry.py        # the manager roster + tiers + command mapping
  tests/
    consumer-example/  # throwaway repo that imports the meta-module (the spike)
  CONCEPT.md
  SPIKE.md
```

The center of gravity is **Nix** (`modules/devenv.nix` + `managers/`); the Python is
a slim conductor.

---

## 8. Open questions / next steps

- ~~**`repoman-sync` resolution**~~ — **decided:** single `repoman.lock` manifest
  (TOML), proven end to end. See `SPIKE.md`.
- **`repoman new`** — fleet-less repo *birth* via copyroom: does it belong in v1, or
  is adoption (`repoman adopt`) of existing repos the more valuable first move?
- ~~**Skill merge narrative**~~ — **built:** generated entrypoint/router skill from the
  roster (`repoman install-skills`, run by `repoman-sync`). Design + verification in
  `docs/SKILLS.md`. Remaining: conflict-precedence table, installing sub-skills, and
  `doctor`-as-skill-linter.
- ~~**gitman & native toolchains**~~ — **done** (project 01, guide 1). gitman needs
  Rust/maturin + the unpublished pyjutsu; `modules/managers/gitman.nix` contributes the
  toolchain (gated on `"git"`) and a `git-pyjutsu` lock pseudo-entry carries the native
  dep. Proves the meta-module can do nix-level (not just venv) provisioning — see §6 and
  `SPIKE.md`. Remaining gitman follow-up: a fleet path (published pyjutsu wheel + `git+…`
  sources) so `path:` checkouts aren't required.
