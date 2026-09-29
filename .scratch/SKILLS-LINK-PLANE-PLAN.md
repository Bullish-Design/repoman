# Skills link-plane plan

Date: 2026-09-19
Mode: planning only
Scope: ~/Documents/Projects and ~/.config/devman

This plan accepts the settled decision in PLATFORM-INVESTIGATION.md section 3.2:
the central overlay owns .agents. The repository keeps no tracked agent skills.

## 1. Re-measured state

| Finding | Current value | Measurement command |
|---|---|---|
| F1 | docman tracks 26 .agents files. DOCMAN_SKILLS_DIR still points to ../.agents/skills. The central declaration omits .agents. | git -C ~/Documents/Projects/docman ls-files .agents | wc -l; rg -n '.agents|DOCMAN_SKILLS_DIR' ~/Documents/Projects/docman/modules/docman.nix ~/.config/devman/projects/docman/devenv.local.nix |
| F2 | 11 tracked real directories have no central project: allium-env 42, clinch 4, fsdantic 5, inferference 26, nix-meta 5, nixos-core 4, nix-terminal 5, PyGentic 4, pytuin-desktop 4, silverbullet-server 4, template-py 4. | Loop over Projects directories. Select real .agents, no central project, and git ls-tree count greater than zero. |
| F3 | Tracked content outside .claude/skills remains in agentfs commands, paloma-story-generation settings, settings files in flora, loci-core, lodestar, nix-meta, nix-secrets, and flora scheduled_tasks.lock. Promotion backups also appear. | Loop over repos with git ls-tree -r --name-only HEAD -- .claude and exclude .claude/skills. |
| F4 | .envrc: argentic, image-gen-pipeline, nixbuild, nixvim, PyGentic. .loci: argentic, devman, image-gen-pipeline, repoman, templateer_v2. devenv.local.nix: repoman. | Loop over .envrc .loci devenv.local.nix with git ls-tree. |
| F5 | 395 tracked promotion paths: devman 8, flora 1, gitman 1, image-gen-pipeline 28, interplay 5, loci-core 343, nixbuild 1, nix-secrets 1, nixvim 1, pyllij 4. | Loop over git ls-tree output and count paths matching .devman-promoted. |
| F6 | Trunks and working copies now have zero devman/modules imports. Local lane refs still have 38 stale refs across flora, flora-qc, llgym, loci.nvim, lodestar, nix-nvim, nixvim, pyjutsu, pytuin, repoman, structured-agents-v2, talkee, templateer_v2, terminal-state, and testee. | Scan main with git show. Scan all lane refs with git for-each-ref and the same test. |
| F7 | 10 devenv.nix files set repoman.managers: agentman, flora-core, forgelab, inferference, lodestar, nix-desktop, nix-nvim, nix-paseo, paloma-text-pipeline, talkee. Three set repoman.cliProvider: flora-core, nix-nvim, paloma-text-pipeline. | rg -l 'repoman\.managers[[:space:]]*=' ~/Documents/Projects/*/devenv.nix; same for cliProvider. |
| F8 | gitman agent-files remains in CLI code, agent_files.py, docs, and tests. | rg -n 'agent-files|agent_files' ~/Documents/Projects/gitman/src ~/Documents/Projects/gitman/docs ~/Documents/Projects/gitman/tests |
| F9 | fsdantic trunk is fix/materialization-remove-exdev-fallback, in sync with origin. main is a merged local lane. | gitman --repo ~/Documents/Projects/fsdantic status; git branch --list |
| F10 | Central still has parked-paloma-handoff, parked-paloma-pairwise-judge, and parked-paloma-judge-skill. | git -C ~/.config/devman branch --list '*paloma*' |
| F11 | repoman doctor now reports FAIL zensical — zensical not on PATH. installed:test is OK. It also reports a pre-existing copier import failure and a test-skill deferral warning. | devenv shell -- repoman doctor |
| F12 | The 11 F2 repositories say that nothing under .agents is tracked, although their trunks track agent files. | rg -n 'agents' on the 11 .gitignore files. |

The F6 trunk result and the F11 test result differ from the brief. This plan
uses the new values. Stale lane refs still need an owner decision.

## 2. Decisions per blocker

### B1 — docman

Recommendation: choose Option B. Move docman's shipped skill pack into a
tracked package asset such as docman/skills. Set DOCMAN_SKILLS_DIR to that Nix
store path. Keep the no-repo-skills law absolute.

canonical = repo works, but it is a stopgap. paths.resolve makes the repository
canonical and exposes a central view. That preserves a real repo directory and
violates the settled content rule. A package asset matches the Nix path contract.

Exact change: move the skill asset, update the module, tests, docs, and
docs-skills-install. Archive .agents. Untrack it. Add the central .agents link.

Exact command:

    cd ~/Documents/Projects/docman
    gitman start link-plane-docman
    # edit module, asset, tests, and docs
    gitman untrack .agents
    devenv shell -- base:check
    devenv shell -- base:test
    gitman describe -m "refactor: package docman skills"
    gitman land
    gitman push
    cd ~/.config/devman
    gitman start link-plane-docman-overlay
    # add the .agents declaration
    devenv shell -- devman-link reconcile
    gitman describe -m "chore: link docman agent surface"
    gitman land
    gitman push

Run reconcile only after the declaration and archive exist.

Proof: docman doctor reports a store-path skill directory; git ls-files
.agents prints 0; test -L .agents exits 0; link status prints docman:.agents ok.

Risk: deploy or check code may require a writable checkout path.
Rollback: gitman undo before landing. After landing, revert both commits and
restore the archive only after removing the declaration.

Questions:
- Is the no-repo-skills law absolute? Recommended: yes.
- If not, should docman use canonical = repo?
- Do deploy and check work with a store path? Recommended: yes.

### B2 — 11 real agent directories

Recommendation: define the fleet as every live git repository in
~/Documents/Projects. Adopt all 11. Create central project directories. Move
project-own skills in allium-env and fsdantic to central.

Central command:

    cd ~/.config/devman
    gitman start link-plane-adopt-b2
    # create each project manifest and central declaration
    gitman describe -m "feat: adopt remaining fleet projects"
    gitman land
    gitman push

Per-repository command:

    cd ~/Documents/Projects/<repo>
    gitman start link-plane-adopt-<repo>
    mkdir -p ~/Documents/Projects/.archive/<repo>-2026-09-19
    # copy tracked .agents content to the archive
    gitman untrack .agents
    test -L .agents
    devenv shell -- devman-link reconcile
    devenv shell -- base:check
    devenv shell -- base:test
    gitman describe -m "chore: adopt agent surface"
    gitman land
    gitman push

Use link status rather than devenv checks for non-devenv repositories.

Proof: all approved repos have .agents as a symlink, a central
.devman/project.toml, and canonical gitman status. Expected output is exit 0.

Risk: template-py may be the canonical template. Overlay content must not
become template input. Project skills may have users outside this machine.
Rollback: restore from the dated archive after removing the declaration.

Questions:
- Is the fleet every live repo? Recommended: yes.
- Are all 11 live?
- Should the six non-devenv repos join?
- Is template-py the canonical template?
- Should project-own skills move central? Recommended: yes.

### B3 — .claude and .agents

Decision: Claude's actual global configuration remains Claude-managed. Devman
does not relocate it. Devman owns only the default repository-root .claude
contents.

The central layout is:

    ~/.config/devman/agents/
        # default repository-root .claude contents
    ~/.config/devman/projects/<p>/agents/
        # project view; default entries may link to ../../../../agents/<name>

The repository view is:

    .claude -> ~/.config/devman/projects/<p>/agents
    .agents -> .claude

The .agents link is a compatibility alias. It keeps tools that expect .agents
aligned with the repository-root .claude view. Do not create a second copy.
Do not link Claude's global configuration.

Project-specific commands and repository-root Claude settings live in the
central project view. Default content lives in ~/.config/devman/agents/.
The implementation must confirm how devman represents the project view and
default-entry links before it changes the filesystem.

Exact command:

    cd ~/.config/devman
    gitman start link-plane-claude
    # create agents/ and project views
    # declare the repository-root .claude view
    gitman describe -m "chore: centralize repository Claude surface"
    gitman land
    gitman push
    cd ~/Documents/Projects/<repo>
    gitman start link-plane-claude-<repo>
    # archive all tracked repository-root .claude content
    gitman untrack .claude
    # create .agents -> .claude as the compatibility alias
    devenv shell -- devman-link reconcile
    gitman describe -m "chore: link repository Claude surface"
    gitman land
    gitman push

Proof: Claude's global configuration remains at its existing location.
test -L .claude and test -L .agents pass. readlink .agents prints .claude.
Central project content appears once. Link status is ok.

Risk: a whole-directory .claude link can conflict with Claude-created local
files. Inventory those files before linking.

Rollback: remove the .agents alias first, remove the .claude declaration,
restore the archive, and revert the repo commit.

### B4 — tracked machine paths

Recommendation: untrack .envrc, .loci, and devenv.local.nix everywhere. Keep
AGENTS.md and CLAUDE.md tracked.

Exact command: change central declarations first, archive each file, then run:

    gitman untrack .envrc .loci devenv.local.nix
    devenv shell -- devman-link reconcile
    gitman status
    devenv shell -- base:check
    gitman describe -m "chore: untrack machine-local paths"
    gitman land
    gitman push

Proof: no tracked-but-gitignored notice remains; declared paths are symlinks;
the two instruction files remain tracked.
Risk: removing repoman/devenv.local.nix first breaks shell entry.
Rollback: restore the declaration and archive, then revert the repo commit.

Decision: untrack .envrc, .loci, and devenv.local.nix everywhere.

### B5 — promotion residue

Recommendation: archive, then remove all 395 paths. Use
~/Documents/Projects/.archive/<repo>-2026-09-19. Store original paths and
hashes in MANIFEST.txt.

Exact command per repo:

    gitman start link-plane-promoted-<repo>
    mkdir -p ~/Documents/Projects/.archive/<repo>-2026-09-19
    # copy residue paths and record source paths and hashes
    gitman untrack <path>
    devenv shell -- base:check
    gitman describe -m "chore: remove devman promotion residue"
    gitman land
    gitman push

Proof: git ls-tree -r --name-only main | rg '\.devman-promoted($|/)'
returns no lines. Archive hashes match the manifest.
Risk: residue may hold the only local edit.
Rollback: restore the archive and revert the repo commit.
Decision: delete residue after archive and hash verification.

### B6 — stale lanes

Recommendation: abandon stale lanes after an owner check. Do not rebase every
old lane. Leave the two carved 038 lanes and all paloma lanes untouched.

    gitman --repo <repo> status
    gitman --repo <repo> log <lane>
    # owner approves that the lane has no needed work
    gitman --repo <repo> abandon <lane>
    gitman --repo <repo> push

Run gitman repair first for DESYNCHRONIZED or OFF-CANONICAL.

Proof: the all-local-ref scan returns no stale refs approved for removal.
Risk: a lane can contain unrelated work.
Rollback: gitman undo immediately after abandon. Later use the recorded lane
commit in a new workspace.

Decision: sweep obsolete pyjutsu and talkee lanes after owner review. Leave the
two carved 038 lanes untouched.

### B7 — repoman options

Recommendation: delete the public repoman.managers and repoman.cliProvider
options after migrating consumers to .repoman/project.toml. Materialize the
shared store closure first. Keep store as the only default.

Update modules/devenv.nix, src/repoman/checks.py,
modules/scripts/repoman-sync.sh, tests/test_modules_nix.py,
tests/test_checks.py, tests/test_repoman_sync.py, and the fixture. Migrate the
10 option repos and tyo3 to manifests.

    cd ~/Documents/Projects/repoman
    gitman start retire-provider-options
    # edit module, checks, sync script, tests, and fixture
    devenv shell -- base:check
    devenv shell -- base:test
    gitman describe -m "refactor: retire provider compatibility options"
    gitman land
    gitman push
    cd ~/.config/devman
    gitman start materialize-repoman-toolchain
    # materialize and export REPOMAN_TOOLCHAIN_BIN
    devenv shell -- repoman doctor
    gitman describe -m "chore: materialize repoman command closure"
    gitman land
    gitman push

Proof: rg -n 'repoman\.(managers|cliProvider)' on consumer devenv.nix files
has no output. Tests pass. Doctor reports store paths for all pure CLIs.
Risk: consumers without the store module lose manager commands.
Rollback: revert repoman and central commits separately.

Decision: delete both public options. Use store as the only provider. Keep the
roster in .repoman/project.toml. Migrate tyo3 to the store provider.

### B8 — gitman writer

Recommendation: delete gitman agent-files. It writes into the pool-owned surface.

    cd ~/Documents/Projects/gitman
    gitman start remove-agent-files
    # delete agent_files.py, CLI registration, tests, and concept rows
    devenv shell -- base:check
    devenv shell -- base:test
    gitman describe -m "remove: gitman agent-files writer"
    gitman land
    gitman push

Proof: gitman --help has no agent-files. rg on src docs tests has no
implementation or test references.
Risk: an external workflow may call it. Search the fleet first.
Rollback: revert the gitman commit.
Decision: remove it.

### B9 — smaller inconsistencies

- F9: leave fsdantic trunk until active owners finish. Proof is gitman status.
  Do not rename it in this work.
- F10: leave all three paloma lanes untouched. Any action needs a new instruction.
- F11: keep copier and zensical outside this work. Record baseline failures.
- F12: rewrite the 11 affected .gitignore files in B2 lanes. Prove zero
  tracked agent files after adoption.

## 3. Ordered execution plan

Wave 0, decisions. Owner: user and migration lead. Repositories: none.
Answer all open questions and assign owners. This blocks all writes.

Wave 1, docman. Owner: docman owner, then one central-overlay owner.
Repositories: docman and central. Package the asset, then declare and reconcile.

Wave 2, adoption. Owner: one agent per repo and one central writer.
Repositories: central and the 11 F2 repos. Create central manifests first.
Then archive, untrack, reconcile, verify, land, and push.

Wave 3, local paths and repository Claude surfaces. Owner: one agent per
touched repo. Repositories: F3 and F4 repos plus central. Leave Claude's global
configuration unchanged. Change declarations first. Archive tracked
repository-root .claude content. Create .agents -> .claude aliases.

Wave 4, residue. Owner: one agent per affected repo. Repositories: the 10 F5
repos. Archive, hash, untrack, delete, verify, land, and push.

Wave 5, stale lanes. Owner: each lane owner. Repositories: approved stale-lane
repos only. Abandon only after ownership review. Do not touch parked lanes.

Wave 6, repoman options. Owner: repoman and central toolchain owners.
Repositories: repoman, the 10 option repos, tyo3, and central. Materialize the
closure, migrate manifests, update tests, verify, land, and push.

Wave 7, gitman writer. Owner: gitman owner. Repository: gitman. Remove command,
tests, and docs. Verify, land, and push.

Wave 8, final gate. Owner: migration lead. Repositories: all touched repos and
central. Run the definition-of-done checks and report baseline failures.

Every wave leaves its repository canonical, landed, and pushed. The central
repository has one writer at a time.

## 4. Question list

All user decisions are resolved. The implementation must not touch the parked
Paloma repositories or Claude's global configuration.

## 5. What stays

- Central ownership of .agents and the shared skill pool.
- Relative project pool links.
- repoman install-skills as the generated-router writer.
- The Claude-managed global configuration.
- The central default repository-root agent surface under ~/.config/devman/agents/.
- The .agents -> .claude compatibility alias in each adopted repository.
- Tracked AGENTS.md and CLAUDE.md.
- The four-manager RepoMan roster.
- The versioned repoman module as a clone input.
- The three parked paloma lanes.
- The current fsdantic trunk.
- Copier and zensical baseline failures.

## 6. Definition of done

Run from a clean shell after approved waves.

    for d in ~/Documents/Projects/*/; do
      r=${d%/}; [ -d "$r/.git" ] || continue
      ! rg -q 'devman/modules' "$r/devenv.yaml" 2>/dev/null || exit 1
      git -C "$r" show main:devenv.yaml 2>/dev/null | ! rg -q 'devman/modules' || exit 1
    done
    # expected: no output, exit 0

    for n in <approved fleet>; do
      test -L ~/Documents/Projects/$n/.agents || exit 1
      test -f ~/.config/devman/projects/$n/.devman/project.toml || exit 1
    done
    # expected: no output, exit 0

    for d in ~/Documents/Projects/*/; do
      r=${d%/}; [ -d "$r/.git" ] || continue
      test "$(git -C "$r" ls-tree -r --name-only main -- .agents | wc -l)" -eq 0 || exit 1
    done
    # expected: no output, exit 0

    cd ~/Documents/Projects/repoman
    devenv shell -- repoman doctor
    # expected: expected pool links; record copier and zensical baseline failures
    cd ~/.config/devman
    gitman status
    # expected: CANONICAL and no implementation work

    for r in <every touched repo>; do
      gitman --repo "$r" status || exit 1
      (cd "$r" && devenv shell -- base:check) || exit 1
      (cd "$r" && devenv shell -- base:test) || exit 1
    done
    # expected: canonical status and green checks

    gitman --repo <repo> push
    # expected: trunk in sync with origin and no implementation lane remains

Also verify zero dangling links, zero approved tracked promotion paths, zero
central generated routers, and a clean central repoman-sync.
