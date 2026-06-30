You are implementing Phase 1 of the `foreman` project — a new *man-family
work-item authoring tool for the Bullish-Design fleet. Phase 1 is SKILLS ONLY.

WORKING CONTEXT
- The design is settled and committed. Read it first, in order, before doing
  anything (paths under ~/Documents/Projects/repoman/.scratch/projects/08-issue-feature-workflow-helpers/):
    1. README.md          — packet index + status
    2. CONCEPT.md         — settled design; §9 = locked decisions, §7 = the skill surface you build
    3. CONTEXT.md         — the backends (TaskNotes/Allium/numbered packets), the knappy substrate, the seams
    4. KICKOFF.md         — the Phase-1 orchestration packet (your spec)
    5. 01-phase1-skills-only.md — the code-grounded, step-by-step implementation guide
- Also read the workspace `new-project` skill:
  ~/Documents/Projects/.agents/skills/new-project/SKILL.md

THE TASK (Phase 1 — skills only)
1. Birth the `foreman` repo via the `new-project` skill: check-name → copyroom new
   from gh:Bullish-Design/template-py → devenv build → wire repoman → fleetman index.
2. Author its agent skills in `foreman/skills/`:
   - foreman-issue   (L0 leaf  → a TaskNotes task note in the vault)
   - foreman-feature (L2 tree  → allium spec + numbered packet + linked tasks + vault project note + feature.toml)
   - foreman-promote (stretch  → adopt an existing leaf and grow it L0→L2)
   - shared/ assets: the TaskNotes frontmatter template, slug+repo-namespacing
     rules, and the vault-discovery order.
   Follow 01-phase1-skills-only.md exactly — it has the templates, slug rules,
   frontmatter schema, linking model, and file:line citations to the patterns to
   reuse (muse slug/path, loci-core adopt/reconcile, allium elicit, TaskNotes schema).

SCOPE FENCE (do NOT do these in Phase 1)
- No Python engine: leave src/foreman/ as the template-py stub.
- No repoman manager-registration: do not touch repoman's registry.py /
  modules/devenv.nix / repoman.lock. (That's Phase 2.)
- No knappy yet: Phase-1 skills author markdown directly from the documented
  templates; write them so the Phase-2 knappy swap is obvious.

ENVIRONMENT RULES (hard)
- Devenv only for in-repo commands: `devenv shell -- <cmd>`; never bare uv/python/pytest.
- The new `foreman` repo gets gitman wired (via template-py's repoman.managers).
  Route its version control through gitman (`devenv shell -- gitman …`); lane first;
  commit as you work; DO NOT push without an explicit ask.
- No AI-authorship trailers/attributions in commits, docs, or skills.
- No silent failures: check exit codes; treat empty/missing output as a failure to investigate.
- The skills write into a REAL Obsidian vault — they must confirm before writing
  and report exact paths after. Self-test against a throwaway slug + scratch vault.

FIRST MOVE
Read the five packet docs + the new-project skill, then propose a step-by-step
plan for my approval BEFORE scaffolding or writing any files.
