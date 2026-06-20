# scripts vs tasks vs processes — the three execution surfaces

| Surface | Ordering / deps | Lifetime | Started by | Use for |
|---|---|---|---|---|
| `scripts` | none | runs to completion | called by name on PATH | plain commands / CLIs |
| `tasks` | `after` / `before` deps | runs to completion | `devenv tasks run <name>` | ordered, dependent steps |
| `processes` | n/a | long-running, supervised | `devenv up` | servers, watchers, daemons |

## scripts

    scripts.hello.exec = "echo hi";     # → `hello` on PATH inside the shell

No ordering. Blocks until it exits — correct for short work, wrong for a server.

## tasks

    tasks."build:assets" = { exec = "..."; after = [ "build:deps" ]; };

Use when one step must precede another. Run with `devenv tasks run <name>`.

## processes

    processes.web.exec = "uvicorn app:app";

Long-running and supervised. Start with `devenv up` (all) or `devenv up web` (one). Does not block
your shell. (Trigger: the `devenv-processes` skill; worked example:
`background-and-long-running-work.md`.)

## Exit-code contract

Scripts/tasks/CLIs should honor: `0` ok · `1` decision/finding · `2` infra/config · `3` usage. The
exit code is the tool's API. (Authoring: the `devenv-authoring` skill.)
