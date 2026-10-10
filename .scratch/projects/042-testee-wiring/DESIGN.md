# 042 Testee wiring: design recommendation (revision 2)

Status: proposal. Nothing is implemented. Baseline: repoman `main@origin` efa1e92c (0.13.0), testee 1c139ecb (0.5.1).
Evidence: `01`–`16` in this directory. Labels: `verified` (command output or code cited), `inferred`, `unknown`.
Revision 1 recommended "self-launch" (enforce the project pin). Revision 2 replaces it. Section 3 says why.
**The canonical concept is now `testee/.scratch/projects/07-host-runner-and-receipts/CONCEPT.md`.** It adds the settled decisions:
commit-tree receipts, a containment floor, a venv that syncs itself, and a devman integrate hook.

## 1. Target architecture

**Testee is a host tool, the repo declares what to check, and every verdict is a receipt bound to a tree.**
One `testee` per machine runs the gate, like `gitman` and `copyroom`. The repo pins only the Testee **module**, as a locked
`devenv.yaml` input. The module declares the checks and the lowest runner version it accepts. Each run writes a receipt with the tree,
the manifest, the runner version and the result. `testee status` answers the agent's real question, "is this tree green?". RepoMan
treats `test` exactly like `copy` and `git`: a command on `PATH`, a minimum version, a skill and doctor rows.

| Concern | Owner | Mechanism |
|---|---|---|
| What to check | the repo | `testee.checks` in `devenv.nix`; the module comes from a `devenv.yaml` input locked by `rev` + `narHash` |
| Which runner versions the repo accepts | the repo (module) | `testee.requires` attribute, e.g. `">=0.6.0"`, outside the manifest |
| Running the gate outside the clean shell | Testee (host) | as today: eval, lock, tree record, `devenv shell --clean`, sealed report |
| Refusing an incompatible manifest | Testee (host) | read `testee.requires` in the same eval; exit 2 "this repo needs testee ≥ X; you have Y; upgrade with …" |
| Binding a verdict to a tree | Testee (receipt) | `report.json` records tree hash, manifest hash, runner version and store path |
| "Is this tree green?" | Testee | `testee status`: exit 0 only for a passing full gate on the current tree and manifest |
| The host install exists and is new enough | RepoMan doctor | `installed:test`, `version:test` (≥ 0.6.0) from a generic `min_version` field |
| When to ask | RepoMan router | "Run `testee status` before you integrate. Integrate only on exit 0." |

## 2. Why this design

1. **Testee is a harness, not a test subject.** Checks (ruff, pytest) define what a test means, and they come from the repo's locked
   environment. Testee runs them and aggregates the result. The common practice for a harness is the CI-runner model: record its version, do not pin it per repo (`inferred`, `05`).
2. **The only verdict flip we found favours a host tool.** The socket-stdin `PATH` bug was fixed by one host upgrade for every repo.
   Per-repo pins would need 23 bumps (`verified`, `07` cell 6, `03`).
3. **Enforcement cannot be complete anyway.** A stale environment that holds an unpatched 0.5.1 runs silently with exit 0, whatever the
   new design does (`verified`, `13` §2). Inside project A's shell, bare `testee` in project B is A's pin (`verified`, `16`). A receipt makes
   both cases visible. Enforcement does not prevent them.
4. **The real gap was the tree, not the version.** After a staged edit, `testee report` still printed `PASS (exit 0; full gate: yes)`.
   It also exits 0 on a partial pass. No saved file records the runner (`verified`, `16`, `07` finding 7). The receipt and `testee status` close this gap.
5. **The host entry keeps honest exit codes.** With a broken `devenv.nix` or a failed build, host `testee` exits 2 and writes a sealed report.
   `devenv shell -- testee` exits 1 and buries the cause in 23–141 KB of stderr. `devenv test` maps exit 2 to 1 (`verified`, `14`, `16`).
6. **The getFlake tag is not locked.** A moved tag gives mixed old and new code through devenv's eval cache. A `devenv.yaml` input locks
   `rev` + `narHash`, and Testee works as an input with no changes (`verified`, `12`).
7. **The fewest concepts, and a uniform manager contract.** All three managers become host commands with an optional floor. RepoMan deletes
   `modules/managers/testee.nix`, `REPOMAN_TESTEE_HOST_BIN`, `REPOMAN_TESTEE_VERSION`, `binary_env`, `version_env`, the profile `PATH` rewrite,
   the shadow check and the exact-version row. A trial of that removal passed 129/129 tests (`verified`, `09`). No `plane` or `source` field is needed (`16` §5).
8. **Enforcement stays possible later.** If several machines or CI ever need exact agreement, add an exact `testee.requires` or the
   self-launch hand-off (`08`, `13`). Receipts already carry the runner, so no redesign is needed.

## 3. Rejected alternatives

- **Self-launch (revision 1): the host hands off to the project pin.** It works (`verified`, `08`, `13`), but it adds a frozen launcher
  contract, three environment variables, a per-command fail policy and a realise step. It still cannot fix stale unpatched environments.
  It buys exact multi-machine agreement, which this one-host fleet does not need now.
- **Two planes (host and project tools).** The split is wrong for copyroom and gitman. A `plane` field duplicates the unused `nix_input` field and `provisioned:<key>` row (`16`).
- **No host install (`devenv shell -- testee`, `devenv test`, tasks).** These lose exit 2, bury the cause, add 0.2–0.3 s and noisy stderr, and have a signal-loss window (`verified`, `14`).
- **B. Exact-version handshake.** It polices equality, forces every machine to upgrade on every patch, and gives opaque errors on old hosts (`06`, `07`).
- **A. Keep and tidy.** Two `testee` on `PATH` and two verdicts (`07` cell 6).
- **RepoMan owns the Testee pin.** Devenv inputs do not pass through transitively (`16`, R1).
- **Pinned worker under a host supervisor.** Skew stays in five file protocols (`10` §2).

## 4. Change list and release order

### Testee 0.6.0 (first)
1. **Receipt.** `run.json` and `report.json` record `runner.version`, `runner.outPath`, `tree.start`, `tree.end`, `manifest.hash` and the result.
2. **`testee status`.** It exits 0 only if the latest full-gate receipt passed and its tree and manifest hashes equal the current ones.
   It exits 1 for red, stale or partial results, and exits 2 for no receipt or an infra fault. It prints one line: why, and the command to run.
3. **`testee.requires`.** Add a module option that is evaluated in the same `devenv eval` as `testee.manifestJson`. It is a separate
   attribute, so 0.5.x hosts ignore it (`verified`, `07` cell 4c). Too old: exit 2 with the required version, the actual version and the upgrade command.
4. **The module stops shipping a runner.** Remove `packages = [ package ]`, `testee:verify` and `enterTest`. Keep `testee.package` as a deprecated
   no-op with a warning for one release, because all 23 consumers set it (`03`).
5. **Readable errors.** If the module is missing, say "add the Testee input to devenv.yaml". For eval errors, strip ANSI codes and keep the cause
   line instead of the first 400 characters (`10` §3c, `14`). Wrapper-level failures write a sealed report too (`02`).
6. **CI.** Document `nix run github:Bullish-Design/testee/v0.6.0#testee -- verify --full`.
7. **ADR.** A new ADR supersedes "the module must supply the same Testee version inside the shell".

### Host (after Testee 0.6.0)
8. Install `testee` 0.6.0. Keep it at `~/.nix-profile/bin` until no repo runs RepoMan 0.13 or older, because their `repoman:test`
   hard-codes that path (`11` §1). Then move it into home-manager next to gitman, if wanted.

### RepoMan 0.14.0
9. Delete the items in section 2 point 7. Keep the venv half of the `enterShell` `PATH` line.
10. Add a generic registry `min_version` field. `test` sets `"0.6.0"`. One parser serves every manager. jj stays in `interface:git`.
11. `base:test` calls `testee check pytest`. The router adds one line: "Run `testee status` before you integrate. Integrate only on exit 0."
12. Update the tests, CHANGELOG (breaking: `repoman:test` and `repoman:test:ci` removed), README, CONCEPT, `docs/SKILLS.md` and the fixture comment (`09`).

### template-py 0.7.0
13. Render Testee as a `devenv.yaml` input with `follows` for nixpkgs and an `imports:` entry. Remove `getFlake` and `testee.package`. Snippets are in `12` §4.
14. Move the `copyroom.yml` guard to `devenv.yaml`: check the tag with a fixed regex (`12`), check the import, check that `getFlake` is absent. Drop the `repoman:test` ban.

### Fleet and devman (last)
15. **scopeman**: replace `base:test.after = ["repoman:test"]` (`devenv.nix:79`) in the same change as the RepoMan bump. Without it the shell does not start (`11` §2).
16. Other repos take the template update through copyroom when convenient. Delete the `testee.package` line within one release.
17. devman: make the central `testee` skill version-neutral and add `testee status`. Run `repoman-sync`.

## 5. Failure modes and what an out-of-date repo sees

| Situation | What happens |
|---|---|
| Two machines with different hosts | Verdicts can differ. Receipts name the runner, so the cause is visible. No prevention, by design. |
| Host older than the repo's `testee.requires` | Exit 2: "this repo needs testee ≥ X; you have Y; upgrade with …". |
| Host 0.5.x with a new module | The old host ignores `testee.requires` and runs. RepoMan doctor `version:test` flags the host as below 0.6.0. |
| Repo still on `getFlake` and module 0.5.1, host 0.6.0 | It works if 0.6.0 still accepts the v1 manifest (a release requirement). The in-shell 0.5.1 package stays on `PATH` until the template update. |
| Repo on RepoMan ≤0.13, host 0.6.0 | Tests run. `repoman doctor` `version:test` fails on exact equality. It gates nothing (`verified`, `11` §1). It clears on the RepoMan bump. |
| Repo bumps RepoMan but still calls `repoman:test` | The shell fails with "non-existent repoman:test" (`verified`, `11` §2). Only scopeman and repoman are affected. |
| Tree edited after a green run | `testee status` exits 1: "receipt is for tree X; current tree is Y; run `testee verify --full`". |
| A Testee release changes gate behaviour | Every repo sees the change at once. Testee must signal it in the version number and the CHANGELOG. |
| No host install (CI) | `nix run …#testee -- verify --full`. |

## 6. Not verified, and how to settle it

- **Inside a devenv task, does bare `testee` resolve to the host install once the module stops shipping the package and RepoMan drops its
  rewrite?** (`inferred` from `09` §3: the host entry stays on the inherited `PATH`.) This decides whether `base:check` keeps working. Test it in a scratch consumer before release.
- How `testee status` computes tree identity in a colocated jj repo (staged, untracked and ignored files). Reuse the runner's tree record (`provenance.py`) and test the edge cases.
- Whether 0.6.0 still accepts every v1 manifest that 0.5.x modules emit. Add a fixture test.
- The effect of `follows: nixpkgs` on the Testee input (`unknown`, `12`).
- macOS: the Testee flake is Linux-only (`verified`).
- Who owns a mechanical push gate. Integrate is native jj and gh, and gitman is work-only. Today the law is enforced by the router plus `testee status`. A hook is a separate decision.

## Process notes

- A wave 2 agent installed a prototype into the live `repoman/.devenv/state/venv`. I removed it (`verified`). Cause: the session exports
  `UV_PROJECT_ENVIRONMENT` and `VIRTUAL_ENV`. Wave 4 ran every command in a scrubbed environment.
- A wave 2 ssh probe added a `localhost` entry at `~/.ssh/known_hosts:174`. It is still there for the user to decide.
- A wave 4 agent ran a local `git daemon` on 127.0.0.1:29461 and killed it afterwards.
- Scratch directories remain under `/tmp/tw-*` and `/tmp/da-exp`. Built store paths remain until the next garbage collection.
