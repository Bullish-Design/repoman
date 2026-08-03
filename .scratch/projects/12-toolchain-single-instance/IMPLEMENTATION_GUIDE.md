# IMPLEMENTATION — 12-toolchain-single-instance

**Reads:** `CONCEPT.md` (this dir) — the blueprint · `../11-uv-sync-prunes-toolchain/FINDINGS.md` §6–§7 — the analysis
**Produces:** a system-wide shared toolchain venv for the pure-CLI managers + testee as a per-repo uv dev dep.
**Status of this file:** implementation guide. Every step below is written to be executed in order; each
carries its exact file, its diff shape, and the check that proves it landed.

---

## 0. Decisions taken (closes CONCEPT §11)

The blueprint left five questions open. They are resolved here so the steps are unambiguous; each
decision is marked **D<n>** and referenced from the step that implements it. Change them here first if
you disagree — the steps follow mechanically.

| # | Question (CONCEPT §11) | **Decision** | Why |
|---|---|---|---|
| **D1** | Shared-venv path resolution in nix: `builtins.getEnv` at eval vs. runtime | **Runtime, never eval.** Nix emits a *shell expression* `${REPOMAN_TOOLCHAIN_VENV:-${XDG_DATA_HOME:-$HOME/.local/share}/repoman/venv}` that bash expands in `enterShell` and in every task exec. | `builtins.getEnv "HOME"` bakes one user's absolute path into the module's eval result — it breaks pure eval, poisons the eval cache across users, and silently yields `/repoman/venv` when `HOME` is unset (CI, nix-daemon builds). The runtime form costs nothing and is correct everywhere. **Consequence:** tasks must not rely on `enterShell` having run (devenv tasks do not source it), so tasks use the expression directly rather than a bare PATH-resolved name. |
| **D2** | Machine-lock location | **repoman checkout root** (`$REPOMAN_ROOT/repoman.lock`, default `$DEVENV_ROOT`). | It is where copyroom convergence points and it stays versioned with the fleet refs. Plus: `--machine` copies the lock it installed from into the shared venv (see D7), so consumers can still audit it. |
| **D3** | pyjutsu wheel at bootstrap | **repoman's own devenv gains the `vendomat` input + `vendor.enable`.** `repoman.nativeBuild`/maturin stays as the wheelhouse-less escape hatch. | Smallest diff, mirrors what consumers do today, ~0 min vs ~7.5 min for a source build. Consumers lose the input entirely — it moves one level up, to the machine bootstrap context. |
| **D4** | `[dependency-groups] dev` vs `[project.optional-dependencies] dev` | **`[dependency-groups] dev`** (PEP 735, uv-native, installed by a bare `uv sync`). | It is on by default, so the documented one-liner is `uv sync` with no flags and no way to forget an extra. Docs standardize on `uv sync --all-extras` (groups + extras) as the single recommended command. |
| **D5** | Doctor UX for uv-declared managers | **Generic, not testee-specific.** `Manager.install ∈ {"toolchain","uv"}` in the registry drives which check runs: `lock:<key>` for toolchain managers, **`uv:<key>`** for uv-declared ones. | The roster, not `checks.py`, decides where a manager lives. A future uv-declared manager is a one-field registry edit. `uv:test` is named for what it asserts (declared in the uv graph); reusing `lock:test` would name a file that no longer exists in a consumer. |
| **D6** | Consumer `repoman-sync` when the shared venv is absent | **Fail (exit 2)** with the bootstrap one-liner, not warn. | Consumer mode's only remaining job is `repoman install-skills` — which *is* the shared `repoman`. Warning and then dying at `command not found` is strictly worse than one clear message. CONCEPT §5.1's "warn" predates the observation that the two are the same binary. |
| **D7** | *(new)* How does a consumer's doctor validate a machine-level lock it cannot see? | **`--machine` writes `$REPOMAN_TOOLCHAIN_VENV/repoman-toolchain.toml`** — a verbatim copy of the lock it synced from, prefixed with a `# synced from <path>` comment. | Keeps the `lock:<key>` self-checks alive fleet-wide (they were the spike's whole point) without teaching consumers where the repoman checkout is. Also makes "shared venv is older than the lock" diagnosable later. |

Two further constraints inherited from CONCEPT, restated because steps depend on them:

- **Toolchain python floor = 3.13** (`gitman >=3.13`, pyjutsu `cp313-abi3`). The consumer's python
  version becomes irrelevant to the toolchain.
- **`modules/managers/testee.nix` does not change.** `${venvBin}/testee` stays correct. Any diff to that
  file in this project is a bug.

---

## 1. Work breakdown at a glance

| Step | Phase | Files | Ships alone? |
|---|---|---|---|
| 1 | Machine manifest | `repoman.lock` (new, root), `.gitignore` | yes |
| 2 | Sync script | `modules/scripts/repoman-sync.sh` | yes |
| 3 | Bootstrap context | `devenv.yaml`, `devenv.nix` (repoman's own) | yes |
| 4 | Meta-module | `modules/devenv.nix` | with 5 |
| 5 | Manager modules | `modules/managers/{gitman,copyroom,docman}.nix` | with 4 |
| 6 | Registry | `src/repoman/registry.py` | with 7 |
| 7 | Doctor | `src/repoman/checks.py` | with 6 |
| 8 | Tests | `tests/test_repoman_sync.py`, `test_checks.py`, `test_cli.py`, `test_registry.py`, new `test_modules_nix.py` | with 2–7 |
| 9 | Docs & skills | `src/repoman/devman/assets/**`, `docs/SKILLS.md`, `CONCEPT.md`, `SPIKE.md` | yes |
| 10 | Fixtures | `tests/consumer-example/**` | after 4–9 |
| 11 | Template | copyroom fixture + `template-py` (external repos) | after 9 |
| 12 | Dogfood & validation | `../image-gen-pipeline`, a copyroom-born repo | last |

Suggested PR slicing: **PR-A** = steps 1–3 (+ their tests) — additive, nothing breaks. **PR-B** = steps
4–8 — the semantic switch. **PR-C** = steps 9–11. **PR-D** = step 12 sign-off. PR-B is the only one that
requires a machine bootstrap to have happened first.

---

## Step 1 — machine `repoman.lock` at the repoman checkout root

**File:** `repoman.lock` (new; the repo currently has none — only `tests/consumer-example/repoman.lock` exists).

Seed it from the consumer-example lock **minus `[managers.test]`**:

```toml
# repoman.lock — the MACHINE toolchain manifest (project 12).
#
# Pins the pure-CLI managers that live in the single system-wide toolchain venv
# ($REPOMAN_TOOLCHAIN_VENV, default ~/.local/share/repoman/venv). `repoman-sync --machine`
# reads this file and installs EVERY entry (add-only `uv pip install`) — the consumer's
# `repoman.managers` roster gates wiring/skills, not installation.
#
# testee is deliberately ABSENT: it runs inside the consumer's code, so it is declared as a
# per-repo uv dev dependency in each consumer's pyproject.toml. See CONCEPT.md §3.
#
# source forms:
#   path:/abs/path                      local checkout (dev; installed --editable)
#   git+https://host/org/repo@vX.Y.Z    pinned git ref (fleet)
#   wheel:<requirement>                 prebuilt wheel from vendomat's wheelhouse (UV_FIND_LINKS)

[repoman]
package = "repoman"
source = "path:/home/andrew/Documents/Projects/repoman"

[managers.copy]
package = "copyroom"
source = "path:/home/andrew/Documents/Projects/copyroom"

[managers.git]
package = "gitman"
source = "path:/home/andrew/Documents/Projects/gitman"

# gitman's native dep — not a manager. Resolved by the "<manager>-*" pseudo-entry rule.
[managers.git-pyjutsu]
package = "pyjutsu"
source = "wheel:pyjutsu>=0.8"

[managers.doc]
package = "docman"
source = "path:/home/andrew/Documents/Projects/docman"
```

Notes:
- Absolute `path:` sources are the **dev** shape. The fleet shape swaps each to
  `git+https://github.com/Bullish-Design/<repo>@vX.Y.Z`; the resolver already passes those through
  verbatim (`test_git_https_source_passes_through_verbatim`). Do not try to make one file serve both —
  machine locks are per-machine by design, which is why D2 keeps it in the checkout.
- **Do not gitignore it.** It is the versioned convergence target.
- Sanity check: `python3 -c "import tomllib,sys;d=tomllib.load(open('repoman.lock','rb'));assert 'test' not in d['managers'];print(sorted(d['managers']))"`
  → `['copy', 'doc', 'git', 'git-pyjutsu']`.

---

## Step 2 — `modules/scripts/repoman-sync.sh`: two modes

Rewrite the script. The embedded TOML resolver, the `wheel:`/`UV_FIND_LINKS` guard and the
`SOURCE_HANDLERS` vocabulary are **reused verbatim** — the only resolver change is a select-all switch
for machine mode. Consumer mode loses the install entirely.

```bash
#!/usr/bin/env bash
# repoman-sync — one script, two modes (project 12).
#
#   repoman-sync --machine    Create/sync the SYSTEM-WIDE toolchain venv from the machine
#                             repoman.lock at the repoman checkout root. Installs EVERY entry
#                             in the lock (add-only `uv pip install`), then records the lock it
#                             synced from inside the venv. Run once per machine, and again on
#                             every toolchain bump.
#
#   repoman-sync              Consumer mode. Installs NO packages: the consumer venv belongs to
#                             `uv sync` alone. Verifies the shared toolchain is present, warns
#                             about orphan per-repo locks, then installs agent skills + devman docs.
set -euo pipefail

mode=consumer
case "${1:-}" in
  --machine)  mode=machine ;;
  -h|--help)  sed -n '2,15p' "$0"; exit 0 ;;
  "")         ;;
  *)          echo "repoman-sync: unknown argument: $1" >&2; exit 2 ;;
esac

# D1: resolved at runtime, never at nix eval.
toolchain_venv="${REPOMAN_TOOLCHAIN_VENV:-${XDG_DATA_HOME:-$HOME/.local/share}/repoman/venv}"
# D7: what the shared venv was last synced from — the consumer doctor reads this.
toolchain_manifest="$toolchain_venv/repoman-toolchain.toml"

bootstrap_hint() {
  echo "repoman-sync: bootstrap the shared toolchain once per machine:" >&2
  echo "    cd <your repoman checkout> && devenv shell -- repoman-sync --machine" >&2
}

# ---------------------------------------------------------------- consumer mode
if [ "$mode" = consumer ]; then
  root="${DEVENV_ROOT:-$PWD}"

  # D6: consumer mode's remaining job IS the shared `repoman` binary — fail, don't limp.
  if [ ! -x "$toolchain_venv/bin/repoman" ]; then
    echo "repoman-sync: shared toolchain venv missing or incomplete: $toolchain_venv" >&2
    bootstrap_hint
    exit 2
  fi
  echo "repoman-sync: shared toolchain → $toolchain_venv"

  # Migration aid (CONCEPT §9.7): per-repo locks are orphans now.
  if [ -f "$root/repoman.lock" ]; then
    echo "repoman-sync: warning: $root/repoman.lock is an ORPHAN manifest — the toolchain is" >&2
    echo "  machine-level now (see repoman CONCEPT.md §6). Delete it; declare testee in" >&2
    echo "  pyproject.toml under [dependency-groups] dev instead." >&2
  fi

  repoman install-skills
  echo "repoman-sync: done (skills + docs; toolchain is machine-level)."
  exit 0
fi

# ---------------------------------------------------------------- machine mode
root="${REPOMAN_ROOT:-${DEVENV_ROOT:-$PWD}}"
lock="$root/repoman.lock"

if [ ! -f "$lock" ]; then
  echo "repoman-sync --machine: no machine repoman.lock at $lock" >&2
  echo "repoman-sync --machine: run this from the repoman checkout, or set REPOMAN_ROOT." >&2
  exit 2
fi

# Resolve install targets from the lock (tomllib ships with Python 3.11+). Command substitution
# (not process substitution) so the resolver's exit code propagates: the wheel:/UV_FIND_LINKS
# guard below must abort the whole sync, which `< <(…)` would have swallowed.
resolved="$(
  REPOMAN_LOCK="$lock" REPOMAN_SYNC_ALL=1 python3 - <<'PY'
import os, sys, tomllib

with open(os.environ["REPOMAN_LOCK"], "rb") as fh:
    data = tomllib.load(fh)

managers = os.environ.get("REPOMAN_MANAGERS", "").split()
# Machine mode installs the whole lock: the shared venv holds every pure-CLI manager
# regardless of any single repo's roster (CONCEPT §5.1).
select_all = os.environ.get("REPOMAN_SYNC_ALL") == "1"

# Open source-kind vocabulary (DESIGN §4.1): prefix -> handler. A new kind ("bin:",
# "closure:") is one more entry here, not a new branch — vendomat's `wheel:` is the first.
SOURCE_HANDLERS = {
    "path:": lambda rest: f"--editable={rest}",
    "wheel:": lambda rest: rest,
}


def target(source: str) -> str:
    for prefix, handler in SOURCE_HANDLERS.items():
        if source.startswith(prefix):
            return handler(source[len(prefix):])
    return source  # git+https://...@ref — uv resolves the name itself


entries = []
if "repoman" in data:
    entries.append(data["repoman"])
selected = set(managers)
for key, entry in data.get("managers", {}).items():
    base = key.split("-", 1)[0]          # native-dep pseudo-entry: "git-pyjutsu" -> "git"
    if select_all or base in selected:
        entries.append(entry)

# Guard (issue #1): a wheel: source only resolves because vendomat's module exported
# UV_FIND_LINKS. No wheelhouse → uv silently hits PyPI (no personal pyjutsu there) and
# fails confusingly. Fail early with a pointer instead.
wheel_sources = [e["source"] for e in entries if e["source"].startswith("wheel:")]
if wheel_sources and not os.environ.get("UV_FIND_LINKS"):
    sys.stderr.write(
        "repoman-sync: wheel: source(s) selected but UV_FIND_LINKS is unset:\n"
        + "".join(f"    {s}\n" for s in wheel_sources)
        + "\nA wheel: source installs a prebuilt wheel from vendomat's wheelhouse.\n"
        "Bootstrap from a context that exports it — repoman's own devenv declares the\n"
        "vendomat input and sets `vendor.enable = true` (see repoman devenv.nix), or set\n"
        "`repoman.nativeBuild = true` and build pyjutsu from source.\n"
    )
    sys.exit(2)

print("\n".join(target(e["source"]) for e in entries))
PY
)" || exit $?

# Drop the lone empty line a zero-target resolution yields, so the count check below holds.
targets=()
while IFS= read -r line; do
  [ -n "$line" ] && targets+=("$line")
done <<< "$resolved"

if [ "${#targets[@]}" -eq 0 ]; then
  echo "repoman-sync --machine: nothing to install (empty lock: $lock)" >&2
  exit 2
fi

py="${REPOMAN_TOOLCHAIN_PYTHON:-3.13}"   # CONCEPT §4.1: gitman >=3.13, pyjutsu cp313-abi3
if [ ! -x "$toolchain_venv/bin/python" ]; then
  echo "repoman-sync --machine: creating shared toolchain venv (python $py) at $toolchain_venv"
  mkdir -p "$(dirname "$toolchain_venv")"
  uv venv --python "$py" "$toolchain_venv"
fi

echo "repoman-sync --machine: installing ${#targets[@]} package(s) into $toolchain_venv:"
printf '  - %s\n' "${targets[@]}"
# --python targets the shared venv explicitly: never inherit an ambient VIRTUAL_ENV
# (the bootstrap runs from inside repoman's OWN devenv venv).
uv pip install --python "$toolchain_venv/bin/python" "${targets[@]}"

# D7: record what this venv was synced from, so a consumer's `repoman doctor` can validate
# the toolchain without knowing where the repoman checkout lives.
{ printf '# synced from %s\n' "$lock"; cat "$lock"; } > "$toolchain_manifest"

echo "repoman-sync --machine: done → $toolchain_venv/bin"
```

**Behavioural deltas to keep in mind**
- Machine mode never runs `repoman install-skills` (there is no repo to install into).
- Consumer mode never reads `repoman.lock` and never calls `uv`.
- `REPOMAN_MANAGERS` is now irrelevant to installation in both modes; it survives only as wiring/roster
  state consumed by the `repoman` CLI (CONCEPT §5.1).

---

## Step 3 — bootstrap context (repoman's own devenv) — D3

**`devenv.yaml`** — add the vendomat input so the machine bootstrap can resolve `wheel:pyjutsu>=0.8`:

```yaml
inputs:
  nixpkgs:
    url: github:cachix/devenv-nixpkgs/rolling
  nixpkgs-python:
    url: github:cachix/nixpkgs-python
  nix2container:
    url: github:nlewo/nix2container
  mk-shell-bin:
    url: github:rrbutani/nix-mk-shell-bin
  # Machine-bootstrap only: vendomat's module exports UV_FIND_LINKS at the prebuilt pyjutsu
  # wheelhouse, which `repoman-sync --machine` needs to resolve the wheel: source in the
  # machine repoman.lock. Consumers no longer declare this input (project 12).
  vendomat:
    url: path:../vendomat        # fleet: github:Bullish-Design/vendomat

imports:
  - vendomat/modules
```

**`devenv.nix`** — enable the wheelhouse and add a machine-sync script (the repoman checkout is not a
repoman *consumer*, so it has no `repoman-sync` script of its own):

```nix
  vendor.enable = true;
  vendor.libs = [ "pyjutsu" ];

  scripts.repoman-sync = {
    description = "Sync the SYSTEM-WIDE repoman toolchain venv from this checkout's repoman.lock.";
    exec = ''REPOMAN_ROOT="''${DEVENV_ROOT:-$PWD}" exec ${pkgs.bash}/bin/bash ${./modules/scripts/repoman-sync.sh} "$@"'';
  };
```

Invoke as `devenv shell -- repoman-sync --machine`. Also extend the `enterShell` banner's "Quick start"
with a line 0: `0. Bootstrap the shared toolchain: repoman-sync --machine`.

**Escape hatch (no wheelhouse):** build pyjutsu once from source in pyjutsu's own repo
(`maturin build --release`), point `UV_FIND_LINKS` at the resulting `target/wheels/`, then run
`--machine`. `repoman.nativeBuild` remains for the consumer-side path and is untouched by this project.

**Check:** `devenv shell -- repoman-sync --machine` → `~/.local/share/repoman/venv/bin` contains
`repoman gitman copyroom docman`, and `~/.local/share/repoman/venv/repoman-toolchain.toml` exists.

---

## Step 4 — `modules/devenv.nix` (the meta-module) — D1

Three changes.

**4a. A single source of truth for the toolchain bin path**, exposed as an internal read-only option so
the manager modules don't each re-derive it:

```nix
let
  cfg = config.repoman;
  allManagers = [ "copy" "git" "test" "doc" ];

  # D1: a SHELL expression, expanded by bash at task/shell time — never a nix-eval-time
  # absolute path. `builtins.getEnv "HOME"` would bake one user's path into the eval result
  # and yield "/repoman/venv" wherever HOME is unset (CI, nix-daemon).
  toolchainVenvExpr = "\${REPOMAN_TOOLCHAIN_VENV:-\${XDG_DATA_HOME:-$HOME/.local/share}/repoman/venv}";
in
```

```nix
    toolchainBin = lib.mkOption {
      type = lib.types.str;
      internal = true;
      readOnly = true;
      default = "${toolchainVenvExpr}/bin";
      description = ''
        Shell expression (NOT a nix path) for the system-wide toolchain venv's bin dir.
        Manager modules interpolate it into task execs: "''${cfg.toolchainBin}"/gitman status.
        Honours $REPOMAN_TOOLCHAIN_VENV, else $XDG_DATA_HOME/repoman/venv, else
        ~/.local/share/repoman/venv. Populated by `repoman-sync --machine`.
      '';
    };
```

**4b. Export + PATH prepend in `enterShell`.** Prepend (not append) so a stale toolchain left in the
consumer venv by a pre-migration `repoman-sync` is shadowed rather than winning:

```nix
    enterShell = ''
      export REPOMAN_TOOLCHAIN_VENV="${toolchainVenvExpr}"
      export PATH="$REPOMAN_TOOLCHAIN_VENV/bin:$PATH"
      if [ ! -x "$REPOMAN_TOOLCHAIN_VENV/bin/repoman" ]; then
        echo "RepoMan: shared toolchain not bootstrapped ($REPOMAN_TOOLCHAIN_VENV)." >&2
        echo "RepoMan:   cd <repoman checkout> && devenv shell -- repoman-sync --machine" >&2
      fi
      if [ -t 1 ]; then
        echo "RepoMan: managers = ${lib.concatStringsSep " " cfg.managers}"
      fi
    '';
```

> The `export REPOMAN_TOOLCHAIN_VENV=…` line is written with nix `''`-string escaping: inside `''…''`,
> write `''${REPOMAN_TOOLCHAIN_VENV:-…}` to emit a literal `${…}` for bash. If you bind
> `toolchainVenvExpr` in the `let` (a normal `"…"` string with `\${`), interpolating `${toolchainVenvExpr}`
> inside the `''` block inserts it verbatim — that is the form used above. Verify with
> `nix eval --raw .#…` or simply by reading `.devenv/…` after a `devenv shell`.

**4c. `scripts.repoman-sync` description + docstring** — the exec line is unchanged (the script now
self-selects consumer mode), only the description and the header comment change:

```nix
    scripts.repoman-sync = {
      description = "Verify the shared toolchain venv, then install this repo's agent skills + devman docs.";
      exec = ''exec ${pkgs.bash}/bin/bash ${./scripts/repoman-sync.sh} "$@"'';
    };
```

Note the added `"$@"` — it lets a consumer run `repoman-sync --help` and keeps the machine path callable
from anywhere if `REPOMAN_ROOT` is set.

**4d. Comment surgery.** The module header and the `repoman.managers` option description both claim the
roster gates toolchain installation. Update to: *"selects which manager tasks/skills are wired; the
shared toolchain venv holds every pure-CLI manager regardless"* (CONCEPT §5.1).

---

## Step 5 — manager modules

**`modules/managers/gitman.nix`**

```diff
-  venvBin = "${config.devenv.state}/venv/bin";
 in
 ...
-        "repoman:vc:status".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/gitman status'';
+        # gitman lives in the SYSTEM-WIDE toolchain venv (project 12), resolved at runtime.
+        # Not a bare `gitman`: devenv tasks do not source enterShell, so PATH may not carry
+        # the shared bin dir.
+        "repoman:vc:status".exec = ''cd "$DEVENV_ROOT" && "${cfg.toolchainBin}"/gitman status'';
```

**`modules/managers/copyroom.nix`** — same shape:

```diff
-  venvBin = "${config.devenv.state}/venv/bin";
...
-      "repoman:template:status".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/copyroom status'';
+      "repoman:template:status".exec = ''cd "$DEVENV_ROOT" && "${cfg.toolchainBin}"/copyroom status'';
```

**`modules/managers/docman.nix`** — same, two tasks:

```diff
-  venvBin = "${config.devenv.state}/venv/bin";
...
-        "repoman:docs:doctor".exec = ''cd "$DEVENV_ROOT" && ${venvBin}/docman doctor'';
-        "repoman:docs:build".exec  = ''cd "$DEVENV_ROOT" && ${venvBin}/docman build'';
+        "repoman:docs:doctor".exec = ''cd "$DEVENV_ROOT" && "${cfg.toolchainBin}"/docman doctor'';
+        "repoman:docs:build".exec  = ''cd "$DEVENV_ROOT" && "${cfg.toolchainBin}"/docman build'';
```

`docman.nix` keeps its presence-gated import of docman's own nix module and the
`REPOMAN_PROVISIONED_DOC` signal — the docs *toolchain* (zensical, lychee, …) is still nix-provisioned
per repo. Only the CLI moved.

**`modules/managers/testee.nix` — DO NOT TOUCH.** `venvBin` there points at the consumer venv, which is
exactly where testee now lives. Its `enterTest` and both tasks stay as they are.

**Check:** `rg -n 'venvBin' modules/` → only `modules/managers/testee.nix`.

---

## Step 6 — `src/repoman/registry.py`: two new fields — D5

Add `install` and `package` to `Manager`, then mark `test` as uv-declared. This is what makes the doctor
generic instead of hardcoding "testee".

```diff
     key: str
     command: str
     tier: str
     summary: str
     doctor: list[str] | None = field(default_factory=lambda: ["doctor"])
     status: list[str] | None = None
     skill: str = ""
     route_when: str = ""
     nix_input: str = ""
+    install: str = "toolchain"  # "toolchain" = system-wide shared venv (machine repoman.lock);
+                                # "uv" = declared in the consumer's pyproject.toml, installed by uv sync
+    package: str = ""           # distribution name; defaults to `command`
 
     def __post_init__(self) -> None:
         if not self.skill:
             object.__setattr__(self, "skill", self.command)
+        if not self.package:
+            object.__setattr__(self, "package", self.command)
```

Docstring additions for both attributes, then:

```diff
     "test": Manager(
         "test",
         "testee",
         "core",
         "Verification (pytest / ruff / ty)",
         status=["list-runs"],
         route_when="verify code health, fix lint/format, or rerun failures",
+        # testee's TOOLS (pytest/ruff/ty) import the consumer's code, so testee is a per-repo
+        # uv dev dependency, not a shared-toolchain package. See CONCEPT.md §3 (project 12).
+        install="uv",
     ),
```

`copy` / `git` / `doc` keep the `"toolchain"` default. Add a guard so a typo can't silently disable a
check — validate in `__post_init__`:

```python
        if self.install not in {"toolchain", "uv"}:
            raise ValueError(f"{self.key}: unknown install model {self.install!r}")
```

---

## Step 7 — `src/repoman/checks.py`: the doctor

This is the largest Python change. Current shape: load `<repo>/repoman.lock` → `lock`, `lock:self`,
`lock:<key>` per manager. New shape:

| Check | When | Level | Detail |
|---|---|---|---|
| `toolchain:venv` | always | ok / **fail** | path, or "missing — run `repoman-sync --machine`" |
| `toolchain:lock` | venv present | ok / warn | `<venv>/repoman-toolchain.toml`, or "no manifest — re-run `repoman-sync --machine`" |
| `toolchain:self` | manifest parsed | ok / warn | replaces `lock:self` |
| `lock:<key>` | `install == "toolchain"` | ok / fail | as today, but resolved against the toolchain manifest |
| `uv:<key>` | `install == "uv"` | ok / fail | "declared in `[dependency-groups] dev`" / "not declared in pyproject.toml — add it" |
| `lock:orphan` | `<repo>/repoman.lock` exists | warn | "machine-level now — delete this file" |
| `installed:<key>` | always | ok / fail | **unchanged** |
| `provisioned:<key>` | `nix_input` set | ok / warn | **unchanged** |
| `skill:*` | always | — | **unchanged** |

Implementation sketch (drop-in replacements for `_load_lock` and the first half of `run_self_check`):

```python
import re

_DEFAULT_TOOLCHAIN = "repoman/venv"


def toolchain_venv() -> Path:
    """The system-wide toolchain venv (project 12), mirroring repoman-sync.sh's resolution."""

    env = os.environ.get("REPOMAN_TOOLCHAIN_VENV")
    if env:
        return Path(env)
    data_home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(data_home) / _DEFAULT_TOOLCHAIN


def _load_toolchain_manifest(venv: Path) -> tuple[dict | None, SelfCheck]:
    """Read the lock `repoman-sync --machine` recorded inside the shared venv (D7)."""

    path = venv / "repoman-toolchain.toml"
    if not path.exists():
        return None, SelfCheck(
            "toolchain:lock", "warn",
            f"no manifest at {path} — re-run `repoman-sync --machine` to record one",
        )
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh), SelfCheck("toolchain:lock", "ok", str(path))
    except tomllib.TOMLDecodeError as exc:
        return None, SelfCheck("toolchain:lock", "warn", f"unparseable: {exc}")


def _requirement_name(req: str) -> str:
    """'testee>=0.3 ; python_version>"3.12"' -> 'testee' (PEP 508 head, normalized)."""

    head = re.split(r"[\s\[<>=!~;@()]", req.strip(), maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", head).lower()


def uv_declared_in(pyproject: dict, package: str) -> str | None:
    """Which pyproject table declares ``package``, or None. Generic over any uv manager (D5)."""

    target = re.sub(r"[-_.]+", "-", package).lower()
    project = pyproject.get("project") or {}
    tables: list[tuple[str, list]] = [("[project.dependencies]", project.get("dependencies") or [])]
    for extra, reqs in (project.get("optional-dependencies") or {}).items():
        tables.append((f"[project.optional-dependencies] {extra}", reqs or []))
    for group, reqs in (pyproject.get("dependency-groups") or {}).items():
        tables.append((f"[dependency-groups] {group}", reqs or []))
    for label, reqs in tables:
        # dependency-groups entries may be {include-group = "..."} dicts — skip non-strings.
        if any(isinstance(r, str) and _requirement_name(r) == target for r in reqs):
            return label
    return None


def _load_pyproject(repo_root: str) -> dict | None:
    path = Path(repo_root) / "pyproject.toml"
    if not path.exists():
        return None
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError:
        return None
```

…and in `run_self_check`, replacing the `_load_lock` block:

```python
    venv = toolchain_venv()
    have_venv = (venv / "bin" / "repoman").exists()
    out.append(SelfCheck(
        "toolchain:venv", "ok" if have_venv else "fail",
        str(venv) if have_venv
        else f"missing or incomplete: {venv} — run `repoman-sync --machine` from the repoman checkout",
    ))

    data = None
    if have_venv:
        data, manifest_check = _load_toolchain_manifest(venv)
        out.append(manifest_check)
        if data is not None and "repoman" not in data:
            out.append(SelfCheck("toolchain:self", "warn", "no [repoman] self entry"))

    pyproject = _load_pyproject(repo_root)
    lock_keys = set((data or {}).get("managers", {}))

    for m in managers:
        if m.install == "uv":
            where = uv_declared_in(pyproject, m.package) if pyproject else None
            out.append(SelfCheck(
                f"uv:{m.key}", "ok" if where else "fail",
                f"uv-declared — {where}" if where
                else f"{m.package} not declared in pyproject.toml — add it to "
                     f'[dependency-groups] dev (+ [tool.uv.sources]) and run `uv sync`',
            ))
            continue
        if data is None:
            continue  # no manifest to check against; toolchain:venv/lock already reported
        # tolerate native-dep pseudo-entries like "git-pyjutsu" (guide 1)
        has = m.key in lock_keys or any(k.split("-", 1)[0] == m.key for k in lock_keys)
        out.append(SelfCheck(
            f"lock:{m.key}", "ok" if has else "fail",
            "" if has else "selected but absent from the machine repoman.lock",
        ))

    if (Path(repo_root) / "repoman.lock").exists():
        out.append(SelfCheck(
            "lock:orphan", "warn",
            "per-repo repoman.lock is obsolete — the toolchain is machine-level; delete this file",
        ))
```

The rest of `run_self_check` (`installed:`, `provisioned:`, `skill:`) is untouched. `self_check_exit` /
`format_self_check` are untouched.

**Two design points worth defending in review:**
1. `toolchain:venv` is **fail**, not warn: with no shared venv, every `installed:<key>` for a toolchain
   manager fails anyway; making the root cause fail once, loudly, with the fix in the detail line is the
   whole point of a preflight.
2. `uv:<key>` checks *declaration*, not installation — `installed:<key>` already covers presence.
   Declaration-vs-presence is the distinction that catches "someone `uv pip install`ed testee by hand
   and the next `uv sync` will prune it".

---

## Step 8 — tests

### 8a. `tests/test_repoman_sync.py` (largest test delta)

Refactor `_run` to take a `mode` and to stub `uv` as a **recorder** so machine mode can be asserted:

```python
def _stub_bin(tmp_path, *, uv_log=None, with_repoman=True, toolchain_venv=None):
    """PATH stubs. `uv` records argv to uv_log; `uv venv` also materialises a fake venv."""
```

Keep every existing resolver test (they exercise the embedded python, now via `--machine`). Add:

| Test | Asserts |
|---|---|
| `test_machine_installs_every_manager_ignoring_roster` | `REPOMAN_MANAGERS=""` still yields copy/git/doc targets (select-all) |
| `test_machine_creates_venv_when_absent` | `uv venv --python 3.13 <venv>` recorded once |
| `test_machine_skips_venv_creation_when_present` | no `uv venv` when `bin/python` exists |
| `test_machine_installs_into_shared_venv` | `uv pip install --python <venv>/bin/python …` — never a bare `uv pip install` |
| `test_machine_records_toolchain_manifest` | `<venv>/repoman-toolchain.toml` exists, starts with `# synced from`, round-trips through `tomllib` |
| `test_machine_wheel_guard_still_aborts` | exit 2 + `UV_FIND_LINKS is unset` (regression on the reused guard) |
| `test_machine_missing_lock_exits_2` | message names `REPOMAN_ROOT` |
| `test_machine_respects_REPOMAN_ROOT` | lock resolved from `$REPOMAN_ROOT`, not `$PWD` |
| `test_consumer_installs_nothing` | uv log file is empty/absent; `repoman install-skills` stub was called |
| `test_consumer_fails_without_shared_venv` | exit 2 + bootstrap one-liner in stderr (D6) |
| `test_consumer_warns_on_orphan_lock` | `repoman.lock` in `$DEVENV_ROOT` → "ORPHAN" on stderr, exit 0 |
| `test_unknown_argument_exits_2` | `repoman-sync --wat` |

### 8b. `tests/test_checks.py`

Add a fixture that builds a fake shared venv (so most tests don't have to):

```python
@pytest.fixture
def toolchain(tmp_path, monkeypatch):
    """A fake bootstrapped shared toolchain venv, wired via REPOMAN_TOOLCHAIN_VENV."""
    venv = tmp_path / "toolchain"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "repoman").write_text("")
    monkeypatch.setenv("REPOMAN_TOOLCHAIN_VENV", str(venv))
    def write(manifest: str) -> Path:
        (venv / "repoman-toolchain.toml").write_text(manifest)
        return venv
    write(_GOOD_LOCK)
    return SimpleNamespace(venv=venv, write=write)
```

Rewrites (the old ones asserted a per-repo lock and now assert the wrong architecture):
- `test_missing_lock_fails` → `test_missing_toolchain_venv_fails` (`toolchain:venv` fail, exit 2, detail
  mentions `repoman-sync --machine`).
- `test_selected_manager_absent_from_lock_fails` → keyed on `git`/`doc` (toolchain managers), reading
  the fixture manifest.
- `test_unparseable_lock_fails` → `toolchain:lock` **warn** (not fail — a broken recorded manifest must
  not mask `installed:*`, which is the real signal).
- `test_missing_self_entry_warns` → name becomes `toolchain:self`.
- `test_native_pseudo_entry_satisfies_base_manager` / `test_pseudo_entry_must_match_base_manager_exactly`
  → unchanged logic, manifest moved into the fixture.
- `test_healthy_wiring_is_all_ok`, `test_full_roster_self_check_is_green` → add a `pyproject.toml` with
  `[dependency-groups] dev = ["testee"]` so `uv:test` is ok; assert
  `{n for n in names if n.startswith("lock:")} == {"lock:copy", "lock:git", "lock:doc"}` and `uv:test` ok.

New:
- `test_uv_declared_manager_is_ok_from_dependency_groups`
- `test_uv_declared_manager_is_ok_from_optional_dependencies` (extras style still recognized)
- `test_uv_declared_manager_is_ok_from_project_dependencies`
- `test_uv_manager_not_declared_fails` — detail names `pyproject.toml` and `[dependency-groups]`
- `test_uv_manager_requirement_specifier_and_extras_are_stripped` — `"testee[all]>=0.3 ; python_version>'3.12'"` matches
- `test_uv_manager_name_normalisation` — `Testee` / `test_ee`-style normalization (PEP 503)
- `test_include_group_entries_are_skipped` — `dev = [{include-group = "lint"}]` doesn't crash
- `test_no_pyproject_fails_uv_check_cleanly` — no `pyproject.toml` → `uv:test` fail, no exception
- `test_uv_manager_gets_no_lock_row` — `"lock:test" not in names` (the regression CONCEPT §5.3 warns about)
- `test_orphan_repo_lock_warns` — non-fatal, exit stays 0
- `test_toolchain_venv_from_xdg_data_home` / `..._from_home_fallback` — `toolchain_venv()` resolution

### 8c. `tests/test_cli.py`

The `_repo` fixture (line ~34) builds a per-repo `repoman.lock`. Rewrite it to build a fake toolchain
venv + manifest + a `pyproject.toml` declaring testee, and to set `REPOMAN_TOOLCHAIN_VENV`. The doctor
exit-code tests then hold unchanged. Update the "absent from lock → exit 2" test (line ~138) to the new
failure it should assert: **`uv:test` fail** when `pyproject.toml` omits testee.

### 8d. `tests/test_registry.py`

- every manager's `install` is `"toolchain"` except `test` → `"uv"`
- `package` defaults to `command` for all four
- `Manager(..., install="bogus")` raises `ValueError`

### 8e. `tests/test_modules_nix.py` (new — cheap grep-level guards on the nix layer)

```python
MODULES = Path(__file__).resolve().parents[1] / "modules"

def test_only_testee_uses_the_consumer_venv():
    users = {p.name for p in (MODULES / "managers").glob("*.nix") if "venvBin" in p.read_text()}
    assert users == {"testee.nix"}

def test_shared_managers_resolve_through_the_toolchain_bin():
    for name in ("gitman.nix", "copyroom.nix", "docman.nix"):
        assert "cfg.toolchainBin" in (MODULES / "managers" / name).read_text()

def test_meta_module_does_not_eval_getenv():
    # D1: no builtins.getEnv anywhere — the path is resolved by bash at runtime.
    assert "builtins.getEnv" not in (MODULES / "devenv.nix").read_text()
```

Full run: `devenv shell -- pytest -q`. Every test above is hermetic (no real venv, no network).

---

## Step 9 — docs & skills

These are shipped assets (`repoman install-skills` writes them into every consumer), so wording here
propagates fleet-wide. The project-11 doc surgery is reverted: `uv sync` is safe again.

| File | Line(s) | Change |
|---|---|---|
| `src/repoman/devman/assets/docs/languages-python.md` | 17–18 | keep `devenv shell -- uv sync --all-extras`; add: it installs app deps **and** the `dev` group (which brings testee + pytest/ruff/ty); note `uv pip install -e .` installs **neither** groups nor extras, so it is not the recommended install |
| `src/repoman/devman/assets/skills/devenv-python-venv/SKILL.md` | 16–17 | `uv sync --all-extras` stays the fix; `repoman-sync` line → "installs agent skills + devman docs (the manager toolchain is machine-wide, not per-repo)" |
| `src/repoman/devman/assets/skills/devenv-troubleshoot/SKILL.md` | 13 | split the row: app/test imports → `uv sync`; `gitman/copyroom/docman: command not found` → `repoman-sync --machine` |
| `src/repoman/devman/assets/articles/command-not-found-in-shell.md` | 25 | add the shared-toolchain symptom + one-liner; keep the `uv sync` line |
| `src/repoman/devman/assets/articles/adopting-the-man-family.md` | 25–27 | step 3 becomes "bootstrap the machine toolchain once (`repoman-sync --machine` in the repoman checkout)"; new step: "declare `testee` in `[dependency-groups] dev` + `[tool.uv.sources]`"; step 4 `repoman-sync` = skills/docs only |
| `src/repoman/devman/assets/articles/authoring-a-manager-module.md` | 29–30, 49 | document the **two install classes** (shared toolchain via machine `repoman.lock` vs uv-declared via consumer `pyproject.toml`) and that `Manager.install` selects the doctor check |
| `src/repoman/devman/assets/articles/ci-inside-devenv.md` | 11 | CI needs `repoman-sync --machine` (cacheable) before `repoman-sync`; then `uv sync --all-extras` |
| `src/repoman/devman/assets/docs/lock-and-cache.md` | 30 | clarify which lock (`repoman.lock` = machine; `uv.lock` = repo) |
| `docs/SKILLS.md` | 37, 90 | `repoman-sync` no longer installs the toolchain — only skills/docs |
| `CONCEPT.md` (root), `SPIKE.md` | — | add a "superseded by project 12" note wherever they describe per-repo toolchain installation |

Bump whatever `repoman` version the devman MANIFEST records so `devman:current` flags stale consumer
installs (`test_devman_stale_manifest_warns` covers the mechanism).

---

## Step 10 — `tests/consumer-example/` fixtures

The fixture repo is the in-repo proof of the consumer shape. It must show the *new* shape:

1. **Delete** `tests/consumer-example/repoman.lock` (`git rm`).
2. **`devenv.yaml`** — drop the `vendomat` input and the `vendomat/modules` import (with its comment
   block). Keep `repoman`, `nixpkgs`, `nixpkgs-python`, `docman`, `shellij`.
3. **`devenv.nix`** — drop `vendor.enable` / `vendor.libs`; keep `repoman.enable`,
   `repoman.managers = [ "copy" "git" "test" "doc" ]`, `repoman.nativeBuild = false`, and the python
   block. Rewrite the header comment: the venv now hosts *the app and testee*, not the manager CLIs.
4. **New `tests/consumer-example/pyproject.toml`** — the canonical consumer declaration:

```toml
[project]
name = "consumer-example"
version = "0.0.0"
requires-python = ">=3.13"
dependencies = []

[dependency-groups]
dev = ["testee"]

[tool.uv.sources]
# fleet: testee = { git = "https://github.com/Bullish-Design/testee", ref = "vX.Y.Z" }
testee = { path = "../../../testee" }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

5. **Regenerate the installed assets** — from the fixture dir, with the shared toolchain on PATH:
   `REPOMAN_MANAGERS="copy git test doc" repoman install-skills` — refreshes
   `.claude/skills/repoman/SKILL.md`, the devman skills, `.agents/devenv/**` and `.devman-source`.
6. Leave `.devenv/` state out of the commit (already the case).

---

## Step 11 — template (external repos)

Both are outside this checkout; do them as sibling PRs after step 9 lands.

- **copyroom** — `demo/fixtures/minimal-python-package/template/pyproject.toml.jinja`: render
  `[dependency-groups] dev = ["testee"]` + `[tool.uv.sources] testee = { git = "…", ref = "…" }`
  (D4). Update the fixture's expected-output assertions.
- **template-py** (fleet genome) — the same `pyproject.toml.jinja` change, plus any README/docs line
  that says `uv sync` is unsafe or that a new repo needs a `repoman.lock`. A copyroom-born repo must
  pass validation steps 2–4 below with **zero** manual edits (that is validation item 6).

---

## Step 12 — migration, dogfood, validation

### 12a. Per-machine, once

```bash
cd ~/Documents/Projects/repoman
devenv shell -- repoman-sync --machine
ls ~/.local/share/repoman/venv/bin        # repoman gitman copyroom docman
```

### 12b. Per consumer (e.g. `../image-gen-pipeline`)

```bash
# 1. declare testee (D4)
#    pyproject.toml:  [dependency-groups] dev = ["testee"]
#                     [tool.uv.sources]  testee = { git = "…", ref = "vX.Y.Z" }
# 2. drop the vendomat input from devenv.yaml and `vendor.enable` from devenv.nix
# 3. retire the orphan manifest
git rm repoman.lock
# 4. let uv prune the old per-repo toolchain — the ex-footgun is now the migration step
devenv shell -- uv sync --all-extras
devenv shell -- repoman-sync          # skills/docs only
devenv shell -- repoman doctor
```

Expected doctor shape after migration:

```
OK   toolchain:venv — /home/…/.local/share/repoman/venv
OK   toolchain:lock — /home/…/.local/share/repoman/venv/repoman-toolchain.toml
OK   lock:copy
OK   lock:git
OK   uv:test — uv-declared — [dependency-groups] dev
OK   lock:doc
OK   installed:copy … installed:test …
OK   provisioned:doc
OK   skill:entrypoint …
```

### 12c. Validation checklist (CONCEPT §9, made executable)

| # | Command(s) | Pass criterion |
|---|---|---|
| 1 | `repoman-sync --machine`; `devenv shell -- gitman status` | shared venv has repoman/gitman/copyroom/docman/pyjutsu; gitman runs from a consumer |
| 2 | `devenv shell -- uv sync --all-extras`; `testee verify --mode quick`; `gitman status`; `repoman doctor` | all green **including `uv:test`**; testee + pytest/ruff/ty in `.devenv/state/venv` |
| 3 | **acceptance test** — `devenv shell -- uv sync --all-extras --dry-run` (second run) | **zero uninstalls** (was 33; project-11 repro) |
| 4 | after each of `uv sync`, `uv sync --all-extras`, `uv pip install --all-extras -e .` | `gitman status`, `testee verify --mode quick`, `repoman status` all still work |
| 5 | `uv lock --upgrade-package testee` → only testee moves; bump a machine pin + `repoman-sync --machine` → only the shared venv moves | two independent upgrade clocks, both end green |
| 6 | `copyroom new` from the updated template | fresh repo passes rows 2–4 with no manual edits |
| 7 | `find . -name repoman.lock` in any consumer → none; `rg -n '\[managers\.test\]' repoman.lock` → none; `rg -n 'uv sync' src/ modules/` → only safe recommendations | no orphan manifests |
| 8 | `devenv tasks run repoman:vc:status` **without** entering the shell first | proves D1: task exec resolves the toolchain without `enterShell` |

Row 8 is the one genuinely new risk this refactor introduces — run it explicitly.

### 12d. Rollback

Steps 1–3 are additive (a shared venv nobody reads yet). The switch is PR-B (steps 4–8): reverting it
restores `${venvBin}/…` execs and the per-repo lock checks, and a consumer recovers with
`devenv shell -- repoman-sync` under the old script. Keep the shared venv around during the transition —
it is inert to a rolled-back consumer, since nothing prepends it to PATH.

---

## 13. Known sharp edges

1. **PATH ordering vs. a stale consumer venv.** Until a consumer runs `uv sync`, its venv may still hold
   an editable `repoman`/`gitman`. The `enterShell` prepend shadows them, but a *task* uses the
   toolchain path explicitly, so both layers agree. `uv sync` cleans it up permanently.
2. **`uv pip install --python` vs. `VIRTUAL_ENV`.** Machine bootstrap runs from inside repoman's own
   devenv venv; without `--python`, uv would install the toolchain into *that* venv. The explicit flag
   is load-bearing — `test_machine_installs_into_shared_venv` guards it.
3. **`uv venv --python 3.13`** requires a 3.13 uv knows about. If `UV_PYTHON_DOWNLOADS=never` is set in
   the environment, bootstrap fails; document `REPOMAN_TOOLCHAIN_PYTHON` as the override and prefer
   devenv's python when it already satisfies the floor.
4. **Editable `path:` sources in the shared venv** mean an edit in `~/Documents/Projects/gitman` is live
   for every repo on the machine at once. That is the intended dev-loop property, and exactly the thing
   that makes the fleet-ref (`git+https@ref`) form mandatory for non-dev machines.
5. **Two consumers, one toolchain, different expectations.** A repo pinned to an older workflow cannot
   pin an older gitman anymore (CONCEPT §10). If that bites, the escape hatch is a per-repo
   `REPOMAN_TOOLCHAIN_VENV` in `devenv.nix` env — a second shared venv, not a per-repo install.
6. **`repoman doctor` inside the repoman checkout itself** now reports `toolchain:venv` against the
   shared venv while the checkout is also the *source* of that venv. That is correct but reads oddly;
   the `# synced from <path>` header in the recorded manifest is what disambiguates.
