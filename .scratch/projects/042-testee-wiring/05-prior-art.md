# Prior art: global launcher versus project-pinned version

Date: 2026-10-10. Labels: `verified` (source quoted or read), `inferred` (my reading), `unknown` (not found).
Fetched content is treated as untrusted data. Quotes are short.

## 1. Survey

### Bazelisk (`.bazelversion`)
- Mechanism: launcher. It picks a Bazel version, downloads it, and runs it. `verified`
  https://raw.githubusercontent.com/bazelbuild/bazelisk/master/README.md
- Order: `USE_BAZEL_VERSION`, then `.bazeliskrc`, then `.bazelversion` (current or parent directory), then fallback, then latest. `verified` (same URL).
- Owner of the check: the launcher. The project owns the pin file. `verified`.
- Semantics: exact by default. The launcher runs the pinned version, so there is no mismatch to detect. `inferred`
- Integrity: SHA256 check only "if `BAZELISK_VERIFY_SHA256` is set". `verified`.
- Layered wrapper: Bazelisk runs `tools/bazel` from the repo if present. It sets `BAZEL_REAL` and `BAZELISK_SKIP_WRAPPER` to prevent loops. `verified` (same URL).
- Bare Bazel reads `.bazelversion` too, and "the failure when it mismatches ... can be quite confusing". `verified` (same URL).
- Complaint: a comment in `.bazelversion` gives a message with no program prefix and no file name. `verified` https://github.com/bazelbuild/bazelisk/issues/711
- Complaint: the file format is undocumented. `verified` (title) https://github.com/bazelbuild/bazelisk/issues/408

### rustup and `rust-toolchain.toml`
- Mechanism: proxy binaries (`cargo`, `rustc`). Each proxy resolves a toolchain per call. `verified`
  https://rust-lang.github.io/rustup/overrides.html
- Order: `+toolchain`, `RUSTUP_TOOLCHAIN`, directory override, `rust-toolchain.toml`, default. Nearest directory wins. `verified` (same URL).
- Owner: the proxy. The project owns the file. Semantics are a channel or exact version. `inferred`
- Auto-install flip-flop: 1.28.0 stopped installing a missing toolchain. `verified` https://blog.rust-lang.org/2025/03/02/Rustup-1.28.0/
  1.29.1 says implicit installation "has been deprecated where deemed unnecessary and will now produce a warning". `verified` https://blog.rust-lang.org/2026/09/01/Rustup-1.29.1
  A search summary says 1.29.x added `RUSTUP_AUTO_INSTALL` and `rustup set auto-install`. `inferred` (not read in the primary source).
- Complaint: unknown keys in `rust-toolchain.toml` are silently ignored. `verified` (title) https://github.com/rust-lang/rustup/issues/2876
- Complaint: the file format needs documentation fixes. `verified` (title) https://github.com/rust-lang/rustup/issues/2880

### pyenv (shims)
- Mechanism: a shims directory at the front of `PATH`. `rehash` rebuilds the shims. Order: `PYENV_VERSION`, `.python-version`, parents, global file. `verified`
  https://raw.githubusercontent.com/pyenv/pyenv/master/README.md
- Owner: the shim, on each call. Semantics are exact. `inferred`
- Complaint: "Shims are too slow". `verified` https://github.com/pyenv/pyenv/issues/2802
- Complaint: a shim leaks internal paths into the child `PATH`. `verified` (title) https://github.com/pyenv/pyenv/issues/3436
- Complaint: `python` shim not used if the user ran `python` before the first alternative install. `verified` (title) https://github.com/pyenv/pyenv/issues/2732

### asdf and mise (`.tool-versions`, shims versus activation)
- mise: shims "resolve the environment each time a command runs". They do not set `[env]` variables or run `cd` hooks. `which` returns the shim. Advice: activation for shells, shims for editors and programs. `verified`
  https://mise.jdx.dev/dev-tools/shims.html
- mise `min_version`: a plain string is a hard minimum ("Older mise releases stop with an error and print upgrade instructions"). An object `{hard, soft}` adds a warn-only soft minimum. `verified`
  https://mise.jdx.dev/configuration.html
- asdf complaint: error says "No version is set" when the version is set but not installed. `verified` https://github.com/asdf-vm/asdf/issues/2142
- asdf complaint: shims are missing from non-interactive shells. An AI editor agent picked the system Ruby. `verified` https://github.com/asdf-vm/asdf/issues/2085
- asdf complaint: `reshim` rebuilds shims in place, so concurrent commands fail. `verified` (title) https://github.com/asdf-vm/asdf/issues/2315
- mise complaint: `npm view` re-enters mise through its own shim and causes a process explosion. `verified` (title) https://github.com/jdx/mise/issues/14068
- Lesson source: a shim `PATH` rewrite fails in non-interactive, agent, and re-entrant calls. `inferred` from the issues above.

### direnv and nix-direnv
- direnv `direnv_version`: "Checks that the direnv version is no older than `version_at_least`". Minimum semantics, owned by the `.envrc`. `verified`
  https://raw.githubusercontent.com/direnv/direnv/master/man/direnv-stdlib.1.md
- direnv runs inside the user's shell, before the environment exists. It has no pinned launcher. `inferred`
- devenv's direnv integration has its own handshake. The generated direnvrc has an integer version (`direnvrcLatestVersion = 2`). The shell compares `DEVENV_DIRENVRC_VERSION` and warns when old. `verified`
  https://github.com/cachix/devenv/blob/main/src/modules/update-check.nix
- Complaint on direnv/nix-direnv version drift: `unknown` (not found in search).

### pre-commit
- `minimum_pre_commit_version`: set by the hook author, default `'0'`. It is a minimum. `verified` https://pre-commit.com/#top_level-minimum_pre_commit_version
- Hook pinning: `rev` must be an immutable tag or SHA; the cache keys on it. `autoupdate` bumps it; `--freeze` stores SHAs. `verified` (same URL).
- Shape: the host tool is global. The hooks are pinned per project and installed by the host. There is no launcher. `inferred`
- Failure message quality: `unknown` (not tested).

### devbox
- Mechanism: a launcher plus a version field in `devbox.json`. The field is `devbox_version`, either a semver constraint string or `{version, on_mismatch}`. `verified`
  https://github.com/jetify-com/devbox/blob/main/internal/devconfig/configfile/devbox_version.go
- Policies: `warn` (default), `error`, `auto`. `off` is allowed only through the env var `DEVBOX_VERSION_POLICY`. `auto` needs an exact version. `verified` (same URL).
- `auto` re-execs the launcher with `DEVBOX_USE_VERSION=<exact>`. The launcher downloads the version if needed. `verified`
  https://github.com/jetify-com/devbox/blob/main/internal/vercheck/project.go
- Loop guards: `__DEVBOX_AUTO_VERSION` stops re-exec loops. `__DEVBOX_VERSION_MISMATCH_WARNED` stops nested duplicate warnings. A user-set `DEVBOX_USE_VERSION` wins over `auto`. `verified` (same URL).
- No launcher present (`LauncherPath` empty): the check fails with "wasn't started by the devbox launcher". `verified` (same URL).
- Message: "This project requires devbox X (devbox_version in PATH), but you are running Y." It then names the fix and the skip switch. `verified` (`mismatchMessage` in the same file).
- Dev builds skip the check. `verified` (`isDevBuild` in the same file).
- Origin: issue asked for "fail with an informative message on the required version and provide instructions on how to install it". `verified` https://github.com/jetify-com/devbox/issues/1371
- Complaint: users want rollback to a prior devbox version after a bug. `verified` https://github.com/jetify-com/devbox/issues/1746

### uv `required-version`
- PEP 440 specifier, for example `==0.5.0` or `>=0.5.0`. "If the version of uv does not meet the requirement at runtime, uv will exit with an error." `verified`
  https://docs.astral.sh/uv/reference/settings/#required-version
- Owner: the running uv binary. There is no auto-switch. `inferred`
- Complaint: `uv self update` ignores `required-version`, so the update causes an error with advice to run `uv self update <version>`. `verified` https://github.com/astral-sh/uv/issues/16014 (also #10547).

### Gradle wrapper
- Mechanism: vendored wrapper. Script and JAR are checked in. `gradle-wrapper.properties` holds `distributionUrl`. The wrapper downloads and caches the distribution. `verified`
  https://docs.gradle.org/current/userguide/gradle_wrapper.html
- Integrity: optional `distributionSha256Sum`. "Gradle will report a build failure if the configured checksum does not match". `verified` (same URL).
- Upgrade: `./gradlew wrapper --gradle-version X`. `verified` (same URL).
- Owner: the project. Exact semantics. There is no host install to drift. `inferred`
- Daemon handshake: the client reuses a daemon only if Gradle version and JVM settings match. Otherwise it starts a new one. `verified`
  https://docs.gradle.org/current/userguide/gradle_daemon.html

### Poetry and PDM
- Poetry `requires-poetry`: "A constraint for the Poetry version ... If you are using a Poetry version that is not allowed by this constraint, an error will be raised." `verified` https://python-poetry.org/docs/pyproject/#requires-poetry
- Poetry complaint: `requires-plugins` fails silently on some commands. `verified` (title) https://github.com/python-poetry/poetry/issues/10341 and #10254
- PDM: no minimum-version setting found on the PEP 621 reference page. `unknown` (absence not proven).

### cargo `rust-version`
- A bare minimum version with no operators. Cargo reports an error on an older toolchain instead of "a less direct diagnostic like invalid syntax". `--ignore-rust-version` bypasses it. `verified`
  https://doc.rust-lang.org/cargo/reference/rust-version.html

### Terraform `required_version`
- A constraint string. "Terraform prints an error and exits without taking actions" on mismatch. It applies to the CLI only. Child modules can add constraints, and all must pass. `verified`
  https://developer.hashicorp.com/terraform/language/terraform#specifying-a-required-terraform-version

### Nix `nix run` / `nix develop`
- `flake.lock` maps unlocked inputs to exact revisions, so `nix run <flake>#tool` is pinned by the lock. `verified`
  https://nix.dev/manual/nix/stable/command-ref/new-cli/nix3-flake.html
- `nixConfig` in a flake needs confirmation unless `accept-flake-config` is set. `verified` (same URL).
- A host wrapper can use `nix run` to fetch the pinned binary before the shell exists. The cost is a Nix evaluation and a flake dependency. `inferred`

### devenv itself (the closest analogue)
- Same shape as Testee: the host `devenv` CLI starts first. The modules come from the `devenv` input in `devenv.lock`. `verified`
- Option `require_version` in `devenv.yaml` (since 2.1): `true` means the CLI version must equal the modules version. A string uses `>=`, `<=`, `>`, `<`, `=`, or a bare exact version. `verified`
  https://devenv.sh/reference/yaml-options/
- Constraint strings: the Rust CLI checks them before Nix evaluation. The error is "devenv version X does not satisfy the constraint 'C' in devenv.yaml". `verified`
  https://github.com/cachix/devenv/blob/main/devenv-core/src/config.rs (`check_version`)
- `true` mode: the check runs as a Nix assertion during evaluation. The message reads "devenv CLI version X does not match the modules version Y ... Run 'devenv update' to sync the modules, or update your CLI to version Y." `verified`
  https://github.com/cachix/devenv/blob/main/src/modules/update-check.nix
- Default without `require_version`: only a warning in `enterShell`. A newer CLI says "devenv X is newer than devenv input (Y) in devenv.lock. Run 'devenv update' to sync." An older CLI says it is out of date. Warnings can be turned off with `warnOnNewVersion`. `verified` (same file).
- Normalisation: trailing `.0` segments are stripped, and development builds skip the check. `verified` (same file).
- Origin: issue 2391 asked how to pin devenv itself. The reporter lost hours to a 1.10 to 1.11 behaviour change. `verified` https://github.com/cachix/devenv/issues/2391
- Gap: the CLI cannot switch itself. It only reports. `inferred` (no re-exec code seen).

### Launcher-to-component handshakes
- LSP: no version handshake in 3.x. The client and server exchange capabilities in `initialize`. `verified` https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#initialize
- Docker: the client and daemon negotiate the highest shared API version. `DOCKER_API_VERSION` "disables API version negotiation". A newer client may call endpoints the daemon lacks. `verified` https://docs.docker.com/reference/api/engine/#versioned-api-and-sdk
- Gradle daemon: reuse only on a match of version and environment (see above). `verified`.
- devenv direnvrc integer version (see direnv section). `verified`.
- Devbox `__DEVBOX_AUTO_VERSION` and `LauncherPath` env vars pass state from launcher to in-process code. `verified`.

## 2. Comparison

| Tool | Pattern | Check owner | Semantics | Message quality |
|---|---|---|---|---|
| Bazelisk | launcher | launcher | exact | poor on bad file (#711) |
| rustup | proxy | proxy | exact/channel | changed twice on auto-install |
| pyenv, asdf | shim | shim | exact | asdf misleading (#2142) |
| mise | shim or activate + min_version | tool | hard/soft minimum | upgrade instructions |
| direnv | stdlib check | `.envrc` | minimum | not tested |
| pre-commit | host + pinned hooks | host | minimum / immutable rev | not tested |
| devbox | launcher + field + policy | tool | constraint; exact for auto | names fix and skip switch |
| uv, Poetry, Terraform, cargo | constraint check | running tool | specifier / minimum | clear error |
| Gradle | vendored wrapper | project | exact | build failure on checksum |
| devenv | constraint + equality to input | CLI and Nix assertion | `true` equals; strings | names `devenv update` |
| Docker, LSP | handshake | both sides | negotiated | n/a |

## 3. Design lessons for Testee

1. Put the pin where the project owns it, and make the check run in the host wrapper first. Devenv and Devbox both check in the launcher before work starts. `inferred`
2. Compare to a single source of truth. Devenv compares the CLI to the module input in the lock. Testee has the same two parts, so compare the wrapper to the pinned package version. `verified` (devenv) / `inferred` (Testee)
3. Pick the semantics on purpose. Use exact equality while the host-to-shell contract is private. Use a minimum only after a stable protocol exists. Devenv offers both. Terraform, uv, and cargo use minimum. Launchers (Bazelisk, Gradle) use exact. `verified`
4. Prefer re-exec over a `PATH` rewrite. Devbox re-execs the pinned version through a launcher and guards loops with env vars. Shims fail in non-interactive shells (asdf #2085) and re-enter themselves (mise #14068). `verified`
5. Give every mismatch message four parts: the required version, the running version, the file that sets the requirement, and the fix. Devbox adds the skip switch. Bazelisk #711 shows the cost of leaving out the source file. `verified`
6. Offer a policy ladder: `error`, `warn`, `off`. Default to `warn` for dev flows and `error` in CI. Keep `off` in an env var, not in the project file, as Devbox does. `verified` (Devbox) / `inferred` (Testee default)
7. Skip the check for development builds and normalise versions (`2.1.0` equals `2.1`). Devenv and Devbox do both. `verified`
8. Add a cheap handshake in the shell. The launcher passes its version in an env var. The in-shell component compares it to its own and fails with a clear message. This catches drift the launcher cannot see, and it works without Nix evaluation. A protocol integer (devenv direnvrc) is enough. LSP shows a capability set can replace version numbers when features vary. `verified` (examples) / `inferred` (Testee fit)
9. Do not auto-install silently. Rustup reversed its auto-install policy twice, and uv users hit a conflict between `self update` and the pin. Make updates explicit, and make the update command respect the pin. `verified`
10. Guard against loops and nesting. Use a "warned once" variable and an "already switched" variable. `verified` (Devbox)

## 4. Best pattern for a launcher that runs before the environment exists

Best fit: Devbox-style launcher check, plus a devenv-style version handshake.

1. The host wrapper reads the required version from a project-owned file or from the `devenv eval` manifest. It runs before the shell exists.
2. On mismatch the wrapper applies a policy: `error` by default. It names both versions, the source file, and the fix.
3. The wrapper passes `TESTEE_WRAPPER_VERSION` (and a protocol integer) into `devenv shell --clean`. The in-shell Testee compares them and fails fast.
4. Re-exec to a pinned binary (`nix run` on the locked flake) is an optional later step. It needs a loop guard.

This replaces the PATH rewrite. A PATH rewrite is the shim pattern, and the shim pattern has the most field complaints. `inferred`

## 5. Open items

- `unknown`: whether `devenv shell --clean` drops custom env vars. Test before relying on lesson 8.
- `unknown`: the exact text of the rustup 1.29 auto-install post of July 2026. Only the 1.29.1 post was read.
- `unknown`: any nix-direnv version-drift complaint. None found.
