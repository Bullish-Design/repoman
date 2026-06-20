---
name: devenv-authoring
description: Use when writing a scripts/tasks/processes entry or a manager module. Covers which surface to use, guarding enterShell echoes, and the 0/1/2/3 exit contract.
auto_trigger:
  keywords: ["write a script", "add a task", "scripts vs tasks", "enterShell", "exit code contract", "authoring module", "manager module", "devenv task dependency"]
---

# Authoring scripts / tasks / processes & modules

Pick the right surface:

- **`scripts`** — a plain command on PATH. No ordering, no deps. Most CLIs.
- **`tasks`** — has dependencies/ordering (`after`/`before`) and runs in a defined sequence. Use
  when one step must precede another.
- **`processes`** — long-running/supervised; started by `devenv up`. See `devenv-processes`.

Two rules that bite agents:

- **Guard `enterShell` greetings** so captured output isn't polluted:

      enterShell = ''if [ -t 1 ]; then echo "…"; fi'';

- **Honor the exit contract**: `0` ok · `1` decision/finding · `2` infra/config · `3` usage. A
  tool's exit code is its API; don't collapse everything to `0`/`1`.

Grep-able surface detail: `scripts-tasks-processes.md`. Building a `*man`-style module (options,
gated config, putting a CLI on PATH): the `authoring-a-manager-module.md` article.

For *when* in the lifecycle to author vs. verify, see the `repoman` skill.
