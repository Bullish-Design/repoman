# Kickoff — complete the fleet link plane (no half measures)

Start from the **repoman** repo root. This prompt finishes the *man family's
migration to the devman central link plane, end to end, and leaves every repo
committed, landed, and pushed. It supersedes `.scratch/PROMPT-TRACK-A-link-plane.md`
(whose stated scope was four repos; the fleet is larger — see §2).

Read first:

- `.scratch/PLATFORM-INVESTIGATION.md` — §3.2, §3.3, §3.4, §Q1, §Q8 record the
  architecture decision this work implements. **Do not re-litigate it.** §2 (D1-D7)
  records the defects, some of which this prompt now closes.
- `~/.config/devman/projects/<p>/devenv.local.nix` — the central overlay's shape.
- `~/.config/devman/.gitignore` — the central repo's ignore rules.

Run commands inside `devenv shell`. Route **all** version control through
`gitman` (`gitman --repo <path> status|log|start|switch|split|describe|land|abandon|sync|push|repair|untrack|workspace`), **never** raw `jj`/`git`. Read-only `git`
inspection (`git log`, `git show`, `git ls-files`, `git diff`, `git merge-base`) is
fine, but remember `git HEAD` lags jj: **`gitman status` is authoritative**; a
`git diff` against `HEAD` can report hundreds of phantom files. When gitman says
`refs lag jj`, run `gitman repair`.

This repo's own AGENTS.md, `.agents/skills/my-ai/SKILL.md`, and
`.agents/skills/gitman/SKILL.md` still bind. Read them.

---

## 1. The settled architecture (the target state)

**devman's central overlay at `~/.config/devman` owns `.agents/` in every repo.**
No repo tracks agent skills.

- `~/.config/devman/skills/<name>/` — the shared pool. One copy of each fleet skill.
- `~/.config/devman/projects/<p>/agents/skills/<name>` — a **relative symlink**
  `../../../../skills/<name>` for each fleet skill the project gets.
- Real entries in a project's skill dir are only: project-own skills, and the
  generated router `<p>/agents/skills/repoman/SKILL.md`.
- Each repo's `.agents` is itself a symlink to `~/.config/devman/projects/<p>/agents`.
- Same for `.claude/skills`, `.envrc`, `.loci`, `devenv.local.nix`: links into the
  central overlay, declared under `devman.link` in the project's `devenv.local.nix`.
- **Link-only is the only devman adoption state.** Identity lives in
  `.devman/project.toml`. No repo imports `devman/modules`.
- **Two writers, disjoint paths:** devman curates pool links and project-own skills;
  `repoman install-skills` generates the router. copyroom is **not** a writer, and
  its `agent-files` surface is deleted.
- The repo keeps only versioned inputs it needs to *evaluate and verify from a
  clone*: repoman's `modules/` pin, manager CLIs, `AGENTS.md` (and its `CLAUDE.md`
  symlink). Agent skills are the one content type deliberately exempted.

The expected link set for a managed project (repoman's `doctor` checks it):

`copyroom`, `gitman`, `testee`, `docman`, `copyroom-adopt`,
`copyroom-template-edit`, `my-ai`, `writing`.

**No backwards-compatibility shims.** Migrate every repo; delete the plane module,
copyroom's export, and the dead docs. Do not leave a fallback path that keeps the
old model alive.

---

## 2. Measured state at 2026-09-19 (re-measure before acting; the fleet moves)

Already done — **do not redo**:

- Fleet-wide pool conversion: 297 duplicate skill dirs → relative pool symlinks;
  central trunk `7e06743c` (after the router-untrack commit); 139 project-own
  skills untouched; 0 dangling links.
- copyroom lane `038-devman-consumer-copyroom` landed + pushed; copyroom lane
  `039-remove-agent-files` landed + pushed (`3a05e7f2`); 572 tests green; no
  `agent-files` surface.
- repoman: `doctor` link-set check extended; `.gitignore` and `docs/AGENT-FILES.md`
  / `docs/SKILLS.md` rewritten for the pool model; landed to repoman `main`
  (`1389a52b`).
- Central routers: 20 `projects/*/agents/skills/repoman/SKILL.md` untracked and
  ignored; `repoman-sync` no longer churns central.
- agentman: `devman/modules` removed, landed to agentman `main` (`86a2dad3`);
  shell evaluates with **one** `devman-link reconcile` line.
- fornix: `nix/fornix-toolbox/devenv.nix` made self-contained (assets under
  `nix/fornix-toolbox/assets/`); landed + pushed (`8d174e87`). This is what
  unblocked forgelab's shell.
- Fleet `.gitignore`: 59 repos rewritten to a single `.agents` ignore with an
  accurate comment (working copies only — **not yet committed**).

Still open (this prompt's work):

1. **25 repos' trunks still import `devman/modules`.** Their working copies are
   already migrated (the prepared `038-devman-consumer-<repo>` lane removed the
   input/import/block, added `.devman/project.toml`), but the lane is **unlanded**.
   Measured (re-verify): `boomtube browsee cairn docman embeddy fornix grail
   interplay mypi-agent nixbuild nix-desktop nixvim observantic parsedantic
   pydantree pytuin structured-agents-v2 talkee templateer_v2 terminal-state testee
   webdantic zelligate` plus `forgelab lodestar` (migrated in the working copy,
   not committed). So `devman/modules/devenv.nix` cannot be deleted yet.
2. **The fleet `.gitignore` fix is uncommitted in 59 repos.** It must ride each
   repo's lane to trunk.
3. **forgelab and lodestar** are not link-only: their `.agents` / `.claude/skills`
   are real directories, and they have no central project dir. They must get the
   full overlay, like every other repo.
4. **copyroom's docs** still describe the deleted `agent-files` surface
   (`docs/user/agent-files.md` and 9 more files reference it).
5. **repoman's `main` is not pushed**: the pre-push hook blocks it because
   `devenv.lock` names `file:///home/andrew/...` inputs (the leak is on
   `origin/main` too). Needs `relock`.
6. **`repoman doctor` reports `FAIL version:repoman`** (machine venv 0.8.0 vs
   checkout `0.9.0`) — heal with `repoman-sync --machine`.
7. **`devman/modules/devenv.nix`** must be deleted once consumers reach zero, and
   devman must build/land/push without it.
8. Some `038-devman-consumer-*` lanes carry **unrelated work** (e.g. `tyo3` holds a
   whole feature branch; `interplay`, `structured-agents-v2` carry artifacts).
   Split the unrelated paths out before landing.

---

## 3. Tasks, in dependency order

Each task names its **owner** (who may run it), its **parallelism**, and its
**proof**. Land **and push** everything green; "done" means it is on `main` and on
`origin/main`, not merely in a working copy.

### Task 0 — Reconnaissance (serial, short; do not mutate)

Produce a state table. Re-measure everything; do not trust §2.

```bash
# Repos whose TRUNK still imports devman/modules:
for d in /home/andrew/Documents/Projects/*/; do r=${d%/}; [ -d "$r/.git" ] || continue; \
  git -C "$r" show main:devenv.yaml 2>/dev/null | grep -q 'devman/modules' && echo "$r"; done

# Repos whose WORKING COPY still imports devman/modules:
for d in /home/andrew/Documents/Projects/*/; do r=${d%/}; [ -f "$r/devenv.yaml" ] || continue; \
  grep -q 'devman/modules' "$r/devenv.yaml" && echo "$r"; done

# .agents shape (symlink = link-only; real dir = not yet adopted):
for d in /home/andrew/Documents/Projects/*/; do r=${d%/}; \
  [ -L "$r/.agents" ] && echo "link $r" || { [ -e "$r/.agents" ] && echo "REAL $r"; }; done

# Repos with a central project dir:
ls ~/.config/devman/projects/

# Repos tracking agent content:
for d in /home/andrew/Documents/Projects/*/; do r=${d%/}; [ -d "$r/.git" ] || continue; \
  n=$(git -C "$r" ls-files .agents .claude/skills 2>/dev/null | wc -l); [ "$n" -gt 0 ] && echo "$r $n"; done

# Existing devman lanes per repo:
for d in /home/andrew/Documents/Projects/*/; do r=${d%/}; [ -d "$r/.git" ] || continue; \
  git -C "$r" branch --list '*devman*' | sed "s|^|$r: |"; done
```

Also record, per repo: trunk name, `gitman status` verdict, whether `@` is on a
lane, and whether `main` is ahead of `origin`.

**Proof:** a written table: repo → trunk imports? → `.agents` shape → central
project dir? → lanes → push state. This table drives the fan-out.

### Task 1 — Complete the devman migration fleet-wide (parallel across repos)

**One subagent per disjoint repo group.** No two agents mutate the same repo.
Within a repo, use an isolated lane so parallel agents never contend on `@`:

```bash
cd <repo>
gitman --repo . status                 # authoritative
gitman --repo . sync                   # catch up the lane (or main)
gitman --repo . land <038-devman-consumer-<repo>>   # fold into trunk
gitman --repo . status
gitman --repo . sync --trunk
```

- If the `038` lane mixes unrelated work, `gitman split --paths <unrelated…> --into <new-lane>` first, land the migration, and leave the other lane for its owner.
- If there is no `038` lane and the trunk imports the module, perform the three edits by hand (remove the `devman:` input and the `- devman/modules` import from `devenv.yaml`; remove the `devman = { enable; project; groups; };` block from `devenv.nix`; keep/verify `.devman/project.toml` with `schema = 1`, `project = "<name>"`, `groups = ["base"]`, `policy = "stable"`).
- If `gitman start` refuses because `@` is not based on trunk, do **not** force it. Recover with `gitman repair`, or recreate the lane in a workspace (`gitman start <lane> --workspace`), land from that workspace, then `gitman workspace forget` + remove the directory.
- **Verify before landing:** `<repo>/.devenv` builds, i.e. `devenv shell -- true` (or `devenv shell -- echo ok`) exits 0.
- **Land, then push** (`gitman push`). Push runs the repo's verify hook; if the hook blocks:
  - `devenv.lock` names `file:///home/andrew/...` → run `relock`, commit the relock, retry.
  - tests fail → fix or report; **do not force the push**.

**Proof per repo:** `grep -c 'devman/modules' devenv.yaml` = 0; `.devman/project.toml`
exists; `devenv shell` exits 0; `gitman status` canonical; `main` in sync with
`origin`. Then: no trunk imports `devman/modules` anywhere.

### Task 2 — Commit the fleet `.gitignore` fix (parallel, rides Task 1's lanes)

The 59-repo rewrite is in the working copies. Fold each into the repo's current
lane (or a fresh one) and land + push with Task 1's repo work. Verify:

- `grep -rn 'agents/skills' */.gitignore` returns nothing fleet-wide.
- `git check-ignore -v .agents` explains itself in each repo.
- `git status` shows no `.agents` noise.

**Proof:** no repo's `.gitignore` mentions `agents/skills`; the fix is on every
trunk.

### Task 3 — Full link-plane adoption for the non-converted repos (parallel, but central is serial)

forgelab and lodestar (and any other repo whose `.agents` is a real directory)
must become link-only. The central repo is a **single-writer** resource: one agent
mutates `~/.config/devman` at a time. The repo-side steps are independent and may
run in parallel.

Order matters. Per repo:

1. **Archive before deleting anything** that is tracked: move it into
   `~/Documents/Projects/.archive/<repo>-<date>/` using the shape of the existing
   archive.
2. Create the central project dir `~/.config/devman/projects/<p>/devenv.local.nix`
   (copy the shape of an existing one, e.g. `projects/repoman/devenv.local.nix`:
   it imports `/run/current-system/sw/share/devman/link-module.nix` and
   `/run/current-system/sw/share/vendomat/consumer-module.nix`, and declares
   `devman.link` for `.envrc`, `.loci`, `.agents`, `.claude/skills`). It reads the
   project name from `.devman/project.toml`.
3. Create `~/.config/devman/projects/<p>/agents/skills/` and add the expected-set
   pool links (`ln -s ../../../../skills/<name> …`) plus any project-own skills
   (real dirs, moved from the repo or from `skills/`).
4. Ensure `.devman/project.toml` exists in the repo.
5. Materialize the repo-side links with the tool, not by hand:
   `devman-link reconcile --root <repo> --overlay ~/.config/devman --project <p>`
   (or just enter the repo shell — `devman-link reconcile` runs at every entry).
   **Change the declaration first, the filesystem second** — deleting a link
   without removing its declaration recreates it.
6. Untrack in-repo `.agents` content (`gitman untrack`), confirm
   `git ls-files .agents` = 0, and remove the real dirs once the symlinks resolve.
7. Commit + land + push the repo.

⚠️ `devman-link` refuses to overwrite/promote in some shapes
(`LinkError: refusing promotion`). Test on **one** repo first; if reconcile
refuses, stop and report the exact error before touching the rest.

**Proof per repo:** `.agents`, `.claude/skills`, `.envrc`, `.loci`,
`devenv.local.nix` are links that resolve; `git ls-files .agents` = 0;
`devenv shell` evaluates; `devman-link reconcile` reports `ok`; the repo is
pushed. Central: `git status` clean apart from intended changes; central gate
(§6) green.

### Task 4 — Delete devman's plane module (serial; after Task 1 reaches zero)

Consumers are zero once Task 1 lands. Then, in `~/Documents/Projects/devman`:

1. Confirm zero consumers: the Task 0 trunk scan returns nothing.
2. Delete `modules/devenv.nix` (the plane module). Inspect `modules/link.nix` and
   the rest of `modules/`: delete anything that only exists to serve the plane
   module; keep only what the machine still ships (`/run/current-system/sw/share/devman/link-module.nix` stays — R2).
3. Update devman's docs to drop the legacy plane path
   (`AGENTS_GUIDE.md:71`, `USER.md:84`, the repository-map table).
4. Ensure devman still builds (`nix flake check`, or the repo's own gate), and
   that `nix-meta`'s pin still evaluates against the new tree. Bump/publish a
   devman release if the flake exposes the module.
5. Commit, land, push.

**Proof:** `grep -rn 'devman/modules' /home/andrew/Documents/Projects/*/devenv.yaml`
returns nothing; devman builds; the central gate is green; `devman-link reconcile`
still works on a fresh shell entry.

### Task 5 — Remove the remaining backwards compatibility (parallel, per repo)

- **copyroom:** rewrite/delete `docs/user/agent-files.md` and the other docs that
  reference the deleted `agent-files` surface (`docs/user/cli-reference.md`,
  `docs/user/adoption.md`, `docs/user/configuration.md`, `docs/user/layers.md`,
  `docs/user/template-editing.md`, `docs/developer/*`). Ensure the canonical
  template ships no `.agents/` content. Land + push.
- **repoman:** heal the machine toolchain (`repoman-sync --machine`) so
  `version:repoman` is `ok`; fix the `devenv.lock` `file://` leak with `relock`;
  commit the result; land; **push**.
- **Decision gate — retire `repoman.managers` / `repoman.cliProvider` as devenv
  options** (investigation D5/C2). This is the "no backwards compatibility" step
  for the roster/provider seam. Do it only after `cliProvider` has a correct
  default (`venv`, per D4/A3) or the store closure is materialised, and after a
  fleet scan shows no repo relies on the option. Migrate every consumer to
  `.repoman/project.toml`, then delete the options. Land + push repoman.
- **docs:** ensure no doc in the fleet claims `.agents/skills/` is tracked
  (repoman's is done; check copyroom, devman, and the genome/template).

**Proof:** `grep -rn 'agent-files' */docs` is empty; `repoman doctor` exits 0
(or only pre-existing unrelated WARNs); no tracked doc claims tracked
`.agents/skills`.

### Task 6 — Final verification (serial, after all mutations)

1. **Central gate** — expect 52 files, 0 failures:
   ```bash
   cd ~/.config/devman
   for f in projects/*/devenv.local.nix; do \
     nix-instantiate --eval --strict --expr "builtins.functionArgs (import \"$PWD/$f\")" >/dev/null \
       || echo "FAIL $f"; done
   ```
2. **Zero dangling links** fleet-wide:
   ```bash
   for d in /home/andrew/Documents/Projects/*/; do
     for p in .agents .claude/skills .envrc devenv.local.nix .loci; do
       [ -L "$d$p" ] && [ ! -e "$d$p" ] && echo "DANGLING $d$p"; done; done
   ```
   Must print nothing. (Use `[ -e ]`, not `test -e` — `test` may resolve to pytest
   inside the devenv shell.)
3. **No repo imports `devman/modules`** (trunk and working copy) and
   `devman/modules/devenv.nix` is gone.
4. **Nothing under `.agents/` is tracked**: `git ls-files .agents` = 0 in every
   repo; central tracks 0 generated routers.
5. **Every managed repo's shell evaluates** (`devenv shell -- true`), green
   `base:check` / `base:test`.
6. **Everything is pushed**: `gitman status` shows no `ahead of origin` and no
   unlanded lanes anywhere.
7. **`repoman doctor`** reports `skill:tool-shipped — expected pool links present`
   and exits 0 (outside pre-existing unrelated findings).
8. **`repoman-sync` in two repos leaves `~/.config/devman` dirty-free**
   (`git status` clean).

---

## 4. Parallelization plan

Use background subagents. The rules that keep it safe:

- **Analysis in parallel, mutation serialized per resource.** Many readers; one
  writer per repo; **one writer in `~/.config/devman`**; one writer in `devman`.
- **Repo-level work fans out freely** — repos do not share state. Give each agent
  a disjoint repo list (e.g. 4-6 agents × ~5 repos).
- **Isolate lanes with `gitman start <lane> --workspace`** so agents never contend
  on `@`; fold from the lane's own workspace (`gitman land` refuses to yank a live
  workspace's `@`). Land transactions still serialize briefly on the repo lock.
- **Wave order:**
  1. Task 0 recon (one agent).
  2. Task 1 + Task 2 per repo (fan out; each agent owns whole repos, so its lane,
     `.gitignore`, shell verification, land, and push all happen locally).
  3. Task 3 central setup is **serial** (one agent), while repo-side adoption fans
     out only after its central dir exists.
  4. Task 4 (devman) is serial, after Task 1 reaches zero.
  5. Task 5 docs per repo fans out; the repoman option retirement is serial.
  6. Task 6 final gate is serial (one agent).
- **Do not let two agents run `devenv shell` in the same repo at once** — it
  writes `.devenv` state and can confuse the other. One agent per repo at a time.

---

## 5. Constraints and traps (measured, not hypothetical)

- **`devman-link reconcile` runs at every shell entry.** Deleting a link without
  removing its declaration recreates it. Change the declaration first.
- **jj is authoritative; git lags.** Trust `gitman status` / `gitman log`. Run
  `gitman repair` on `DESYNCHRONIZED` / `OFF-CANONICAL`. A `git diff` against
  `HEAD` mid-operation can report hundreds of phantom files.
- **`gitman sync --dry-run` mutates.** Measured: it performed a real rebase.
  Check `gitman status` after it; `gitman undo` reverts.
- **After any abandon or lane switch, immediately check fleet links** (the command
  in Task 6.2). A previous abandon left the working copy 47 commits behind and
  dangled six live links, including repoman's own `.agents`.
- **Archive before deleting anything.** `~/Documents/Projects/.archive/<name>-<date>/`.
- **`git ls-files .agents` returns 0** even in repos that "track" it, because
  `.agents` is a symlink git cannot descend. Do not use it to decide whether a repo
  is converted — check `[ -L .agents ]` and the central project dir.
- **A repo's `@` may not be based on trunk**, so `gitman start` refuses to adopt
  it (`@ holds uncommitted work that is not based on trunk`). Recover with
  `gitman repair`, or recreate the lane in a workspace; do **not** force it.
- **Pre-push hooks run verify.** A `devenv.lock` naming `file:///home/andrew/...`
  blocks the push; `relock` fixes it. Never force-push past a failing verify.
- **`forgelab` imports `fornix/nix/fornix-toolbox`.** Its assets must stay in the
  module's own tree (`nix/fornix-toolbox/assets/`); never let a Nix module reach
  through a machine-local symlink again.
- **Do not touch `parked-paloma-pairwise-judge`** (and the `parked-paloma-handoff`
  lane carved from the same unbookmarked work) in `~/.config/devman` — another
  session owns them. If they block a central mutation, ask the user; do not sweep
  them.
- **Exit-code contract:** `0` ok · `1` a decision is needed · `2` infra/config · `3`
  invalid usage. Keep it consistent across managers.
- **STE writing style** (`my-ai` SKILL.md): short sentences, active voice, one word
  per meaning — docs, commit messages, code comments, replies.

---

## 6. Definition of done

1. No repo imports `devman/modules` — trunk, working copy, or lane — and
   `devman/modules/devenv.nix` is deleted in devman.
2. Every managed repo is link-only: `.agents` is a symlink to its central project
   dir, `.devman/project.toml` exists, and the expected 8-link set resolves.
3. `git ls-files .agents` is 0 in every repo; central tracks 0 generated routers.
4. No `.gitignore` or doc anywhere claims `.agents/skills/` is tracked, and no doc
   references copyroom's deleted `agent-files` surface.
5. `repoman-sync` leaves `~/.config/devman` clean.
6. `repoman doctor` reports the expected link set and a missing link as `warn`.
7. `base:check` and `base:test` are green in every touched repo; the central gate
   is 52/52.
8. Zero dangling links across the fleet.
9. **Every change is landed on `main` and pushed to `origin/main`; no repo carries
   an unlanded lane or a dirty working copy that belongs to this work.**

---

## 7. Report

Report per repo: what changed, the lane/commit, push state, and the proof output.
Report anything that contradicts `.scratch/PLATFORM-INVESTIGATION.md` or §2 of
this prompt — both were written from measurement, and the fleet moves. If a step
cannot be completed safely, stop and say exactly which repo, which command, and
which error; do not force it.
