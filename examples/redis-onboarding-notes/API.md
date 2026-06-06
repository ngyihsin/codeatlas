# APIs & Interfaces — Redis

**Doc type:** reference (interface surface + feature map)
**Audience:** a developer learning Redis's entry points, public surface, and dependencies
**You are assumed to know:** C and the client/server model
**Before you begin:** read `OVERVIEW.md`
**Owner:** _(example instance — unowned)_
**Last verified against commit:** _(fill from your checkout)_   **Status:** ◐ Read-only

> Illustrative reference instance. Anchors are `file → symbol`; re-verify before use.

## Provided API Surface (what Redis exposes)

| API / Symbol | Kind | Anchor | Stability | Entry point? | Purpose |
|---|---|---|---|---|---|
| RESP command set (`GET`, `SET`, `EXPIRE`, …) | network protocol | dispatch at `src/server.c → call` (search `"call("`); table generated from `src/commands/*.json` | public, stable | **yes** → FLOWS "Life of a `GET`" | The primary public API: every client request is a command |
| Server `main()` | process entry | `src/server.c → main` (search `"int main(int argc"`) | — | **yes** | Process startup; sets up the event loop |
| Module API (`RedisModule_*`) | C API for loadable modules | `src/redismodule.h` (search `"RedisModule_Call"`) | public, versioned ABI | yes (for module devs) | Lets native modules add commands and types |
| `redis-cli` | CLI | `src/redis-cli.c → main` | public | no (a client) | Interactive/scripted client |

## Consumed Library Interfaces (what Redis uses, and how)

| Library / Module | Interface used (the subset) | Wrapped / adapted at | Why / for what |
|---|---|---|---|
| jemalloc (`deps/jemalloc`) | `malloc`/`free`/`realloc` + size introspection | `src/zmalloc.c → zmalloc`, `zfree` (search `"void *zmalloc"`) | All allocation goes through `zmalloc`, not raw `malloc` |
| OS poller (epoll / kqueue / select) | readiness notification | `src/ae.c → aeApiPoll` (+ `ae_epoll.c`, `ae_kqueue.c`) | The single-threaded event loop |
| Lua (`deps/lua`) | embed + call interpreter | `src/script_lua.c`, `src/eval.c → evalCommand` | Server-side scripting (`EVAL`) |
| OpenSSL | TLS handshake / read / write | `src/tls.c` (via the connection abstraction) | Encrypted client/replica connections |
| linenoise (`deps/linenoise`) | line editing | `src/redis-cli.c` | `redis-cli` input editing |

## Internal Module Interfaces

| Module boundary | Interface (the contract) | Anchor | Notes |
|---|---|---|---|
| networking → transport | `ConnectionType` (plain socket vs TLS) | `src/connection.h` (search `"ConnectionType"`) | One interface; TLS is a drop-in implementation |
| dispatch → a command | `redisCommandProc` — `void cmd(client *c)` | `src/server.h` (search `"redisCommandProc"`) | Every command implements this; replies via `addReply*` |

## Feature → API Map

| Feature | Provided entry-point API | Key consumed interfaces | Flow |
|---|---|---|---|
| Read a value | `GET` → `src/t_string.c → getCommand` | `dict` (`dictFind`), reply API (`addReplyBulk`) | → `FLOWS.md` → "Life of a `GET`" |
| Expire a key | `EXPIRE` → `src/expire.c → expireGenericCommand` | `setExpire` (`db.c`), `mstime()` | (not yet traced) ◐ |
| Run a script | `EVAL` → `src/eval.c → evalCommand` | Lua interpreter interface | (not yet traced) ◐ |
| Snapshot to disk | `BGSAVE` → `src/rdb.c` (search `"bgsaveCommand"`) | `fork(2)`, RDB serialization | (not yet traced) ◐ |

## API Stability & Versioning

The **RESP command set is the stable public contract** — backward compatibility is a
strong project norm. The **module API** (`redismodule.h`) is versioned
(`REDISMODULE_APIVER_1`) and is the ABI native modules link against. Internal C
functions (e.g. `dictFind`) are *not* a public API and change freely.
