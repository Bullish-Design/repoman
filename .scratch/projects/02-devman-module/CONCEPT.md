# devman — Concept (brainstorm)

## One-line

A **devenv-literacy layer for coding agents**, shipped as a subsystem **inside the repoman
repo**: a curated bundle of agent **skills**, a distilled **documentation export**, and
**articles/recipes** — installed alongside RepoMan's entrypoint skill — whose single job is to
make Claude Code agents use `devenv.sh`-managed repos *correctly*.

## Why it exists

The `*man` family are **doers**: copyroom scaffolds, gitman versions, testee verifies, docman
builds docs. Each runs *inside* `devenv shell` and assumes the agent already knows how to
operate a devenv repo. That assumption is false. The same agent mistakes recur everywhere:

- **Bare commands.** Running `pytest`/`python`/`uv`/`ruff` directly instead of
  `devenv shell -- …`, so none of the pinned PATH / env / determinism vars apply. (This user's
  global `CLAUDE.md` exists *only* to fight this — devman makes that rule an installed, versioned
  asset instead of a paragraph re-typed per machine.)
- **Lock / eval-cache confusion.** Editing a `modules/` file or `env.*` and seeing no change,
  because the consumer's `devenv.lock` pins the module input and the eval cache is stale. The
  fix (`rm -f devenv.lock && rm -rf .devenv`, or `--refresh-eval-cache`, or `devenv update`) is
  folklore passed between READMEs instead of one canonical skill. (We hit this very loop while
  hardening the conductor — see `01-conductor-hardening`.)
- **Input gotchas.** A devenv-module input needs `flake: false`; pinning
  `languages.python.version` needs the `nixpkgs-python` input; remote module imports merge
  `devenv.nix` but **not** `devenv.yaml`, so consumers must declare transitive inputs.
- **Venv reality.** `languages.python.venv.enable` creates a venv but the project deps aren't
  there until `uv sync` / the sync script runs; `import`s then fail mysteriously.
- **Surface confusion.** `scripts` vs `tasks` vs `processes`; `enterShell` greetings that
  pollute captured output unless guarded by `if [ -t 1 ]`; the `0/1/2/3` exit contract.
- **Background/long-running work.** `devenv up` for processes; not blocking the shell on a
  server; polling logs rather than piping output somewhere invisible.

These aren't bugs in any one tool — they're a **missing literacy layer**. devman is that layer,
and because it's always needed wherever RepoMan is, it lives in this repo.

## What devman is (and is not)

- **Is:** a knowledge product — skills + a docs export + articles — versioned with repoman,
  installed by `repoman-sync`, and lint-checked by `repoman doctor`.
- **Is not:** a CLI that runs build/test/git actions, and **not a separate repo or input**. It
  teaches; it doesn't do. There is no `devman` command — its install/verify needs fold into the
  existing `repoman` CLI.

This is the **allium-env shape** (value = installing agent assets correctly), generalized to
"the devenv fundamentals every agent in every repo needs," and absorbed into RepoMan.

## Form: a subsystem of repoman

```
repoman/
  modules/
    devenv.nix            # meta-module (unchanged role); installs devman assets via sync
    devman/
      assets/
        skills/           # the devenv-literacy SKILL.md files (Layer 1)
        docs/             # the distilled documentation export (Layer 2)
        articles/         # explainers + recipes (Layer 3)
  src/repoman/
    skills.py             # extend: also install devman's skills (not just the entrypoint)
    checks.py             # extend: self-check that devman skills/docs are installed + current
```

- **Installation:** `repoman-sync` already runs `repoman install-skills` (generates the
  entrypoint). Add a step that also copies devman's `assets/skills` + `assets/docs` into the
  consumer (`skillsDir` / a `docsDir`), recording a manifest for drift detection (the allium-env
  `.allium-devenv-source` pattern).
- **Verification:** `repoman doctor`'s self-check (`checks.py`) already lints installed skills.
  Extend it with `devman:skills` / `devman:docs` checks — installed? at the current repoman
  version? — under the same `ok/warn/fail` → `0/0/2` mapping it already uses.
- **No new options surface required** beyond maybe `repoman.devman.enable` (default on) and a
  `docsDir`. Consumers who import repoman get the literacy layer for free.

## Where it sits relative to RepoMan and the family

- **RepoMan entrypoint skill** owns the **lifecycle** narrative (verify before save, scaffold
  before change) — *which tool, in what order*.
- **devman skills** own the **devenv-mechanics** narrative beneath it — *how to operate the
  devenv shell those tools live in*.
- They co-install and cross-link with the same discipline RepoMan already uses for manager
  skills (`docs/SKILLS.md`): devman skills trigger on *mechanics* keywords ("command not found",
  "rebuild", "lock", "import fails"); the entrypoint triggers on *lifecycle* keywords; each
  devman skill defers cross-cutting ordering up to the `repoman` skill.

## Folding the would-be `devman` CLI into `repoman`

No separate binary. The verbs map onto the existing conductor:

- **install** → `repoman-sync` / `repoman install-skills` also lays down devman assets.
- **doctor** → `repoman doctor` self-check gains `devman:*` checks (assets present + current +
  the devenv rule reachable). Reuses `checks.py`, `self_check_exit`, `format_self_check`.
- **enforcement (stretch)** → an opt-in pre-tool-use hook that flags bare
  `pytest`/`uv`/`python` and nudges to `devenv shell -- …`. Distinct from guidance; ship later.

## Key tensions / decisions to make

| Decision | Options | Lean |
|---|---|---|
| Home | (a) separate repo, (b) **subsystem of repoman** | (b) — decided: always used together |
| Docs export | (a) mirror devenv.sh, (b) curated distilled subset, (c) link-only | (b) — agent-optimized, regenerable |
| Install path | (a) new sync, (b) **fold into `repoman-sync`** | (b) |
| Verify path | (a) new `devman doctor`, (b) **extend `repoman doctor` self-check** | (b) |
| Enforcement | (a) guidance only (skills), (b) + a hook that blocks bare commands | start (a); (b) opt-in later |
| Editor scope | Claude Code only, or Codex/others too | skills Claude-first; docs/articles tool-agnostic |

## Open questions

- **Asset layout & options** — `modules/devman/assets/` vs co-locating under existing skill
  templates; what `repoman.devman.*` options (if any) are worth exposing.
- **Skill granularity & triggers** — how many skills, on what triggers, without colliding with
  the entrypoint or manager skills (reuse the `docs/SKILLS.md` trigger discipline).
- **Docs-export source** — vendor + distill official devenv.sh docs, or write from observed
  failure modes? (Lean: skeleton from official + a hand-curated "agent gotchas" overlay,
  generated so it tracks devenv releases.)
- **Self-check strictness** — should missing devman skills be `warn` or `fail` in
  `repoman doctor`? (Probably `warn` until devman is mandatory, then `fail`.)
- **Hook surface** — is a bare-command-catching pre-tool-use hook in scope here, or its own
  follow-up project? (High value, higher risk — likely separate.)
- **Name** — keep `devman` for family consistency even though it's *knowledge*, not a *doer*.
  (Lean: keep `devman` as the subsystem name.)
