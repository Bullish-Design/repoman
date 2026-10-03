# 01 — Findings: the nix-layer provisioning bridge

> **Status: investigation complete (Tasks 1–5). Plan only — nothing implemented.** Grounded against
> the live repos on 2026-06-20. The single most important finding is cross-cutting and sits in
> Task 4: **devenv.yaml `inputs` are not transitive across a remote module import**, which directly
> constrains how a manager's nix module can reach a consumer and qualifies repoman's "one import"
> promise (CONCEPT §3).

## Task 1 — The two-layer model: **CONFIRMED**

repoman bridges exactly two layers, and the brief's hypothesis holds verbatim.

1. **Python/venv layer.** `modules/scripts/repoman-sync.sh` reads `repoman.lock`, resolves the
   `[repoman]` self entry + each selected `[managers.<key>]` (+ `<key>-*` native-dep pseudo-entries)
   and `uv pip install`s them (editable for `path:` sources) into the devenv venv. Works for all 7.
2. **Nix layer.** `modules/devenv.nix` declares `options.repoman.*` and **statically imports every**
   `modules/managers/<m>.nix`; each gates its own `config` on `cfg.enable && elem "<key>" cfg.managers`
   (imports can't read `config`, so import-all-gate-each — the standard idiom, confirmed at
   `modules/devenv.nix:29-36`). Each manager module contributes `tasks`/`scripts` and **may**
   contribute system `packages` / `languages.*` / `env.*`.

**The gap, confirmed:** nix-layer provisioning is bridged for **only** `git`, via **approach A**
(inline re-declaration in `gitman.nix`: `packages=[pkgs.git pkgs.maturin]` + `languages.rust.enable`).
Every other manager module wires *only* tasks (and `zelligate`/`mypi` add a single `pkgs.*` each).
CONCEPT §6 already anticipates this ("Managers may contribute nix-level provisioning") but only
gitman exercises it. SPIKE §"transitive nix inputs mostly not needed" concluded the nix layer rarely
matters *because tools arrive via venv* — **that conclusion is now partially refuted**: three
managers (`doc`, `spec`, `agent`) need real nix-layer provisioning (binaries/scripts/env/assets) that
a venv install cannot supply.

## Task 2 — Per-manager nix-provisioning audit

| key | repo | nix provisioning the **CLI** needs in a consumer | repo exposes a reusable module? | repoman pulls it through today? | gap | class & proposed fix |
|---|---|---|---|---|---|---|
| `copy` | copyroom | `git` **and** `patch` (gnupatch) on PATH — the CLI shells out (`doctor.py:56`, `workshop/edits.py:274`); `copier` console script (venv-provided, invoked as a subprocess) | **yes** `modules/copyroom.nix` (`options.copyroom.{enable,package}`, enable default `true`, imported by own `devenv.nix`) — but it **nix-builds the CLI** (we don't want that; repoman uses venv) | task-only (`status`); **no packages** | `git`/`patch` absent unless ambient | **(i) — approach A.** Add `packages=[pkgs.git pkgs.gnupatch]` gated on `copy`. Do **not** import copyroom's module (would double-provide the CLI). Optional `env.COPYROOM_CACHE_DIR`. |
| `test` | testee | only `git` on PATH (shared base); ruff/ty/pytest/pytest-json-report are **pip deps** resolved as venv-siblings (`adapters.py:23-35`, `pyproject.toml:18-21`) | `nix/testee.nix` exists but tasks/enterTest only, **no enable gating** | tasks + enterTest, no packages | none (git is a base concern) | **none — pure-Python.** Current module is complete/correct. |
| `git` | gitman | `maturin` + `languages.rust.enable` to build **pyjutsu** (PyO3). Verified **pure-Rust** chain (gitoxide/zlib-rs) — **no** openssl/pkg-config/libgit2/cmake needed. **Python ≥3.13** (both gitman & pyjutsu require it) | **no** toolchain module — `nix/gitman.nix` is tasks-only; provisioning is inline in its project `devenv.nix` | **yes (approach A)**: `pkgs.git pkgs.maturin` + `languages.rust.enable`, gated on `git` | **Python 3.13 pin missing** — repoman base pins 3.12 (`devenv.nix:42`), consumer-example pins none → latent build blocker at the Python layer | **(i) — keep approach A**, add `languages.python.version="3.13"` gated on `git` (or raise the consumer floor). Toolchain itself is complete & correctly minimal. |
| `doc` | docman | **venv**: `zensical==0.0.45` (pinned), python 3.13; **nixpkgs**: lychee, markdownlint-cli2, typos, git, gettext(`envsubst`); `docs-*` scripts; `env.DOCMAN_*`; `enterShell` runs `docs-init` to seed `.docman/zensical.toml` | **yes — `modules/docman.nix`, already import-ready**: `options.docman.*` + whole `config` wrapped in `mkIf cfg.enable` (`docman.nix:124`), imported by its own `devenv.nix` | task-only (doctor/build); **pulls none** | zensical + python + seeded config all absent → **3 hard doctor FAILs** | **(i) — approach B (import the module).** Import `modules/docman.nix`, bind `docman.enable` to `"doc"∈managers`. Consumer `devenv.yaml` must add `docman` + `nixpkgs-python` inputs (see Task 4 crux). |
| `session` | zelligate | `pkgs.zellij` (git/devenv intrinsic). **Plus** `ZELLIGATE_*` env defaults — without them the baked Docker-first config (`/workspaces`, `docker_mode=True`, `config.py:70-75`) makes doctor fail | `modules/devenv.nix` provides only a `zelligate-manifest` script + `zelligate.{enable,name,port}` — **orthogonal** (for a repo *being exposed to* a workbench, supplies no `zellij`/env) | **yes (approach A)**: `packages=[pkgs.zellij]` + tasks | env defaults not bridged → doctor FAILs on `/workspaces`; remaining checks are external | **mostly (ii), small (i).** Keep `pkgs.zellij`; **add `env` defaults** (workspace/state → in-repo paths, `ZELLIGATE_DOCKER_MODE=0`). The rest (Docker daemon, public host, running daemon, populated workspace) is (ii) — flag the upstream warn-vs-fail change. Importing the module is **not** a fix. |
| `agent` | mypi-agent | `nodejs_22`; `env` NPM_CONFIG_*/MYPI_*/`PI_CODING_AGENT_DIR` (doctor reads these); `scripts` mypi/pi/secretspec-setup; `pkgs.secretspec`; a bootstrap (`mypi sync` → npm-installs the `pi` runtime) | **yes — `modules/pi-agent.nix`** (`options.piAgent.*`, enable default `true`, `bootstrap.mode` enum, imported by own `devenv.nix`) | **partial (approach A)**: only `pkgs.secretspec` + tasks | node + env + scripts absent → the **(i)** doctor errors (npm-scope, node/npm, pi-not-on-path, resource dirs) | **(i) env/node/scripts — approach B with care.** Import `pi-agent.nix` with `bootstrap.mode="manual_only"`, `telegram.enable=false`, banner off. Keep `mypi sync` + real secrets user-driven **(ii)**. Watch the **CLI-shadow** risk (its `scripts.mypi` points at a nix-built mypi 0.5.1 that would shadow the venv mypi). |
| `spec` | allium-env | `allium-install-codex-skills` script (needs minijinja/git/bash/coreutils) + `env.ALLIUM_*` + the vendored asset trees it copies from. The third-party `allium` **binary is NOT needed** by the `alliman` CLI | **no — monolithic inline** `devenv.nix` (`options.allium.*` + everything in one 241-line file); needs extraction to `modules/allium.nix` | task-only; **pulls none** | script + env + assets absent → `install-skills` (script not on PATH) and `doctor` both fail | **(i) — approach B (extract, import, gate).** The worked plan in Task 5. **Blocker R4:** the asset trees are git-ignored → won't materialize through a `flake:false` input. |

### Notes worth carrying forward

- **copyroom is not pure-pip** (surprise): the CLI shells out to `git` and `patch`. Small, but real.
- **gitman's approach-A bridge is complete for the Rust surface** (verified, no hidden system libs) —
  it works *because the surface is tiny*. The only drift is the **Python 3.13 pin**, coupled today by
  a hand-written comment, not by import. This is the canonical argument for "A scales only for
  nix-light managers."
- **docman's module is the model B-class citizen**: namespaced, enable-gated, `mkIf cfg.enable`,
  imported by its own shell — repoman can import it *as-is*.
- **mypi's module is B-class but dangerous on defaults** (network npm at entry, writes to `$HOME`/repo,
  telegram install, `profiles.pi` auto-launch, CLI shadowing). Importable only with bootstrap/telegram/
  banner disabled.
- **allium-env is the only manager not yet modularized at all** — and additionally blocked by R4
  (git-ignored assets) and R5 (darwin placeholder hashes).

## Task 3 — Classification: (i) nix-bridge gap vs (ii) external requirement

**(i) repoman nix-bridge gaps — fixable by provisioning / pulling a module through:**
- `copy` — `git` + `gnupatch` on PATH.
- `git` — the Python **3.13** pin (toolchain itself already bridged).
- `doc` — `zensical` + `python` + the `enterShell`-seeded `.docman/zensical.toml` (all activate
  together when docman's module is imported).
- `agent` — `nodejs_22`, the `NPM_CONFIG_*`/`MYPI_*`/`PI_CODING_AGENT_DIR` env, the `mypi`/`pi`/
  `secretspec-setup` scripts (all from `pi-agent.nix`).
- `spec` — the `allium-install-codex-skills` script, the `ALLIUM_*` env, and the vendored assets.

**(ii) genuine external/host requirements — consumer/host must supply; doctor should WARN not FAIL:**
- `session` — a Docker daemon (not even doctor-checked), a routable `ZELLIGATE_PUBLIC_HOST` (already a
  warn), a running `zelligated` daemon, a populated workspace. The **hard FAILs** today
  (workspace-not-a-dir, state-not-writable) stem from the `/workspaces` defaults; once repoman sets
  in-repo `ZELLIGATE_*` env they pass. **Recommend upstream**: when `docker_mode` is off, downgrade
  workspace-missing/state-unwritable from FAIL→WARN.
- `agent` — the **real secret values** (off-repo `~/.config/mypi-agent/secrets/<slug>/.env`), the
  `mypi sync` network npm install of the `pi` runtime, and Telegram pairing. All correctly **warn**
  severity upstream already; must never be forced or hard-failed. repoman's "leave `mypi sync` to the
  user" stance is **right for the bootstrap, wrong for the env bridge** — bridge the env, keep sync
  manual.
- `spec` — effectively **none** once assets ship with the module; the `allium` binary is optional and
  out of scope for `alliman`.

## Task 4 — The general mechanism

### The crux: devenv.yaml `inputs` are **not transitive** across a remote module import

A consumer imports repoman via a `flake:false` path/git input. A manager's nix module (docman's,
mypi's, the extracted allium's) lives in a **different** repo. repoman's `modules/managers/<m>.nix`
can only `imports = [ ... ]` or reference `inputs.<manager>` if **the consumer's own `devenv.yaml`
declares that input** — devenv does not let an imported module pull its own inputs into the
consumer transitively (this was SPIKE's original open question; for venv-delivered tools it didn't
bite, but for nix-provisioned managers it does). Both the docman and allium audits hit this
independently. **Consequence:** the literal "one import" promise (CONCEPT §3) holds only for
nix-light (approach-A) managers; any approach-B manager requires the consumer to declare that
manager's repo as an input too.

Three ways to resolve it — recommend **(R2) with (R1) as the honest default**:

- **(R1) Consumer declares each approach-B manager's input** (repoman scaffolds it via `repoman init`
  / a documented `devenv.yaml` snippet, and `repoman doctor` *warns* when a selected approach-B
  manager's input is missing). Simple, explicit, no duplication; cost: repoman's composition leaks a
  few lines into the consumer's `devenv.yaml`.
- **(R2) repoman re-exports/vendors the manager modules** under its own `modules/` (git subtree or a
  thin generated re-export), so only the `repoman` input is needed — preserves "one import"; cost:
  duplicated nix code in repoman that must be kept in lockstep with each manager (a `repoman.lock`-
  style pin for modules).
- **(R3) flake-native transitive inputs** (convert managers to flakes repoman composes) — biggest
  blast radius, off-pattern for this family; not recommended now.

**Recommendation:** ship **(R1) now** (it's honest, low-risk, and unblocks spec/doc/agent
immediately), and design toward **(R2)** later if the input boilerplate proves annoying — gate the
choice on a tiny verification spike (confirm a `flake:false` module genuinely cannot reference an
input the consumer didn't declare). Either way, the **module contract below** is identical.

### Recommended overall shape: **Hybrid (option C)** — classify each manager

- **pure-Python (no nix module):** `test`. Venv install suffices; do nothing. State this explicitly.
- **nix-light (approach A — inline in repoman's `managers/<m>.nix`, gated on membership):** `copy`
  (`git`+`gnupatch`), `git` (rust+maturin+3.13 pin), `session` (`zellij`+env defaults). Cheap, few
  `pkgs.*`/`env.*`, no consumer input needed, acceptable drift risk because the surface is tiny.
- **nix-heavy / asset / fetched-binary (approach B — import the manager's own gated module):** `doc`,
  `agent`, `spec`. Rich provisioning (venv+scripts+enterShell+assets / node+env+scripts / fetched
  binary) that is impractical to re-declare and would drift. The manager **owns** it; repoman
  composes.

### The contract a manager repo must satisfy to be approach-B composable

1. **Module path:** `<repo>/modules/<manager>.nix` (or a `modules/` that re-exports it), importable
   `flake:false`.
2. **Single option namespace** `options.<ns>.*` with an **`enable`** flag (`mkEnableOption`) and the
   **entire `config` wrapped in `lib.mkIf cfg.enable`**. **Enable defaults to `false`** (opt-in) so a
   bare import is inert and repoman gates explicitly. (docman already complies; allium must flip its
   `true`→`false`; mypi defaults `true` and needs explicit opt-out of bootstrap/telegram.)
3. **The manager repo's own `devenv.nix` imports the module** and sets `<ns>.enable = true` (+ any
   defaults it relied on) so **standalone behavior is unchanged**.
4. **Heavy/optional sub-provisioning** (fetched binaries, network bootstraps, auto-launch profiles)
   behind **independent sub-options** (`cli.enable`, `bootstrap.mode`, `telegram.enable`, …),
   defaulting **off** for consumers.
5. **Any assets the module installs must be tracked in git** (not git-ignored) so a `flake:false`
   input materializes them into the nix store (allium R4).
6. **repoman side:** add the manager repo as a `flake:false` devenv.yaml input (R1) or vendor it (R2);
   statically `import` the module in `modules/managers/<m>.nix`; bind `<ns>.enable` to
   `"<key>" ∈ repoman.managers` inside a `config` block (imports can't read `config`); keep the
   `repoman:<domain>:doctor` task. Stays consistent with the family contract (managers own their
   domain; repoman composes; gated on membership; `0/1/2/3`).

## Task 5 — Worked fix for `spec` / allium-env (end to end)

**Goal:** in a consumer that selects `spec`, `allium-install-codex-skills` is on PATH, `ALLIUM_*`
env + vendored assets are present, so `alliman install-skills` and `alliman doctor` pass. (The
third-party `allium` binary is **not** required and stays opt-in.)

**Prerequisite blocker — R4 (do first):** `.vendor/allium`, `.skills/`, `.agents/` are **git-ignored**
in allium-env. A `flake:false` input is materialized from the git tree, so git-ignored asset dirs
won't reach the nix store and the installer will fail in a consumer. **Un-ignore / commit these asset
trees** (or vendor them into the module dir) before any wiring can work. This is independent of the
nix code and is the #1 practical blocker.

**Step A — extract a reusable module in allium-env** (`modules/allium.nix`). Move in: the `let`
bindings (asset paths, `shellSkillList`), the `alliumCliRelease` table + `alliumCli` derivation +
`system`/`systemSupported`, the whole `options.allium.*` block, and the `config` for `packages`,
`env.ALLIUM_*`, `scripts.allium-install-codex-skills`, and the `enterShell` freshness check. **Keep
OUT:** the `languages.python` editable-venv block + `alliManSrcPresent` guard (repo-local dev
convenience; repoman installs `alliman` from `repoman.lock`). **Flip `allium.enable` default
`true→false`.**

**Step B — allium-env's own `devenv.nix` imports it** (behavior-preserving): `imports =
[ ./modules/allium.nix ]; allium.enable = true; allium.specsDir = ".scratch/specs/allium";` and keep
the editable-venv block as-is. Net standalone behavior identical **iff** `enable=true` is set
explicitly and assets remain in place. (Also update `tests/consumer-example` input path — R6.)

**Step C — repoman's `modules/managers/alliman.nix` imports + gates** on `spec`:
- Add allium-env as a `flake:false` input in the consumer's `devenv.yaml` (R1) — repoman scaffolds
  it; `repoman doctor` warns if missing.
- `imports = [ <allium-env module> ];` (static); then
  `config = lib.mkIf enabled { allium.enable = true; allium.cli.enable = lib.mkDefault false; }` where
  `enabled = cfg.enable && elem "spec" cfg.managers`. Because the upstream `config` is
  `mkIf allium.enable` and now defaults false, a consumer **not** selecting `spec` activates nothing —
  and the lazy `fetchurl` for the `allium` binary is never forced (confirmed gating). Keep the
  `repoman:spec:doctor` task.

**Behavior-change risks to flag:** R1 enable-default flip (must land with allium-env's explicit
`enable=true`); R2 editable-venv must stay out of the module; R3 binary fetch stays double-gated
(`spec` membership + `cli.enable`); **R4 git-ignored assets** (hard blocker); R5 darwin placeholder
hashes (keep `cli.enable` off so non-spec/mac users never evaluate them); R6 consumer-example input
path.

**Validation:** in `tests/consumer-example` with `spec` selected: `repoman-sync` then
`repoman doctor` → `spec` section green; `command -v allium-install-codex-skills` resolves;
`command -v allium` only if `cli.enable` opted in.

### Sketches for the other (i)-class managers

- **doc (docman) — easiest B; do it right after spec.** Module is already import-ready. Import
  `modules/docman.nix`, bind `docman.enable` to `"doc"∈managers`; add `docman` + `nixpkgs-python`
  inputs to the consumer `devenv.yaml` (R1). The 3 hard FAILs clear once active (config self-seeds via
  `enterShell` `docs-init`). No extraction needed upstream.
- **agent (mypi) — B with safety options.** Import `pi-agent.nix` gated on `agent`, set
  `piAgent.bootstrap.mode="manual_only"`, `piAgent.telegram.enable=false`, banner off, and resolve the
  **CLI-shadow** (don't let its `scripts.mypi` override the venv `mypi` — likely set the script off or
  point it at the venv). Bridges the env/node/script gaps; keeps `mypi sync` + secrets user-driven.
- **copy (copyroom) — A.** `packages=[pkgs.git pkgs.gnupatch]` gated on `copy`; optional
  `env.COPYROOM_CACHE_DIR`. No module import.
- **git (gitman) — A (extend).** Add `languages.python.version="3.13"` gated on `git` (or raise the
  consumer floor) so the native build resolves; toolchain already bridged.
- **session (zelligate) — A (extend).** Add `env` defaults: `ZELLIGATE_WORKSPACE_DIR`/`_STATE_DIR`
  → in-repo paths, `ZELLIGATE_DOCKER_MODE=0`. Pursue the upstream warn-vs-fail downgrade for the (ii)
  checks separately.

## Open question for review (decide before implementing)

1. **R1 vs R2** for the input-transitivity problem — accept a few `devenv.yaml` input lines in the
   consumer (R1), or invest in repoman vendoring/re-exporting manager modules (R2)? Recommend R1 now.
2. **Upstream warn-vs-fail** changes in zelligate (and confirming mypi already warns) — in scope here
   or a separate per-repo follow-up? Recommend separate follow-ups, referenced from here.
3. **Quick verification spike** to confirm the non-transitivity assumption (and that a `config`-bound
   `<ns>.enable` import works as designed) before committing to the contract.
