# IMPLEMENTATION — 031-store-toolchain-python-shadowing

**Reads:** `../12-toolchain-single-instance/IMPLEMENTATION_GUIDE.md` (the venv provider this project
retires) · vendomat `docs/IMPLEMENTATION_PLAN.md` §Face D (the store provider this project adopts)
**Produces:** one source for the `*man` commands in every repo, the vendomat store closure (Face D),
and a `python` in `devenv shell` that always resolves to the project venv.
**Status of this file:** implementation guide, written 2026-09-10. Do the phases in order. Each step
names its repo, its file, its change, and the check that proves it landed.

---

## 0. The problem

**Symptom.** In `paloma-text-pipeline`, `devenv shell -- python -c "import pyphen"` failed with
`ModuleNotFoundError` right after a successful `uv sync`. `python` resolved to
`~/.local/share/repoman/venv/bin/python`, not to `.devenv/state/venv/bin/python`.

**Root cause.** The repoman meta-module, `modules/devenv.nix`, puts the whole machine toolchain venv
`bin/` first on `PATH` (v0.7.1 line 145; HEAD line 197, in the `cliProvider == "venv"` branch):

```nix
export PATH="${config.devenv.state}/venv/bin:$PATH"   # project venv
export PATH="$REPOMAN_TOOLCHAIN_VENV/bin:$PATH"       # machine venv, lands FIRST
```

The order is deliberate: it stops a stale manager CLI in the project venv from shadowing the shared
one. But `bin/` also holds that venv's `python`, `copier`, `typer`, `pygmentize`, and every other
dependency script. They shadow the project venv too. That part is a bug, not a design choice.

**Five related defects found in the same investigation:**

| # | Where | Defect | Evidence |
|---|---|---|---|
| P1 | repoman `modules/devenv.nix` | The venv provider puts the whole machine venv `bin/` first on `PATH`. | paloma PATH, 2026-09-10 |
| P2 | vendomat **v0.3.7** | The store closure also exposes `python`, `activate`, `tqdm`, `httpx`… (templateer was joined as a full venv). Eight repos pin v0.3.7. | `/nix/store/fbhsb7…-repoman-toolchain-core/bin` |
| P3 | repoman HEAD (untagged) | `79db869` (2026-09-08) made `cliProvider` default to `"store"`. A repo that tracks the repoman checkout and does not import vendomat gets no `REPOMAN_TOOLCHAIN_BIN`, so no manager commands. | 9 repos use `git+file:`/`path:` repoman without vendomat |
| P4 | repoman `src/repoman/checks.py` | `run_self_check` always checks the machine venv (`toolchain:venv`, `toolchain:lock`, `version:*`, `deps:toolchain`), also in store mode. | paloma doctor, 2026-09-10 |
| P5 | template-py genome v0.2.0 | Does not import vendomat, and pins `repoman_ref` v0.7.1. Every new repo starts on the venv provider. vendomat left the genome in `6826bb1` (2026-08-03), when vendomat was only a wheelhouse. Face D came later (2026-09-08). | `template/devenv.yaml.jinja` |
| P6 | devman skill pool `devenv-python-venv` | Tells agents that `devenv shell -- python …` uses the project venv. With P1 or P2, that is false. | `~/.config/devman/skills/devenv-python-venv/SKILL.md` |

**Local reorder does not work.** A `PATH` prepend in a consumer's `devenv.nix` runs before
repoman's `enterShell`, so repoman wins again. Do not add local `PATH` hacks.

**Already fixed (2026-09-10).** paloma now imports vendomat v0.3.9 and pins repoman v0.7.5. Its
`python` resolves to the project venv, and `repoman doctor` exits 0. Phase A lands that change.

---

## 1. Decisions

| # | Question | **Decision** | Why |
|---|---|---|---|
| **D1** | Which provider do consumers use? | **Store (vendomat Face D), everywhere.** | Its bin holds only the declared commands. One `flake.lock` pins the whole toolchain. vendomat's plan already calls the venv fallback "short-lived". |
| **D2** | Fix the venv provider or delete it now? | **Fix it now, delete it later (Phase J).** Put a command-only `commands/` dir on `PATH`, never `bin/`. | Tool-author repos (editable mode) still use the venv provider. They need a safe provider until Phase J gives them a replacement. |
| **D3** | What does doctor check? | **Only the active provider.** Add a `path:python` row for both providers. | A doctor that checks the wrong provider reports green for a broken shell. `path:python` is the alarm for this whole bug class. |
| **D4** | Minimum vendomat? | **v0.3.9.** Also make `mkToolchain` fail the build when `bin/` has an undeclared executable. | v0.3.7 leaks `python` (P2). A build-time guard stops a repeat. |
| **D5** | Genome shape | **template-py and template-nix import vendomat.** `repoman_ref` default ≥ v0.7.6. New `vendomat_ref` answer. | New repos must start on the store provider. |
| **D6** | Local PATH workarounds in consumers | **None.** Fix the providers upstream. | A local reorder does not win (§0), and it hides the fault. |
| **D7** | devman | **Out of scope.** devman stays a NixOS install through `nix-meta` (`devman` v0.5.1). | devman runs services, not only a dev CLI. vendomat's scope is the per-repo dev toolchain. See Phase J4. |

---

## 2. Work breakdown

| Phase | Repo(s) | What | Depends on | Ships alone? |
|---|---|---|---|---|
| A | paloma-text-pipeline | Land the applied fix | — | yes |
| B | 8 repos on vendomat v0.3.7 | Bump to v0.3.9 | — | yes |
| C | 10 repos without vendomat | Import vendomat | — | yes |
| D | vendomat | Build guard: no undeclared executables | — | with F |
| E | repoman | Venv provider `commands/` dir; provider-aware doctor; `path:python`; release 0.7.6 | C | yes |
| F | vendomat | Pin repoman v0.7.6; release v0.3.10 | D, E | yes |
| G | template-py, template-nix | Import vendomat; bump ref defaults; release | F | yes |
| H | devman skill pool | Correct `devenv-python-venv` (and `devenv-run-commands`) | — | yes |
| I | all consumers | `copyroom update` or bump pins | G | per repo |
| J | repoman, vendomat, each machine | Retire the machine venv | I + a design gate | last |

Phases A, B, C, D, and H are independent. Start them in any order. **Finish C before you tag repoman
0.7.6** (E6): the tag makes P3 reach every repo that bumps.

VC rule for every repo: run each change in its own gitman lane. Verify, save, land, push. Never run
raw `git` or `jj`. The canonical release sequence is in the `gitman` skill, section "Versioning".

---

## Phase A — paloma: land the applied fix

**State.** `devenv.yaml` and `devenv.lock` are already changed and verified. They sit in the working
copy of the lane `probe-investigation`, together with about 10,000 lines of other work.

**A1. Carve the change into its own lane.**

```bash
cd ~/Documents/Projects/paloma-text-pipeline
devenv shell -- gitman status
devenv shell -- gitman split --paths devenv.yaml devenv.lock --into toolchain-store \
  -m "fix(devenv): take the *man commands from vendomat's store closure"
```

`split` puts the two files on a new sibling lane on trunk. `@` stays on `probe-investigation`.
Do not include `.agents/**` (see Appendix B).

**A2. Verify on the new lane.**

```bash
devenv shell -- gitman switch toolchain-store
devenv shell -- bash -c 'command -v python; python -c "import pyphen, pydantic; print(\"ok\")"'
devenv shell -- repoman doctor
```

**Check:** `python` is `…/paloma-text-pipeline/.devenv/state/venv/bin/python`. Imports print `ok`.
Doctor exits 0.

**A3. Land, push, and go back to the work lane.**

```bash
devenv shell -- gitman land toolchain-store
devenv shell -- gitman push
devenv shell -- gitman switch probe-investigation
devenv shell -- gitman sync
```

**Note.** `.copier-answers.yml` still says `repoman_ref: v0.7.1`. Do not edit it by hand. Phase I
corrects it through `copyroom update`.

---

## Phase B — bump vendomat v0.3.7 to v0.3.9 (fixes P2)

**Repos:** `argentic`, `eventic`, `flora-core`, `flora-qc`, `poddantic`, `pyllij`,
`shellij`. Each pins `git+https://github.com/Bullish-Design/vendomat?ref=refs/tags/v0.3.7`.

Do these steps in each repo:

**B1.** `devenv shell -- gitman start vendomat-0.3.9`

**B2.** In `devenv.yaml`, change `ref=refs/tags/v0.3.7` to `ref=refs/tags/v0.3.9`.

**B3.** Re-lock and check the closure:

```bash
devenv shell -- bash -c 'command -v python; ls "$REPOMAN_TOOLCHAIN_BIN"'
jq -r '.nodes.vendomat.locked.ref' devenv.lock
```

**Check:** `python` resolves under `<repo>/.devenv/state/venv/bin` (or to no venv, if the repo has
none). It must never resolve under `/nix/store/…-repoman-toolchain-core`. The bin lists exactly
`copyroom docman gitman repoman templateer`. The lock says `refs/tags/v0.3.9`.

**B4.** `devenv shell -- repoman doctor` exits 0.

**B5.** Save, land, push:

```bash
devenv shell -- gitman save -m "fix(devenv): pin vendomat v0.3.9 (command-only closure)"
devenv shell -- gitman land
devenv shell -- gitman push
```

**Dev-shape repos.** `flora`, `loci.nvim`, `nix-nvim`, and `nix-paseo` use
`git+file:///home/andrew/Documents/Projects/vendomat`. They follow the checkout, which is past
`6e0e32d` (the uv2nix migration). Run only the B3 check in each.

---

## Phase C — import vendomat where it is missing (fixes P3)

**Repos that track the repoman checkout** (`git+file:` or `path:`): `foreman`, `forgelab`,
`image-gen-pipeline`, `inferference`, `llgym`, `lodestar`, `talkee`, `nix-desktop`, `nix-secrets`.
Their `devenv.lock` has no `rev` for repoman, so they evaluate the checkout as it is. Since
`79db869`, that means `cliProvider = "store"` with no closure.

**Repo on an old tag:** `agentman` (repoman v0.7.1, the same state paloma was in).

**C1. Diagnose.**

```bash
devenv shell -- bash -c 'echo "provider=$REPOMAN_CLI_PROVIDER"; command -v repoman python'
```

A broken repo prints `provider=store`, the stderr line
`RepoMan: cliProvider is "store" but REPOMAN_TOOLCHAIN_BIN is unset.`, and no `repoman`.

**C2. Add the input and the import.** In `devenv.yaml`:

```yaml
  # vendomat supplies the *man commands as one pinned Nix closure (Face D).
  # Its bin holds only the manager commands, so `python` stays the project venv.
  vendomat:
    url: "git+https://github.com/Bullish-Design/vendomat?ref=refs/tags/v0.3.9"
```

```yaml
imports:
  - vendomat/modules   # first, like repoman's own devenv.yaml
  - repoman
  # …keep the rest
```

Rules:
- Do not add `flake: false`. vendomat is a real flake.
- Do not add a `nixpkgs` `follows`. Without it, every repo gets the same shared closure store path.
- For `agentman`, also bump repoman to `ref=refs/tags/v0.7.5`.
- If the repo is the source of a roster tool (repoman, copyroom, gitman, docman, templateer), also
  set `vendor.toolchain.mode = "editable";` in `devenv.nix`. None of the repos above is a tool repo.
- If the repo has a `devenv.local.yaml`, check that it does not override `vendomat` to an old path.

**C3. Verify:** run the B3 and B4 checks. Also check `echo $REPOMAN_CLI_PROVIDER` prints `store`.

**C4.** Save, land, and push in a lane named `vendomat-store`.

**Gate for E6.** Run the static inventory (Appendix A1). No repo that imports repoman may show
`vendomat=no`.

---

## Phase D — vendomat: fail the build on undeclared executables (D4)

**D1. File:** `vendomat/lib/mkToolchain.nix`. At the start of the `postBuild` of the `symlinkJoin`,
add:

```nix
    postBuild = ''
      # The join exposes ONLY declared commands. An undeclared executable (a tool venv's
      # python, activate, tqdm) lands on every consumer's PATH ahead of the project venv
      # and shadows it. v0.3.7 shipped exactly that: bin/python from templateer.
      declared=" ${lib.concatStringsSep " " allCommands} "
      extra=""
      for f in "$out"/bin/*; do
        n=$(basename "$f")
        case "$declared" in
          *" $n "*) ;;
          *) extra="$extra $n" ;;
        esac
      done
      if [ -n "$extra" ]; then
        echo "mkToolchain: roster ${name} exposes undeclared executables:$extra" >&2
        exit 1
      fi

      mkdir -p $out/share/vendomat
      # …existing manifest lines stay unchanged
    '';
```

**D2. Tests:**
- In `tests/test_toolchain_nix.py`, add a text-level test: `mkToolchain.nix` contains
  `exposes undeclared executables`.
- In `tests/test_store_consumer_e2e.py` (gated by `VENDOMAT_E2E=1`), assert that the sorted
  `os.listdir($REPOMAN_TOOLCHAIN_BIN)` equals the sorted union of `tools.*.commands` from
  `$REPOMAN_TOOLCHAIN_MANIFEST`.

**D3. Verify:**

```bash
cd ~/Documents/Projects/vendomat
devenv shell -- testee verify --mode ci
nix build .#repoman-toolchain-core --no-link --print-out-paths
```

**Check:** the build succeeds, and its `bin/` holds the five commands only.

**D4.** Land the lane. Do not release yet. Phase F releases D and the repoman bump together.

---

## Phase E — repoman: fix the venv provider and the doctor (fixes P1, P4)

Run each step in its own lane from `~/Documents/Projects/repoman` (for example
`gitman start 031-venv-commands-dir`, then `gitman start 031-doctor-provider`).

### E1. The venv provider puts a command-only dir on PATH

**File 1:** `modules/scripts/repoman-sync.sh`, machine mode. Near the top of the machine-mode
section (line ~173), declare the command list:

```bash
# The commands a consumer may see from the shared venv (project 031). Keep this list
# equal to the registry's toolchain managers plus repoman itself —
# tests/test_repoman_sync.py pins the two together.
toolchain_commands="repoman copyroom gitman docman templateer vendomat"
```

After the manifest write (the `mv -f "$toolchain_manifest.tmp" …` line, ~616) and before the final
`echo`, add:

```bash
# bin/ holds python and every dependency's console scripts. The module puts commands/ on
# PATH, never bin/, so none of them can shadow a consumer's own venv (project 031).
# Built beside the target, then swapped in, so a consumer never sees a half-built dir.
commands_dir="$toolchain_venv/commands"
rm -rf "$commands_dir.tmp"
mkdir -p "$commands_dir.tmp"
for c in $toolchain_commands; do
  if [ -x "$toolchain_venv/bin/$c" ]; then
    ln -s "../bin/$c" "$commands_dir.tmp/$c"
  fi
done
rm -rf "$commands_dir"
mv "$commands_dir.tmp" "$commands_dir"
```

**File 2:** `modules/devenv.nix`, the `cliProvider == "venv"` branch (line ~197). Replace the single
line `export PATH="$REPOMAN_TOOLCHAIN_VENV/bin:$PATH"` with:

```nix
      # Project 031: commands/ holds ONLY the manager commands. bin/ also holds python
      # and every dependency script, and first on PATH it shadowed the consumer venv.
      if [ -d "$REPOMAN_TOOLCHAIN_VENV/commands" ]; then
        export PATH="$REPOMAN_TOOLCHAIN_VENV/commands:$PATH"
      else
        # A machine synced before 031 has no commands/ yet. Keep the old prepend so the
        # managers still resolve, and say how to stop it shadowing python.
        export PATH="$REPOMAN_TOOLCHAIN_VENV/bin:$PATH"
        echo "RepoMan: $REPOMAN_TOOLCHAIN_VENV/bin is first on PATH and shadows this repo's python." >&2
        echo "RepoMan:   re-run repoman-sync --machine, or import vendomat (store provider)." >&2
      fi
```

Keep the comment above it ("ORDER IS LOAD-BEARING"). The order rule still holds for `commands/`.
Do not change `cliBinExpr`. Tasks exec absolute paths under `bin/`, which does not affect `PATH`.

**Tests:**
- `tests/test_modules_nix.py`. Update three tests to expect the `commands/` prepend:
  `test_meta_module_exports_toolchain_venv_in_enter_shell` (line 31),
  `test_toolchain_bin_is_prepended_after_the_consumer_venv_so_it_wins` (line 37), and
  `test_venv_provider_still_exports_the_toolchain_venv` (line 163). Add
  `test_venv_provider_prepends_whole_bin_only_in_the_fallback`. It asserts that the `bin` prepend
  appears only inside the `else` branch.
- `tests/test_repoman_sync.py`. Add three tests:
  - `test_machine_writes_a_command_only_dir`: after a machine sync, `commands/` holds the listed
    commands and no `python`.
  - `test_machine_commands_dir_skips_absent_commands`: a command missing from `bin/` gets no link.
  - `test_machine_command_list_matches_registry`: parse `toolchain_commands` from the script, and
    compare it with the toolchain managers in `src/repoman/registry.py` plus `repoman`.

**Machine step (after E1 lands):**

```bash
cd ~/Documents/Projects/repoman && devenv shell -- repoman-sync --machine
ls ~/.local/share/repoman/venv/commands
```

**Check:** the dir lists the manager commands only.

### E2. Doctor checks the active provider only

**File:** `src/repoman/checks.py`, `run_self_check` (line 612).

1. At the top, read the provider: `provider = cli_provider()`.
2. **Store branch** (new helper `_store_self_check(managers) -> list[SelfCheck]`). Rows:
   - `toolchain:store`: `ok` if `REPOMAN_TOOLCHAIN_BIN` is set and `<bin>/repoman` is executable.
     Else `fail`: "cliProvider is store but no closure — add vendomat/modules to devenv.yaml
     imports".
   - `toolchain:manifest`: read `REPOMAN_TOOLCHAIN_MANIFEST` with `json.load`. `warn` if it is
     missing or unparseable. The shape is
     `{"python": "3.13", "roster": "core", "tools": {"<name>": {"commands": [...], "store": "...", "version": "..."}}}`.
   - `lock:<key>`, for each `install == "toolchain"` manager: `ok` if a tool in `tools` lists
     `m.command` in its `commands`. Else `fail`: "roster <roster> does not provide <command>".
   - `version:<tool>`: an informational `ok` row per tool, with the text `"<name> <version>"`.
   - Do not run `version_checks(venv, …)` or `dependency_checks(venv)` in store mode. The closure was
     resolved from each tool's `uv.lock`, and vendomat guards lock drift at build time (`a14f4f1`).
3. **Venv branch:** keep the current code. Add a `toolchain:commands` row. It is `warn` when
   `<venv>/commands` is missing: "re-run `repoman-sync --machine` — bin/ shadows python until you
   do".
4. **Both providers:** add a `path:python` row. Only emit it when `DEVENV_ROOT` is set and
   `consumer_venv_bin()/python` exists. Compare `shutil.which("python")` with that path. `ok` if
   they are equal. Else `warn`: "python resolves to <X>, not the project venv <Y> — a dir earlier on
   PATH shadows it". This row is the regression alarm for P1 and P2.
5. Keep `installed:<key>` for both providers. It already resolves through `manager_binary()`, which
   is provider-aware.

**Tests** in `tests/test_checks.py`. Build fixtures with a temporary bin dir that holds an executable
`repoman`, and a temporary JSON manifest. Set `REPOMAN_CLI_PROVIDER`, `REPOMAN_TOOLCHAIN_BIN`, and
`REPOMAN_TOOLCHAIN_MANIFEST` with `monkeypatch`. Add these tests:
- `test_store_mode_does_not_check_the_machine_venv`: no `toolchain:venv` row, even when the venv is
  absent.
- `test_store_mode_without_bin_fails_actionably`
- `test_store_mode_reads_versions_from_the_manifest`
- `test_store_mode_roster_missing_a_manager_fails`
- `test_path_python_ok_when_project_venv_wins`
- `test_path_python_warns_when_shadowed`: put a fake `python` in an earlier `PATH` dir.
- `test_venv_mode_warns_without_commands_dir`

Keep the existing venv-mode tests. Make them set `REPOMAN_CLI_PROVIDER=venv` explicitly, because
the default is now `store`.

**Docs:** in the `README.md` doctor table (lines 160–161), mark `toolchain:venv` and
`toolchain:lock` as "venv provider only". Add rows for `toolchain:store`, `toolchain:manifest`,
`toolchain:commands`, and `path:python`.

### E3. Changelog

In `CHANGELOG.md` "Unreleased", add a section for project 031 that names:
- the store default (`79db869`)
- the `commands/` dir
- the provider-aware doctor
- `path:python`
- the upgrade note: "a repo that tracks this module without importing vendomat must add
  `vendomat/modules` (or set `repoman.cliProvider = "venv"`)"

### E4. Verify

```bash
cd ~/Documents/Projects/repoman
devenv shell -- testee verify --mode ci
```

This is the same gate that `gitman.toml` `[publish].verify` runs.

### E5. Pre-release gate

- Phase C is finished (Appendix A1 shows no `vendomat=no` row).
- `repoman-sync --machine` has been re-run on this machine (the `commands/` dir exists).

### E6. Release 0.7.6

```bash
devenv shell -- gitman start repoman-0.7.6-version-bump
devenv shell -- gitman version bump patch
devenv shell -- gitman save -m "chore: bump version to 0.7.6"
devenv shell -- gitman land
devenv shell -- gitman push
devenv shell -- gitman release
```

**Check:** `git ls-remote --tags origin` lists `v0.7.6`. Run it through `devenv shell -- gitman`
if gitman exposes that operation; else read the GitHub tags page.

---

## Phase F — vendomat: ship the guard and repoman 0.7.6

**F1.** In `vendomat/flake.nix` (line ~40), change the repoman input to
`ref=refs/tags/v0.7.6`. Then re-lock that one input:

```bash
cd ~/Documents/Projects/vendomat
devenv shell -- nix flake update repoman
```

**F2. Verify:**

```bash
devenv shell -- testee verify --mode ci
VENDOMAT_E2E=1 devenv shell -- testee verify --mode quick
p=$(nix build .#repoman-toolchain-core --no-link --print-out-paths)
ls "$p/bin"; jq -r '.tools.repoman.version' "$p/share/vendomat/toolchain.json"
```

**Check:** the tests pass, including `test_fleet_shape.py`. The bin holds five commands. The manifest
says `0.7.6`.

**F3.** Release v0.3.10 with the six-step gitman sequence (bump `patch`).

---

## Phase G — genomes ship vendomat (fixes P5)

### template-py

**G1. File `copier.yml`.** Change the `repoman_ref` default to `"v0.7.6"`. Add after it:

```yaml
vendomat_ref:
  type: str
  help: >-
    Published vendomat tag the devenv input pins (fleet shape). vendomat supplies
    the *man commands as one Nix closure; its bin holds only those commands.
  default: "v0.3.10"
```

**G2. File `template/devenv.yaml.jinja`.** After the `repoman:` input, add:

```yaml
  # vendomat: the *man commands (repoman, copyroom, gitman, docman, templateer) as
  # one pinned Nix closure. Its bin holds only those commands, so `python` stays this
  # repo's venv. A real flake input — no `flake: false`, and no nixpkgs follows, so
  # every repo shares one closure store path.
  vendomat:
    url: "git+https://github.com/Bullish-Design/vendomat?ref=refs/tags/{{ vendomat_ref }}"
```

In `imports:`, add `- vendomat/modules` as the first entry.

**G3. File `template/devenv.nix.jinja`.** Replace the comment "the pure-CLI managers
(copyroom/gitman) come from the system-wide toolchain venv (`repoman-sync --machine`) instead" with
"the pure-CLI managers come from vendomat's store closure instead".

**G4. File `template/.agents/devenv/languages-python.md`.** Next to the `sys.executable` example
(line 37), add: "It must print this repo's `.devenv/state/venv/bin/python`. Any other path means a
dir earlier on PATH shadows the venv; see the `devenv-python-venv` skill."

**G5.** Check `scenarios/py/basic.yml` and `scenarios/py/probe.yml`. If either pins `repoman_ref`,
bump it.

**G6. Render, test, and refresh the golden:**

```bash
cd ~/Documents/Projects/template-py
devenv shell -- copyroom render py basic
grep -n vendomat generated/py/basic/devenv.yaml
(cd generated/py/basic && devenv shell -- bash -c 'command -v python repoman; echo $REPOMAN_CLI_PROVIDER')
devenv shell -- copyroom golden py basic --refresh
devenv shell -- copyroom release-check py
```

**Check:** the rendered repo prints its own venv `python`, a store `repoman`, and `store`.
`release-check` passes.

**G7.** Release template-py v0.2.1 (six-step gitman sequence).

### template-nix

**G8.** `template/devenv.yaml.jinja` uses the dev shape (`path:{{ repoman_dev_root }}/repoman/modules`).
Add vendomat in the same shape, and add `- vendomat/modules` first in `imports:`:

```yaml
  vendomat:
    url: path:{{ repoman_dev_root }}/vendomat
```

Render, run the golden refresh and `release-check` for its template id, then release v0.3.1. Moving
template-nix to the fleet shape is a separate change.

---

## Phase H — correct the agent skills (fixes P6)

**Source.** devman's skill pool: `~/.config/devman/skills/devenv-python-venv/SKILL.md`.
`~/.config/devman` is a local git repo with no remote. Each project gets a real-file copy, for
example `~/.config/devman/projects/paloma-text-pipeline/agents/skills/devenv-python-venv/SKILL.md`.
It was byte-identical to the pool on 2026-09-10. A repo's `.agents` is a symlink into that project
dir.

**H1.** In the pool file, insert before "Fix — install the deps…":

```markdown
## First check which python you get

    devenv shell -- bash -c 'command -v python'

It must print `<repo>/.devenv/state/venv/bin/python`. Any other path means a dir earlier on
PATH shadows the project venv. `uv sync` cannot fix that:

- `~/.local/share/repoman/venv/bin/python` — the repo uses RepoMan's legacy venv provider.
  Import vendomat (`vendomat/modules`, tag v0.3.9 or later) so the store provider supplies
  the *man commands.
- `/nix/store/…-repoman-toolchain-core/bin/python` — vendomat is older than v0.3.9. Bump the tag.

Do not reorder PATH in the repo's devenv.nix. RepoMan's enterShell runs later and wins.
From repoman 0.7.6, `repoman doctor` reports this as `path:python`.
```

Change the sentence "Then run your command **through the shell** (`devenv shell -- python …`) so it
uses that venv" to end with "…so it uses that venv — after the check above passes."

**H2.** Open `~/.config/devman/skills/devenv-run-commands/SKILL.md`. If it claims that
`devenv shell -- python` always reaches the project venv, add one line that points to the H1 check.

**H3. Propagate and check.** Enter one repo's shell, then compare:

```bash
cmp ~/.config/devman/skills/devenv-python-venv/SKILL.md \
    ~/.config/devman/projects/paloma-text-pipeline/agents/skills/devenv-python-venv/SKILL.md
```

I did not confirm which command copies pool skills into project dirs. The project copies were
rewritten at shell entry on 2026-09-10. If `cmp` still differs after a shell entry, find the writer in
devman `.scratch/projects/025-the-link-plane/GUIDE-01-agent-plane.md` before you copy by hand.

**H4.** Commit the pool change with the VC flow that `~/.config/devman` uses.

---

## Phase I — converge the consumers

**I1. template-py consumers** (after G7):

```bash
devenv shell -- gitman start converge-template-py-0.2.1
devenv shell -- copyroom update
```

Resolve `devenv.yaml` conflicts in favor of the genome's vendomat block. For paloma, this drops the
local comment from Phase A and corrects `.copier-answers.yml` (`repoman_ref: v0.7.6`,
`vendomat_ref: v0.3.10`). Run the B3/B4 checks, then save, land, and push.

**I2. Repos without copier answers** (`flora` and the Phase B/C repos not born from
template-py): bump the pins by hand to repoman `v0.7.6` and vendomat `v0.3.10`. The archived
personal-layer source is not an active consumer. Run the B3/B4 checks, then land.

**I3. Fleet check:** run Appendix A2. Every row shows `store`, a project-venv `python`, and a store
`repoman`.

---

## Phase J — retire the machine venv (design gate)

vendomat is the only provider when nothing reads `~/.local/share/repoman/venv`. One user of the
venv provider remains after Phase I: **tool-author repos**. vendomat's `mode = "editable"` sets
`repoman.cliProvider = "venv"` (repoman's own `devenv.nix` line 28), so the repo runs its own
working tree and takes the other managers from the machine venv.

**J1. Design (write a CONCEPT before code).** Give editable mode a store-based replacement:
- vendomat delivers the roster closure without the repo's own tool. For example, a
  `vendor.toolchain.self = "<tool>"` that `mkToolchain` filters out.
- The repo's own venv (`.devenv/state/venv/bin`) provides that one tool.
- repoman task execs for the self tool resolve to the consumer venv, not `REPOMAN_TOOLCHAIN_BIN`.

Decide whether the self tool may appear on `PATH` ahead of the closure, and how doctor reports it.

**J2. After J1 ships in every tool repo:**
- repoman: remove `"venv"` from the `cliProvider` enum, `toolchainVenvExpr`, the venv
  `enterShell` branch, `repoman-sync --machine`, `toolchain_venv()`, and the `toolchain:venv`,
  `toolchain:lock`, `toolchain:commands`, `version_checks`, and `dependency_checks` venv paths.
- Decide the future of the machine `repoman.lock`. Face D's source of truth is vendomat's
  `flake.lock`.
- vendomat: remove the "venv escape hatch" wording from `vendor.toolchain.enable`.

**J3. Each machine:** check first, then delete:

```bash
rg -l 'REPOMAN_TOOLCHAIN_VENV|repoman/venv' ~/Documents/Projects/*/devenv.nix ~/Documents/Projects/*/devenv.yaml
rm -rf ~/.local/share/repoman/venv
```

Delete only when `rg` prints nothing.

**J4. devman.** It stays a NixOS install through `nix-meta` (`flake.nix` line ~205, devman v0.5.1).
The devman CLI in a dev shell comes from `/run/current-system/sw/bin`. To serve it from vendomat as
well, add a separate roster (for example `ops`) to vendomat. That is a separate decision, because
devman's NixOS module also runs services that a devenv closure cannot own.

---

## Appendix A — fleet checks

**A1. Static inventory** (no shell entry, fast):

```bash
cd ~/Documents/Projects
for d in */; do d=${d%/}; y="$d/devenv.yaml"
  [ -f "$y" ] && grep -q repoman "$y" || continue
  r=$(grep -A1 -E '^\s*repoman:'  "$y" | grep -oE 'url: *"?[^"]+' | sed 's/url: *"\{0,1\}//')
  v=$(grep -A1 -E '^\s*vendomat:' "$y" | grep -oE 'url: *"?[^"]+' | sed 's/url: *"\{0,1\}//')
  i=$(grep -qE '^\s*-\s*vendomat' "$y" && echo yes || echo no)
  printf '%-22s vendomat=%-3s repoman=%s\n    vendomat-url=%s\n' "$d" "$i" "${r:-none}" "${v:-none}"
done
```

**A2. Live check** (enters every shell; slow; it re-locks changed inputs):

```bash
cd ~/Documents/Projects
for d in */; do d=${d%/}
  [ -f "$d/devenv.yaml" ] && grep -q repoman "$d/devenv.yaml" || continue
  out=$(cd "$d" && timeout 300 devenv shell -- bash -c \
    'printf "%s | %s | %s\n" "${REPOMAN_CLI_PROVIDER:-?}" "$(command -v python)" "$(command -v repoman)"' \
    2>/dev/null | tail -1)
  printf '%-22s %s\n' "$d" "$out"
done
```

Expected per row: `store | <repo>/.devenv/state/venv/bin/python | /nix/store/…-repoman-toolchain-core/bin/repoman`.

## Appendix B — paloma `.agents` shows as deleted

devman's link plane replaced paloma's `.agents` with a symlink to
`~/.config/devman/projects/paloma-text-pipeline/agents`. git does not follow a symlinked directory,
so it reports every tracked file under `.agents/` as deleted. Keep those deletions out of toolchain
lanes. Decide separately whether to untrack them (`gitman untrack .agents`) or keep them. Follow the
policy in devman project 025.

## Appendix C — rollback

| Phase | Rollback |
|---|---|
| A, B, C | `gitman undo`, or restore the old tag in `devenv.yaml` and re-enter the shell. |
| D, F | Consumers stay on the previous vendomat tag. Nothing moves until they bump. |
| E | The `else` fallback keeps pre-031 machines working. Consumers on 0.7.5 are not affected until they bump. |
| G | Genome releases are tagged. Consumers converge only on `copyroom update`. |
| J | Do not start J until I3 is green. Re-create the venv with `repoman-sync --machine` from a pre-J repoman tag. |

## Appendix D — evidence (2026-09-10)

| Item | Value |
|---|---|
| paloma PATH before the fix | `~/.local/share/repoman/venv/bin` : `<repo>/.devenv/state/venv/bin` : … |
| repoman module at v0.7.1 | rev `a83b571`, `modules/devenv.nix` lines 128–145 |
| `cliProvider` option added | `01f3c81`, first in v0.7.2. Shell-safe store bin: `b3a7cbf`, v0.7.4 |
| `store` default | `79db869` (2026-09-08), untagged; `checks.py` `_DEFAULT_CLI_PROVIDER = "store"` |
| vendomat v0.3.7 closure | `/nix/store/fbhsb7nz5hr91sqwr3mqn0nvpy1g4fqs-repoman-toolchain-core`: exposes `python`, `activate*`, `distro`, `genai-prices`, `httpx*`, `idna`, `normalizer`, `pai`, `tqdm` |
| vendomat v0.3.9 closure | `/nix/store/z6ayz3iz2c3plgidf7kfslwnwrzc7yk2-repoman-toolchain-core`: `copyroom docman gitman repoman templateer` only |
| uv2nix migration (the fix for P2) | `6e0e32d`, `a14f4f1`: first in v0.3.8 |
| vendomat left template-py | `6826bb1` (2026-08-03, project 12) |
| paloma after the fix | `python` → project venv; `repoman doctor` exit 0; `gitman status` healthy |
