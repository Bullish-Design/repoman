# 10 Devil's advocate 2: the "self-launch" hypothesis

Labels: `verified` (code or command cited), `inferred`, `unknown`.
Sources: `/tmp/tw-trunk/{repoman,testee,template-py}`, notes 01, 02, 04, 05, 06, the parent prototype in
`/tmp/tw-launch/testee-src` (read only), and my experiments in `/tmp/tw-da2/`
(`fx` = copy of the Testee self-hosting fixture, `rm` = copy of the RepoMan trunk, `nomod` = project without the module,
`envt` = env-assert probe, `bin/launch.py` = my 50-line stdlib launcher).
Host: devenv 2.4.0, Nix 2.34.7, Linux, host `testee 0.5.1` (`~/.nix-profile/bin/testee`).

## Verdict

Amend. The core holds: the launcher makes the pin run, so host/pin skew cannot change behaviour.
It breaks in one place the hypothesis does not yet cover: the launcher lives after `argparse`.
That placement freezes Testee's CLI grammar forever. Move it before `argparse`, freeze a short contract,
and keep a minimum-version row in RepoMan doctor. The amended text is in section 5.

## 1. Failure modes

### 1.1 Launcher placed after argparse blocks every new verb and flag (the main break)
- `verified` The parent prototype calls `_launch` inside `main()` after `parser.parse_args`
  (`/tmp/tw-launch/testee-src/src/testee/runner/cli.py:311`, `:303-308`).
- `verified` Run: `testee frobnicate` and `testee verify --changed` on the prototype exit 2 with
  `invalid choice` and `unrecognized arguments`, before any launch. A pin that adds a verb or flag cannot be reached through an older host.
- `verified` The CLI grammar already changed once: 0.4 to 0.5 removed `--mode`, `fix`, `rerun-failures`, `--changed`
  (`~/.config/devman/skills/testee/SKILL.md`, step 4). Expect it to change again.
- Fix: the launcher runs first, with stdlib only, and treats argv as opaque (contract F1 below).

### 1.2 Testee developing itself
- `verified` Testee's own `devenv.nix` sets `testee.package = import ./nix/testee-package.nix`, so the pin is the working tree
  (`/tmp/tw-trunk/testee/devenv.nix:7`; the package embeds `${../src}`).
- `verified` Any edit changes `outPath`. Even an untracked file or a `__pycache__` directory changes it
  (I added `src/zz_new.py`, then `src/testee/__pycache__/x.pyc`: two new `outPath` values, git-ignore did not help).
- `verified` Each changed tree costs a cold eval (2.4 to 2.9 s against 0.11 s warm) plus a realise (0.96 s).
- `inferred` Danger: a self-hosting launcher would exec the snapshot of the code under test. A syntax error in the working tree then
  breaks the gate that should report it. Today the stable host runs the gate.
- `inferred` `uv run testee` and `python -m testee` also run a checkout, not a store build. Testee's `pyproject.toml:19` maps the
  console script to `testee.runner.cli:main`, so the launcher must not live in `main()` (tests call `main()` directly).
- Fix: identity comes from `TESTEE_SELF_OUT`, set by the package wrapper. No variable means a dev build. A dev build never launches
  silently: it prints one clear error unless `TESTEE_NO_LAUNCH=1` is set. Testee's own `devenv.nix` sets that variable.
- `verified` The prototype already has `TESTEE_SELF_OUT` and `TESTEE_NO_LAUNCH`
  (`cli.py:114-120`). It only warns, and it warns on every dev call, which is noise (seen in my run). Warn once, or fail.

### 1.3 Stray `testee` that is not a Nix build
- `verified` A venv `testee` exists right now at `/home/andrew/Documents/Projects/repoman/.devenv/state/venv/bin/testee`
  (the parent prototype, `0.5.1+selflaunch`). It first on `PATH` in this session. template-py warns that such copies shadow the host
  (`/tmp/tw-trunk/template-py/README.md:82-90`).
- `inferred` With "warn and continue", a venv or uv copy silently becomes the runner again. Skew returns with no signal.
  "Fail unless `TESTEE_NO_LAUNCH` is set" closes the hole. It also removes the need for RepoMan's shadow check.

### 1.4 Repos that do not import the module
- `verified` `devenv eval testee.package.outPath` in `nomod` exits 1: `attribute ... not found` (after 0.64 s).
- `verified` Today `testee doctor` there also fails: `Cannot evaluate Testee manifest ... attribute ... not found`. So the launcher adds no new failure
  class for `verify`, `check`, `doctor`. It adds a new, better message site.
- `verified` My launcher exits 2 with a one-line cause. For `report` and `doctor` I recommend fail-open (section 1.9).
- `inferred` Module imported but `testee.package` unset gives a different Nix error ("option used but not defined"). Test it before release (`unknown`).

### 1.5 Pin older than the launcher
- `verified` The 0.5.x pin has no launcher and ignores the new variables. The parent's logs show the flow for pins 0.5.0 and 0.5.1
  (`/tmp/tw-launch/logs/calls-pin051.log`: eval of three attributes, exec, second eval of `testee.manifestJson`, `shell.drvPath`, shell launch).
  DA1 ran the same shape with a bash launcher (`06-devils-advocate.md` section 3).
- `verified` Existing consumers pinned at v0.5.1 gain the fix at once. Only the host changes.
- Trade-off, `inferred`: the pin now wins even when old. A host upgrade can no longer fix a bug in a project's pin (for example the 0.5.0
  NixOS PATH bug that 0.5.1 fixed in worker code, `02-testee-architecture.md` section 5). Fixes travel by pin bump, as with the Gradle wrapper.

### 1.6 Pin newer than host: what must stay stable forever
Only the host's reading of the project matters, because a pin never receives anything beyond argv and env. The frozen contract:

- F1 Order. The launcher runs before `argparse`, before any `.testee/` write, before the run lock. Stdlib only (no pydantic import).
- F2 argv. Opaque. The launcher reads only `--root PATH` and `--root=PATH` (exact spelling, up to the first `--`),
  and `-h`, `--help`, `--version` (answered by the host, no launch). It passes the original argv unchanged.
  Check IDs cannot start with `-` (`models.py:9` pattern), so a scan of all tokens is safe.
- F3 Project. `--root` if given, else the nearest `devenv.nix` from cwd. None found: no launch; the host answers or errors.
- F4 Eval. `devenv eval testee.package.outPath testee.package.drvPath [testee.manifestJson]`, cwd = root, env without `DEVENV_*`, `TESTEE_*`,
  `GIT_*` (same strip as `provenance.py:61-63`). Output is a JSON object keyed by those exact paths. `testee.package` is never renamed;
  any rename keeps an alias forever.
- F5 Target. `<outPath>/bin/testee` exists after `nix-store --realise <drvPath>`.
- F6 Exec. `os.execv`, same cwd, same fds, same pid, same argv, env plus `TESTEE_LAUNCHED=<chain of outPaths>`. Pins treat a non-empty
  `TESTEE_LAUNCHED` as "do not launch again". The chain (as in the prototype, `cli.py:127-129`) detects loops; a boolean would not.
- F7 Identity. The package wrapper exports `TESTEE_SELF_OUT=$out`. A pin is a launcher only if it reads it.
- F8 Escape. `TESTEE_NO_LAUNCH=1` skips everything.
- F9 Exit codes. Launcher failures exit 2 with a `testee:` prefix, the cause, the project file, and the fix. 0, 1 and 2 keep their meaning.
- A new pin must work with exactly this input. If it needs more, it derives the need itself. A launcher change reaches only upgraded hosts,
  so every launcher change must be backward compatible with the pins it launches.
- `inferred` `--root` abbreviations: argparse accepts `--ro X` (abbreviation is on by default; not tested). The scan sees only the exact spelling.
  The launcher and the pin could then pick different projects. Reject abbreviations in the pin from 0.6 on (`allow_abbrev=False`).

### 1.7 GC of the realised path
- `verified` `devenv shell` roots the shell closure under `.devenv/gc/shell` (`ls .devenv/gc` in `fx`). The pin is in `packages`, so a
  successful shell build roots it.
- `inferred` The unrooted window is the time between a realise and the first shell build. A GC in that window forces a re-realise
  (about 1 s warm). No data loss. A launcher-owned root in `.testee/` is possible but adds a second state path; skip it.
- Side effect to record: my `nix-store --query --roots` call removed stale auto-root links from deleted pytest temp directories under
  `/nix/var/nix/gcroots/auto`. That is routine link housekeeping, not a garbage collection. No store path was deleted.

### 1.8 Cold cache, offline, macOS, CI
- Cold eval: `verified` 2.4 to 3.6 s with an empty eval cache; 0.09 to 0.12 s warm (`fx`, `rm`).
- Realise: `verified` 0.96 s for a new `runCommand` derivation when its inputs are present. Closure size `verified` 404 MB
  (`nix path-info -rS`). A cold machine downloads that closure. `inferred` The shell needs the same closure anyway, because the pin is in
  `packages`. For `verify` the launcher moves the cost earlier; it adds none. For `doctor` and `report` it can add a download.
- Offline: `verified` `devenv eval testee.package.outPath` succeeds inside `unshare -rn` (no network) on a copy of RepoMan with a warm cache.
  `unknown` Expired fetch TTL for `ref=refs/tags/...` offline. `inferred` A missing `outPath` offline fails with the realise error, as `devenv shell` would.
- macOS: `verified` Testee's flake lists only `x86_64-linux` and `aarch64-linux` (`flake.nix:8`), and containment uses Linux features.
  The launcher adds no new platform limit. `unknown` otherwise.
- CI with no host install: `verified` `nix run path:/tmp/tw-trunk/testee#testee -- --version` prints `testee 0.5.1`.
  So CI can run `nix run github:Bullish-Design/testee/<tag> -- verify --full`: the launcher bootstraps, the pin runs. No profile step.
  The CI tag is a floor (any launcher-capable tag), not the project pin.

### 1.9 Security
- `inferred` No new trust for `verify`, `check`, `doctor`. Today the host already runs `devenv eval` on the project and `devenv shell --clean`,
  which runs the project's `enterShell` (`cli.py:68-101, 178-187`). Executing `<outPath>/bin/testee` is the same class of code execution.
  `nix-store --realise` is sandboxed builds; it adds less than `enterShell` does.
- New trust: `testee report`. Today it reads JSON only (`cli.py:195-204`). A launching `report` would execute project-named code to print a file.
  Rule: `report` launches only when `.testee/latest` exists (a prior run in this checkout, so trust was already given), and fails open to the host reader.
  `.testee/` is Git-ignored, so a fresh clone has none (`README.md:43`, `02` section 9).
- `inferred` `devenv eval` can write `.devenv/` and, with no `devenv.lock`, create it. The rule above keeps `report` from doing that in a fresh checkout.

### 1.10 Report and doctor
- `verified` `Report` is a strict model (`models.py:15-17`, `extra=forbid`). A newer pin's report with one extra field fails to parse in an older host.
  So `report` must launch, or the model must become tolerant. Launch, fail-open.
- `doctor` in a broken project is the command you run to diagnose. If the pin cannot build, launch fails closed and doctor shows nothing.
  Rule: `doctor` fails open, prints the launch failure as its first finding, and exits 2. `verify` and `check` fail closed.
- `inferred` `doctor` should print launcher state: host version, pin `outPath`, launched or not, via `TESTEE_LAUNCHED`.

### 1.11 argv, cwd, stdin, signals, lock across exec
- `verified` Experiment (`/tmp/tw-da2/ex.py`): `os.execv` keeps the pid (1305509 before and after), keeps piped stdin (`hello` read after exec),
  and delivers SIGTERM to the exec'd program (trap ran, exit 7). So signals and the pid for wrappers stay the same.
- `verified` Python `flock` file descriptors are close-on-exec (`os.get_inheritable` returned False). A lock taken before exec would vanish.
  F1 forbids that: the launcher takes no lock and writes no state before exec. The pin takes the lock after exec (`cli.py:138-142`).
- `verified` My launcher with a host/pin mismatch ran `doctor` through the pin (3.75 s cold eval, includes pin work). With host equal to pin it
  returned to the caller after one eval (0.17 s total, of which about 0.1 s is the eval).
- `inferred` Relative `--root` and cwd work because exec keeps cwd and the pin resolves them the same way (`cli.py:55-65`).

### 1.12 Eval in the steady state, and the "same eval" idea
- `verified` One `devenv eval` of two or three attributes costs the same as one: 0.11 to 0.12 s warm (`fx`).
- `inferred` Same eval only pays off when host equals pin (the common case): the process keeps the manifest and evaluates once. When it execs,
  the pin re-evaluates `testee.manifestJson` (parent log: about 0.3 s gap). Do not pass the manifest across exec: that adds a protocol, and a
  0.5.x pin would ignore it anyway.

### 1.13 Cross-project contamination inside a shell
- `verified` In `fx`, inside a devenv shell and inside a devenv task, `testee` resolves to the pin first (`/nix/store/...-testee-0.5.99/bin/testee`,
  tested with `command -v testee` in a task).
- `inferred` Inside project A's shell, `testee verify` in project B starts A's pin. With a launcher-capable A pin, it relaunches B's pin. With a 0.5.x pin
  it runs A's runner on B, as today.

## 2. Self-launch against "host as pure supervisor"

The alternative: the host stays the supervisor and launches `devenv shell --clean -- testee _worker STATE RUN_ID ROOT`, so the worker is the in-shell pin.

| Item | Self-launch | Supervisor split |
|---|---|---|
| New concepts | launcher stage, 2 eval attributes, 3 env vars, exec | `_worker` verb, PATH order inside the shell, plus every protocol below |
| Manifest parse | in the pin | in the host (strict v1 model, `cli.py:83-89`) |
| `run.json` (`testee.run.v1`) | pin both sides | host writes, pinned worker reads (`supervisor.py:51-53`) |
| start/result/finish records | pin both sides | worker writes, host collector reads |
| Verdict (exit code, `is_full_gate`) | pin | host `Collector` (`collector.py:251-271`) |
| `report` reader | pin | host models, strict |
| Skew points left | 0 for behaviour; 1 for launcher grammar (F1 to F9) | 5 file protocols plus 1 argv protocol |
| Change size in Testee | one stdlib module, one env line in the wrapper | new verb, new launch path, PATH reliance |

- `verified` Today the host owns manifest parse, `run.json`, collector and verdict (`02` sections 2, 3). The split moves only the worker.
- `inferred` The split leaves behaviour in the host (verdict, gate rules) and keeps skew in all file formats. `extra=forbid` makes added fields loud.
  Meaning changes stay silent. DA1 fact 3 shows behaviour changes with no schema change.
- `inferred` Self-launch is simpler for the invariant "runner = pin". The split is simpler only in that it needs no realise before the shell.
- The split needs the pin on the in-shell `PATH` first. `verified` that holds in a plain shell (`fx`). RepoMan's current `dirname` rewrite breaks it.
- Verdict: self-launch is simpler by concept count and by skew. Keep it.

## 3. Smaller designs

### 3a. No host install; `devenv tasks run testee:verify` or `devenv test` only
- Measured loss `verified`: with a package that fails to build in `packages` (a `runCommand` that exits 1),
  host `testee verify` still wrote a sealed report (`INFRA (exit 2)`, `wrapper_error`, `not_run` for each check, one run directory),
  while `devenv tasks run --no-tui testee:verify` failed in devenv's own `Evaluating shell` step with no Testee output and no run directory.
  The cause line is "Failed to realize shell derivation" in both cases; the sealed report does not carry the build error text.
- Surface loss `verified`: the task runs `verify --full` only. `check <id>`, `report`, `doctor`, quick `verify` have no task form
  (`nix/testee.nix:66`). Every agent-facing command in the testee skill (`SKILL.md` Commands) would move to `devenv shell -- testee ...`.
- Cost `verified` by DA1: +0.6 s per call (outer shell first). TUI hazard: every call needs `--no-tui` (`AGENTS.md`).
- Containment `verified`: both `devenv tasks run` and `devenv test --no-tui` reported `containment: strong` on this host (PID namespace).
  `unknown` for hosts where user namespaces are restricted; the memo says only the outer wrapper can make a scope (memo section 14, gap 2).
- ADR reason for a host install `verified`: one sentence, no stated reason (`02` section 7). Memo reasons: the wrapper owns exit code after failure
  (memo line 102), and scope containment. Both survive self-launch because the pin runs outside the shell it opens.
- Verdict: keep (a) as the fallback for CI and "no host", not as the RepoMan entry. It breaks the uniform `testee` command in the router.

### 3b. Generic family launcher for copyroom, gitman, testee
- `verified` copy and git have no devenv-evaluable pin that drives their runner (04 section 3); gitman has no `--version`; RepoMan imports no
  copyroom module (04 deviation 10). Their drift is cosmetic (copyroom 0.8.0 versus a 0.7.7 string).
- `inferred` A shared launcher would add a package, a frozen contract for three tools, and a naming convention (`<tool>.package`), for two tools that have no skew defect.
- Verdict: reject now. Write the launcher as a module parameterised only by the attribute name, so extraction later is a rename.

### 3c. A devenv `require_version` analogue
- `verified` `require_version` in `devenv.yaml` constrains the devenv CLI against the devenv modules (`05` section 1, devenv).
  It does not reach Testee.
- A Testee-side form is a Nix assertion on a host-provided variable. `verified` in `envt`: `builtins.getEnv` works under `devenv eval`, and an
  assertion with a message fails the eval. But an old host (0.5.x) prints only the first 400 characters of stderr (`cli.py:78-79`); the 8130-character
  trace puts the message after character 400 (`MSG IN FIRST400: False`). So it fails loudly but not usably, and it blocks pairings that would work.
- Verdict: reject. Once hosts launch, the pin always runs and a project-level version policy has no purpose.

## 4. Does RepoMan need Nix code or a version row?

### Nix code
- `verified` Without `REPOMAN_TESTEE_VERSION`, `modules/managers/testee.nix` no longer reads `config.testee.package`. That removes the evaluation coupling
  that 04 deviation 3 lists.
- `verified` Callers of `repoman:test`: RepoMan's own `base:test` (`devenv.nix:182`), docs (`README.md:189`, `AGENTS.md:36`),
  and template-py comments and README (`template-py/README.md:88`). No code outside RepoMan calls it.
- Strictly required Nix: none. Recommended: keep `"repoman:test".exec` and `"repoman:test:ci".exec` as two lines that call bare `testee`
  (`verified` that inside a task `testee` is the pin), with no `config.testee` read and no `REPOMAN_TESTEE_HOST_BIN`. They keep the template-py contract
  and `base:test`. Delete them in a later release if a caller search finds none (`unknown` for repos outside the snapshots).
- Delete: `REPOMAN_TESTEE_HOST_BIN` (three places), `binary_env`, `version_env`, `env.REPOMAN_TESTEE_VERSION`, the `dirname` half of the
  `PATH` rewrite (`modules/devenv.nix:139-140`), `_version_check` exact equality, the shadow branch of `_installed_check`,
  and the tests that pin them (`test_checks.py:28-49, 153-188`, `test_cli.py:72-89`, `test_registry.py:83-85`, `test_modules_nix.py:7-12, 35-41`).
- `unknown` Whether the `venv/bin` half of the `PATH` rewrite is needed ("Keep app tools available", `devenv.nix:136`). Leave it; it is not Testee's.

### Version row: one owner
- Choice: RepoMan doctor owns "host too old", as a minimum row, like `interface:git` (`checks.py:301-323`, jj >= 0.46.0).
- Reasons:
  1. `inferred` Only an outside checker can see an already-installed old host. The 0.5.x host has no code for it.
  2. `verified` The module route (3c) is loud but unreadable on old hosts.
  3. `verified` A schema bump (`testee.manifest.v2`) makes old hosts fail with a Pydantic error (`Invalid Testee manifest ...`, `cli.py:88-89`), and it also breaks
     host/pin pairings that work. DA1 saw the same failure class for an extra field (`06` section 2.5). It is opaque.
  4. The number changes only if the frozen launcher changes. So the constant is stable. Keep it in the registry (`min_version="0.6.0"`), not in the Nix module.
- Row design: `interface:test` runs `testee --version`, parses `testee <ver>`, compares `>=`. `fail` below the floor. The check proves a launcher-capable
  version, not that launching is active. Testee covers the rest: a non-store build refuses to run project commands without `TESTEE_NO_LAUNCH` (section 1.2).
- Testee owns everything else: the launcher, the frozen contract, `doctor` output about the launch. RepoMan never reads the pin version again.

## 5. Amended hypothesis

Self-launch with these changes:

1. Entry. A stdlib-only `testee.launch` module is the console script and `python -m testee` target. It runs before `argparse` and imports no pydantic.
   `cli.main` is not changed and keeps no launch code, so tests call it directly.
2. Contract F1 to F9 (section 1.6), including opaque argv, exact `--root` scan, chained `TESTEE_LAUNCHED`, `TESTEE_SELF_OUT` from the package wrapper,
   `TESTEE_NO_LAUNCH` escape, no state or lock before exec. Add `allow_abbrev=False` to the parser.
3. Policy by command. `verify` and `check` fail closed. `doctor` fails open and prints the launch failure. `report` launches only if `.testee/latest` exists, else
   reads locally. A non-store build without `TESTEE_NO_LAUNCH=1` is an error, not a warning. Testee's own `devenv.nix` sets that variable.
4. One eval of `testee.package.outPath`, `testee.package.drvPath`, and (when the command needs it) `testee.manifestJson`. Reuse it when host equals pin.
   Do not pass the manifest across exec. Do not add a GC root.
5. Messages carry four parts: required thing, running thing, file, fix.
6. RepoMan: bare `testee`; delete the items in section 4; add `interface:test` with floor `0.6.0` (the first launcher release); keep `installed:test`.
   Keep two task lines or delete the module body. No `config.testee` read.
7. CI: `nix run github:Bullish-Design/testee/<floor tag> -- verify --full`, or `devenv test --no-tui`.
8. Release order: ship Testee 0.6.0 and install it on hosts first. Then ship RepoMan with the floor row. Until a host is 0.6.0 the old behaviour (silent skew) remains;
   the new row is the only signal.
9. Later, separate: pin Testee through `devenv.lock` (DA1 F6), and do not extract a family launcher until a second tool has a pin defect.

## 6. Caveats on my evidence
- The parent installed a prototype `testee 0.5.1+selflaunch` in RepoMan's venv while I worked. Bare `testee` on my `PATH` was that prototype. Timed or compared host
  runs used `~/.nix-profile/bin/testee` explicitly, or the pin, except `ent.sh`; I treat its report contents as indicative only.
- The `fx` fixture is not a clean Testee checkout. Its `.devenv/` files are tracked, and its tests fail (`source_changed`, pytest exit 5). I used it for eval,
  realise, PATH and containment facts, not for gate results.
- Not tested: cold-store download time, expired fetch TTL offline, macOS, restricted user namespaces, abbreviations of `--root`, the "module imported, package unset" error.
