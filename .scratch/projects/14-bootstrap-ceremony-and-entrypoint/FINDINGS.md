# Project 14 — the bootstrap ceremony: no single entrypoint for machine toolchain + new-repo creation

**Status:** open · discovered 2026-08-06 while bootstrapping `talkee` (a brand-new
repo) as the first consumer of the project-12 toolchain split.

## 1. The issue, observed

Creating a new repo required assembling a ceremony from **scattered
knowledge** — no single entrypoint or doc describes it end-to-end:

1. **Machine toolchain is not on a bare PATH.** `copyroom`/`gitman` exist only
   in `~/.local/share/repoman/venv/bin/` (the project-12 system-wide venv).
   Nothing on a fresh PATH exposes them; they are wired onto PATH only **inside
   a managed repo's `devenv shell`** (via the repoman module). `which copyroom`
   → nothing; `copyroom --version` → command not found.
2. **Chicken-and-egg.** To create the *first* repo you need `copyroom`, but to
   have `copyroom` on PATH you need an existing managed repo's shell — or you
   must know the undocumented trick used for `talkee`: run `copyroom new` from
   **another** repo's devenv shell (here: `cd copyroom && devenv shell --
   copyroom new …`).
3. **The ceremony itself is 6+ hand-assembled steps.** For `talkee`:
   write an answers YAML (template question keys) → `copyroom new <template>
   <target> --answers … --trust` (from a host repo's shell) → the birth hooks
   (repoman-sync, gitman init/seed) → `uv sync` → `copyroom agent-files export`
   (project 09) → `repoman doctor`. Nothing prints or scripts this sequence;
   each step's knowledge lives in a different repo's README/docs.
4. **Bootstrap failures don't self-diagnose.** `repoman doctor` from a wrong
   context misleads instead of pointing at the ceremony (project 13); the
   `repoman-sync --machine` bootstrap (`cd <repoman checkout> && devenv shell --
   repoman-sync --machine`) is documented in the repoman README but nothing
   *tells* a user to go there when the toolchain is missing.

## 2. Root cause

- By design (project 12) the toolchain is a single system-wide venv, not
  per-repo — but the **activation story** (how a human or agent gets those CLIs
  onto a PATH) was never given a first-class command; it relies on "be inside
  some managed repo's shell".
- There is no **bootstrap command or doc** that composes the ceremony: machine
  toolchain sync + template render + birth hooks + verify. `repoman` has
  `install-skills`, `sync`, `doctor` — but no `new`/`create`, and nothing that
  routes to copyroom's `new`.
- Template *knowledge* (answers keys, template locations) lives in
  `template-*`/`template-nix` repos; the *ceremony* knowledge is split across
  copyroom docs (trust, new) and repoman README (sync, machine). New users and
  agents must cross-reference three repos to run one workflow.

## 3. Impact

- **Every new-repo bootstrap is a mini-research project** — exactly what
  happened with `talkee`: reverse-engineering template paths, answers keys,
  `--trust`, host-shell invocation, then post-birth steps nobody printed.
- **Agents can't be trusted to reproduce it** — the sequence above is
  hand-assembled from memory of scattered docs; a fresh agent session would
  re-derive it differently (or badly).
- Compounds with project 13 (misleading doctor output) — the two failure modes
  jointly make the first-run experience the roughest part of the family.

## 4. Fix options

| # | Option | Pros | Cons |
|---|--------|------|------|
| A | **Canonical ceremony doc** in repoman (README or `docs/`): one page — "bootstrap a machine" (`repoman-sync --machine`) + "create a new repo" (answers → `copyroom new --trust` → hooks → `uv sync` → agent-files export → `repoman doctor`), with template locations/keys. | Zero code; immediately useful; both 13's doctor message and the repoman skill can link it. | Docs drift; doesn't remove the hand-assembly. |
| B | **`repoman new` wrapper** — `repoman new <template> <target> --answers …` that runs inside any managed shell: delegates to `copyroom new --trust`, then runs post-birth (uv sync, agent-files export) and finishes with `repoman doctor`. | One entrypoint; the ceremony becomes reproducible and testable; natural home for future steps (project 09/10 fixes). | New command surface; must stay thin (delegate to copyroom, not reimplement); template inventory/answers UX still needed. |
| C | **Make the missing-toolchain state self-diagnosing** — `repoman` (and the shell hook) detect the venv/CLIs are absent and print the `repoman-sync --machine` bootstrap line (tightly coupled to project 13's preflight). | Closes the chicken-and-egg blind spot cheaply. | Doc pointer only; doesn't compose the ceremony. |
| D | A+B+C. | Complete: docs teach, `new` executes, missing-toolchain self-diagnoses. | Most surface area; B deserves its own planning pass. |

**Recommendation: A now, B as the flagship follow-up, C folded into project 13.**
A is a docs change landing immediately in this repo; B is a real feature —
scope it in its own implementation pass once A exists (the doc becomes the
spec for what B must reproduce).

## 5. Design constraints

- A's doc must name **exact commands** for both flows and link the template
  repos (locations of `template-py` / `template-nix`, the answers keys each
  asks for) — the knowledge that was hardest to recover during `talkee`.
- B (when planned): delegates to `copyroom new` (never reimplements render);
  runs inside any managed shell; exit codes follow the family contract; `--json`
  support for agents.
- The doc becomes the canonical target for: project 13's short-circuit message,
  the `repoman` skill's bootstrap section, and repoman README's onboarding.

## 6. Acceptance criteria

1. A doc exists in repoman (README section or `docs/`) that a fresh user/agent
   can follow top-to-bottom to create a new repo, without consulting any other
   repo's docs — verified by following it for a throwaway repo in `/tmp`.
2. The doc covers both machine bootstrap (`repoman-sync --machine`) and
   new-repo creation, including template locations + answers keys.
3. Project 13's doctor message links to this doc when context is wrong.
4. (Later, B) `repoman new <template> <target> --answers …` reproduces the
   doc's ceremony end-to-end and ends green with `repoman doctor`.

## 7. Evidence / reference

- The `talkee` bootstrap sequence (2026-08-06) — every step listed in §1.3 was performed by hand; the host-shell invocation (`cd copyroom && devenv shell -- copyroom new …`) was the only way to get `copyroom` on PATH.
- Project-12 model: repoman README "Two install models (project 12)" + `.scratch/projects/12-toolchain-single-instance/`; machine sync: `repoman-sync --machine` (`modules/scripts/repoman-sync.sh`).
- Template knowledge: `template-py` (Python genome, answers keys in its `copier.yml`), `template-nix` (`.refs/` copy), `copyroom new` (`docs/user/cli-reference.md`, `docs/user/trust-and-safety.md`).
