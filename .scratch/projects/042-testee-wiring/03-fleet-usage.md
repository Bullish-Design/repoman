# 03 Fleet usage of Testee and RepoMan's `test` manager

Survey date: 2026-10-10. Read-only. Labels: **V** verified (file or command output), **I** inferred, **U** unknown.
Scope: 70 dirs under `~/Documents/Projects/` plus `~/.config/devman`. Trunk snapshots: `/tmp/tw-trunk/{repoman,template-py,...}`.
Method: `rg -uu` (excludes `.devenv .direnv node_modules .venv .git .jj .worktrees gitman-workspaces .archive *.lock`). `.scratch` is reported apart.

## 1. Summary (V)

- 23 `devenv.nix`/`flake.nix` files pin `Bullish-Design/testee?ref=refs/tags/v0.5.1`. The template adds one more as `{{ testee_ref }}`. No other testee tag is pinned in a live devenv file.
- Every one of them imports `testeeFlake.devenvModules.default`, sets `testee.package` and declares `testee.checks`.
- Testee is never a `devenv.yaml` input. So **no `devenv.lock` pins Testee** (V: zero `testee` nodes in any `devenv.lock`). The only pin is the `ref=` tag in `devenv.nix`. Nix resolves it at evaluation time through `builtins.getFlake`.
- Host `testee` is 0.5.1. It matches every repo pin (V).
- Only 4 of the 19 repos that use Testee route `base:check`/`base:test` through `testee`: agentman, inferference, linkman, mancore. The template-py trunk does the same.
- 13 repos define `testee.checks` but run `base:check`/`base:test` through raw `uv run ruff` and `uv run pytest` task chains. Testee runs only via `testee verify` by hand, `gitman.toml`, or `enterTest`/`testee:verify` from the Testee module.
- No repo calls `repoman:test` or `repoman:test:ci` from code, except RepoMan itself and scopeman (see section 3).
- No CI workflow in any repo mentions Testee (V: `rg` over `*/.github/workflows`). Only siteman runs `devenv test` in CI.

## 2. Per-repo table

Columns: **RM** = imports the RepoMan module (V: `repoman:` input in `devenv.yaml` and `repoman.enable = true`). **Roster** = `.repoman/project.toml` managers. **base:*** = what `base:check` / `base:test` run. **gitman verify** = `gitman.toml` `verify`.

### Repos that use Testee (19, plus the Testee repo itself) (V)

| Repo | RM (pin) | Roster | testee.package / checks | base:check / base:test | gitman verify | Other |
|---|---|---|---|---|---|---|
| agentman | yes v0.12.1 | copy git test | yes / yes | `testee check ruff && testee check ty && lint-imports` / `testee check pytest` | `testee verify --full` | |
| argentic | yes v0.12.1 | copy git test | yes / yes | after `argentic:lint` / `argentic:test` (raw uv ruff, pytest) | `testee verify --full` | flake.nix comment says `testee verify` is the gate |
| flora | yes v0.12.1 | copy git test | yes / yes | after `flora:lint` / `flora:test` (raw) | none | |
| flora-core | yes v0.12.1 | copy git test | yes / yes | after raw tasks | none | |
| flora-qc | yes v0.12.1 | copy git test | yes / yes | after raw tasks | none | |
| fornix | no | none | yes / yes | after `fornix:lint` / `fornix:test` (raw) | `testee verify --full` | own `enterTest` runs `uv run pytest -q` (plus Testee module `enterTest`) |
| inferference | yes v0.12.1 | copy git test | yes / yes | `testee check ruff ruff-format ty` / `testee check pytest` | `testee verify --full` | `ci/runner/library-venv.sh` mentions Testee |
| linkman | yes v0.12.1 | copy git test | yes / yes | `testee verify --full` / `testee check pytest` | none | |
| llgym | yes v0.12.1 | copy git test | yes / yes | after raw tasks | none | |
| loci-core | no | none | yes / yes | after `loci-core:lint/test` (`devenv tasks run loci:*`) | `testee verify --full` | own `enterTest = "devenv tasks run loci:verify"` |
| mancore | yes v0.12.1 (plus vendomat v0.4.5 input) | copy git test | yes / yes | `testee verify --full` / `testee check pytest` | `testee verify --full` | |
| poddantic | yes v0.12.1 | copy git test | yes / yes | after raw tasks (`ruff check .`, `pytest`) | none | |
| pyllij | yes v0.12.1 | copy git test | yes / yes | after raw tasks (lint, format, types, proto) | none | |
| pytuin | no (`imports: []`) | none | yes / yes | after raw tasks | none | |
| repoman | self-hosts (`path:./modules`) | copy git test | yes / yes | `base:test.after = repoman:test` (= `testee verify`); `base:check.after = repoman:lint` | none | `gate` script runs `testee verify --full` |
| scopeman | yes v0.12.1 | copy git test | yes / yes | `base:test.after = ["repoman:test"]`; `base:check.after = scopeman:lint` (raw) | none | only fleet repo that calls `repoman:test` in code |
| shellij | yes v0.12.1 | copy git test | yes / yes | after raw tasks | `testee verify --full` | |
| talkee | yes, local `git+file://` path (comment says v0.12.0) | copy git test | yes / yes | after raw tasks | none | |
| testee | no | none | own module + `./nix/testee-package.nix` | n/a | none | defines the module; see section 5 |
| vendomat | no | none | yes / yes | after `vendomat:lint/test` (raw) | `testee verify --full` | own `nix/testee.nix` defines `testee:quick/full/doctor/report` tasks and `VENDOMAT_TESTEE_HOST_BIN` |

19 users = all rows except the testee repo. Source: `rg -l 'Bullish-Design/testee'` over devenv files.

### Repos with RepoMan but no Testee (V)

| Repo | RM | Roster | Note |
|---|---|---|---|
| eventic | yes v0.12.1 | copy git | `devenv.nix` comment: "does not declare Testee, so `test` is not on the roster"; has a GitHub CI file without Testee |
| forgelab | yes, local `git+file://` | copy git | `enterTest` runs `repoman-sync` |
| mnemonix, nix-desktop, nix-nvim, nix-paseo | yes (local path or template tag) | copy git | `template-nix` repos |
| loci.nvim, nix-secrets | yes via host module `/run/current-system/sw/share/repoman/module/devenv.nix` | copy git | host module is stale (section 4) but inert: no `test` on roster |
| tyo3 | yes via host module | git | same |
| nix-meta, nix-meta-channel4 | `repoman` input, local path in lock | n/a | no Testee |

### Repos with no Testee and no RepoMan wiring (V, `rg` found no live Testee reference in devenv files)

atuout, browsee, cairn, clinch, copyroom, devman, devman-spike, docman, embeddy, fsdantic, gitman, grail, interplay, knappy, nixbuild, nixvim, nix-systems, nixos-core, nvim-review, observantic, parsedantic, pydantree, PyGentic, pyjutsu, siteman, structured-agents-v2, templateer_v2, terminal-state, vendomat-demo, webdantic, zelligate, plus non-repo dirs.
Exceptions in docs only: devman `uv.lock` pins `testee` git tag **v0.5.0** (V: `devman/uv.lock:87`). structured-agents-v2 `uv.lock` uses a local path `directory = ".../testee"`. Both are Python dev dependencies, not wrapper installs.
`.agents/skills/testee` exists in clinch, forgelab, fsdantic, inferference, linkman, nix-meta, nixos-core, nix-terminal, PyGentic, repoman, scopeman, silverbullet-server, template-py, testee, vendomat (V: `ls`).

## 3. References to the named tokens (V)

Live = outside `.scratch`. Counts are hits.

| Token | Live references | Meaning |
|---|---|---|
| `repoman:test`, `repoman:test:ci` | Defined only in `repoman/modules/managers/testee.nix:34-35`. Header comments in 13 fleet `devenv.nix` files say "RepoMan wires `repoman:test`, `repoman:test:ci`, and `enterTest`". Template: 15 files, one `copyroom.yml` check forbids `"repoman:test` in rendered `devenv.nix`. Code use: scopeman `base:test.after`, repoman `base:test.after`. Scopeman `.loci/` guide repeats it. | Fleet does not use the task; the comments are boilerplate from the template. |
| `REPOMAN_TESTEE_HOST_BIN` | repoman: `modules/managers/testee.nix:24`, `modules/devenv.nix:139-140`, `src/repoman/registry.py:108`, tests, README. template-py: 7 files (docs, README). Nowhere else. | Used only by RepoMan. Vendomat has its own twin `VENDOMAT_TESTEE_HOST_BIN`. |
| `REPOMAN_TESTEE_VERSION` | repoman only: `modules/managers/testee.nix:28`, `registry.py:109`, `checks.py:274`, tests. | Doctor version row. Tests fake it as `0.5.0` (stale vs 0.5.1). |
| `testee:verify` | testee only: `nix/testee.nix:66`, its README, AGENTS.md, research docs. Vendomat uses `testee:quick/full` instead. | Defined by the Testee module for every importer (V). Runs `${package}/bin/testee verify --full` (the Nix-pinned package, not the host binary). |
| `enterTest` | Testee module sets it (`testee.nix:67`) for all 19 importers. Own extra `enterTest`: fornix, loci-core, forgelab, devman, tyo3, gitman. RepoMan sets none (since 0.12.1; V: `modules/managers/testee.nix:8-10`, test `test_modules_nix.py:19`). 13 fleet header comments still say RepoMan wires `enterTest` (stale). | |
| `devenv test` | Docs: copyroom (workshop runs it), testee README/AGENTS, cairn, siteman CI, gitman AGENTS. devman docs say it "exits 0 having tested nothing" in 30 of 58 repos. | |

`.scratch` hits (historical, V counts of files/hits):
- `repoman:test`: repoman 5/28, testee 2/17, devman 2/3, vendomat 1/2.
- `repoman:test:ci`: repoman 1/2, testee 2/11, vendomat 1/1.
- `REPOMAN_TESTEE_HOST_BIN`: repoman 2/23, testee 1/3.
- `REPOMAN_TESTEE_VERSION`: repoman 2/15, testee 1/1.
- `testee:verify`: repoman 3/9, testee 1/2.
- `enterTest`: copyroom 61/125, shellij 63/126, vendomat 41/86, structured-agents-v2 44/90, others smaller.

Central `~/.config/devman`:
- `skills/testee/SKILL.md` is the pool skill. It says "Testee 0.5.0" in the description and body. Host is 0.5.1 (stale, V).
- `agents/devenv/**` docs (copied into projects) mention `devenv test` and `enterTest` (V: 39 files).
- `devenv.yaml` of the central repo pins repoman **v0.7.1** with managers `git test` (V). Its `base:check` is a custom Nix eval loop.
- Three projects import the host module: loci.nvim, nix-secrets, tyo3 (`devenv.local.nix`). No fleet repo imports `repoman:*` tasks from the host path otherwise.

## 4. Install locations on this host (V unless noted)

`which -a` (from the repoman devenv shell the tool inherited):

| Command | Path | Resolved | Version | Source |
|---|---|---|---|---|
| testee | `~/.nix-profile/bin/testee` | `/nix/store/rs4i9wy1…-testee-0.5.1/bin/testee` | `testee 0.5.1` | imperative `nix profile` entry |
| gitman | `/etc/profiles/per-user/andrew/bin/gitman` | `…-python3.13-gitman-0.12.1` | 0.12.1 (`--version` flag not supported; version from store path) | home-manager path (NixOS `home-manager.useUserPackages`) |
| jj | `/etc/profiles/per-user/andrew/bin/jj` | `…-jujutsu-bin-0.46.0` | 0.46.0 | same |
| devenv | `/etc/profiles/per-user/andrew/bin/devenv` | `…-devenv-wrapped-2.4.0` | 2.4.0+b904dcb | same, from nix-meta `pinnedDevenv` |
| repoman | `~/Documents/Projects/repoman/.devenv/state/venv/bin/repoman` | repo venv | 0.13.0 | repo-local, not a host install |
| copyroom | not on `PATH` of this shell | | | |

Other host facts:
- `~/.nix-profile/bin` holds only `act` and `testee`. `/run/current-system/sw/bin` holds `devman`, `devman-link` (0.6.0) and `vendomat` (0.5.0). `/etc/profiles/per-user/andrew/bin` holds gitman, jj, devenv. `testee` appears in none of the system or home-manager paths.
- **Testee install method:** `nix profile list` shows `testee` from `git+https://github.com/Bullish-Design/testee?ref=refs/tags/v0.5.1` locked at rev `1c139ecb…`. This is an imperative profile install. No Nix config in `nix-meta`, `nix-systems`, `nix-terminal` or `/etc/nixos/configuration.nix` mentions testee (V: `rg`). So a rebuild or profile rollback does not manage Testee.
- **Login-shell toolchain closure** (`hm-session-vars.sh:16` appends `/nix/store/h9glapz…-repoman-toolchain-core/bin` last on PATH): repoman 0.10.0, copyroom 0.8.0, gitman 0.9.1, plus agentman, docman, pyjutsu 0.23.0, templateer. The per-user gitman 0.12.1 precedes it. A login shell outside a devenv gets repoman 0.10.0. Inside a devenv shell the repo venv wins.
- **Host-installed RepoMan module** (nix-meta `repoman` input, flake.nix pin `v0.9.2`; `flake.lock` locks `v0.7.5`; U which one built generation 152): `/run/current-system/sw/share/repoman/module/managers/testee.nix` still wires `${venvBin}/testee verify --mode quick|ci` and sets its own `enterTest`. That is the old v1 wiring and conflicts with Testee 0.5 (modes are removed). Impact today is nil: the three importers (loci.nvim, nix-secrets, tyo3) do not have `test` in the roster.
- Source of the gitman 0.12.1 per-user package: U (not found in the nix-meta working copy; the live system generation 152 dates 2026-10-09 17:40).
- `testee/.venv` still carries `testee-0.3.0` (V). Not on PATH.
- The Testee wrapper uses `~/.nix-profile/bin/testee` as the default host path in RepoMan (`REPOMAN_TESTEE_HOST_BIN` default). That path exists here (V).

## 5. Pinned versions vs host (V)

| Item | Value |
|---|---|
| Host `testee` | 0.5.1 (rev `1c139ec`) |
| Testee repo checkout | tag `v0.5.1` at `1c139ec` |
| Fleet `devenv.nix` pins | 23 x `v0.5.1`, 0 other |
| `devenv.lock` pin of Testee | none exist (Testee is not a devenv input; only `ref=` tag in `devenv.nix`) |
| `uv.lock` | devman: tag `v0.5.0`; structured-agents-v2: local path |
| template-py trunk `testee_ref` default | `v0.5.1` |
| copier answers (`.copier-answers.yml`) `testee_ref` | `v0.5.1` in all 15 py repos; `_commit v0.5.0` of template-py |
| Central skill text | 0.5.0 (stale) |
| RepoMan test fixtures | `REPOMAN_TESTEE_VERSION=0.5.0` (stale) |

RepoMan pin in the fleet (`devenv.lock` and `devenv.yaml`): **v0.12.1** in 14 repos. Talkee, forgelab, nix-* use local paths. Mnemonix and the nix-* repos have no tag. RepoMan trunk is **0.13.0**, template-py default `repoman_ref: v0.13.0`, so the fleet lags by one release (V). `.copier-answers.yml` `repoman_ref` is v0.12.0 for several repos while their `devenv.yaml` says v0.12.1 (V: answers drift from yaml).
Because `getFlake` with a tag ref is not locked, a re-tag or cache expiry could change the module without a lock diff (I). Both module and wrapper package come from one tag, so they stay in step (V: comment and code in every file).

## 6. template-py trunk snapshot (V, `/tmp/tw-trunk/template-py`)

`template/devenv.nix.jinja`:
- `testeeFlake = builtins.getFlake "git+https://github.com/Bullish-Design/testee?ref=refs/tags/{{ testee_ref }}"`; `imports = [ testeeFlake.devenvModules.default ]`; `repoman.enable = true`; `testee.package = testeePackage`.
- `testee.checks`: `ruff`, `ruff-format` (profiles quick+full), `ty` and `pytest` (full). Tools are absolute paths in `${config.devenv.state}/venv/bin`. `pytest` writes `$TESTEE_RUN_DIR/pytest.junit.xml`. Parsers are `ruff-json` and `junit-xml`.
- `tasks."base:check".exec` = `cd "$DEVENV_ROOT"; testee check ruff ruff-format ty`.
- `tasks."base:test".exec` = `cd "$DEVENV_ROOT"; testee check pytest`.
- No `repoman:test`, no `enterTest` in the file. The header comment says RepoMan wires `repoman:test` and `repoman:test:ci`, and Testee's module sets `enterTest`.
- `testee` is found through `PATH` (host `~/.nix-profile/bin`). The template does not name `REPOMAN_TESTEE_HOST_BIN`.

`copier.yml`: question `managers` (multiselect copy/git/test, default all three), `repoman_ref` default `v0.13.0`, `testee_ref` default `v0.5.1`, comment "The project's uv graph does not carry testee".
`copyroom.yml` template `py` checks (all `grep`/`test`):
- must contain `"base:check"`, `"base:test"`, `testee check ruff ruff-format ty`, `testee check pytest`, `testee.package = `, `testee.checks = `, parsers `ruff-json` and `junit-xml`;
- tag regex `testee[?]ref=refs/tags/v0[.][5-9]`; RepoMan tag regex `v0[.](1[3-9]|[2-9])`;
- **forbid** `"repoman:test` and `enterTest *=` in `devenv.nix`;
- forbid `testee` in `pyproject.toml` deps, `[tool.testee`, `testee.t*` files, removed flags (`verify --mode`, `--tool`, `rerun-failures`, `list-runs`), vendomat/mkForce, local `path:`/`git+file:` in `devenv.yaml`;
- require `.testee/` in `.gitignore`.
- `template/.repoman/project.toml.jinja` renders `managers = [...]` from the answers.
`template/AGENTS.md` and `README.md.jinja` tell agents to run `testee verify --full`, `testee check <id>`, `testee report`, `testee doctor`.

## 7. Findings worth acting on

1. **Two shapes in the fleet.** Template shape (`testee check ...` in `base:*`) vs older shape (`base:*` after raw `uv run ruff/pytest`). Thirteen repos have a Testee gate that `base:check`/`base:test` bypass (V).
2. **`repoman:test` is dead weight in the fleet.** Only RepoMan and scopeman call it. The template forbids calling it. Skills and header comments still advertise it (V).
3. **Stale header comments.** 13 fleet files say RepoMan wires `enterTest`. RepoMan stopped in 0.12.1; Testee's module sets it (V).
4. **Two `enterTest` writers collide in places.** fornix and loci-core set their own `enterTest`; devenv joins the values, so `devenv test` runs both Testee's full gate and the local command (I, from devenv's join semantics cited in `testee.nix` header).
5. **Host Testee is an imperative profile install.** Not declared in nix-meta; no rollback, and the version can drift from repo pins (V that it is imperative; I that drift is a risk).
6. **Host RepoMan module is stale** (v1 wiring, `--mode`). Inert now because no importer has `test` on its roster (V).
7. **Stale version strings:** central testee skill (0.5.0), RepoMan test fixtures (0.5.0), `testee/.venv` (0.3.0), devman `uv.lock` (v0.5.0), router skill text "fix lint/format, or rerun failures" in 14 fleet `.agents/skills/repoman/SKILL.md` (V: `grep`; trunk `registry.py` text is already updated to "verify code health and review the latest report").
8. **Doctor interaction** (I): RepoMan's `checks.py` compares `testee --version` on `REPOMAN_TESTEE_HOST_BIN` with `REPOMAN_TESTEE_VERSION` derived from `testee.package.name`. This works only for repos that set `testee.package`. The 4 roster-`test` repos without RepoMan import are not affected.
9. **Gitman wiring.** 8 repos set `verify = ["testee","verify","--full"]` in `gitman.toml` (agentman, argentic, fornix, inferference, loci-core, mancore, shellij, vendomat; V). gitman 0.12 is work-only (`gitman work`), so this key may be unread now (I; U whether any tool reads it).

## 8. Unknowns

- Which flake revision built system generation 152 and where per-user gitman 0.12.1 is declared (U).
- Whether any tool still reads `gitman.toml` `verify` (U).
- Whether `devenv test` in fornix/loci-core runs the gate twice in practice (I only, not run; no devenv shells entered).
- Fleet `devenv.lock` files may be stale versus a fresh eval; not evaluated (U).
