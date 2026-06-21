# 05 — The nix-layer provisioning bridge

**Problem.** repoman bridges its managers' **Python/venv layer** (`repoman-sync` →
`uv pip install` each selected manager into the devenv venv) but **not** their **nix layer**
(system packages, fetched/built binaries, `scripts.*`, `env.*`, `languages.*`, `enterShell`
hooks). Only `gitman` gets nix provisioning, and only by **hand-replicating** its needs inline in
`modules/managers/gitman.nix`. Every other manager module wires *only* a doctor/status task. So any
manager whose tool needs nix-level setup half-works in a consumer: the Python CLI installs, but the
tooling it drives is missing.

**Reproduced** in consumer `karakeeper` (full roster): self-check + `test` + `git` green, but
`spec` (alliman) can't find `allium-install-codex-skills` or the `allium` binary, and `agent` /
`session` / `doc` doctors fail. See the full brief.

## Source brief

The detailed investigation brief lives at **[`../../INVESTIGATION-nix-provisioning.md`](../../INVESTIGATION-nix-provisioning.md)**
(repo-root `.scratch/`). It carries the symptom, root-cause hypothesis, the A/B/C mechanism options,
the investigation tasks, deliverables, and the constraints to honor. Read it first. This directory
is the **working space** that brief asks for — notes, the audit, the recommendation, and the plan.

## Central question

How should a manager's nix-layer provisioning reach the consumer devenv when that manager is
selected? Evaluate:

- **(A)** repoman re-declares it inline per manager module (today's gitman approach).
- **(B)** each manager repo exposes a reusable devenv module; repoman's `managers/<m>.nix`
  **imports + gates** it on roster membership (the user's stated intent).
- **(C)** hybrid — pure-pip managers need nothing; native/asset managers expose a module.

Recommend one, justify it, note migration cost.

## Deliverables (this project)

1. **[`01-findings.md`](01-findings.md)** — the written findings doc: two-layer confirmation, the
   per-manager audit table, the (i) nix-bridge-gap / (ii) genuine-external-requirement
   classification, the recommended mechanism with trade-offs, and a step-by-step fix plan for
   **spec** + a sketch for any other (i)-class managers.
2. (later, separate) implementation guide(s) once the plan is reviewed.

**Do not implement yet** — investigation + plan only, for review. Flag any change that would alter a
manager repo's own standalone devenv behavior.

## Scope — audit all seven managers

`copy` (copyroom) · `git` (gitman) · `test` (testee) · `doc` (docman) · `session` (zelligate) ·
`agent` (mypi-agent) · `spec` (alliman/allium-env).

## Progress log

> Append-only; newest at the bottom. Date · what was done · what's next.

- **2026-06-20** — Project scaffolded from the root investigation brief. Next: map the mechanism
  (`modules/devenv.nix`, `managers/*.nix`, `repoman-sync.sh`, `registry.py`, `CONCEPT.md` §6,
  `SPIKE.md`, `tests/consumer-example/`) and begin the per-manager audit in `01-findings.md`.
- **2026-06-20** — Investigation complete (Tasks 1–5). Read repoman's mechanism (CONCEPT §6, SPIKE,
  all `managers/*.nix`) → two-layer model **confirmed**; nix layer bridged only for `git` (approach
  A). Ran 7 parallel grounded per-repo audits. Wrote up full `01-findings.md`: audit table, (i)/(ii)
  classification, the **devenv.yaml input non-transitivity crux**, the approach-A/B/none hybrid
  recommendation + module contract, and the end-to-end `spec` fix plan (+ sketches for doc/agent/
  copy/git/session). **Key surprises:** copyroom isn't pure-pip (needs git+patch); gitman's only gap
  is a Python 3.13 pin; docman's module is already import-ready; mypi's module is importable only
  with bootstrap/telegram off (CLI-shadow risk); allium-env needs extraction **and** has a hard
  blocker R4 (git-ignored asset trees won't materialize through a flake:false input).
  **Next:** review the 3 open questions (R1-vs-R2 input strategy; upstream warn-vs-fail; a small
  verification spike) before implementing. No code touched.

- **2026-06-21** — **Phase 5 done + verified.** `repoman doctor` now warns (non-fatal) when a selected
  approach-B manager (`doc`/`spec`/`agent`) is missing its `devenv.yaml` input. Mechanism: each module
  signals `env.REPOMAN_PROVISIONED_<KEY>=1` (inside `optionalAttrs hasInput (mkIf enabled …)`),
  `checks.py` reads it as `provisioned:<key>` (orthogonal to `installed:<key>`). Registry gains
  `Manager.nix_input`. 61 unit tests pass; positive (consumer-example, inputs present → all OK) and
  negative (isolated consumer, input absent → WARN, exit 0, clean eval) both verified. Detail in
  [`02-implementation.md`](02-implementation.md). **Next:** Phase 6 (full-roster capstone re-verify).

## Status checklist

- [x] Task 1 — Map the mechanism; confirm/refute the two-layer model — **confirmed**
- [x] Task 2 — Per-manager nix-provisioning audit (7 rows) — **done (7 grounded audits)**
- [x] Task 3 — Classify each failure (i) nix-bridge gap vs (ii) external requirement
- [x] Task 4 — Design the general mechanism — **hybrid A/B/none + module contract; input-transitivity crux surfaced**
- [x] Task 5 — Worked end-to-end fix for spec/allium-env — **plan written + sketches for the rest**
- [x] Findings doc complete and ready for review — **see [`01-findings.md`](01-findings.md)**
- [x] Review the 3 open questions → decisions taken (R1; upstream warn-vs-fail deferred; spike = doc)
- [x] **Implementation Phase 1** (approach A): copy (git+gnupatch), session (ZELLIGATE_* env) — verified
- [x] **Implementation Phase 2** (approach B spike): doc/docman — verified, mechanism confirmed
- [x] **Implementation Phase 3** (approach B): spec/allium-env (module extracted upstream) — verified green
- [x] **Phase 4**: agent/mypi (import pi-agent.nix; bootstrap=manual_only, telegram off; CLI-shadow) — verified
- [x] **Phase 5**: repoman R1 doctor warnings (selected approach-B manager missing its input) — verified
      (registry `nix_input`; modules signal `REPOMAN_PROVISIONED_<KEY>`; `checks.py` `provisioned:<key>`
      warn; 61 tests pass; positive + negative + eval-safety verified)
- [ ] **Phase 6**: unit tests + full-roster consumer-example re-verify

> Implementation detail + verification evidence: [`02-implementation.md`](02-implementation.md).
> Phases 1–4 are **merged to main** (`d3aa73b`); allium-env's `modules/allium.nix` extraction is
> merged to allium-env main (`ca88652`).

## Constraints to honor (from the brief)

- Manager nix provisioning stays **gated on roster membership** (no `git` ⇒ no Rust; no `spec` ⇒
  no allium binary fetch).
- Prefer the manager repo **owning** its provisioning over repoman re-declaring it.
- `imports` can't depend on `config` ⇒ keep the "import all manager modules statically, gate each
  one's `config` on membership" idiom.
- Pure-Python (pip-only) managers need **no** nix module — say so explicitly.
- All in-repo commands run via `devenv shell -- <cmd>`.

## Validation criteria (for the eventual fix, not this pass)

In a consumer (`tests/consumer-example` or `karakeeper`): `devenv shell -- repoman doctor` exits 0
(or only (ii)-class warnings), with `allium-install-codex-skills` and `allium` on PATH and
`alliman doctor` green.

## Key files

- **repoman:** `modules/devenv.nix`, `modules/managers/{gitman,alliman,testee,copyroom,docman,zelligate,mypi}.nix`,
  `modules/scripts/repoman-sync.sh`, `src/repoman/registry.py`, `CONCEPT.md`, `SPIKE.md`,
  `tests/consumer-example/`
- **manager repos:** `../{copyroom,gitman,testee,docman,zelligate,mypi-agent,allium-env}` — esp.
  `allium-env/devenv.nix` (the worked example: `options.allium.*`,
  `scripts.allium-install-codex-skills`, the `alliumCli` derivation, `env.*`, `enterShell`).
