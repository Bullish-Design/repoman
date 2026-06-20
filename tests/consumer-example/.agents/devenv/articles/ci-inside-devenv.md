# Running CI inside the devenv shell

The whole value of devenv is reproducibility: the same pinned tools locally and in CI. CI that
shells out to system `python`/`pytest` throws that away. Run the verify/test loop **through the
shell** so CI uses exactly what you use.

## The shape

    # any CI runner
    - run: nix profile install nixpkgs#devenv   # or cachix/install-nix-action + devenv
    - run: devenv shell -- repoman-sync          # install the pinned toolchain
    - run: devenv shell -- repoman doctor         # self-check the wiring
    - run: devenv shell -- repoman status         # or the repo's verify/test verb

Every step is `devenv shell -- …` for the same reason agents must use it locally (the
`devenv-run-commands` skill): the pinned PATH, env, and determinism vars only exist inside.

## Determinism levers

- **Pin everything** via `devenv.lock`; commit it so CI resolves the identical inputs. Don't
  `devenv update` in CI — that re-locks and defeats reproducibility.
- **Cache the nix store** (e.g. Cachix) so CI doesn't rebuild the world each run.
- **No global installs.** If CI needs a tool, add it to `packages` so local == CI
  (`command-not-found-in-shell.md`).

## Exit codes are the CI signal

Route work through the managers / `repoman` and let the `0/1/2/3` contract decide pass/fail:
`0` green; `1` a finding/decision; `2` infra/config broken; `3` usage error. Don't swallow non-zero
exits — they're the point. (`scripts-tasks-processes.md`.)

## Background / long steps

A long build in CI is still a foregrounded, polled step — don't detach it into invisibility. The
local discipline transfers: `background-and-long-running-work.md`.

For *when* in the lifecycle CI verifies (before save/release), see the `repoman` skill.
