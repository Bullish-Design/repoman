# Kickoff prompt — Phase 5: `repoman doctor` warns when an approach-B manager's input is missing

Paste the block below into a **fresh session in the `repoman` repo**
(`/home/andrew/Documents/Projects/repoman`) to implement Phase 5. Phases 1–4 of the nix-provisioning
bridge are **done and merged to main** (`d3aa73b`); this is the remaining repoman-side polish.

---

You are implementing **Phase 5** of the nix-layer provisioning bridge in **repoman** — the agentic
devenv meta-module that composes the `*man` manager family. Phases 1–4 (merged to main) bridged the
nix-layer provisioning for five managers. Some managers are **approach-B**: their nix module
(toolchain / fetched binary / env) lives in the *manager's own repo* and is pulled in via a
**presence-gated import** that only fires when the consumer declares that manager's `devenv.yaml`
input (decision **R1** — devenv.yaml inputs are not transitive across a remote module import).

**The gap Phase 5 closes:** if a consumer selects an approach-B manager (`doc`, `spec`, `agent`) but
**forgets to declare its input**, the manager's venv CLI still installs (so `installed:<key>` is OK)
yet its nix provisioning is silently absent — the failure only surfaces later as a confusing
sub-doctor error. `repoman doctor` should instead emit a **clear, early WARN**: "doc selected but its
nix module isn't imported — add the `docman` input to devenv.yaml."

## Read first (orient before editing)

1. `.scratch/projects/05-nix-provisioning-bridge/01-findings.md` — the investigation; esp. Task 4
   (the input-transitivity crux + R1) and the module contract.
2. `.scratch/projects/05-nix-provisioning-bridge/02-implementation.md` — the running log of Phases
   1–4 and the **canonical approach-B pattern** (`imports = lib.optional (inputs ? X) …` +
   `optionalAttrs hasInput`).
3. `src/repoman/checks.py` — `run_self_check()` and `SelfCheck`; the `_LEVELS` map (`warn` → exit 0).
4. `src/repoman/registry.py` — the `Manager` dataclass + `REGISTRY`.
5. `modules/managers/{docman,alliman,mypi}.nix` — the three approach-B modules (what you'll add an
   env signal to). Contrast with the approach-A `copyroom.nix`/`zelligate.nix` (no input needed).

## The mechanism (why it needs a nix→python signal)

`checks.py` runs **inside the devenv shell** and cannot see whether a `devenv.yaml` input was
declared — that's nix-eval-time information. So each approach-B manager module must **signal
input-presence into the shell via an env var**, which `checks.py` reads. (`installed:<key>` checks the
venv CLI; `provisioned:<key>` is the new, orthogonal check for the nix layer.)

## Implementation (three parts + tests)

### 1. Registry — mark approach-B managers and the input each needs

In `src/repoman/registry.py`, add a field to `Manager`:

```python
nix_input: str = ""   # devenv.yaml input the manager's approach-B nix module needs; "" = none
```

Set it on the three approach-B entries (leave copy/git/test/session at `""`):

- `doc`   → `nix_input="docman"`
- `spec`  → `nix_input="allium-env"`
- `agent` → `nix_input="mypi-agent"`

### 2. Nix modules — export a presence signal when imported AND selected

In each of `modules/managers/{docman,alliman,mypi}.nix`, set a per-manager env var in the
**`hasInput` + `enabled`** branch (the same branch that flips the manager's own `enable`). The var
name is `REPOMAN_PROVISIONED_<KEY_UPPER>`. Example for `docman.nix` — fold the env into the existing
`optionalAttrs hasInput` block, gated on `enabled`:

```nix
(lib.optionalAttrs hasInput (lib.mkIf enabled {
  docman.enable = true;
  env.REPOMAN_PROVISIONED_DOC = "1";
}))
```

Do the equivalent in `alliman.nix` (`REPOMAN_PROVISIONED_SPEC`) and `mypi.nix`
(`REPOMAN_PROVISIONED_AGENT`) — restructure their current `optionalAttrs hasInput { … = mkIf enabled
… }` to an `optionalAttrs hasInput (mkIf enabled { … })` so the env sits beside the `enable`/settings.
Keep the existing behavior identical otherwise (re-verify the negative case still evals — see below).
**Watch mypi:** its `piAgent.enable = enabled` is set unconditionally-when-hasInput (because the
upstream default is TRUE); keep that as-is and add the env only under `mkIf enabled`.

### 3. checks.py — the `provisioned:<key>` warning

In `run_self_check()`, after the `installed:<key>` loop, add (with `import os` at top):

```python
for m in managers:
    if not m.nix_input:
        continue
    signalled = os.environ.get(f"REPOMAN_PROVISIONED_{m.key.upper()}") == "1"
    out.append(SelfCheck(
        f"provisioned:{m.key}",
        "ok" if signalled else "warn",
        "" if signalled
        else f"{m.key} selected but its nix module isn't imported — add the "
             f"'{m.nix_input}' input to devenv.yaml, then `devenv update` + repoman-sync",
    ))
```

`warn` is non-fatal (`_LEVELS["warn"] == 0`), so a missing input never fails the aggregate — it just
guides the fix. (The manager's own doctor still reports the real breakage if the user ignores it.)

### 4. Tests

- `tests/test_registry.py` — assert `nix_input` for doc/spec/agent (`"docman"`/`"allium-env"`/
  `"mypi-agent"`) and `== ""` for copy/git/test/session.
- `tests/test_checks.py` — mirror the existing style (monkeypatch `checks.shutil.which`; use
  `monkeypatch.setenv`/`delenv` for the signal):
  - `doc` selected, `REPOMAN_PROVISIONED_DOC` **unset** → `provisioned:doc` is `warn`; `self_check_exit == 0`.
  - `doc` selected, env set to `"1"` → `provisioned:doc` is `ok`.
  - an approach-A manager (e.g. `copy`) selected → **no** `provisioned:copy` row at all.
- `tests/test_cli.py` — optional: a `doctor --self-only` run on a manager with `nix_input` set and the
  env unset shows `WARN provisioned:` and still exits 0.

### 5. Verify

- Unit: `devenv shell -- pytest -q` (was 55 passing — keep them green plus the new ones).
- Consumer-example (`tests/consumer-example` declares docman/allium-env/mypi-agent inputs):
  `rm -f devenv.lock && devenv shell -- bash -c 'repoman-sync >/dev/null; repoman doctor --self-only'`
  → `provisioned:{doc,spec,agent}` all **OK** (inputs present), exit 0.
- Negative (the real point): an isolated throwaway consumer that selects `doc` but declares **no**
  docman input → `WARN provisioned:doc … add the 'docman' input`, and the run still exits 0.
  (Mirror the `/tmp` isolated-consumer pattern from the Phase 2/3 log.)

## Constraints / notes

- **Keep the approach-B eval-safety pattern intact:** re-run a negative-case eval (selected manager,
  input absent) after editing each module — it must still evaluate cleanly (no "option `docman' does
  not exist"). This is why the env goes inside `optionalAttrs hasInput`, never a bare `mkIf`.
- `installed:<key>` (venv CLI) and `provisioned:<key>` (nix module) are **orthogonal** — a manager can
  be installed-but-not-provisioned. Don't conflate them.
- Approach-A managers (`copy`, `session`) and pure-Python (`test`) get **no** `provisioned:` row.
  `git` is approach-A → `nix_input=""`. (Its latent Python-3.13 concern is a *separate* possible
  check — out of scope for Phase 5; note it if you add it.)
- All in-repo commands run via `devenv shell -- <cmd>`.
- Work on a branch; the user will say when to commit/push/merge. Update
  `.scratch/projects/05-nix-provisioning-bridge/02-implementation.md` (log) and the README checklist
  (tick Phase 5) when done.

## Out of scope (possible Phase 5b / 6)

- **Auto-scaffolding** the inputs into a consumer's `devenv.yaml` (R1's "repoman scaffolds" half) —
  Phase 5 is *detection/warning only*.
- Phase 6: any further test hardening + a final full-roster aggregate `repoman doctor` capstone.
