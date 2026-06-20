# lock & cache — why a module edit didn't take

devenv has **two** layers of caching between a `.nix` edit and the running shell. A change that
"does nothing" is almost always one of them.

## `devenv.lock`

Pins every input (nixpkgs, imported modules) to an exact revision. A **module imported by path or
git** is an input: editing the *upstream* module does not change the consumer until the lock is
refreshed.

- Local path input, want live edits picked up → `rm -f devenv.lock` (re-locks on next shell entry),
  or `devenv update <input>` to re-lock one input.
- Remote git input bumped upstream → `devenv update <input>`.

## The eval cache (`.devenv/`)

devenv memoises evaluation. Editing the consumer's **own** `devenv.nix` / `env.*` and seeing no
change usually means a stale eval cache.

- Force a re-eval → `devenv shell --refresh-eval-cache -- <cmd>`.
- Nuke it entirely → `rm -rf .devenv` (rebuilds on next entry).

## The reliable full reset

When unsure which layer is stale:

    rm -f devenv.lock && rm -rf .devenv

Then re-enter the shell (or re-run `repoman-sync`). This is the loop that bit the conductor
hardening work; the worked walkthrough — with the three distinct situations — is in the
`the-lock-cache-loop.md` article. The skill that triggers on it is `devenv-module-edits`.
