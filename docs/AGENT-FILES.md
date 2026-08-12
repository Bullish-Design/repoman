# Decision — the agent-files convention (`.agents/skills` + `AGENTS.md` + `CLAUDE.md`)

- **Status:** Accepted — the one convention every `*man` repo (and every repo
  generated from the genome) follows.
- **Date:** 2026-08-03
- **Deciders:** the `*man` family (copyroom, gitman, testee, docman, shellij,
  repoman)
- **Reference implementation:** copyroom — see copyroom's
  `docs/user/agent-files.md` and the project-07 scratch notes.

This record exists so the convention is a **shared decision**, not a drift of
per-repo habits.

## The convention (fixed)

| File | Role | Owner |
|------|------|-------|
| `.agents/skills/<name>/SKILL.md` | Skills — imperative, short, domain-bounded; they link to docs, never repeat them | see ownership split |
| `AGENTS.md` | The **canonical** repo instructions file — one source of truth | the repo (may be seeded by the genome/copyroom) |
| `CLAUDE.md` | A **symlink to `AGENTS.md`** — every tool reads the same file | the repo (seeded by the genome/copyroom) |

Every repo in the family self-adopts: a root `AGENTS.md`, a `CLAUDE.md` symlink
(git mode `120000`), and its own skills under `.agents/skills/`. The default
skill directory is `.agents/skills` everywhere (repoman's `skillsDir` default;
copyroom's `agent.skills_dir`; each manager's own self-adoption).

## Ownership split

- **Tool-shipped** — version-locked skills ship with their tool. CopyRoom's
  canonical set (`copyroom`, `copyroom-adopt`, `copyroom-template-edit`) lives in
  copyroom's package assets and is materialized by `copyroom agent-files export`
  (one source of truth; copyroom's `doctor` checks currency). Tool skills are
  installed by the tool's own sync (repoman-sync today).
- **Genome / fleet** — skills and docs that belong to the family rather than one
  tool (the devenv-literacy layer: `devenv-*` skills, the `.agents/devenv/` docs
  export) live in the **genome** (template-py, under `template/.agents/`) and are
  converged by `copyroom update`.
- **Personal** — skills that belong to the *user* rather than to any tool,
  genome, or single repo: true in every repo they work in, versioned on their own
  schedule. These ship as their own **Copier overlay layer** (`my-ai`, recorded
  in `.copier-answers.my-ai.yml`) and are converged by
  `copyroom update --layer my-ai`. They cannot live in a tool's package (wrong
  owner, wrong release cadence) nor in one genome (that only reaches repos
  generated from it). See copyroom's `docs/user/layers.md`.
- **Repoman's router** — the generated entrypoint skill stays *generated* at
  sync time (it depends on the runtime manager roster). Repoman owns exactly one
  skill. Because it is generated **per repo** from that repo's roster, it must
  never be redistributed as a static copy — a snapshot is wrong wherever it lands.
- **Overlay** — a repo's own additions/modifications under `.agents/skills/`.
  Permanent divergence is declared in `copyroom.project.yml` `agent.overlay`,
  which `copyroom update` maps to Copier `--exclude` so the template stops
  managing that skill.

## The two-writer rule

CopyRoom owns the *canonical set* (package assets + the `agent-files` command)
and must never fight another writer over the same files: the skills it ships are
the ones under its `assets/`; everything else under `.agents/skills/` belongs to
the genome or the repo. `copyroom agent-files check` reports extra skills as
present without judging them.

## Template requirements (what a template must declare)

Verified empirically with Copier 9.17 (see copyroom's SPIKE notes): without
`_preserve_symlinks: true`, Copier dereferences the `CLAUDE.md` symlink into a
regular file on both `new` and `update`. And skills contain literal `{{ }}`
examples, so templates must declare:

```yaml
_preserve_symlinks: true
_copy_without_render:
  - ".agents/skills/**"
  - ".agents/devenv/**"   # only if the template ships docs there (the genome does)
```

`_preserve_symlinks: true` is **required** — without it, `CLAUDE.md` lands as a
regular file on both `new` and `update`. `_copy_without_render` is required for
every tracked `.agents/` subtree: skills (and the genome's `.agents/devenv/`
docs) contain literal `{{ }}` examples that must survive byte-for-byte.

An **overlay layer** template (the personal layer) declares two more:

```yaml
_answers_file: .copier-answers.my-ai.yml   # the layer's identity — keeps its link
                                            # out of the genome's answers file
_skip_if_exists:
  - "AGENTS.md"                             # seed only; AGENTS.md belongs to the repo
```

`_answers_file` is what makes layering possible at all: Copier scopes both `copy`
and `update` to a single answers file, so each layer is an independent merge
lineage. `_skip_if_exists` is what lets one overlay serve dozens of repos that
each own their `AGENTS.md` — it holds on the update path too. Note that the
genome ships an `AGENTS.md` as well, so whichever gets there first seeds it:
bring a repo's base layer current *before* adding an overlay.

## `.agents/` is dual-use

`.agents/skills/` (and the genome's `.agents/devenv/` docs export) are the
convention and are **tracked**. The rest of `.agents/` (e.g. `.agents/pi/`, a pi
package's `node_modules`) is platform/tool runtime state and stays **gitignored**.
Repos adopting the convention carry the carve-out in `.gitignore`:

```gitignore
.agents/**
!.agents/skills/
!.agents/skills/**
!AGENTS.md
!CLAUDE.md
```

## Skill discipline (family law)

Skills are imperative + short; docs are the detailed source of truth. Every
skill carries a domain boundary and a deferral footer pointing to the entry
skill (the `repoman` router for cross-domain ordering). RepoMan's `doctor` lints
deferral and ownership — it never installs static skill copies.
