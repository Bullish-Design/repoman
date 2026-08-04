# Changelog

## 0.5.0 — hardening pass

The theme: the diagnostic layer used to trust its environment more than the thing it
was diagnosing. It parsed without guarding, resolved binaries via `PATH` while
executing absolute paths, checked presence instead of currency, and computed
information it never printed.

### Fixed — correctness

- **`repoman doctor` no longer crashes on the inputs it exists to diagnose.** Only
  `TOMLDecodeError` was caught, so an unreadable/directory `pyproject.toml`, a
  permission-denied toolchain manifest, or a non-UTF-8 `SKILL.md` escaped as a
  traceback. All filesystem reads are guarded and reported as findings.
- **A crashed conductor exits `2` (infra/config), not `1`.** Under the shared
  contract `1` means "a domain decision is needed"; an unhandled traceback used to
  masquerade as one. `main()` now maps unexpected exceptions to `2` and
  `KeyboardInterrupt` to `130`.
- **`installed:<key>` validates the binary the nix tasks actually exec** — the
  absolute path under the toolchain (or consumer) venv — instead of trusting a `PATH`
  hit. When `PATH` resolves a *different* copy, that shadowing is reported.
- **PATH order in `modules/devenv.nix` corrected.** The consumer venv was prepended
  *after* the toolchain, so it won — exactly defeating the comment above it. A stale
  pre-migration manager CLI in `.devenv/state/venv/bin` could shadow the shared
  toolchain, leaving `doctor` green while `devenv tasks run` used another binary.
- **`repoman-sync` (consumer mode) runs the `repoman` it verified.** It gated on
  `-x "$toolchain_venv/bin/repoman"` and then invoked bare `repoman`.
- **Stale toolchains are now detected.** New `version:<entry>` rows compare what is
  installed in the shared venv against what the lock pins. `lock:<key>` only ever
  proved a key was *present* in the manifest.
- **`repoman-sync --machine` passes `--upgrade`.** Without it a range pin such as
  `wheel:pyjutsu>=0.8` counts as already satisfied, so re-syncing after a toolchain
  bump silently installed nothing.
- **`repoman.managers = [ ]` means "wire nothing".** An empty `REPOMAN_MANAGERS`
  fell through to the three core defaults.
- **A malformed `repoman.lock` produces a message, not a traceback** (missing
  `source`, non-table entry, invalid TOML, empty source) — and exits `2`.
- **The resolver→bash protocol is NUL-delimited.** A newline inside a lock `source`
  could inject an extra argument into `uv pip install` — relevant now that
  `REPOMAN_LOCK` invites machine-generated fleet locks.
- **Duplicate roster entries are collapsed**, so `REPOMAN_MANAGERS="git git"` no
  longer runs gitman's doctor twice or duplicates routing rows.
- **`REPOMAN_SKILLS_DIR` must be repo-relative.** An absolute value made
  `install-skills` write outside the repo entirely; `..` traversal is rejected too.

### Fixed — reporting

- **An unavailable manager explains itself.** `repoman status` printed a bare header
  and exited `2` in silence; `SubResult.available` was computed and never rendered.
  Results now carry a `reason` the CLI prints.
- **Sub-managers have a timeout** (`REPOMAN_SUB_TIMEOUT`, default 900s, `0` to
  disable) so a hung manager can't hang the conductor forever.
- The generated routing table follows the lifecycle spine rather than the order the
  roster happened to be written in.

### Added

- `repoman --version`.
- `README.md`, `LICENSE`, this changelog; `readme`/`license`/`authors` in
  `pyproject.toml`.
- `tests/conftest.py` isolates every test from an ambient devenv shell — previously a
  test could read, and one did *execute*, the real machine toolchain.

### Changed

- `install-skills` writes atomically (temp file + `os.replace`); a partial write left
  a truncated `SKILL.md` that the next `doctor` reported as healthy.
- `repoman-sync --machine` writes its manifest atomically, rejects trailing
  arguments, checks that `uv` is on `PATH`, and `--help` no longer spills into the
  script body.
- Dead code removed: the resolver's unreachable `REPOMAN_MANAGERS` selection branch
  (machine mode always installs the whole lock).

## 0.4.0 and earlier

See `.scratch/projects/` for the project-by-project history.
