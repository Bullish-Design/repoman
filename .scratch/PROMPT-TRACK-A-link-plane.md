# Kickoff — finish the link plane (Track A remainder)

Start from the **repoman** repo root. Read `.scratch/PLATFORM-INVESTIGATION.md`
first — sections **D2**, **D3**, **D6**, **3.2**, **3.3**, **Q1**, **Q8**. It
records the architecture decisions this work implements. **Do not re-litigate
them.**

Run commands inside `devenv shell`. Route version control through `gitman`
(`gitman --repo <path> status|log|start|describe|land|abandon|repair`), never raw
`jj`. Read-only `git` inspection (`git log`, `git diff`, `git show`,
`git ls-files`, `git ls-tree`) is fine.

---

## The settled architecture

**devman's central overlay at `~/.config/devman` owns `.agents/` in every repo.**
No repo tracks agent skills. The agent surface is composed inside the central
repo: `projects/<p>/agents/skills/<name>` is a relative symlink
`../../../../skills/<name>` into the shared pool. Real entries are only
project-own skills and the generated router. This is devman's own specified
design — `devman/.scratch/projects/025-the-link-plane/CONCEPT.md` §7.2-7.3,
*"one link per repository, not one per skill."*

**Link-only is the single devman adoption state.** Project identity lives in
`.devman/project.toml`. No repo imports `devman/modules`.

---

## Already done — do not redo

Completed 2026-09-18/19, verified by three independent passes:

- **The fleet-wide pool conversion.** 297 duplicate skill directories are now
  relative pool symlinks. Central repo trunk is at `288cbd79`. 392 symlinks, 0
  dangling, 0 stragglers, 139 project-own skills untouched, 20 generated routers
  intact, `base:check` 52/52, 0 dangling links across the fleet.
- **repoman's agent surface** is the full 8-link set; its router renders four
  routing rows.
- **Central repo lanes cleared**: five lanes → zero. `037-central-settings-gate-2`
  landed (gitman terminology rewrite `save`→`describe`, `reconcile`→`repair`,
  `/`-lanes→`+`). Three obsolete lanes abandoned. `037-part-a-lodestar` archived
  and abandoned.
- **Archive** at `~/Documents/Projects/.archive/devman-central-20260919/` —
  472 files, 8.2 MB: deleted content, the lodestar spec, and the 48 pre-conversion
  divergent copies.

One lane exists in the central repo: **`parked-paloma-pairwise-judge`**, someone
else's draft. **Do not land, touch, or sweep it in.**

## Out of scope

- Do not move `.agents/` back into repos as tracked content.
- Do not use `canonical = "repo"` in `devman.link` — implemented but never used,
  and flipping an existing link fails with `LinkError: refusing promotion`.
- Do not touch the packaging track (uv2nix, vendomat, Attic, `cliProvider`).
- Do not re-run the pool conversion.

---

## Tasks, in dependency order

### Task 1 — Migrate the four repos off `devman/modules` (fixes D2 + D6)

Four repos import devman's plane module. Where a repo *also* receives the central
overlay, two files declare `options.devman.link` and `mergeOptionDecls` throws —
copyroom's shell is broken by this today; agentman's survives only because
nothing currently forces the option, which is a latent trap, not a fix.

| repo | devman ref | imports | `devman = {...}` | `.devman/project.toml` |
|---|---|---|---|---|
| copyroom | v0.5.1 | `devenv.yaml` | – | **missing** |
| agentman | v0.7.0 | `devenv.yaml` | `devenv.nix:35` | present |
| forgelab | v0.4.0 | `devenv.yaml` | `devenv.nix:67` | **missing** |
| lodestar | v0.5.1 | `devenv.yaml` | `devenv.nix:25` | **missing** |

Per repo: remove the `devman` input and the `- devman/modules` import from
`devenv.yaml`; remove the `devman = { enable; project; groups; }` block from
`devenv.nix`; create `.devman/project.toml` where missing
(`schema = 1`, `project = "<name>"`, `groups = ["base"]`, `policy = "stable"`).

**copyroom already has this written** as lane `038-devman-consumer-copyroom`
(local and on origin, **not merged** — confirm with
`git merge-base --is-ancestor 038-devman-consumer-copyroom main`). Its record
claims `base:check` and `base:test` pass with 603 tests. Land it rather than
redoing it.

⚠️ copyroom's working copy may be detached with lane `039`'s deletions
uncommitted. Shelve or stash 039 before landing 038. Do not merge onto a dirty
tree.

**Proof:** each repo's `devenv shell` evaluates, and its generated shell script
contains **one** `devman-link reconcile` line, not two.

### Task 2 — Land copyroom lane `039-remove-agent-files`

Requires Task 1's copyroom half. 039 deletes copyroom's whole agent-files surface
(`AgentConfig`, the `copyroom agent-files` CLI group, the `_check_agent_files`
doctor check, the `agent.overlay` → Copier `--exclude` mapping, the
`src/copyroom/agent/` package) and relocates `resolve_target` to
`gitutil.resolve_repo_root`.

With the central pool as the source of agent skills, copyroom's export is
redundant, so this lane is **required by the architecture**. But it is a draft
that has never run green — only because copyroom's shell was broken.

**Verify before landing.** Run `base:check` and `base:test`. If red, report what
fails and stop; do not force it.

**Proof:** copyroom's suite green with 039 applied, `copyroom doctor` exits 0, no
`agent-files` command remains.

### Task 3 — Stop tracking generated routers in the central repo

20 projects carry `projects/<p>/agents/skills/repoman/SKILL.md` **tracked** in
`~/.config/devman`, and every `repoman-sync` rewrites it. This already produced
churn during the previous session.

Projects: `agentman argentic eventic flora flora-core image-gen-pipeline llgym
loci-core loci.nvim nix-desktop nix-nvim nix-paseo nix-secrets
paloma-text-pipeline poddantic pyllij repoman shellij talkee tyo3`.

Add an ignore rule for generated routers in `~/.config/devman/.gitignore` and
untrack the existing ones (`git rm --cached`, routed through a gitman lane).
Follow that file's existing shape and comment style — it already distinguishes
tracked agent content from runtime state.

**Do this before any broad `repoman-sync`.** Now that pool skills are linked
fleet-wide, a sync regenerates each router with populated rows — the desired
outcome, but it is exactly the churn this task exists to stop.

**Proof:** run `repoman-sync` in two different repos; `git status` in
`~/.config/devman` shows no new modifications.

### Task 4 — Correct the repo-side `.gitignore` and docs

Every repo's `.gitignore` contradicts itself and both halves are now wrong. In
repoman, lines 218-232:

```
# Agent-files generated by `repoman install-skills` ... Generated, not authored
.agents/skills/                       # ← line 221, ignores it
...
# ... `.agents/skills/` IS tracked ...
.agents/**                            # ← line 229
!.agents/skills/                      # ← line 230, un-ignores it
!.agents/skills/**                    # ← line 231
```

`git ls-files .agents` returns **0** regardless — `.agents` is a symlink and git
cannot descend it. Under the settled architecture `.agents/` is wholly external
and nothing under it is tracked. Delete the un-ignore rules; keep one plain
ignore with an accurate comment.

Consider `.git/info/exclude` instead: `.claude/skills` is already excluded there
(`.git/info/exclude:10`), which is the right home for a machine-local link. Make
the two paths consistent.

Then rewrite **`docs/AGENT-FILES.md`**, whose "two-writer rule" section states:

> *"CopyRoom owns the canonical set (package assets + the `agent-files` command)
> and must never fight another writer over the same files"*

After Task 2 copyroom is not a writer at all. The two writers are now **devman**
(curates pool links and project-own skills) and **repoman** (`install-skills`
generates the router). Describe the pool-symlink model and the `skills/` pool.

Apply the `.gitignore` fix across the fleet, not just repoman.

**Proof:** `git status` clean with no `.agents` noise; `git check-ignore -v
.agents` explains itself; the doc describes what the code does.

### Task 5 — Backstop the drift in `repoman doctor`

Nothing enforces which pool links a project gets — that is how repoman ended up
with one skill and agentman with seven. The detection half-exists:
`src/repoman/devman/check.py:75-84` emits `skill:tool-shipped` for a missing
canonical set, and would have reported repoman's gap. Nobody acted on it.

Extend it to the full expected link set: the four manager skills the router needs
(`copyroom`, `gitman`, `testee`, `docman`) plus the canonical set and the personal
layer (`my-ai`, `writing`). Note `p.is_dir()` at `check.py:70` follows symlinks,
so linked skills already register as present — confirm that holds.

Its current remediation message says *"run `copyroom agent-files export`"*, which
is wrong after Task 2. Point it at the pool-link mechanism instead.

Decide and state whether a missing link is `warn` or `fail`, following the
`0/1/2/3` exit-code contract. Add tests beside the existing ones in
`tests/test_devman.py`.

**Proof:** new tests pass; `repoman doctor` in a project with a deliberately
missing link reports it; `devenv tasks run -v base:check` and `base:test` green in
repoman.

---

## Constraints

- **One writer at a time in `~/.config/devman`.** It is jj-colocated and ~48 repos
  symlink into it. If you use subagents, run analysis in parallel but serialise
  every mutation through a single agent on a single lane.
- **`devman-link reconcile` runs at every shell entry.** Deleting a link without
  removing its declaration just recreates it. Change the declaration first.
- **jj is authoritative; git lags.** `git status` and `git diff` against `HEAD`
  can be badly misleading mid-operation — during the previous session a `git diff`
  reported 231 files when the real change was 2. Trust `gitman status`. When
  gitman reports `git HEAD ... lags @`, run `gitman repair`.
- **`gitman sync --dry-run` mutates.** Measured: it performed a real rebase. Check
  `gitman status` after any `--dry-run`, and use `gitman undo` to revert.
- **Verify before landing.** The central repo's gate is
  `for f in projects/*/devenv.local.nix; do nix-instantiate --eval --strict --expr "builtins.functionArgs (import \"$PWD/$f\")" >/dev/null || echo "FAIL $f"; done`
  — expect 52 files, 0 failures. Per-repo it is `devenv tasks run -v base:check`
  and `base:test`.
- **After any abandon or lane switch, immediately check fleet links.** During the
  previous session an abandon left the working copy 47 commits behind and dangled
  six live links, including repoman's own `.agents`. Check:
  ```
  for d in /home/andrew/Documents/Projects/*/; do
    for p in .agents .claude/skills .envrc devenv.local.nix; do
      [ -L "$d$p" ] && [ ! -e "$d$p" ] && echo "DANGLING $d$p"
    done
  done
  ```
  Must print nothing. Note `test` may resolve to pytest inside the devenv shell —
  use `[ -e ]`, not `test -e`.
- **Archive before deleting anything**, into
  `~/Documents/Projects/.archive/devman-central-<date>/`, following the existing
  archive's shape.

## Definition of done

1. No repo imports `devman/modules`; all four have `.devman/project.toml`.
2. `devman/modules/devenv.nix` deleted in devman, once consumers are zero.
3. copyroom's suite green with 039 applied; no `agent-files` surface remains.
4. `repoman-sync` produces no diff churn in `~/.config/devman`.
5. No repo's `.gitignore` or `docs/AGENT-FILES.md` claims `.agents/skills/` is tracked.
6. `repoman doctor` reports a missing pool link.
7. `base:check` and `base:test` green in repoman and copyroom; central gate 52/52.
8. Zero dangling links across the fleet.

Report what changed per repo, and anything that contradicts
`.scratch/PLATFORM-INVESTIGATION.md` — it was written from measurement, but the
fleet moves.
