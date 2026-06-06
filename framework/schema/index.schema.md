# Schema: INDEX.md (Consumer Entry Point)

**Schema version:** index/v1

`INDEX.md` is the machine-readable entry point a consuming skill reads first. This
file is the contract it may rely on. Stable within a major version; incompatible
changes bump the major version, declared in the `Index schema:` field of the
instance's `INDEX.md` header.

## Guaranteed structure

A conforming `INDEX.md` contains these sections, in this order:

1. **Header** — the standard doc header (`doc-header.schema.md`) plus
   `Index schema: vN`.
2. **Consumption Protocol** — the trust gates and re-verify rule.
3. **Knowledge Map** — the parseable tables below.
4. **Consumer Contract** — schema + safety boundaries.
5. **Task Recipes** — read / extract / guardrails / write-back per task.

## Parseable tables (the data contract)

| Table | Columns (in order) |
|---|---|
| Concepts | Concept, Anchor, Status, What breaks without it, Use when |
| Flows | Flow, Trigger, Error / early-exit branch, Status, Use when |
| Key Data Structures | Structure, Anchor, Invariants documented in |
| Task → Location | To change…, Look in, Owner |
| Invariants Registry | Invariant, Enforced / relied on at, Explained in, Status |
| Commands | Need, Command, Verified |

The **API & interface surface** (provided APIs / entry points, consumed interfaces,
feature→API map) is authored in `API.md`, not in `INDEX.md`. INDEX points to it
(single source of truth); a consuming skill that needs entry points reads `API.md`.

## Field rules

- **Anchor** — `path/to/file → SymbolName` plus `(search "<literal>")`. Never a bare
  line number; line numbers are not part of the contract.
- **Status** — exactly one tag from `tags.md` (`✓` / `◐` / `?`).
- **Links** — every Concepts/Flows row resolves to a section that exists in
  `CONCEPTS.md` / `FLOWS.md`. A dangling row is a contract violation.

## Authoring and coverage

The whole of `INDEX.md` — including the Knowledge Map tables — is **authored** and is
the single source of truth; no tool rewrites it. `tools/check-index.sh` *verifies*
coverage: it reads the `## Concept:` and `## Flow:` headings in `CONCEPTS.md` /
`FLOWS.md` and fails if any is missing from the Knowledge Map. A missing concept/flow
or a dangling row is a contract violation; fix it by editing `INDEX.md`.
