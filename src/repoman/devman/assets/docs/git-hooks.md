# git-hooks — opt-in pre-commit hooks

devenv integrates [git-hooks](https://devenv.sh/git-hooks/) (pre-commit) declaratively. Hooks are
**opt-in**: nothing runs until you enable specific hooks.

## Enable

    git-hooks.hooks = {
      ruff.enable = true;
      ruff-format.enable = true;
    };

On the next shell entry devenv installs the git hook scripts into `.git/hooks`. Hooks run inside
the devenv environment, so they use the repo's pinned tools (consistent with `devenv-run-commands`).

## Notes

- Some devenv versions surface this as `pre-commit.hooks.*`; check the version's docs if
  `git-hooks.hooks` doesn't resolve.
- Running hooks manually: `devenv shell -- pre-commit run --all-files`.
- Hooks are determinism-friendly: same pinned tools in CI and locally — see `ci-inside-devenv.md`.
- If `*man` managers own verification (e.g. testee), prefer routing through them rather than
  duplicating checks as raw hooks — see the `repoman` skill.
