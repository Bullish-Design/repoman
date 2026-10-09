# RepoMan

**The agentic repo lifecycle conductor for [devenv.sh](https://devenv.sh) repos — one import that composes the `*man` manager family.**

RepoMan is the *conductor*. It re-implements nothing and aggregates nothing at runtime.
It discovers which managers a repo wired in and wires their tasks. It generates one file,
the router skill. The router states the lifecycle order: `change`, `verify`, `integrate`.

| Manager | Key | Owns |
|---|---|---|
| [copyroom](https://github.com/Bullish-Design/copyroom) | `copy` | templating / scaffolding / convergence (Copier) |
| [gitman](https://github.com/Bullish-Design/gitman) | `git` | version control (native jj and `gh`; gitman opens workspaces) |
| [testee](https://github.com/Bullish-Design/testee) | `test` | verification (pytest / ruff / ty) |
| [docman](https://github.com/Bullish-Design/docman) | `doc` | docs build/lint/check (zensical) |

---

## Bootstrapping a brand-new repo

```bash
copyroom new gh:Bullish-Design/template-py /path/to/new-repo --answers answers.yaml --trust
```

copyroom owns birth. RepoMan does not wrap it. The genome template (`template-py`
above), not copyroom, renders the `devenv.yaml` input block and `devenv.nix` toggle below.

```bash
cd /path/to/new-repo && devenv shell && repoman-sync
```

That's the whole adoption step.

## Adopting an existing repo

Already have a repo and want RepoMan's lifecycle wiring instead of starting
over? Run `copyroom adopt` directly:

```bash
cd /path/to/existing-repo && copyroom adopt gh:Bullish-Design/template-py --ref v1.2.3 --answers answers.yaml --write
```

`adopt` is report-only unless you pass `--write`: without it, you get a
reviewable drift patch under `.copyroom/adopt/` and nothing else. `--write`
additionally records the link (`.copier-answers.yml`) but still does not place
the template's files — that's a separate step, `copyroom layer add` (not
wrapped by RepoMan either; run it directly once the drift report looks right). See
copyroom's own `copyroom-adopt` skill for the full adopt / layer add /
templatize decision tree.

Once the link is recorded and the files are in place, same as a new repo:

```bash
devenv shell && repoman-sync
```

`repoman doctor` confirms the wiring landed.

## What `copyroom new` generates

Only `copyroom new` renders these two blocks, and the genome template does it.
`copyroom adopt` writes at most `.copier-answers.yml` and a patch under
`.copyroom/adopt/`. It never places template files. After `copyroom adopt`, the blocks
arrive only through `copyroom layer add` or your own edit.

Pin a published tag, and fetch it with `git+https://` rather than the `github:`
shorthand: the shorthand uses nix's builtin fetcher, which needs `access-tokens`
and fails on a private repo, while the git fetcher uses your git credential
helper.

```yaml
# devenv.yaml
inputs:
  repoman:
    url: "git+https://github.com/Bullish-Design/repoman?dir=modules&ref=refs/tags/v0.10.0"
    flake: false
imports:
  - repoman
```

```nix
# devenv.nix
{
  repoman.enable = true;
}
```

Create `.repoman/project.toml` to choose the lifecycle roster:

```toml
schema = 1
managers = ["copy", "git", "test"]
```

RepoMan also accepts the legacy `cliProvider` key so an old manifest still loads. It
ignores the key. The host profile puts the manager commands on `PATH`.

See "Where the local paths go" below for developing against a local `*man`
checkout instead of a published tag.

## Re-syncing an existing RepoMan repo

Pulled changes to an already-managed repo, or bumped a manager version?

```bash
devenv shell && repoman-sync && repoman doctor
```

`repoman-sync` checks that `repoman` is on `PATH` and regenerates the entrypoint
(router) skill from the roster. `repoman doctor` confirms the wiring. The host
profile owns manager versions and updates.

## Where the local paths go

Every committed devenv file is portable: it names published tags, never one
machine's working trees. That holds for this repo and for every repo `copyroom
new` generates.

To develop a `*man` tool from a local checkout, write `devenv.local.yaml` next to
`devenv.yaml`. It is untracked, uses the same schema, and devenv merges it over
the committed file:

```yaml
inputs:
  docman:
    url: "git+file:///home/you/Projects/docman"
    flake: false
```

The committed file says **what**. The local overlay says **where**.

One sharp edge. devenv rewrites `devenv.lock` in place, so a shell taken with the
overlay active re-locks those inputs at the local paths. Re-lock without it before
you commit:

```bash
mv devenv.local.yaml /tmp/ && devenv update && mv /tmp/devenv.local.yaml .
```

In this repo, run `relock` instead. It runs the same steps and restores the overlay
on any exit.

`tests/test_fleet_shape.py` fails if a local path reaches `devenv.yaml`. It does not
check `devenv.lock`, because devenv rewrites that file on every shell entry. A
release gate guards the lock. The `gate` script runs `scripts/check-fleet-lock.py --rev HEAD`,
which fails if any lock node in the committed `devenv.lock` names a local path, and then runs `testee verify --mode ci`.
Native `jj git push` runs no hook, so run `gate` before you push or tag:

```bash
gate                                   # lock check, then the full Testee gate
jj bookmark create NAME -r @-
jj git push --bookmark NAME
gh release create vX.Y.Z               # for a release
```

RepoMan's own `repoman` input is `path:./modules`, not a git url. A git input
copies **tracked** files only, so a brand-new `modules/*.nix` would be invisible
to nix until `git add` — and it would surface as an eval error, never as "you
forgot to stage". A path input reads the directory literally.

## Two install models

The manager family deliberately splits in two, and knowing which is which explains
most of what `repoman doctor` tells you:

- **Host managers** (`copyroom`, `gitman`, `docman`, plus `repoman` itself) are
  pure CLIs. The host profile puts them on `PATH`, and RepoMan runs them by name.
  A consumer repo has no toolchain lock or provider option.
- **uv managers** (today only `testee`) run *inside* your code — its tools import your
  package — so it is a normal per-repo dev dependency declared in your
  `pyproject.toml` under `[dependency-groups] dev` and installed by `uv sync`.

`.repoman/project.toml` selects what is wired (tasks, skills, and routing). It
does not select or install the shared closure.

## Commands

```bash
repoman managers        # what's wired into this repo
repoman doctor          # self-check of RepoMan's own wiring
repoman doctor --json   # the same check as one JSON document (exit repeats the exit code)
repoman install-skills  # regenerate the router skill
repoman --version
```

RepoMan runs no manager. Call each manager's own CLI:

- **Birth and adoption:** `copyroom new` and `copyroom adopt`.
- **Health:** each manager's own `doctor`. The managers use different exit-code dialects,
  so RepoMan merges none of them. The router skill is where the knowledge joins.
- **Test verdict:** `testee verify` (the `repoman:test` task).

RepoMan does not write `.devman/project.toml`. Devman writes no manifests by design. A
person maintains the file by hand, and the template seeds it.

Devman has no `register` command, by design. It also walks no disk to find
manifests: its guide forbids discovery (`devman/AGENTS_GUIDE.md`, §15.1). Two
explicit steps connect a repo:

- **Link plane** (the repo's machine-local links). Run
  `devman-link reconcile --root "$PWD"` once to create the central bootstrap.
  After that, shell entry reconciles the links by itself.
- **Workflow plane** (the workflows that Dagu runs). Run
  `vendomat plane update devman --to <devman-tag> --project-root "$PWD" --policy-root <devman-checkout>`.
  Later updates carry the project forward.

A hand-written manifest alone adds no workflow to Dagu.

Exit codes follow the family contract: `0` clean · `1` act on findings ·
`2` the tool could not run. `repoman doctor` exits `2` on a context failure
and `1` on a failed row.

## Reading manager status

RepoMan has no `status` command. Four facts limit the status commands of the managers:

- `copyroom status` reports version lag, not template drift. It exits `0` even when a
  newer tag exists or the worktree is dirty. For drift, read the `copyroom adopt` report
  or run `copyroom template-preview`.
- `copyroom status` exits `1` in a repo with no Copier answers file. RepoMan's own
  checkout has none.
- `testee list-runs` always exits `0`, even after a failed run, in a repo never
  verified, or outside any repo. For a verdict, run `testee verify`.
- `jj status` is not read-only. It snapshots the working copy (`@`).

## Reading `repoman doctor`

| Row | Means |
|---|---|
| `pyproject` | `pyproject.toml` parses (a missing file is not a failure) |
| `uv:<key>` | a uv manager is declared in `pyproject.toml` |
| `installed:<key>` | a host manager is on `PATH`; a uv manager is in the consumer venv (warns if `PATH` would give you a different copy) |
| `interface:git` | `gitman` is the work-only tool and `jj` is 0.46.0 or later |
| `provisioned:<key>` | an approach-B manager's nix module actually imported |
| `skill:entrypoint` | the router skill exists |
| `skill:<key>:defers` | an installed manager skill defers to the router (warn only) |
| `skill:tool-shipped` | every expected skill link exists |
| `skill:genome-overlay` | skills in the directory that the lint cannot judge |

`warn` never fails the run; `fail` contributes exit `1`.

`doctor` checks RepoMan's own wiring only. To check a manager, run that manager's own
`doctor`. The skill lint derives its list from the roster. It expects `writing` always,
each enabled manager's skill, and copyroom's two sub-skills only when `copy` is enabled.
Skill rows are `ok` or `warn`. They never gate.

### Running `repoman doctor` outside a repo

`doctor` checks a repo's RepoMan wiring, and it knows where it's allowed to run.
From a bare shell in a managed repo (no devenv) it says "enter the devenv shell";
from a non-repo directory it says "not inside a repoman-managed repo" — one clear
block, exit `2`, and **zero self-check rows**, so the wrong context can't masquerade
as a pile of per-row failures. With `--json`, the output is one JSON document and nothing else. The fix is always the same invocation:

    cd <repo> && devenv shell -- repoman doctor

## Environment

| Variable | Effect |
|---|---|
| `REPOMAN_MANAGERS` | roster (set by the nix module). Unset → core default; **empty → wire nothing** |
| `REPOMAN_SKILLS_DIR` | where skills go, repo-relative (default `.agents/skills`) |

## Developing RepoMan

```bash
devenv shell
uv sync --all-extras
test      # pytest + coverage
lint      # ruff
format    # ruff format
```

Repoman's own dev shell is a first-class managed repo: it imports the meta-module
(`devenv.yaml` → `imports: [repoman]`) and its tracked manifest selects the full
roster, so the host's managers (`copyroom`, `gitman`, `docman`) are on
PATH inside it. That makes this checkout the canonical **host** for bootstrapping a new
repo — no need to hop into another repo's shell:

```bash
cd <repoman checkout> && devenv shell -- copyroom new gh:Bullish-Design/template-py /path/to/new-repo --answers answers.yaml --trust
```

Design notes live in [`CONCEPT.md`](CONCEPT.md), the skill architecture in
[`docs/SKILLS.md`](docs/SKILLS.md), and the agent-files convention in
[`docs/AGENT-FILES.md`](docs/AGENT-FILES.md).
