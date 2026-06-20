---
name: devenv-processes
description: Use when starting a server or any long-running / heavy task. Use processes + devenv up; don't block the shell; poll logs instead of piping out of view.
auto_trigger:
  keywords: ["start a server", "long running", "background process", "devenv up", "daemon", "watch", "dev server", "heavy build", "poll logs"]
---

# Long-running & background work

Don't block the shell on a server or a heavy build, and don't pipe output to a file you then can't
see.

- **Daemons / servers** → declare a `processes` entry and run `devenv up` (optionally
  `devenv up <name>`). It supervises them; it does not tie up your shell.
- **One-off heavy command** (a big build/test) → run it in the **background** and **poll its log**
  visibly. Never hide output by redirecting it somewhere you won't look — surface it.
- A `scripts`/`tasks` entry blocks until it exits; that's correct for short work, wrong for a
  server.

Grep-able surface comparison: `scripts-tasks-processes.md`. Worked example (processes, `devenv up`,
polling, not blocking): the `background-and-long-running-work.md` article.

For *when* in the lifecycle to start processes, see the `repoman` skill.
