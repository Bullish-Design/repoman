# Decision — the agent surface is the devman link plane

- **Status:** Accepted 2026-09-19. Supersedes the 2026-08-03 agent-files
  convention (tool-shipped / genome / overlay, tracked `.agents/skills/`).
- **Deciders:** the `*man` family (copyroom, gitman, testee, docman, shellij,
  repoman).
- **Reference:** `.scratch/PLATFORM-INVESTIGATION.md` §3.2, §3.3, Q1;
  `devman/.scratch/projects/025-the-link-plane/CONCEPT.md` §7.2-7.3.

The central devman overlay at `~/.config/devman` owns `.agents/` in every repo.
No repo tracks agent skills.

## The convention (fixed)

| Path | Role | Owner |
| ------ | ------ | ------- |
| `~/.config/devman/skills/<name>/` | the shared skill pool — one copy of each fleet skill | devman |
| `~/.config/devman/projects/<p>/agents/skills/<name>` | a **relative symlink** `../../../../skills/<name>` for each fleet skill the project gets | devman |
| `<p>/agents/skills/<name>/` (real dir) | a project-specific skill | devman |
| `<p>/agents/skills/repoman/SKILL.md` | the generated router | repoman (`install-skills`) |
| `AGENTS.md` | the **canonical** repo instructions file — one source of truth | the repo (may be seeded by the genome/copyroom) |
| `CLAUDE.md` | a **symlink to `AGENTS.md`** — every tool reads the same file | the repo (seeded by the genome/copyroom) |

Each repo's `.agents` is itself a symlink to
`~/.config/devman/projects/<p>/agents`.

## The pool-symlink model

The central repo composes the agent surface — *one link per repository, not one
per skill*. Adding a skill to a project is one `ln -s` in the config repository:

```bash
ln -s ../../../../skills/<name> ~/.config/devman/projects/<p>/agents/skills/<name>
```

`devman-link reconcile` runs at every shell entry. It links only the
machine-local views into the repo: `.agents`, `.claude/skills`, `.envrc`, `.loci`,
and `devenv.local.nix`. If a canonical directory is missing, it creates that
directory empty. It does not create the per-skill links above. A person writes
each link by hand with `ln -s`, and the config repository tracks it. A brand-new
repo therefore has an empty skill surface until a person links skills into it.

The shell-entry hook does not check the exit code of `devman-link reconcile`.
Treat the sync as advisory. `devman doctor` and `devman central-verify` are the
real checks.

The expected link set for a managed project is:

- the four manager skills the router needs — `copyroom`, `testee`, `docman`,
  and either `gitman` for v1 or `gitman-v2` for an opted-in v2 project;
- the copyroom canonical set — `copyroom` (already listed), `copyroom-adopt`,
  `copyroom-template-edit`;
- the shared writing guide — `writing`.

Real entries in a project's central skill directory are only project-specific
skills and the generated router.

## The two-writer rule

Two writers, on disjoint paths:

- **devman** curates the pool, the per-project relative symlinks, and the
  project-specific skills that stay real content in the same directory. This is
  hand-written content in the config repository. `devman-link reconcile` writes
  none of it.
- **repoman** generates the router (`install-skills`) from the runtime manager
  roster.

CopyRoom is **not** a writer. Its `agent-files` surface is deleted: no tool
exports skills into a repo. `repoman doctor` lints the expected link set
(`skill:tool-shipped`) and reports a missing link as a **warning**, never a gate.

## Why `.agents/` is not tracked

A repository must evaluate and verify from a clone alone; anything required to do
that is a versioned input. Agent skills are the one content type deliberately
exempted — they are developer-facing guidance, not an input to evaluating or
verifying the repo. The cost is accepted and recorded: a fresh clone and a CI
runner have no agent skills. The escape hatch is that `~/.config/devman` is a git
repo, so CI can clone it and run `devman-link reconcile`.

`AGENTS.md` and `CLAUDE.md` are not under `.agents/`; they stay committed in each
repo.

Each repo ignores `.agents` in `.gitignore`, and a bare `git` also finds the
machine-local links (`.agents`, `.claude/skills`, `.envrc`, `.loci`,
`devenv.local.nix`) in `.git/info/exclude`.
