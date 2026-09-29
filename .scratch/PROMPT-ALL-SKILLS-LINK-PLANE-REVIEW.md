# Kickoff — review and plan the conversion of *all* skills to the devman link plane

Start from the **repoman** repo root. This is a **planning session. It mutates
nothing.** Its one output is a decision document: a costed, ordered plan that
names, for every blocker, the exact change and the exact command, plus a list of
questions for the user.

The previous arc (`.scratch/PROMPT-FLEET-LINK-PLANE-COMPLETE.md`) migrated the
managed fleet. It left a small set of blockers, listed in §4 below. This session
resolves them on paper. A later, separate session implements the result.

---

## 1. Rules for this session

- **Do not mutate.** No `gitman start/land/push`, no file edits outside
  `.scratch/`, no `devman-link reconcile`, no `gitman init`. Read-only git
  inspection is fine (`git log`, `git show`, `git ls-tree`, `git ls-files`,
  `git diff`, `git merge-base`). `gitman status`/`log` are fine.
- **Re-measure before you reason.** The fleet moves. Every number in §3 is a
  measurement with a date. Re-run each measurement and record the new value.
- **Ask, do not assume.** Where a choice is the user's (fleet boundary, tracked
  vs linked content, scope), ask. Do not invent intent.
- **Route version control through `gitman`.** Never raw `jj`/`git` for mutation.
  (This session should not need mutation at all.)
- **STE writing style** (`my-ai` SKILL.md, `writing` SKILL.md): short sentences,
  active voice, one word per meaning.

Read first:

- `.scratch/PLATFORM-INVESTIGATION.md` — §1.3 (fleet inventory), §2 (D1–D7),
  §3.2–§3.4 (the rules R1–R7), §4 (Phase C), §5 (Q1–Q8). **Do not re-litigate
  the settled decision in §3.2/Q1** (the central overlay owns `.agents`).
- `.scratch/PROMPT-FLEET-LINK-PLANE-COMPLETE.md` — the arc that just finished.
  Its "Contradictions and deviations" section is this session's input.
- `.agents/skills/gitman/SKILL.md`, `.agents/skills/repoman/SKILL.md`,
  `.agents/skills/my-ai/SKILL.md`.
- `~/.config/devman/.gitignore` and `~/.config/devman/projects/repoman/devenv.local.nix`.
- The `devman-link` source for the tool's real contract:
  `/nix/store/1k3v49wsb948r1jwxw3yz8sjdd9r95ny-devman-0.6.0/lib/python3.14/site-packages/devman_link/`
  (`paths.py`, `declarations.py`, `reconcile.py`, `excludes.py`). Read
  `paths.py`'s `resolve()` closely: it defines `canonical = "repo"`.

---

## 2. The target end state (settled; restate it, do not debate it)

From §3.2–§3.4 and §1 of the completed arc:

- `~/.config/devman` owns `.agents/` in every repo. No repo tracks agent skills.
- The shared pool is `~/.config/devman/skills/<name>/` — one copy per fleet skill.
- `~/.config/devman/projects/<p>/agents/skills/<name>` is a **relative symlink**
  `../../../../skills/<name>` for each pool skill the project gets.
- Real entries in a project skill dir are only: project-own skills, and the
  generated router `<p>/agents/skills/repoman/SKILL.md`.
- The repo's `.agents` is a symlink to `~/.config/devman/projects/<p>/agents`.
- `.claude/skills`, `.envrc`, `.loci`, `devenv.local.nix` are links declared
  under `devman.link` in the project's `devenv.local.nix`.
- **Two writers, disjoint paths:** devman curates pool links and project-own
  skills; `repoman install-skills` generates the router. copyroom is not a writer.
- The repo keeps only versioned inputs it needs to evaluate and verify from a
  clone. Agent skills are the one content type deliberately exempted.

---

## 3. Measured state at 2026-09-19 (re-measure all of it)

Done and verified:

- All 25 trunks that imported `devman/modules` no longer do. `devman/modules/devenv.nix`
  is deleted. `devman/modules/` holds `link.nix` only.
- `forgelab` and `lodestar` are link-only, with central project dirs.
- The fleet `.gitignore` no longer mentions `agents/skills` (0 files).
- copyroom's `agent-files` docs are deleted; no copyroom doc references it.
- Central tracks 0 generated routers; central `git status` is clean.
- Central gate: 54 `projects/*/devenv.local.nix`, 0 evaluation failures.
- `repoman doctor`: `version:repoman` ok, `skill:tool-shipped — expected pool
  links present` ok.
- `base:check`/`base:test` green in repoman, copyroom, and devman.

Still open, with the exact current numbers:

| # | Finding | Measurement |
|---|---|---|
| F1 | `docman` is not link-only | tracks 26 `.agents/` files; central `devenv.local.nix` omits the `.agents` link, with a comment saying `docman.nix` needs a tracked real dir |
| F2 | 11 repos have a real `.agents/` and no `.devman/project.toml` | `allium-env` (42 tracked), `clinch` (4), `fsdantic` (5), `inferference` (26), `nix-meta` (5), `nixos-core` (4), `nix-terminal` (5), `PyGentic` (4), `pytuin-desktop` (4), `silverbullet-server` (4), `template-py` (4) |
| F3 | 3 more repos track `.claude/` content outside `.claude/skills` | `agentfs` (2 `commands/*.md`), `paloma-story-generation` (1 `settings.json`), plus `settings*.json` in `flora`, `image-gen-pipeline`, `loci-core`, `lodestar`, `nix-meta`, `nix-secrets` |
| F4 | Repos track machine-local paths R4 says the overlay owns | `.envrc`: `argentic`, `image-gen-pipeline`, `nixbuild`, `nixvim`, `PyGentic`. `.loci`: `argentic`, `devman`, `image-gen-pipeline`, `repoman`, `templateer_v2`. `devenv.local.nix`: `repoman` |
| F5 | `.devman-promoted` residue is still tracked | `devman` 8, `flora` 1, `gitman` 1, `image-gen-pipeline` 28, `interplay` 5, `loci-core` 343, `nixbuild` 1, `nix-secrets` 1, `nixvim` 1, `pyllij` 4 |
| F6 | Stale lanes still import `devman/modules` | lanes in `flora`, `flora-qc`, `llgym`, `loci.nvim`, `nix-nvim` (2), `nixvim`, `pyjutsu` (many), `pytuin`, `templateer_v2`, `testee`, `talkee` (many), plus `038-devman-artifacts-structured-agents-v2` and `038-terminal-state-uvlock` |
| F7 | `repoman.managers` / `repoman.cliProvider` are not retired | 10 repos set `managers` (`agentman`, `flora-core`, `forgelab`, `inferference`, `lodestar`, `nix-desktop`, `nix-nvim`, `nix-paseo`, `paloma-text-pipeline`, `talkee`); 3 set `cliProvider` = `"venv"` (`flora-core`, `nix-nvim`, `paloma-text-pipeline`); `tyo3` relies on the `store` default |
| F8 | `gitman` still ships `gitman agent-files` | `gitman/src/gitman/agent_files.py` writes `.agents/skills/gitman/SKILL.md` into a target repo — a second writer to the pool-owned surface |
| F9 | `fsdantic` gitman trunk is not `main` | trunk = `fix/materialization-remove-exdev-fallback`; `main` still carries the old `.gitignore` |
| F10 | Central has 3 parked paloma lanes | `parked-paloma-handoff`, `parked-paloma-pairwise-judge`, `parked-paloma-judge-skill` (the last is the carve from the completed arc) |
| F11 | `repoman doctor` prints pre-existing FAILs | `zensical — zensical not on PATH`; `installed:test` needed `uv sync --extra dev` |
| F12 | `.gitignore` honesty in F2 repos | their `.gitignore` says nothing under `.agents` is tracked, but files are tracked |

Count check at 2026-09-19: `~/Documents/Projects` holds **72** directories, **70** of which
hold a `.git`. **51** of those 70 have a central project dir under the same name.
**54** central project dirs exist; 3 name repos with no directory (`foreman`,
`my-ai`, `siteman`; `my-ai` is delivered as a copyroom layer).

---

## 4. The blockers, and what the session must decide

For each blocker, produce: **a recommendation, the exact change, the exact
command, the proof, the risk, and the open questions.** Do not stop at "do X";
show the command and the expected output.

### B1 — `docman` cannot be link-only while `docman.nix` reads a Nix path

**Evidence.** `docman/modules/docman.nix:175` sets
`DOCMAN_SKILLS_DIR = ../.agents/skills;`. A Nix path must be a real, tracked
directory. `~/.config/devman/projects/docman/devenv.local.nix` documents this and
omits the `.agents` link.

**The mechanism you must evaluate.** `devman-link` supports
`canonical = "repo"` (`declarations.py`: `CANONICAL_KINDS = ("central", "repo",
"external")`; `paths.py` `resolve()` **inverts** the sides for `repo`). With
`canonical = "repo"`, the repository keeps the real tracked content and the
overlay (`projects/<p>/repo/<view>`) carries a *view* into it. No project uses
`canonical = "repo"` today. Read the code and decide whether it is the right
answer, a stopgap, or a mis-fit.

**Decide.**
- Option A: keep the exception, but declare it `canonical = "repo"` so the tool
  owns the relationship. The repo still tracks `.agents`.
- Option B: move docman's skills into a Nix package or flake asset. Set
  `DOCMAN_SKILLS_DIR` to the store path. Then `.agents` can be a central link.
- Option C: keep the hand-written exception and add a `repoman doctor` rule that
  whitelists it by name.
- Option D: something else you find in the code.

**Questions for the user.** Is the "no repo tracks agent skills" law absolute, or
does one named, tool-justified exception stay? If `canonical = "repo"` exists and
works, do you want docman to use it? What breaks in docman's deploy/check path if
`DOCMAN_SKILLS_DIR` points at a store path instead of the checkout?

### B2 — 11 repos with a real `.agents/` and no central project dir

**Evidence.** F2. Their `.agents/skills/` holds pool skills (`copyroom`,
`copyroom-adopt`, `copyroom-template-edit`, `my-ai`, `gitman`, `devenv-*`,
`repoman`) and, in `allium-env` and `fsdantic`, project-own skills
(`allium*`, `distill`, `elicit`, `propagate`, `tend`, `weed`, `SKILL-AGENTFS.md`).
`allium-env` and `PyGentic` already have a linked `.envrc`. `inferference` already
imports repoman. `nix-meta`, `nixos-core`, `nix-terminal`, `pytuin-desktop`,
`silverbullet-server`, and `template-py` do not use devenv at all.

**Decide.**
- The fleet boundary. Is the target "every directory in `~/Documents/Projects`",
  "every repo with a central project dir", or "every repo the user names"?
- For each of the 11: full adoption (create `.devman/project.toml`, a central
  project dir, and the five links), or leave it, or untrack its `.agents` and
  leave it unmanaged.
- Whether the project-own skills in `allium-env` and `fsdantic` move into central
  or stay in the repo as real content.

**Questions for the user.** Which of the 11 are still live? Should the non-devenv
repos (`nix-meta`, `nixos-core`, `nix-terminal`, `pytuin-desktop`,
`silverbullet-server`, `template-py`) join the plane at all? Is `template-py` the
canonical template that copyroom ships, and does that change the answer?

### B3 — `.claude/` is only partly in the link plane

**Evidence.** F3. `devman.link` declares `.claude/skills` only. Several repos
track `.claude/settings.json`, `.claude/settings.local.json`,
`.claude/commands/*.md`, and `.claude/scheduled_tasks.lock`.

**Decide.** Does the plane own *all* of `.claude/`, or only `.claude/skills`?
Which `.claude/*` files are machine-local (link them) versus repo-authored
(config files, command definitions)? Name each file and its owner.

**Questions for the user.** Are `.claude/commands/*.md` repo content or machine
content? Is `.claude/settings.json` shared or per-repo?

### B4 — tracked machine-local paths

**Evidence.** F4. `gitman status` prints "tracked but gitignored" for these.

**Decide.** The exact `gitman untrack` list per repo, and whether that rides the
current lane or a fresh one. State the rule: which paths R4 makes link-only, and
which stay tracked (`AGENTS.md`, `CLAUDE.md` by design).

**Questions for the user.** Do `.envrc` and `.loci` become untracked everywhere?
Does `repoman` keep a tracked `devenv.local.nix`, or link it like every other
repo?

### B5 — `.devman-promoted` residue

**Evidence.** F5. `loci-core` alone tracks 343 paths under `.devman-promoted`.

**Decide.** For each repo: archive then delete, untrack only, or leave. Use the
archive shape at `~/Documents/Projects/.archive/<repo>-<date>/`. Say what the
archive holds and how a reader finds it.

**Questions for the user.** Is the residue dead once the content is in git
history and in central? May we delete it, or must it persist on disk?

### B6 — stale lanes that still import `devman/modules`

**Evidence.** F6. The lanes are unlanded and mostly far behind trunk.

**Decide.** Per lane: abandon, rebase-and-fix, or leave. Justify each. Note that
`038-devman-artifacts-structured-agents-v2` and `038-terminal-state-uvlock` were
carved by the completed arc.

**Questions for the user.** Do you want the old project lanes (`pyjutsu` `003+*`
and `004+*`, `talkee` `17-*`) swept, or left as history?

### B7 — retire `repoman.managers` / `repoman.cliProvider`

**Evidence.** F7. The retirement gate in the completed arc was unmet. `checks.py`
(`_DEFAULT_CLI_PROVIDER = "store"`) must match the module default. `tyo3` needs
`store`. Read `modules/devenv.nix` options `managers` and `cliProvider`, and the
`manifest-venv` fixture at `tests/fixtures/manifest-venv/.repoman/project.toml`.

**Decide.** How to make the options internal (`internal = true`, `readOnly =
true`) or delete them and rename the plumbing. How to migrate each of the 10
repos and `tyo3`. Which default is correct: `venv` (R6, the closure is not
materialised) or `store` (materialise the closure). The full test list to update
(`tests/test_modules_nix.py`, `tests/test_checks.py`, `tests/test_repoman_sync.py`,
`src/repoman/checks.py`, `modules/scripts/repoman-sync.sh`).

**Questions for the user.** Do you want the option surface deleted, or internal
and read-only? Do you want `venv` as the default, or a materialised store
closure as the default?

### B8 — `gitman agent-files` is a second writer

**Evidence.** F8. `gitman agent-files export` writes
`.agents/skills/gitman/SKILL.md` into a target repo.

**Decide.** Delete the command (as copyroom's was), or repoint it at the central
overlay, or leave it. State the effect on `gitman`'s tests and docs
(`gitman/docs/GITMAN_CONCEPT.md`).

**Questions for the user.** Is `gitman agent-files` still wanted? Does any
workflow call it?

### B9 — smaller inconsistencies

- **F9:** `fsdantic` trunk is not `main`. Normalise, or leave and document?
- **F10:** the 3 parked central paloma lanes. Who owns them? When do they land?
  Do not touch them without the user's word.
- **F11:** `repoman doctor`'s pre-existing FAILs (`zensical`, `testee`). Are they
  in scope, or accepted noise?
- **F12:** the F2 repos' `.gitignore` claims nothing under `.agents` is tracked
  while files are tracked. Fix by F2's decision, or reword the comment.

---

## 5. Deliverables of this session

Write **one** document to `.scratch/SKILLS-LINK-PLANE-PLAN.md`. It must hold:

1. **A re-measured state table.** One row per finding F1–F12, with the current
   value and the command that produced it.
2. **A decision per blocker B1–B9.** Recommendation, why, the exact change, the
   exact command, the proof command with its expected output, the risk, and the
   rollback.
3. **An ordered execution plan.** Waves, the owner of each wave, the
   dependencies, and the repositories in each wave. Respect the constraints in
   §6. The plan must land and push every change, and must name the repository
   boundary for each wave.
4. **A question list.** Every unresolved choice, grouped by blocker, phrased as
   one question each, with the recommended answer marked.
5. **A "what stays" list.** Content the plan will not change, and the reason.
6. **A definition of done** for the follow-on implementation session: the exact
   commands a reviewer runs, and their expected output.

Present the document to the user. **Stop there.** Do not start implementation.

---

## 6. Constraints and traps

- **Central is single-writer.** One agent mutates `~/.config/devman` at a time.
- **`devman-link reconcile` runs at every shell entry.** Change the declaration
  before the filesystem.
- **`devman-link` promotion is the safety rule.** It refuses when the canonical
  side changed since the last record. Measured recoveries: create the declaration
  and let promote copy the repo content; then convert pool names to relative
  symlinks. A `.claude/skills` dir that holds `../../.agents/skills/*` symlinks
  makes promotion fail with a same-file error — remove those symlinks first.
- **`canonical = "repo"` inverts the sides.** Read `paths.py` before you rely on it.
- **jj is authoritative; git lags.** Trust `gitman status`/`log`. Run
  `gitman repair` on `DESYNCHRONIZED` or `OFF-CANONICAL`.
- **`git ls-files .agents` returns 0 in a repo whose `.agents` is a symlink.**
  Check `[ -L .agents ]` and the central project dir to decide if a repo is
  converted. To see tracked agent content, use `git ls-tree -r <trunk> --name-only`.
- **Archive before deleting tracked content.** `~/Documents/Projects/.archive/<name>-<date>/`.
- **A repo's `@` may not be based on trunk**, so `gitman start` refuses it.
  Recover with `gitman repair`, or a lane in a workspace (`gitman start <lane>
  --workspace`), then `gitman workspace forget` and remove the directory.
- **Pre-push hooks run verify.** A `devenv.lock` naming `file:///home/andrew/...`
  blocks the push; `relock` fixes it. `devenv shell` rewrites `devenv.lock` in
  place, so re-run `relock` after any shell use and before a commit.
- **`gitman push` is a content-gated fast-forward.** Re-hash twins need
  `gitman push --reset-origin`, which drops forge merge commits.
- **Do not touch the parked paloma lanes** without the user's word.
- **Exit codes:** `0` ok · `1` a decision is needed · `2` infra/config · `3`
  invalid usage.
- **STE writing style** for the plan and for replies.

---

## 7. Report

Report: the re-measured numbers, the decision per blocker, the ordered plan, and
the question list. Where a number contradicts §3 of this prompt or §2 of the
completed arc, say so and give the new number. If a blocker cannot be resolved
without a user decision, stop at the question and say exactly what it blocks.
