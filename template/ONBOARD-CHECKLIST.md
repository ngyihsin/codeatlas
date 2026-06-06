# Onboarding Checklist

Tracks which phases of `ONBOARD-GUIDE.md` are complete, and which concepts / flows have been deep-dived.

Update this file at the end of every session.

## Phase Status

| Phase | Status | Date Completed | Notes |
|---|---|---|---|
| 1. Ignorance Scan | ☐ Not started | — | — |
| 2. Structural Map | ☐ Not started | — | — |
| 3. Reverse Recommendation | ☐ Not started | — | — |
| 4. Deep Dive (per concept) | ☐ Ongoing | — | See concept table below |
| 5. Trace a Flow (per flow) | ☐ Ongoing | — | See flow table below |
| 6. Distill CLAUDE.md | ☐ Not started | — | — |
| 7. Verification | ☐ Never run | — | Re-run periodically |

Status legend: ☐ Not started, 🟡 In progress, ✅ Complete, 🔁 Needs re-run (drift suspected)

## Concepts Deep-Dived (Phase 4)

`Tech writer reviewed` is set after a human (ideally one for whom English is not the first language) has read the entry. The agent's first pass does not count. See `WRITING-STYLE.md`.

`Level` is the maturity grade from `STANDARD.md` (L0 stub → L3 professional). Aim for L3; L2 is the minimum to be useful to anyone but the author.

| # | Concept | Status | Tag | Level | Last Reviewed | Tech writer reviewed |
|---|---|---|---|---|---|---|
| 1 | (filled in Phase 3) | ☐ | — | L0 | — | ☐ |
| 2 | | ☐ | — | L0 | — | ☐ |
| 3 | | ☐ | — | L0 | — | ☐ |
| 4 | | ☐ | — | L0 | — | ☐ |
| 5 | | ☐ | — | L0 | — | ☐ |

Add rows as you discover more concepts to learn.

## Flows Traced (Phase 5)

| # | Flow | Status | Tag | Level | Last Reviewed | Tech writer reviewed |
|---|---|---|---|---|---|---|
| 1 | | ☐ | — | L0 | — | ☐ |
| 2 | | ☐ | — | L0 | — | ☐ |
| 3 | | ☐ | — | L0 | — | ☐ |

Add rows as more flows become relevant.

## Verification History (Phase 7)

| Date | Commit Hash Anchored | Drift Found | Notes |
|---|---|---|---|
| — | — | — | First verification not yet run |

## Subsystems Tackled

Some codebases are too large to onboard whole. Track which subsystems have been onboarded.

| Subsystem / Path | Phases Completed | Status |
|---|---|---|
| (whole repo, top level) | — | — |
| | | |

For a worked example (Chromium subsystem tracking), see `EXAMPLES.md` → "Chromium Subsystems Tracker".

## Definition of Done Gate

The notes directory is "professional" — never "finished" — when these all hold. This mirrors `STANDARD.md` → "Definition of Done for the Whole Notes Directory". Walk it before declaring Phase 6 done or handing the docs to a new reader.

**Artifacts present:**

- [ ] Every doc opens with the standard header (type, audience, prerequisites, owner, verified commit)
- [ ] OVERVIEW.md is L3 (positioning + measured map + entry points + the *why* of the top-level split)
- [ ] At least one FLOWS.md flow is L3 (real action, end-to-end, rendered diagram, citable call-chain table, primary error branch)
- [ ] At least three CONCEPTS.md entries are L3, including the single hardest concept and at least one **key data structure with a worked API example**
- [ ] A common-tasks how-to exists and works on a clean checkout
- [ ] CLAUDE.md is ≤200 lines and names no concept/flow that does not exist in the detailed docs
- [ ] Every code claim has a stable anchor (`file + symbol`) and a `✓ / ◐ / ?` tag
- [ ] Every concept and flow entry records `Last verified against commit:`
- [ ] OPEN-QUESTIONS.md is non-empty and honest

**Outcomes verified (the real test):**

- [ ] Continuity test passes (see `HANDOFF.md`) — proves transfer, not value
- [ ] Cold-start quiz: a newcomer answers 5 pre-agreed questions using only the docs
- [ ] Time-to-first-change: a new hire builds, runs, and lands a one-line change using only the how-to
