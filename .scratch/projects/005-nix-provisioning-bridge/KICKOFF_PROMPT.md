# Kickoff prompt — investigate & plan the nix-layer provisioning bridge

Paste the block below into a **fresh session in the `repoman` repo** to begin. This session's job is
**investigation + a written plan only — do NOT implement.** Produce the findings doc; flag anything
that would change a manager repo's standalone devenv behavior.

---

You are investigating a structural gap in **repoman** (`/home/andrew/Documents/Projects/repoman`),
the devenv meta-module that composes the `*man` manager family. repoman bridges its managers'
**Python/venv layer** (`repoman-sync` → `uv pip install`) but not their **nix layer** (system
packages, fetched/built binaries, `scripts.*`, `env.*`, `languages.*`, `enterShell`). Only `gitman`
gets nix provisioning, and only by hand-replicating it inline in `modules/managers/gitman.nix`. So
managers whose tools need nix-level setup (notably `spec`/alliman, `doc`/docman) half-work in
consumers: the Python CLI installs, but the tooling it drives is absent.

**Read these first, in order:**

1. `.scratch/projects/05-nix-provisioning-bridge/README.md` — this project's frame, scope, progress
   log, and status checklist.
2. `.scratch/INVESTIGATION-nix-provisioning.md` — the full brief (symptom, root-cause hypothesis,
   A/B/C mechanism options, tasks, deliverables, constraints, validation criteria).
3. `.scratch/projects/05-nix-provisioning-bridge/01-findings.md` — the skeleton you will fill in.

**Then do the five investigation tasks** (from the brief), recording everything in `01-findings.md`
and ticking the README checklist + appending to its progress log as you go:

1. **Map the mechanism** — `modules/devenv.nix`, `modules/managers/*.nix`,
   `modules/scripts/repoman-sync.sh`, `src/repoman/registry.py`, `CONCEPT.md` §6, `SPIKE.md`,
   `tests/consumer-example/`. Confirm/refute the two-layer model.
2. **Per-manager nix audit** — for each of the 7 managers, inspect its repo
   (`../<repo>/devenv.nix` + any `modules/`) and complete the audit table row (provisioning needed /
   reusable module? / pulled through today? / gap / proposed fix).
3. **Classify each failure** — (i) repoman nix-bridge gap (fixable by pulling the module through)
   vs (ii) genuine external requirement (consumer/host must provide; doctor should *warn*, not
   *fail*). Don't propose fixes for (ii) — specify what the consumer must supply.
4. **Design the general mechanism** — answer the central question (recommend A/B/C with rationale +
   migration cost); define the contract a manager repo satisfies to be nix-composable, consistent
   with the family contract (managers own their domain; repoman composes; gated on membership;
   `0/1/2/3`).
5. **Worked fix for spec/allium-env** — end to end: what to change in allium-env (expose its nix
   wiring as an importable module **without breaking its standalone devenv**) and in repoman's
   `alliman.nix` (import + gate on `spec`), so `allium-install-codex-skills` + the `allium` binary
   land in a consumer and `alliman doctor`/`install-skills` pass. Sketch any other (i)-class manager
   (e.g. `doc`/docman).

**Constraints:** keep provisioning **gated on roster membership**; prefer manager repos **owning**
their provisioning over repoman re-declaring it; keep the "import all manager modules statically,
gate each `config` on membership" idiom; say explicitly which managers are pure-Python and need no
module. Run all in-repo commands via `devenv shell -- <cmd>`.

**Deliverable:** a complete `01-findings.md` (two-layer confirmation, audit table, (i)/(ii)
classification, recommended mechanism + trade-offs, step-by-step spec fix plan + sketches).
**Do not edit `src/`, `modules/`, or `tests/`** this pass — investigation and plan only.
