# RepoMan current state: the `test` manager and Testee

Source: trunk snapshot `/tmp/tw-trunk/repoman` (repoman efa1e92c, version 0.13.0;
`pyproject.toml:5`). Testee facts come from `git show 1c139ecb:...` in
`/home/andrew/Documents/Projects/testee` (Testee 0.5.1; `src/testee/__init__.py`).
All paths below are relative to `/tmp/tw-trunk/repoman` unless noted.

Labels: `verified` = read in code or a command; `inferred` = my reasoning from
verified facts; `unknown` = I could not establish it.

## 1. The design in one paragraph

- The `test` manager has key `test`, command `testee`, install model `path`.
  (verified: `src/repoman/registry.py:99-110`)
- RepoMan installs nothing. The host profile (`$HOME/.nix-profile`) holds the
  `testee` wrapper. (verified: `CHANGELOG.md:56-57`, `README.md:160-162`)
- The consumer pins Testee in Nix. One pinned flake supplies both the devenv
  module and the wrapper package. (verified: `devenv.nix:6-15`,
  `tests/consumer-example/devenv.nix:6-12`)
- RepoMan reads the pinned package name to learn the required version, then
  checks that the host wrapper reports exactly that version.
  (verified: `modules/managers/testee.nix:28`, `src/repoman/checks.py:264-298`)
- Two tasks call the host wrapper. (verified: `modules/managers/testee.nix:34-35`)

## 2. CHANGELOG reasoning, verbatim

Entry 0.12.0 (`CHANGELOG.md:41-60`), the full intro and bullets that cover the design:

> ## 0.12.0 — 2026-10-09 — Testee 0.5.0 host wrapper
>
> Testee 0.5.0 runs checks that the consumer declares in Nix. Its wrapper starts before
> devenv and opens one clean shell. The `test` manager follows that model.

> - **The `test` manager runs the host `testee` wrapper.** `repoman:test` runs
>   `testee verify`. `repoman:test:ci` and `enterTest` run `testee verify --full`. The
>   wrapper path is `REPOMAN_TESTEE_HOST_BIN`, default `$HOME/.nix-profile/bin/testee`.
>   The v0.4 flags (`--mode quick`, `--mode ci`) and the venv-installed `testee` are gone.
> - **RepoMan ships no default checks.** The consumer imports Testee's devenv module, sets
>   `testee.package` and declares `testee.checks`. The module exports
>   `REPOMAN_TESTEE_VERSION` from the pinned package name, so `testee.package` is required
>   when the `test` manager is on the roster.
> - **Testee is no longer a uv dependency of the consumer.** `Manager.install` for `test`
>   is `"path"`. The host profile installs Testee.
> - **`repoman doctor` checks the wrapper.** The rows check that the configured binary
>   exists, that it matches `PATH`, and that its version equals the pinned package.
> - **The consumer fixture** under `tests/consumer-example/` pins the Testee flake and
>   declares its own checks.

Entry 0.12.1 (`CHANGELOG.md:32-39`):

> ## 0.12.1 — 2026-10-10 — one full gate in `devenv test`
>
> - **RepoMan no longer sets `enterTest` for the `test` manager.** Testee's own devenv
>   module sets `enterTest` to `testee verify --full`, and devenv joins both values. The
>   full gate ran twice under `devenv test`. Now it runs once. `repoman:test`,
>   `repoman:test:ci` and `REPOMAN_TESTEE_VERSION` do not change.

Gaps in the CHANGELOG reasoning:

- (verified) No CHANGELOG entry explains the `enterShell` PATH rewrite
  (`modules/devenv.nix:139-140`). `grep -n HOST_BIN CHANGELOG.md` hits only line 50.
  The only written reason is the code comment at `modules/devenv.nix:136-138`
  (quoted in section 4).
- (verified) No CHANGELOG entry says why the version check uses exact equality.
  The wording is "its version equals the pinned package" (`CHANGELOG.md:58-59`).
- (verified) The 0.12.0 bullet says `enterTest` runs `testee verify --full`.
  0.12.1 reversed that. The 0.12.0 bullet is now wrong as history of the current state.
- (verified) The 0.11.0 entry (`CHANGELOG.md:103-104`) says `gate` runs
  `testee verify --mode ci`. That flag is gone; `devenv.nix:165` now runs
  `testee verify --full`.

## 3. Nix module: `modules/managers/testee.nix`

What it is for: wires the `test` manager into devenv. It activates only when
`repoman.enable` is true and `"test"` is in the roster (`testee.nix:23`, verified).

Line map (all verified):

| Lines | Content | Purpose |
|---|---|---|
| 1-17 | Header comment | States the model, "RepoMan sets no `enterTest`", and that the consumer must set `testee.package` and `testee.checks`. |
| 19 | Args `{ lib, config, repomanManagers, ... }` | `repomanManagers` comes from `_module.args` (`modules/devenv.nix:119`). |
| 23 | `enabled = cfg.enable && builtins.elem "test" repomanManagers` | Roster gate. |
| 24 | `testeeBin = ''"''${REPOMAN_TESTEE_HOST_BIN:-$HOME/.nix-profile/bin/testee}"''` | Shell expansion evaluated when the task runs. Default is the user Nix profile. |
| 28 | `env.REPOMAN_TESTEE_VERSION = lib.removePrefix "testee-" config.testee.package.name` | Exports the required version. |
| 34 | `"repoman:test".exec = cd "$DEVENV_ROOT" && ${testeeBin} verify` | Quick gate. |
| 35 | `"repoman:test:ci".exec = ... verify --full` | Full gate. |

Facts about the version export (line 28):

- (verified) Testee's package derivation is named `testee-0.5.1`
  (testee `nix/testee-package.nix`, `pkgs.runCommand "testee-0.5.1"`). The prefix
  strip yields `0.5.1`.
- (verified) `testee --version` prints `testee 0.5.1` (testee
  `src/testee/runner/cli.py:229`, `version=f"testee {__version__}"`).
- (inferred) The derivation name is a convention, not an API. If Testee renames the
  derivation, the `removePrefix` leaves `testee-...` in place, `REPOMAN_TESTEE_VERSION`
  carries a wrong string, and `version:test` fails. No test covers that
  (`tests/test_modules_nix.py:12` only checks the source text).
- (inferred) A consumer with `test` on the roster but no Testee module imported gets
  a Nix evaluation error, because `config.testee.package` has no definition. I did not
  run `devenv` to confirm the exact message.

Who reads it: devenv at evaluation; the task runner for `repoman:test*`; `checks.py`
through `REPOMAN_TESTEE_VERSION`.

What breaks if removed:

- (verified) No `repoman:test` / `repoman:test:ci` tasks. `devenv.nix:182`
  (`"base:test".after = [ "repoman:test" ]`) points at a task that no longer exists.
  `README.md:189` and `AGENTS.md:36` name the task.
- (verified) `REPOMAN_TESTEE_VERSION` is unset, so `version:test` fails with
  "REPOMAN_TESTEE_VERSION is missing" (`checks.py:269-275`).
- (verified) The template-py scenario check `! grep -Eq '"repoman:test|enterTest *='
  devenv.nix` (`/tmp/tw-trunk/template-py/copyroom.yml:28`) assumes RepoMan supplies
  these tasks, so consumers do not define them.

## 4. Meta-module: `modules/devenv.nix`

- `:80` imports `./managers/testee.nix` unconditionally. (verified)
- `:30` `allManagers = [ "copy" "git" "test" ]`; `:75` default roster. (verified)
- `:123` `env.REPOMAN_MANAGERS` carries `test` when on the roster. The Python CLI
  reads it. (verified)
- `:135-144` `enterShell`. Quoted:

  ```
  # Tasks run this enterShell block, but do not prepend the consumer venv.
  # Keep app tools available, then put the host Testee profile before packages
  # added by devenv. The doctor and manager task use this same wrapper.
  export REPOMAN_TESTEE_HOST_BIN="${REPOMAN_TESTEE_HOST_BIN:-$HOME/.nix-profile/bin/testee}"
  export PATH="${config.devenv.state}/venv/bin:$(dirname "$REPOMAN_TESTEE_HOST_BIN"):$PATH"
  ```
  (verified: `modules/devenv.nix:136-140`)

What each line does (verified unless marked):

- Line 139 exports `REPOMAN_TESTEE_HOST_BIN` as a shell variable, not through
  `env.`. It is set only where `enterShell` runs.
- Line 140 puts two directories at the front of `PATH`: the consumer venv bin, then
  `dirname $REPOMAN_TESTEE_HOST_BIN` (by default `~/.nix-profile/bin`).
- (verified) The second directory is the whole host profile bin dir. Every tool in
  it (repoman, copyroom, gitman, jj, and others) moves ahead of devenv `packages`,
  not only `testee`.
- Why it exists (inferred from the comment and from Testee's module): Testee's own
  module sets `packages = [ package ]` (testee `nix/testee.nix:65`). That puts the
  store copy of `testee` on the devenv `PATH`. The rewrite makes the host copy win.
  The module also keeps the venv bin first so app tools resolve.
- Why it is needed for the doctor (inferred): `checks.py:216-226` fails when
  `which testee` differs from the configured binary. Without the rewrite the two
  could differ.
- (inferred) When the host profile holds the same pinned package, both paths resolve
  (`Path.resolve()`, `checks.py:218`) to the same store file. The shadow check then
  passes even without the rewrite. The rewrite matters only when the host and the
  pin differ, and in that case the `version:test` row fails anyway.
- (verified) The default path `$HOME/.nix-profile/bin/testee` appears in three
  places: `testee.nix:24`, `modules/devenv.nix:139`, and `README.md:169`.
  CHANGELOG line 50 is a fourth statement of it. No single source of truth.
- `:132` `repoman-sync` script and `modules/scripts/repoman-sync.sh:40` run
  `repoman install-skills`. No Testee content. (verified)
- `:21-24` header comment says the host profile puts `copyroom`, `gitman` and
  `testee` on `PATH` and "Testee starts outside devenv and opens a clean shell for
  the checks." (verified)

What breaks if the PATH rewrite is removed:

- (verified) `tests/test_modules_nix.py:35-41` fails. It asserts the exact strings
  `export REPOMAN_TESTEE_HOST_BIN=`, `$(dirname "$REPOMAN_TESTEE_HOST_BIN")` and the
  venv prefix.
- (inferred) A shell that imports Testee's module would resolve `testee` to the store
  copy. The `installed:test` row would then fail only if that copy differs from the
  host copy. Bare `testee verify --full` in `devenv.nix:165` (`gate`) would run the
  store copy instead of the host copy.

What breaks if only the venv-bin half is removed: (unknown) not traced; the comment
says "Keep app tools available".

## 5. Registry: `src/repoman/registry.py`

- `Manager` dataclass fields `binary_env` (`:53`, doc `:36-37`) and `version_env`
  (`:54`, doc `:38`). Both default to `""`. (verified)
- `REGISTRY["test"]` (`:99-110`): key `test`, command `testee`, tier `core`,
  summary "Verification (pytest / ruff / ty)", `status=["report"]`,
  `route_when="verify code health and review the latest report"`,
  `binary_env="REPOMAN_TESTEE_HOST_BIN"`, `version_env="REPOMAN_TESTEE_VERSION"`.
  `doctor` keeps its default `["doctor"]`. `skill` defaults to `testee`
  (`:57-58`). (verified)
- `SPINE` (`:70-74`): `("verify", "test")`. The router renders the `verify` phase only
  when `test` is enabled. (verified)
- `DEFAULT_MANAGERS = ["copy","git","test"]` (`:113`). (verified)
- `binary_env` and `version_env` are used only for `test`. Only `checks.py` reads
  them. (verified: `grep -rn "binary_env\|version_env" src`)
- `Manager.doctor` and `Manager.status` have no reader in `src/`.
  (verified: `grep -rnE "\.doctor|\.status" src` returns nothing; the CLI docstring
  at `cli.py:202-203` says doctor does not run manager doctors.) The only user of
  `status` is the test `tests/test_registry.py:85`. So `status=["report"]` is data
  with no consumer in RepoMan. (inferred: it is a leftover from the aggregating CLI
  that 0.10.0 dropped; CHANGELOG title says "drop the aggregating CLI".)
- What breaks if `binary_env` is removed: `manager_binary` falls back to
  `shutil.which`; the shadow check can no longer compare against the task binary;
  `tests/test_registry.py:83`, `tests/test_checks.py:83` fail. (verified for the
  tests, inferred for behaviour)
- What breaks if `version_env` is removed: `_version_check` returns `None`
  (`checks.py:267-268`), so `version:test` vanishes and `tests/test_checks.py:153-188`
  and `tests/test_cli.py:83-89` fail. (verified)

## 6. Doctor: `src/repoman/checks.py`

Module docstring `:6-9, :17-19` states the model. (verified)

`manager_binary` (`:129-143`):

- For a `path` manager: use `os.environ[binary_env]` if set and non-empty, else
  `shutil.which(command)`. (verified)
- For a `uv` manager: `<DEVENV_STATE>/venv/bin/<command>`. Unused by any shipped
  manager. (verified: all three registry entries use `path`; `tests/test_registry.py`
  asserts it.)

`_installed_check` for path managers (`:204-231`), in order (verified):

1. Fail "`<binary>` missing or not executable" or "`testee not on PATH`" (`:207-209`).
2. Fail "`testee is missing from PATH; add <dir>`" when `binary_env` is set and
   `which` finds nothing (`:210-215`).
3. Fail "tasks use `<binary>`, but PATH resolves testee to `<on_path>`" when the
   resolved paths differ (`:216-226`). This is the "shadow detection". It resolves
   symlinks on both sides.
4. Else OK with the binary path (`:227-231`).

`_version_check` (`:264-298`), in order (verified):

1. Return `None` when `version_env` is empty (`:267`).
2. Fail if `REPOMAN_TESTEE_VERSION` is missing: "`... is missing — import the pinned
   Testee module`" (`:269-275`). The message names Testee, so the generic mechanism
   holds a Testee-only string.
3. Fail if the binary is missing (`:276-280`).
4. Run `<binary> --version`, 10 s timeout (`:282`). Fail on OS error, timeout, or
   non-zero exit (`:283-290`).
5. Match `re.fullmatch(r"testee\s+(\S+)", output)` (`:292`). The pattern hard-codes
   the word `testee`. Fail "unrecognized version" otherwise (`:293-294`).
6. Exact string equality `actual == required` (`:296`). Detail:
   "`<binary> reports X; pinned package requires Y`" (`:297`).

Consequences (verified unless marked):

- Any version difference fails the row, including a newer host wrapper. No
  minimum-version or range mode exists.
- (inferred) Any change in `testee --version` output format breaks the row.
- `run_self_check` loop (`:361-367`) emits `installed:test` and `version:test` for
  every enabled manager that has them.
- `interface:git` (`:301-323`, called only when `m.key == "git"` at `:366-367`) checks
  gitman's usage text for `{work}` and `jj >= 0.46.0` (`:321`). There is no
  `interface:test` row. RepoMan checks nothing about Testee's CLI surface
  (for example that `verify`, `verify --full` and `report` exist) beyond `--version`.
  (verified)
- `provisioned:test` is never emitted because `nix_input` is empty (`:378-380`).
  (verified)
- `skill:test:defers` (`:405-419`) reads `<skills_dir>/testee/SKILL.md` if present
  and warns when it does not defer to the repoman skill. (verified)
- `roster:unknown-manager` (`:424-443`) is not test-specific. (verified)

Who reads the rows: `repoman doctor` (`cli.py:215-229`) prints them or emits JSON;
exit code 1 on any `fail`. Agents and the router skill read the output.
(verified for CLI; inferred for agents)

What breaks if removed: see test list in section 9.

## 7. Router generation

- `src/repoman/skills.py:95` builds each table row from `m.key`, `m.command`,
  `m.skill`, `m.route_when`. For `test` the row is `| verify code health and review
  the latest report | test | testee | testee |`. (verified)
- `skills.py:87` renders a row only when `<skills_dir>/testee/SKILL.md` exists.
  Without the skill link the `test` row is absent but the `verify` spine phase still
  appears. (verified)
- `src/repoman/templates/entrypoint.SKILL.md.j2:13` says "Never invoke pytest / ruff /
  copier directly ... Go through the manager (or `repoman`)." `:47-48` set the laws
  "Verify before you integrate" and "Never integrate on red". The template does not
  name `testee` or any command; the table supplies it. (verified)
- Contradiction (verified): `devenv.nix:58-62` defines a `test` script that runs
  `pytest "$@"` directly, and `devenv.nix:60-77` defines `format` and `lint` scripts
  that run `ruff` directly. The router tells agents not to do that. This is in
  RepoMan's own dev shell only.
- `src/repoman/devman/check.py:58-68`: `expected_skills` adds the `testee` skill when
  `test` is in the roster. That drives `skill:tool-shipped`. A missing link is `warn`,
  never `fail`. (verified)
- `modules/scripts/repoman-sync.sh` has no Testee content. (verified)

Who reads the router: agents in the repo. What breaks if the `test` registry entry
or `route_when` is removed: no `verify` row and no `verify` phase; agents lose the
only pointer to `testee`. (inferred)

## 8. Docs, fixtures and the dev shell

| File:line | Says | Status |
|---|---|---|
| `devenv.nix:3-15` | Pins Testee v0.5.1 with `builtins.getFlake "git+https://github.com/Bullish-Design/testee?ref=refs/tags/v0.5.1"`, imports `devenvModules.default`, sets `testee.package`. | verified |
| `devenv.nix:12-14` | "the HOST also runs the same tagged wrapper from `nix profile` (fleet v2 pattern)". Nothing in the repo enforces that the host tag equals `v0.5.1` except the doctor row. | verified |
| `devenv.nix:16-35` | Four checks: ruff, ruff-format, ty, pytest. `uv run --no-sync` inside a bash argv. | verified |
| `devenv.nix:156-167` | `gate` script runs `scripts/check-fleet-lock.py --rev HEAD` then bare `testee verify --full`. It uses `PATH`, so it relies on the `enterShell` rewrite. | verified; reliance inferred |
| `devenv.nix:174-182` | `base:test` runs after `repoman:test`. Comment says `repoman:test` is "defined by the testee manager module (`testee verify`)". | verified |
| `devenv.yaml` | No Testee input. Testee arrives by `builtins.getFlake` in `devenv.nix`. The same holds for `tests/consumer-example/devenv.yaml`. | verified |
| `tests/consumer-example/devenv.nix:6-15` | Same pin form; no `testee.checks` declared. | verified |
| `pyproject.toml:31-34` (dev group) | `dev = ["pytest-cov>=5", "ty"]`, no `testee`; comment "Testee's wrapper is installed by the host profile." | verified |
| `.gitignore:56-57, 227` | Ignores `.testee/`. | verified |
| `README.md:13` | Table row for testee. | verified |
| `README.md:144-148` | `gate` runs `testee verify --full`. | verified |
| `README.md:160-169` | "Manager installation": host profile, clean shell, same pinned source, doctor check, `REPOMAN_TESTEE_HOST_BIN` override. | verified |
| `README.md:189` | "Test verdict: `testee verify` (the `repoman:test` task)." | verified |
| `README.md:215-216` | `testee report` reads the latest saved report. | verified |
| `README.md:226-227` | Doctor table rows `installed:<key>`, `version:test`. | verified |
| `AGENTS.md:36` | `devenv tasks run -v base:test    # repoman:test`. The only Testee line in AGENTS.md. | verified |
| `CONCEPT.md:6-7` | Says "RepoMan installs no manager commands. The host profile puts them on `PATH`, except testee, which the repo declares." | verified text; STALE (contradicts `CONCEPT.md:72` and 0.12.0) |
| `CONCEPT.md:98-100` | Says `pyproject.toml` "declares testee under `[dependency-groups] dev`". | verified text; STALE (`pyproject.toml:35` has none; `tests/test_modules_nix.py:91` forbids it) |
| `CONCEPT.md:26, 72, 140, 224-226, 265-273, 355` | Current model: host wrapper, pinned Nix package, doctor version check. | verified |
| `CONCEPT.md:224-226` | Abandoned `repoman verify`/`save`/`release` ideas ("testee ci"). | verified; history |
| `CONCEPT.md:358` | "verify the closure, then generate the router skill". | verified; STALE (the script reads no closure) |
| `docs/SKILLS.md:90` | Route text "verify code health, fix lint/format, or rerun failures". Registry says "verify code health and review the latest report". | verified; STALE |
| `docs/SKILLS.md:151` | Open question on `template-test` vs `testee verify`. | verified |
| `docs/AGENT-FILES.md:5, 49` | Names `testee` skill in the expected link set. | verified |
| `SPIKE.md` (12 hits) | Describes testee as a per-repo uv dev dependency and `repoman doctor` running `testee doctor`. | verified; STALE (history) |
| `.scratch/projects/0xx/**` | Many hits, mostly v0.4 `--mode` era and the retired Vendomat closure. | verified; history, not current |

External consumers of RepoMan's test wiring (outside the repo, verified):

- `/tmp/tw-trunk/template-py/README.md:82-90` says the `dev` group must not carry
  `testee` because "a venv copy would shadow it (`repoman doctor` row
  `installed:test`)", and that RepoMan wires `repoman:test` and `repoman:test:ci`.
- `/tmp/tw-trunk/template-py/template/devenv.nix.jinja:3-10, 15-19` pins Testee with
  `testee_ref` (default `v0.5.1`) and sets no `enterTest`.
- `/tmp/tw-trunk/template-py/copyroom.yml:28` asserts the rendered `devenv.nix`
  contains no `"repoman:test` and no `enterTest =`.

## 9. Tests that pin the current design

All verified by reading the files.

`tests/test_checks.py`:

- `:28-49` `host` fixture. Builds a fake host bin with a `testee` that prints
  `testee 0.5.0`. Sets `REPOMAN_TESTEE_HOST_BIN` and `REPOMAN_TESTEE_VERSION=0.5.0`.
  Patches `shutil.which`. The fixture version (0.5.0) differs from the real pin
  (0.5.1); this is harmless because both sides come from env vars.
- `:81-84` `manager_binary(REGISTRY["test"]) == host.bin / "testee"`.
- `:153-157` version matches, so `installed:test` and `version:test` are OK.
- `:160-172` shadow on PATH, so `installed:test` fails with "tasks use".
- `:175-181` host 0.4.0 vs pin 0.5.0, so `version:test` fails with "reports 0.4.0".
- `:184-188` missing `REPOMAN_TESTEE_VERSION`, so fail with "is missing".
- `:68-70` `test_self_check_reads_no_vendomat_closure` asserts no `toolchain:`,
  `lock:` or `version:` rows for the `git` manager. This forbids a generic
  `version:` row for managers without `version_env`.
- No test covers these branches (verified: grep over `tests/`): "is missing from PATH"
  (`checks.py:210-215`), "cannot read version" (`:278-284`), non-zero `--version`
  exit (`:285-290`), "unrecognized version" (`:293-294`).

`tests/test_cli.py`:

- `:10-33` `managers` output contains `testee` for rosters with `test`.
- `:36-69` `_healthy_repo` helper sets the same env vars.
- `:72-80` missing host binary, so `FAIL installed:test`, exit 1.
- `:83-89` version mismatch, so `FAIL version:test`, "pinned package requires 0.5.0".
- `:114-117`, `:133-152` clean roster and skill-link rows for `copy test`.
- `:167-181` unset roster gives defaults; duplicate keys collapse.

`tests/test_modules_nix.py` (reads source text only; it never evaluates Nix):

- `:7-12` no manager module mentions `venvBin`; `testee.nix` contains
  `REPOMAN_TESTEE_HOST_BIN` and `lib.removePrefix "testee-" config.testee.package.name`.
- `:15-21` `testee.nix` has no line starting with `enterTest`, and contains
  `"repoman:test".exec` and `"repoman:test:ci".exec`. This is the 0.12.1 regression guard.
- `:35-41` `modules/devenv.nix` contains the `export REPOMAN_TESTEE_HOST_BIN=`
  and `dirname` strings and the venv prefix.
- `:51-55` every manager module mentions `repomanManagers`.
- `:87-97` the dev shell pins Testee with `builtins.getFlake ...v0.5.1` and
  `testee.package = testeeFlake.packages.`; `testee` is absent from the `dev` group.
- Note (inferred): these are string-presence checks. They would not catch a
  semantically wrong PATH rewrite or a broken Nix expression.

`tests/test_registry.py:81-85` pins `binary_env`, `version_env` and `status == ["report"]`.
`tests/test_fleet_shape.py:52` asserts `"testee verify --full" in nix` for the `gate`
script. `tests/test_skills.py:76, 111-125` check the router mentions `testee` and routes
only to skills present on disk. `tests/test_devman.py:60-66, 132-145` check the
`testee` skill is in the expected set for `test`.

## 10. Environment variables, tasks, doctor rows: index

Environment variables:

| Name | Set by | Read by | Notes |
|---|---|---|---|
| `REPOMAN_TESTEE_HOST_BIN` | `modules/devenv.nix:139` (shell `export`, not `env.`) | `testee.nix:24` (task default expansion), `checks.py:137` via `binary_env`, README | Default `$HOME/.nix-profile/bin/testee`. Unset outside a shell where `enterShell` ran. (verified) |
| `REPOMAN_TESTEE_VERSION` | `testee.nix:28` (`env.`) | `checks.py:269` via `version_env` | Set only when `test` is on the roster. (verified) |
| `REPOMAN_MANAGERS` | `modules/devenv.nix:123` | `cli.py:56-60`, `checks.py:93` | Contains `test`. Doctor context gate. (verified) |
| `REPOMAN_SKILLS_DIR` | `modules/devenv.nix:127` | `cli.py:49` | Router location. (verified) |
| `TESTEE_RUN_DIR` | Testee (external) | `devenv.nix:31` pytest check | (verified use; setter inferred from the name) |
| `__NIXOS_SET_ENVIRONMENT_DONE` | Testee module (testee `nix/testee.nix:64`) | bash in the check shell | Not RepoMan's. (verified) |

Tasks: `repoman:test`, `repoman:test:ci` (`testee.nix:34-35`); `base:test` ->
after `repoman:test` (`devenv.nix:182`). Testee's own module adds task
`testee:verify` and `enterTest` (testee `nix/testee.nix:66-67`; verified). Nothing in
the RepoMan repo calls `repoman:test:ci` (verified: only `testee.nix:35`,
`tests/test_modules_nix.py:21`, and template-py docs mention it). Who runs it:
(unknown) external callers such as Dagu groups; `devenv.nix:171-172` mentions a
`base` group in another repo.

Doctor rows for `test`: `installed:test`, `version:test`, `skill:test:defers`,
`skill:tool-shipped` (shared), `skill:entrypoint` (shared). No `provisioned:test`,
no `interface:test`.

## 11. Findings for the design study

1. (verified) Three overlapping mechanisms select the Testee binary: the env var,
   the PATH rewrite, and Testee's own `packages = [ package ]`. Each has its own
   default or check. The doctor reports a conflict; it does not prevent one.
2. (verified) The pin has two homes that must agree: the flake tag in the consumer's
   `devenv.nix`, and whatever the user installed with `nix profile`. Only the
   exact-equality `version:test` row links them.
3. (verified) The version mechanism is generic in name (`version_env`) but Testee-only
   in code (`checks.py:274`, `:292`).
4. (verified) The default host path is stated in four places with no shared constant.
5. (verified) `status=["report"]` and `doctor=["doctor"]` for `test` are unused by the
   code in `src/`.
6. (verified) `CONCEPT.md:6-7`, `:98-100`, `:358` and `docs/SKILLS.md:90` contradict
   the current design.
7. (unknown) Whether a running `devenv shell` sets `PATH` so that
   `which testee` equals `REPOMAN_TESTEE_HOST_BIN` on a NixOS host. I read code only
   and ran no shell.
8. (unknown) Whether any consumer outside the five snapshots sets
   `REPOMAN_TESTEE_HOST_BIN` to a non-default value.
