# Schema: Verification Tags and Maturity Levels

**Schema version:** tags/v1

The shared vocabulary every doc and every consuming skill relies on. Stable within a
major version.

## Verification tags

Applied to every code claim, prose or diagram.

| Tag | Name | Meaning | A consuming skill may… |
|---|---|---|---|
| `✓` | Verified | Read the code AND confirmed by running, debugging, or an authoritative doc | act on it |
| `◐` | Read-only | Read but not executed or tested | act only after re-verifying against current code |
| `?` | Speculation | Inferred, not confirmed | **not** act on it; treat as an open question |

Default to `?` when unsure.

## Maturity levels

Applied to each document (graded in `ONBOARD-CHECKLIST.md`).

| Level | Name | Meaning |
|---|---|---|
| `L0` | Stub | Headers exist, content is placeholder |
| `L1` | Transcript | Records what the author did, in author order |
| `L2` | Useful | Answers a reader's question with citations and tags; minimum to be useful |
| `L3` | Professional | Reader-ordered, linked, anchored, owned, gaps named; a newcomer is productive from it alone |

Full definitions and per-document L3 criteria: `STANDARD.md`.
