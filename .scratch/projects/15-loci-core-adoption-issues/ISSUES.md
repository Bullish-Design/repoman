# 15 — Issues found running repoman against a partially-adopted repo

**Date:** 2026-08-13
**repoman version:** 0.7.0
**Consumer repo:** `../loci-core` (devenv-managed, Python 3.13, jj-colocated)
**Session:** ran `managers`, `doctor`, `status`, `install-skills`; wired two of
three managers into the repo by hand; landed the result.

**The state that produced these findings.** loci-core is **partially adopted**:
`repoman` is on `PATH` from the user profile, `managers` correctly reports the
three-manager roster, but the repo does **not** import `repoman/modules` in its
`devenv.yaml` and has no `repoman.lock`. This is a common shape — a repo that
knows about repoman without having taken its devenv module — and repoman's
diagnostics handle it poorly.

**Verdict.** `install-skills` worked perfectly and fixed four findings in one
command. `doctor`'s *detection* is good. Its *remediation advice* is wrong for
this repo shape, in a way that dead-ends the user.

---

## R1 — `doctor` recommends `repoman-sync`, which cannot exist in this repo

**Severity:** Blocker for adoption

**Symptom.** `repoman doctor` printed, three times:

```
FAIL installed:copy — copyroom not on PATH — run repoman-sync
FAIL installed:git — gitman not on PATH — run repoman-sync
FAIL installed:test — testee not on PATH — run repoman-sync
```

`repoman-sync` is not a command:

```
$ command -v repoman-sync            # nothing
$ devenv shell -- command -v repoman-sync   # nothing, inside the shell too
```

**Cause.** `repoman-sync` is a **devenv script**, not a binary:

```nix
# repoman/modules/devenv.nix:121
scripts.repoman-sync = {
  exec = ''exec ${pkgs.bash}/bin/bash ${./scripts/repoman-sync.sh} "$@"'';
```

It exists only in a shell whose `devenv.yaml` imports `repoman/modules`.
loci-core's `devenv.yaml` imports `vendomat/modules` and nothing else, so the
script is unreachable — and no amount of following the advice will help.

**Consequence.** The user is told to run a command that does not exist, cannot
exist, and whose absence is the actual diagnosis. I spent a meaningful part of
this session establishing that `repoman-sync` was not merely missing from
`PATH` but structurally unavailable, and concluded — wrongly at first — that the
managers simply could not be installed.

**Fix.** Make the diagnosis match the repo shape. `doctor` already knows enough
to tell these apart:

| Detected state | Correct advice |
|---|---|
| module imported, `repoman.lock` present, tools pruned | `run repoman-sync` (today's message — correct here, and the case project 11 covers) |
| module **not** imported | "this repo has not adopted repoman's devenv module — add `repoman` to `devenv.yaml` inputs and `repoman/modules` to `imports`, then `repoman-sync`" |
| module imported, no lock | "run `repoman-sync` to write `repoman.lock`" (see R2) |

A cheap first step: before printing `run repoman-sync`, check whether the script
resolves. If it does not, say so and print the adoption stanza instead.

---

## R2 — `repoman.lock` fails the doctor and no subcommand can create it

**Severity:** Serious

**Symptom.**

```
FAIL lock — missing: /home/andrew/Documents/Projects/loci-core/repoman.lock
```

The installed CLI has four subcommands — `managers`, `doctor`, `status`,
`install-skills` — and **none takes any option other than `--help`**. Nothing
writes a lock.

**Cause.** The lock is written by `repoman-sync`, which is unavailable per R1.
So the two findings are circular: the lock is missing because the sync script is
unavailable, and the advice for both is to run the unavailable script.

**Consequence.** A partially-adopted repo has no path forward from the CLI
alone. `doctor` reports a permanent, unfixable `FAIL`.

**Fix.** Either give the CLI a way to write the lock (`repoman lock`, or
`repoman adopt`), or make R1's message explain that the lock arrives with the
devenv module and is not a CLI operation.

---

## R3 — `install-skills` writes to `.claude/skills/`; the agent-files convention says `.agents/skills/`

**Severity:** Serious

**Symptom.**

```
$ repoman install-skills
repoman: wrote entrypoint skill → …/loci-core/.claude/skills/repoman/SKILL.md
repoman: installed devman assets (21 files) → .claude/skills, .agents/devenv
```

But the my-ai personal layer — the cross-repo law every one of these repos
carries — documents a different location:

```markdown
| `.agents/skills/<name>/SKILL.md` | skills — imperative, short, domain-bounded |

| repoman's router | `.agents/skills/repoman/` — *generated* from this repo's
                     manager roster | `repoman install-skills` |
```

`.agents/skills/repoman/` does not exist after `install-skills` runs.

**Consequence.** Two tools disagree about where a skill lives, and both think
they are right:

- `repoman doctor` reports `OK skill:entrypoint — .claude/skills/repoman/SKILL.md`.
- A conformance check written against the documented convention reports the
  repoman skill **missing**. I hit exactly this: an automated probe over
  `.agents/skills/**` flagged `my-ai/SKILL.md`'s pointer to
  `.agents/skills/repoman/` as a broken reference, and it is — permanently,
  by design, in every repo repoman touches.

The `.gitignore` shipped with the convention reinforces the mismatch: it
tracks `.agents/skills/**` and ignores the rest of `.agents/`, so the devman
docs at `.agents/devenv/` are correctly untracked, but the skills land outside
the tracked tree entirely and had to be committed from `.claude/`.

**Fix.** Decide which location is canonical and make all three agree —
repoman's writer, my-ai's ownership table, and the `.gitignore` stanza. If
`.claude/skills/` is intentional (platform-specific install), then my-ai's table
needs a row saying so, and its pointer to `.agents/skills/repoman/` must go.

---

## R4 — `installed:*` checks read `PATH`, which transient state can satisfy

**Severity:** Serious — this produced a false OK in this session

**Symptom.** Mid-session `doctor` reported:

```
OK   installed:git — gitman
```

It was false. gitman was in the venv only because unrelated
`uv run --project <gitman-checkout>` calls had materialized it there as a side
effect. The next dependency sync removed it:

```
$ devenv tasks run loci:build     # uv sync --extra dev
 - pyjutsu==0.15.0
$ ls .devenv/state/venv/bin | grep gitman     # gone
$ repoman doctor
FAIL installed:git — gitman not on PATH
```

**Cause.** The check asks "is the binary reachable right now". In a shared
devenv venv that two mechanisms co-manage — the project's `pyproject.toml` and
repoman's `repoman.lock` — presence on `PATH` is not evidence of *installed*.
Project `11-uv-sync-prunes-toolchain` already established that this venv is
co-managed and that `uv sync` prunes anything not in the uv graph; this finding
is the diagnostic-side consequence of that same model.

**Consequence.** `doctor` can report a green toolchain that evaporates on the
next `uv sync`. A green doctor is exactly when a user stops checking.

**Fix.** Check durability, not presence. Options, cheapest first:

1. Verify the tool is named in a manifest that survives a sync — `repoman.lock`
   for the module path, or the project's `pyproject.toml` for a uv-native
   adoption — and report `WARN present-but-undeclared` when it is on `PATH`
   without being declared anywhere.
2. Record the resolved path and flag when it sits inside a venv the project's
   own lockfile controls.

Option 1 would have caught this exact case and printed something true.

---

## R5 — no `--json` on any subcommand

**Severity:** Moderate

**Symptom.**

```
$ repoman doctor --json
No such option: --json
```

None of the four subcommands accepts it. Output is Rich-formatted with box
drawing throughout.

**Cause / consequence.** The my-ai law §3 requires "structured plain-text
reports — simple lines an agent can parse; no rich coloring under `--json`."
repoman is the front door agents are told to use, and it is the least parseable
of the three managers. I read its output with `head` and `grep` and had to
count `FAIL` strings by eye.

`doctor`'s line format (`FAIL <check> — <detail>`) is already close to the
law's "simple lines" ideal — the gap is the absence of a flag that turns off
the framing and guarantees stability.

**Fix.** Add `--json` to `doctor` and `status` at minimum. The check results are
already structured internally; this is a serializer, not a redesign.

---

## R6 — exit codes do not distinguish FAIL from WARN

**Severity:** Moderate — reported as an open question, not a confirmed defect

**Observed.**

| Command | State | Exit |
|---|---|---|
| `repoman doctor` | 2 FAIL, 0 WARN | `2` |
| `repoman doctor` | 3 FAIL, 3 WARN | `2` |
| `repoman status` | same repo | `0` |

Exit `2` for a missing toolchain is **correct** under the contract (`2` =
infra/config). What I could not test is the WARN-only case: whether a repo whose
only problems are warnings also exits `2`, which would make "needs attention"
indistinguishable from "is broken".

`status` exiting `0` while `doctor` exits `2` on the same repo is also worth a
look — the skill describes `status` as "exit = worst sub-exit", and a repo with
three failing installs arguably is not a `0`.

**Fix.** Confirm the intended mapping and pin it with a test:
`1` for a decision needed / warnings, `2` for infra genuinely broken. Then make
`status` reflect it.

---

## What worked

- **`install-skills` is excellent.** One command, 21 assets, and it closed four
  separate doctor findings at once (`skill:entrypoint`, `devman:skills`,
  `devman:docs`, `devman:current`). It printed exactly what it wrote and where.
  No prompts, no ceremony.
- **`managers` is exactly right.** Three lines, one per manager, with domain and
  tier. This is the format the rest of the CLI should look like.
- **`doctor`'s detection.** Every FAIL and WARN it raised was a real problem.
  Nothing was a false negative. The problems above are all in what it says to
  *do*, or in one case (R4) what it accepts as evidence — never in what it
  noticed.
- **Domain routing held.** At no point was it unclear which manager owned a
  decision.

## Suggested order

1. **R1** — a dead-end diagnosis is worse than no diagnosis, and it is the first
   thing a new adopter hits.
2. **R4** — a false green is the most dangerous output a doctor can produce.
3. **R3** — needs a decision between two tools before it can be fixed; worth
   settling before more repos are adopted and diverge.
4. **R2** — largely resolves with R1's message.
5. **R5 / R6** — contract conformance; cheap, and both are law obligations.

## Cross-reference

- `11-uv-sync-prunes-toolchain` — the co-managed-venv model that R4 is the
  diagnostic-side consequence of.
- `13-doctor-outside-repo-diagnostics` — adjacent: doctor behavior in a repo
  shape it was not designed for. R1 is the partially-adopted variant.
- `14-bootstrap-ceremony-and-entrypoint` — R3 belongs to this arc.
- `../gitman/.scratch/projects/32-loci-core-adoption-issues/ISSUES.md` — the
  gitman half of the same session. G3 there (gitman un-adoptable without
  vendomat's exact wheelhouse) is the upstream cause of R4's false OK here.
