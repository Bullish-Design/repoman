---
name: devenv-python-venv
description: Use on ModuleNotFoundError or import failures inside the devenv shell, or after a fresh venv. The venv exists but deps may not be installed.
auto_trigger:
  keywords: ["ModuleNotFoundError", "import fails", "no module named", "fresh venv", "uv sync", "package not installed", "editable install"]
---

# A venv that exists ≠ deps that are installed

`languages.python.venv.enable = true` creates a venv and puts it on PATH, but **the project's
dependencies are not in it until a sync runs**. Imports then fail with `ModuleNotFoundError` even
though "the venv is enabled."

Fix — install the deps into the active venv:

    devenv shell -- uv sync --all-extras      # generic
    devenv shell -- repoman-sync              # if the repo wires repoman (installs the toolchain)

Then run your command **through the shell** (`devenv shell -- python …`) so it uses that venv — see
the `devenv-run-commands` skill. Editable installs (`uv pip install -e .`) put your package on the
path so `import yourpkg` resolves to the working tree.

Grep-able detail: `languages-python.md`. If the *command* (not a Python import) is missing, it's a
PATH question — see `command-not-found-in-shell.md` / the `devenv-troubleshoot` skill.

For *when* in the lifecycle to sync, see the `repoman` skill.
