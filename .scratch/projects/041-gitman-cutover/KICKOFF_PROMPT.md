# Kickoff prompt — Gitman 0.12.0 cutover and cleanup

Paste everything below the line into a new agent session. Start the session at the
gitman repository root: `/home/andrew/Documents/Projects/gitman`.

---

You are finishing the Gitman cutover. Gitman was rewritten as a work-only tool. It
has one command: `gitman work NAME [--from REVSET] [--path DIRECTORY]`. The
repository calls this "v2", but the version number will be a **minor bump to
0.12.0**. Your job is to release 0.12.0 cleanly and to align the skill pool.

Write in Simplified Technical English. Read the `writing` skill first. Keep
sentences short. Use the active voice. Use one word for one meaning.

## Context you must know

- Read `AGENTS.md` and `docs/GITMAN_CONCEPT.md` first. `AGENTS.md` wins when a
  skill disagrees. This repository uses **native jj**. Do not use the `gitman`
  skill's v1 lane commands here. Do not use raw `git` to change state.
- Run project commands inside the devenv shell. Batch them in one call:
  `devenv shell -- bash -c '...'`.
- `pyproject.toml:3` says `version = "2.0.0"`. The newest tag is `v0.11.0`.
  HEAD is 18 commits past it. No v2 tag exists. The decision: the next release is
  **v0.12.0**. It is breaking, and 0.x allows that in a minor bump.
- Gitman 0.12.0 has no `doctor`, `status`, `init`, `start`, `describe`, `sync`,
  `land`, `push`, `publish`, `undo`, `repair`, `release` or `close` command. Native
  jj and `gh` replace them. It uses only the Python standard library. It needs jj
  0.46.0 or later and a colocated repository.
- Consumers pin Gitman by tag. Vendomat still pins `v0.9.1` (v1) in
  `vendomat/flake.nix` at lines 4 and 54, and builds it through uv2nix. RepoMan
  needs a tag to move to.
- The consumer-side decisions are already made. RepoMan makes a clean cut: no
  `gitmanVersion` switch, no dual mode. Do **not** document or promise
  `gitmanVersion`.
- RepoMan work is out of scope. Another session does it.

## Phase 1 — Audit (read-only)

1. List every v1 leftover in this repository. Search for the retired command names
   and v1 ideas: `gitman start|describe|sync|land|publish|push|undo|repair|release|
   status|doctor|close`, `lane`, `gitman.toml`, `.gitman`, `pyjutsu`,
   `.pyjutsu-hooks.toml`, `agent/`, `gitmanVersion`, `v1`, `v2`.
2. Classify each hit: **shipped** (code, README, docs, nix, tests, skills assets),
   **dev tooling** (gitman's own `gitman.toml`, hooks, devenv), or **history**
   (`.scratch/`, CHANGELOG entries for old versions). Leave history alone.
3. Find how this repository releases today. Read `nix/gitman.nix` (the
   `gitman:publish` task, lint, test and wheel tasks) and `gitman.toml`. Note that
   `[publish].verify` in `gitman.toml` is ignored by the work-only tool. Decide
   where the release gate lives now, and say so in your report.
4. Report the audit as a short table before you edit. Continue unless you find a
   surprise (for example, shipped code that still depends on a removed command).

## Phase 2 — Gitman repository changes

Make small commits with native jj. One idea per commit. Use the repository's
commit-message style.

1. **Version.** Set `pyproject.toml:3` to `0.12.0`. Check for any other place that
   states a version (code, tests, docs, nix). The audit finds them. Make them agree.
2. **Remove v1 leftovers** from shipped files that the audit lists. This includes
   dead code, stale pyjutsu wiring in `nix/`, unused dev dependencies, and the empty
   `src/gitman/agent/` directory (a stray `__pycache__`). Do not remove
   `nix/jj.nix`. It pins the jj binary that `work` needs.
3. **Wording.** In shipped docs, name the tool "the work-only interface". Do not
   call it "v2" in shipped text. Keep "v2" only in `.scratch/` history. Add one line
   to the changelog: "Earlier drafts called this interface v2."
4. **Docs.**
   - `docs/USING_GITMAN.md`: replace the `rev = 88c1993…` pin (line 23) with
     `tag = "v0.12.0"`. Delete the `gitmanVersion = 2` passages (about lines 39-48).
     Delete the "use the `gitman-v2` skill" wording. The skill is now named
     `gitman` (Phase 4).
   - `docs/GITMAN_CONCEPT.md`: delete the v1/v2 coexistence text (about line 126)
     and the `gitmanVersion` sentence (about line 129). State plainly that
     version control is native jj and `gh`.
   - `AGENTS.md:10`: remove the "`gitman-v2` skill … shared `gitman` skill remains
     for v1" sentences. One skill, `gitman`, now describes the work-only tool.
   - `README.md`: make it describe only `gitman work`.
   - Add an **integration section** that tells consumers how to do each lifecycle
     step without Gitman. Use a short table: describe → `jj describe`; bookmark →
     `jj bookmark create NAME -r @-`; sync → `jj git fetch` then `jj rebase`; push →
     `jj git push --bookmark NAME`; pull request or merge → `gh pr create`,
     `gh pr merge`; undo → `jj undo`; status → `jj status`; remove a workspace →
     `jj workspace remove NAME`. Mention that `jj status` snapshots the working
     copy. This table is the replacement for the retired verbs. RepoMan's router
     will point at it.
5. **Tests.** Keep the real-jj tests. Add no mock of jj. Make sure a test covers the
   refusal paths in `docs/GITMAN_CONCEPT.md` (occupied path, existing workspace
   name, jj older than 0.46.0 if the code checks it).
6. **Changelog.** Add a `0.12.0` entry. List it as breaking. Name every removed
   command and the native replacement. State that nothing needs migration inside
   Gitman because it stores no state.

## Phase 3 — Verify, release, tag

1. Run the full gate inside the devenv shell, the way `AGENTS.md` says:
   `devenv shell -- bash -c 'ruff check src tests && pytest -q'` (or `devenv test`).
   Run the type check and format check if the repository defines them. Do not
   release on red.
2. Build the wheel with the repository's task. Confirm it installs and that
   `gitman --help` shows only `work`.
3. Release with the repository's release path (the `gitman:publish` task or the
   documented `jj` and `gh release` steps). Create a bookmark first. A workspace name
   is not a bookmark. Tag `v0.12.0` at the release commit. Push the tag and the
   branch. Check the result with `git ls-remote --tags origin v0.12.0` and
   `gh release view v0.12.0`. Do not trust the push exit code alone.
4. Stop and report instead of continuing if the verify gate fails or is skipped, a
   merge conflict appears, or the tag already exists on the remote.

## Phase 4 — Skill pool (`~/.config/devman/skills/`)

The pool is a tracked git repository with many unrelated uncommitted changes
(about 340 entries when this prompt was written). **Touch only the paths named
here. Stage only those paths.** Do not run any command that reverts, cleans or
commits the whole tree. Check `git -C ~/.config/devman branch --show-current`. It
may be empty (a detached head). If so, report it and ask before you commit.

Facts about the pool when this prompt was written:

- `skills/gitman/SKILL.md` is the v1 skill (243 lines, lanes). 55 projects link it
  with a relative symlink such as `projects/<name>/agents/skills/gitman ->
  ../../../../skills/gitman`.
- `skills/gitman-v2/SKILL.md` is the work-only skill. Only `projects/gitman` links
  it.
- `projects/devman/workflows/gitman-commit-message.yaml` calls gitman.
- `common/claude.json` allows `Bash(gitman *)`. That stays valid.

Steps:

1. **Replace the content of `skills/gitman/SKILL.md`** with the work-only skill.
   - Keep `name: gitman`. Write a new `description` that says: open jj workspaces
     with `gitman work`; use native jj and `gh` for all other version control.
   - Start from `skills/gitman-v2/SKILL.md`. Remove the sentences about v1 and about
     "repositories that select v2". Remove the line "Apply this skill only when the
     repository selects work-only Gitman".
   - Add a **lifecycle section** with the native-jj integrate recipe from the Phase 2
     table. State the two laws: verify before you integrate, and never integrate on
     red. Say that RepoMan's `repoman` skill owns lifecycle order, and that this skill
     only gives the commands.
   - Carry over the one v1 rule that still holds: entering a devenv shell can change
     tracked `devenv.lock` or `uv.lock`. Tell the agent to run `jj status` after shell
     entry, to review any lock change, and to save a stable lock change as its own
     change before unrelated work. Do not copy any `gitman start/describe/land` text.
   - Say plainly: "Gitman has one command. Do not run `gitman status`, `gitman land`
     or any other v1 verb. They no longer exist."
   - Keep the skill under about 80 lines. Use Simplified Technical English.
2. **Delete `skills/gitman-v2/`.** Then fix the one symlink that points to it:
   `projects/gitman/agents/skills/gitman-v2`. Replace it with `gitman`. Check the
   `links.yaml` of project `gitman` (and run a repo-wide search of the pool for
   `gitman-v2`) and fix every declaration. Remember the rule: the per-skill pool
   links are hand-authored, one `ln -s` per skill. Do not run
   `devman-link reconcile` unless you have to. If you do, run it only for the
   `gitman` project and read its diff first.
3. **Check `projects/devman/workflows/gitman-commit-message.yaml`.** If it calls a
   retired gitman verb, report it. Do not rewrite it without a decision. Propose the
   native-jj replacement.
4. **Sequencing gate.** The swap changes the guidance of all 55 linked projects at
   once. Their installed closure still ships Gitman v0.9.1 until Vendomat moves.
   Prepare every edit, but **stop and ask me before you commit the pool change.**
   I will confirm that the Vendomat closure ships 0.12.0.
5. After the commit, run: `rg -n "gitman-v2" ~/.config/devman --glob '!.git'` and
   confirm no live reference remains. Confirm that
   `readlink ~/.config/devman/projects/pyjutsu/agents/skills/gitman` still resolves
   and that the file it points to starts with `name: gitman`.

## Phase 5 — Hand-offs (write notes, do not edit other repositories)

Write one short note per item to `.scratch/projects/<next-number>-cutover-handoffs/`
in this repository. Each note is a ready kickoff for another session.

1. **Vendomat.** Bump `flake.nix` lines 4 and 54 from `v0.9.1` to `v0.12.0`. Refresh
   `flake.lock`. Rebuild the toolchain closure. Check that uv2nix builds the
   dependency-free package. Check that the closure supplies **jj 0.46.0 or later**,
   because `gitman work` needs `workspace add --colocate`. Report the jj version it
   ships. Note that the pyjutsu wheel wiring near `flake.nix:143` is now dead for
   Gitman. It may stay for other consumers.
2. **RepoMan.** List what RepoMan must change. The RepoMan session owns the work.
   Point at `/home/andrew/Documents/Projects/repoman/.scratch/projects/041-gitman-cutover/`.
3. **Release gate.** State where "verify before you integrate" lives now. The
   `gitman.toml` `[publish].verify` key and the pyjutsu pre-push hook no longer
   fire in consumers that use native `jj git push`. Propose one option. Do not decide
   it.

## Acceptance checklist

Report each item as done, not done, or blocked, with evidence:

- [ ] `pyproject.toml` and every other version string say `0.12.0`.
- [ ] No shipped file mentions a retired command as if it still works.
- [ ] No shipped file mentions `gitmanVersion` or calls the tool "v2".
- [ ] Gate green: lint, format, types (if defined), tests.
- [ ] Wheel builds. `gitman --help` lists only `work`.
- [ ] Tag `v0.12.0` exists on the remote (`git ls-remote`) and the release exists.
- [ ] Pool: `skills/gitman` holds the work-only skill; `skills/gitman-v2` is gone; no
      `gitman-v2` reference remains; only the named paths were staged.
- [ ] Pool change is committed only after my confirmation.
- [ ] Hand-off notes for Vendomat, RepoMan and the release gate exist.

## Rules for this session

- Stop and ask before any action that is hard to undo and that this prompt does not
  name. Pushing the Gitman branch and tag in Phase 3 is named, so it is authorized
  once the gate is green.
- Report failing output in full. Do not hide a skipped step.
- Do not edit RepoMan, Vendomat, or any consumer repository.
- Keep replies short. Lead with the result or the problem.
