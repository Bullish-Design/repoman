---
name: repoman
description: Start here for any work in this repo. Routes to the right manager and owns the lifecycle order (verify before you integrate, never integrate on red).
auto_trigger:
  keywords: ["this repo", "lifecycle", "verify and land", "ship it", "release", "what's the state of the repo"]
---

# RepoMan — repo front door

This repo is managed by **RepoMan**. Managers wired in: **test git copy**.

Run everything inside `devenv shell`. Exit codes: `0` clean · `1` act on findings · `2` the tool could not run.
Never invoke pytest / ruff / copier directly. Use native `jj` for version control. Go through the manager (or `repoman`).

## The loop

Run these phases in this order.

```
change → verify → integrate
```

## Activities

These activities have no order. Run each one when you need it.

```
birth / converge
```

## Routing — which manager owns what

| When you want to… | Manager | Skill | Command |
|---|---|---|---|
| verify code health and review the latest report | test | `testee` | `testee` |
| open a workspace with `gitman work`; use native jj and `gh` to describe, bookmark, push, and open a PR | git | `gitman` | `gitman` |
| scaffold a repo, pull template updates, or check template drift | copy | `copyroom` | `copyroom` |

For domain detail, open that manager's own skill under `.agents/skills/`.

## Laws

- **Verify before you integrate.** Run `verify` first. Then run `integrate`.
- **Never integrate on red.** Never merge or push while `verify` fails.
- **One front door.** Route domain work through the manager. Cross-phase ordering lives here.
- **Health is per manager.** `repoman doctor` checks RepoMan's own wiring only. To check a manager, run that manager's own `doctor`. `repoman managers` lists what is wired.
