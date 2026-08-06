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

## Adding RepoMan to a repo

```yaml
# devenv.yaml
inputs:
  repoman:
    url: github:Bullish-Design/repoman?dir=modules   # or path:../repoman/modules
    flake: false
imports:
  - repoman
```

```nix
# devenv.nix
{
  repoman.enable = true;
  repoman.managers = [ "copy" "git" "test" ];   # pick your toolchain
}
```

`devenv shell`, then `repoman-sync`. That's the whole adoption step.

## Two install models (project 12)

The manager family deliberately splits in two, and knowing which is which explains
most of what `repoman doctor` tells you:

- **Toolchain managers** (`copyroom`, `gitman`, `docman`, plus `repoman` itself) are
  pure CLIs. They live **once per machine** in a shared venv —
  `$REPOMAN_TOOLCHAIN_VENV`, default `~/.local/share/repoman/venv` — installed by
  `repoman-sync --machine` from the machine `repoman.lock` at the repoman checkout.
  A consumer repo has no `repoman.lock`.
- **uv managers** (today only `testee`) run *inside* your code — its tools import your
  package — so it is a normal per-repo dev dependency declared in your
  `pyproject.toml` under `[dependency-groups] dev` and installed by `uv sync`.

`repoman.managers` selects what is **wired** (tasks, skills, routing). It does not
gate toolchain installation.

## Bootstrapping a machine

Once per machine, and again on every toolchain bump:

```bash
cd <your repoman checkout>
devenv shell -- repoman-sync --machine
```

This creates the shared venv, installs every entry in `repoman.lock` (with
`--upgrade`, so a bump actually takes effect), and records the lock it synced from
inside the venv as `repoman-toolchain.toml`. `repoman doctor` reads that manifest to
tell you whether this repo's roster is satisfied — and whether what's installed still
matches what the lock pins.

A CI runner can point at a differently-shaped lock without editing the checkout:

```bash
REPOMAN_LOCK=/path/to/fleet-repoman.lock repoman-sync --machine
```

## Commands

```bash
repoman managers        # what's wired into this repo
repoman doctor          # preflight + every enabled manager's doctor
repoman doctor --self-only   # just RepoMan's own wiring
repoman doctor --json   # context verdict + self-check rows as JSON (exit repeats the exit code)
repoman status          # each manager's status side by side
repoman install-skills  # regenerate the entrypoint (router) skill
repoman --version
```

Exit codes follow the family contract: `0` ok · `1` a domain decision is needed ·
`2` infra/config · `3` invalid usage. `repoman doctor` returns the worst of its own
preflight and every sub-doctor.

## Reading `repoman doctor`

| Row | Means |
|---|---|
| `toolchain:venv` | the shared machine venv exists |
| `toolchain:lock` | the manifest `repoman-sync --machine` recorded inside the shared venv (`repoman-toolchain.toml`) |
| `lock:<key>` | this manager is present in the recorded toolchain manifest (`repoman-toolchain.toml` in the shared venv) |
| `version:<entry>` | what's **installed** still satisfies what the lock **pins** (catches a stale toolchain) |
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
| `REPOMAN_TOOLCHAIN_VENV` | override the shared venv location |
| `REPOMAN_LOCK` | override the machine lock path (`--machine` only) |
| `REPOMAN_ROOT` | where to look for `repoman.lock` (`--machine` only) |
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
(`devenv.yaml` → `imports: [repoman]`, `repoman.managers = [copy git test doc]`), so the
full manager suite is wired and the shared toolchain (`copyroom`, `gitman`, `docman`) is on
PATH inside it. That makes this checkout the canonical **host** for bootstrapping a new
repo — no need to hop into another repo's shell:

```bash
cd <repoman checkout> && devenv shell -- copyroom new gh:Bullish-Design/template-py /path/to/new-repo --answers answers.yaml --trust
```

Design notes live in [`CONCEPT.md`](CONCEPT.md), the skill architecture in
[`docs/SKILLS.md`](docs/SKILLS.md), and the agent-files convention in
[`docs/AGENT-FILES.md`](docs/AGENT-FILES.md).
