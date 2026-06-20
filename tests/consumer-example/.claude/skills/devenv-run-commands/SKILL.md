---
name: devenv-run-commands
description: Use when about to run pytest, python, uv, ruff, or any build/tooling command in this repo. Enforces running through the devenv shell.
auto_trigger:
  keywords: ["command not found", "run pytest", "run the tests", "run python", "run uv", "run ruff", "run the build", "bare command", "wrong python"]
---

# Run commands through the devenv shell

This repo is managed by **devenv.sh**. A bare `pytest` / `python` / `uv` / `ruff` runs in a
shell without the repo's pinned PATH, env vars, and determinism settings — it will behave
differently or fail.

**Always** run in-repo commands as:

    devenv shell -- <command>

…or use the repo's own scripts/tasks (e.g. `devenv shell -- repoman doctor`). For a long or
heavy command, run it in the background and poll its log rather than blocking the shell — see
the `devenv-processes` skill.

If a command still isn't found inside the shell, it's a venv-vs-nix-vs-script question — see the
`devenv-troubleshoot` skill. Background and reference: `shell.md` in the devenv docs export.

For *when* to verify vs. commit vs. release, see the `repoman` skill.
