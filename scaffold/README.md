# <PROJECT_NAME> Onboarding Notes

> AI-assisted onboarding notes for understanding `<PROJECT_NAME>`. Built on the [docforge-onboard](https://github.com/your-fork/docforge-onboard) template.

## What This Is

A structured set of documents that an AI agent (and you) progressively fill in to understand a large existing codebase. The codebase being studied is at:

- **Codebase path:** `<CODEBASE_PATH>`
- **Languages:** `<LANGUAGES>`

This is **not** the codebase itself. This is the **understanding** of the codebase — captured as living documents that survive across AI sessions.

## How to Use This in a Session

1. Open your AI agent (Claude Code, Cursor, Codex, etc.).
2. Tell it: **"Read AGENT-warm-up.md"**
3. The agent will detect whether this is a first-time onboarding or a continuing session, and proceed accordingly.

That's it. Everything else is described inside `AGENT-warm-up.md`.

**To instead use these docs to get work done** — a digital colleague fixing a bug,
building a feature, or writing a design document — point the skill at `INDEX.md`.
It routes to the right knowledge and defines what is safe to act on.

## Document Index

These are the files **you own** in this instance. The methodology they follow lives
in the read-only framework cache `.docforge/framework/` (pinned to `template_version`
in `HANDOFF.md`). You edit the *authored* files; `tools/check-index.sh` verifies
`INDEX.md` covers every concept and flow; you never hand-edit the cache. Full role
taxonomy: `.docforge/framework/MANIFEST.md`.

**Instance files (you own):**

| Document | Role |
|---|---|
| `AGENT-warm-up.md` | Bootstrap for the **authoring** agent, read every session (state) |
| `INDEX.md` | Entry point for **consuming** skills (authored map; coverage checked by `check-index.sh`) |
| `OVERVIEW.md` | What the project is, top-level structure (authored) |
| `CONCEPTS.md` | Core abstractions, deep-dived (authored) |
| `FLOWS.md` | Concrete call chains for user-visible behaviors (authored) |
| `HOW-TO.md` | Copy-pasteable common first-week tasks (authored) |
| `OPEN-QUESTIONS.md` | Things we don't yet understand (authored) |
| `CLAUDE.md` | ≤200-line per-session context (curated) |
| `HANDOFF.md` | Last session, next step, state sentinel + version pin (state) |
| `ONBOARD-CHECKLIST.md` | Phase / topic completion tracking (state) |
| `logs/` | Per-session detailed logs (state) |

**Framework cache (`.docforge/framework/`, read-only):**

| Document | Role |
|---|---|
| `STANDARD.md` | The quality bar, exemplars, maturity rubric |
| `ONBOARD-GUIDE.md` | Phase definitions and workflow |
| `WRITING-STYLE.md` | Writing rules for non-native readers; diagrams |
| `AGENT-PROTOCOL.md` | Canonical behavioral rules |
| `EXAMPLES.md` | Illustrative fragments |
| `MANIFEST.md`, `schema/`, `tools/` | File-role taxonomy, versioned contracts, automation |

## How Far Along Are We?

See `ONBOARD-CHECKLIST.md` for the current state.

See `HANDOFF.md` for what we're doing next.

## Project-Specific Notes

_(Anything unique about this codebase that doesn't fit elsewhere — links to upstream docs, mailing lists, IRC channels, key contributors, etc.)_

- Upstream repository:
- Bug tracker:
- Mailing list / forum:
- Key documentation links:
