# Worked Reference Instance — Redis Onboarding Notes

This directory is a **filled, end-to-end example** of what the `docforge-onboard`
template produces at the **L3 ("professional")** level. It documents a real
codebase — [Redis](https://github.com/redis/redis) — so a new hire can see the bar,
not just the blank templates.

> **Read this caveat first.** Verified against `redis/redis` @`4625b89` (the `unstable`
> dev branch) on 2026-06-06. Two levels of verification: **anchors** — every cited file
> and symbol confirmed present; and **behavior** — Redis was actually **built and run**,
> confirming the HOW-TO build/run and the "Life of a GET" flow (happy path, the exact
> `WRONGTYPE` error, and `nil` for a missing key) → those are now `✓`. Claims still read,
> not run (call-chain steps, the shared-object invariant — which in fact *drifted* on the
> 8.x `kvobj` line) stay `◐`.
> Anchors use `file → symbol (search "…")`, never line numbers. Because `unstable` is
> dev, a stable release may differ; the most notable drift is flagged inline (e.g.
> keyspace lookups now return `kvobj*`, and `redisObject` lives in `src/object.h`).
> Re-verify against *your* checkout's commit before acting. This is the honesty
> discipline `STANDARD.md` requires; the instance models it on purpose.

## What's here

| File | Role | Demonstrates |
|---|---|---|
| `CLAUDE.md` | Auto-loaded lean index | The ≤200-line per-session boot context |
| `INDEX.md` | Entry point for consuming skills | Machine-readable map, invariants registry, task recipes |
| `OVERVIEW.md` | What Redis is + structural map | L3 reference doc |
| `CONCEPTS.md` | The `dict` and incremental rehashing | L3 **data-structure** entry: fields, *why*, API usage |
| `FLOWS.md` | "Life of a `GET`" | L3 **flow**: end-to-end trace + diagram + error branch |
| `HOW-TO.md` | Build / run / test / change Redis | L3 **how-to**: copy-pasteable, with error strings |
| `API.md` | Provided commands + consumed libs + feature→API | L3 **API/interface** surface and entry points |

## How to read it

Start at `INDEX.md` if you are a skill here to do a task; start at `OVERVIEW.md` if
you are a human learning Redis. Notice that every doc opens with the standard header
(type, audience, prerequisites, owner, verified commit), every code claim has a
stable anchor and a status tag, and the hardest concept (incremental rehashing) gets
a data-structure table, a *why-this-shape* section, a worked API call, and an
invariant a consuming skill must not break.
