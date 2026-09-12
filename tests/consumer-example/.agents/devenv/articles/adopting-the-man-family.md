# Adopting devman + RepoMan + the `*man` family — what to install first

How the pieces fit, and the order to bring them into a repo.

## The layers

- **devenv.sh** — the substrate: the reproducible shell every tool runs in.
- **devman** — the machine-wide automation plane: one Dagu control plane per machine. It schedules,
  queues, watches, and routes workflows to `devenv tasks`; it does not implement repository work.
- **Devenv literacy** (this directory) — the genome-shipped docs and articles that teach an agent to
  operate the shell correctly. `copyroom update` converges them; RepoMan does not install them.
- **RepoMan** — the *conductor*: composes the `*man` doers, owns the lifecycle order, and is the
  single front door (the generated `repoman` entrypoint skill).
- **The `*man` doers** — copyroom (scaffold), testee (verify), gitman (save), docman (publish) —
  each runs *inside* the shell and owns its domain.

Devman and RepoMan meet at `devenv tasks`: devman owns *when, where, and under which queue* a
workflow runs; RepoMan owns *which lifecycle manager handles the work and in what order*. The
repository's task graph is the implementation.

## Order of adoption

1. **Get a devenv shell.** A working `devenv.nix` + `devenv.yaml`; confirm `devenv shell` enters
   (`shell.md`).
2. **Import RepoMan.** Add the `repoman` input with `flake: false` and import it
   (`inputs-and-imports.md`); set `repoman.enable = true` and `repoman.managers = [ … ]`.
3. **Join devman when the repo uses automation.** Declare and import the `devman` module, then set
   its project name and workflow groups. The machine-side Dagu control plane is installed once
   through devman's NixOS module; RepoMan does not install a second devman CLI.
4. **Bootstrap the machine toolchain (once per machine).** The pure-CLI managers
   (repoman/gitman/copyroom/docman) live in ONE system-wide venv, populated from the machine
   `repoman.lock` at the repoman checkout: `cd <repoman checkout> && devenv shell --
   repoman-sync --machine`. There is no per-repo `repoman.lock` anymore (project 12).
5. **Declare `testee` in `pyproject.toml`.** testee runs *inside* your code, so it is a per-repo uv
   dev dependency: `[dependency-groups] dev = ["testee"]` + `[tool.uv.sources] testee = { … }`,
   then `devenv shell -- uv sync --all-extras`.
6. **Run `repoman-sync`.** Verifies the shared toolchain, then generates the entrypoint skill
   (`devenv shell -- repoman-sync`) — it installs nothing into this repo's venv.
7. **Verify.** `devenv shell -- repoman doctor` — the self-check validates the toolchain venv, the
   recorded machine manifest, testee's uv declaration, the installed CLIs, and the entrypoint
   skill.
8. **Add managers incrementally.** Each new manager: select it and re-sync. Building one from
   scratch: `authoring-a-manager-module.md`.

## What you get for free

Importing RepoMan supplies the generated lifecycle router only. It does not install devman assets
or the devman CLI. The `.agents/devenv/` docs and articles arrive from the genome and stay current
through `copyroom update`; an enabled devman module separately registers the repository with the
automation plane.

For the lifecycle order itself (verify before save, scaffold before change), see the `repoman`
skill.
