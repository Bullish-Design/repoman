# Project 19 — link-plane follow-ups

**Status:** queued follow-up work  
**Created:** 2026-09-19  
**Parent work:** skills link-plane implementation

## Summary

The link-plane migration is complete. The system now uses the released
Vendomat and RepoMan modules. The system switch completed successfully.

This project records the follow-up work that remains optional:

1. Review pre-existing draft lanes.
2. Decide how to handle unrelated full-fleet verification failures.
3. Run a consumer-repository smoke test after the system switch.

None of these items blocks the link-plane migration.

## Completed baseline

The migration reached its required state before this project started.

### Releases and system inputs

The required releases are published:

| Project | Release | Commit | Use |
| --- | --- | --- | --- |
| Vendomat | `v0.4.3` | `04ee9bcaa0f1c7a6b081fb84acc338ca29fcbc5b` | central consumer module and toolchain |
| RepoMan | `v0.9.1` | `7c5b79b995e1942a78dbce8b8677969d3ef11233` | central RepoMan module |

`nix-meta` now pins those published tags. Its retarget commit is
`ef89582fd0f0d0618d956b193be731e2d9309d65`.

The active system uses the rebuilt `server` generation from those inputs.

### Verification evidence

The following checks passed:

- Vendomat Testee CI verification.
- RepoMan Testee CI verification.
- `nix flake check --no-update-lock-file` in `nix-meta`.
- The full `server` system derivation build.
- The `nixos-rebuild dry-build --flake .#server` check.
- The privileged `nixos-rebuild switch --flake .#server` operation.
- The post-switch module inspection.
- The fleet-lock portability check.

The active Vendomat module exports `REPOMAN_TOOLCHAIN_BIN`. The active RepoMan
module accepts the `schema` and `managers` manifest fields. The active modules
contain no `cliProvider` seam.

### Repository hygiene

Every audited repository has a root `.testee/` entry in `.gitignore`. This
prevents Testee reports and run data from entering version control.

The central Devman configuration remains local by design. It has no remote.
That state is accepted and is not a project blocker.

## Follow-up 1 — review pre-existing draft lanes

### Goal

Review old draft lanes without deleting user work. Give every lane an explicit
owner decision or preserve it as an intentional draft.

### Known lanes

These lanes existed before the link-plane work or were preserved during it.

| Repository | Lane | Current handling |
| --- | --- | --- |
| RepoMan | `adopted-98d9fe14` | preserve pending owner review |
| RepoMan | `preexisting-scratch-doc` | preserve pending owner review |
| RepoMan | `preserve-devenv-lock` | preserve pending owner review |
| RepoMan | `preserve-devenv-lock-2` | preserve pending owner review |
| RepoMan | `preserve-preexisting-scratch-doc` | preserve pending owner review |
| GitMan | `preserve-preexisting-devman-envrc` | preserve pending owner review |
| GitMan | `preserve-preexisting-gitman-docs` | preserve pending owner review |
| nix-meta | `adopted-nix-meta-existing` | preserve pending owner review |
| central Devman | `parked-paloma-handoff` | protected; do not change |
| central Devman | `parked-paloma-judge-skill` | protected; do not change |
| central Devman | `parked-paloma-pairwise-judge` | protected; do not change |

Other repositories can hold older lanes. Inspect their GitMan status before
making a fleet-wide claim.

### Review procedure

For each lane:

1. Read the lane description and changed paths.
2. Compare the lane with current `main`.
3. Identify the original owner or source of the work.
4. Check for conflicts and duplicate content.
5. Record one decision: preserve, land, split, or abandon.
6. Record the reason and the next action.

Use GitMan for every status, review, land, and abandon operation. Do not run
raw `git` or `jj` commands.

### Decision options

#### Preserve the lane

Keep the lane unchanged and record its owner and purpose.

**Pros:** no data loss; no unrelated changes reach `main`.  
**Cons:** lane inventory stays less clean.  
**Implication:** the lane remains a future review item.  
**Opportunity:** preserve historical or experimental work until its owner is ready.

#### Land the lane

Review the change, resolve any conflict, verify it, and land it on `main`.

**Pros:** removes draft debt; makes the change part of the supported branch.  
**Cons:** may mix unrelated work into the current branch.  
**Implication:** the owner accepts the change as current project behavior.  
**Opportunity:** reduce long-term lane maintenance.

#### Split the lane

Separate useful work from obsolete or unrelated work. Preserve each result in
its own named lane.

**Pros:** narrows review scope; keeps useful history.  
**Cons:** requires more review and creates more lane operations.  
**Implication:** the owner must decide which part belongs in `main`.  
**Opportunity:** recover a small useful change from a large draft.

#### Abandon the lane

Abandon it only after the owner confirms that the work is obsolete or safely
stored elsewhere.

**Pros:** removes stale lane noise.  
**Cons:** can make recovery harder; an abandoned lane is a destructive choice.  
**Implication:** record the reason before the operation.  
**Opportunity:** keep the active lane set small and clear.

### Acceptance criteria

- Every known lane has a recorded decision.
- No protected Paloma lane changes.
- No user lane is abandoned without explicit owner approval.
- Any landed lane passes the repository verification gate.
- The final lane inventory distinguishes active drafts from stale drafts.

## Follow-up 2 — decide the full-fleet verification scope

### Goal

Decide whether the fleet must be fully green or whether the remaining failures
stay documented baseline debt.

These findings did not block the link-plane migration. They matter only when the
project claims that every repository is green, or when a release depends on one
of the affected repositories.

### Known findings

| Repository or group | Finding | Why it matters |
| --- | --- | --- |
| clinch and PyGentic | Missing pre-commit hooks input or `configPath` | The verification environment may not match the intended hook setup. |
| fsdantic | Missing vendored Cargo source at `.devman/store/vendor/agentfs/cli/Cargo.toml` | A native build cannot resolve the expected vendored source. |
| inferference | `cuda_nvcc` is unfree | Verification needs an explicit license-policy decision or an allowed host. |
| docman | Testee was unavailable in the local verification path | Docman uses its native verification path; this does not show a link-plane failure. |

### Why these findings are separate

The findings concern repository-specific build inputs or host policy. They do
not change the central symlink plane, the RepoMan manifest, the Vendomat store
closure, or the deployed NixOS modules.

Fixing them now would expand the project from link-plane delivery into fleet
environment repair. That can be useful, but it needs a separate scope decision.

### Decision options

#### Fix the findings now

Repair the missing inputs, vendor data, and host policy. Re-run each affected
repository through its supported verification path.

**Pros:** strongest fleet confidence; fewer hidden failures.  
**Cons:** adds environment and dependency work; may require unfree-package approval.  
**Implication:** the project grows beyond link-plane delivery.  
**Opportunity:** produce a stronger fleet release baseline.

#### Accept the baseline and defer the fixes

Keep the findings in this project as known limitations. Do not claim a full-fleet
green state.

**Pros:** preserves the completed scope; avoids unrelated changes.  
**Cons:** the affected repositories remain less verified.  
**Implication:** future work must keep the exceptions visible.  
**Opportunity:** solve each finding with its own owner and evidence.

#### Verify on a suitable CI or host

Run each affected repository in an environment that provides the required hook
inputs, vendored source, or license allowance.

**Pros:** separates code failures from local host limits.  
**Cons:** needs CI or host capacity; may still expose real failures.  
**Implication:** local green status remains conditional.  
**Opportunity:** make the fleet result reproducible for future agents.

### Acceptance criteria

Choose one of the following outcomes:

- all listed findings are fixed and verified;
- all listed findings have an owner, a reason, and a follow-up date; or
- CI evidence shows that the local failures are host-only.

Do not report the fleet as fully green while these findings remain unresolved.

## Follow-up 3 — run a consumer smoke test

### Goal

Confirm that a normal consumer shell uses the active central modules after the
system switch.

### Scope

Use one representative F2 repository and one provider consumer if time allows.
Choose repositories that do not use a temporary local module override. Keep the
central Devman configuration local during the test.

### Procedure

1. Select a representative consumer repository.
2. Enter its normal `devenv shell`.
3. Confirm that the shared manager commands resolve from the system-provided
   toolchain.
4. Confirm that the repository manifest supplies its manager roster.
5. Confirm that the expected `.agents/skills/` links resolve.
6. Run the repository's supported verification command.
7. Record the repository, generation, commands, and result.

The test must prove the normal consumer path. Do not replace the system module
with a sibling checkout during this test.

### Expected observations

- `REPOMAN_TOOLCHAIN_BIN` points to the shared store closure.
- The requested RepoMan, GitMan, Testee, CopyRoom, or DocMan commands resolve.
- The consumer reads `.repoman/project.toml` for its manager roster.
- The link plane resolves the expected skill files.
- Testee artifacts remain under `.testee/` and stay ignored.
- No consumer writes `repoman.cliProvider` or other retired options.

### Acceptance criteria

- One consumer enters its normal shell successfully.
- The shared command closure resolves from the active system configuration.
- The consumer manager roster matches its manifest.
- The expected skill links resolve.
- The supported verification command passes, or the failure has a recorded cause
  outside the link-plane migration.

## Recommended order

Run the follow-ups in this order:

1. Run the consumer smoke test. It is small and confirms the deployed path.
2. Review the draft lanes. This work needs owner decisions.
3. Decide the full-fleet verification scope. Fix only the findings that have an
   owner and a clear reason to expand the project.

## Boundaries

Keep these boundaries for all follow-up work:

- Keep central Devman configuration local.
- Do not add a remote to central Devman.
- Do not modify or abandon protected Paloma lanes.
- Do not remove `.testee/` from any `.gitignore`.
- Use GitMan for version-control operations.
- Use Testee or the repository's documented native verifier for verification.
- Preserve unrelated user work.
- Record evidence before changing the project status.

## Completion definition

This follow-up project is complete when:

- the consumer smoke test has a recorded result;
- every known draft lane has an owner decision or an explicit preserve record;
- the full-fleet findings have a documented disposition; and
- the final report does not claim more verification than the evidence supports.

The original link-plane migration remains complete even if this follow-up project
stays queued or accepts the known verification baseline.
