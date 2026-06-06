# Agent Protocol — Canonical Behavioral Rules

The rules an authoring agent follows across all phases and sessions. This is the
**single source of truth**; `scaffold/AGENT-warm-up.md` and `CLAUDE.md` point here
rather than duplicating it. It is a **framework** file — read-only in an instance
(`.docforge/framework/AGENT-PROTOCOL.md`).

## Code as Truth

When the code and a document disagree, the code wins. Update the document. Do not
ignore the discrepancy. Add an entry to `OPEN-QUESTIONS.md` if the cause of the
divergence is unclear.

## Verification Tagging

Every claim you write into `CONCEPTS.md` or `FLOWS.md` must be tagged:

- ✓ **Verified** — read the code AND confirmed by running, debugging, or an
  authoritative doc
- ◐ **Read-only** — read but not executed or tested
- ? **Speculation** — inferred, not confirmed

Default to ? if unsure. It is far better to mark something as speculation than to
claim verification you did not perform. This rule applies to **diagrams as well as
prose**. The vocabulary is the versioned contract in `schema/tags.md`.

## Cite a Stable Anchor for Every Code Claim

Any claim about how the code works must reference `file → symbol (search "…")`. Prefer
a stable anchor over a bare line number — line numbers drift, and an agent acts on a
stale one literally. Without an anchor, it is speculation.

## Use Sub-Agents for Exploration

Do not dump large files into the main conversation. When you need to read 5+ files or
a long file, spawn a sub-agent or Explore task and have it return a summary with
anchors. The main conversation stays focused.

## Don't Assume the User Knows Project Vocabulary

If you use a project-specific term (a class name, a subsystem, a domain concept),
explain it the first time in this session, even if it appears in `CLAUDE.md`.

## Render Diagrams Before Committing

Mermaid fails silently on syntax errors. Before saving a doc with a new mermaid block,
paste the source into [mermaid.live](https://mermaid.live) or run `mmdc` locally.

## Write for a Global Audience

Notes are read by developers using English as a second language and by future AI
sessions. Follow `WRITING-STYLE.md`: short sentences, no idioms, define every term on
first use, prefer a mermaid diagram over a long prose explanation.

## What NOT to Capture

The notes directory may be committed to git or shared with another AI session. Do not
write any of the following into any file:

- API keys, tokens, passwords, certificates
- Internal hostnames or URLs that are not public
- Customer names, employee names, or any personally identifying information
- Vendor contract terms, license keys, or pricing information

If you see something sensitive in the code, do not copy it. Reference its location and
describe it in general terms.

## Respect the File Roles

Edit **authored** files by hand; rebuild **generated** files (`CLAUDE.md`, `INDEX.md`)
with `tools/generate.sh`; never hand-edit the framework cache. See `MANIFEST.md`.

## Update Docs at Session End

Before ending a session, update:

1. `HANDOFF.md` — current state, next step, **and the DOCFORGE-ONBOARD STATE block**
2. `ONBOARD-CHECKLIST.md` — tick off what was completed
3. `OPEN-QUESTIONS.md` — add new mysteries, resolve solved ones
4. `logs/YYYY-MM-DD-session-NN-<slug>.md` — full session log
5. Re-run `tools/generate.sh` if concepts or flows changed (rebuilds `CLAUDE.md` /
   `INDEX.md`)

## Stop and Wait

Phases are interactive. Do not run multiple phases in a single agent turn. After each
phase, summarize what was produced and ask the user how to proceed.

## What This Project Is NOT

- Not a place to write new design proposals (this is for understanding, not designing).
- Not a wiki to record every detail. `CLAUDE.md` must stay lean.
- Not a one-shot task. Understanding is ongoing; the checklist tracks progress.

## What Success Looks Like

A new session, given only `AGENT-warm-up.md` and the docs it points to, can reach the
same operational understanding the user has — within one session, without re-exploring
the codebase. If a new session would have to start over, the docs failed; fix them.

The full definition of "good" lives in `STANDARD.md`. Grade every doc against it
before calling it complete.
