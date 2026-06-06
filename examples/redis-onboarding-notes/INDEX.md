# Knowledge Base Index — Redis (Entry Point for Consuming Skills)

**Doc type:** reference (machine-readable routing + action contract)
**Audience:** an agent or skill here to do a task on Redis; humans wanting the map
**Before you begin:** none
**Owner:** _(example instance — unowned)_
**Last verified against commit:** 4625b89 (redis unstable)   **Status:** ◐ Read-only
**Index schema:** v1 — column meanings stable within a major version

> Illustrative reference instance. Anchors **verified against `redis` @`4625b89`**
> (2026-06-06); rows stay `◐` because behavior was read, not run. Re-verify before
> acting. To *build* these notes you would read `AGENT-warm-up.md`; this is the
> *consume* entry point.

## Consumption Protocol (read before acting)

1. **Route by task** — jump to the matching recipe below.
2. **Trust gates:** act on `✓`; re-verify `◐` against current code before editing;
   **never act on `?`.** Here, treat all rows as `◐`.
3. **Re-verify before editing:** `git log <Last verified commit>..HEAD -- <path>`.
   Code wins over docs.
4. **Honor invariants** in the registry below — a violation is a bug even if tests
   pass.
5. **Write back** any correction, with updated provenance.

## Knowledge Map

### Concepts

| Concept | Anchor | Status | What breaks without it | Use when |
|---|---|---|---|---|
| `dict` + incremental rehashing | `src/dict.c` → `dict` (search `"struct dict"`) | ◐ | You assume one bucket array and lose keys during a resize | Touching the keyspace, a data type, or expiration |
| `redisObject` (`robj`) | `src/object.h` → `redisObject` | ◐ | You mutate a shared/immutable value object | Reading or creating any stored value |
| Single-threaded execution | `src/server.c` → `call` | ◐ | You add needless locks, or assume concurrency that isn't there | Any command-path change |

→ Detail: `CONCEPTS.md`

### Flows

| Flow | Trigger | Error / early-exit branch | Status | Use when |
|---|---|---|---|---|
| Life of a `GET` | client `GET key` | `src/object.c` → `checkType` (WRONGTYPE) | ◐ | A bug in read commands or reply encoding |

→ Detail: `FLOWS.md`

### Key Data Structures

| Structure | Anchor | Invariants documented in |
|---|---|---|
| `dict` | `src/dict.h` → `dict` | `CONCEPTS.md` → `dict` |
| `redisObject` | `src/object.h` → `redisObject` | `CONCEPTS.md` → `redisObject` |

### APIs, Entry Points & Interfaces

The provided API surface (RESP commands, the module API), the consumed interfaces
(jemalloc, the event-loop poller, Lua, …), and the feature→API map are authored in
**`API.md`** — the single source of truth. Process/binary start points are in
`OVERVIEW.md` → Entry Points.

### Task → Location Map

| To change… | Look in | Owner |
|---|---|---|
| How a command is dispatched | `src/server.c` → `processCommand`, `call` | — |
| A specific command's behavior | `src/t_<type>.c` (e.g. `t_string.c`) | — |
| Keyspace read/write/expiry | `src/db.c` | — |
| Hash-table behavior | `src/dict.c` / `src/dict.h` | — |
| Protocol parsing / replies | `src/networking.c` | — |

### Invariants / Must-Not-Break Registry

| Invariant (what must stay true) | Enforced / relied on at | Explained in | Status |
|---|---|---|---|
| During a `dict` rehash, entries are in both tables; ops check both, inserts go to `ht[1]` | `src/dict.c` → `dictFind`, `dictAdd` | `CONCEPTS.md` → `dict` | ◐ |
| Command logic runs single-threaded; no locks needed for keyspace access | `src/server.c` → `call` | `CLAUDE.md`, `OVERVIEW.md` | ◐ |
| Shared/immutable objects (e.g. small ints) must never be mutated or freed — **but on the 8.x `kvobj` line keyspace values are not the shared object** (verified: `OBJECT REFCOUNT` of a small int = 1) | `src/object.c`, `src/server.c` → `shared` | `CONCEPTS.md` → `redisObject` | ◐ |
| A read must call `expireIfNeeded`; an "expired" key may still be present | `src/db.c` → `lookupKeyReadWithFlags` | `FLOWS.md` notes | ◐ |
| Commands reply via `addReply*`, never via C return values | `src/networking.c` | `CLAUDE.md` | ◐ |

### Commands

| Need | Command | Verified |
|---|---|---|
| Build | `make -j$(nproc)` | ✓ |
| Run one test | `./runtest --single unit/type/string` | ◐ (needs `tclsh`) |
| Run | `./src/redis-server --port 6379` | ✓ |

→ Full procedures and failure strings: `HOW-TO.md`

## Consumer Contract

### Schema

Anchors are `path → Symbol (search "…")` — never bare line numbers. Status is exactly
one of `✓ / ◐ / ?`. Every Concepts/Flows row links to a section that exists. The
Invariants Registry rows are rule + enforcing anchor + explaining doc + status.

### Safety Boundaries

| Action | Rule |
|---|---|
| Read | Always allowed. |
| Edit code | Only on `✓` or re-verified `◐`; never on `?`. |
| Break an invariant | Escalate as a design change with the anchor as a named risk. |
| Before editing | Re-verify the anchor against the recorded commit; code wins. |
| After editing | Write back: update the cited doc and its provenance. |
| Push / PR | Not granted by this KB; follow the host project's rules. |

## Task Recipes

Each recipe = read → extract → guardrails → write back. Worked against this instance.

### Recipe: Fix an Issue / Bug (example: "`GET` returns wrong reply")

1. **Read:** `FLOWS.md → Life of a GET` (incl. the WRONGTYPE branch); `CONCEPTS.md →
   dict` and `redisObject`; the invariants registry.
2. **Extract:** the failing step's anchor (e.g. `t_string.c → getGenericCommand`);
   the invariants your fix must keep (single-threaded; reply via `addReply*`).
3. **Guardrails:** re-verify each `◐` anchor; keep every registry invariant true.
4. **Write back:** if the root cause contradicts a note, fix the note + provenance.

### Recipe: Develop a Feature (example: a new string command)

1. **Read:** `OVERVIEW.md` (where things live); `t_string.c` for a sibling command;
   `CLAUDE.md` conventions.
2. **Extract:** the command-registration pattern (`src/commands/*.json` + a
   `*Command` function); the reply helpers; the keyspace API in `db.c`.
3. **Guardrails:** reply via `addReply*`; allocate via `zmalloc`; do not add locking.
4. **Write back:** add a Concept/Flow entry and an INDEX row for the new command.

### Recipe: Write a Design Document (example: change the rehash policy)

1. **Read:** `CONCEPTS.md → dict`; every invariants-registry row for the keyspace;
   `FLOWS.md` (lookup step).
2. **Extract and cite:** the current dual-table invariant; flows that depend on it;
   the latency goal that motivates incremental rehashing.
3. **Guardrails:** the dual-table invariant is load-bearing — a design that changes
   it is a **migration**; call it out with the anchor as a named risk.
4. **Write back:** link the design from `CONCEPTS.md → dict`.

### Recipe: Review a Change · Incident/Debug · Generate Tests · Refactor · Explain · Impact Analysis

These follow the same structure as the master `INDEX.md` in the template. For Redis,
the load-bearing inputs are always: the **invariants registry** above, the relevant
**flow's error branch**, and the **single-threaded** assumption. Example impact
analysis: a change to `dictFind` reaches *every* command (all keyspace reads go
through it) — blast radius is the whole command surface; treat with care.

## How This Index Stays True

Derived from `CONCEPTS.md`, `FLOWS.md`, and `HOW-TO.md`; refresh when they change.
Run `../../framework/tools/check-doc-drift.sh` (pointed at a Redis checkout) to find
which rows cite changed code. If a row points at a section or symbol that no longer
exists, the index has drifted — fix it before a skill acts on it.
