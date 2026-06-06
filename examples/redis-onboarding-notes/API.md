# APIs & Interfaces — Redis

**Doc type:** reference (interface surface + feature map)
**Audience:** a developer learning Redis's entry points, public surface, and dependencies
**You are assumed to know:** C and the client/server model
**Before you begin:** read `OVERVIEW.md`
**Owner:** _(example instance — unowned)_
**Last verified against commit:** _(fill from your checkout)_   **Status:** ◐ Read-only
**Last verified date:** _(fill in)_

> Illustrative reference instance. Anchors are `file → symbol`; re-verify before use.
> Process/binary start points (`main`, `redis-cli`, the test runner) live in
> `OVERVIEW.md` → Entry Points; this doc covers the *callable* API surface.

## Provided API Surface (what Redis exposes)

| API / Symbol | Kind | Anchor | Stability | Entry point? | Purpose |
|---|---|---|---|---|---|
| RESP command set (`GET`, `SET`, `EXPIRE`, …) | network protocol | dispatch: `src/server.c → processCommand` (looks up + calls `call`) (search `"void call("`); table generated from `src/commands/*.json` | public, stable | **yes** → FLOWS "Life of a `GET`" | The primary public API: every client request is a command |
| Module API (`RedisModule_*`) | C API for loadable modules | `src/redismodule.h` (search `"RedisModule_Call"`) | public, versioned ABI | yes (for module devs) | Lets native modules add commands and types |

## Consumed Interfaces (libraries & internal modules)

The slice of each dependency — and each major internal module boundary — that the code
calls directly, with the wrapper that adapts it. Not exhaustive: only directly-used
interfaces, not every transitive dependency or boundary.

| Library / Module | Interface used (the subset) | Wrapped / adapted at | Why / for what |
|---|---|---|---|
| jemalloc (`deps/jemalloc`) | `malloc`/`free`/`realloc` + size introspection | `src/zmalloc.c → zmalloc`, `zfree` (search `"void *zmalloc"`) | All allocation goes through `zmalloc`, not raw `malloc` |
| OS poller (epoll / kqueue / select) | readiness notification | `src/ae_epoll.c` (+ `ae_kqueue.c` / `ae_evport.c` / `ae_select.c`) `→ aeApiPoll`; `ae.c` is the generic loop that calls it | The single-threaded event loop |
| Lua (`deps/lua`) | embed + call interpreter | `src/script_lua.c`, `src/eval.c → evalCommand` (Redis ≥ 7.0; pre-7.0 `src/scripting.c`) | Server-side scripting (`EVAL`) |
| OpenSSL | TLS handshake / read / write | `src/tls.c` (via the connection abstraction) | Encrypted client/replica connections |
| internal: networking → transport | `ConnectionType` (plain socket vs TLS) | `src/connection.h` (search `"ConnectionType"`) | One interface; TLS is a drop-in implementation |
| internal: dispatch → a command | `redisCommandProc` — `void cmd(client *c)` | `src/server.h` (search `"redisCommandProc"`) | Every command implements this; replies via `addReply*` |

## Feature → API Map

For each feature: the entry-point API you trace from, the interfaces it consumes, and
the flow (filled in as flows are traced).

| Feature | Provided entry-point API | Key consumed interfaces | Flow |
|---|---|---|---|
| Read a value | `GET` → `src/t_string.c → getCommand` | `dict` (`dictFind`), reply API (`addReplyBulk`) | → `FLOWS.md` → "Life of a `GET`" |
| Expire a key | `EXPIRE` → `src/expire.c → expireGenericCommand` | `setExpire` (`db.c`), `mstime()` | — (not yet traced) |

## API Stability & Versioning

The **RESP command set is the stable public contract** — backward compatibility is a
strong project norm. The **module API** (`redismodule.h`) is versioned
(`REDISMODULE_APIVER_1`) and is the ABI native modules link against. Internal C
functions (e.g. `dictFind`) are *not* a public API and change freely.
