# Implementation kickoff — convert the fleet to the devman link plane

Start from the RepoMan repository root:

    cd /home/andrew/Documents/Projects/repoman

This is an implementation session. Follow the approved plan in:

    .scratch/SKILLS-LINK-PLANE-PLAN.md

The user approved all decisions in that plan. Do not ask the user to repeat
those decisions. Stop only when an external owner or a new unsafe choice blocks
the work.

## 1. Read the operating instructions

Read these files before changing anything:

    AGENTS.md
    .agents/skills/repoman/SKILL.md
    .agents/skills/gitman/SKILL.md
    .agents/skills/testee/SKILL.md
    .agents/skills/writing/SKILL.md
    .scratch/PLATFORM-INVESTIGATION.md
    .scratch/PROMPT-FLEET-LINK-PLANE-COMPLETE.md
    .scratch/SKILLS-LINK-PLANE-PLAN.md

Read the devman-link implementation:

    /nix/store/1k3v49wsb948r1jwxw3yz8sjdd9r95ny-devman-0.6.0/lib/python3.14/site-packages/devman_link/paths.py
    /nix/store/1k3v49wsb948r1jwxw3yz8sjdd9r95ny-devman-0.6.0/lib/python3.14/site-packages/devman_link/declarations.py
    /nix/store/1k3v49wsb948r1jwxw3yz8sjdd9r95ny-devman-0.6.0/lib/python3.14/site-packages/devman_link/reconcile.py
    /nix/store/1k3v49wsb948r1jwxw3yz8sjdd9r95ny-devman-0.6.0/lib/python3.14/site-packages/devman_link/excludes.py

Read the central configuration and ignore file:

    ~/.config/devman/projects/repoman/devenv.local.nix
    ~/.config/devman/.gitignore

Run all commands inside the pinned devenv shell. Route verification through
Testee. Route version control through gitman. Route central convergence through
copyroom where the plan requires it. Verify before every save.

Do not invoke raw git or jj for mutation. Read-only git inspection is allowed.
Use gitman for all branches, lanes, commits, land operations, pushes, and
untracking.

## 2. Approved end state

The following decisions are final.

### Fleet

Adopt all 11 F2 repositories:

    allium-env
    clinch
    fsdantic
    inferference
    nix-meta
    nixos-core
    nix-terminal
    PyGentic
    pytuin-desktop
    silverbullet-server
    template-py

The fleet boundary is every live git repository in
/home/andrew/Documents/Projects. The six non-devenv repositories may join the
link plane without importing a devenv module.

Move project-own skills from allium-env and fsdantic into their central project
directories. The central project view may contain project-own skills as real
entries. Pool skills remain relative links into the shared pool.

### Agent surface

The central overlay owns the repository-root agent surface.

The shared pool remains:

    ~/.config/devman/skills/<name>/

The default repository-root Claude contents live here:

    ~/.config/devman/agents/

Each project has a central project view here:

    ~/.config/devman/projects/<p>/agents/

Use default entries from ~/.config/devman/agents where appropriate. Keep
project-specific entries in the project view.

For each adopted repository, provide:

    .claude -> ~/.config/devman/projects/<p>/agents
    .agents -> .claude

The .agents link is a compatibility alias. It must not create a second content
copy. Confirm the exact devman declaration and reconcile behavior before
changing the filesystem.

Claude's actual global configuration stays Claude-managed. Do not move it into
~/.config/devman. Do not link or rewrite it.

Do not track agent skills in repositories. Repo-root .claude content also moves
out of repositories. Keep AGENTS.md and CLAUDE.md tracked.

### Claude content

Use the central project view for project-specific repository-root Claude content.
Use ~/.config/devman/agents for default repository-root content.

Do not leave .claude/commands, .claude/settings.json,
.claude/settings.local.json, .claude/scheduled_tasks.lock, or other repository
root .claude content tracked after adoption. Archive tracked content first.

### Machine-local paths

Untrack these paths everywhere:

    .envrc
    .loci
    devenv.local.nix

Change the central declaration before changing the repository filesystem.

### Residue

Archive every .devman-promoted path before removal:

    ~/Documents/Projects/.archive/<repo>-2026-09-19/

Record each original path, source commit, and hash in MANIFEST.txt. Delete the
residue after archive verification.

### Stale lanes

Sweep obsolete pyjutsu 003+ and 004+ lanes and talkee 17-* lanes after checking
their owners and unique changes.

Leave these untouched:

    038-devman-artifacts-structured-agents-v2
    038-terminal-state-uvlock

Do not touch any Paloma repository, branch, lane, or central Paloma lane:

    parked-paloma-handoff
    parked-paloma-pairwise-judge
    parked-paloma-judge-skill

### RepoMan options

Delete the public repoman.managers and repoman.cliProvider options. Do not make
them internal compatibility options.

Keep the manager roster in .repoman/project.toml. Use the materialized store
provider as the only provider. Remove the cliProvider manifest field after all
consumers migrate.

Migrate tyo3 to the store provider. It should retain its git-only roster:

    managers = ["git"]

Materialize and export REPOMAN_TOOLCHAIN_BIN before removing the provider
fallback. Update:

    modules/devenv.nix
    src/repoman/checks.py
    modules/scripts/repoman-sync.sh
    tests/test_modules_nix.py
    tests/test_checks.py
    tests/test_repoman_sync.py
    tests/fixtures/manifest-venv/.repoman/project.toml

### gitman agent-files

Remove gitman agent-files completely. Remove its implementation, CLI
registration, tests, and documentation. Search the fleet for callers first.

### Accepted baseline

Keep these outside this migration:

    copier import failure in repoman doctor
    zensical not on PATH
    test skill deferral warning

Record them in the final report. Do not claim a clean doctor result while they
remain.

## 3. Execution order

### Wave 0 — re-measure and inspect

Re-run the F1–F12 measurements from the plan. Check the current gitman status
for every repository that will change. Check central status first.

Do not start a lane in a repository with an unowned dirty working copy. If
gitman reports unbookmarked work or another session owns a path, preserve it and
carve or park it through gitman.

### Wave 1 — docman

In docman:

1. Archive the tracked .agents content.
2. Move docman's shipped skill pack to a package-owned tracked asset directory.
3. Change DOCMAN_SKILLS_DIR to the Nix store asset path.
4. Update docs-skills-install, tests, and docs.
5. Run Testee verification.
6. Land and push.

Then, in the central devman repository:

1. Add the docman .agents declaration.
2. Verify the declaration before reconciliation.
3. Reconcile.
4. Verify central status.
5. Land and push.

The declaration must exist before the repository .agents path changes.

### Wave 2 — central adoption setup

Use one central writer.

For each approved project:

1. Create .devman/project.toml.
2. Create the central project view.
3. Add the repository-root .claude declaration.
4. Add the .agents alias relationship.
5. Add .envrc, .loci, and devenv.local.nix declarations as needed.
6. Add default repository-root entries from ~/.config/devman/agents.
7. Add project-own skills as central real entries.
8. Convert pool skills to relative links.

Confirm that a whole-directory .claude link and the .agents -> .claude alias
do not cause a same-file or parent-link error. Use a scratch project view if
needed. Do not experiment against a live repository without an archive.

### Wave 3 — repository adoption

Use one agent per repository. Do not run two devenv shells in the same repo.

For every approved repository:

1. Start an isolated gitman lane.
2. Record status.
3. Archive tracked .agents and .claude content.
4. Untrack .agents, .claude, and applicable machine-local paths.
5. Reconcile only after the central declaration exists.
6. Confirm .claude points to the central project view.
7. Confirm .agents points to .claude.
8. Confirm pool skills resolve to the shared pool.
9. Update .gitignore comments for the new ownership model.
10. Run the repository verification.
11. Describe, land, and push.

For non-devenv repositories, use link-plane status and gitman checks. Do not add
a fake devenv module.

### Wave 4 — local paths and residue

For F4 repositories, change declarations before untracking files.

For F5 repositories:

1. Archive every residue path.
2. Write and verify MANIFEST.txt.
3. Untrack and delete the residue.
4. Run verification.
5. Land and push.

### Wave 5 — stale lanes

For each obsolete lane:

1. Run gitman status.
2. Run gitman log for the lane.
3. Check unique changes with the lane owner.
4. Abandon only after approval.
5. Push the resulting trunk state if needed.

Run gitman repair before any operation on an OFF-CANONICAL or DESYNCHRONIZED
repository. Do not touch the carved 038 lanes or Paloma lanes.

### Wave 6 — provider retirement

1. Build and materialize the store closure.
2. Confirm REPOMAN_TOOLCHAIN_BIN in a real consumer shell.
3. Migrate the 10 manager-option repositories and tyo3.
4. Remove public option declarations and venv fallback code.
5. Remove the cliProvider manifest field.
6. Update all named tests and fixtures.
7. Run Testee verification in repoman.
8. Verify representative consumers.
9. Land and push repoman.
10. Land and push central toolchain changes.

Do not remove the fallback before a real store-backed consumer passes its doctor
and task checks.

### Wave 7 — remove gitman agent-files

1. Search all repositories and scripts for agent-files callers.
2. Remove the implementation, CLI registration, tests, and docs.
3. Run Testee.
4. Land and push gitman.

### Wave 8 — final gate

Run the final checks in the plan. Confirm:

- No approved trunk or working copy imports devman/modules.
- Every approved repository has .devman/project.toml.
- Every approved repository has .claude -> central project view.
- Every approved repository has .agents -> .claude.
- No approved repository tracks .agents or .claude content.
- No approved repository tracks .envrc, .loci, or devenv.local.nix.
- No approved .devman-promoted residue remains.
- Central has no generated routers tracked.
- No dangling links exist.
- Central status is canonical and clean.
- Every implementation change landed and pushed.
- Paloma repositories remain untouched.
- Claude's global configuration remains untouched.

## 4. Required reporting

Report each changed repository:

    repository
    lane
    commit
    verification result
    landing result
    push result

Report central changes separately. Report every archived path group and its
archive location.

Report any deviation from the approved end state. Include the command output
that proves the deviation.

Stop and ask only when:

- an owner claims a lane;
- a promotion safety check refuses;
- a central single-writer conflict exists;
- a store closure cannot materialize;
- a repository has unowned work;
- a command would touch a Paloma repository;
- a command would touch Claude's global configuration.

Do not broaden the scope.
