# How-To: Common Tasks — Redis

**Doc type:** how-to (procedural)
**Audience:** a new hire in their first week on Redis
**You are assumed to know:** a C toolchain and a Unix shell
**Before you begin:** a clean checkout of `redis/redis`; `make` and a C compiler
**Owner:** _(example instance — unowned)_
**Last verified against commit:** 4625b89 (redis unstable)   **Status:** ◐ Read-only

> Procedural steps only. For *why* anything works this way, see `CONCEPTS.md`.
> Commands below are standard for recent Redis; confirm on your checkout and promote
> their status to `✓` the first time you run each.

## Prerequisites: One-Time Setup

| Tool | Version | Check |
|---|---|---|
| C compiler | gcc or clang | `cc --version` |
| make | any recent | `make --version` |
| Tcl | 8.5+ (for tests) | `echo 'puts $tcl_version' \| tclsh` |

Redis vendors its allocator (jemalloc) and other deps under `deps/`; `make` builds
them automatically. No package install is required for a basic build.

## Task 1: Build

```
$ make

# Expected (last lines):
#   Hint: It's a good idea to run 'make test' ;)
# Binaries appear in src/: redis-server, redis-cli, redis-check-rdb, ...
```

- **Time:** the first build is a few minutes (it builds jemalloc and Lua).
- **Common failure:** `jemalloc/jemalloc.h: No such file or directory` → the deps
  were not built; run `make distclean && make`.
- **Faster rebuilds:** `make -j$(nproc)`.

## Task 2: Run

```
$ ./src/redis-server --port 6379

# Expected: a startup banner, then
#   * Ready to accept connections tcp
```

In another terminal, talk to it:

```
$ ./src/redis-cli -p 6379 SET hello world
OK
$ ./src/redis-cli -p 6379 GET hello
"world"
```

- **Common failure:** `Could not create server TCP listening socket *:6379: bind:
  Address already in use` → another Redis is running; pick another `--port`.

## Task 3: Run a Single Test

The full suite is slow. Run one unit file:

```
$ ./runtest --single unit/type/string

# Expected: a series of [ok] lines, ending with
#   The End
#   All tests passed without errors!
```

- **Where tests live:** `tests/unit/` and `tests/integration/`. → see `OVERVIEW.md`.
- **Common failure:** `couldn't execute "tclsh": no such file or directory` → install
  Tcl (`apt-get install tcl` / `brew install tcl-tk`).

## Task 4: Make and Land a One-Line Change

The smallest end-to-end loop. Do it once on day one to prove your pipeline works.

1. Edit the startup log line: `src/server.c → main` (search the ASCII-art banner /
   the "Ready to accept connections" log). Change a log string.
   - Use a stable anchor, not a line number — the file shifts often.
2. Rebuild: `make -j$(nproc)`
3. Run: `./src/redis-server` and confirm your changed message appears.
4. Run the smoke tests: `./runtest --single unit/keyspace`
5. Submit: push a branch and open a pull request on GitHub. Redis uses PR review;
   sign-off and a clean CI run are expected.

- **Convention:** keep changes small and focused; the maintainers value minimalism.
- **Common failure:** edited a generated file (`commands.def`) by mistake → your edit
  is overwritten on build. Change the source `*.json` under `src/commands/` instead,
  or the C function, not the generated table.

## Task 5: Debug

```
# Run under a debugger:
$ gdb --args ./src/redis-server --port 6379

# Or enable verbose logging:
$ ./src/redis-server --loglevel debug
```

- **Most useful for a newcomer:** `redis-cli MONITOR` streams every command the
  server processes — a fast way to see your client's effect.
- **Common failure:** breakpoints "not hit" → you built with optimizations; rebuild
  with `make CFLAGS="-O0 -g"` for a debuggable binary.

## When a Command Here Stops Working

These steps drift as the build evolves. If one fails on a clean checkout and the
failure is not listed above, the step is stale — fix it and update
`Last verified against commit:` at the top.
