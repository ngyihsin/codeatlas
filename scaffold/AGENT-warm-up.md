# AGENT Warm-Up

**You are about to help a human understand a large, unfamiliar codebase.**

Read this file at the start of EVERY session. It is the single bootstrap file.

## Project Identity

- **Project name**: <PROJECT_NAME>
- **Codebase path**: <CODEBASE_PATH>
- **Primary language(s)**: <LANGUAGES>
- **Notes directory**: this directory (where you found this file)
- **Framework cache**: `.docforge/framework/` (read-only; pinned to `template_version` in `HANDOFF.md`)

> Replace the three angle-bracket placeholders above when you first set up this template, then leave them alone. The notes directory is self-referential and needs no edit.

> **File roles:** you write the *authored* docs (`OVERVIEW`, `CONCEPTS`, `FLOWS`, `HOW-TO`, `OPEN-QUESTIONS`, the curated `CLAUDE.md`, and `INDEX.md`); `tools/check-index.sh` verifies `INDEX.md` covers every concept and flow; the framework docs (`STANDARD.md`, `ONBOARD-GUIDE.md`, `WRITING-STYLE.md`, `AGENT-PROTOCOL.md`) are read-only in `.docforge/framework/`. See `MANIFEST.md` and `GOVERNANCE.md`.

> For monorepos with multiple distinct subprojects, create one notes directory per subproject. See `EXAMPLES.md` → "Monorepo with Multiple Codebases".

## Session Bootstrap Sequence

Execute these steps in order. Do not skip.

### Step 1: Determine Session Type

Read the **state block** at the top of `HANDOFF.md`. It is an HTML comment with this shape:

```
<!-- DOCFORGE-ONBOARD STATE
state: pre-bootstrap | onboarding | continuing
phase1_complete: true | false
last_session: <integer>
last_session_date: YYYY-MM-DD
last_verified_commit: <short-hash> | —
-->
```

Route by the `state` field:

- `pre-bootstrap` → This is the **first-ever session**. Go to Step 2A.
- `onboarding` → Onboarding has started but Phase 1 is not complete. Go to Step 2A and resume the in-progress phase.
- `continuing` → Phase 1 is complete. Go to Step 2B.

If the state block is missing or malformed, treat it as `pre-bootstrap` and tell the user the block must be repaired before the next session.

### Step 2A: First-Time or In-Progress Onboarding

1. Read `STANDARD.md` — this defines what "good" output looks like. It is the target every doc you write must hit.
2. Read `ONBOARD-GUIDE.md` in full — this is the process for reaching that target.
3. Read `WRITING-STYLE.md` — every doc you write must follow these rules.
4. Tell the user: "I see this is the first onboarding session. I'll walk through the phases in ONBOARD-GUIDE.md, aiming for the quality bar in STANDARD.md. We start with Phase 1: Ignorance Scan, which is code-free."
5. Begin Phase 1. **Stop after each phase and wait for the user.**
6. At session end: set `state: onboarding` in the HANDOFF.md state block. When Phase 1 completes, set `phase1_complete: true`. When Phase 6 produces the first CLAUDE.md, set `state: continuing`.

### Step 2B: Continuing Session

1. Read these files in order, briefly:
   - `CLAUDE.md` — distilled context (this is your "always-on" memory)
   - `HANDOFF.md` — what was done last session and what is next
   - `ONBOARD-CHECKLIST.md` — what is complete vs. pending
   - `OPEN-QUESTIONS.md` — outstanding mysteries
2. Summarize for the user in 3-5 bullets:
   - What is already understood (high level)
   - What is pending in the checklist
   - What HANDOFF.md suggests doing next
   - Top 1-2 open questions (if any)
3. Ask: "Do you want to (a) continue with the suggested next step in HANDOFF, (b) tackle a specific concept or flow, or (c) re-verify drifted docs (Phase 7)?"
4. **Wait for the user.** Do not start work until they choose.

## Behavioral Rules (Always)

The canonical rules live in the framework: `AGENT-PROTOCOL.md` (in an instance,
`.docforge/framework/AGENT-PROTOCOL.md`). Read it once per onboarding. In short:

1. **Code is truth** — when code and a doc disagree, the code wins.
2. **Tag every claim** ✓ / ◐ / ? (same rule for diagrams) — vocabulary in
   `schema/tags.md`.
3. **Cite a stable anchor** `file → symbol`, not a bare line number.
4. **Respect file roles** — write the *authored* files (including `CLAUDE.md` and
   `INDEX.md`); run `tools/check-index.sh` to confirm `INDEX.md` coverage; never edit
   the framework cache. See `MANIFEST.md`.
5. **Never capture secrets**, write for a global audience, render diagrams before
   committing, and stop between phases.

For the full text of every rule, see `AGENT-PROTOCOL.md`.

## What Success Looks Like

A new session, given only `AGENT-warm-up.md` and the docs it points to, can reach the
same operational understanding the user has — within one session. The full definition
of "good" lives in `STANDARD.md`; grade every doc against it.

---

**Now: execute Step 1 above.**
