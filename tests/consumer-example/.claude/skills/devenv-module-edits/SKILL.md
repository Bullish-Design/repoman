---
name: devenv-module-edits
description: Use when you edited a modules/ file, devenv.nix, or env.* and nothing changed. Resolves the lock + eval-cache staleness loop.
auto_trigger:
  keywords: ["nothing changed", "module edit", "edited devenv.nix", "no effect", "stale", "rebuild devenv", "eval cache", "devenv.lock", "module not picked up"]
---

# When a module edit "does nothing"

A `.nix` edit that has no effect is almost always a stale cache. There are **two** layers; pick by
*what you edited*:

- Edited **this repo's own** `devenv.nix` / `env.*` → stale **eval cache**:

      devenv shell --refresh-eval-cache -- <cmd>     # or: rm -rf .devenv

- Edited a **module this repo imports by path** (it's pinned in `devenv.lock`) → re-lock it:

      rm -f devenv.lock        # re-locks on next entry
      devenv update <input>    # surgical: re-lock one input

- Don't know which → reset both and re-enter:

      rm -f devenv.lock && rm -rf .devenv

Grep-able summary: `lock-and-cache.md`. The three-situation walkthrough (consumer pin vs local
module vs input update): the `the-lock-cache-loop.md` article.

For *when* in the lifecycle to rebuild vs. verify vs. commit, see the `repoman` skill.
