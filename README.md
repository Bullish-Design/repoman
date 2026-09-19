# RepoMan

**The agentic repo lifecycle conductor for [devenv.sh](https://devenv.sh) repos — one import that composes the `*man` manager family.**

RepoMan is the *conductor*. It re-implements nothing: it discovers which managers a
repo wired in, sequences their own CLIs, and collapses their reports into one exit
code and one agent-facing front door.

| Manager | Key | Owns |
|---|---|---|
| [copyroom](https://github.com/Bullish-Design/copyroom) | `copy` | templating / scaffolding / convergence (Copier) |
| [gitman](https://github.com/Bullish-Design/gitman) | `git` | version control (jujutsu + colocated git) |
| [testee](https://github.com/Bullish-Design/testee) | `test` | verification (pytest / ruff / ty) |
| [docman](https://github.com/Bullish-Design/docman) | `doc` | docs build/lint/check (zensical) |

---

## Bootstrapping a brand-new repo

```bash
repoman new gh:Bullish-Design/template-py /path/to/new-repo --answers answers.yaml --trust
```

`repoman new` is a transparent pass-through to `copyroom new`: RepoMan does not
re-implement scaffolding, it just spares you from having to know that copyroom,
not RepoMan, owns it. It generates the `devenv.yaml` input block and `devenv.nix`
toggle below for you.

```bash
cd /path/to/new-repo && devenv shell && repoman-sync
```

That's the whole adoption step.

## Adopting an existing repo

Already have a repo and want RepoMan's lifecycle wiring instead of starting
over? `repoman adopt` is the same kind of pass-through, to `copyroom adopt`:

```bash
cd /path/to/existing-repo && repoman adopt gh:Bullish-Design/template-py --ref v1.2.3 --answers answers.yaml --write
```

`adopt` is report-only unless you pass `--write`: without it, you get a
reviewable drift patch under `.copyroom/adopt/` and nothing else. `--write`
additionally records the link (`.copier-answers.yml`) but still does not place
the template's files — that's a separate step, `copyroom layer add` (not
wrapped by RepoMan; run it directly once the drift report looks right). See
copyroom's own `copyroom-adopt` skill for the full adopt / layer add /
templatize decision tree.

Once the link is recorded and the files are in place, same as a new repo:

```bash
devenv shell && repoman-sync
```

`repoman doctor` confirms the wiring landed.

## What `repoman new` / `repoman adopt` generate

Both commands write the same two blocks. Pin a published tag, and fetch it
with `git+https://` rather than the `github:` shorthand: the shorthand uses
nix's builtin fetcher, which needs `access-tokens` and fails on a private
repo, while the git fetcher uses your git credential helper.

```yaml
# devenv.yaml
inputs:
  repoman:
    url: "git+https://github.com/Bullish-Design/repoman?dir=modules&ref=refs/tags/v0.7.1"
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

See "Where the local paths go" below for developing against a local `*man`
checkout instead of a published tag.

## Re-syncing an existing RepoMan repo

Pulled changes to an already-managed repo, or bumped a manager version?

```bash
devenv shell && repoman-sync && repoman doctor
```

`repoman-sync` verifies Vendomat's shared command closure and regenerates the
entrypoint (router) skill from the roster. `repoman doctor` confirms the wiring.
Vendomat's flake owns toolchain versions and updates.

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

This is the same split as `repoman.lock` / `repoman.local.lock`: the committed
file says **what**, the local overlay says **where**.

One sharp edge. devenv rewrites `devenv.lock` in place, so a shell taken with the
overlay active re-locks those inputs at the local paths. Re-lock without it before
you commit:

```bash
mv devenv.local.yaml /tmp/ && devenv update && mv /tmp/devenv.local.yaml .
```

`tests/test_fleet_shape.py` fails if a local path reaches `devenv.yaml` or the
inputs this repo declares in `devenv.lock`, so verify catches the leak before a
land does.

RepoMan's own `repoman` input is `path:./modules`, not a git url. A git input
copies **tracked** files only, so a brand-new `modules/*.nix` would be invisible
to nix until `git add` — and it would surface as an eval error, never as "you
forgot to stage". A path input reads the directory literally.

## Two install models

The manager family deliberately splits in two, and knowing which is which explains
most of what `repoman doctor` tells you:

- **Toolchain managers** (`copyroom`, `gitman`, `docman`, plus `repoman` itself) are
  pure CLIs. Vendomat supplies them from one pinned Nix closure and exports its
  bin directory as `$REPOMAN_TOOLCHAIN_BIN`. A consumer repo has no toolchain
  lock or provider option.
- **uv managers** (today only `testee`) run *inside* your code — its tools import your
  package — so it is a normal per-repo dev dependency declared in your
  `pyproject.toml` under `[dependency-groups] dev` and installed by `uv sync`.

`.repoman/project.toml` selects what is wired (tasks, skills, and routing). It
does not select or install the shared closure.

## Commands

```bash
repoman new              # birth a new repo from the genome — pass-through to `copyroom new`
repoman adopt            # link an existing repo to a template — pass-through to `copyroom adopt`
repoman managers        # what's wired into this repo
repoman doctor          # preflight + every enabled manager's doctor
repoman doctor --self-only   # just RepoMan's own wiring
repoman doctor --json   # context verdict + self-check rows as JSON (exit repeats the exit code)
repoman status          # each manager's status side by side
repoman install-skills  # regenerate the entrypoint (router) skill
repoman devman status   # inspect the repository's Devman manifest migration
repoman devman migrate  # propose a reviewable manifest migration
repoman devman migrate --apply  # write only .devman/project.toml
repoman --version
```

`repoman devman migrate` belongs to RepoMan because it changes one repository.
It derives `project` and ordered `groups` from that repository's tracked
`devenv.nix`. The default is a proposal. `--apply` writes only the new
`.devman/project.toml`; it never updates the machine plane, edits `devenv.nix`,
or commits the result. Review and commit the file through the repository's
normal GitMan lane.

No further step registers the repo with devman: devman has no `register`
command by design and auto-discovers `.devman/project.toml` lazily, wherever
it next resolves this repo's identity.

Exit codes follow the family contract: `0` ok · `1` a domain decision is needed ·
`2` infra/config · `3` invalid usage. `repoman doctor` returns the worst of its own
preflight and every sub-doctor.

## Reading `repoman doctor`

| Row | Means |
|---|---|
| `toolchain:store` | Vendomat's shared command closure exists |
| `lock:<key>` | this manager is present in Vendomat's toolchain manifest |
| `version:<key>` | the store version for this manager |
| `uv:<key>` | a uv manager is declared in `pyproject.toml` |
| `installed:<key>` | the exact binary the nix tasks exec is present (warns if `PATH` would give you a different copy) |
| `provisioned:<key>` | an approach-B manager's nix module actually imported |
| `skill:*` | the entrypoint router and skill-ownership lint |

`warn` never fails the run; `fail` contributes exit `2`.

### Running `repoman doctor` outside a repo

`doctor` checks a repo's RepoMan wiring, and it knows where it's allowed to run.
From a bare shell in a managed repo (no devenv) it says "enter the devenv shell";
from a non-repo directory it says "not inside a repoman-managed repo" — one clear
block, exit `2`, and **zero self-check rows**, so the wrong context can't masquerade
as a pile of per-row failures. The fix is always the same invocation:

    cd <repo> && devenv shell -- repoman doctor

## Environment

| Variable | Effect |
|---|---|
| `REPOMAN_MANAGERS` | roster (set by the nix module). Unset → core default; **empty → wire nothing** |
| `REPOMAN_SKILLS_DIR` | where skills go, repo-relative (default `.agents/skills`) |
| `REPOMAN_TOOLCHAIN_BIN` | Vendomat's shared command-closure bin directory |
| `REPOMAN_TOOLCHAIN_MANIFEST` | optional path to Vendomat's provenance manifest |
| `REPOMAN_SUB_TIMEOUT` | seconds before a sub-manager is killed (default 900; `0` disables) |

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
roster, so the shared toolchain (`copyroom`, `gitman`, `docman`) is on
PATH inside it. That makes this checkout the canonical **host** for bootstrapping a new
repo — no need to hop into another repo's shell:

```bash
cd <repoman checkout> && devenv shell -- repoman new gh:Bullish-Design/template-py /path/to/new-repo --answers answers.yaml --trust
```

Design notes live in [`CONCEPT.md`](CONCEPT.md), the skill architecture in
[`docs/SKILLS.md`](docs/SKILLS.md), and the agent-files convention in
[`docs/AGENT-FILES.md`](docs/AGENT-FILES.md).
