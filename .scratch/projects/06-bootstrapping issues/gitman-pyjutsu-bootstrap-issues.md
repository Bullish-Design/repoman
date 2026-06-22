# Gitman / pyjutsu bootstrap issues (found wiring citegeist)

> **STATUS: RESOLVED (2026-06-21).** All six issues below now have landed, tested fixes in pyjutsu
> (0.7.x, commit `6f656a5`) and gitman (`seed` front door + defensive root resolution). Verified
> end-to-end — see **[Resolution & end-to-end verification](#resolution--end-to-end-verification)**
> at the bottom. The original 6-dead-end bootstrap now collapses to two clean front-door paths, with
> **no external `jj` binary and no `rm -rf .git`**. The issue write-ups below are kept as the
> historical record; each carries an inline ✅ pointer to its fix.

> Context: bootstrapping gitman in the **citegeist** repo — an *existing* git repo
> (one "Initial commit", plus uncommitted work) inside a devenv that provides
> **pyjutsu 0.7.0 (jj-lib 0.38.0)** but **no `jj` CLI binary**. Goal was simply
> "commit step 1 via gitman". It took ~6 dead-ends; each is a concrete, fixable gap.
>
> Environment facts that matter:
> - gitman's repoman manager module contributes pyjutsu + Rust/maturin but **not** a
>   `jj` binary.
> - `nixpkgs` (devenv rolling) ships **jujutsu 0.42.0**; pyjutsu's `JJ_LIB_TARGET` is
>   **0.38.0**. So the only available external `jj` is 4 minors ahead of the linked lib.

---

## Issue 1 — pyjutsu `Workspace.init(colocate=True)` can't adopt an existing `.git`

**Severity:** high (blocks the documented bootstrap on any existing git repo).

`pyjutsu.Workspace.init(path, colocate=True)` binds jj-lib's `Workspace::init_colocated_git`
directly (`Pyjutsu/src/workspace.rs:698-699`). When the directory already contains a
`.git`, it fails:

```
_pyjutsu.WorkspaceError: Failed to initialize git repository
```

The real `jj git init --colocate` *adopts* an existing colocated git (creates `.jj`
backed by the existing `.git`, importing refs). pyjutsu only supports the "create a
fresh git repo" path. The Python docstring even says *"Raises WorkspaceError if `path`
already holds a repo"* — so this is known, but it means **pyjutsu alone cannot bootstrap
gitman into an existing repo.**

**Suggested fix (pyjutsu):** bind the adopt-existing path too. jj-lib / the jj CLI's
`git init --colocate` detects an existing `.git` and runs an import rather than a fresh
init. Expose e.g. `Workspace.init(path, colocate=True, adopt_existing=True)` (or detect
an existing `.git` and branch internally). Without this, gitman *requires* an external
`jj` binary just to start — which is the whole problem below.

> **✅ Fixed — pyjutsu `6f656a5`.** `Workspace.init(colocate=True)` now adopts an existing `.git`:
> `adopt_existing_git()` opens it via `init_external_git` and imports HEAD/refs (branches → bookmarks),
> placing `@` as an empty child of the imported HEAD (or on `root()` if the repo has no commits yet) so
> uncommitted edits survive. The external-jj bootstrap dependency — and with it the version skew of
> Issue 2 — is gone. Covered by `tests/test_init_adopt.py`.

---

## Issue 2 — version-skew: pyjutsu 0.38 reads a jj-0.42-written workspace path as `'../../'`

**Severity:** high (silent, produces a confusing wrong state).

Because pyjutsu can't adopt (Issue 1), the fallback was the gitman-doctor-prescribed
`jj git init --colocate` using the only available binary (**jj 0.42**). It "succeeded",
but then **pyjutsu 0.38 misreads the metadata jj 0.42 wrote**:

```python
ws = pyjutsu.Workspace.load(repo)
for w in ws.workspaces():
    print(w.name, repr(w.path))
# default '../../'          <-- relative, wrong
```

So the default workspace's `path` came back as the relative string `'../../'` instead of
the absolute repo root. (Verified: when pyjutsu 0.38 *both writes and reads* — i.e. a
clean `Workspace.init` with no external jj involved — the same call returns the correct
absolute path `/home/andrew/Documents/Projects/citegeist`.)

**Root cause:** format/relativization skew between the jj 0.42 binary's stored workspace
path and what jj-lib 0.38 (pyjutsu) expects to read.

**Suggested fixes:**
- **pyjutsu:** make `WorkspaceInfo.path` always absolute — resolve any stored relative
  path against the repo/workspace root before returning. A relative `path` leaking out of
  the typed API is a footgun regardless of where it came from.
- **Toolchain:** gitman's repoman manager module should pin a `jj` binary matching
  `pyjutsu.JJ_LIB_TARGET` (0.38.0), or — better — remove the need for an external `jj`
  entirely by fixing Issue 1. Mixing jj 0.42 with jj-lib 0.38 is the trigger here.

> **✅ Fixed — pyjutsu `6f656a5`.** `workspaces()` returns absolute paths via
> `absolutize_workspace_path()`, so a relative path written by a mismatched binary can no longer leak
> through the typed API. Moot in practice anyway: Issue 1's fix removes the external-jj step that
> caused the skew. The "pin a `jj` matching `JJ_LIB_TARGET`" toolchain half is **intentionally not
> needed** — no external `jj` is used. *(Note: `pyjutsu.__version__` still reports `0.7.0`; the `0.7.1`
> bump in `25ede1b` touched only `Cargo.toml`. The compiled extension carries the fix regardless —
> confirmed behaviourally below — but the Python package version string is worth syncing.)*

---

## Issue 3 — gitman `_shared_root` trusts `w.path` is absolute

**Severity:** medium (defensive gap; turns Issue 2 into a hard failure).

`gitman/src/gitman/session.py` `_shared_root`:

```python
for w in ws.workspaces():
    if w.name == "default" and w.path:
        return Path(w.path)          # <-- trusts absolute
```

With Issue 2's `'../../'`, this returns `PosixPath('../..')`, and every downstream
`repo_root / ".git"` / `repo_root / ".jj"` check resolves against the wrong place.

**Suggested fix (gitman):** resolve defensively against the known root:
`return (ws.root / w.path).resolve()` (or `Path(w.path).resolve()` anchored at
`ws.root`). gitman would then have survived Issue 2 entirely.

> **✅ Fixed — gitman.** `_shared_root(ws, start)` now resolves defensively: an absolute, existing
> `path` is used as-is; a relative or nonexistent one is anchored at `start` (the filesystem-resolved
> root the caller already walked to), falling back to `start` itself. A bad recorded path can no longer
> propagate. Covered by `tests/test_session_root.py`.

---

## Issue 4 — `gitman doctor` and `gitman init` disagree on "is this colocated?"

**Severity:** medium (very confusing UX).

In the same directory, at the same moment:

```
gitman init --trunk main   ->  "not a colocated jj repo — run `jj git init --colocate`."  (exit 2)
gitman doctor              ->  "ok colocated  .git + .jj present"  ... "HEALTHY"           (exit 0)
```

Both call a byte-identical `_is_colocated(repo_root)` (`doctor.py:41`, `state.py:31`) —
but with **different `repo_root`s**. `do_init` uses `session.repo_root`
(`= _shared_root(ws)`, the broken `'../..'` from Issues 2/3). `doctor` evidently resolves
the root another way (filesystem / cwd) and so passes. A user sees "doctor says HEALTHY
and colocated" but "init says not colocated" and has no way to reconcile it.

**Suggested fix (gitman):** one root-resolution path for all commands. If `_shared_root`
is the canonical answer, doctor should use it too (and would then have surfaced the real
problem); if the filesystem answer is canonical, init should use it. Don't let two
notions of "the repo root" diverge.

> **✅ Fixed — gitman.** Both `doctor` and `Session.load` now resolve the root through the same
> `_repo_root()` → `resolve_repo_root()` (filesystem walk), and `_shared_root` falls back to exactly
> that root (Issue 3). Init and doctor can no longer disagree. Verified below: in the same dir,
> `gitman init` → INITIALIZED and `gitman doctor` → HEALTHY/"ok colocated" agree.

---

## Issue 5 — pyjutsu `git_export` doesn't sync git `HEAD` (colocated git left broken)

**Severity:** medium (colocated git tooling is unusable until HEAD is fixed).

After seeding a commit via pyjutsu and calling `ws.git_export()`:

```
$ git show-ref
8b09963... refs/heads/main          # <-- correct, the seed commit
$ cat .git/HEAD
ref: refs/jj/root                   # <-- HEAD parked at jj's sentinel
$ git log            ->  fatal: your current branch 'refs/jj/root' does not have any commits yet
$ git status         ->  On branch refs/jj/root / No commits yet
$ git log main       ->  8b09963 Initial commit: ...   # only works with an explicit ref
```

`git_export` writes `refs/heads/<bookmark>` but never updates `.git/HEAD`. The real `jj`
CLI keeps git `HEAD` detached at `@`'s parent on every operation, so colocated `git
log`/`git status` stay sane. With pyjutsu, bare git is broken even though the branch refs
are correct.

**Suggested fix (pyjutsu):** on `git_export` (or as an explicit `sync_git_head()`),
update `.git/HEAD` to `@`'s parent commit (detached), matching jj-CLI colocation
semantics.

> **✅ Fixed — pyjutsu `6f656a5`.** `git_export()` now calls jj-lib `git::reset_head`, so colocated
> `.git/HEAD` tracks `@`'s parent. Verified below: after adoption `.git/HEAD` is `refs/heads/main`
> (or detached at the seed commit), and bare `git log` / `git status` work without an explicit ref.

---

## Issue 6 — no gitman-native way to make the *first* commit of a repo

**Severity:** medium (design gap; every fresh adoption hits it).

Once colocated + `gitman init`'d, trunk `main` sits on `@`, and `@` holds all the
not-yet-described file changes. From there:

- `gitman save -m ...` → **"not on a lane — run `gitman start <name>` first."** (no
  direct-to-trunk commits, by design).
- `gitman start <name>` → `_adoptable_work` (`core.py`) returns **False** because `@`
  *has a bookmark* (trunk is on it), so it takes the `else` branch: `tx.new(trunk)` after
  the precheck snapshot **folds all files into the trunk commit** and creates an *empty*
  lane. The real content ends up undescribed on trunk and the lane/`save`/`land` describe
  an empty change. Wrong outcome.

There's no clean front-door path to seed "the initial commit that already exists on
disk." We worked around it by seeding directly via pyjutsu (snapshot → `tx.describe("@")`
→ `tx.new("@")` so trunk = the described seed and `@` = a fresh empty child), then
`git_export`. That's a bootstrap *outside* the lane model.

**Suggested fixes (gitman), any of:**
- A `gitman init --seed -m "..."` (or a `gitman seed`) that makes the first described
  commit on trunk and leaves a clean empty `@`.
- Teach `start`/adoption to handle "trunk bookmark is on `@` and `@` has changes": move
  trunk to an empty base and adopt the changes as the lane, instead of folding into trunk.
- At minimum, document the bootstrap recipe in the gitman skill ("adopting an existing
  repo / first commit").

> **✅ Fixed — gitman.** Two complementary front doors landed: (1) `gitman seed -m "…"` (`do_seed`,
> CLI-wired, documented in `init.py`) makes a repo's **first** commit — describes `@` as trunk's
> initial commit (the trunk bookmark follows the rewrite) and opens a clean empty `@`, then exports;
> one-shot, refuses once trunk has history or lanes. (2) `gitman start` now *adopts* in-progress work
> on trunk into the new lane instead of folding it in (`d12f14b`). Covered by
> `tests/test_seed_integration.py`. So both adoption shapes work front-door: a repo **with** history
> needs no seed (`init` reuses the existing commit; `start` adopts the WIP), a repo **without** history
> uses `seed`.

---

## What actually worked (end-to-end recipe, for reference)

For an existing git repo, in a devenv with pyjutsu 0.38 + jj 0.38 binary available:

1. `rm -rf .git .jj` (only because we chose a clean re-init; not required if Issue 1 is fixed).
2. Ensure jj identity exists (we wrote `~/.config/jj/config.toml` `[user] name/email`);
   gitman/pyjutsu author commits from jj settings — there is no gitman-level identity.
3. `pyjutsu.Workspace.init(repo, colocate=True)` on the clean dir → correct absolute
   workspace path (no Issue 2).
4. `gitman init --trunk main` → HEALTHY, trunk frozen.
5. Seed the first commit via pyjutsu (no gitman path exists — Issue 6):
   `with ws.transaction(...) as tx: tx.describe("@", msg); tx.new("@")`.
6. `ws.git_export()` → `refs/heads/main` correct (but fix HEAD per Issue 5).
7. `gitman status` → CANONICAL. From here, normal `gitman start/save/land` works.

## Priority recommendation (original — all now done)

1. **pyjutsu Issue 1** (adopt existing `.git`) — removes the need for an external `jj`
   binary, which is what dragged in the version skew (Issues 2). Highest leverage. — ✅ done
2. **pyjutsu Issue 2 + gitman Issue 3** (absolute workspace paths / defensive resolve) —
   cheap, prevents a silent wrong-state. — ✅ done
3. **gitman Issue 6** (first-commit bootstrap) — every repo adoption needs it. — ✅ done
4. **gitman Issue 4** (single root resolution) and **pyjutsu Issue 5** (HEAD sync) —
   correctness/UX polish. — ✅ done

---

## Resolution & end-to-end verification

**All six issues have landed, tested fixes** — pyjutsu commit `6f656a5` (Issues 1, 2, 5; +
`tests/test_init_adopt.py`) and gitman (Issue 3 defensive `_shared_root`, Issue 4 unified
`resolve_repo_root`, Issue 6 `gitman seed` + `start` adoption; + `tests/test_seed_integration.py`,
`tests/test_session_root.py`).

**Re-verified end-to-end on 2026-06-21** in two throwaway consumers (managers `["git"]`, devenv
providing pyjutsu + Rust/maturin but **no `jj` binary** — the citegeist condition), with no external
`jj` and no `rm -rf .git`:

- **Existing repo with history** (one "Initial commit" + an uncommitted edit):
  `pyjutsu.Workspace.init(".", colocate=True)` → **ADOPTED OK** (Issue 1); `workspaces()` reports the
  **absolute** root (Issue 2); `gitman init --trunk main` → INITIALIZED reusing the existing `main`;
  `gitman doctor` → **HEALTHY / "ok colocated"** — init and doctor agree (Issue 4); `.git/HEAD` =
  `refs/heads/main` and bare `git log` works (Issue 5); the uncommitted edit survived on `@`, and
  `gitman start` → "adopted in-progress work into lane", `gitman save` → SAVED (Issue 6 `start` path).
- **Fresh empty repo** (no commits): adopt → `gitman init` creates trunk at `@` → `gitman seed -m`
  → **SEEDED** (trunk lands on the first commit, clean empty `@`); `.git/HEAD` detached at the seed,
  `git log` shows the initial commit; `gitman status` → CANONICAL; `gitman doctor` → HEALTHY (Issue 6
  `seed` path).

**The original 6-dead-end ordeal now collapses to two front-door recipes:**

| Repo state | Recipe |
|---|---|
| Existing `.git` **with** history | `pyjutsu adopt` → `gitman init` → `gitman start <lane>` (adopts the WIP) → `save`/`land` |
| Fresh/empty `.git` (no commits) | `pyjutsu adopt` → `gitman init` → `gitman seed -m "…"` → normal flow |

### Residual polish

1. **pyjutsu Python version string** — `__version__` still reports `0.7.0`; the `0.7.1` bump touched
   only `Cargo.toml`. Sync the Python package version (cosmetic; the compiled fix is present).
   **Deferred** — pyjutsu's working tree is mid-port to **jj-lib 0.42** (the version bump belongs with
   that effort); left untouched on purpose.
2. **gitman bootstrap UX** — ✅ **done (2026-06-22, gitman `856133e`).** `gitman init --colocate`
   now runs the pyjutsu adopt itself (`ensure_colocated()` — adopts an existing `.git` or creates one,
   idempotent) so bootstrap is a single command. The not-colocated errors (`session.load`, `do_init`)
   now point at `--colocate`. Covered by `tests/test_colocate_init.py` (5 cases). Smoke-tested
   end-to-end: `gitman init --colocate --trunk main` on an existing repo → INITIALIZED, doctor HEALTHY,
   `gitman start` adopts the WIP.
3. **gitman skill docs** — ✅ **done (same commit).** `SKILL.md`'s "Bootstrapping a repo" section now
   gives both recipes explicitly (existing-history → `init --colocate` + `start`; fresh/empty →
   `init --colocate` + `seed`).

### Follow-up A — colocated git not exported after mutations — ✅ FIXED (gitman `18c7b19`)

`gitman land` (and `save`/`start`) advanced the **jj** trunk/lane bookmarks but never called
`git_export()` — only `do_seed` did. So after a land the colocated git `refs/heads/<trunk>` (and
HEAD) lagged jj, and a plain `git push <trunk>` shipped a stale ref. **Fixed** by centralizing the
export in the `canonical_tx` / `canonical_guard` wrappers (the choke point every mutating intent runs
through), matching the jj CLI which exports after every op. Best-effort like jj: a partial export
failure (a branch rewound by `undo`, diverged from its git ref → "failed to export some bookmarks")
is swallowed rather than aborting the already-committed intent. Covered by
`tests/test_colocated_git_sync.py`; verified end-to-end (`land` then a plain `git push` ships the
landed commit, no manual export).

### Follow-up B — `gitman start` after a `land` diverges from the pushed trunk (open gitman bug)

Found while dogfooding the above. After `land` leaves the trunk bookmark on `@` (or its parent),
editing files then `gitman start <lane>` did **not** stack a clean lane on the just-landed trunk —
it rebuilt a fresh commit off the **pre-land parent**, folding the new work in and producing a commit
that is a *sibling* of the landed/pushed commit (shared grandparent), not a child. Net effect: trunk
silently diverged from `origin/main`, and the lane showed `+0 −0`. This is the same family as the
original **Issue 6** "start folds into trunk" symptom, resurfacing in the post-`land` state.
**Recovered** by resetting jj trunk to the pushed commit at the git level (git is the durable store:
`refs/heads/main` was correct), committing the held-aside change on top, pushing fast-forward, and
re-adopting `.jj` via pyjutsu. Worth a proper fix + regression test in gitman (start must stack on the
current trunk after a land). Not a bootstrap issue; logged for traceability.

### Follow-up C — pyjutsu 0.42 adopt + git tags → divergent change blocks `gitman reconcile` (found 2026-06-22)

Surfaced while re-adopting `.jj` after the recovery, with the **in-flight pyjutsu 0.42** build (the
0.38 build never showed any of this — the repo was canonical). Three linked observations:

1. **0.42 adopt imports git *tags* as visible heads.** The repo has a `v0.2.0` tag pointing at an
   **off-main** commit (`c2a8443` "Bump version to 0.2.0" — the 0.2.0 release commit was rebased out
   of main's line at some point). pyjutsu 0.38's adopt didn't surface it; 0.42's does, so `c2a8443`
   becomes a `(trunk..)` stray → `gitman status` OFF-CANONICAL on an otherwise-clean repo.
2. **Divergent change-id.** That off-main `c2a8443` shares jj change-id `poosovxy` with an **on-main**
   commit (`c90ef6c` "Pyjutsu bootstrap fixes") — a historical rewrite jj recorded as one divergent
   change. `gitman reconcile` abandons/adopts a stray **by change-id** (`tx.abandon(change.change_id)`),
   and jj refuses a divergent change-id → `reconcile` (both adopt and `--abandon`) hard-fails with
   "Change ID … is divergent", so the repo **cannot be recovered** through gitman's front door.
3. **Stale `refs/jj/keep/*` accumulate in `.git`.** ~50 of them survived `.jj` deletion (they live in
   `.git`, not `.jj`), and each re-adopt re-imported them, resurrecting extra divergent copies of old
   commits. They had to be purged (`git update-ref -d`) before re-adopting.

**Recovered** by abandoning the off-main stray **by commit-id** (`tx.abandon("c2a8443…")` — unambiguous,
sidesteps the divergent change-id), which jj allows where the change-id form fails → CANONICAL again.
**Suggested gitman fix:** `reconcile` should handle divergent strays — target the specific commit-id
rather than the change-id (or skip/flag divergent changes) so an off-canonical repo is always
recoverable. **Suggested pyjutsu fix:** revisit whether 0.42's adopt should import tags as visible
heads (0.38 didn't), and whether `.jj` deletion should also prune `refs/jj/keep/*`.

**Project status: CLOSED.** Two gitman polish items + Follow-up A are done and pushed (gitman
`18c7b19`, linear `colocate → export-fix`); gitman's local `.jj` was recovered to CANONICAL/HEALTHY,
60 tests pass. Open follow-ups for the owning repos: pyjutsu version string (deferred to the in-flight
jj-lib 0.42 port), Follow-up B (start-after-land divergence), and Follow-up C (reconcile vs divergent
change + pyjutsu-0.42 tag-import / `refs/jj/keep` cleanup).
