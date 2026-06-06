# APIs & Interfaces

**Doc type:** reference (interface surface + feature map)
**Audience:** anyone learning where the code is entered, what it exposes, and which
library interfaces it depends on — a prime starting point for code tracing
**You are assumed to know:** the project's language(s)
**Before you begin:** read `OVERVIEW.md` for the structural map
**Owner:** _(who keeps this true)_
**Last verified against commit:** _(short hash)_   **Status:** ✓ / ◐ / ?
**Last verified date:** _(YYYY-MM-DD)_

> Why this doc: the **public API surface** is the set of front doors into the code, so
> it is the best place to *start a trace*. Knowing what the codebase **provides** and
> what library interfaces it **consumes** answers "where does this enter?" and "what
> does this depend on?" before you read a line of logic. Use stable `file → symbol`
> anchors, not line numbers. Tag entry points so a reader (or skill) can jump straight
> in. See `STANDARD.md` → "Documenting APIs and Interfaces".

## Provided API Surface (what this codebase exposes)

The public *callable* surface this codebase offers — functions, classes, commands,
endpoints, the registration/config interface. `Entry point?` marks the ones a reader
should trace *from*; link them to `FLOWS.md`. Keep **process/binary start points**
(`main`, daemons, the CLI binary, the test runner) in `OVERVIEW.md` → Entry Points, not
here — no row should appear in both. (For a library whose entry points *are* its API,
point `OVERVIEW.md` here instead of duplicating.)

| API / Symbol | Kind | Anchor | Stability | Entry point? | Purpose |
|---|---|---|---|---|---|
| _(name)_ | function / class / CLI cmd / endpoint / macro / config | `path → Symbol` (search `"…"`) | public / internal / experimental | yes → FLOWS "…" / no | _(one line)_ |

> **Kinds** to consider per project type: a library exposes functions/classes/headers;
> a CLI exposes commands/flags; a service exposes HTTP/RPC/socket endpoints; a plugin
> host exposes a registration/config interface; many codebases have a top-level
> **entry-point macro or `main`** (e.g. a module-init macro, a command table).

## Consumed Interfaces (libraries & internal modules)

For each external dependency — and each major **internal module boundary** not already
covered by a `CONCEPTS.md` entry — record the *slice* of its interface the codebase
actually uses and where that use is wrapped or adapted. This is the interface you must
understand to follow a call out of this codebase (or across a module boundary). Prefix
internal-module rows with `internal:` to tell them from third-party libraries.

| Library / Module | Interface used (the subset) | Wrapped / adapted at | Why / for what |
|---|---|---|---|
| _(dependency)_ | _(the functions/types/protocol actually called)_ | `path → Symbol` (the adapter/wrapper) | _(the feature or subsystem that needs it)_ |
| internal: _(A → B)_ | _(what B promises A)_ | `path → Symbol` | _(direct call / callback / queue / IPC)_ |

> Get the dependency list from the build config read in Phase 1
> (`package.json` / `Cargo.toml` / `CMakeLists.txt` / `go.mod` / `pyproject.toml`).
> **Not exhaustive:** list only the interfaces the code calls directly and the wrapper
> that adapts them — not every transitive dependency or internal boundary. If a
> boundary already has a `CONCEPTS.md` entry, point to it instead of re-describing it.

## Feature → API Map (what APIs power what features)

For each user-visible feature: the provided API you enter through, the key consumed
interfaces it relies on, and the flow it triggers. This is the fast path from "I care
about feature X" to "here is where it starts and what it touches".

| Feature | Provided entry-point API | Key consumed interfaces | Flow |
|---|---|---|---|
| _(feature)_ | `path → Symbol` | _(library/module interfaces it calls)_ | → `FLOWS.md` → "…" |

## API Stability & Versioning (notes)

_(How does this project signal what is public vs internal? Semantic versioning? A
header/namespace convention? A deprecation policy? Anything that tells a reader which
APIs are safe to depend on. If the project does not signal this, say so.)_
