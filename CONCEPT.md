# RepoMan — Concept

> **One devenv import that turns any repo into a fully-managed agentic repo.**
> Add RepoMan to `devenv.yaml`, set `repoman.enable = true`, pick your managers —
> and copyroom, gitman, testee, docman, siteman, … are installed, wired, and
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
| **siteman** | site / publishing | _(skeleton)_ |
| **zelligate** | live terminal / session surface | Zellij web + daemon |
| **mypi-agent** | coding-agent runtime + secrets | Pi, secretspec |
| **allium-env** | spec-driven agent workflow | Allium prompts / skills |

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
  for v1 (zelligate already covers cross-repo discovery if needed later).
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
- **Publish:** `doc` (docman), `site` (siteman).
- **Situational:** `session` (zelligate), `agent` (mypi-agent), `spec` (allium).

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
repoman release    # → testee ci → gitman release → docman/siteman
```

Pass-through means each tool keeps its own report and skill; `repoman` runs them,
prints each result, and returns the worst exit code under the shared `0/1/2/3` contract.

---

## 6. How composition actually works

Two layers, mirroring the proven allium-env / zelligate / testee patterns:

1. **Nix layer (the meta-module).** `modules/devenv.nix` declares `options.repoman.*`
   and statically imports one thin wiring module per manager from `modules/managers/`.
   Each manager module gates its own `config` on membership in `repoman.managers`
   (imports can't depend on `config`, so we import all and gate each — the standard
   module-system idiom). Each manager module contributes that manager's `tasks` /
   `scripts` and registers its skill for installation.

2. **Python/CLI layer (getting the tools into the repo).** The manager CLIs
   (copyroom, gitman, testee, …) are Python packages that must land in the devenv
   venv. The proven family mechanism (allium-env) is a `*-sync` script that installs
   assets into the repo, optionally on `enterShell`. RepoMan generalizes this:
   `repoman-sync` installs the selected managers' Python packages into the venv and
   installs their skills under `skillsDir`.

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
- **gitman & native toolchains** — gitman needs Rust/maturin + the unpublished pyjutsu;
  the meta-module must contribute system `packages`, not just venv installs. First
  manager that forces nix-level (not just venv) provisioning.
