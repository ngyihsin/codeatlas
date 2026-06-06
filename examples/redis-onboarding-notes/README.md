# Worked Reference Instance — Redis Onboarding Notes

This directory is a **filled, end-to-end example** of what the `docforge-onboard`
template produces at the **L3 ("professional")** level. It documents a real
codebase — [Redis](https://github.com/redis/redis) — so a new hire can see the bar,
not just the blank templates.

> **Read this caveat first.** These notes were authored from knowledge of Redis, not
> from a live checkout in this session. Every code claim is therefore tagged `◐`
> (read-only) at best, and every anchor uses `file → symbol (search "…")` rather than
> a line number — line numbers drift and were never measured here. Redis also changes
> across major versions; version-sensitive details are flagged inline. **Before
> acting on anything here, re-verify against your own checkout** and set the real
> commit hash in each `Last verified against commit:` field. This is exactly the
> honesty discipline `STANDARD.md` requires; the instance models it on purpose.

## What's here

| File | Role | Demonstrates |
|---|---|---|
| `CLAUDE.md` | Auto-loaded lean index | The ≤200-line per-session boot context |
| `INDEX.md` | Entry point for consuming skills | Machine-readable map, invariants registry, task recipes |
| `OVERVIEW.md` | What Redis is + structural map | L3 reference doc |
| `CONCEPTS.md` | The `dict` and incremental rehashing | L3 **data-structure** entry: fields, *why*, API usage |
| `FLOWS.md` | "Life of a `GET`" | L3 **flow**: end-to-end trace + diagram + error branch |
| `HOW-TO.md` | Build / run / test / change Redis | L3 **how-to**: copy-pasteable, with error strings |

## How to read it

Start at `INDEX.md` if you are a skill here to do a task; start at `OVERVIEW.md` if
you are a human learning Redis. Notice that every doc opens with the standard header
(type, audience, prerequisites, owner, verified commit), every code claim has a
stable anchor and a status tag, and the hardest concept (incremental rehashing) gets
a data-structure table, a *why-this-shape* section, a worked API call, and an
invariant a consuming skill must not break.
