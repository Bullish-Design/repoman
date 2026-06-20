# Guide — Implement devman as a repoman subsystem

**Goal:** ship the devenv-literacy layer (skills + docs export + articles) from inside the
repoman repo, installed by `repoman-sync` and lint-checked by `repoman doctor` — no separate
repo, input, or CLI. Build to `CONCEPT.md` + `CONTENT_INVENTORY.md` in this directory.

## What we're extending (code-grounded)

The conductor already has every seam devman needs:

- `src/repoman/skills.py` — `install_entrypoint(managers, skills_dir, repo_root)` renders +
  writes the generated entrypoint skill from `templates/entrypoint.SKILL.md.j2`. devman adds a
  sibling installer for its static assets.
- `src/repoman/cli.py` — `install_skills()` reads `REPOMAN_SKILLS_DIR` / `DEVENV_ROOT` and calls
  `install_entrypoint(...)`. `doctor()` runs `run_self_check(...)` then the manager doctors.
- `src/repoman/checks.py` — `SelfCheck(name, level, detail)` with `_LEVELS = {"ok":0,"warn":0,
  "fail":2}`, `run_self_check`, `self_check_exit`, `format_self_check`. devman adds checks here.
- `modules/scripts/repoman-sync.sh` — installs the toolchain, then runs `repoman install-skills`.
  Since devman install folds into that command, **the sync script needs no change** (confirm).
- `modules/devenv.nix` — `options.repoman.{enable,managers,template,installSkills,skillsDir}`;
  exports `env.REPOMAN_MANAGERS` / `env.REPOMAN_SKILLS_DIR`. devman adds a `docsDir` option+env.
- `pyproject.toml` — `[tool.setuptools.package-data] repoman = ["templates/*.j2"]`. devman's
  assets ship the same way.

### Correction to CONCEPT.md (asset location)

CONCEPT.md sketched assets under `modules/devman/assets/`. That's wrong for the install path:
it's the **installed `repoman` Python package** (run as `repoman install-skills`) that lays the
assets down, so they must be **package-data inside `src/repoman/`**, exactly like
`templates/entrypoint.SKILL.md.j2`. Use `src/repoman/devman/assets/`. (Update CONCEPT.md /
CONTENT_INVENTORY.md paths when you implement.)

## Target layout

```
repoman/
  src/repoman/
    devman/
      __init__.py
      assets.py            # enumerate expected skills/docs; resolve the assets dir
      install.py           # install_devman(skills_dir, docs_dir, repo_root) + manifest
      assets/
        skills/
          devenv-run-commands/SKILL.md
          devenv-module-edits/SKILL.md
          devenv-inputs/SKILL.md
          devenv-python-venv/SKILL.md
          devenv-processes/SKILL.md
          devenv-authoring/SKILL.md
          devenv-troubleshoot/SKILL.md
        docs/
          shell.md  languages-python.md  scripts-tasks-processes.md
          inputs-and-imports.md  lock-and-cache.md  git-hooks.md  glossary.md
        articles/
          the-lock-cache-loop.md  authoring-a-manager-module.md
          command-not-found-in-shell.md  ci-inside-devenv.md
          background-and-long-running-work.md  adopting-the-man-family.md
    skills.py              # (unchanged) entrypoint installer
    checks.py              # (edit) add devman_checks()
    cli.py                 # (edit) install-skills also installs devman; doctor runs devman_checks
  modules/devenv.nix       # (edit) add repoman.docsDir option + env.REPOMAN_DOCS_DIR
  pyproject.toml           # (edit) package-data globs for devman/assets
  tests/                   # (edit) test_devman.py + extend test_cli/test_checks
```

## Step 1 — asset scaffold + packaging

Create `src/repoman/devman/` and the `assets/` tree. Author at least one **complete** skill now
(the rest in Step 6) so the pipeline is testable end to end.

`src/repoman/devman/assets/skills/devenv-run-commands/SKILL.md`:

```markdown
---
name: devenv-run-commands
description: Use when about to run pytest, python, uv, ruff, or any build/tooling command in this repo. Enforces running through the devenv shell.
---

# Run commands through the devenv shell

This repo is managed by **devenv.sh**. A bare `pytest` / `python` / `uv` / `ruff` runs in a
shell without the repo's pinned PATH, env vars, and determinism settings — it will behave
differently or fail.

**Always** run in-repo commands as:

    devenv shell -- <command>

…or use the repo's own scripts/tasks (e.g. `devenv shell -- repoman doctor`). For a long or
heavy command, run it in the background and poll its log rather than blocking the shell.

For *when* to verify vs. commit vs. release, see the `repoman` skill.
```

Note the two disciplines from `docs/SKILLS.md`: the `description` carries the **trigger**
(mechanics keywords), and the footer **defers ordering** up to the `repoman` skill. Every devman
skill follows this shape.

Packaging — extend `pyproject.toml`:

```toml
[tool.setuptools.package-data]
repoman = [
  "templates/*.j2",
  "devman/assets/skills/*/SKILL.md",
  "devman/assets/docs/*.md",
  "devman/assets/articles/*.md",
]
```

`[tool.setuptools.packages.find]` already discovers `repoman`; `devman` is a subpackage (hence
`devman/__init__.py`). Editable installs resolve assets from the working tree; wheels ship them
via the globs above.

## Step 2 — `src/repoman/devman/assets.py` (enumerate expected assets)

The expected skill/doc set is derived from the shipped package, so the self-check always knows
what *should* be installed regardless of the consumer's state.

```python
"""Locate devman's shipped assets and the names that must end up installed."""
from __future__ import annotations

from pathlib import Path

ASSETS = Path(__file__).parent / "assets"
SKILLS_SRC = ASSETS / "skills"
DOCS_SRC = ASSETS / "docs"
ARTICLES_SRC = ASSETS / "articles"


def expected_skills() -> list[str]:
    """Skill directory names devman ships (each has a SKILL.md)."""
    return sorted(p.name for p in SKILLS_SRC.iterdir() if (p / "SKILL.md").exists())


def expected_docs() -> list[str]:
    return sorted(p.name for p in DOCS_SRC.glob("*.md"))
```

## Step 3 — `src/repoman/devman/install.py` (install + manifest)

Mirror `skills.install_entrypoint`'s contract (return the written paths) and write a manifest so
the self-check can detect drift — the allium-env `.allium-devenv-source` pattern.

```python
"""Install devman's static assets into a consumer repo + record a manifest."""
from __future__ import annotations

import shutil
from importlib.metadata import version
from pathlib import Path

from .assets import ARTICLES_SRC, DOCS_SRC, SKILLS_SRC, expected_skills

MANIFEST = ".devman-source"


def install_devman(skills_dir: str, docs_dir: str, repo_root: str) -> list[Path]:
    root = Path(repo_root)
    written: list[Path] = []

    # Skills → <repo>/<skills_dir>/<name>/SKILL.md
    skills_root = root / skills_dir
    for name in expected_skills():
        dest = skills_root / name
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SKILLS_SRC / name / "SKILL.md", dest / "SKILL.md")
        written.append(dest / "SKILL.md")

    # Docs + articles → <repo>/<docs_dir>/...
    docs_root = root / docs_dir
    for src_dir, sub in ((DOCS_SRC, ""), (ARTICLES_SRC, "articles")):
        target = docs_root / sub if sub else docs_root
        target.mkdir(parents=True, exist_ok=True)
        for md in src_dir.glob("*.md"):
            shutil.copy2(md, target / md.name)
            written.append(target / md.name)

    # Manifest (drift detection: version + source list)
    manifest = skills_root / MANIFEST
    manifest.write_text(
        "Generated by repoman (devman subsystem).\n"
        f"repoman version: {version('repoman')}\n"
        f"skills: {', '.join(expected_skills())}\n"
        "Do not edit these copies; update repoman and re-run `repoman install-skills`.\n"
    )
    written.append(manifest)
    return written
```

> `version("repoman")` via `importlib.metadata` avoids importing the package; it resolves for
> editable + wheel installs alike.

## Step 4 — wire into the CLI (`src/repoman/cli.py`)

`install-skills` becomes the one install path (entrypoint **and** devman). Add a `docsDir` env
read; default `.agents/devenv`.

```python
from .devman.install import install_devman

@app.command("install-skills")
def install_skills() -> None:
    """Generate the entrypoint skill and install devman's devenv-literacy assets."""
    skills_dir = os.environ.get("REPOMAN_SKILLS_DIR", ".claude/skills")
    docs_dir = os.environ.get("REPOMAN_DOCS_DIR", ".agents/devenv")
    repo_root = os.environ.get("DEVENV_ROOT", os.getcwd())
    dest = install_entrypoint(_enabled(), skills_dir, repo_root)
    typer.echo(f"repoman: wrote entrypoint skill → {dest}")
    written = install_devman(skills_dir, docs_dir, repo_root)
    typer.echo(f"repoman: installed devman assets ({len(written)} files) → {skills_dir}, {docs_dir}")
```

And in `doctor()`, append the devman checks before computing the exit (reuse the existing
self-check machinery):

```python
from .devman.check import devman_checks   # Step 5

    self_checks = run_self_check(managers, repo_root, skills_dir)
    docs_dir = os.environ.get("REPOMAN_DOCS_DIR", ".agents/devenv")
    self_checks += devman_checks(repo_root, skills_dir, docs_dir)
    typer.echo(format_self_check(self_checks))
    self_code = self_check_exit(self_checks)
```

## Step 5 — self-check (`src/repoman/devman/check.py`)

Reuse `checks.SelfCheck` so output + exit math stay uniform. Keep devman **`warn`** for now
(it's not yet mandatory); flip to `fail` once devman is required.

```python
"""devman self-checks for `repoman doctor` (are the literacy assets installed + current?)."""
from __future__ import annotations

from importlib.metadata import version
from pathlib import Path

from ..checks import SelfCheck
from .assets import expected_docs, expected_skills
from .install import MANIFEST


def devman_checks(repo_root: str, skills_dir: str, docs_dir: str) -> list[SelfCheck]:
    root = Path(repo_root)
    out: list[SelfCheck] = []

    missing_skills = [n for n in expected_skills()
                      if not (root / skills_dir / n / "SKILL.md").exists()]
    out.append(SelfCheck(
        "devman:skills",
        "ok" if not missing_skills else "warn",
        "all installed" if not missing_skills
        else f"missing {missing_skills} — run `repoman install-skills`",
    ))

    missing_docs = [n for n in expected_docs() if not (root / docs_dir / n).exists()]
    out.append(SelfCheck(
        "devman:docs",
        "ok" if not missing_docs else "warn",
        docs_dir if not missing_docs else f"missing {len(missing_docs)} doc(s) — run `repoman install-skills`",
    ))

    manifest = root / skills_dir / MANIFEST
    if manifest.exists():
        current = f"repoman version: {version('repoman')}"
        fresh = current in manifest.read_text()
        out.append(SelfCheck("devman:current", "ok" if fresh else "warn",
                             "up to date" if fresh else "assets stale — re-run `repoman install-skills`"))
    return out
```

## Step 6 — author the full asset set

Write the remaining skills (Step 1 shape), the docs export, and the articles per
`CONTENT_INVENTORY.md`. Keep the layering discipline: **skills imperative + short**, **docs
factual + grep-able**, **articles explanatory**; never repeat a fact across layers — link
instead. Each doc should be agent-optimized (foreground the gotcha; drop marketing prose). The
`lock-and-cache.md` doc + `the-lock-cache-loop.md` article are the highest-value first targets
(that loop bit us in `01-conductor-hardening`).

## Step 7 — `modules/devenv.nix` (docsDir option + env)

```nix
    docsDir = lib.mkOption {
      type = lib.types.str;
      default = ".agents/devenv";
      description = "Directory (relative to repo root) where devman's docs export is installed.";
    };
```

```nix
    env.REPOMAN_DOCS_DIR = cfg.docsDir;
```

`repoman-sync` already runs `repoman install-skills`, which now also installs devman — **confirm
no sync-script change is needed** (it shouldn't be). Optionally add `repoman.devman.enable`
(default true) if you want a kill switch; skip if YAGNI.

## Step 8 — tests

- `tests/test_devman.py` — `install_devman(tmp)` writes every expected skill + docs + manifest;
  `expected_skills()` is non-empty and matches the shipped tree.
- extend `tests/test_checks.py` — `devman_checks`: clean tmp repo → both `warn` (nothing
  installed); after `install_devman` → `ok`; stale manifest → `devman:current` warn.
- extend `tests/test_cli.py` — `install-skills` lays down devman skills + docs under tmp
  `DEVENV_ROOT` (the existing test already checks the entrypoint; assert a devman skill too).

Run: `devenv shell -- pytest`. Keep `checks.py`/`devman` at full coverage (it's pure I/O on
`tmp_path`).

## Verification (consumer-example)

```bash
cd tests/consumer-example
rm -f devenv.lock && rm -rf .devenv          # asset/env changes
devenv shell -- repoman-sync                 # installs toolchain + entrypoint + devman assets
devenv shell -- bash -c 'ls .claude/skills && ls .agents/devenv'   # devman skills + docs present
devenv shell -- bash -c 'repoman doctor; echo exit=$?'             # self-check shows devman:* OK
# break it:
devenv shell -- bash -c 'rm -rf .claude/skills/devenv-run-commands && repoman doctor | grep devman'
#   → devman:skills WARN (missing …)
```

## Downstream / follow-ups (not this guide)

- **Enforcement hook** — an opt-in pre-tool-use hook that catches bare `pytest`/`uv`/`python`
  and nudges to `devenv shell -- …`. High value, higher risk — its own project.
- **Generated docs export** — wire a regeneration step that distills official devenv.sh docs +
  the gotchas overlay, so `assets/docs` tracks devenv releases instead of drifting.

## Risks

| Risk | Mitigation |
|---|---|
| Assets not shipped in the wheel | Package-data globs (Step 1) + a test that `expected_skills()` is non-empty when imported from the installed package. |
| Path drift between CONCEPT (`modules/devman`) and reality (`src/repoman/devman`) | This guide corrects it; update CONCEPT/INVENTORY when implementing. |
| devman skills collide with manager/entrypoint triggers | Trigger only on mechanics keywords; footer-defer to `repoman`; reuse `docs/SKILLS.md` discipline. |
| Self-check too noisy as `fail` pre-adoption | Ship as `warn`; flip to `fail` when devman is mandatory. |
| Doc export rots vs devenv.sh | Treat `assets/docs` as generated; add the regeneration follow-up. |
