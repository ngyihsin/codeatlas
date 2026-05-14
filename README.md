# Docforge-Onboard

A doc-driven **codebase onboarding** template for AI-assisted understanding of large existing projects.

This is a sibling project to [docforge](https://github.com/ThinkerYzu/docforge). Where docforge helps you start a new project from scratch, docforge-onboard helps an AI agent (and you) systematically understand a large, unfamiliar codebase — like Chromium, the Linux kernel, a game engine, or any legacy codebase you just inherited.

## Why a Separate Template?

| | docforge | docforge-onboard |
|---|---|---|
| Scenario | New project from scratch | Existing project, understand current state |
| Doc direction | Design → Implementation | Code → Understanding |
| Source of truth | Docs (code follows) | Code (docs describe) |
| Main risk | Implementation drifts from design | Docs go stale as code changes |

Both share the same architecture: a single warm-up entry point, phased progression, HANDOFF.md for session continuity, and per-session logs. Only the document semantics differ.

## Quick Start

1. Copy the template into your target codebase (or a sibling directory):

   ```
   cp -r docforge-onboard/template my-codebase-notes
   ```

2. Open `my-codebase-notes/AGENT-warm-up.md` and fill in the three placeholders: project name, codebase path, primary languages.

3. Start a conversation with your AI agent:

   > "Read my-codebase-notes/AGENT-warm-up.md"

4. The agent detects `ONBOARD-GUIDE.md` and walks you through structured codebase exploration, starting with reading human-written docs (no code yet).

**This is the same step you repeat every session.** `AGENT-warm-up.md` is the single bootstrap file — on the first session it triggers onboarding; on subsequent sessions it loads accumulated understanding and points to `HANDOFF.md` for current state and next exploration target.

## What's in the Template

```
template/
  AGENT-warm-up.md            # Agent reads this at the start of every session
  ONBOARD-GUIDE.md            # Step-by-step exploration phases (kept, not deleted)
  ONBOARD-CHECKLIST.md        # Tracks which phases / topics have been completed
  OVERVIEW.md                 # What the project is, top-level structure (Phase 1-2)
  CONCEPTS.md                 # Core abstractions and which files embody them (Phase 3-4)
  FLOWS.md                    # Important call chains and user-visible flows (Phase 5)
  CLAUDE.md                   # Distilled context for every session (Phase 6, ~200 lines)
  HANDOFF.md                  # Current understanding state, next exploration target
  OPEN-QUESTIONS.md           # Things not yet understood, with confidence levels
  WRITING-STYLE.md            # Writing rules for non-native readers + diagrams
  EXAMPLES.md                 # Illustrative examples (Chromium, monorepos, forks)
  README.md                   # This file (in template form, project-specific)
  logs/
    SESSION-LOG-TEMPLATE.md   # Format for each session log
```

## How the Process Works

The onboarding follows six phases. Unlike docforge, **understanding is never "complete"** — phases can be revisited, and the checklist tracks ongoing progress rather than a one-shot init.

### Phase 1 — Ignorance Scan (No Code)

Read only what humans wrote for humans: README, CONTRIBUTING, ARCHITECTURE, docs/, build configs. Answer four questions:

- One-sentence project positioning
- What problem it solves, for whom
- Languages, frameworks, target platforms
- Where the entry points are

Output: First draft of **OVERVIEW.md**.

### Phase 2 — Structural Map (No Explanation)

List first-level directories with one-sentence descriptions. Mark the largest, the smallest-but-critical, and the skippable (third_party, vendor). Output: Map section in **OVERVIEW.md**.

### Phase 3 — Reverse Recommendation

The agent — based on what it has seen so far — proposes the 5 most important concepts you should learn next, ranked. For each: why it matters, what you will misunderstand if you skip it, which file embodies it. Output: First entries in **CONCEPTS.md**.

### Phase 4 — Deep Dive Per Concept

For each concept the user picks: explain with everyday analogy first (no code), then point to 1-2 files, walk through 20-30 key lines. Agent ends with "what's confusing?" and waits. Output: Detailed entries in **CONCEPTS.md**, new questions in **OPEN-QUESTIONS.md**.

### Phase 5 — Trace a Concrete Flow

Pick a user-visible behavior ("press reload", "open new tab"). Trace the full call chain across modules using sub-agent / Explore mode. Don't paste full files — only file paths, line numbers, key function names. Output: **FLOWS.md**.

### Phase 6 — Distill into CLAUDE.md

Produce a ≤200-line CLAUDE.md as an **index, not an encyclopedia**. Only "if you don't know this you'll misread the project" content. Cross-link to OVERVIEW, CONCEPTS, FLOWS, OPEN-QUESTIONS for detail.

### Phase 7 — Verification (Recurring)

For each file path referenced in CONCEPTS.md / FLOWS.md, check `git log` since last verification. Mark drifted entries for re-verification. Move resolved questions out of OPEN-QUESTIONS, demote stale "verified" entries back to "speculation".

## Session Continuity

Every session starts the same way: the agent reads `AGENT-warm-up.md`. It serves as the bootstrap regardless of session number.

1. **Agent reads `AGENT-warm-up.md`** — gets project title, codebase path, workflow.
2. **First session:** Detects `ONBOARD-GUIDE.md` → starts Phase 1.
3. **Later sessions:** Loads CLAUDE.md (always), reads HANDOFF.md for state, picks up from where last session left off based on ONBOARD-CHECKLIST.md and OPEN-QUESTIONS.md.

The continuity test: *"Could a fresh AI session, given only AGENT-warm-up.md, reach the same level of understanding I have right now within one session?"*

If yes, your docs are honest. If no, something didn't get distilled.

## Document Roles at a Glance

| Document | Role | When Filled |
|---|---|---|
| **OVERVIEW.md** | What the project is, top-level structure | Phase 1-2 |
| **CONCEPTS.md** | Core abstractions and embodying files | Phase 3-4, ongoing |
| **FLOWS.md** | Concrete call chains | Phase 5, ongoing |
| **CLAUDE.md** | Per-session boot context (≤200 lines) | Phase 6, revised continuously |
| **HANDOFF.md** | Current state, next target, verified-vs-speculative | Every session |
| **OPEN-QUESTIONS.md** | What we don't yet understand | Every session |
| **ONBOARD-CHECKLIST.md** | Phase / topic completion tracking | Continuously |
| **AGENT-warm-up.md** | Session entry point | Once at setup |
| **ONBOARD-GUIDE.md** | Detailed phase instructions | Reference only |

## Suggested Methodology

### Read Human Docs First, Code Later

Do not start with `grep`. Phase 1 is deliberately code-free. The agent reads README, docs/, design notes — anything humans wrote to explain the project. Code without context is a maze; human docs are the legend.

### Let the Agent Reverse-Recommend

The hardest part of onboarding an unfamiliar codebase is **knowing what to ask**. You don't know the vocabulary yet. Phase 3 inverts the problem: the agent, based on what it has seen, tells *you* what concepts to learn next. This breaks the circular dependency of "I don't know what I don't know."

### Separate Verified from Speculated

Every claim in CONCEPTS.md / FLOWS.md should be tagged:
- ✓ **Verified**: read the code AND ran/debugged it OR confirmed via authoritative doc
- ◐ **Read-only**: read the code or doc but didn't run/test
- ? **Speculation**: inferred from context, not confirmed

Without this discipline, docs that *sound* confident slowly fill with claims that are wrong but read as authoritative.

### Treat Code as Truth, Docs as a Summary

When code and docs disagree, code wins. The only exception is when the doc is itself part of the contract (for example, an RFC or a public API spec). This is the opposite of docforge. Update OPEN-QUESTIONS.md every time you spot a divergence.

### One Session, One Concept (Or One Flow)

Don't try to understand everything in one session. Pick one concept (Phase 4) or one flow (Phase 5). Going deep on one thing teaches more than going shallow on five.

### Keep CLAUDE.md Lean

CLAUDE.md goes into every session's context window. Every line costs tokens. Resist the urge to dump everything into it. The rule: if the AI could find this information by reading another doc when needed, it does not belong in CLAUDE.md. Only "things that change interpretation of everything else" go in.

Run `wc -l template/CLAUDE.md` before committing. If it is over 200 lines, cut.

### Verify Periodically

Code moves. Run Phase 7 (verification) at least every few weeks, or after the upstream codebase has had significant commits. A doc that says "Verified against commit abc1234" is honest; a doc with no provenance is a liability.

### Open Questions Are Features, Not Bugs

A long OPEN-QUESTIONS.md is a sign of intellectual honesty, not failure. The goal is not to empty it — the goal is to know what's in it. Mysterious code is mysterious; pretending otherwise is how teams ship bugs.

## Tips

- **Start with the smallest readable thing.** Even in Chromium, find a small standalone library or component first. Build confidence before tackling the core.
- **Use sub-agents for exploration.** Don't fill the main conversation with raw file dumps. Spawn an Explore / sub-agent task that returns a summary.
- **Add infrastructure early.** ripgrep, [tokei](https://github.com/XAMPPRocky/tokei) or [cloc](https://github.com/AlDanial/cloc) for size measurement, clangd (for C/C++), tree-sitter, language server MCP — these multiply the agent's effectiveness more than any prompt tuning.
- **Trust git blame.** When code looks unusual, the commit message often explains why. Make it a habit.
- **Don't delete ONBOARD-GUIDE.md.** Unlike docforge's INIT-GUIDE, this stays — you will re-run phases as the codebase evolves or you tackle new subsystems.

## Writing for a Global Audience

Notes will be read by developers who use English as a second language and by AI agents across sessions. Follow `template/WRITING-STYLE.md`: short sentences, no idioms, mermaid diagrams for flows, a human technical-writer review before any doc is considered stable.

## Differences from docforge

If you've used docforge, the differences in spirit:

- **No SPEC.md.** The spec was decided by the original authors years ago. Your job is to recover it from code, not write it.
- **No DESIGN.md as a forward-looking doc.** CONCEPTS.md describes design as it exists, not design you're proposing.
- **HANDOFF.md tracks understanding, not implementation progress.**
- **OPEN-QUESTIONS.md is a first-class document.** docforge has open questions as a section; here it's a standalone file because mysteries are central to onboarding.
- **Verification phase exists.** Code drift is the dominant failure mode; you need an explicit step to catch it.

## License

MIT. See [LICENSE](LICENSE). Same spirit as docforge: copy it, fork it, make it yours.
