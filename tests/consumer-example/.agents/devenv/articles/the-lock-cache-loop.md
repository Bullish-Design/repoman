# The lock/cache loop — why your module edit didn't take

You edited a `.nix` file. You re-entered the shell. Nothing changed. This is the single most
common devenv confusion, and it has three distinct causes with three distinct fixes. Diagnose by
asking **what did I edit?**

## Situation 1 — I edited the consumer's own `devenv.nix` / `env.*`

The file is local; no input is involved. The culprit is the **eval cache**.

    devenv shell --refresh-eval-cache -- <cmd>
    # or, the bigger hammer:
    rm -rf .devenv

devenv normally detects changes to the top-level `devenv.nix`, but `import`-ed local files and
some `env.*` interpolations can slip past the change detector — hence the manual refresh.

## Situation 2 — I edited a module that this repo imports by path

The imported module (e.g. `repoman/modules`) is an **input pinned in `devenv.lock`**. Your edit to
the upstream checkout is real, but the consumer is still pinned to the old revision.

    rm -f devenv.lock        # re-locks every input on next entry
    # or surgically:
    devenv update repoman    # re-lock just the `repoman` input

For a tight authoring loop on the module itself, work inside the module's *own* devenv (where it is
local, not an input) so Situation 1 applies instead.

## Situation 3 — I bumped a remote input upstream

A `github:`/`git+https:` input moved; you want the new revision.

    devenv update <input>    # re-lock that one input
    devenv update            # re-lock everything

## When you don't know which

Reset both layers and re-enter:

    rm -f devenv.lock && rm -rf .devenv

This is slower (it re-locks and re-evaluates from scratch) but it is the reliable recovery. The
grep-able summary of the two cache layers is in the `lock-and-cache.md` doc; the skill that fires
on "I edited a module and nothing changed" is `devenv-module-edits`.

For *when* in the lifecycle to rebuild vs. verify vs. commit, see the `repoman` skill.
