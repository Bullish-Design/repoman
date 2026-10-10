# 16 Devil's advocate 3: the "two planes" concept

Labels: `verified` (command output or code cited), `inferred`, `unknown`.
Sources: notes 01 to 11 and DESIGN.md in this directory; snapshots in `/tmp/tw-trunk/{repoman,testee,template-py,copyroom,gitman}`.
My experiments: `/tmp/tw-w4e/` (read-only on all repos; scrubbed env; no jj/git writes outside `/tmp`).
Host: devenv 2.4.0, NixOS, host `testee 0.5.1`. Fixtures: `p1` (Testee as a `devenv.yaml` input), `p3` (shell cannot build),
`p4` (pins a different Testee store path), `q_red`, `q_infra` (a failing check, a malformed structured file).

## 0. Verdict in five lines

1. "Two planes" does not survive as a concept. Every invariant it claims is held by the hand-off (launcher), and the hand-off is the
   self-launch mechanism of DESIGN.md. The planes name where a binary sits. The hand-off makes that place irrelevant.
2. Keep three parts of it: the Testee pin in `devenv.yaml`/`devenv.lock` (works today, verified), the hand-off, and the lean RepoMan row.
3. Drop four parts: the word "plane", the registry field `plane`, `devenv test` as the CI door, and "no host install" as a design goal.
4. Add the one thing no plane design has: a tree-bound verdict (a receipt) and a command that reads it. Without it, "never integrate on red" has no check.
5. Replacement concept: **the tree names its verifier** (section 3, candidate A). It is DESIGN.md plus the lock pin plus the receipt.

## 1. Attacks on the concept

### 1.1 The hand-off is not optional, so the host/pin mechanism is not removed (verified, inferred)

- `verified` Inside the activated shell of project A, standing in project B, bare `testee` is A's pin, not B's.
  Run: `devenv shell -- bash -c 'cd /tmp/tw-w4e/p4; command -v testee'` in `p1` printed `.../rs4i9wy1...-testee-0.5.1/bin/testee`.
  `devenv eval testee.package.outPath` in `p4` printed `.../rcv33z0w...-testee-0.5.99`. The claim "inside an activated env bare `testee` is the pin"
  holds only for the tree that built the env. An env belongs to a shell session. A tree belongs to a directory. They differ whenever an agent changes directory.
- `verified` This session is the example. The inherited `PATH` holds `repoman/.devenv/state/venv/bin` and `testee-0.5.1/bin`, and the agent works on other directories.
- `inferred` Nobody reloads an agent env. direnv reloads at an interactive prompt (`~/.config/devman/common/envrc` uses `use devenv`). An agent tool call does not run a prompt.
- `inferred` The change under test can be the pin bump itself (a lane edits `devenv.yaml` or `devenv.lock`). The old env then verifies the new pin with the old pin.
  Only the hand-off checks the right code. This is the case the law cares about most.
- Conclusion: the hand-off evaluates the tree, finds a pin, and `exec`s it. That is the host-launcher design with a different start point.
  The plane model adds a second way to get a correct binary (the env) next to the first (the hand-off). Two mechanisms hold one invariant.

### 1.2 The hand-off needs a host tool and an up-to-date first hop (verified, inferred)

- `verified` The hand-off runs `devenv eval` and `nix-store --realise` (DESIGN F4, F5; `10` §1.6). `devenv` and `nix` are on the PATH of a normal `devenv shell`
  (host PATH is inherited) but not in `devenv shell --clean` (`command -v devenv nix` returned rc=1 in `p1`). The "project plane" binary therefore depends on a "host plane" binary to name itself.
- `verified` All 23 fleet pins are v0.5.1 and carry no hand-off code (`03` §1). With planes only, the first hop in each repo is the pin itself.
  A 0.5.1 pin cannot hand off. The stale-env and cross-project cases stay unsolved in a repo until that repo bumps to a launcher version.
- `verified` The host-launcher design fixes all 23 repos with one host install (`08` test 1: the launcher ran unchanged 0.5.0 and 0.5.1 pins).
  The plane design needs 23 repo edits plus the template. During that time the invariant "I am the pin of the tree" is false for old pins.
- `inferred` Any hand-off needs one trusted first hop whose version the tree does not control. A project pin cannot be that hop. This is why Gradle vendors its wrapper
  into the tree and Bazelisk sits outside it (`05`).

### 1.3 `devenv shell -- testee` loses the red/could-not-run split (verified)

I ran the same projects through four doors. Exit codes:

| Door | `q_red` (a check fails) | `q_infra` (malformed structured file) | `p3` (shell cannot build) |
|---|---|---|---|
| host `testee verify --full` | 1 | 2 | 2, sealed `INFRA` report, `wrapper_error` |
| `devenv shell -- testee verify --full` | 1 | 2 | **1**, no run directory, no Testee output |
| `devenv test --no-tui` | 1 | **1** | not run |
| `devenv tasks run --no-tui testee:verify` | 1 | **1** | not run |

- `verified` (`/tmp/tw-w4e/bin/modes.sh`, `p3.err`). `devenv shell -- testee` keeps 0/1/2 when the env builds. When the env does not build, devenv exits 1,
  the same code as a failed check. The agent sees a build error and no Testee line. Exit 1 is on the safe side for the law (no integrate), but it breaks "honest".
- `verified` `devenv test` and `devenv tasks run` map Testee's exit 2 to 1 on every path. The concept names `devenv test` as the CI door. CI then cannot tell red from could-not-run.
  A flaky infra fault looks like a failing test.
- `verified` Cost of the shell door: `devenv shell -- testee --version` 0.48 to 0.50 s warm (3 runs). `verify --full` 1.34 and 1.46 s against 1.13 s for the host command (1 run each, noisy).
  About +0.3 s. A nested clean shell works: containment `strong`, report written. The cost is small.
- `verified` Progress output: 20 stderr lines per call with `TERM=dumb` and no tty. `unknown` whether a tty draws the full-screen UI (`AGENTS.md` demands `--no-tui` for tasks and tests).
  My `script` probe did not execute, so I did not measure it.
- `inferred` The shell door builds the whole outer shell on every call. Anything in the tree that breaks the outer shell now also hides Testee's sealed report.
  The ADR's reason for starting outside (the supervisor outlives a broken shell) is exactly this case (`02` §7; `10` §3a).

### 1.4 The stale-env hand-off is needed only because the front door is a PATH name (inferred)

If the front door is always `devenv shell -- testee`, devenv builds the env from the tree on each call (cached eval, 0.5 s). The env is then fresh by construction and no hand-off is needed.
The concept keeps both doors (bare in env, shell from outside) and adds the hand-off to repair the first. It buys the cheap door (bare) and pays with a launcher.
Choose one. A pure shell door costs the honest exit code (1.3). A pure hand-off costs nothing at runtime (DESIGN §2 point 4). So the hand-off wins, and the env door becomes a fallback.

### 1.5 "Project plane" does not fit RepoMan's CLI or devman's skill pool (verified, inferred)

- `verified` RepoMan's module is imported as `flake: false` with `dir=modules` (`devenv.yaml`). That input has no package output, so no CLI can come from it.
  The module (pinned per repo in `devenv.lock`) and the CLI (host profile or venv) have two pins. No doctor row compares them (`01` §6 lists the rows). `inferred`: the skew class that the
  concept removes for Testee is open for RepoMan's own CLI.
- `verified` `repoman` and `copyroom` are not on this host's profile today: `which repoman copyroom` fails under the scrubbed `PATH`; `/etc/profiles/per-user/andrew/bin` has `gitman`, `jj`, `devenv`, no `copyroom`.
  agentman's venv has no `repoman` either (`ls .devenv/state/venv/bin`). `repoman-sync` exits 2 when `repoman` is missing (`modules/scripts/repoman-sync.sh` (the `command -v repoman` check)). `unknown` how fleet shells get it
  (the Vendomat V5 host switch is owner-side and unfinished, per memory). The "host plane" list in the concept is partly aspirational.
- `verified` The skill pool is host-level: `~/.config/devman/skills/testee/SKILL.md` is one file for all repos. It says "Testee 0.5.0" and "puts `testee` on `PATH` before devenv starts".
  A tool in the project plane can have one version per repo. A skill in the host plane has one text for all. The skill documents the CLI grammar, which changes between versions
  (the 0.4 to 0.5 break removed `--mode`, `fix`, `--changed`). No plane design fixes this. Make the skill thin (point at `testee --help` and `testee doctor`) or let the pin print it.
- `verified` RepoMan already has the vocabulary: `Manager.install` ("path" or "uv"), `Manager.nix_input` and the doctor row `provisioned:<key>` (`registry.py:49-58`, `checks.py:369-391`, tests at
  `test_checks.py:207-220`). A new `plane` field is a third word for what `nix_input` already says. `CONCEPT.md` calls this "approach B". No manager uses it today (`04` deviation 11).
- `verified` `CLAUDE.md` and `AGENTS.md` already use "automation plane" for devman. A new "host plane / project plane" would collide with it.

### 1.6 Does the plane split hold for gitman and copyroom? No (verified, inferred)

- `verified` The stated test is "tools that act on or across repos". RepoMan's own concept says copyroom "has no cross-repo command" (`CONCEPT.md` §2) and gitman opens one workspace for one repo. All three managers act within one repo.
- `verified` The real reason `jj` is host-level is repo state, not reach. gitman ships `jujutsu-bin` because two jj versions break one repo's op log (`04` deviation 9). A per-project jj pin would let two lanes write one `.jj` with two versions.
- `inferred` The useful criterion is: "does the tool read a definition the tree declares, whose meaning depends on the tool version?" Testee: yes (checks, manifest). devenv: yes.
  ruff, pytest: yes (config). gitman, jj: no (host-wide state format). copyroom: weak. The tree stores a template ref (`_commit: v0.5.0` in `.copier-answers.yml`) and a schema number (`copyroom.version: 1`), not a tool pin.
  Observed drift is cosmetic (copyroom 0.8.0 against a 0.7.7 string, `04`).
- `unknown` Whether copyroom ever needs a project pin. No source shows a defect from copyroom skew. Do not build a family guard for it (agree with `10` §3b).
- `verified` devenv has the same shape as Testee and stays a host tool: `require_version` in `devenv.yaml` constrains the CLI against the modules (`05`). The plane model does not move devenv.
  The root of the chain is always a host tool. The model relocates the skew, one level up, for the tool it cannot move.

### 1.7 `plane` in the registry (inferred)

- `verified` Vendomat V5 ruling (memory): RepoMan runs managers by name from `PATH` and reads no closure or manifest. A `plane` field gives RepoMan provisioning knowledge to print one fix line.
- `inferred` The fix text belongs to the tool. `testee doctor` can print "pin Testee in `devenv.yaml`". RepoMan can say "command not found: testee, see the testee skill".
  If RepoMan must know, use the existing `nix_input` (non-empty means a repo input provisions it). Do not add a field.

### 1.8 What the lifecycle law needs and nothing here supplies (verified)

- `verified` Nothing enforces "never integrate on red". Integrate is native `jj` and `gh` (`CONCEPT.md` §5). gitman 0.12 has one verb, `work` (memory). `.git/hooks` holds only samples in every repo (`11` §1).
  No fleet CI runs Testee (`03` §1). The law is router text. The `gitman.toml` key `[publish] verify` is present in 8 repos and read by nothing known (`03` §7.9).
- `verified` `testee report` is not a tree-bound verdict. Test in `p1`: after a green full gate, I staged a new file. `testee report` still printed `PASS (exit 0; full gate: yes)` and returned the saved exit code.
  `cli.py:193-204` never compares the saved `source_tree_*` with the current tree. After a partial run (`testee check ok`), `testee report` exits 0 with `PASS (PARTIAL: 1 of 1 ...)`. An agent that reads exit 0 integrates on a stale or partial green.
- `verified` No saved file records the runner (`07` finding 7). A report cannot say which Testee made it.
- `inferred` What the law needs: one cheap command, "is this tree green by this tree's verifier?", with three answers: yes (0), no (1), cannot tell (2, no receipt, tree changed, wrong runner, partial).
  It reads the receipt. It runs nothing. This is the direct form of the user's question ("is this change green?").
- `verified` The verdict is also not purely a function of the tree today. Containment varies by host (weak containment can pass a full gate, ADR rule 5). The checks' tools often come from a mutable uv venv outside the lock
  (`uv run --no-sync pytest`, template-py absolute paths in `.devenv/state/venv/bin`, `03` §6). `environment_identity` records `shell.drvPath` and the lock hash, not the venv (`provenance.py:126-140`).
  The pin does not fix this. The report should at least record the containment level and the runner (it records containment now).

### 1.9 Smaller points

- `verified` Testee's own repo pins `testee.package` to the working tree (`devenv.nix:7`). In the plane model its project-plane `testee` is the code under test. DESIGN item 6 (pin the gate runner to the last release) is still required.
- `verified` The concept wants the pin "as a `devenv.yaml` input in `devenv.lock`". Today the fleet uses `builtins.getFlake` with a tag ref and the lock holds no Testee node (`03` §1).
  Moving it works: `p1` evaluates, `devenv eval testee.package.outPath` returns the store path, and `devenv.lock` gains a `testee` node (type `path` here; a `github:` URL would lock a rev).
  `unknown`: with `follows: nixpkgs`, the Testee closure uses the repo's nixpkgs, so the store path differs per repo and may rebuild (404 MB closure, `10` §1.8). Without `follows`, the lock gets a second nixpkgs. Measure before choosing.
- `inferred` RepoMan cannot own the pin (candidate b). Inputs are not transitive across a remote module import (R1, `CONCEPT.md` §6, `checks.py:369-377`). RepoMan can only presence-import Testee's module when the repo declares the input,
  as it does for shellij (`modules/devenv.nix:98`). `unknown` whether devenv 2.4 changed this; I did not re-test.

## 2. Alternatives considered

| Alt | Idea | Result |
|---|---|---|
| (a) devenv only: `devenv test` / `devenv tasks run`; Testee as library + module | One front door, no host tool | Fails. Exit 2 becomes 1 (table 1.3). No sealed report when the shell does not build. A non-clean shell exposes host tools (`command -v jj git nix devenv` all found; none in `--clean`). `enterTest` collides in fornix and loci-core (`03` §7.4). |
| (b) RepoMan owns the Testee pin | One input to bump | Partly blocked by R1. A bundle through a RepoMan flake would work, but it brings back a toolchain pin inside RepoMan, which Vendomat V5 and 0.9.1 removed. It couples the Testee version to the RepoMan version for the fleet. Reject. Keep only the wiring (presence-import plus `provisioned:test`). |
| (c) Testee checks as native devenv tasks; Testee only collects | Reuse devenv scheduling | Fails. Tasks run in the outer non-clean shell, lose containment and the 0/1/2 code (table 1.3), and need an ordering layer for collection. Testee's value is the supervisor outside the shell. |
| (d) Family "project tool" convention and shared guard | `<tool>.package` plus one launcher | Premature. Only Testee has a pin that drives its runner (`10` §3b). Write the launcher so the attribute name is a parameter, nothing more. |
| (e) Tree names its verifier, with a receipt | Self-launch, lock pin, `testee status` | Best. Section 3 A. |
| (f) Authority moves to CI | The remote gate decides, local runs advise | Not a fit now. No fleet CI runs Testee (`03`). Keep as a later add-on. |

## 3. The best two candidates

### A. The tree names its verifier (replaces "two planes")

Concept in three sentences. The tree names its verifier with `testee.package`, pinned in `devenv.lock`. Any `testee` that starts, wherever it sits, runs the verifier the tree names, so the location of the binary does not matter.
Every run saves a receipt that names the tree, the manifest and the verifier, and `testee status` answers "is this tree green" from that receipt.

Concept count: two (the named verifier; the receipt). RepoMan adds none: a command name, a floor version, a skill, a router row.

Owner per invariant:

| Invariant | Owner |
|---|---|
| The runner is the tree's pin | Testee launcher (DESIGN F1 to F9) |
| The pin is locked | the repo: `devenv.yaml` input plus `devenv.lock` (template-py generates it) |
| Red, could-not-run and green are different exit codes | Testee wrapper outside the shell (0/1/2, verified in the table) |
| A verdict names its tree and runner | Testee report: add runner `outPath`, version, manifest hash (tree hash exists) |
| "Is this tree green" | `testee status` (new): exit 0 only for a passed full gate whose tree, manifest and runner equal the current ones |
| Verify before integrate | RepoMan router text; `testee status` is the check before `jj git push`. An optional pre-push hook calls it. Owner of a mechanical gate: `unknown` (gitman is work-only) |
| `testee` is on PATH and launcher-capable | RepoMan doctor (`installed:test`, floor `>= 0.6.0` from a generic `min_version`) |
| The skill matches the CLI | Testee (`testee --help`, `doctor`); the pool skill stays thin |

What an agent types: `testee verify --full` to run. `testee status` to ask. Nothing else. From a bare machine: `nix run github:Bullish-Design/testee/<tag> -- verify --full` (the launcher then runs the tree's pin).

Failure modes:
1. A host `testee` older than 0.6.0 has no launcher. It silently runs its own code. Only the doctor floor row shows it, and only when someone runs doctor (`11` §1: nothing runs doctor).
2. Launcher grammar freezes (F1 to F9). Every later change must stay compatible with old pins (`10` §1.6).
3. A launcher runs project-named code. `report` and `status` must not launch in a fresh clone (`10` §1.9).
4. A receipt can go stale. `status` must treat a missing receipt, a changed tree or a partial run as exit 2, never 0.
5. A receipt written by a pre-0.6 pin has no runner field. `status` treats it as exit 2 ("no receipt"). It costs one rerun per repo.
6. Self-hosting: Testee's gate runner must be the last release tag (DESIGN item 6).
7. Cold realise downloads about 404 MB on a fresh machine (`unknown` timing).

### B. Two planes, amended

Concept in three sentences. Host tools (nix, devenv, jj, gitman, copyroom) come from the user profile. Project tools (testee, repoman, ruff, pytest) come from the repo's locked devenv env, and Testee hands off to the tree's pin when it is not that pin.
RepoMan wires the Testee module when the repo declares the `testee` input (approach B: `nix_input="testee"`, row `provisioned:test`), and checks a floor version.

Concept count: five (host plane, project plane, the pin, the hand-off, the door forms). Remove the `plane` field and "no host install" as a goal and it falls to three plus the doors.

Owner per invariant: same as A for the runner, the exit codes and the pin. Differences: the "where does it come from" fact is owned by the repo (`devenv.yaml`), and RepoMan prints a fix from `nix_input`. No owner for the receipt unless A's receipt is added.

What an agent types: `testee verify --full` inside an env. `devenv shell -- testee verify --full` from a plain shell. Never `devenv test` for a verdict (it hides exit 2).

Failure modes:
1. Old 0.5.1 pins cannot hand off. A bump of 23 repos is a precondition (1.2).
2. Three doors. Two keep exit codes, one does not (1.3). Documentation must say which door to use.
3. An env that does not build gives exit 1 and no report (1.3).
4. The skill and the CLI grammar drift per repo (1.5).
5. The plane list is wrong for copyroom and repoman today (1.5, 1.6). The doctor message would send an agent to the wrong place.
6. No tree-bound verdict (1.8).

## 4. Verdict

**Replace the framing, keep the mechanism.** Do not adopt "two planes". Amend DESIGN.md as follows.

1. Keep DESIGN §1 to §5 (self-launch, F1 to F9, RepoMan lean row, release order). Rewrite the concept line as "the tree names its verifier".
2. Add a lock pin step after Testee 0.6.0: the template generates `devenv.yaml` `inputs.testee` (with a `github:` URL and a tag) and `devenv.nix` reads `inputs.testee`. It replaces `builtins.getFlake`. Decide `follows` first (1.9). This is DESIGN "later" item F6 made concrete. The fleet can migrate repo by repo.
3. Use the existing `nix_input` and `provisioned:test` row for the "input missing" fix text. Add no `plane` field. Add the generic `min_version` field as DESIGN says.
4. Add the receipt: record runner `outPath`, version and manifest hash in `run.json` and `report.json` (DESIGN item 5 already adds runner version). Add `testee status [--full]`: exit 0 only for a passed full gate on the current tree by the current pin; 2 otherwise unless the receipt is a clean red (1).
5. Change the router row for `verify`/`integrate`: "run `testee status` before you push". Ship an optional pre-push hook example. Mark the hook owner as `unknown`.
6. Document the doors. First choice: bare `testee`. No-host fallback: `devenv shell -- testee verify --full`. CI: that same shell door or `nix run`, not `devenv test`, because `devenv test` maps exit 2 to 1.
7. Make the pool skill thin and version-neutral. Fix "0.5.0" and "puts `testee` on PATH before devenv starts".
8. State the host floor honestly: a host or pin below the launcher version has no hand-off. The doctor row is the only signal.

## 5. Not verified

- A tty run of `devenv shell -- testee` (full-screen UI risk). `script` did not execute.
- `follows: nixpkgs` effect on the Testee store path and closure size.
- Whether devenv 2.4 allows a transitive input through a remote module (R1 is from RepoMan docs).
- The cost of `testee status` (a tree hash plus one `devenv eval`). Expect about 0.2 s warm (`inferred` from `10` §1.12 and `provenance.py:66-110`).
- A pre-push hook in a jj workspace. `jj git push` may not run Git hooks. `unknown`.
- Where fleet shells get the `repoman` CLI today.

## 6. Command log (all under `/tmp/tw-w4e/bin/s.sh`, a wrapper for `env -i ...`)

- `devenv eval testee.package.outPath` in `p1`: returned `.../rs4i9wy1...-testee-0.5.1` after 3.1 s cold. `devenv.lock` gained a `testee` node.
- `devenv shell -- testee --version` x3: 0.48, 0.50, 0.49 s. `devenv shell -- bash -c 'exit 2'` returned 2, `exit 7` returned 7.
- `bin/modes.sh q_red` and `q_infra`: the exit code table in 1.3.
- `p3`: package `runCommand ... exit 1` in `packages`. Host `testee verify --full` exit 2, `INFRA`, `wrapper_error`. `devenv shell -- testee` exit 1, `Failed to realize shell derivation`, empty stdout, no `.testee`.
- `p4` against `p1`: cross-project `command -v testee` (1.1).
- `testee report` after a staged edit and after a partial run (1.8).
- Side effects: only files under `/tmp/tw-w4e/` (fixtures with their own `git init`, `.devenv` and `.testee` dirs). Nix store gained fixture shell closures and `testee-0.5.99`. No GC. No change under `~/Documents/Projects`, `~/.config` or `~/.ssh`.
