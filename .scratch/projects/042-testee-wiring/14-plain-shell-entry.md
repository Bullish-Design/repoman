# 14 Plain-shell entry: `devenv shell -- testee ...` with no host install

Wave 4, experiment C. Labels: `verified` (ran it, output in `/tmp/tw-w4c/logs/`), `inferred`, `unknown`.
Tools: devenv 2.4.0, Nix 2.34.7, testee 0.5.1 pin. All commands ran in a scrubbed env (`/tmp/tw-w4c/envrun.sh`).

## Setup

- Consumer: `/tmp/tw-w4c/consumer`. I rendered `template-py` with `copier copy --defaults` (`verified`). I then removed the RepoMan input and import, the Python venv and the `.repoman` files. The Testee wiring is the template's (`builtins.getFlake "git+https://github.com/Bullish-Design/testee?ref=refs/tags/v0.5.1"`, module import, `testee.package`).
- Checks: `ok` (passes), `flag` (fails while `/tmp/tw-w4c/flags/fail` exists), `slow` (sleeps 20 s, not required), `infra` (missing tool, not required, gives exit 2).
- Scrub: `env -i ... PATH=/run/current-system/sw/bin:/etc/profiles/per-user/andrew/bin`. `command -v testee` returns rc 1 (`verified`, `logs/00-first.log`).
- Trap (`verified`): the tool shell has a socket as stdin. With that stdin and no guard variable, NixOS bash re-adds the profile PATH, and the plain `env -i` form then **finds the host testee** (first attempt: `/home/andrew/.nix-profile/bin/testee`). I added `__NIXOS_SET_ENVIRONMENT_DONE=1` to the scrub. Section 7 tests socket stdin both with and without the guard.
- The host binary and the pin are the same store path (`rs4i9wy...-testee-0.5.1`). This experiment cannot show skew. It shows the wrapper cost and behaviour only.
- All timings are warm unless stated. `devenv shell -- true` alone costs 0.15 to 0.24 s.

## Results

| # | Test | `devenv shell -- testee ...` | Host binary by absolute path | Label |
|---|---|---|---|---|
| 1 | `verify` (median of 3) | 1.27 s, rc 0 | 1.07 s, rc 0 | verified |
| 1 | `verify --full` | 1.31 s, rc 0 | 1.15 s, rc 0 | verified |
| 1 | `check ok` | 1.29 s, rc 0 | 0.96 s, rc 0 | verified |
| 1 | `report` | 0.44 s, rc 0 | 0.24 s, rc 0 | verified |
| 1 | `doctor` | 0.77 s, rc 0 | 0.50 s, rc 0 | verified |
| 1 | stdout content | identical to host (diff of `verify --full`) | | verified |
| 1 | first run after a `devenv.nix` edit | 9.95 s | 9.91 s. The second caller pays about 1.3 s. The eval cache is shared. | verified |
| 2 | exit 0 / 1 / 2 | 0 (pass), 1 (`flag` fails), 2 (`check infra`) | same 0 / 1 / 2 | verified |
| 2 | other rc | usage error `check nosuchid` gives 2; `-- bash -c 'exit 7'` gives 7 | usage error gives 2 | verified |
| 3 | stdout to file, no pty | stdout clean. **738 B of progress goes to stderr** (also with `--no-tui`). | stderr empty | verified |
| 3 | pty (`script -qec`), no `--no-tui` | 5.1 to 5.3 s (3 runs). The TUI sends `ESC[?u`, `ESC[c`, `ESC[6n` and waits. | n/a | verified |
| 3 | pty, `--no-tui` | 1.2 s, 27 lines of progress text | n/a | verified |
| 3 | pty driver that answers the queries | 1.22 s. Without the answers 5.25 s. So the 4 s is the wait for terminal replies. | n/a | verified |
| 4 | SIGTERM / SIGINT to the process I launched, mid-`slow` | rc 2 in 0.26 to 0.31 s. Report `infra_error/interrupted` (SIGTERM or SIGINT), sealed, lock free, no `sleep` left. | identical | verified |
| 4 | what "outer devenv" is | none. `devenv shell -- cmd` **execs** the command at the same PID (`/proc/PID/exe` goes from `.devenv-wrapped` to `sleep`/`python3.14` within 0.3 s). The signal reaches Testee directly. | n/a | verified |
| 4 | signal at 0.05, 0.12, 0.2 s (SIGTERM and SIGINT) | **Lost.** The run finished, rc 0, after 21 s. | n/a | verified |
| 4 | signal at 0.3 s | rc -15, no report. Testee had not yet installed its handler. | n/a | verified |
| 4 | SIGTERM at 2 s, during a re-eval after an edit | **Lost.** devenv logged "(cancelled)" for its tasks, then still ran Testee. rc 0 after 28 s. | n/a | verified |
| 5 | syntax error in `devenv.nix` | rc 1, 0.31 s, nothing on stdout. 23 KB stderr. Cause (`syntax error, unexpected identifier` with file:line) is at the **end**. | rc 2, 0.62 s. One line: "Testee infrastructure error: Cannot evaluate Testee manifest:" plus the **first 400 chars** of devenv stderr. The syntax error is cut off. No report. | verified |
| 5 | package fails to build (`runCommand` exits 1) | rc 1, 5.3 s, nothing on stdout. 141 KB stderr (1034 lines). Cause (`boom-in-build`) at line 12. The final line is only "Failed to realize shell derivation". | rc 2, 10.6 s. Sealed `INFRA` report with `not_run` for both checks and `wrapper_error`. The text does not give the cause. It is in `worker.log` (line 14). | verified |
| 6 | `devenv test` (pass) | rc 0, 1.3 to 1.4 s warm; 7.2 s first. Runs `enterTest` = pin `verify --full`. Output goes to stderr (stdout empty). | n/a | verified |
| 6 | `devenv test` (`flag` fails) | rc 1, 1.36 s, "Tests failed :(" | n/a | verified |
| 6 | `devenv test` (Testee exit 2) | **rc 1**. The 2 is lost. `devenv shell -- testee verify --full` on the same project gives rc 2. | n/a | verified |
| 7 | socket stdin (`socketpair`), guard set or unset in the outer env | rc 0, 1.44 / 1.50 s. `command -v testee` inside gives the pin first in PATH. | rc 0, 1.34 / 1.24 s | verified |
| 8 | nested: `testee verify`, `verify --full`, `doctor` from an interactive `devenv shell` on a pty | `testee` resolves to the pin. rc 0 / 0. Lock free afterwards. | n/a | verified |
| 8 | nested, second run while `check slow` holds the lock | "BUSY: another Testee run holds the state lock", rc 2. The next run works. | n/a | verified |

## Findings

1. **Cost.** The wrapper adds 0.2 to 0.3 s per command (devenv startup). `report` doubles (0.24 to 0.44 s). Absolute cost is small.
2. **Exit codes 0, 1, 2 pass through unchanged** from `devenv shell --`, because devenv execs the command. `devenv test` is the exception: it collapses 1 and 2 to 1.
3. **Progress noise.** devenv writes 738 B of progress to **stderr** on every call, even with `--no-tui` and even with no pty. Agents that merge stderr into stdout see it. Use `2>/dev/null` or `--quiet` (untested: `unknown`). In a pty without `--no-tui`, a terminal that answers queries is fine. A pty with no terminal behind it waits 4 s. Agent shells that use a pty should pass `--no-tui`.
4. **Signals.** After devenv execs, there is no extra layer. Testee gets the signal, seals a report and frees the lock exactly like the host binary. **Before the exec (about 0.2 s warm, longer during a cold re-eval) devenv swallows SIGTERM and SIGINT.** A CI timeout or an agent kill in that window does not stop the run. The host binary has no such window (`inferred`: it installs handlers early; I did not time it).
5. **Failure UX is worse through devenv.** A syntax error is fully readable but sits at the end of 23 KB. A build failure buries the cause in 1000 lines, and the last line does not name it. The host binary gives a sealed report for build failures but truncates the eval-error cause to 400 chars. Neither path prints the cause cleanly. Through devenv the exit code is 1 (devenv's own failure code). The host binary returns 2.
6. **Exit code ambiguity.** Through `devenv shell --`, rc 1 means "check failed" or "devenv could not start the shell". The host binary maps start failures to 2. A script cannot tell the two cases apart without reading stderr.
7. **Socket stdin works** through `devenv shell --`. The pin is first on PATH. Inferred: `devenv shell -- cmd` runs the command directly, so the NixOS bash PATH rewrite does not apply. The guard remains needed for the Testee-launched `devenv shell --clean ... bash` path and for the outer `env -i bash` here.
8. **Nested use is fine.** The shell puts the pin first on PATH (`rs4i9wy...-testee-0.5.1`), and the lock works.

## Not done / unknown

- A host with an older pin: no skew test (same store path here).
- Cold download of a never-built pin through `devenv shell --`: `unknown` (the store had it).
- `devenv shell --quiet` or other flags to silence stderr: `unknown`.
- Signal window on a cold first evaluation (several seconds): the 2 s re-eval case is `verified`; the full width is `unknown`.
- A second signal (double Ctrl-C) during the lost window: `unknown`.

## Process notes

- One backgrounded command of mine hung because `ls -a` is aliased to `eza` in this shell. I killed it. No repo file was touched.
- Logs: `/tmp/tw-w4c/logs/` (`01-timing.log`, `m/*.out|err`, `sig-*.report`, `sig-dv-early.report`, `07-*.log`, `08-inner.txt`, `b-*`). Scripts: `/tmp/tw-w4c/scripts/`. I removed the run directories and the broken-project copies.
