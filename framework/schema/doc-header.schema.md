# Schema: Document Header

**Schema version:** doc-header/v1

Every authored and generated document opens with this header so any reader — human or
agent — knows instantly whether it applies and whether to trust it. Stable within a
major version.

## Fields

```
**Doc type:** explanation | reference | how-to
**Audience:** who this is for
**You are assumed to know:** the prerequisite knowledge
**Before you begin:** what must be working first (checkout, build), or "none"
**Owner:** who keeps this true and acts on drift
**Last verified against commit:** <short hash>   **Status:** ✓ / ◐ / ?
```

| Field | Required | Notes |
|---|---|---|
| `Doc type` | yes | one of `explanation`, `reference`, `how-to` (see `STANDARD.md`) |
| `Audience` | yes | the single reader the doc is scoped to |
| `You are assumed to know` | yes | the curse-of-knowledge guard |
| `Before you begin` | yes | prerequisites, or the literal word `none` |
| `Owner` | yes | a person or team; enforced via `CODEOWNERS` in the host repo |
| `Last verified against commit` | yes | provenance for drift checks |
| `Status` | yes | a tag from `tags.md` |

`INDEX.md` additionally carries an `Index schema:` line (see `index.schema.md`). All
instance docs are authored; none carry a "generated" banner.
