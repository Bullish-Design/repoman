# Adopting devman + RepoMan + the `*man` family — what to install first

How the pieces fit, and the order to bring them into a repo.

## The layers

- **devenv.sh** — the substrate: the reproducible shell every tool runs in.
- **devman** (this layer) — the *literacy* layer: skills + docs + articles that teach an agent to
  operate that shell correctly. Knowledge, not a doer. Installed with RepoMan; no separate repo or
  CLI.
- **RepoMan** — the *conductor*: composes the `*man` doers, owns the lifecycle order, and is the
  single front door (the generated `repoman` entrypoint skill).
- **The `*man` doers** — copyroom (scaffold), testee (verify), gitman (save), docman (publish) —
  each runs *inside* the shell and owns its domain.

devman sits **beneath** RepoMan: RepoMan's entrypoint owns *which tool, in what order*; devman's
skills own *how to operate the shell those tools live in*. They co-install and cross-link.

## Order of adoption

1. **Get a devenv shell.** A working `devenv.nix` + `devenv.yaml`; confirm `devenv shell` enters
   (`shell.md`).
2. **Import RepoMan.** Add the `repoman` input with `flake: false` and import it
   (`inputs-and-imports.md`); set `repoman.enable = true` and `repoman.managers = [ … ]`.
3. **Bootstrap the machine toolchain (once per machine).** The pure-CLI managers
   (repoman/gitman/copyroom/docman) live in ONE system-wide venv, populated from the machine
   `repoman.lock` at the repoman checkout: `cd <repoman checkout> && devenv shell --
   repoman-sync --machine`. There is no per-repo `repoman.lock` anymore (project 12).
4. **Declare `testee` in `pyproject.toml`.** testee runs *inside* your code, so it is a per-repo uv
   dev dependency: `[dependency-groups] dev = ["testee"]` + `[tool.uv.sources] testee = { … }`,
   then `devenv shell -- uv sync --all-extras`.
5. **Run `repoman-sync`.** Verifies the shared toolchain venv, then generates the entrypoint skill
   (`devenv shell -- repoman-sync`) — it installs nothing into this repo's venv.
6. **Verify.** `devenv shell -- repoman doctor` — the self-check validates the toolchain venv, the
   recorded machine manifest, testee's uv declaration, the installed CLIs, and the entrypoint
   skill.
7. **Add managers incrementally.** Each new manager: select it and re-sync. Building one from
   scratch: `authoring-a-manager-module.md`.

## What you get for free

Importing RepoMan pulls the devman literacy layer in with it — the devenv-mechanics skills
(`devenv-run-commands`, `devenv-module-edits`, …) install alongside the entrypoint, so an agent
dropped into the repo learns both the lifecycle *and* the shell mechanics. That's the point of
folding devman into RepoMan rather than shipping it separately.

For the lifecycle order itself (verify before save, scaffold before change), see the `repoman`
skill.
