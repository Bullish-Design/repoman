# Project 039 — repoman half: final report

Session date: 2026-09-15 → 2026-09-16. Scope: `REPOMAN_PROMPT.md`, the repoman
half of "remove repoman from per-repo pins." The vendomat half is a sibling
document (`VENDOMAT_PROMPT.md` / its own stage log) and is not covered here.

## 1. Starting point

Twenty-five repositories declared repoman directly in their own `devenv.yaml`,
each pinning a separate revision (or an unpinned local path). The goal: one
machine-owned pin in `nix-meta`, delivered to every consumer through the
central `devman` overlay, with the per-repo manager roster moved to a small
tracked manifest (`.repoman/project.toml`) instead of a `devenv.nix` option
block.

## 2. What shipped, phase by phase

### Phase 0 — the fixture experiment

Built a throwaway `/tmp` fixture reproducing the shape of a machine-delivered
module (imported by absolute path, not through a `devenv.yaml` input name) and
evaluated it with `nix-instantiate`. Confirmed that `inputs` still resolves
correctly in that shape — `specialArgs` is set once for the whole
`lib.evalModules` call, regardless of how a module file entered the `modules`
list. The suspected trap (repoman's transitive `shellij`/`docman` imports
breaking under machine delivery) does not exist. No prerequisite phase needed.

### Phase 1 — package and install the module

- `flake.nix`: added `packages.repoman-module` (installs `modules/` to
  `$out/share/repoman/module/`), `nixosModules.default` (with
  `repoman.installConsumerModule`, default `true`, and the required
  `environment.pathsToLink = [ "/share/repoman" ]`), and
  `checks.repoman-consumer-module` (proves the packaged module file exists,
  `builtins.functionArgs` evaluates, and a fixture consumer with no manifest
  resolves the default roster).
- `nix-meta`: added the `repoman` flake input, wired
  `inputs.repoman.nixosModules.default` into `machines/server.nix` next to the
  existing `vendomat` wiring.
- Verified end to end: `nix build .#nixosConfigurations.server.config.system.build.toplevel`
  succeeded locally and the resulting closure carried the module at
  `share/repoman/module/devenv.nix`. **You ran `nixos-rebuild boot` +
  `switch`** (twice, once per repoman release — see §4); each time I verified
  `/run/current-system/sw/share/repoman/module/devenv.nix` was present and
  `readlink -f` matched the store path I had predicted from the local build.

### Phase 2 — manifest-driven module

- `modules/devenv.nix` now reads `.repoman/project.toml` under
  `${config.devenv.root}` (schema 1, `managers = [...]`), with the same
  discipline as `devman/src/devman_contract/manifest.py`: fixed field set,
  unknown fields rejected, `managers` values checked against the same enum the
  option already used. Absent file → default roster `["copy" "git" "test"]`.
- `repoman.managers`' option default now resolves from the manifest when
  present, else the pre-039 default; an explicit `repoman.managers = [...]`
  in a consumer's `devenv.nix` still wins (kept for one release as a
  compatibility fallback, per the same pattern `devman/modules/link.nix`
  uses for `config.devman.project`).
- Deleted three genuinely dead options — `template`, `installSkills`,
  `skillsDir` (the third's behavior is now a hardcoded constant, since no
  repository ever overrode it). **Did not** delete `toolchainBin`: despite
  appearing in the prompt's "0 repos set it" table, it is `internal = true`,
  `readOnly = true`, and load-bearing (every shared manager module
  interpolates `cfg.toolchainBin`) — the "0 repos set it" fact is explained by
  it never having been settable, not by it being unused.
- Committed this repository's own `.repoman/project.toml`
  (`["copy" "git" "test" "doc"]` — repoman is one of the eight roster
  exceptions).

### Phase 3 — consumer migration (partial, by design)

Twelve repositories fully migrated — pin removed, manifest added where the
roster differs from default, central overlay wired, verified, landed, pushed:

| Repo | Roster | Notes |
|---|---|---|
| nix-secrets | `[copy git]` | manifest added |
| llgym | `[copy git test]` (default) | |
| image-gen-pipeline | `[copy git test]` (default) | |
| shellij | `[copy git test]` (default) | kept `cliProvider = "venv"` |
| poddantic | `[copy git test]` (default) | kept `cliProvider = "venv"` |
| pyllij | `[copy git test]` (default) | kept `cliProvider = "venv"` |
| eventic | `[copy git test]` (default) | kept `cliProvider = "venv"` |
| argentic | `[copy git test]` (default) | kept `cliProvider = "venv"` |
| flora-qc | `[copy git test]` (default) | no explicit options originally |
| loci.nvim | `[copy git]` | manifest added, kept `cliProvider = "venv"` |
| flora | `[copy git test]` (default) | kept `cliProvider = "venv"` |
| tyo3 | `[git]` | manifest added; needed `SECRETSPEC_REASON` to enter its shell (pre-existing repo gate, unrelated) |

Five repositories were attempted and reverted cleanly (working tree restored,
lanes abandoned) because of **pre-existing problems unrelated to repoman**:

| Repo | Blocker |
|---|---|
| agentman | Never onboarded to devman's link plane at all — no `.devman/project.toml`, `.envrc`, or central `devenv.local.nix` |
| inferference | Same — not onboarded |
| talkee | `devman.link` double-declared: the repo still directly imports `devman/modules` in its own `devenv.yaml` **and** the central overlay imports `devman`'s `link-module.nix`. Fixed the same defect in other repos (it was the point of the already-prepared `038-devman-consumer-*` lane); talkee has no such lane and the fix wasn't attempted after a deeper, still-unexplained `devman.enable` failure surfaced in devenv's internal "profiles" bootstrap machinery |
| flora-core | Pre-existing `ruff` import-order failure in `src/flora_core/__init__.py`, confirmed via `git diff` to predate this session |
| paloma-text-pipeline | Pre-existing `ty` type error in `src/paloma/constraints/core.py`, confirmed via `git diff` to predate this session |

Four repositories were skipped by explicit instruction (the `nix-*` set):
`nix-desktop`, `nix-nvim`, `nix-paseo`, `nix-terminal` (the last also has its
own `modules/repoman.nix` home-manager wrapper — a different consumption
shape, flagged in the prompt for separate treatment).

Two repositories are out of scope by design: `forgelab` and `lodestar` (the
archive set — never touch, per the prompt).

### Phase 4 — collapse the remaining pins

Verified by sweeping every `devenv.yaml` under `~/Documents/Projects/*` for a
`repoman:` input. Exactly the expected set remains:

- `nix-meta/flake.nix` — the machine pin, now `v0.8.1`.
- `vendomat/flake.nix` — the toolchain-build pin (`v0.7.5`), correctly left
  untouched; the repository that builds `repoman-uv2nix-cli` must pin the
  toolchain it builds.
- `repoman/devenv.yaml` — the self-host, `path:./modules`, correctly kept.
- The five blocked repos, the archive set, and the `nix-*` skip set — all
  expected, all already accounted for above.

No unexpected repository still names a stale repoman revision.

### Phase 5 — untrack the router skill

Checked whether `.agents/skills/repoman/SKILL.md` is still tracked as a static
file anywhere in the fleet. It is **not** tracked in any of the twelve
migrated repositories — devman's own earlier `.agents` central-link migration
(which each of those repos had already been through) moved the whole
`.agents` tree to a symlinked central path before this session started, so
Phase 5's stated problem was already solved for every repo this session
touched. Fleet-wide, only three repos still track it: `agentman` and
`inferference` (same devman-onboarding blocker as Phase 3), and `lodestar`
(archive set, don't touch). No new work was needed or performed here.

## 3. The bug found and fixed along the way

Verifying `nix-secrets` after its pin removal showed `REPOMAN_MANAGERS` was
completely unset — repoman was silently **not running** despite the migration
looking correct. Root cause: `options.repoman.enable` was still declared with
`lib.mkEnableOption` (default `false`). That was correct when the module was
*always* imported (the old per-repo `devenv.yaml` pin) — an explicit
`repoman.enable = true;` was the real signal. Once the module is only present
when a consumer's central `devenv.local.nix` imports it, presence of that
import needed to *be* the enable signal (the same pattern `shellij` and
`docman` already use), so the pre-039 Phase-3 instruction to delete the whole
`repoman.*` block silently disabled every migrated consumer.

Fixed by changing the default to `true` (`repoman.enable = false;` still
opts a repo out explicitly if ever needed). This required a full second
release cycle:

- `modules/devenv.nix` fixed, released as `v0.8.1`.
- `nix-meta` re-pinned to `v0.8.1`, rebuilt locally, **you ran
  `nixos-rebuild switch` a second time**.
- Confirmed live (`REPOMAN_MANAGERS=copy git` for `nix-secrets` with a clean
  environment) before any further consumer migration proceeded.
- Re-ran `repoman-sync --machine` to refresh stale machine toolchain metadata
  (`repoman doctor` had flagged the version skew).

Every one of the twelve migrated repos was verified (or re-verified) against
the fixed `v0.8.1`, not the buggy `v0.8.0`.

## 4. Process notes worth keeping

- **The fleet-lock trap is real and fires on nearly every push.** Any
  `devenv shell` invocation rewrites `devenv.lock` with the machine's local
  `devenv.local.yaml` overlay paths baked in. Fix is always `relock`
  (temporarily hides the overlay, runs `devenv update`, restores it) run
  **immediately before** `gitman save`, with no `devenv shell` calls in
  between — otherwise the very next shell entry re-dirties the lock before the
  commit lands. Chaining `relock && gitman save && gitman land && gitman push`
  inside one `devenv shell -- bash -c '...'` invocation is the reliable shape.
- **`gitman start`/`subtask` can adopt more than intended.** Twice this
  session (once in `repoman` itself, once nearly in `nix-secrets`) a stray
  pre-existing uncommitted changeset got pulled into a new lane alongside the
  intended change. The fix each time was `git diff --stat main -- <files>` to
  confirm scope before saving, not to trust the lane's diff blindly.
  `gitman subtask` onto an existing `038-devman-consumer-*` lane occasionally
  hit a transient "change belongs to no lane" ref-locking error; `gitman
  reconcile` always repaired it without discarding anything, though it
  sometimes revealed that the lane's content had *already* been merged to
  trunk via an out-of-band PR, making the lane safely abandon-able.
- **A repo's own environment (secretspec, missing tasks, etc.) can block
  verification** independent of repoman. `tyo3` needed
  `SECRETSPEC_REASON` set to enter its shell at all; several repos have no
  `base:check` task and needed their actual lint/quality script named
  directly.
- **Central overlay edits were left uncommitted by design.** Several
  `~/.config/devman/projects/<repo>/devenv.local.nix` edits (adding the
  repoman module import) were applied to the working tree but not committed —
  `~/.config/devman` itself carries many unrelated in-progress lanes across
  other projects, and bundling a one-line addition into that shared repo's
  history was judged the user's call, not mine, each time it came up.

## 5. Ending status

- **repoman** itself: `v0.8.1` released, machine-packaged, manifest-driven,
  `enable` defaults correctly. All flake checks green.
- **nix-meta**: pinned to `v0.8.1`, switched, confirmed live.
- **12 of 23 originally-scoped consumers**: fully migrated, verified, on
  `origin/main`.
- **5 consumers**: attempted, cleanly reverted, blocked on problems this
  project did not create and was not scoped to fix.
- **4 `nix-*` consumers + `nix-terminal`'s wrapper**: untouched by explicit
  instruction.
- **2 archive-set repos**: correctly never touched.
- **Phase 4 and Phase 5**: both verified complete for everything in scope —
  no further action identified.

Nothing is stuck mid-migration: every touched repository is either fully
migrated and pushed, or fully reverted to its original state. The remaining
work is entirely the five blocked repos (each needs its own unrelated fix
first) and, if wanted later, the `nix-*` set and `nix-terminal`'s separate
wrapper shape.
