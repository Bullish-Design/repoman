# Guide 03 — Wire the `doc` manager (docman) — **DONE ✅**

**Status: DONE & verified end-to-end (2026-06-25).** The blocking prerequisite —
docman's `02-cli-conductor-alignment` project — shipped a conforming `docman` Typer CLI +
Pydantic `doctor` on 2026-06-20 17:04. The repoman side landed the same day: `57d6fe7`
(*Wire the doc (docman) and spec (alliman) managers*), refined by `1c30ca4` (nix-layer
provisioning bridge) and `a494e91` (phase-5: doctor warns when an approach-B input is
missing). Registry, `modules/managers/docman.nix`, the consumer lock/inputs, `checks.py`,
and the unit tests are all in place and green.

**Live verification (2026-06-25, `tests/consumer-example` cold build, full roster):**

- `repoman doctor` self-check: `OK lock:doc` · `OK installed:doc — docman` ·
  **`OK provisioned:doc`** (approach-B signal `REPOMAN_PROVISIONED_DOC=1` + the `docman` /
  `nixpkgs-python` inputs declared).
- `=== doc (docman) ===` sub-doctor invokes the real venv `docman doctor` and returns an
  all-OK Pydantic report (zensical 0.0.45, python 3.13.13, lychee/markdownlint/typos/
  mdformat/ghp-import, config, site-gitignored, input declarations).
- Exit contract confirmed: `docman doctor` exits **0** healthy; deleting
  `.docman/zensical.toml` *after* shell entry (so docman's `docs-init` re-seed doesn't mask
  it) yields **`FAIL config — missing`** and exit **2**. Config self-heals on next entry.

The original spec below is retained as the (now-satisfied) prerequisite record.

---

The repoman side was trivial composition (mirrors guides 01/02); it could not land until
docman shipped a `docman` console command with a conforming `doctor`. This guide wrote the
repoman side in full *and* named the exact prerequisite so it was a finish-the-last-mile job
once the sibling project landed — which it now has.

## Prerequisite / blocked-on (read this first)

**Sibling project:** `docman/.scratch/projects/02-cli-conductor-alignment/`
(`/home/andrew/Documents/Projects/docman/.scratch/projects/02-cli-conductor-alignment/README.md` +
`01-docman-cli.md`).

**Verified current state of docman** (`/home/andrew/Documents/Projects/docman`):

- **No `pyproject.toml` at all** — docman today is a devenv module (`modules/docman.nix`) + a set of
  `scripts/docs-*.sh` bash scripts (`docs-build`, `docs-doctor`, `docs-lint`, …) + a shipped skill
  set (`skills/docman-{setup,reference,authoring}/SKILL.md`).
- **No `docman` command on PATH.** Its doctor exists only as `scripts/docs-doctor.sh` (plain text,
  exit 0/1), not `docman doctor` emitting a structured report under the family contract.
- The registry already maps `doc → docman` with `doctor=["doctor"]` (default) and **no status**, so
  the *names* are right — there's just nothing to invoke yet.

**Exact contract the alignment project must expose before this guide is implementable** (from its
README's "family CLI contract"):

1. `pyproject.toml` with `[project.scripts] docman = "docman.cli:app"`, src layout (`src/docman/`),
   installable into the devenv venv exactly like testee/copyroom.
2. `docman doctor` — a Python port of `scripts/docs-doctor.sh` returning a Pydantic `DoctorReport`,
   with `--json`, exiting **`0`** if all ok else **`2`** (infra/config). This is the verb
   `repoman doctor` will call (default `["doctor"]`).
3. The `0/1/2/3` exit contract honored.
4. Domain verbs (`build/serve/clean/new/lint/fmt/check/deploy`) delegating to the existing
   `docs-*.sh` — repoman does **not** drive these; only `doctor`.

**Pure-Python?** Expected yes (Typer wrappers over bash). If the alignment project pulls a native
build, add a pseudo-entry per the gitman/pyjutsu rule (§Step 3); otherwise a single plain block.

> **Do not build the docman CLI here.** That's the sibling project's job. This guide is the repoman
> wiring that consumes it.

## Once it lands, do X (the finish-the-last-mile summary)

When docman ships `docman doctor` (exit 0/2) on PATH:

1. Add `modules/managers/docman.nix` (Step 1) and register it in `modules/devenv.nix` imports
   (Step 2).
2. Add the `[managers.doc]` lock block (Step 3).
3. Confirm `REGISTRY["doc"]` is unchanged-correct (Step 4) — **no registry edit needed** for `doc`.
4. Add tests (Step 6) and run the consumer-example verification (Step 7).

That's the entire job — no upstream coordination beyond the alignment project existing.

## Target layout (repoman only — applied after the prereq lands)

```
repoman/
  modules/
    devenv.nix                      # (edit) add ./managers/docman.nix to imports
    managers/
      docman.nix                    # (new) gated on "doc"; repoman:docs:* tasks
  tests/
    consumer-example/repoman.lock   # (edit) add [managers.doc]
    test_registry.py                # (edit) assert doc entry shape
    test_checks.py                  # (edit) doc lock/installed rows
    test_cli.py                     # (edit) doc in managers
```

## Step 1 — manager module `modules/managers/docman.nix`

docman's docs toolchain (zensical/lychee/markdownlint/etc.) already ships through **docman's own**
`modules/docman.nix`. The repoman manager module's job is narrower: put the `docman` console script
on PATH via the venv and expose the `repoman:docs:*` task namespace. Mirror the **pure-Python**
`copyroom.nix`/`testee.nix` shape (no extra `packages` unless the alignment project proves a system
tool isn't already covered by docman's module).

```nix
# RepoMan manager wiring: docman (docs build/check).
#
# Imported unconditionally by ../devenv.nix; activates only when "doc" is in
# `repoman.managers`. The `docman` console script (added by docman's CLI-alignment project)
# is installed into the venv by repoman-sync. The docs TOOLCHAIN (zensical/lychee/…) ships
# through docman's own devenv module; this module only namespaces the repoman:* tasks. If a
# consuming repo wants the full docs toolchain it imports docman's module too — repoman drives
# the CLI, not the toolchain.
{ lib, config, ... }:

let
  cfg = config.repoman;
  enabled = cfg.enable && builtins.elem "doc" cfg.managers;
  venvBin = "${config.devenv.state}/venv/bin";
in
{
  config = lib.mkIf enabled {
    tasks = {
      # docman owns its own report; `repoman doctor` aggregates via the CLI.
      "repoman:docs:doctor".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/docman doctor'';
      "repoman:docs:build".exec  = ''cd "$DEVENV_ROOT" && ${venvBin}/docman build'';
    };
  };
}
```

> **Toolchain note.** `doc` is `tier="publish"`. The docs build tools live in docman's module, not
> here, to keep this gating cheap — a repo that selects `doc` for the *CLI surface* shouldn't be
> forced to pull the full mkdocs/lychee stack unless it also imports docman's module. If the
> alignment project decides the toolchain must travel with the manager, add the relevant `packages`
> here, gated on `"doc"`, exactly like gitman adds Rust.

## Step 2 — register the import in `modules/devenv.nix`

```nix
  imports = [
    ./managers/testee.nix
    ./managers/copyroom.nix
    ./managers/gitman.nix
    ./managers/docman.nix      # activates when "doc" is selected
  ];
```

`allManagers` already includes `"doc"`. No options change.

## Step 3 — lock entry (`tests/consumer-example/repoman.lock`)

Assuming pure-Python (confirm against the shipped `pyproject.toml`):

```toml
[managers.doc]
package = "docman"
source = "path:/home/andrew/Documents/Projects/docman"
```

**If** the alignment project introduces a native build, add the pseudo-entry per the
gitman/pyjutsu rule and provision the toolchain in Step 1:

```toml
[managers.doc-<dep>]
package = "<native-dep>"
source = "path:/home/andrew/Documents/Projects/<dep>"
```

(`run_self_check` already tolerates `doc-*` as satisfying `lock:doc`.)

## Step 4 — registry correctness (confirm, no change)

`REGISTRY["doc"]` is already correct and needs **no edit**:

```python
"doc": Manager(
    "doc", "docman", "publish",
    "Docs",
    route_when="build or check the docs",
),
```

`doctor` defaults to `["doctor"]`; `status` is `None` (docman has no status verb — `repoman status`
correctly skips it via the `if manager.status is None: continue` guard). `skill` defaults to
`"docman"`. Optionally enrich the one-word `summary` ("Docs" → e.g. "Docs build/lint/check
(zensical)") when implementing — a cosmetic touch, not required.

## Step 5 — CLI conformance

| repoman calls | actual invocation | conforms? (after prereq) |
|---|---|---|
| `manager.doctor` | `docman doctor` | must print a `DoctorReport` and exit `0`/`2` — **delivered by the alignment project** |
| `manager.status` | — | `status=None`; `repoman status` skips `doc` |

Until the alignment project lands, `docman` is not on PATH, so `repoman doctor` reports
`installed:doc` **FAIL** (`docman not on PATH — run repoman-sync`) and `aggregate.run_sub` would
return `127` → treated as `2`. That is the correct "blocked" signal, not a wiring bug.

## Step 6 — sub-skill

docman **already ships** `skills/docman-{setup,reference,authoring}/SKILL.md`. Whichever the
alignment project installs as the manager's skill (`skill` defaults to `"docman"`, so the self-check
looks for `<skills_dir>/docman/SKILL.md`) must carry the deferral footer
*"For when to build docs vs. verify vs. save, see the `repoman` skill."* — otherwise
`skill:doc:defers` WARNs once installed. The skill-install path itself is the open question in
`docs/SKILLS.md`; flag it in the alignment project so the installed skill name matches `skill`
(`docman`) or set `skill="docman-reference"` (etc.) in the registry to match what docman installs.

## Step 7 — tests + verification (after the prereq lands)

- **`tests/test_registry.py`** — `REGISTRY["doc"].command == "docman"`, `tier == "publish"`,
  `doctor == ["doctor"]`, `status is None`.
- **`tests/test_checks.py`** — `doc` lock + installed rows (mirror guide 01/02's added tests, package
  name `"docman"`).
- **`tests/test_cli.py`** — `managers` lists `docman`; `status` does **not** emit a `doc` section
  (it has no status verb).
- **Verification (consumer-example):**

  ```bash
  cd tests/consumer-example
  #   repoman.managers = [ "copy" "git" "test" "doc" ];
  rm -f devenv.lock && rm -rf .devenv
  devenv shell -- repoman-sync                       # installs docman into the venv
  devenv shell -- command -v docman
  devenv shell -- bash -c 'repoman doctor; echo exit=$?'
  #   → OK lock:doc   OK installed:doc   then "=== doc (docman) ===" + docman's report
  ```

## Risks

| Risk | Mitigation |
|---|---|
| Implementing this guide before docman's CLI exists | **Hard block.** `installed:doc` FAILs and `docman doctor` 127s until the alignment project ships. Do the READY managers (guides 01/02) first; revisit when docman lands. |
| docman installs its skill under a name ≠ `docman` | Set `REGISTRY["doc"].skill` to the installed skill dir name (e.g. `"docman-reference"`) so `skill:doc:defers` lints the right file. Decide jointly with the alignment project. |
| Alignment project adds a native build | Add a `doc-<dep>` pseudo-entry (Step 3) + provision the toolchain in Step 1, per the gitman precedent. |
| Docs toolchain double-provisioned (docman module + repoman module) | Keep the toolchain in docman's module; repoman's module only namespaces tasks (Step 1 note). `packages` merge is harmless if both list it, but avoid duplicating intent. |
| `docman doctor` exits 0/2 only (no `1`) | Fine — `aggregate.worst_exit` handles any of `0/1/2/3`; `doc` simply never emits a domain `1`. |
