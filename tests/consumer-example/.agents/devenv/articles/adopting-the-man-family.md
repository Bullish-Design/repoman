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
3. **Create `repoman.lock`.** Pin the `[repoman]` self entry plus each selected manager.
4. **Run `repoman-sync`.** Installs the manager CLIs, generates the entrypoint skill, **and installs
   devman's skills + docs export** in one step (`devenv shell -- repoman-sync`).
5. **Verify.** `devenv shell -- repoman doctor` — the self-check validates the lock, the installed
   CLIs, the entrypoint skill, and the `devman:skills` / `devman:docs` / `devman:current` rows.
6. **Add managers incrementally.** Each new manager: pin it, select it, re-sync. Building one from
   scratch: `authoring-a-manager-module.md`.

## What you get for free

Importing RepoMan pulls the devman literacy layer in with it — the devenv-mechanics skills
(`devenv-run-commands`, `devenv-module-edits`, …) install alongside the entrypoint, so an agent
dropped into the repo learns both the lifecycle *and* the shell mechanics. That's the point of
folding devman into RepoMan rather than shipping it separately.

For the lifecycle order itself (verify before save, scaffold before change), see the `repoman`
skill.
