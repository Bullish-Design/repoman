# Kickoff prompt — the bootstrap ceremony: canonical doc (+ `repoman new` scoping)

Paste the block below into a **fresh session in the `repoman` repo** to begin.
This session's job is **implementation planning only — do NOT implement.**
Produce the `IMPLEMENTATION_GUIDE.md` in
`.scratch/projects/14-bootstrap-ceremony-and-entrypoint/`; do not edit `src/`,
`modules/`, `tests/`, or any consumer repo this pass. You *may* run read-only
commands and safe experiments in `/tmp` to verify the plan's mechanics hold.

---

You are planning the fix for **the missing bootstrap ceremony** in **repoman**
(`/home/andrew/Documents/Projects/repoman`): creating a brand-new repo today is
a hand-assembled, multi-repo research project (answers YAML → `copyroom new
--trust` from a host repo's shell → birth hooks → `uv sync` → agent-files
export → `repoman doctor`), and the machine toolchain (`copyroom`/`gitman`) is
not on a bare PATH — it appears only inside a managed repo's devenv shell.

Read `.scratch/projects/14-bootstrap-ceremony-and-entrypoint/FINDINGS.md` first
— observed evidence, options (A–D), acceptance criteria. The owner's lean is
**A now, B as a scoped follow-up, C folded into project 13**:
(A) a canonical ceremony doc in this repo (README section or `docs/`) covering
machine bootstrap + new-repo creation with exact commands, template locations,
and answers keys; (B) a `repoman new <template> <target> --answers …` wrapper
that reproduces the doc end-to-end — **scope B only** in this plan, do not
build it.

## Planning checklist

1. **Document home.** Where in this repo does the ceremony doc live (README
   section vs `docs/` page), and how does the `repoman` skill / doctor message
   link to it? The doc is the spec B must later reproduce.
2. **Content inventory for the doc.** Verify each step's exact commands and
   where the knowledge currently lives: `repoman-sync --machine`
   (`modules/scripts/repoman-sync.sh`), `copyroom new --trust`
   (`docs/user/cli-reference.md` + `trust-and-safety.md` in copyroom), the
   birth hooks (`copyroom.project.yml` post_project_create), `uv sync`,
   `copyroom agent-files export` (project 09 in copyroom), `repoman doctor`.
   Confirm the answers keys `template-py`'s `copier.yml` asks for, and the
   template locations (local checkouts vs `gh:` refs).
3. **Machine-bootstrap flow.** Precise steps for a fresh machine: checkout the
   repoman repo, `devenv shell -- repoman-sync --machine`, and what "toolchain
   ready" looks like (`repoman doctor` rows). Note where project 13's
   short-circuit message will point.
4. **New-repo flow.** The exact ceremony, in order, with the host-shell trick
   documented (run `copyroom new` from any managed repo's devenv shell) — or a
   cleaner alternative if one exists in the current tooling.
5. **Scope B (`repoman new`).** A *plan-only* spec: subcommand shape, how it
   delegates to copyroom (never reimplement render), post-birth steps it
   orchestrates, exit codes, `--json`, and a phase list for a later session —
   do not build any of it now.
6. **Acceptance mapping.** Walk the acceptance criteria (esp. #1: follow the
   doc top-to-bottom against a throwaway repo in `/tmp`) and note anything the
   doc must say that the current tooling does not support (feed that back into
   this or the copyroom projects).

## Deliverable

`IMPLEMENTATION_GUIDE.md` — the doc outline + full drafted ceremony content
(commands verbatim), the B spec (scoped, phased), and the link-map from doctor /
skill / README to the doc. Verify commands you quote by running them read-only
or in `/tmp` — do not modify any repo.

Do not implement. Do not commit changes to `src/` or `modules/`.
