<!-- DOCFORGE-ONBOARD STATE
state: pre-bootstrap
phase1_complete: false
last_session: 0
last_session_date: —
last_verified_commit: —
template_version: 0.1.0
-->

# Handoff

> Updated **at the end of every session**. The next session reads this immediately after `AGENT-warm-up.md`.

**Continuity test:** *"Could a fresh AI agent, reading only `AGENT-warm-up.md` → `CLAUDE.md` → `HANDOFF.md` → `ONBOARD-CHECKLIST.md` → `OPEN-QUESTIONS.md`, pick up where we left off without asking clarifying questions?"*

If not, fix the docs.

## How the State Block Works

The HTML comment at the top of this file is the **authoritative session-state signal**. The agent reads it in Step 1 of `AGENT-warm-up.md`.

- `state` — one of `pre-bootstrap`, `onboarding`, `continuing`
- `phase1_complete` — `true` after Phase 1 finishes
- `last_session` — integer, increments each session
- `last_session_date` — `YYYY-MM-DD`
- `last_verified_commit` — short hash of the codebase commit at last Phase 7 verification, or `—`
- `template_version` — the framework version this instance is pinned to (see `framework/VERSION` / `CHANGELOG.md`). Bump it only when you run `update-framework.sh` and complete the migration notes.

Update the block at the end of every session. Do not delete it.

---

## Current Understanding State

> What we know, at a high level. Update sparingly — most state lives in CONCEPTS.md and FLOWS.md.

- ✅ **Solid:**
  - _(e.g., overall architecture, top-level directory map)_
- 🟡 **Partial:**
  - _(e.g., understand network stack but not its threading model)_
- ⬜ **Untouched:**
  - _(e.g., GPU subsystem, IPC serialization details)_

## Last Session Summary

> **Pre-bootstrap state:** before the first session, leave this section as-is. The first session that reads this file will see "no prior session" and start Phase 1 from `ONBOARD-GUIDE.md`.

- **Date:** _(YYYY-MM-DD — empty before session 1)_
- **Session number:** _(e.g., 5 — `0` before session 1)_
- **Goal:** _(what we set out to do)_
- **Done:** _(what we actually accomplished)_
- **Discoveries:**
  - _(non-obvious things found, especially surprises)_
- **Updates made to docs:**
  - `CONCEPTS.md` → added Concept #3 deep dive
  - `OPEN-QUESTIONS.md` → +Q7, -Q4 (resolved)
  - _(etc.)_

Full log: `logs/YYYY-MM-DD-session-NN-<slug>.md`

## Suggested Next Step

The agent's recommendation for what to tackle next session, with rationale.

**Recommendation:** _(e.g., "Phase 4 deep dive on Concept #4 (Mojo IPC) — it's referenced by both FLOWS Flow #1 and Concept #2, but we still mark it as ?")_

**Why:** _(why this is the highest-value next step)_

**Estimated effort:** _(e.g., one session)_

## Alternatives the User Might Choose

If the user prefers a different direction, here are reasonable alternatives:

- **Re-verification (Phase 7).** Last verification was N weeks ago; upstream has had M commits in tracked files.
- **Trace another flow (Phase 5).** Candidates: _(list)_.
- **Tackle a specific subsystem.** Candidates: _(list)_.

## Open Questions Snapshot

The top 3 from OPEN-QUESTIONS.md, for quick reference:

1. _(Q-id)_ — short summary
2. _(Q-id)_ — short summary
3. _(Q-id)_ — short summary

See OPEN-QUESTIONS.md for the full list.

## Verification Status

- **Last full verification (Phase 7):** _(date or "never")_
- **Codebase commit at last verification:** _(hash or "—")_
- **Files marked drift-suspected:** _(count)_
- **Re-verification recommended after:** _(date)_

## Recent Session Logs

The 5 most recent only. When adding a sixth row, drop the oldest. Older logs remain in `logs/` as files; do not summarize them here.

| Date | Slug | Phase / Focus |
|---|---|---|
| | | |
| | | |
| | | |
| | | |
| | | |
