---
name: repoman
description: Start here for any work in this repo. Routes to the right manager and owns the lifecycle order (verify before save, scaffold before change).
auto_trigger:
  keywords: ["this repo", "lifecycle", "verify and commit", "ship it", "release", "scaffold", "what's the state of the repo"]
---

# RepoMan — repo front door

This repo is managed by **RepoMan**. Managers wired in: **copy git test session agent**.

Run everything inside `devenv shell`. Exit codes: `0` ok · `1` decision · `2` infra/config · `3` usage.
Never invoke pytest / ruff / git / copier directly — go through the manager (or `repoman`).

## The loop

```
scaffold → change → verify → save
```

## Routing — which manager owns what

| When you want to… | Manager | Skill | Command |
|---|---|---|---|
| scaffold a repo, pull template updates, or check template drift | copy | `copyroom` | `copyroom` |
| commit, branch, land, undo, or release | git | `gitman` | `gitman` |
| verify code health, fix lint/format, or rerun failures | test | `testee` | `testee` |
| open a live terminal/session for this repo | session | `zelligate` | `zelligate` |
| manage the coding-agent runtime or secrets | agent | `mypi` | `mypi` |

For domain detail, open that manager's own skill under `.claude/skills/`.

## Laws

- **Verify before you save.** Never commit/`save` on a red `verify`.
- **One front door.** Route domain work through the manager; cross-phase ordering lives here.
- **Aggregate health:** `repoman doctor` (all managers) · `repoman status` (state) · `repoman managers` (what's wired).
