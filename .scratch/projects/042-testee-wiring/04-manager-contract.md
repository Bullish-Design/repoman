# 04 Manager contract: copy / git / test

Source: snapshots under /tmp/tw-trunk. Paths are relative to it.
Labels: V = verified (read in the file), I = inferred, U = unknown.
Short names: NIX-C = repoman/modules/managers/copyroom.nix, NIX-G = .../gitman.nix,
NIX-T = .../testee.nix, DEV = repoman/modules/devenv.nix, REG = repoman/src/repoman/registry.py,
CHK = repoman/src/repoman/checks.py.

## 1. What RepoMan defines per manager

### copy (copyroom)
- Packages: `pkgs.git`, `pkgs.gnupatch`. NIX-C:21. V. The CLI shells out to both (NIX-C:6-10). V.
- Task: `repoman:template:status` runs `copyroom status`. NIX-C:25. V.
- Env vars: none. V (no `env.` in NIX-C).
- enterShell: none in the module. V.
- Options: none. Gate is `builtins.elem "copy" repomanManagers`. NIX-C:15. V.
- Binary: host PATH, bare name `copyroom`. NIX-C:24, REG:84. V.
- REG fields: key copy, command copyroom, tier core, doctor ["doctor"], status ["status"],
  route_when set, install default "path", no binary_env, no version_env, no nix_input. REG:82-90. V.

### git (gitman)
- Packages: `pkgs.git` only. NIX-G:18. V.
- Tasks: none. V. A hermetic flake check pins this: `gitman-adds-git-only` asserts one package, no tasks,
  no Rust. repoman/flake.nix:93-152. V.
- Env vars, enterShell, options: none. V.
- Binary: host PATH. jj also from host profile. NIX-G:7-8. V.
- REG fields: command gitman, tier core, `doctor=None`, status None, route_when set,
  no binary_env, no version_env. REG:91-98. V.

### test (testee)
- Packages: none from RepoMan. NIX-T has no `packages`. V. Testee's own module adds `[ package ]`
  (testee/nix/testee.nix:65). V.
- Tasks: `repoman:test` runs `$REPOMAN_TESTEE_HOST_BIN verify`; `repoman:test:ci` runs `verify --full`.
  NIX-T:34-35. V.
- Env var: `REPOMAN_TESTEE_VERSION` = `config.testee.package.name` minus `testee-`. NIX-T:28. V.
  This line reads `config.testee.package`. Without the Testee module imported, eval fails. I.
- No `enterTest` by design, to avoid a double gate. NIX-T:8-10. V.
- Binary: `${REPOMAN_TESTEE_HOST_BIN:-$HOME/.nix-profile/bin/testee}`. NIX-T:24. V.
- REG fields: command testee, tier core, doctor default ["doctor"], status ["report"],
  `binary_env="REPOMAN_TESTEE_HOST_BIN"`, `version_env="REPOMAN_TESTEE_VERSION"`. REG:99-110. V.

### Shared (DEV)
- Roster comes from `.repoman/project.toml`, default `copy git test`. DEV:75. V.
- Exports `REPOMAN_MANAGERS` and `REPOMAN_SKILLS_DIR`. DEV:123, 127. V.
- Script `repoman-sync` generates the router. DEV:130-133. V.
- Exports `REPOMAN_TESTEE_HOST_BIN` for every roster. DEV:139. V.
- Rewrites PATH for every roster: `<state>/venv/bin : dirname(testee host bin) : $PATH`. DEV:140. V.
  It runs even when `test` is not on the roster. I (no gate around the line; `mkIf cfg.enable` only).
- Options: only `repoman.enable`. DEV:110. V.
- Imports all three modules statically; each gates itself. DEV:79-83. V.
- Removed key `doc` is accepted. DEV:35. V.
- shellij is not a manager. RepoMan presence-imports its devenv module. DEV:99. V.

## 2. Python side

Doctor rows (CHK `run_self_check`, 336-421):

| Row | copy | git | test |
|---|---|---|---|
| `installed:<key>` | yes | yes | yes |
| `version:<key>` | skipped (no version_env, CHK:267) | skipped | yes, exact equality (CHK:296) |
| `interface:git` | no | yes (CHK:366-367) | no |
| `uv:<key>` | only if install=="uv"; none is | same | same |
| `provisioned:<key>` | skipped (nix_input empty, CHK:379) | skipped | skipped |
| `skill:<key>:defers` | if skill installed | if installed | if installed |

All V. Plus global rows: `pyproject`, `roster:unknown-manager`, `skill:entrypoint`,
`skill:tool-shipped`, `skill:genome-overlay`. CHK:343, 393; devman/check.py:72-135. V.

`installed:<key>` details (CHK:197-231):
- For `copy` and `git` it resolves `shutil.which(command)` and checks it is executable. V.
- For `test` it resolves `$REPOMAN_TESTEE_HOST_BIN` first. V.
- A set `binary_env` plus a missing PATH entry is a `fail`. CHK:210. V.
- A PATH binary that resolves differently from the task binary is a `fail` (`shadowed`). CHK:216-226. V.
- Only `test` can trigger the shadow `fail` in practice. It is the only entry with `binary_env`.
  For `copy`/`git`, `binary == which(command)`, so shadow cannot occur. I.

`version:test` (CHK:264-298):
- Runs `<bin> --version`, requires the form `testee <ver>`, and compares to the pinned package. V.
- The regex is hard-coded to `testee` inside a field named generically. CHK:292. V.

`interface:git` (CHK:301-323):
- Checks `gitman --help` matches `usage: gitman .*{work}`. V.
- Checks `jj version` is at least 0.46.0. V.
- This is a minimum, not an exact pin. V.
- It is called by `m.key == "git"`, not by a registry field. CHK:366. V.

Dead registry fields:
- `Manager.doctor`, `Manager.status` and `Manager.nix_input` have no readers except `nix_input` in CHK:379.
  `cli.py` reads only `key`, `command`, `tier`, `summary`. V (grep over repoman/src).
- `Manager.package` and `install` matter only for the `uv` model. No manager uses it. V.
- Consequence: `doctor=None` for git and `status=["report"]` for test change no behavior. V/I.
  The docstring says RepoMan aggregates them (REG:1-7). Cli.py:202 says doctor does not run manager doctors. V.

Router generation (skills.py, entrypoint template):
- A row appears only if `<skills_dir>/<m.skill>/SKILL.md` exists. skills.py:87. V.
- Row shape: `route_when | key | skill | command`. skills.py:95; template:35-39. V.
- Order: spine `test`, `git`, then activity `copy`. skills.py:24; REG:70-78. V.
- Spine text is `change → verify → integrate`. `verify` renders only if `test` is on the roster. V.
- Skill name defaults to `command`. REG:57-58. So skill names are `copyroom`, `gitman`, `testee`. V.
- Router has no manager-specific text. All three get one row. V.
- Skills come from the devman pool (`~/.config/devman/...`), not from the tools. devman/check.py:4-13. V.
  No sibling repo ships a SKILL.md outside test fixtures. V (find over copyroom, gitman, testee).
- The `copy` entry also expects `copyroom-adopt`, `copyroom-template-edit`. check.py:51, 67. V.
- Template says "Never invoke pytest / ruff / copier directly" and "Use native jj". Template:13. V.

## 3. Sibling side

| | copyroom 0.8.0 | gitman 0.12.1 | testee 0.5.1 |
|---|---|---|---|
| flake.nix | none (V: no file) | yes: packages gitman, jujutsu-bin, overlay, checks (flake.nix:39-94) | yes: packages.testee, devenvModules.default (flake.nix:12-16) |
| Devenv module exported | `modules/copyroom.nix`, imported as `flake: false` input (copyroom.nix:1-14) | `nix/gitman.nix` is dev-only (own lint/test/publish tasks), not for consumers (gitman.nix:1-5) | `nix/testee.nix`, consumer-facing (README:34-36) |
| Module adds | `copyroom` package and `pkgs.jujutsu` (copyroom.nix:44) | n/a | `testee.package`, task `testee:verify`, `enterTest`, `__NIXOS_SET_ENVIRONMENT_DONE` (testee.nix:56-67) |
| Module options | `copyroom.enable`, `copyroom.package` | none | `testee.package/checks/services/manifestJson` |
| Package | `nix/` buildPythonApplication, version string "0.7.7" (copyroom-cli.nix:14) vs pyproject 0.8.0 | buildPythonPackage, reads version from pyproject (package.nix:20-24); runs real `gitman work` at install check (package.nix:58-84) | `runCommand "testee-0.5.1"` shell wrapper with hard-coded name (testee-package.nix:6) |
| `--version` | `copyroom <ver>` (cli.py:117-134) | none: parser has no version flag (gitman cli.py:12-20) | `testee <ver>` (testee cli.py:229) |
| Own doctor | `doctor` returns templateer, jj, guard (workflow.py:2146-2167) | none | `doctor` prints checks, root, shell guard; exit 2 on probe fail (testee cli.py:207-224) |
| Expected install | host `PATH` (REG:30; DEV:21-24) | host `PATH`, plus the flake's pinned `jujutsu-bin` as the only jj (flake.nix:11-14; package.nix:3-8) | host `nix profile add .#testee` (README:14-17); `~/.nix-profile/bin/testee` (NIX-T:24) |

All V except the "expected install" reading of who runs `nix profile` for copyroom/gitman. The repo says
"the host profile installs them" (CHK:6-9) but names no profile source. U (the machine profile is outside the snapshots).

Other facts:
- The REG comment lists copyroom doctor rows as copier, git, cache, template-source (REG:87).
  The code returns templateer, jj, guard (workflow.py:2159-2166). The comment is stale. V.
- REG:87 says "copyroom 0.6+". No code checks a copyroom version. V.
- RepoMan's NIX-C adds git and gnupatch although copyroom's own module does not. V.
  It also never imports `modules/copyroom.nix`. V (DEV:79-83 imports only managers/*.nix).
  So the copyroom's own module is unused by RepoMan. V.
- gitman's flake says Linux only (flake.nix:18). testee also Linux only (flake.nix:8). copyroom `platforms.all`. V.
- Template-py devenv.nix imports Testee's module and sets `testee.package`, `testee.checks`.
  template-py/template/devenv.nix.jinja:43-63. V. Repoman's own devenv.nix does the same (devenv.nix:6-35). V.
- Both `testee:verify` (testee.nix:66) and `repoman:test` (NIX-T:34) run `verify`. Different flags:
  the first uses `${package}/bin/testee ... --full`, the second the host binary without `--full`. V.

## 4. Contract table

| Contract element | copy | git | test |
|---|---|---|---|
| Command on PATH | `copyroom` | `gitman` | `testee` |
| How found | `which` on PATH | `which` on PATH | `$REPOMAN_TESTEE_HOST_BIN`, default `~/.nix-profile/bin/testee`; PATH made to match |
| Install model | `path` | `path` | `path` (host profile) + pinned Nix package for the version |
| Min vs exact version | none checked | min for jj (>=0.46.0); gitman identified by help shape, no version | exact: `--version` must equal pinned package version |
| Tasks | `repoman:template:status` | none | `repoman:test`, `repoman:test:ci` |
| Env vars | none | none | `REPOMAN_TESTEE_VERSION` (module); `REPOMAN_TESTEE_HOST_BIN` (meta-module) |
| PATH rewrite | none (shared DEV line puts venv and testee dir first) | none | the shared DEV:140 line exists for testee only |
| Extra packages | git, gnupatch | git | none (Testee module adds the wrapper) |
| Options | none | none | none in RepoMan; consumer must set `testee.package` and `testee.checks` |
| Skill | `copyroom` + 2 sub-skills (pool) | `gitman` (pool) | `testee` (pool) |
| Router phase | activity (`birth / converge`) | spine `integrate` | spine `verify` |
| Doctor rows | `installed:copy` | `installed:git`, `interface:git` | `installed:test`, `version:test` |
| Registry doctor/status | doctor, status (unread) | doctor None (unread) | doctor, status report (unread) |
| Devenv module from the tool itself | exists (`modules/copyroom.nix`), RepoMan ignores it | dev-only module; none for consumers | exists, consumer must import; RepoMan reads it (`config.testee.package`) |
| Own `--version` | yes | no | yes |
| Own `doctor` | yes | no | yes |

## 5. Common shape

Every manager: (1) a console script on host PATH, found by bare name; (2) a roster-gated Nix module
under `managers/`; (3) a `Manager` row with command, tier, summary, `route_when`; (4) one
`installed:<key>` row; (5) a pool skill named after the command; (6) one router row.
The Nix module adds only what the CLI shells out to, not the CLI itself. V (NIX-C:19-20, NIX-G:6-9).

## 6. Deviations

| # | Deviation | Verdict | Reason |
|---|---|---|---|
| 1 | test has exact version pin; copy and git have none | Essential in part | Testee ships a wrapper that carries the manifest schema, and the project's `testee.manifestJson` must match the runner (testee.nix:56). The package pin is the right source. Accident: copy and git have no such check although `copyroom` 0.8.0 vs module 0.7.7 already drifts (copyroom-cli.nix:14). I |
| 2 | test needs `binary_env` and a PATH rewrite | Accident of history | Testee starts outside devenv, then opens a clean shell (README:9). That forces the wrapper to run from host, not the dev shell. But `~/.nix-profile/bin` is a path that PATH lookup already finds for the other two. The shadow problem arises only because the same package also sits in devenv `packages` (testee.nix:65). Dropping the `packages = [ package ]` line or the PATH rewrite would remove the need. I |
| 3 | RepoMan reads `config.testee.package` | Essential for the pin, accident for the coupling | The pin has to come from somewhere. It couples RepoMan eval to the Testee module being imported; copy and git have no such coupling. I |
| 4 | Version regex hard-coded to `testee` in a generic function | Accident | `_version_check` is generic by field name only (CHK:292). I |
| 5 | git has `interface:git` (help shape and jj min) | Essential in part | gitman has no `--version` (cli.py:12-20), so help shape is the only probe. The jj minimum is real: `workspace add --colocate` needs 0.46.0 (jj.nix:1-3). Dispatch by `m.key == "git"` (CHK:366) is an accident; a registry field would fit. |
| 6 | git `doctor=None` | Essential | gitman has no doctor command. V. But the field is unread, so the value is moot. |
| 7 | copy has a task, git has none, test has two | Mixed | Tasks exist where the tool has a cheap read-only command (`status`, `verify`). gitman has none. The `repoman:*` names are a convention. Task for test is a duplicate of Testee's own `testee:verify` (testee.nix:66). Accident. |
| 8 | git and copy install by host profile; test also by `nix profile add` plus pinned package | Accident | Same install model in practice; test documents it more exactly. |
| 9 | gitman ships `jujutsu-bin` and asks the host to install it | Essential | Two jj versions on one repo break the op log (package.nix:3-8). RepoMan's `interface:git` checks the result. |
| 10 | copyroom module adds `jujutsu`; RepoMan's copyroom.nix adds git/gnupatch and never imports it | Accident | Two wiring paths for one tool. Neither imports the other. |
| 11 | Dead registry fields (`doctor`, `status`, `nix_input`, `package`, `install="uv"`) | Accident | Left from the earlier approach-B and uv models. CHK:369-391 describes a model no manager uses. |
| 12 | copy is an "activity", others are spine | Essential | Copy has no order in the loop (REG:76-78). |

## 7. Open points (U)
- U: Which file in the machine profile pins the host versions of copyroom, gitman and testee. Not in snapshots.
- U: Whether `devenv tasks run` sees `REPOMAN_TESTEE_HOST_BIN` before the DEV:139 enterShell runs. DEV:136 says tasks run enterShell. I.
- U: Whether `repoman:test` without `--full` is meant to be quick profile. NIX-T:34 vs testee cli.py `verify` help. I (yes).
