# 12 Lock pinning: `getFlake ?ref=tag` versus a `devenv.yaml` input

Wave 4a. Date 2026-10-10. Labels: `verified` (ran it, output seen), `inferred`, `unknown`.
All runs used a scrubbed env (`/tmp/tw-w4a/scripts/e.sh`). Tools: nix 2.34.7, devenv 2.4.0, host testee 0.5.1.
Scripts and logs: `/tmp/tw-w4a/scripts/` (`t1*.sh`, `t2*.sh`, `t3a.sh`, `t4a.sh`, `ttl.sh`). Test repos: `/tmp/tw-w4a/testee-src` (v0.5.1 copy, commit `f77da95`, plus a `next` commit `5660ffa` that renames the package to `testee-moved` and sets `env.TW_MARK=moved`), bare remote `/tmp/tw-w4a/remote/*.git` served by `git daemon` on 127.0.0.1:29461.

## Answer in four lines

1. The current `getFlake ...?ref=refs/tags/v0.5.1` is **not hash-locked** anywhere. A moved tag reaches the consumer. The only brake is a cache with a time limit.
2. A `devenv.yaml` input **is** locked (`rev` and `narHash`). A moved tag changes nothing until `devenv update testee`.
3. Testee's module and package work as a devenv input **unchanged**. One small Testee change makes the consumer `devenv.nix` need no Testee code at all.
4. template-py renders two lines of `devenv.yaml` and a checks-only `devenv.nix`. The `copyroom.yml` guard moves from `devenv.nix` to `devenv.yaml`.

## 1. Is `getFlake ...?ref=tag` locked?

Consumer: `/tmp/tw-w4a/proj-getflake`. Its `devenv.nix` has `builtins.getFlake "git+file:///tmp/tw-w4a/testee-src?ref=refs/tags/vX"`, the same shape as the template. `testee.package` comes from the flake. `testee.checks.t` runs `true`.

| Question | Result | Label |
|---|---|---|
| Does it need `--impure`? | No. `devenv eval testee.package.name` works with no flag. | verified |
| Does `devenv.lock` record Testee? | No. `grep -ci testee devenv.lock` prints `0`, before and after the eval. Fleet agrees: 0 `testee` nodes in 23 locks (`03` §1). | verified |
| Does the flake registry hold it? | No. `nix registry list` shows only `system` and `global` entries. | verified |
| Is there a pin in the nix tree? | No. `getFlake` of a `ref=` URL writes no lock. Testee's own `flake.lock` pins only the nixpkgs that Testee's flake uses. | verified (no node), inferred (cause) |
| Move the tag, fresh process, devenv eval cache warm | Mixed answer. `testee.package.name` stayed `testee-0.5.1` (cached). `env.TW_MARK`, never asked before, read `moved` (new code). One project gave two Testee versions in one run. | verified |
| Same, but `devenv shell` | The shell kept the old package (`...-testee-0.5.1`, `MARK=[]`). | verified |
| `--no-eval-cache` or `--refresh-eval-cache` | Both pick up the moved tag (`testee-moved`). | verified |
| Edit `devenv.nix` by one comment line | The eval cache drops. The shell now runs `...-testee-moved`. The edit did not touch the Testee line. | verified |
| Fresh clone, no `.devenv/` | The clone runs the **moved** code. Nothing in the committed tree names a revision. | verified |

The devenv eval cache (`.devenv/nix-eval-cache.db`) does not track the tag. Per attribute it keeps the old value until a file in `devenv.nix` changes or you pass a refresh flag (`verified`).

Remote refs add a second cache. For a real remote URL, nix caches the ref-to-revision lookup for `tarball-ttl`. I tested with `git+git://127.0.0.1:29461/...?ref=refs/tags/vR` (`ttl.sh`):

- First `nix eval`: `testee-0.5.1`.
- I moved the remote tag. The next `nix eval` still printed `testee-0.5.1`.
- `nix eval --refresh` printed `testee-moved` (`verified`).
- By accident the daemon test also showed the same stale lookup after I re-created the remote with the tag at a different commit: the lock got the cached old rev (`verified`, `t2e.sh`).

The TTL value is the nix default of 3600 s (`inferred`; I did not read it from config). `git+file://` gets no TTL because nix reads the local refs on each call (`verified`: the moved tag showed at once).

**Verdict.** The pin is a tag name that a person can move. Behaviour depends on three caches: the devenv eval cache, the nix ref TTL, and the tag state at fetch time. A fresh clone or CI gets whatever the tag names at that time. This is not "the verdict is a function of the tree" (`verified`).

## 2. Testee as a `devenv.yaml` input

Three working shapes. Reproduced in `proj-input-d` (A), `proj-input-e` (B), `proj-input-f` (C).

**A. Flake input, `follows` the project nixpkgs.**
```yaml
inputs:
  nixpkgs: { url: github:cachix/devenv-nixpkgs/rolling }
  testee:
    url: git+https://github.com/Bullish-Design/testee?ref=refs/tags/v0.5.1
    inputs: { nixpkgs: { follows: nixpkgs } }
imports:
  - testee/nix/testee.nix
```
```nix
{ pkgs, inputs, ... }: {
  testee.package = inputs.testee.packages.${pkgs.stdenv.hostPlatform.system}.testee;
}
```
`inputs` is a `devenv.nix` argument; `inputs.testee` is the flake output set (`verified`). Without `follows` the lock gains `nixpkgs_2` and `nixpkgs-src_2` (7 nodes versus 5) (`verified`, `t2i.sh`).

**B. `flake: false`, package built from the project `pkgs`.** Lock has 5 nodes, the same as the fleet `repoman` input (`verified`).
```nix
testee.package = import "${inputs.testee}/nix/testee-package.nix" { inherit pkgs; };
```

**C. `flake: false`, no Testee code in `devenv.nix`** (needs the change in §3). The module supplies the default package.

`imports: - testee/nix/testee.nix` works for `flake: true` and `flake: false` (`verified`). `inputs.testee` need not exist in the `devenv.nix` arguments for C.

Lock and move test (`t2f.sh`, `t2g.sh`, remote `git+git://`):

| Step | Result | Label |
|---|---|---|
| First eval | `devenv.lock` node `testee`: `rev f77da957...`, `narHash sha256-N0myHuhh...`, `lastModified`, `revCount`, `ref refs/tags/vP`. `follows` recorded as `"nixpkgs": ["nixpkgs"]`. | verified |
| Move the remote tag to the `next` commit, then `devenv shell` in the same dir | Old code (`...-testee-0.5.1`, `MARK=[]`). | verified |
| Same, after editing `devenv.nix` to drop the eval cache | Old code. The lock decides. | verified |
| Same with `--no-eval-cache` | Old code. | verified |
| Fresh clone of the committed tree (lock included) | Old code. | verified |
| `devenv update testee` in the clone | Lock diff: `rev` -> `5660ffac...`, new `narHash`, `revCount 1 -> 2`. Shell now `...-testee-moved`, `MARK=[moved]`. | verified |
| `devenv shell -- testee verify --full` (pin) | `PASS (exit 0; full gate: yes)`, check `t` = `true`. | verified |
| `$HOME/.nix-profile/bin/testee verify` and `verify --full` (host) | `PASS`. The host run needs no extra flag. | verified |
| `devenv tasks run testee:verify` | Runs in 6 s, exit 0. | verified |

**`git+file://` locks without a rev.** With `git+file:///...?ref=refs/tags/vY` the `devenv.lock` node has `url`, `ref` and `type` only. There is no `rev` and no `narHash` (`verified`, `proj-input-a`, `-b`). `nix flake metadata` on the same URL does print a rev, so devenv writes the lock differently (`verified`; cause `unknown`). The fleet shows the same for `forgelab` (`git+file` repoman: no rev) (`verified`). Use `git+git://` or `git+https://` for lock tests. For the real `git+https://github.com/...` the scopeman lock for `repoman` has `rev`, `narHash`, `revCount` (`verified`). I did not fetch the private Testee URL. The match is `inferred`.

**Local-tree override.** `devenv.local.yaml` with `testee: {url: path:/path/to/testee}` takes the working tree: `MARK=[moved]`. It rewrites `devenv.lock` to a `path` node (`verified`, `t4a.sh`). This is the same re-lock warning the template already gives for repoman.

**Recommendation.** Use shape C. It needs no `inputs.testee` plumbing, no `getFlake`, and no second nixpkgs. Use shape B until Testee ships the change. Use shape A only if a flake output is wanted.

## 3. Does Testee work unchanged as a devenv input?

- **Module.** `nix/testee.nix` takes `{ config, lib, ... }`. It sets only `env`, `packages`, `tasks` and `enterTest`. It has no `getFlake`, no `self`, no `<nixpkgs>` and no absolute path (`verified`: `rg 'getFlake|self|NIX_PATH' nix/` finds only `flake.nix:6,15`). It worked as a plain import in shapes A and B (`verified`).
- **Package.** `nix/testee-package.nix` takes `{ pkgs }` and reads `../src` relative to itself. It works from any fetched tree, so `flake: false` is fine (`verified`, shape B).
- **Flake.** `flake.nix` uses `self` only to define `packages.default` (`verified`). Systems are `x86_64-linux` and `aarch64-linux` only. A macOS consumer would fail on shape A and succeed on B or C (`inferred`; no mac host).
- **`testee.package` has no default.** The consumer must set it. This is the only friction.
- **Change needed (optional, 3 lines).** In `nix/testee.nix`: add `pkgs` to the arguments, and set `default = import ./testee-package.nix { inherit pkgs; };` on `options.testee.package`. I tested this on a branch copy (`proj-input-f`): eval, `devenv shell -- testee verify --full` and host `testee verify --full` all passed with a `devenv.nix` that has only `testee.checks` (`verified`). The consumer can still set `testee.package` to override it.
- **Wanted next to this change.** Keep `packages.<system>.testee` in `flake.nix`, so `nix profile add` for the host install still works. No other Testee change is needed for the lock concept.
- **Launcher (DESIGN §4).** The launcher reads `testee.package` through `devenv eval`. That works the same when the value comes from an input (`inferred`: the eval attribute path is the same, `testee.package.name` returned in A, B and C).

## 4. Template-py snippet

`devenv.yaml.jinja` adds one input and one import:
```yaml
inputs:
  nixpkgs:
    url: github:cachix/devenv-nixpkgs/rolling
  repoman:
    url: "git+https://github.com/Bullish-Design/repoman?dir=modules&ref=refs/tags/{{ repoman_ref }}"
    flake: false
  # Testee: pinned in devenv.lock. Move the pin with `devenv update testee`.
  testee:
    url: "git+https://github.com/Bullish-Design/testee?ref=refs/tags/{{ testee_ref }}"
    flake: false

imports:
  - repoman
  - testee/nix/testee.nix
```
`devenv.nix.jinja` drops the `let testeeFlake ... in` block, the `imports = [ testeeFlake... ]` line and the `testee.package = ...` line. It keeps `testee.checks` and the `base:*` tasks. It also drops the `testeeFlake`/`testeePackage` comment lines. Until Testee ships the default package, keep one line: `testee.package = import "${inputs.testee}/nix/testee-package.nix" { inherit pkgs; };`, and add `inputs` to the argument set. The header comment should say "devenv.lock pins Testee".

`devenv.local.yaml.jinja` gets a second commented example: `testee: {url: "path:{{ repoman_dev_root }}/testee", flake: false}`.

### `copyroom.yml` guard (today lines 33-34)

Today:
```
grep -Eq 'getFlake "git[+]https://github.com/Bullish-Design/testee[?]ref=refs/tags/v0[.][5-9]' devenv.nix
grep -Fq 'testee.package = ' devenv.nix
```
Replace with:
```
grep -Eq 'Bullish-Design/testee[?]ref=refs/tags/v0[.]([5-9]|[1-9][0-9])' devenv.yaml
grep -Fxq '  - testee/nix/testee.nix' devenv.yaml
! grep -Fq 'getFlake' devenv.nix
```
Notes:
- Keep `grep -Fq 'testee.checks = ' devenv.nix`. Drop the `testee.package = ` check once Testee ships the default.
- The old regex `v0[.][5-9]` also accepts `v0.50` by accident and rejects `v0.10`. The new class fixes that (`inferred` from regex reading).
- The existing guard `! grep -Eq 'path:|git\+file:' devenv.yaml` still holds. The committed input is a `git+https` tag. It also blocks the `git+file` no-rev lock shape (`verified` above).
- A guard on `devenv.lock` cannot run in the rendered tree: the template ships no lock (`verified`, `ls template/`). The first `devenv shell` creates it. Add a line to `template/README.md.jinja` and `AGENTS.md.jinja`: "Commit `devenv.lock`." A CI or `gitman` verify step may then check `jq -e '.nodes.testee.locked.rev' devenv.lock` (`inferred`; not built).
- `copier.yml` `testee_ref` help text must change: "devenv.yaml takes the module and package from this tag, locked in devenv.lock".

## 5. Residual risks and unknowns

- A tag can still move **before** the first lock, and `devenv update` (with no name) moves every input, including Testee. The lock fixes the tree, not the tag. Use `devenv update <name>` to move one input (`verified`: `devenv update testee` touched only the `testee` node in the diff).
- Two runners remain. The host `testee` runs host code while the pin runs pinned code. The launcher design (DESIGN §4) closes that. Locking closes only the pin side (`verified`, see the host/pin run in §2).
- I did not test the real private `github.com` URL, an offline eval with an expired TTL, or macOS (`unknown`).
- Existing fleet repos with `getFlake` stay on tag semantics until they move to the input. Migration per repo: edit two files, run `devenv update testee`, commit `devenv.lock` (`inferred`).
- No `uv`, no jj or git write ops in real repos, no GC, no push. `/tmp/tw-w4a` is 2.5 MB after cleanup. Nix store paths built for the tests remain (no system GC).
