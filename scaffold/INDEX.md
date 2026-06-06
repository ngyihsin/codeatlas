# Knowledge Base Index — Entry Point for Consuming Skills

**Doc type:** reference (machine-readable routing + action contract)
**Audience:** an agent, skill, or digital colleague here to **do a task** (fix a bug,
build a feature, write a design doc) — and humans who want the map
**You are assumed to know:** nothing project-specific; this file routes you
**Before you begin:** none
**Owner:** _(who keeps this index in sync with CONCEPTS / FLOWS / HOW-TO)_
**Last verified against commit:** _(short hash)_   **Status:** ✓ / ◐ / ?
**Index schema:** v1 — column names and meanings are stable within a major version (see "Consumer Contract")

> **Two entry points exist.** To **build** these docs, read `AGENT-warm-up.md`. To
> **use** these docs to get work done, you are in the right place. This file is the
> single front door for consuming skills. `CLAUDE.md` is auto-loaded by the harness
> and points here.
>
> This index is a **router, not a copy.** It points at the detailed docs
> (`CONCEPTS.md`, `FLOWS.md`, `HOW-TO.md`) and adds the few things a skill needs to
> act **safely**: trust gates, an invariants registry, and task recipes.

## Consumption Protocol (read before acting)

1. **Route by task.** Jump to the matching recipe under "Task Recipes" below. It
   tells you which docs to read and what to extract.
2. **Trust gates — the `✓ / ◐ / ?` tag decides what you may do:**
   - `✓ Verified` — safe to rely on and act on.
   - `◐ Read-only` — read but not run; **re-verify the anchor before editing code**.
   - `?  Speculation` — **do not act on it.** Treat as an open question; confirm
     first.
3. **Re-verify before you edit.** Each entry has a `Last verified against commit`.
   Run `git log <that-hash>..HEAD -- <path>`. If the file changed, the claim may be
   stale — confirm against current code. **When code and a doc disagree, the code
   wins.**
4. **Honor invariants.** The Invariants Registry lists must-not-break rules. A change
   that violates one is a bug **even if the tests pass**. If your task *requires*
   breaking one, that is a design change — say so explicitly (see the design-doc
   recipe).
5. **Write back.** If you learn something new, or your change makes a doc wrong,
   update the cited doc and bump its `Last verified against commit`. Consumers keep
   the knowledge base true; a KB that only authors maintain rots between sessions.

## Knowledge Map (machine-readable)

> Tables a skill can parse without reading prose. Anchors are `file + symbol +
> search-string` (line numbers drift). Each row links to the detailed doc.

### Concepts

| Concept | Anchor (file → symbol) | Status | What breaks without it | Use when |
|---|---|---|---|---|
| _(name)_ | `path → Symbol` (search `"…"`) | ✓/◐/? | _(the mental-model error)_ | _(the task signal that means "read this")_ |

→ Detail: `CONCEPTS.md`

### Flows

| Flow | Trigger | Error / early-exit branch | Status | Use when |
|---|---|---|---|---|
| _(name)_ | _(action)_ | `path → Symbol` | ✓/◐/? | _(e.g., "a bug in reload behavior")_ |

→ Detail: `FLOWS.md`

### Key Data Structures

| Structure | Anchor | Invariants documented in |
|---|---|---|
| _(name)_ | `path → Struct` (search `"…"`) | `CONCEPTS.md` → _(concept)_ |

### Task → Location Map

| To change… | Look in | Owner |
|---|---|---|
| _(behavior / feature area)_ | `path/` | _(team / person)_ |

### Invariants / Must-Not-Break Registry

The rules a change must preserve. Action-critical: a consuming skill checks this
before editing.

| Invariant (what must stay true) | Enforced / relied on at (anchor) | Explained in | Status |
|---|---|---|---|
| _(e.g., "the task list is walked only under rcu_read_lock")_ | `path → Symbol` | `CONCEPTS.md` → _(concept)_ | ✓/◐/? |

### Commands

| Need | Command | Verified |
|---|---|---|
| Build | `<cmd>` | ✓/◐ |
| Run one test | `<cmd>` | ✓/◐ |
| Run | `<cmd>` | ✓/◐ |

→ Full procedures and failure strings: `HOW-TO.md`

## Consumer Contract

Other skills depend on this file having a predictable shape and clear rules. This
section is that contract.

### Schema (stable shape for parsers)

The `Index schema` field in the header gives the major version. Within a major
version, these column meanings do not change; new columns may be appended.

| Element | Stable shape |
|---|---|
| **Anchor** | `path/to/file → SymbolName` plus `(search "<literal string>")`. Never a bare line number — line numbers are not part of the contract. |
| **Status** | Exactly one of `✓` (verified), `◐` (read-only), `?` (speculation). |
| **Concepts / Flows / Data Structures** | Each row links to a section that exists in `CONCEPTS.md` / `FLOWS.md`. A dangling row is a contract violation. |
| **Invariants Registry** | Each row is a rule that must stay true, an enforcing anchor, the explaining concept, and a status. |

A parser may rely on: the header fields, the section headings above, and the column
order in each table. If the schema must change incompatibly, bump the major version.

### Safety Boundaries — What a Consuming Skill May Do

| Action | Rule |
|---|---|
| **Read** | Always allowed. |
| **Edit code** | Only when the relevant claim is `✓`, or `◐` that you re-verified against current code. **Never edit based on a `?` claim.** |
| **Break an invariant** | Not allowed silently. If your task requires it, escalate it as a design change (see the design-doc recipe) with the anchor as a named risk. |
| **Before editing** | Re-verify the anchor: `git log <Last verified against commit>..HEAD -- <path>`. If the file changed, confirm against current code. Code wins over docs. |
| **After editing or learning** | Write back: update the cited doc and bump its `Last verified against commit`. |
| **Push / open a PR** | This KB does not grant that permission. Follow the host project's rules and the user's instructions. |
| **Secrets** | The docs deliberately exclude secrets (see `AGENT-warm-up.md` → "What NOT to Capture"). Do not add any while writing back. |

## Task Recipes

Each recipe is a reading path + what to extract + guardrails + what to write back.

### Recipe: Fix an Issue / Bug

1. **Read:** the matching Flow (incl. its error branch), the Concept(s) it lists,
   and the relevant Invariants Registry rows.
2. **Extract:** the `file + symbol` where the behavior lives; the invariants your fix
   must preserve; the literal error signature from the flow's error branch.
3. **Guardrails:** do not act on `?` claims; re-verify `◐` anchors against current
   code; keep every listed invariant true.
4. **Write back:** if the root cause contradicts a doc, fix the doc and its
   provenance; add a resolved entry to `OPEN-QUESTIONS.md` if it answered a mystery.

### Recipe: Develop a Feature

1. **Read:** `OVERVIEW.md` (where things live + module boundaries), the Concepts for
   the subsystem you extend, and the Flow(s) your feature changes.
2. **Extract:** the extension point (where similar features hook in); the module
   boundary and dependency rules you must respect; project conventions from
   `CLAUDE.md`.
3. **Guardrails:** stay inside the module boundaries in the Task→Location map; do not
   break an Invariants Registry rule without escalating it as a design change.
4. **Write back:** add a new Concept or Flow entry for what you built, anchored and
   tagged, so the next skill can find it.

### Recipe: Write a Design Document

These onboarding docs are **code → understanding**; a design doc is **design →
code** (the sibling `docforge` direction). Ground the design in current reality:

1. **Read:** the Concepts, Flows, and Invariants for every area the design touches,
   plus relevant `OPEN-QUESTIONS.md` entries.
2. **Extract and cite (with anchors):** the current behavior the design changes; the
   invariants the design must preserve **or** explicitly proposes to change; the
   affected flows; the open questions the design must resolve.
3. **Guardrails:** any invariant the design breaks is a migration — call it out, with
   the anchor, as a named risk. A design that silently violates an invariant is the
   most expensive kind of bug.
4. **Write back:** link the finished design doc from the Concepts it builds on, so
   future readers see "understanding → design" in both directions.

### Recipe: Review a Change (Code / PR Review)

1. **Read:** the diff; the Concepts and Flows for the touched area; the Invariants
   Registry; the conventions in `CLAUDE.md`.
2. **Extract:** which invariants the change touches; whether it stays inside the
   module boundaries in the Task→Location map; whether it follows project
   conventions; whether any cited doc is now stale.
3. **Guardrails:** an invariant violation is a **blocking** review finding even if
   the tests pass. Flag boundary and convention breaks. Do not approve a behavior
   change that leaves a cited doc wrong.
4. **Write back:** record which docs the author must update; if the change is sound
   but the doc drifted, note the fix needed.

### Recipe: Respond to an Incident / Debug

1. **Read:** match the observed error to a Flow's **error branch** (Knowledge Map →
   Flows); find the owning subsystem via Task→Location; use `HOW-TO.md` to reproduce.
2. **Extract:** the failing step's `file + symbol`; the invariant possibly violated;
   the reproduction command and the literal error signature.
3. **Guardrails:** re-verify `◐` anchors before changing anything; do not act on `?`.
4. **Write back:** if the incident reveals undocumented behavior, add a Flow or
   error-branch entry, or an `OPEN-QUESTIONS.md` entry.

### Recipe: Generate Tests

1. **Read:** the Flow (happy path **and** error branch) or the Concept; the data
   structure's invariants.
2. **Extract:** the steps to assert; the error branch to cover; the boundary
   conditions implied by the invariants.
3. **Guardrails:** cover the documented **error branch**, not only the happy path.
   Tag any behavior you could not confirm as `?` rather than asserting it.
4. **Write back:** link the tests from the Flow; if a test proves a doc wrong, fix
   the doc and its provenance.

### Recipe: Refactor / Migrate

1. **Read:** the Concept and data structure; every Invariants Registry row for the
   area; every Flow that passes through it; the concept's Connections
   (callers / callees).
2. **Extract:** every invariant that must survive the refactor; every flow that must
   still work; the dependents that the change reaches.
3. **Guardrails:** preserve all invariants. If one must change, that is a
   **migration** — document it and flag the dependents from the Connections list.
4. **Write back:** a refactor moves code, so **update the anchors**, the
   data-structure table, and the provenance. Stale anchors after a refactor are the
   most common way this KB rots.

### Recipe: Explain / Answer a Question (human support)

1. **Read:** route the question through the Knowledge Map; read the matching Concept
   or Flow.
2. **Extract:** the answer, its anchor, and its status tag.
3. **Guardrails:** answer only at the confidence the tag allows. Cite the anchor. If
   the source is `?`, say the answer is unverified.
4. **Write back:** if the question exposes a gap, add an `OPEN-QUESTIONS.md` entry.

### Recipe: Impact Analysis ("Blast Radius")

1. **Read:** the Concept's Connections (called-by / calls-into); the Flows that
   traverse it; the Invariants that rely on it; Task→Location for owners.
2. **Extract:** the set of dependent flows, callers, and invariants the change
   reaches; the owners to notify.
3. **Guardrails:** a `◐` or `?` connection means the blast radius is **uncertain** —
   say so explicitly rather than implying completeness.
4. **Write back:** if you discover an undocumented dependency, add it to the
   concept's Connections.

<!-- GENERATED:registry START — do not edit; run framework/tools/generate.sh -->
### Concept & Flow Registry (generated)

| Kind | Name | Anchor | Status |
|---|---|---|---|
| flow | _<User-Visible Action>_ | _(what starts this — a button click, a network packet, a timer fires, etc.)_ | ✓ |
| flow | _<Next Action>_ | — | — |
<!-- GENERATED:registry END -->

## How This Index Stays True

This file is **derived** from `CONCEPTS.md`, `FLOWS.md`, and `HOW-TO.md`. It is
refreshed when those change — at Phase 6 (distillation) alongside `CLAUDE.md`, and
re-checked in Phase 7 (verification). If a row here points at a doc section that no
longer exists, this index has drifted; fix it before a consuming skill acts on it.

Run `tools/check-doc-drift.sh` (ideally in CI) to find which entries cite code that
changed, so re-verification targets exactly the rows at risk.
