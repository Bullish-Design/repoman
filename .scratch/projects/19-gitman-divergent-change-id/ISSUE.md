# Issue — a divergent change-id livelocks a colocated repository

Date: 2026-09-16
Found in: `~/Documents/Projects/devman`, during Project 039 (tool de-pinning)
Tool: gitman 0.6.2 (pyjutsu 0.21.1, jj-lib 0.44.0)
Severity: **blocking** — every gitman verb except `abandon` refuses; the only
exit from a recoverable state is a destructive one.

## 1. Summary

A jj change-id in `devman` pointed at two commits. `gitman status` reported the
repository off-canonical and told the operator to run `gitman reconcile`.
`reconcile` cannot repair a divergent change-id. It returns `PARTIAL` and
repeats the same instruction, so the advertised remedy is a loop. Meanwhile
`start`, `sync`, `publish`, `land` and `push` all refuse because they gate on
canonical state.

The result: a repository that cannot commit, branch or release, whose only
documented escape is `gitman abandon` — a terminal verb that discards a lane.

The content at risk was never actually in danger, but **that is not visible from
any message gitman prints**. Establishing it took a manual investigation of git
trees. An operator reading only the tool's output would reasonably conclude that
5068 lines of unlanded work were on the line, and would either abandon real work
or stall.

## 2. Symptom

```
$ gitman status
Gitman status — OFF-CANONICAL
Reason: lane(s) 021-changelog have a divergent change-id (one change → multiple commits)
        — run `gitman reconcile`.
Recover: `gitman reconcile`  — adopt it into a lane, or abandon it.
Exit: 1

$ gitman reconcile
Gitman reconcile — PARTIAL
note: still off-canonical: lane(s) 021-changelog have a divergent change-id — run `gitman reconcile`.

$ gitman sync --all
refusing: repo is off-canonical (...) — run `gitman reconcile`.

$ gitman start 039-tool-depinning-docs
refusing: repo is off-canonical (...) — run `gitman reconcile`.
```

`gitman doctor` reports **WARNINGS** and does not mention the divergence at all:

```
ok colocated-head git HEAD reachable from a bookmark
!! colocated-refs 1 leftover git ref(s): 039-tool-depinning-docs — run `gitman reconcile`
```

So the health command says the repository is broadly fine while `status`
refuses every operation. The two disagree.

## 3. The state, measured

Two git commits, one jj change-id:

| Ref | Commit | Tree |
|---|---|---|
| `refs/heads/021-changelog` (local) | `1a55a680` | `ef6d6e49` |
| `refs/remotes/origin/021-changelog` | `7ed3045a` | `043e9d78` |

Both carry the same parent chain (`7eff595 → 335fb73`) and the **same commit
subject**, "fix(changelog): the summary workflow crosses no import boundary".

The feature work is **byte-identical** on both sides:

```
$ git diff 021-changelog origin/021-changelog -- groups/ --stat
(empty)
```

The entire difference is three files present only in the local tip:

```
.scratch/projects/023-toolchain/OVERLAY.md                   132 lines
.scratch/projects/023-toolchain/prompts/03c-lock-overlay.md  136 lines
.scratch/projects/023-toolchain/prompts/05-close-out.md      178 lines
```

Those three are **project 023 documents in a project 021 lane**. `main` has no
`.scratch/projects/023-toolchain/` directory at all, and `git log --all` finds
them reachable from `1a55a680` and nowhere else. They were also absent from the
working tree, so the lane tip was their only copy.

## 4. Root cause

Four things compound. Only the first is a mistake by the operator.

### 4.1 `gitman start` adopts the whole working copy

`start` sweeps every uncommitted change into the new lane. Three unrelated
project-023 documents were sitting in the working tree and were adopted into the
`021-changelog` lane. That is what made the local tip differ from the pushed one.

This is a known trap. `repoman/.scratch/projects/039-repoman-depin/FINAL_REPORT.md`
§4 records it firing **twice** in one session: *"Twice this session a stray
pre-existing changeset got pulled into a new lane alongside the intended
change."* It has now caused a third, worse failure.

### 4.2 The lane was amended after it was pushed

The lane was published as `7ed3045a`, then amended locally — jj rewrites in
place, keeping the change-id and producing `1a55a680`. A later fetch imported
origin's commit under that same change-id. jj then saw one change with two
visible commits: divergence.

This is ordinary jj behaviour, not a bug. The bug is that gitman offers no
non-destructive way out of it.

### 4.3 jj owns the colocated git refs, so git-level repair is futile

The obvious fix is to point the local branch at origin's commit. It does not
hold. Measured:

```
$ git update-ref refs/heads/021-changelog origin/021-changelog
$ git rev-parse --short 021-changelog     # 7ed3045  — looks fixed

$ gitman reconcile
re-pointed colocated git ref(s) to jj: 021-changelog 7ed3045a -> 1a55a680
```

`reconcile` treats jj as authoritative and rewrites the git ref back. The
divergence lives in the jj operation log, and **nothing reachable through git
can resolve it.** Any documentation that suggests a git-level fix is wrong.

### 4.4 `reconcile` deletes colocated git refs that hold unpushed work

Twice in this session `reconcile` removed a branch ref that was the only anchor
for four finished, unpushed commits:

```
removed leftover colocated git ref(s): 039-tool-depinning-prompts, ...
removed leftover colocated git ref(s): 039-tool-depinning-docs.
```

A ref jj does not know about is classified as "leftover" and deleted. In a
colocated repository an operator may reasonably park work on a git branch —
especially when gitman itself refuses to make a lane because the repo is
off-canonical. The recovery path that is supposed to be safe is the one that
removes the anchor.

The commits stayed reachable by hash and reflog, so nothing was lost here. That
was luck plus a deliberately placed tag, not a property of the tool.

## 5. Why it bit us

**The failure is not the divergence. It is that the tool cannot distinguish a
cosmetic twin from a real fork, and neither can the operator from its output.**

Everything gitman printed was consistent with catastrophe: an off-canonical
repository, a lane carrying 5068 unlanded insertions across 51 files, and a
`Recover:` line whose second option is "abandon it". Nothing in any message says
that the two commits differ by three unrelated scratch documents and that the
feature work is identical on both sides.

Establishing that took roughly a dozen manual commands — comparing trees,
diffing the twins path-scoped to `groups/`, checking each differing file against
`main`, and running `git log --all` to prove where the unique blobs lived. Only
after that was it safe to act.

An operator who trusted the output would either have abandoned the lane, losing
three design documents that exist nowhere else — including `OVERLAY.md`, which
records why the `vendomat.toml` publish path for `repoman.lock` was superseded,
architecture the plane still rests on — or stalled, which is what happened: the
repository could not take a commit for the duration.

Two smaller aggravations:

- **`doctor` and `status` disagree.** `doctor` returns WARNINGS and never
  mentions the divergence. A health check that misses the condition blocking
  every write is not a health check.
- **The escape hatch is terminal.** `abandon` is the only verb that still runs.
  The tool's answer to a recoverable state is a destructive command.

## 6. What was done

1. Rescued the three files from `1a55a680` into the working tree, verified by
   comparing `git hash-object` against `git rev-parse 1a55a680:<path>` — all
   three blobs identical.
2. Tagged the old tip so it cannot be garbage-collected:
   `021-changelog-pre-twin-fix -> 1a55a680`.
3. Confirmed the work exists on the server, not merely in a stale
   remote-tracking ref:
   ```
   $ git ls-remote origin refs/heads/021-changelog
   7ed3045a...  refs/heads/021-changelog
   ```
4. Attempted the git-level fix; proved it does not hold (§4.3).

**Remaining, one command:** `gitman abandon 021-changelog`. It is safe now —
the feature work is on origin at `7ed3045a`, the three documents are on disk,
and the old tip is tagged. The lane can be re-adopted from `origin/021-changelog`
afterwards. Commit the three rescued documents in their own `023-toolchain`
lane; they do not belong in a changelog lane.

## 7. Proposed fixes

Ordered by value.

1. **Stop advertising a remedy that cannot work.** When the only fault is a
   divergent change-id, `reconcile` should say so plainly and name the real
   options, rather than printing `run gitman reconcile` as its own remedy. The
   present behaviour is a livelock.

2. **Resolve the twin automatically when it is a twin.** If two commits share a
   change-id and one is an ancestor-equivalent or content-equal sibling of the
   other, gitman can pick one and report the choice. Where content differs, it
   should print the differing paths — the single most useful fact, and the one
   that took a dozen commands to obtain:
   ```
   021-changelog: change X has 2 commits
     1a55a680 (local)   +3 files: .scratch/projects/023-toolchain/{OVERLAY.md,...}
     7ed3045a (origin)
     groups/ identical
   ```

3. **Offer a non-terminal resolution.** Something like
   `gitman resolve --divergent <lane> --keep local|origin`, so the exit from a
   recoverable state is not `abandon`.

4. **Never delete a colocated git ref that holds commits absent from jj and from
   origin.** Refuse, and name the ref, rather than removing the operator's only
   anchor. At minimum, tag before deleting.

5. **Make `doctor` report the divergence.** It currently passes a repository in
   which no write can succeed.

6. **Narrow `start`.** A `--paths` flag, or a printed summary of what was
   adopted with a confirmation when the change set exceeds the expected scope.
   Adopting the whole working copy silently is the upstream cause of this issue
   and of two near-misses already recorded in 039.

## 8. Prevention, for operators today

- Run `git diff --stat main -- .` immediately after **every** `gitman start`
  and confirm the scope before `save`. This single check would have prevented
  this issue entirely.
- Before trusting an alarming lane diff, compare the twins path-scoped to the
  directory that matters (`-- groups/`, `-- src/`). "5068 insertions" was the
  lane's diff against trunk, carried identically by both commits — not work at
  risk.
- In a colocated repository, anchor unpushed work with a **tag** as well as a
  branch. `reconcile` deletes branch refs it does not recognise; the tag is what
  survived here.
