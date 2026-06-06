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

1. Create a notes **instance** from the scaffold, inside or beside your codebase:

   ```
   cp -r docforge-onboard/scaffold my-codebase-notes
   ```

2. Add the **framework** as a pinned, read-only dependency of the instance:

   ```
   docforge-onboard/framework/tools/update-framework.sh my-codebase-notes
   ```

   This populates `my-codebase-notes/.docforge/framework/` and records the version.
   You reference the framework — you never copy-and-edit it. See `GOVERNANCE.md`.

3. Open `my-codebase-notes/AGENT-warm-up.md` and fill in the three placeholders: project name, codebase path, primary languages.

4. Start a conversation with your AI agent:

   > "Read my-codebase-notes/AGENT-warm-up.md"

5. The agent reads the framework (`STANDARD.md`, `ONBOARD-GUIDE.md`) from the cache and walks you through structured exploration, starting with human-written docs (no code yet).

**This is the same step you repeat every session.** `AGENT-warm-up.md` is the single bootstrap file. To use the finished notes to *do* work (fix a bug, build a feature, write a design doc), a skill instead starts at `INDEX.md`.

> **Two readers, two entry points.** The *authoring* agent enters at `AGENT-warm-up.md`; a *consuming* skill enters at `INDEX.md`. See `GOVERNANCE.md` for how the framework, the instance, and their update flows are kept separate.

## What's in the Repo

The repository separates the **framework** (the versioned methodology you depend on)
from the **scaffold** (the blank fill-in files an instance starts from). See
`GOVERNANCE.md` for the full model.

```
docforge-onboard/                 # the framework repo (this repo)
  CHANGELOG.md                    # framework history (SemVer + migration notes)
  GOVERNANCE.md  CONTRIBUTING.md  # the two change-control flows; how to contribute

  framework/                      # versioned, READ-ONLY methodology (the dependency)
    VERSION                       # framework version (travels with the cache)
    STANDARD.md                   # what "good" looks like + exemplars (Linux, Chromium, Gecko, Servo)
    ONBOARD-GUIDE.md              # the phase-by-phase process
    WRITING-STYLE.md              # writing rules for human + agent readers
    AGENT-PROTOCOL.md             # canonical behavioral rules for the authoring agent
    EXAMPLES.md                   # illustrative fragments
    MANIFEST.md                   # the file-role taxonomy (framework / authored / state)
    schema/                       # versioned contracts: index, doc-header, tags
    tools/                        # check-index.sh, update-framework.sh, check-doc-drift.sh

  scaffold/                       # blank fill-in starting point for an instance
    AGENT-warm-up.md              # session entry point
    OVERVIEW.md CONCEPTS.md FLOWS.md HOW-TO.md OPEN-QUESTIONS.md   # authored sources
    CLAUDE.md                     # curated lean per-session index (authored)
    INDEX.md                      # consumer entry point (authored; coverage checked by check-index.sh)
    HANDOFF.md  ONBOARD-CHECKLIST.md   # state (HANDOFF pins template_version)
    README.md                     # the instance's own readme
    logs/SESSION-LOG-TEMPLATE.md

  examples/                       # filled L3 reference instances (Redis, pybind11)
```

A **created instance** (a copy of `scaffold/`) additionally gets a
`.docforge/framework/` cache — a read-only copy of the framework at the pinned
version, populated by `update-framework.sh`. You edit the authored files (nothing is
machine-generated); `check-index.sh` verifies `INDEX.md` stays complete; you never
hand-edit the cache. Roles are listed in `framework/MANIFEST.md`.

## Worked Reference Instances

The blank templates show the *structure*; the `examples/` directory shows the *bar* —
complete, filled note sets for real codebases at the **L3 ("professional")** level.
Each has an `OVERVIEW`, a data-structure `CONCEPTS` entry (with the *why* and a worked
API call), a `FLOWS` trace (with its error branch), a `HOW-TO`, a lean `CLAUDE.md`,
and a consumer `INDEX.md` with an invariants registry and task recipes.

| Instance | Codebase | Stack | Shows |
|---|---|---|---|
| `examples/redis-onboarding-notes/` | Redis | C, `make` | A pure C systems codebase; incremental rehashing; "Life of a `GET`" |
| `examples/pybind11-onboarding-notes/` | pybind11 | C++ + Python, **CMake** | A polyglot header-only library; type casters across the C++/Python boundary; the GIL and ABI invariants |

Both are illustrative: authored from knowledge of each project, so every claim is
tagged `◐` and every anchor is `file → symbol` rather than a line number. Read them to
see what "good" looks like before filling the templates on your own codebase.

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
| **STANDARD.md** | The quality bar: what "good" looks like, exemplars, maturity rubric | Read-only reference (not filled) |
| **INDEX.md** | Entry point for consuming skills: machine-readable map, invariants registry, task recipes | Phase 6, refreshed with the docs |
| **OVERVIEW.md** | What the project is, top-level structure | Phase 1-2 |
| **CONCEPTS.md** | Core abstractions and embodying files | Phase 3-4, ongoing |
| **FLOWS.md** | Concrete call chains | Phase 5, ongoing |
| **HOW-TO.md** | Common first-week tasks, as copy-pasteable steps | After Phase 1-2, kept working |
| **CLAUDE.md** | Per-session boot context (≤200 lines) | Phase 6, revised continuously |
| **HANDOFF.md** | Current state, next target, verified-vs-speculative | Every session |
| **OPEN-QUESTIONS.md** | What we don't yet understand | Every session |
| **ONBOARD-CHECKLIST.md** | Phase / topic completion tracking | Continuously |
| **AGENT-warm-up.md** | Session entry point | Once at setup |
| **ONBOARD-GUIDE.md** | Detailed phase instructions | Reference only |

## What Professional Large-Codebase Documentation Is

Before generating anything, know the target. The goal is not "notes" — it is
documentation good enough that a new hire becomes productive without re-reading
the whole source tree. `framework/STANDARD.md` defines this bar in full, drawing on
how the largest open codebases actually document themselves:

- **Linux kernel** — a `Documentation/` tree layered by reader, a `MAINTAINERS`
  file mapping every subsystem to an owner, and deep single-topic docs for the
  hardest concepts. *Lesson: layer by reader, assign ownership, go deep on the
  hard thing.*
- **Chromium** — "Life of a Pixel" and "Life of a Navigation" trace one
  user-visible action across the whole multi-process stack; per-feature design
  docs capture the *why* and the rejected alternatives. *Lesson: the end-to-end
  flow document is the highest-value artifact.*
- **Firefox / Gecko** — Sphinx docs paired with **Searchfox**, a fully
  cross-referenced code index. *Lesson: documentation without code links is half a
  document.*
- **Servo** — architecture docs that name the few load-bearing abstractions (the
  constellation, parallel layout, WebRender) a newcomer cannot guess. *Lesson:
  name the load-bearing concepts and explain the surprising design choice.*

`STANDARD.md` turns these into nine required traits, a maturity rubric (L0 stub →
L3 professional) for grading each document, and a definition of done measured by
*outcomes* (can a new hire build, answer cold questions, and land a change from the
docs alone?). It also covers two things easy to miss: **documenting the key data
structures** of a subsystem — their fields, *why* they are shaped that way, and a
worked API example, because in a systems codebase the data structures *are* the
architecture — and **writing for agent readers**, since these docs are re-read by
future AI sessions that retrieve fragments, follow instructions literally, and need
stable anchors instead of drift-prone line numbers. It also treats the output as a
**knowledge base other skills act on**: a digital colleague dispatched to fix a bug,
build a feature, or write a design document reads `INDEX.md` — a machine-readable
map with an invariants registry and task recipes — to ground its work in the real
codebase and know what is safe to change. **Read it before Phase 1, re-read it
before Phase 6, and check each doc against it as you draft.** The phases below are
how you get there; the standard is how you know you arrived.

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

Run `wc -l CLAUDE.md` before committing. If it is over 200 lines, cut.

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

Notes will be read by developers who use English as a second language and by AI agents across sessions. Follow `framework/WRITING-STYLE.md`: short sentences, no idioms, mermaid diagrams for flows, a human technical-writer review before any doc is considered stable.

## Differences from docforge

If you've used docforge, the differences in spirit:

- **No SPEC.md.** The spec was decided by the original authors years ago. Your job is to recover it from code, not write it.
- **No DESIGN.md as a forward-looking doc.** CONCEPTS.md describes design as it exists, not design you're proposing.
- **HANDOFF.md tracks understanding, not implementation progress.**
- **OPEN-QUESTIONS.md is a first-class document.** docforge has open questions as a section; here it's a standalone file because mysteries are central to onboarding.
- **Verification phase exists.** Code drift is the dominant failure mode; you need an explicit step to catch it.

## License

MIT. See [LICENSE](LICENSE). Same spirit as docforge: copy it, fork it, make it yours.
