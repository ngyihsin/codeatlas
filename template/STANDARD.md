# What "Good" Looks Like: The Standard for Large-Codebase Documentation

> Read this **before** Phase 1 and re-read it **before Phase 6**. It defines the
> target. The other files tell you the *process*; this file tells you what the
> *output* must achieve to be worth keeping.
>
> The goal of this whole template is one document set good enough that a new hire,
> or a fresh AI session, can become productive in a large codebase without
> re-deriving everything from raw source. This file is the bar for "good enough".

## The Bar, in One Sentence

Professional documentation for a large codebase lets a competent newcomer answer
**"where does this behavior live, and why is it built this way?"** without reading
the whole source tree first.

Everything below is detail in service of that sentence.

## Why a Pile of Notes Is Not Documentation

Most onboarding notes fail the same way. They are a transcript of what one person
read, in the order they read it. They answer "what did I look at on Tuesday?" — a
question no future reader has.

Documentation answers the *reader's* questions, not the *author's* history. The
test is not "did I write down what I found?" It is "can someone who was not here
use this to get unstuck?" Write for the reader who arrives six months from now and
knows nothing.

## What the Best Codebases Actually Do

These four projects are among the largest and longest-lived open codebases in the
world. New contributors join them every week and become productive. Study how they
document, and steal the patterns.

| Project | Scale | Signature documentation artifact | What to steal |
|---|---|---|---|
| **Linux kernel** | ~30M+ lines, C | `Documentation/` tree (reStructuredText → Sphinx, published at docs.kernel.org); the `MAINTAINERS` file; deep single-topic docs like `memory-barriers.txt` | Layer docs by reader. Map every subsystem to an owner. Give the *hardest* concept its own long, careful document. |
| **Chromium** | ~30M+ lines, C++ | "Life of a Pixel" and "Life of a Navigation"; per-feature design docs; "Getting Around the Chromium Source Code"; `DEPS` layering rules | Trace one user-visible action end-to-end across processes. Write a design doc *per feature*, capturing the *why* and the rejected alternatives. Make module boundaries explicit and enforced. |
| **Firefox / Gecko** | ~20M+ lines, C++/Rust/JS | firefox-source-docs.mozilla.org (Sphinx); **Searchfox**, a fully cross-referenced code index | Pair prose with a way to jump straight to the code. Cross-reference relentlessly: every concept points at the symbols that embody it. |
| **Servo** | Large, Rust | Architecture docs describing the **constellation** (manages pipelines/browsing contexts), parallel layout, and the WebRender GPU renderer | Name and explain the few load-bearing abstractions a newcomer *must* know. Explain the unusual design choice (here, parallelism) explicitly, because the reader will not guess it. |

### The four lessons, distilled

1. **Linux → layer by reader, and assign ownership.** A doc with no owner rots.
   A doc that mixes "how to use" with "how to hack on it" serves neither reader.
2. **Chromium → the flow document is the highest-value artifact.** "Life of a
   Pixel" teaches more about Chromium than any module list. Our `FLOWS.md` exists
   to produce exactly this. Also: capture the *why*, including paths not taken.
3. **Gecko → documentation without code links is half a document.** Every claim
   must point at a `path:line`. Searchfox works because text and code are joined.
   Our verification tags and citation rule encode the same idea.
4. **Servo → name the load-bearing concepts, and explain the surprise.** A
   newcomer can learn a million lines of ordinary code on their own. They cannot
   guess the three abstractions and the one counterintuitive decision that the
   whole design rests on. Those are what `CONCEPTS.md` must capture.

## The Eight Traits of Professional Large-Codebase Documentation

A document set hits the bar when it has all eight. Each maps to a file in this
template, so "write good docs" becomes "fill these files to this standard".

| # | Trait | What it means | Delivered by |
|---|---|---|---|
| 1 | **A routing entry point** | One "start here" file that sends each reader to the right place. No reader has to guess. | `AGENT-warm-up.md`, `README.md` |
| 2 | **Positioning + a real map** | What the project is in one sentence, and where things live — measured, not guessed. | `OVERVIEW.md` |
| 3 | **The *why*, not just the what** | Invariants, module boundaries, and at least one rejected alternative per major decision. The reader learns *why* the lines are drawn where they are. | `CONCEPTS.md`, `OVERVIEW.md` notes |
| 4 | **At least one end-to-end flow** | One concrete user-visible action traced across every module and process it touches. The "Life of a Pixel" pattern. | `FLOWS.md` |
| 5 | **The hard concepts, deep** | The 3–7 abstractions a newcomer cannot guess, each explained from analogy down to code. Concurrency, IPC, and memory models get their own treatment. | `CONCEPTS.md` |
| 6 | **A task → location map** | "I need to change X — where do I look?" answered as a table. Plus ownership and dependency rules. | `CLAUDE.md`, `OVERVIEW.md` |
| 7 | **Provenance and drift control** | Every claim is anchored to a commit hash and re-verified on a schedule. The reader can trust it or check it. | Verification tags, Phase 7 |
| 8 | **Honest about its own gaps** | Verified knowledge is separated from guesses. What is *not* understood is written down, not hidden. | `✓ / ◐ / ?` tags, `OPEN-QUESTIONS.md` |

If a trait is missing, the document set is incomplete — no matter how many pages
it has. Length is not the measure. Coverage of these eight is.

## Maturity Levels: Grade Your Own Output

For each document, decide which level it is at. Aim for **L3** before calling a
document done. **L2** is the minimum to be useful to anyone but the author.

| Level | Name | Description |
|---|---|---|
| **L0** | Stub | Headers exist, content is placeholder. Useless to a reader. |
| **L1** | Transcript | Records what the author did, in author order. Useful only to the author. |
| **L2** | Useful | Answers a reader's question correctly, with citations and verification tags. A newcomer gets unstuck, but must still connect dots themselves. |
| **L3** | Professional | Reader-ordered, links concept ↔ flow ↔ code, captures the *why* and at least one rejected alternative, anchored to a commit, gaps named honestly. A newcomer becomes productive from it alone. |

### What L3 looks like, per key document

- **OVERVIEW.md (L3):** A newcomer reads it and can correctly predict which
  directory a given feature lives in, and name the project's two or three
  load-bearing subsystems — before opening any source file.
- **CONCEPTS.md (L3):** Each entry starts with an analogy, descends to a
  `path:line` walkthrough, links to the flow that exercises it, and states what
  the reader would misunderstand without it. A concept entry that cannot say
  "here is what breaks in your mental model without this" is not yet L3.
- **FLOWS.md (L3):** A reader can follow the traced action across every process
  boundary, knows which step uses IPC versus a direct call, and could set a
  breakpoint at any step from the citation alone. This is the "Life of a Pixel"
  bar.
- **CLAUDE.md (L3):** Under 200 lines, every line earns its place in *every*
  future session, and the task→location table answers the most common "where do I
  look" questions without a search.

## Definition of Done for the Whole Notes Directory

The directory is "professional" — not "finished", this is never finished — when
all of the following hold. This is the gate before a new hire's work is trusted by
the next reader.

- [ ] **OVERVIEW.md** is L3: one-sentence positioning, measured structural map,
      entry points, and the *why* behind the top-level split.
- [ ] **At least one FLOWS.md flow** is L3: a real user-visible action, traced
      end-to-end, with a rendered diagram and a citable call-chain table.
- [ ] **At least three CONCEPTS.md entries** are L3, including the single hardest
      concept in the codebase (usually concurrency, IPC, or the memory model).
- [ ] **CLAUDE.md** is ≤200 lines and every concept/flow it names actually exists
      in the detailed docs (no dangling pointers).
- [ ] **Every code claim** in CONCEPTS.md and FLOWS.md has a `path:line` citation
      and a `✓ / ◐ / ?` tag.
- [ ] **Every concept and flow entry** records `Last verified against commit:`.
- [ ] **OPEN-QUESTIONS.md** is non-empty and honest. A large codebase you claim to
      fully understand after a few sessions is a warning sign, not a triumph.
- [ ] **The continuity test passes:** a fresh reader, given only the entry point
      and the files it links, reaches the author's level without re-exploring from
      scratch. (See `HANDOFF.md` for the exact phrasing.)

## Amateur Tells: How to Spot Documentation That Will Not Help Anyone

If your draft does any of these, it is below the bar. Fix it before committing.

- **Narrates the author's journey.** "First I looked at X, then I found Y." The
  reader does not care what order you read files in. Re-order around *their*
  questions.
- **Lists files without saying why they matter.** A directory listing is not a
  map. A map says which directories are load-bearing and which are noise.
- **States what without why.** "The scheduler uses a red-black tree." Good — but
  *why* a red-black tree, and what breaks if you change it? The why is the part the
  reader could not have derived alone.
- **No code citations.** A claim about behavior with no `path:line` is a rumor.
  Searchfox and kernel-doc exist precisely to kill rumors.
- **No rejected alternatives.** Every real design chose A over B. A doc that never
  mentions B has not captured the actual decision, only its outcome.
- **Confident everywhere, uncertain nowhere.** Real understanding of a large
  codebase has edges. A doc with no `?` tags and an empty OPEN-QUESTIONS.md is
  hiding its gaps, not lacking them.
- **No provenance.** "This is how it works" — as of which commit? Code moves.
  Undated, unanchored claims are the first to become wrong while still sounding
  authoritative.

## How to Use This File

1. **Before Phase 1:** read it once so you know the target.
2. **During Phases 3–5:** when you draft a concept or flow, check it against the
   relevant L3 description above.
3. **Before Phase 6 and before any commit you call "done":** walk the *Definition
   of Done* checklist and the *Amateur Tells* list. Fix what fails.
4. **In review:** the human (ideally a non-native English reader, per
   `WRITING-STYLE.md`) grades each document L0–L3 and records it in
   `ONBOARD-CHECKLIST.md`.

This file defines *what good is*. `ONBOARD-GUIDE.md` defines *how to get there*.
`WRITING-STYLE.md` defines *how to write it clearly*. Read all three as one set.
