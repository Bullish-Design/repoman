# Project 18 — the incoherent machine toolchain

## The report

In `/home/andrew/Documents/Projects/talkee`:

```
devenv shell -- gitman status
AttributeError: 'Workspace' object has no attribute 'git'
```

`gitman doctor` and `repoman doctor` failed the same way. The trace ended in
`gitman/src/gitman/core.py:239`, `has_remote()`, which calls `ws.git.remotes()`.
`Workspace.git` arrived in pyjutsu 0.20. The machine toolchain had pyjutsu 0.15.0.

## The root cause

A `path:` manager is installed `--editable`. Its **code** follows the checkout;
its **metadata** — version plus `Requires-Dist` — is a snapshot taken when the
package was last built. The two drift apart the moment the checkout advances.

The shared venv at `~/.local/share/repoman/venv` was last synced on 2026-07-31
(`gitman-0.4.2.dist-info/uv_cache.json`). Since then the gitman checkout advanced
to 0.6.0, which requires `pyjutsu>=0.20.0`. Nothing re-synced the venv, so:

| layer | what it saw | verdict |
|---|---|---|
| the code that ran | gitman 0.6.0, needs `Workspace.git` | broken |
| installed metadata | `gitman 0.4.2`, `Requires-Dist: pyjutsu>=0.15.0` | satisfied |
| `repoman.lock` | `[managers.git-pyjutsu] wheel:pyjutsu>=0.8` | satisfied |
| `uv pip check` | "All installed packages are compatible" | green |
| `repoman doctor` | `OK version:managers.git — gitman 0.4.2` | green |

Every constraint anyone could see was met, because **the stale metadata hid the
real one**. The lock's loose pseudo-entry then let the old pyjutsu stay: `>=0.8`
is true of 0.15.0.

The specific defects, at the RepoMan boundary:

1. **`repoman-sync --machine` never forced a rebuild of an editable manager.** It
   trusted the resolver to notice a checkout had moved. Whether it does depends on
   uv's build-cache heuristics, not on anything RepoMan states.
2. **`repoman-sync --machine` verified the command, not the result.** `uv pip
   install` exiting 0 proves uv resolved what it was *asked* for. It does not prove
   the venv now satisfies what every installed manager *needs*. The script recorded
   a manifest — a claim the venv matches the lock — without checking.
3. **A failed resolution exited 1.** Under the shared contract `1` means "a domain
   decision is needed". An unresolvable toolchain is infra/config: `2`.
4. **`repoman doctor` treated a `path:` source as unfalsifiable.** `_constraints()`
   returned `[]` for `path:` with the comment "editable checkouts — always current
   by construction, so they pin nothing". The code is current; the metadata is not.
   So `version:managers.git` reported `OK gitman 0.4.2` against a 0.6.0 checkout.
5. **Nothing compared the venv against the managers.** `version:<entry>` compares
   the venv against the *lock*. Only each manager's own `Requires-Dist` states its
   real floor, and no check read it.

## Answers to the investigation questions

1. **Why is the editable code current while the metadata is 0.4.2?** That is what
   editable means. `_editable_impl_gitman.pth` adds the checkout's `src` to the
   path, so imports always resolve the working tree. `gitman-0.4.2.dist-info` is a
   build artefact from the last sync, 2026-07-31.
2. **Why did pyjutsu 0.15.0 survive?** No sync ran after the gitman bump. Had one
   run, the stale metadata would have offered `pyjutsu>=0.15.0` to the resolver,
   and `wheel:pyjutsu>=0.8` would have offered nothing stricter.
3. **Does the sync install managers and pseudo-entries separately?** No — one
   `uv pip install` carries every lock entry, so the constraints meet in a single
   resolution. That part was already right; it is the *inputs* to that resolution
   that were stale.
4. **Does `uv pip install` honour gitman's `[tool.uv.sources]` for a local path?**
   Yes, on uv 0.12.1. A fresh sync resolved pyjutsu from the pinned release URL
   (`pyjutsu-0.20.0-cp313-abi3-manylinux_2_39_x86_64.whl`), not the wheelhouse.
5. **Manifest, algorithm, or both?** Both. The algorithm never enforced or verified
   the combined constraint set; the lock's pseudo-entry floor had drifted to a
   number no manager had used for several releases.
6. **Does repeated synchronisation converge?** With uv 0.12.1, yes — it rebuilds
   path requirements each run. That convergence was a property of uv's current
   behaviour, not of anything RepoMan asserted, and it silently did not happen for
   five weeks because nobody ran the command.
7. **Did the sync detect or repair stale editable metadata?** No. It had no notion
   of the checkout's declared version.
8. **Can other pseudo-dependencies fail the same way?** Yes. The rule is generic:
   any `[managers.<m>-<dep>]` floor that lags its manager's real requirement admits
   a version the manager cannot use. The fix is generic for the same reason.

## The fix

`modules/scripts/repoman-sync.sh` (machine mode):

* every `path:` entry gets `--reinstall-package=<name>`, so the resolver reads the
  checkout's current requirements, never the last build's snapshot;
* after the install, the script verifies the venv — each `path:` manager's
  installed version against its checkout's `[project].version`, and every installed
  distribution's `Requires-Dist` against the installed set. A finding names the
  package, the constraint, and the installed version. The script exits `2` and
  records **no** manifest;
* a failed resolution exits `2`, naming the constraint set that has no solution.

`src/repoman/checks.py` (`repoman doctor`):

* `version:<key>` compares a `path:` entry's installed version with its checkout's
  declared version, so drift *between* syncs is reported instead of hidden;
* new `deps:toolchain` rows verify every installed distribution's own requirements.

`repoman.lock`:

* `[managers.git-pyjutsu]` floors at `pyjutsu>=0.20.0`, matching what gitman
  declares. Enforcement no longer depends on that floor being current — the floor
  is documentation and a wheelhouse hint.

Requirements carrying an environment marker or an extra are not evaluated in
either layer. Neither has a PEP 508 marker parser, and a wrong answer from a
diagnostic is worse than a narrower one.

## Evidence

* `evidence/00-broken-state/` — the venv as found: site-packages listing, gitman's
  stale `METADATA` and `uv_cache.json`, the recorded toolchain manifest, the three
  failing talkee commands, and `uv pip check` reporting green.
* `evidence/01-repaired/` — the same commands after a sync through the fixed
  script, plus the second (idempotent) sync.
