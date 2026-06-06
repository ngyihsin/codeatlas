# CLAUDE.md — Redis onboarding notes

> Lean per-session index (≤200 lines). Illustrative reference instance — all code
> claims are `◐`; re-verify against your checkout.
>
> **Here to DO a task — fix a bug, build a feature, write a design doc?** Start at
> `INDEX.md` (machine-readable map, invariants registry, task recipes).

## Project in One Paragraph

Redis is an in-memory data-structure store (database, cache, message broker). It
holds native data types in RAM and serves clients over the text-based RESP protocol.
The distinctive trait: command execution is **single-threaded** over a custom event
loop, which makes every command atomic and lock-free.

## Top-Level Architecture (5 lines)

- One event loop (`ae.c`) waits on all client sockets.
- `networking.c` reads bytes and parses RESP into a command array.
- `server.c` (`processCommand` → `call`) dispatches to a per-type command function.
- Commands read/write the keyspace, a `dict` per `redisDb` (`db.c`, `dict.c`).
- Persistence (`rdb.c`/`aof.c`) and replication run around command execution.

## Core Concepts You Must Know

- **Single-threaded execution** — commands run on one thread; no locks needed. → OVERVIEW
- **`dict` + incremental rehashing** — the keyspace hash table resizes gradually. → CONCEPTS.md
- **`redisObject` (`robj`)** — every value is a boxed type+encoding+refcount. → CONCEPTS.md

## Where to Look for What

| Task | Look in |
|---|---|
| Command dispatch | `src/server.c → processCommand`, `call` |
| A specific command | `src/t_<type>.c` (e.g. `t_string.c → getCommand`) |
| Keyspace read/write | `src/db.c → lookupKeyRead`, `dbAdd` |
| Hash table internals | `src/dict.c` / `src/dict.h` |
| Protocol / replies | `src/networking.c → addReply*` |
| Persistence | `src/rdb.c`, `src/aof.c` |

## Build / Test / Run

```
$ make -j$(nproc)                       # build
$ ./src/redis-server --port 6379        # run
$ ./runtest --single unit/type/string   # one test
```

Full steps and error strings: `HOW-TO.md`.

## Project Conventions That Aren't Obvious

- **Single-threaded:** never add locking inside a command proc for keyspace access.
- **Replies, not return values:** commands answer via `addReply*`, not C returns.
- **Memory:** allocate via `zmalloc`/`zfree` (`src/zmalloc.c`), not raw `malloc`.
- **Generated command table:** edit `src/commands/*.json` or the C function, not
  generated `commands.def`.

## Pointers to Detailed Docs

- **Knowledge-base entry for other skills** → `INDEX.md`
- **Common tasks** → `HOW-TO.md`
- **Structure** → `OVERVIEW.md`
- **Concepts (deep dives)** → `CONCEPTS.md`
- **Flows** → `FLOWS.md`

## Behavioral Reminders

1. Code is truth; when code and these notes disagree, the code wins.
2. Tag every claim ✓ / ◐ / ? — here, treat everything as ◐ until you re-verify.
3. Cite `file → symbol`, not line numbers.

---

_Illustrative reference instance. Last revised: example — set a real commit before use._
