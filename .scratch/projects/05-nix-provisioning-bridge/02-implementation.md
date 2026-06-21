# 02 — Implementation (running log)

Implements the plan in [`01-findings.md`](01-findings.md). Decisions taken (per review go-ahead):
**R1** (consumer declares each approach-B manager's input; `repoman doctor` warns when a selected
approach-B manager's input/provisioning is missing); upstream warn-vs-fail changes are **separate
follow-ups**; the docman wiring doubles as the **verification spike** for the approach-B mechanism.

## The approach-B import mechanism (the spike result will confirm/adjust this)

A devenv module receives `inputs` (the consumer's declared inputs) as a module arg. `imports` may be
computed from `inputs` (not from `config`). So an approach-B manager module in repoman uses a
**presence-gated static import** + a **membership-gated config**:

```nix
{ inputs, pkgs, lib, config, ... }:
let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "doc" cfg.managers;
  hasInput = inputs ? docman;                       # consumer declared the docman input?
in {
  imports = lib.optional hasInput (inputs.docman + "/modules/docman.nix");
  config = lib.mkMerge [
    (lib.mkIf (enabled && hasInput) { docman.enable = true; })   # activate the manager's own module
    (lib.mkIf enabled {                                          # task is wired regardless
      tasks."repoman:docs:doctor".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/docman doctor'';
    })
  ];
}
```

- A consumer **without** the docman input → `imports` is empty → no eval error, no `options.docman`,
  the task still wires. `repoman doctor` should WARN ("doc selected but its nix module isn't imported
  — add the docman input").
- A consumer **with** the input + `doc` selected → docman's gated module activates → zensical/python/
  config land.

## Phasing (low-risk first, de-risk the mechanism, then the heavy lifts)

- **Phase 1 — approach-A quick wins (no consumer input needed).** `copy` (+`pkgs.git pkgs.gnupatch`),
  `session` (`env.ZELLIGATE_*` in-repo writable defaults, `DOCKER_MODE=0`, all `mkDefault`). `git`'s
  3.13 concern becomes a doctor warning (Phase 5), NOT a forced pin (a pin would impose
  `nixpkgs-python` on every git consumer; rolling nixpkgs already gives 3.13).
- **Phase 2 — approach-B spike via `doc`/docman.** Implement the mechanism above; add the docman input
  to the consumer-example; eval + verify zensical lands and `docman doctor` improves. This validates
  R1 + the import pattern on the easiest B-class manager (module already import-ready).
- **Phase 3 — `spec`/allium-env.** Un-gitignore assets (R4), extract `modules/allium.nix` (enable
  default→false), allium-env imports it (`enable=true`), repoman imports+gates on `spec`.
- **Phase 4 — `agent`/mypi.** Import `pi-agent.nix` gated on `agent` with `bootstrap.mode=manual_only`,
  telegram off, banner off; resolve CLI-shadow (don't let its `scripts.mypi` shadow the venv mypi).
- **Phase 5 — repoman R1 support.** `repoman doctor` self-check: for each selected approach-B manager,
  warn when its provisioning/input is absent; scaffold the required `devenv.yaml` inputs (doc/init).
- **Phase 6 — tests + consumer-example full-roster re-verify.**

## Log

- **2026-06-20** — Plan recorded; R1 chosen. Starting Phase 1 (copy + session approach-A edits).
- **2026-06-20** — **Phases 1 + 2 done and verified end-to-end** in `tests/consumer-example`.
  - **copy (A):** `copyroom.nix` now adds `packages = [pkgs.git pkgs.gnupatch]`. Verified `git`+`patch`
    on PATH; `copyroom doctor` exit 0.
  - **session (A):** `zelligate.nix` now sets `env.ZELLIGATE_{DOCKER_MODE,WORKSPACE_DIR,STATE_DIR}`
    (`mkDefault`, in-repo writable). Verified workspace+state `ok`, docker_mode=false;
    `zelligate doctor` exit **0** (was 2).
  - **doc (B) — the spike:** `docman.nix` rewritten to the presence-gated import pattern
    (`imports = lib.optional (inputs ? docman) (inputs.docman + "/modules/docman.nix")` +
    membership-gated `docman.enable`). Consumer-example `devenv.yaml` gained `docman` +
    `nixpkgs-python` inputs (R1). Verified zensical + full docs toolchain on PATH, `.docman/zensical.toml`
    auto-seeded via docman's `enterShell`; **`docman doctor` exit 0** (was 2, with 2 hard FAILs).
  - **Mechanism CONFIRMED:** approach-B import works; `inputs`-gated import is legal; R1 input
    declaration is the right model. Bonus: docman's *own* doctor already checks "docman input declared"
    / "nixpkgs-python input declared", so the R1 "missing input" warning is partly self-served by the
    sub-doctor (repoman-side warning still worth adding for managers whose doctor doesn't — Phase 5).
  - Fixture hygiene: gitignored docman's seeded scaffold (`.docman/ docs/ snippets/ .markdownlint.jsonc
    .typos.toml`) in the consumer-example. Unit suite still 55 passed.
  - **Negative case verified:** a throwaway consumer selecting `doc` with **no** docman input evals
    cleanly. This forced a fix: `docman.enable` must be set via `lib.optionalAttrs hasInput { … }`
    (vanishes at the attrset level when the input is absent), **not** `lib.mkIf (enabled && hasInput)`
    — `mkIf` alone still registers a definition for the then-undeclared `docman` option and throws
    "option `docman' does not exist" under strict eval. **This is the canonical approach-B pattern**
    and must be reused for spec/agent. Committed (`1c30ca4`).
  - **Next:** Phase 3 (spec/allium-env — needs R4 un-gitignore + extraction).
- **2026-06-21** — **Phase 3 (spec/allium-env) done and verified.**
  - **R4 was a non-issue:** the asset source trees (`.vendor/allium`, `.skills/allium-cli`,
    `.skills/allium-entrypoint`, `.agents/prompts`) are all already **tracked** — the audit's
    git-ignored claim was wrong. Only the install *target* `.agents/skills/allium-entrypoint/` is
    untracked (correct).
  - **allium-env (committed + merged to main, `ca88652`):** extracted `modules/allium.nix`
    (enable default→**false**; the allium CLI derivation, installer script, env, enterShell;
    asset paths `../…` relative to the module). `devenv.nix` slimmed to `imports = [ ./modules/allium.nix ]`
    `+ allium.enable = true` + the repo-local editable venv (kept OUT of the module). **Standalone
    preserved:** `alliman doctor` → 0 after `allium-install-codex-skills`; allium-env's own
    `tests/consumer-example` still green.
  - **repoman:** `alliman.nix` rewritten to the canonical approach-B pattern (presence-import
    `inputs.allium-env + "/modules/allium.nix"`, `optionalAttrs hasInput { allium.enable = mkIf
    enabled true; allium.cli.enable = mkDefault false; }` — binary fetch off, alliman doesn't need
    it). consumer-example `devenv.yaml` gained the `allium-env` input.
  - **Verified in an ISOLATED git consumer** (`/tmp/spec-iso`, managers=["spec"]): installer on
    PATH (was absent — the core symptom), `alliman install-skills` runs, **`alliman doctor` → 0**.
    Negative case (spec selected, no allium-env input) evals cleanly.
  - **Two findings recorded:** (a) git-based inputs (`git+file://`, flake:false) only materialize
    **committed** files — approach-B modules + their assets must be committed before any git consumer
    sees them (the `path:` input copies the worktree, which masked this in repoman's consumer-example).
    (b) allium's installer is **git-root-relative**, so in repoman's *nested* consumer-example it
    escapes to the repoman repo root; a real (isolated-git) consumer is unaffected. Both are
    environment facts, not wiring bugs.
  - **Next:** Phase 4 (agent/mypi — import `pi-agent.nix`, bootstrap=manual_only, telegram off,
    resolve CLI-shadow), then Phase 5 (repoman R1 doctor warnings) + Phase 6 (tests).
- **2026-06-21** — **Phase 4 (agent/mypi) done and verified** (user chose the "safe bridge").
  `mypi.nix` presence-imports `pi-agent.nix` and gates it. Two mypi-specific wrinkles handled:
  (a) `piAgent.enable` defaults TRUE upstream, so set `= enabled` explicitly (else declaring the
  input would activate it uninvited); (b) the module's `scripts.mypi`/`secretspec-setup` point at a
  nix-built mypi — overridden via `mkForce` to the venv CLI (resolves the shadow **and** avoids
  building the nix CLI). Safe knobs (`mkDefault`): `bootstrap.mode="manual_only"`,
  `telegram.enable=false`, `showUsageOnEntry=false`, `secrets.enable=false`.
  **Verified in consumer-example:** node 22 on PATH; `NPM_CONFIG_PREFIX`/`PI_CODING_AGENT_DIR`/
  `MYPI_AGENT_ROOT` env set; `mypi` resolves to the **venv** bin (shadow resolved). `mypi doctor`:
  the (i) provisioning errors (`npm_scope_not_project_local`, missing node/npm, `missing_agent_root`,
  `pi_not_on_path`) are **gone**; only the 3 `mypi sync`-dependent errors remain (settings shim,
  manifest, pi executable) — the (ii) user-driven part we intentionally don't auto-run. **No
  side-effects:** no `secretspec.toml`/`devenv.local.yaml` written, no on-entry npm install.
  - **All 5 (i)-class managers now bridged** (copy, session, doc, spec, agent). `test` is pure-Python
    (no module). `git` toolchain already bridged (approach A); its only residual is the latent
    Python-3.13 concern → a doctor warning (Phase 5), not a forced pin.
  - **Remaining:** Phase 5 (repoman-side R1 warning when a selected approach-B manager's input/
    provisioning is absent — partly self-served already by docman's/alliman's own doctors, so lower
    value; needs the nix modules to signal input-presence to the Python layer) + Phase 6 (unit tests
    + full-roster re-verify).
- **2026-06-21** — **Phase 5 (repoman R1 doctor warning) done and verified.** `repoman doctor` now
  emits a non-fatal `provisioned:<key>` row for each selected approach-B manager, distinct from
  `installed:<key>` (venv CLI). The nix→python signal: each approach-B module sets
  `env.REPOMAN_PROVISIONED_<KEY> = "1"` inside its `optionalAttrs hasInput (mkIf enabled { … })`
  block (folded beside the `enable`/settings), so the env exists iff the input was declared AND the
  manager is selected; `checks.py` reads it (`os.environ`). Absent → `warn` (`_LEVELS["warn"]==0`,
  never fails the aggregate) with a fix hint ("add the '<input>' input to devenv.yaml").
  - **registry.py:** new `Manager.nix_input` field; set `doc→"docman"`, `spec→"allium-env"`,
    `agent→"mypi-agent"`; `""` for copy/git/test/session.
  - **modules:** `docman.nix`/`alliman.nix` restructured from `optionalAttrs hasInput { … = mkIf
    enabled … }` to `optionalAttrs hasInput (mkIf enabled { … })` so the env sits beside the enable.
    `mypi.nix`: `piAgent.enable = enabled` stays unconditional-when-hasInput (upstream default TRUE);
    the env was added to the existing `optionalAttrs hasInput (mkIf enabled { scripts … })` block.
    Eval-safety of the canonical approach-B pattern preserved (env lives inside `optionalAttrs
    hasInput`, never a bare `mkIf`).
  - **checks.py:** `import os`; after the `installed:` loop, a `provisioned:<key>` row per manager
    with a non-empty `nix_input`.
  - **Tests (55→61):** `test_registry.py` asserts `nix_input` for the three + `""` for the rest;
    `test_checks.py` covers warn-when-signal-absent (exit 0), ok-when-`"1"`, and no-row for an
    approach-A manager; `test_cli.py` adds a `doctor --self-only` WARN-and-exit-0 case. Full suite
    `devenv shell -- pytest -q` → **61 passed**.
  - **Verified positive** (consumer-example, all three inputs declared): with
    `devenv shell --refresh-eval-cache` (NB: `rm devenv.lock` alone does NOT bust devenv's eval
    cache — must refresh, else the new env vars read empty), `provisioned:{doc,spec,agent}` all **OK**,
    exit 0.
  - **Verified negative** (isolated `/tmp` git consumer, `managers=["doc"]`, **no** docman input):
    `installed:doc` **OK** but `provisioned:doc` **WARN** (the orthogonality — installed≠provisioned),
    exit 0. Extended to all three approach-B managers selected with no inputs → three WARNs, exit 0,
    **module set still evals cleanly** (no "option `docman' does not exist") — eval-safety holds.
  - **Out of scope (5b/6):** auto-scaffolding the inputs into a consumer's `devenv.yaml`; the
    git-manager Python-3.13 doctor warning (separate check); final full-roster aggregate capstone.
