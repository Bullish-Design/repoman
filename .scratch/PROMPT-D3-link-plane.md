> **SUPERSEDED — 2026-09-19.** Tasks 0 and 1 of this prompt are done: repoman's
> agent surface is complete and the fleet-wide pool conversion landed (297
> directories → symlinks, central trunk `288cbd79`). The remaining items moved to
> **`.scratch/PROMPT-TRACK-A-link-plane.md`**, which supersedes this file. Kept
> only as a record of how the work was scoped before the lanes were cleared.

# Kickoff — fix the link plane's agent surface (D3)

Start from the **repoman** repo root. Read
`.scratch/PLATFORM-INVESTIGATION.md` first — sections **D3**, **3.2**, **3.3**,
**3.4**, **Q1** and **Q8**. It is the output of a prior investigation and it
records the architecture decision this work implements. Do not re-litigate that
decision.

Run commands inside `devenv shell`. Route version control through `gitman`
(`gitman --repo <path> status|log|save|land`), never raw `jj`. Read-only `git`
inspection (`git log`, `git diff`, `git ls-files`, `git show`) is fine.

---

## The decision you are implementing

**devman's central overlay at `~/.config/devman` owns `.agents/` in every repo.**
No repo tracks agent skills. The agent surface is composed *inside* the central
repo:

- `~/.config/devman/skills/<name>/` — the shared pool, 16 skills, one copy each.
- `~/.config/devman/projects/<p>/agents/skills/<name>` — a **relative symlink**
  `../../../../skills/<name>` for each fleet skill that project should have.
- Real entries in a project's dir are only: project-specific skills, and the
  generated router `<p>/SKILL.md`.
- Each repo's `.agents` is a symlink to `~/.config/devman/projects/<p>/agents`
  (`canonical = "central"`, which is what all 159 existing declarations use).

This is devman's own specified design —
`devman/.scratch/projects/025-the-link-plane/CONCEPT.md` §7.2-7.3: *"one link per
repository, not one per skill… adding a skill to a project is one `ln -s` in the
config repository."*

`projects/argentic/agents/skills/gitman -> ../../../../skills/gitman` is that
design working on disk. Copy its shape.

### Explicitly out of scope — do not do these

- **Do not** move `.agents/` back into any repo as tracked content. An earlier
  draft recommended it; it is withdrawn.
- **Do not** use `canonical = "repo"`. It is implemented (`paths.py:119-121`) but
  used zero times, and flipping an existing link from `central` to `repo` fails
  with `LinkError: refusing promotion` (`reconcile.py:227-231`) because
  `.devman-link-state.json` records the canonical path and hash but not the kind.
- **Do not** touch the packaging / uv2nix / vendomat / Attic work. Separate track.
- **Do not** change `devman_link`'s merge behaviour. It does no composition by
  design; the pool links are plain git-tracked symlinks made outside the tool.

---

## Hard prerequisite: copyroom's shell is broken

Task 3 below depends on it, and you cannot verify anything in copyroom until it
is fixed.

**Cause (already diagnosed, do not re-derive).** copyroom imports
`devman/modules` (`devenv.yaml:37`) against devman `v0.5.1`, *and* its
`devenv.local.nix` symlinks to a central overlay that imports
`/run/current-system/sw/share/devman/link-module.nix`. Both declare
`options.devman.link` with `default` and `description`, so
`mergeOptionDecls` throws. v0.5.1 forces the option at `modules/devenv.nix:473`
(`effectiveLinks = bootstrapLink // cfg.link`), which is why it fires there.

**Fix.** Land lane `038-devman-consumer-copyroom`. It already exists locally and
on origin; its change record claims `base:check` and `base:test` pass with 603
tests. It removes the `devman` input, the `devman/modules` import and the
`devman = {...}` block, and adds `.devman/project.toml`.

⚠️ copyroom's working copy is **detached** with lane `039`'s deletions
uncommitted. Shelve or stash 039 before landing 038. Do not merge onto a dirty
tree.

---

## Tasks

Do them in this order. Each has a stated proof — verify it before moving on.

### Task 0 — populate repoman's agent surface (highest signal, do first)

`~/.config/devman/projects/repoman/agents/skills/` currently holds only
`repoman/`. Add eight relative symlinks, matching `projects/argentic/`'s shape:

```
copyroom               -> ../../../../skills/copyroom
copyroom-adopt         -> ../../../../skills/copyroom-adopt
copyroom-template-edit -> ../../../../skills/copyroom-template-edit
gitman                 -> ../../../../skills/gitman
testee                 -> ../../../../skills/testee
docman                 -> ../../../../skills/docman
my-ai                  -> ../../../../skills/my-ai
writing                -> ../../../../skills/writing
```

Leave `repoman/SKILL.md` as a real file — it is generated.

`copyroom`, `gitman`, `testee`, `docman` are what make the router table render:
`skills.py:75` emits a row only for a manager whose `<skills_dir>/<command>/SKILL.md`
exists, and `m.skill` defaults to `m.command` (`registry.py:51-52`). The other
four cover `repoman doctor`'s `skill:tool-shipped` canonical set and the personal
layer the global `CLAUDE.md` points at.

**Proof:** invoke the `repoman` skill from the repoman repo. Its routing table
must render **four rows** instead of an empty body. Confirm the pool targets
resolve (`ls -L`) and that no link dangles.

### Task 1 — normalize the real-directory copies

Some projects hold **real directories** where pool symlinks belong, so those
copies will drift. Confirmed: `projects/gitman/agents/skills/{copyroom,gitman,my-ai}`.

Audit **all 52** projects under `~/.config/devman/projects/`, classify every
entry in each `agents/skills/` as (a) pool symlink, (b) real dir duplicating a
pool skill, (c) real dir that is genuinely project-specific, (d) generated
router. Convert every (b) to a relative pool symlink.

Before converting, diff each copy against its pool counterpart. **If a copy has
diverged, do not silently discard it** — report the diff and ask which side wins.

**Proof:** every fleet skill exists exactly once, in the pool. A report listing
each project's classification, with zero remaining (b).

### Task 2 — stop the repos lying about `.agents/`

In **repoman** (then the same pattern fleet-wide):

- `.gitignore:226-231` claims *"`.agents/skills/` IS tracked"* and un-ignores it.
  Under this architecture nothing under `.agents/` is tracked — `git ls-files
  .agents` already returns **0**, because git cannot descend a symlink. Delete
  the un-ignore rules and the now-redundant `.agents/skills/` line at `:221`;
  leave a plain ignore.
- `docs/AGENT-FILES.md:54-60` states a "two-writer rule" with copyroom owning an
  in-repo canonical set. Rewrite it for the central-overlay model. The two
  writers are now **devman** (curates pool links and project-specific skills) and
  **repoman** (`install-skills` generates the router). copyroom is not a writer.

Check whether `.git/info/exclude` is the better home than `.gitignore` for these
— `.claude/skills` is already excluded there (`.git/info/exclude:10`), which is
the right place for a machine-local link. Make the two paths consistent.

**Proof:** `git status` is clean with no `.agents` noise; `git check-ignore -v
.agents` explains itself; the doc describes what the code does.

### Task 3 — land copyroom lane `039-remove-agent-files`

Requires the prerequisite (038) landed first.

039 deletes copyroom's entire agent-files surface: `AgentConfig`, the
`copyroom agent-files` CLI group, the `_check_agent_files` doctor check, the
`agent.overlay` → Copier `--exclude` mapping, and the `src/copyroom/agent/`
package; it relocates `resolve_target` to `gitutil.resolve_repo_root`. It is a
**draft lane that has never run green**, only because copyroom's shell was
broken.

With the central pool as the source, copyroom's export is redundant, so this lane
is now required by the architecture. But **verify before landing**: run
`base:check` and `base:test`. If the suite is red, report what fails and stop —
do not force it.

**Proof:** copyroom's suite green with 039 applied; `copyroom doctor` exits 0;
no `agent-files` command remains.

### Task 4 — gitignore generated routers in the central repo

`projects/<p>/agents/skills/<p>/SKILL.md` is git-tracked in `~/.config/devman`
and rewritten by every `repoman-sync`, producing diff churn.

Add an ignore rule for generated routers and untrack the existing ones. Check
`~/.config/devman/.gitignore` — it already distinguishes tracked agent content
from runtime state, so follow its existing shape and comment style.

**Proof:** run `repoman-sync` in two different repos; `git status` in
`~/.config/devman` shows no new modifications.

### Task 5 — backstop the drift

Nothing enforces which pool links a project gets, which is how repoman ended up
with one skill and agentman with seven. The detection partly exists and was
ignored: `repoman doctor`'s `skill:tool-shipped` check
(`src/repoman/devman/check.py:75-84`) flags a missing canonical set and *would*
have reported repoman's gap.

Extend it to the full expected link set — the four manager skills the router
needs plus the canonical set — so drift reports itself. Decide and state whether
a missing link is `warn` or `fail`; follow the existing `0/1/2/3` exit-code
contract. Add tests alongside the existing ones in `tests/test_devman.py`.

**Proof:** new tests pass; `repoman doctor` in a project with a deliberately
missing link reports it; `devenv tasks run -v base:check` and `base:test` green
in repoman.

---

## Constraints and risks

- ⚠️ **`~/.config/devman` has five lanes in flight** — `037-central-settings-gate-2`
  and four others, all real committed branches, with an unbookmarked jj working
  change on top. Tasks 0, 1 and 4 all edit that repo. **Ask before starting**
  which lane to branch from, or whether those lanes should land or be parked
  first. Make each task one commit on its own lane there.
- The repo is jj-colocated. `git status` mid-operation is stale; `git clean`
  no-ops on paths git still thinks are tracked. A tag deleted with `git tag -d`
  persists in jj's `tags()` until an explicit `git_import()` and will make
  `gitman land` refuse with a misleading message.
- `devman-link reconcile` runs at **every shell entry**. If you delete a symlink
  without removing its declaration, the next shell recreates it. Change the
  declaration first, the filesystem second.
- Do not run `copyroom update` in any repo until Task 3 lands — with `.agents`
  symlinked, its export writes into `~/.config/devman`.

## Definition of done

1. repoman's router skill renders four routing rows.
2. Every fleet skill exists once, in the pool; no duplicate real directories.
3. No repo's `.gitignore` or docs claim `.agents/skills/` is tracked.
4. copyroom has no agent-files surface, and its suite is green.
5. `repoman-sync` produces no diff churn in `~/.config/devman`.
6. `repoman doctor` reports a missing pool link.
7. `devenv tasks run -v base:check` and `base:test` green in repoman and copyroom.

Report what you changed per repo, and anything you found that contradicts the
investigation document — it was written from measurement, but the fleet moves.
