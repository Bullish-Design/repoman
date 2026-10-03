# Kickoff prompt — `repoman doctor` context preflight (implementation planning)

Paste the block below into a **fresh session in the `repoman` repo** to begin.
This session's job is **implementation planning only — do NOT implement.**
Produce the `IMPLEMENTATION_GUIDE.md` in
`.scratch/projects/13-doctor-outside-repo-diagnostics/`; do not edit `src/`,
`modules/`, `tests/`, or any consumer repo this pass. You *may* run read-only
commands and safe experiments in `/tmp` to verify the plan's mechanics hold.

---

You are planning the fix for **`repoman doctor` outside a managed repo** in
**repoman** (`/home/andrew/Documents/Projects/repoman`): running doctor from a
non-repo directory (or without the repo's devenv shell) produces a pile of
misleading per-row FAILs (`FAIL lock — missing: <cwd>/repoman.lock`,
`installed:* — not on PATH`) instead of one true statement about the context.

Read `.scratch/projects/13-doctor-outside-repo-diagnostics/FINDINGS.md` first —
it contains the observed evidence, options (A–C), and acceptance criteria. The
owner's lean is **option A with B's relabel folded in**: a context preflight
that detects "not inside a managed repo" and short-circuits with one clear
message + exit `2`; plus fixing the `lock` row so it never implies a per-repo
`repoman.lock` file (modern consumers have none).

## Planning checklist

1. **Where doctor lives.** Find the self-check and per-manager doctor
   invocation (`repoman doctor`, `--self-only`, exit-code aggregation). Where
   does the preflight slot in so it dominates the aggregated exit code?
2. **Marker set.** Decide the conservative "managed repo" and "inside the
   devenv shell" signals from `modules/devenv.nix` (e.g. `REPOMAN_TOOLCHAIN_VENV`
   export, PATH wiring) + repo markers (`gitman.toml` / `.gitman/`). Specify
   precedence and why each marker is unambiguous. Distinguish the two failure
   contexts from acceptance criteria 2 and 3 (not-a-repo vs bare-shell-in-a-repo).
3. **Message + exit code.** Exact plain-text and `--json` output for the
   short-circuit (the family contract: parseable plain lines, exit `2` for
   infra/config). Ensure the message names the correct invocation
   (`cd <repo> && devenv shell -- repoman doctor`).
4. **The `lock` row relabel.** What the row should say in-repo so it never
   reads as "missing file" — align naming with `toolchain:lock` semantics, keep
   the in-repo green output stable for any consumer that parses it.
5. **Tests.** Existing doctor tests; new tests for the three contexts
   (non-repo dir, bare shell in repo, devenv shell in repo) incl. `--json` and
   `--self-only`.
6. **Interaction with project 14** (bootstrap ceremony): the short-circuit
   message may point at the bootstrap doc/entrypoint if 14 lands — note the
   seam, don't build it.

## Deliverable

`IMPLEMENTATION_GUIDE.md` — phase-by-phase, file paths, the marker-precedence
table, exact before/after output for the three contexts, JSON schema changes,
and the test matrix. Verify anything uncertain with safe experiments in `/tmp`
and read-only inspection of `modules/devenv.nix` (the PATH/`REPOMAN_TOOLCHAIN_VENV`
wiring is the authoritative contract).

Do not implement. Do not commit changes to `src/` or `modules/`.
