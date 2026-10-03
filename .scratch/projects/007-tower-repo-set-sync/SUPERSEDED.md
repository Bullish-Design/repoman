# 07 — tower repo-set sync — SUPERSEDED / RETIRED

**Status: CANCELLED on 2026-07-01. Do not build.**

## What this project was

A plan to extend **repoman** with a v2 "fleet feature": a `repos.toml`-driven
`repoman fleet-sync` command (plus a `src/repoman/fleet/` subpackage and a
`modules/managers/fleet.nix` wiring module) that would idempotently clone/fetch the
declared `~/Documents/Projects` repo set on both machines. It was explicitly framed
as a reversal of repoman's own `CONCEPT.md §2` ("fleet/workspace management is
explicitly out of scope").

## Why it was cancelled

Fleet-wide clone/fetch/flake-update is a **fleet** operation, not a per-repo one, and
it directly overlapped **fleetman**'s `002-fleet-write-ops` `sync` engine (same
`repos.toml`, same clone/fetch semantics). Building both would have produced two
competing clone engines and two divergent drift reports.

The overlap was resolved by descoping fleet-sync from repoman entirely:

- **fleetman is the sole owner** of all fleet-wide sync/write operations
  (clone / fetch / flake-update). It already owns the workspace domain and the
  derived dependency DAG that a topo-ordered publish needs.
- **repoman remains per-repo by design** (`CONCEPT.md §2`). Its lane is composing
  gitman/testee/… *inside* a single repo, not materializing the repo set across the
  fleet.

## Where this capability lives now

**fleetman** — see `fleetman/.scratch/projects/002-fleet-write-ops/`.
