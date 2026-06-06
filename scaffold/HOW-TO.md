# How-To: Common Tasks

**Doc type:** how-to (procedural)
**Audience:** a new hire in their first week on this codebase
**You are assumed to know:** the language and general developer tooling, but
nothing about *this* project's build
**Before you begin:** a clean checkout of the codebase at `<CODEBASE_PATH>`
**Owner:** _(who keeps these steps working)_
**Last verified against commit:** _(short hash)_   **Status:** ✓ / ◐ / ?

> This is the new hire's first stop. It answers "how do I build, run, test, and
> land a one-line change" — nothing else. Keep it **procedural**: steps that work
> as written, with expected output. Do **not** explain *why* here; send the reader
> to `CONCEPTS.md` for that.
>
> Every command must be **copy-pasteable** and verified on a clean checkout. A step
> that "usually works" is a broken step. Show the expected output so the reader
> knows it worked. Include the literal **error string** for the common failure of
> each task, so an agent reader can self-correct (see `STANDARD.md` → "Writing for
> Agent Readers").

## Prerequisites: One-Time Setup

The tools and versions this codebase needs. Pin versions — "latest" drifts.

| Tool | Version | Install / check |
|---|---|---|
| _(compiler / runtime)_ | _(e.g., 1.78)_ | `<command --version>` |
| _(build system)_ | | |
| _(package manager)_ | | |

```
# One-time environment setup (clone, submodules, deps)
$ <command>

# Expected: <what success looks like — last line, exit 0, etc.>
```

**Common failure:** `<literal error string>` → _(what it means and the fix)_

## Task 1: Build

```
$ <build command>

# Expected (last lines):
# <success marker>
```

- **Time:** _(rough first-build time, so the reader does not think it hung)_
- **Common failure:** `<literal error string>` → _(fix)_

## Task 2: Run

```
$ <run command>

# Expected: <what the running program shows / which port / what to open>
```

- **Common failure:** `<literal error string>` → _(fix)_

## Task 3: Run a Single Test

Running the whole suite is slow. This is how to run just one.

```
$ <command to run ONE test by name or file>

# Expected: <pass output>
```

- **Where tests live:** _(path)_  → see `OVERVIEW.md` → Entry Points
- **Common failure:** `<literal error string>` → _(fix)_

## Task 4: Make and Land a One-Line Change

The smallest end-to-end loop: edit, build, test, submit. Do this once on day one to
prove the whole pipeline works for you.

1. Edit a file: _(suggest a safe, low-risk first change — e.g., a log string)_
   - Anchor: `<file + symbol>` (search `<string>`). Avoid bare line numbers.
2. Rebuild: `<command>`
3. Run the relevant test: `<command>`
4. Submit for review: `<command>` _(the project's PR / CL / patch flow)_

- **Branch / review convention:** _(branch naming, who reviews, required checks)_
- **Common failure:** `<literal error string>` → _(fix)_

## Task 5: Debug (Optional but Common)

```
$ <how to run under a debugger, or attach, or enable verbose logging>
```

- **Most useful log / flag for a newcomer:** _(name it)_
- **Common failure:** `<literal error string>` → _(fix)_

## When a Command Here Stops Working

These steps drift as the build changes. If a command fails on a clean checkout and
the failure is not in a "Common failure" note above, the step is stale. Fix it and
update the `Last verified against commit:` field at the top. A how-to that does not
work on a clean checkout is worse than none.
