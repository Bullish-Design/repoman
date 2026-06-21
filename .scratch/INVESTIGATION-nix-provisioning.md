# Investigation: repoman managers don't pull their nix-layer provisioning into consumers

You're working in the **repoman** repo (`/home/andrew/Documents/Projects/repoman`),
the devenv meta-module that composes the `*man` manager family (copyroom, gitman,
testee, docman, zelligate, mypi-agent, allium-env). Sibling repos are at
`/home/andrew/Documents/Projects/<repo>`.

## Symptom (reproducible)

A consumer repo (`karakeeper`) adopted repoman with the full roster
(`repoman.managers = [ "copy" "git" "test" "doc" "session" "agent" "spec" ]`),
ran `repoman-sync`, and then `repoman doctor`. Results:

- ✅ self-check (lock + venv installs + skills) all OK
- ✅ `test` (testee) green; `git` (gitman) toolchain present (native pyjutsu builds)
- ❌ `spec` (alliman): `allium-install-codex-skills` **not on PATH**; skills/prompts not installed
- ❌ `agent` (mypi), `session` (zelligate), `doc` (docman): doctor failures

Concretely for `spec`: `devenv shell -- alliman install-skills` fails because it
shells out to `allium-install-codex-skills`, which **does not exist in the consumer
shell**. The `allium` CLI binary is also absent.

## Root-cause hypothesis

repoman bridges **two layers** (see `CONCEPT.md` §6 and `SPIKE.md`):

1. **Python/venv layer** — `repoman-sync` reads `repoman.lock` and `uv pip install`s
   each selected manager's package into the devenv venv. This works for all managers.
2. **Nix layer** — system packages, fetched/built binaries, `devenv` `scripts.*`,
   `env.*`, `languages.*`, and `enterShell` hooks that a manager needs.

The nix layer is **only** bridged for gitman, and only by **hand-replicating** its
needs inline: `modules/managers/gitman.nix` adds `packages = [pkgs.git pkgs.maturin]`
+ `languages.rust.enable`, gated on `"git" ∈ managers`. Every other manager module
(`modules/managers/*.nix`) wires *only* a doctor/status task and contributes **no
nix provisioning**. So any manager whose tool needs nix-level setup is broken in
consumers.

Worked example — **allium-env**: its `devenv.nix` defines, as an inline monolithic
module (`options.allium.*` + `config`):
- a `scripts.allium-install-codex-skills` (the installer the `alliman` CLI calls),
- an `alliumCli` `fetchurl` + `mkDerivation` that puts the pinned `allium` binary on PATH,
- `env.*` (ALLIUM_CODEX_SKILLS_DIR, …) that `alliman doctor` reads,
- an `enterShell` asset-freshness check.

None of this is exposed as an importable module, and repoman's `modules/managers/alliman.nix`
doesn't pull any of it through. So `spec` only half-works: the Python CLI installs,
but the tooling it drives is missing.

## Already-observed evidence (from the karakeeper consumer)

While trimming karakeeper's roster to the working set, two more managers showed the
same nix-layer gap — record these so you don't rediscover them:

- **git (gitman):** `repoman-sync` installs gitman + pyjutsu fine, but `gitman init`
  and `gitman status` deadlock — `gitman doctor` reports HEALTHY (`.git + .jj present`,
  filesystem check) while `init`/`status` (pyjutsu-based) say "not a colocated jj repo"
  / "repo not initialized". Root cause: **pyjutsu embeds jj-lib 0.38.0, but the only
  `jj` CLI obtainable (`pkgs.jujutsu`) is 0.42.0**; the `.jj` store jj 0.42 writes isn't
  openable by jj-lib 0.38. gitman's own devenv ships **no** jj CLI ("talks to jj-lib
  in-process via pyjutsu"), so a consumer can't bootstrap the colocated workspace at a
  compatible version. Fix likely: gitman provisions a jj CLI pinned to its jj-lib
  version, or bootstraps colocation via pyjutsu directly (no CLI).
- **doc (docman):** doctor wants `zensical` on PATH, but zensical is declared nowhere
  (not in docman's pyproject deps nor its devenv.nix) and isn't installed by repoman-sync.

Net: in a fresh consumer only **testee** (and copyroom, which has no doctor) is green
out of the box. Every other manager has a nix-layer provisioning gap.

## Scope

Audit **all seven managers**, not just spec: `copy` (copyroom), `git` (gitman),
`test` (testee), `doc` (docman), `session` (zelligate), `agent` (mypi-agent),
`spec` (alliman/allium-env).

## Central architectural question

How should a manager's **nix-layer provisioning** reach the consumer devenv when
that manager is selected? Options to evaluate:

- **(A) repoman re-declares it** inline per manager module (the current gitman approach).
  Simple for `[pkgs.x]`, but doesn't scale to fetched binaries + scripts + assets
  (allium-env), and duplicates the manager's own nix logic.
- **(B) Each manager repo exposes a reusable devenv module** (e.g. `modules/<manager>.nix`
  with `options`/`config`), and repoman's `modules/managers/<m>.nix` **imports it**,
  gating its activation on roster membership. The manager owns its provisioning;
  repoman composes. (The user's stated intent: "update allium-env so it pulls in
  allium-env's nix module correctly via repoman.")
- **(C) Hybrid** — pure-pip managers need nothing; native/asset managers expose a module.

Recommend one, justify it, and note migration cost.

## Investigation tasks

1. **Map the mechanism.** Read `modules/devenv.nix` (the meta-module: imports, options,
   `REPOMAN_MANAGERS`, repoman-sync wiring), `modules/managers/*.nix`,
   `modules/scripts/repoman-sync.sh`, `registry.py`, `CONCEPT.md` §6, `SPIKE.md`,
   and `tests/consumer-example/` (the canonical consumer). Confirm/refute the two-layer
   model above.

2. **Per-manager nix-provisioning audit.** For each of the 7 managers, inspect its repo
   (`../<repo>/devenv.nix` and any `modules/`) and produce a row:
   | manager | nix provisioning its tool needs (pkgs / binaries / scripts / env / languages / enterShell) | does the repo expose a reusable module? | does repoman's `managers/<m>.nix` pull it through today? | gap | proposed fix |

3. **Classify each failure** as either:
   - **(i) repoman nix-bridge gap** — fixable by pulling the manager's nix module through, vs
   - **(ii) genuine external requirement** the consumer/host must provide (e.g. zelligate
     may need Docker + a `/workspaces` dir + `ZELLIGATE_PUBLIC_HOST`; mypi may need an
     external `pi` binary + secretspec secrets). Don't propose "fixes" for (ii); instead
     specify what the consumer must supply and whether doctor should *warn* rather than *fail*.

4. **Design the general mechanism** (answer the central question). Define the contract a
   manager repo must satisfy to be composable at the nix layer (module path, option
   namespace, how repoman imports + gates it, how it interacts with `repoman.lock`/venv).
   Keep it consistent with the family contract (managers own their domain; repoman composes;
   gated on membership; `0/1/2/3` exit codes).

5. **Worked fix for spec/allium-env** end to end: what to change in allium-env (expose its
   nix wiring as an importable module without breaking its own standalone devenv) and in
   repoman's `alliman.nix` (import + gate it), so `allium-install-codex-skills` and the
   `allium` binary land in a consumer and `alliman doctor`/`install-skills` pass.

## Deliverables

- A written findings doc (propose `.scratch/` in the repoman repo) containing: the two-layer
  confirmation, the per-manager audit table, the (i)/(ii) classification, the recommended
  general mechanism with rationale and trade-offs, and a concrete step-by-step fix plan for
  **spec** (and a sketch for any other (i)-class managers).
- **Do not implement yet** — investigation + plan only, for review. Flag any change that would
  alter a manager repo's own standalone devenv behavior.

## Constraints / principles to honor

- Manager nix provisioning must stay **gated on roster membership** — a repo that doesn't
  select `git` must never pull Rust; one without `spec` must never fetch the allium binary.
- Prefer the manager repo **owning** its provisioning over repoman re-declaring it.
- `imports` can't depend on `config`, so the established idiom is "import all manager modules
  statically, gate each one's `config` on membership" — keep this.
- Some managers are pure-Python (pip-only) and need **no** nix module; say so explicitly.

## Validation criteria (for the eventual fix, not this pass)

In a consumer (`tests/consumer-example` or `karakeeper`):
`devenv shell -- repoman doctor` exits 0 (or only (ii)-class warnings), with
`allium-install-codex-skills` and `allium` on PATH and `alliman doctor` green.

## Key files
- `modules/devenv.nix`, `modules/managers/{gitman,alliman,testee,copyroom,docman,zelligate,mypi}.nix`,
  `modules/scripts/repoman-sync.sh`, `registry.py`, `CONCEPT.md`, `SPIKE.md`, `tests/consumer-example/`
- Manager repos: `../{copyroom,gitman,testee,docman,zelligate,mypi-agent,allium-env}` (esp.
  `allium-env/devenv.nix` — the worked example: `options.allium.*`,
  `scripts.allium-install-codex-skills`, the `alliumCli` derivation, `env.*`, `enterShell`).
- All in-repo commands run via `devenv shell -- <cmd>` (never bare, never wrapped in `bash -c`).
