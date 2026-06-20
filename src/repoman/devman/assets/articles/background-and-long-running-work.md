# Background & long-running work — without blocking or hiding output

Two failure modes recur with servers and heavy commands: (1) blocking the shell on something that
never returns, and (2) detaching a command and piping its output somewhere you then can't see, so
you can't tell whether it worked. devenv gives you the right tools for each case.

## Daemons & servers → `processes` + `devenv up`

A server should never be a `scripts`/`tasks` entry — those block until they exit, and a server
doesn't. Declare it as a process:

    processes.web.exec = "uvicorn app:app --port 8000";

Start it supervised, without tying up your shell:

    devenv up            # start all processes
    devenv up web        # start one

`devenv up` supervises them and streams logs; your shell stays free for other commands. (Trigger:
the `devenv-processes` skill; surface comparison: `scripts-tasks-processes.md`.)

## One-off heavy commands → background + poll the log *visibly*

For a big build or a long test run you don't want to block on, run it in the background and **poll
its log where you can read it**. The anti-pattern is redirecting output to a file you never look at
and declaring success blind.

- Run it in the background (a background shell / job), keep the log reachable, and **poll it
  visibly** — show the tail as it progresses rather than hiding it.
- Force a rebuild when env/module changes aren't picked up before the heavy step:
  `rm -f devenv.lock && rm -rf .devenv` (`lock-and-cache.md`).
- Report the real outcome and exit code; don't claim done until the log/exit confirms it.

This mirrors the repo-wide rule: long or opaque commands run **visibly** — no piping to files, no
hidden poll loops.

## CI

The same discipline applies in CI — a long step is still a foregrounded, polled step, not an
invisible detached one. See `ci-inside-devenv.md`.

For *when* in the lifecycle to start processes vs. verify vs. ship, see the `repoman` skill.
