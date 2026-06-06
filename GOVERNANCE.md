# Governance

How this project separates the **framework** from a **generated instance**, and the
two change-control flows that keep both honest. Read this first if you are confused
about "what do I edit, and how do updates flow?"

## The Three Planes

The single most important idea: there are three kinds of files, with a **one-way
dependency**. An instance depends on the framework; the framework never depends on an
instance.

```
  framework/   (this repo, versioned)   ── maintainers own ── read-only to instances
       ▲
       │  pinned by version, referenced — never copied-and-edited
       │
  instance     (in a target codebase)   ── the dev/team owns
       ├─ authored   sources of truth, hand-written, reviewed
       ├─ generated  projections of the authored sources, rebuilt by tools
       └─ state      provenance + progress (pins the framework version)
```

| Plane | What it is | Lives in | Who owns it | How it changes |
|---|---|---|---|---|
| **Framework** | The methodology: standard, guide, writing style, agent protocol, schemas, tools | `framework/` (upstream) | maintainers | PR + SemVer + CHANGELOG (Flow A) |
| **Scaffold** | The blank fill-in starting point an instance is created from | `scaffold/` (upstream) | maintainers | same as framework |
| **Instance** | A *filled* note set for one real codebase | the target codebase | the developer/team | edited locally; updated via Flow B |
| **Fixtures** | Sample filled instances kept for illustration | `examples/` | maintainers | docs of the template |

`framework/MANIFEST.md` classifies every file's role (framework / authored /
generated / state). When in doubt, that file is authoritative.

## File Roles Inside an Instance

A created instance has three roles, and you treat each differently:

- **Authored (source of truth):** `OVERVIEW.md`, `CONCEPTS.md`, `FLOWS.md`,
  `HOW-TO.md`, `OPEN-QUESTIONS.md`, and the curated `CLAUDE.md` lean index. You write
  these. Review them like code.
- **Generated (do not hand-edit):** the `GENERATED:registry` block inside `INDEX.md` —
  a projection of `CONCEPTS.md` / `FLOWS.md`, rebuilt by
  `framework/tools/generate.sh`. The rest of `INDEX.md` (protocol, map, recipes) is
  authored.
- **State:** `HANDOFF.md` (pins `template_version`), `ONBOARD-CHECKLIST.md`,
  `logs/`. Provenance and progress.
- **Framework cache:** `.docforge/framework/` — a read-only copy of the framework at
  the pinned version, refreshed by `update-framework.sh`. Never hand-edited. (Like
  `node_modules`: present for offline and agent use, regenerated, not source.)

## Flow A — Evolving the Framework

For changing the template itself (the `framework/` and `scaffold/` planes).

1. Propose the change as a PR. See `CONTRIBUTING.md`.
2. **Meta-rule:** a change to `STANDARD.md` must itself meet the bar it defines. The
   standard governs its own edits.
3. Version with **SemVer** in `VERSION`:
   - **major** — a change that requires existing instances to do work (e.g., a new
     required section). Must include **instance-migration notes**.
   - **minor** — additive, no instance action required.
   - **patch** — clarifications, typos, tooling fixes.
4. Record it in `CHANGELOG.md`, with migration notes for any breaking change.
5. Merge after review. Schema changes additionally bump the schema version in
   `framework/schema/`.

## Flow B — Maintaining a Generated Instance

For keeping a real codebase's notes correct over time.

1. **Pin:** the instance records the framework version it was generated from in the
   `HANDOFF.md` state block (`template_version`).
2. **Edit authored docs only.** Never edit generated files or the framework cache.
3. **Rebuild projections** after editing concepts/flows:
   `framework/tools/generate.sh <instance-dir>`.
4. **Change control on content** (the gate before another reader or skill trusts it):
   - **Code is truth** — when code and a doc disagree, the code wins.
   - **Every claim is tagged** `✓ / ◐ / ?` and anchored `file → symbol`.
   - **Each doc has an Owner**; enforce it with `CODEOWNERS` in the host repo.
   - **Drift is checked in CI** — `framework/tools/check-doc-drift.sh` flags notes that
     cite changed code.
   - **Write-back** — a skill that changes the code updates the cited doc and its
     provenance.
5. **Upgrade the framework** when ready:
   - bump `template_version`, run `framework/tools/update-framework.sh <instance-dir>`
     to refresh `.docforge/framework/`,
   - read the `CHANGELOG.md` migration notes for the versions you crossed,
   - do the migration work (e.g., re-grade docs against a new required section),
   - re-run `generate.sh`.

## Why Reference, Not Copy

Copying the framework into each codebase forks it: the instance drifts from upstream
and can never cleanly adopt improvements. Pinning a version and refreshing a
read-only cache gives **controlled upgrades** instead — the same reason you depend on
a library at a version rather than vendoring and editing its source.

## Versioned Contracts (for Agents)

These docs are an API between agents that produce and consume them. The contracts an
agent may rely on are versioned in `framework/schema/`:

- `index.schema.md` — the shape of `INDEX.md` (the consumer entry point)
- `doc-header.schema.md` — the per-document header
- `tags.md` — the verification-tag vocabulary and the L0–L3 maturity levels

A consuming skill declares which schema version it targets, exactly as it would for
any API. Incompatible changes bump the schema's major version.
