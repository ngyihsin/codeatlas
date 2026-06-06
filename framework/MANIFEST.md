# Manifest — File Roles

The authoritative classification of every file by **role**. This is what tells you
what to edit, what to leave to the tools, and what to pull from upstream. See
`GOVERNANCE.md` for the planes.

Roles:

- **framework** — upstream-owned methodology. Read-only in an instance (lives in the
  `.docforge/framework/` cache). Edit only in the upstream repo.
- **authored** — a source of truth you write and review by hand.
- **state** — provenance and progress.

No file in an instance is machine-generated; nothing is overwritten by a tool. The
authored docs are the source of truth, and `tools/check-index.sh` *verifies* (but
never rewrites) that `INDEX.md` stays complete.

## Framework plane (upstream)

| File | Role |
|---|---|
| `framework/STANDARD.md` | framework |
| `framework/ONBOARD-GUIDE.md` | framework |
| `framework/WRITING-STYLE.md` | framework |
| `framework/AGENT-PROTOCOL.md` | framework |
| `framework/GENERATION.md` | framework (auto-generation pipeline spec) |
| `framework/EXAMPLES.md` | framework |
| `framework/MANIFEST.md` | framework |
| `framework/schema/*.md` | framework (versioned contract) |
| `framework/tools/*.sh` | framework |

## Scaffold plane → becomes an instance

When `scaffold/` is used to create an instance, each file takes the role below.

| File | Role | You… |
|---|---|---|
| `AGENT-warm-up.md` | state + framework pointer | fill the identity block |
| `OVERVIEW.md` | authored | write |
| `CONCEPTS.md` | authored | write |
| `FLOWS.md` | authored | write |
| `HOW-TO.md` | authored | write |
| `API.md` | authored | write (provided + consumed interfaces, feature→API map) |
| `OPEN-QUESTIONS.md` | authored | write |
| `CLAUDE.md` | authored (curated lean index) | curate by hand; keep ≤200 lines |
| `INDEX.md` | authored (Knowledge Map is the source of truth) | write the protocol/map/recipes; run `check-index.sh` to confirm coverage |
| `HANDOFF.md` | state | update each session; **holds the `template_version` pin** in its state block |
| `ONBOARD-CHECKLIST.md` | state | update each session |
| `logs/` | state | one file per session |
| `.docforge/framework/` | framework (cache) | never edit — `update-framework.sh` |

## Keeping INDEX.md complete

`check-index.sh` verifies — it does not generate. It reads the `## Concept:` and
`## Flow:` headings in `CONCEPTS.md` / `FLOWS.md` and fails if any is missing from the
`INDEX.md` Knowledge Map. The Knowledge Map and `CLAUDE.md` are both authored by hand;
nothing overwrites them.
