# CLAUDE.md

> **Lean** per-session bootstrap. Loaded into every conversation. **Target: ≤200 lines.**
> Check before commit: `wc -l CLAUDE.md`. If over 200, cut.
>
> If the AI can find something by reading another doc when needed, it does NOT belong here. This file is an **index**, not an encyclopedia.
>
> **Here to DO a task — fix a bug, build a feature, write a design doc — not to onboard?** Start at `INDEX.md`. It is the knowledge-base entry point for consuming skills: a machine-readable map, an invariants registry, and task recipes.

## Project in One Paragraph

_(Filled in Phase 6. 3-5 sentences max. What the project is, what it does, what's distinctive about how it does it.)_

## Top-Level Architecture (5 Lines)

_(5 lines. No more. The high-level shape — e.g., "Browser process orchestrates; renderer processes are sandboxed; GPU process owns hardware; all IPC goes through Mojo.")_

## Core Concepts You Must Know

If you don't know these, you'll misread everything else.

- **<Concept 1>** — one-line description. → See CONCEPTS.md
- **<Concept 2>** — one-line description. → See CONCEPTS.md
- **<Concept 3>** — one-line description. → See CONCEPTS.md
- **<Concept 4>** — one-line description. → See CONCEPTS.md
- **<Concept 5>** — one-line description. → See CONCEPTS.md

## Where to Look for What

| Task | Look in |
|---|---|
| Network behavior | `path/to/net/` |
| UI / rendering | `path/to/ui/` |
| Cross-process IPC | `path/to/ipc/` |
| Build configuration | `BUILD.gn` / `Cargo.toml` / etc. |
| Tests | `path/to/tests/` |

## Build / Test / Run

```
# Build (canonical command)
$ <command>

# Run a single test
$ <command>

# Run the binary
$ <command>
```

## Project Conventions That Aren't Obvious

These are the project-specific habits that affect every interaction:

- **File naming:** _(e.g., `*_win.cc` / `*_mac.mm` for platform-specific code)_
- **Module boundaries:** _(e.g., `content/` cannot depend on `chrome/`)_
- **Error handling:** _(e.g., uses `Status` returns, not exceptions)_
- **Threading:** _(e.g., UI thread vs IO thread is strictly separated)_
- **(Add others as discovered)**

## What to Search With What Tool

| Need | Tool |
|---|---|
| Find a definition or all references | clangd / LSP (most accurate) |
| Quick text grep | ripgrep (`rg`) |
| Cross-file structural map | Aider repomap (if installed) |
| Git history of a region | `git log -L` or `git blame` |

## Pointers to Detailed Docs

- **Knowledge-base entry for other skills** → `INDEX.md`
- **Common tasks (build / run / test / change)** → `HOW-TO.md`
- **Project structure** → `OVERVIEW.md`
- **Core concepts (deep dives)** → `CONCEPTS.md`
- **Important call chains** → `FLOWS.md`
- **Things we don't yet understand** → `OPEN-QUESTIONS.md`
- **Onboarding progress** → `ONBOARD-CHECKLIST.md`
- **Last session and next step** → `HANDOFF.md`
- **Phase definitions** → `ONBOARD-GUIDE.md`

## Behavioral Reminders for the Agent

The canonical rules live in the framework: `AGENT-PROTOCOL.md` (in an instance,
`.docforge/framework/AGENT-PROTOCOL.md`). A four-line summary for in-session reference:

1. **Code is truth.** When code and docs disagree, the code wins.
2. **Tag every claim.** ✓ Verified / ◐ Read-only / ? Speculation. Same rule for diagrams as for prose.
3. **Cite a stable `file → symbol` anchor for every code claim.** Untagged, uncited claims rot first.
4. **Respect file roles.** This file is curated by hand; `INDEX.md` is authored and its coverage is checked by `tools/check-index.sh`. Don't bloat this file — it changes rarely.

For the full rules (secrets, diagram rendering, writing-style, file roles), see `AGENT-PROTOCOL.md`.

---

_Last revised: YYYY-MM-DD against codebase commit `<HASH>`_
