# Manifest — File Roles

The authoritative classification of every file by **role**. This is what tells you
what to edit, what to leave to the tools, and what to pull from upstream. See
`GOVERNANCE.md` for the planes.

Roles:

- **framework** — upstream-owned methodology. Read-only in an instance (lives in the
  `.docforge/framework/` cache). Edit only in the upstream repo.
- **authored** — a source of truth you write and review by hand.
- **generated** — a projection of authored sources, rebuilt by `generate.sh`. Do not
  hand-edit.
- **state** — provenance and progress.

## Framework plane (upstream)

| File | Role |
|---|---|
| `framework/STANDARD.md` | framework |
| `framework/ONBOARD-GUIDE.md` | framework |
| `framework/WRITING-STYLE.md` | framework |
| `framework/AGENT-PROTOCOL.md` | framework |
| `framework/EXAMPLES.md` | framework |
| `framework/MANIFEST.md` | framework |
| `framework/schema/*.md` | framework (versioned contract) |
| `framework/tools/*.sh` | framework |

## Scaffold plane → becomes an instance

When `scaffold/` is used to create an instance, each file takes the role below.

| File | Role | You… |
|---|---|---|
| `AGENT-warm-up.md` | state + framework pointer | fill the identity block; pins `template_version` |
| `OVERVIEW.md` | authored | write |
| `CONCEPTS.md` | authored | write |
| `FLOWS.md` | authored | write |
| `HOW-TO.md` | authored | write |
| `OPEN-QUESTIONS.md` | authored | write |
| `CLAUDE.md` | authored (curated lean index) | curate by hand; keep ≤200 lines |
| `INDEX.md` | authored prose + **generated registry** | write the protocol/map/recipes; the registry block between `GENERATED` markers is rebuilt by `generate.sh` — do not hand-edit it |
| `HANDOFF.md` | state | update each session; holds the version pin |
| `ONBOARD-CHECKLIST.md` | state | update each session |
| `logs/` | state | one file per session |
| `.docforge/framework/` | framework (cache) | never edit — `update-framework.sh` |

## Generated-from map

`generate.sh` builds the generated region from these authored sources:

| Generated region | Built from |
|---|---|
| `INDEX.md` → the `GENERATED:registry` block (Concept/Flow registry: name, anchor, status) | `CONCEPTS.md`, `FLOWS.md` (`## Concept:` / `## Flow:` headings + Anchor/Trigger/Status) |

Hand-authored prose in `INDEX.md` lives **outside** the `GENERATED` marker region and
is preserved across rebuilds. `CLAUDE.md` is curated by hand (judgment required to stay
lean), not generated.
