# What "Good" Looks Like: The Standard for Large-Codebase Documentation

> Read this **before** Phase 1, **re-read it before Phase 6**, and **check each
> concept or flow against it as you draft** — quality is built in, not inspected at
> the end. The other files tell you the *process*; this file tells you what the
> *output* must achieve to be worth keeping.
>
> Three readers use these docs: **humans** (new hires), **authoring agents** (future
> onboarding sessions), and **consuming skills** (digital colleagues that read the
> docs to *do* a task — fix a bug, build a feature, write a design doc). Most rules
> serve all three. Where agents differ, see "Writing for Agent Readers"; where
> consuming skills differ, see "The Docs as a Knowledge Base for Other Skills." The
> goal is one document set good enough that any of them becomes productive without
> re-deriving everything from raw source.

## The Bar, in One Sentence

Professional documentation for a large codebase lets a competent newcomer answer
**"where does this behavior live, what shape is the data, and why is it built this
way?"** without reading the whole source tree first.

Everything below is detail in service of that sentence.

## Why a Pile of Notes Is Not Documentation

Most onboarding notes fail the same way. They are a transcript of what one person
read, in the order they read it. They answer "what did I look at on Tuesday?" — a
question no future reader has.

Documentation answers the *reader's* questions, not the *author's* history. The
test is not "did I write down what I found?" It is "can someone who was not here
use this to get unstuck?" Write for the reader who arrives six months from now and
knows nothing about this project.

## What the Best Codebases Actually Do

These four projects are among the largest and longest-lived open codebases in the
world. New contributors join them every week and become productive. Study how they
document, and steal the patterns.

**Caveat first:** these projects are exemplary in *specific named artifacts*, not
uniformly. Some of their docs are stale or abandoned. Revere the artifact below,
not the whole doc set.

| Project | Exemplary artifact | The transferable lesson |
|---|---|---|
| **Linux kernel** | `Documentation/` split into `admin-guide/`, `core-api/`, `process/`; the `MAINTAINERS` file | **Layer docs by reader, and assign an owner to every area.** A doc that mixes "how to use" with "how to hack on it" serves neither reader. A doc with no owner rots. |
| **Chromium** | "Life of a Pixel" / "Life of a Navigation" | **Choose one canonical path and omit aggressively.** Its power is not completeness — it picks *one* route through staggering complexity and ruthlessly drops the rest. Trace one user-visible action end-to-end; do not trace everything. |
| **Firefox / Gecko** | **Searchfox**, a fully cross-referenced code index | **Documentation without code links is half a document.** Every claim points at the symbol that embodies it. Searchfox works because text and code are joined. |
| **Servo** | Architecture docs for the **constellation**, parallel layout, WebRender | **Spend your words only on the non-obvious.** A newcomer can learn ordinary code alone. They cannot guess the few load-bearing abstractions, the key data structures, and the one surprising design choice the whole system rests on. Those are what to document. |

> Note on `memory-barriers.txt`: it is famous partly as a *cautionary* artifact —
> dense and hard. Do not treat it as the model. The Linux lesson to copy is the
> *layering*, not the density.

## Documents Come in Types — Know Which You Are Writing

A senior reviewer's first question is "what kind of document is this?" Mixing types
serves no one. The bar differs per type.

| Type | Job | Examples in this set | Its specific bar |
|---|---|---|---|
| **Explanation** | Build understanding; give the *why* | `CONCEPTS.md`, `FLOWS.md` | Captures the *why*; covers the unhappy path |
| **Reference** | Be exhaustive and skimmable; answer "where / what" | `OVERVIEW.md` map, CLAUDE.md "where to look" | Accurate, scannable, complete for its scope |
| **How-to (procedural)** | Get a named task done with copy-pasteable steps | **Common Tasks doc (see Trait 9)** | Steps work as written; no detours into *why* |

The "capture the *why* and a rejected alternative" rule below applies to
**explanation** docs. It does **not** apply to reference or how-to docs. A "how do
I run one test" doc that pauses to explain rejected alternatives is a *bad* doc.

## The Ten Traits of Professional Large-Codebase Documentation

A document set hits the bar when it has all ten. Each maps to a file in this
template, so "write good docs" becomes "fill these files to this standard."

| # | Trait | What it means | Delivered by |
|---|---|---|---|
| 1 | **Routing entry points** | One "start here" for authors (`AGENT-warm-up.md`) and one for consuming skills (`INDEX.md`). Each reader is routed, not left to guess. | `AGENT-warm-up.md`, `INDEX.md` |
| 2 | **Positioning + a real map** | What the project is in one sentence, and where things live — measured, not guessed. | `OVERVIEW.md` |
| 3 | **The *why*, where recoverable** | Invariants, module boundaries, and — *if recoverable from history, comments, or design docs* — the rejected alternative. If not recoverable, say so and mark it `?`. Never fabricate a rationale. | `CONCEPTS.md` |
| 4 | **At least one end-to-end flow** | One concrete user-visible action traced across every module and process it touches, including its primary error branch. | `FLOWS.md` |
| 5 | **The hard concepts and key data structures, deep** | The 3–7 abstractions and the load-bearing data structures a newcomer cannot guess, each explained from contract down to code, with a worked API example. See "Documenting a Major Subsystem." | `CONCEPTS.md` |
| 6 | **A task → location map** | "I need to change X — where do I look?" answered as a table. Plus ownership and dependency rules. | `CLAUDE.md`, `OVERVIEW.md` |
| 7 | **Provenance and drift control** | Every claim is anchored to a commit hash and re-verified on a schedule — ideally enforced by a CI check that flags when cited code changes. | Verification tags, Phase 7, `tools/check-doc-drift.sh` |
| 8 | **Honest about its own gaps** | Verified knowledge is separated from guesses. What is *not* understood is written down, not hidden. | `✓ / ◐ / ?` tags, `OPEN-QUESTIONS.md` |
| 9 | **A common-tasks how-to** | The 3–5 things a new hire does in week one — build, run, test, land a one-line change — as copy-pasteable steps with expected output. | `OVERVIEW.md` or a `HOW-TO.md` |
| 10 | **The API & interface surface** | What the codebase *exposes* (public APIs, CLI, endpoints, entry-point macros), what library interfaces it *consumes*, and which APIs power which features. The public surface is where a trace starts. | `API.md` |

If a trait is missing, the document set is incomplete — no matter how many pages it
has. Length is not the measure. Coverage of these ten is.

## Every Document Starts the Same Way

A reader (human or agent) who lands mid-document must know instantly whether it
applies to them and whether to trust it. Every generated doc opens with this header:

```
**Doc type:** explanation | reference | how-to
**Audience:** who this is for
**You are assumed to know:** the prerequisite knowledge
**Before you begin:** what must be working first (checkout, build), or "none"
**Owner:** who keeps this true and acts on drift
**Last verified against commit:** <short hash>   **Status:** ✓ / ◐ / ?
```

Provenance without ownership still rots. Name an owner, even if it is "the
onboarding team."

## Maturity Levels: Grade Your Own Output

For each document, decide which level it is at. Aim for **L3**. **L2** is the
minimum to be useful to anyone but the author.

| Level | Name | Description |
|---|---|---|
| **L0** | Stub | Headers exist, content is placeholder. Useless to a reader. |
| **L1** | Transcript | Records what the author did, in author order. Useful only to the author. |
| **L2** | Useful | Answers a reader's question correctly, with citations and verification tags. A newcomer gets unstuck, but must still connect dots themselves. |
| **L3** | Professional | Reader-ordered; declares audience and type; links concept ↔ data structure ↔ flow ↔ code; gives the *why* where recoverable; anchored and owned; gaps named honestly. A newcomer becomes productive from it alone. |

### What L3 looks like, per key document

- **OVERVIEW.md (L3):** A newcomer reads it and can correctly predict which
  directory a given feature lives in, and name the project's two or three
  load-bearing subsystems — before opening any source file.
- **CONCEPTS.md (L3):** Each entry leads with a concrete example, states the
  contract, documents the **key data structure** (fields, invariants, lifetime),
  explains **why it is shaped that way**, shows a **worked API call**, links to the
  flow that exercises it, and says what the reader would misunderstand without it.
  An entry for a central subsystem that lacks the data structure or a usage example
  caps at **L2**, never L3.
- **FLOWS.md (L3):** A reader can follow the traced action across every process
  boundary, knows which step uses IPC versus a direct call, sees the primary error
  branch, and could set a breakpoint at any step from the citation alone. This is
  the "Life of a Pixel" bar.
- **How-to (L3):** A new hire pastes the steps and they work, first try, on a clean
  checkout. Expected output is shown so they know it worked.
- **API.md (L3):** A reader can name the codebase's public entry points and start a
  trace from any of them, see which library interfaces each feature consumes, and go
  from a named feature to its starting symbol and flow without searching. An API doc
  that lists symbols but marks no entry points and maps no feature is not yet L3.
- **CLAUDE.md (L3):** Under 200 lines, every line earns its place in *every* future
  session, and the task→location table answers the most common "where do I look"
  questions without a search.

## Documenting a Major Subsystem: Data Structures and APIs

For a systems codebase, the **key data structures are the architecture.** You
cannot understand Linux without `task_struct`, Chromium without `WebContents`, or
Gecko without the frame tree. An explanation doc for a central subsystem must
include three parts:

1. **The key data structure(s).** A table of the fields that carry the design, with
   their invariants, ownership, lifetime, and concurrency rules. Not prose — a
   table a reader can scan.
2. **Why this shape.** Tie each structural choice to the constraint that forced it
   (memory, concurrency, performance, compatibility). Include the rejected
   alternative **only if recoverable**; otherwise mark it `?`.
3. **A worked API usage example.** Real calling code, with the non-obvious calls
   explained *by* the rationale above. The reader should see the design pay off in
   how the API must be called.

See `EXAMPLES.md` → "Documenting a Key Data Structure" for a full worked entry.

## Documenting APIs and Interfaces

The **interface surface** is where reading a codebase starts. The public API is the
set of front doors, so it is the best place to begin a trace; the libraries a codebase
consumes are where a trace leaves it. `API.md` captures both directions, plus the map
from features to the APIs that implement them.

Capture three things:

1. **The provided API surface** — what the codebase *exposes*: public
   functions/classes/headers, CLI commands, network/RPC endpoints, plugin and config
   interfaces, and any top-level entry-point macro or `main`. Mark each that is a good
   **entry point** for tracing and link it to its flow. A reader who knows the public
   surface can find any feature's starting line.
2. **The consumed library interfaces** — for each external dependency *and* major
   internal module boundary, the *slice* of its interface the code actually calls, and
   the wrapper/adapter where that call happens. This answers "what does this depend on,
   and where does a trace leave this codebase?" List only directly-used interfaces, not
   every transitive dependency.
3. **The feature → API map** — for each user-visible feature, the provided entry-point
   API, the key consumed interfaces it relies on, and the flow it triggers. This is the
   fast path from "I care about feature X" to "here is where it starts and what it
   touches."

Entry points, not exhaustiveness, are the goal: a newcomer needs the doors and the
dependency edges, not a generated list of every symbol. See `EXAMPLES.md` →
"Documenting the API & Interface Surface" for a worked entry.

## Writing for Agent Readers

A future AI session reads these docs to act, not just to learn. An agent retrieves
*fragments*, follows instructions literally, has no memory of this project, and will
confidently fill gaps from its training prior. Design for that:

1. **Self-contained chunks.** Every concept or flow entry must be usable in
   isolation. Restate its key identifier, define its terms, and never rely on "as
   mentioned above." An agent may retrieve only this one section.
2. **Stable anchors over line numbers.** Cite `file + symbol + search-string`, not
   just `:LINE`. Line numbers drift, and an agent acts on a stale one literally —
   editing the wrong code. Treat `:LINE` as a convenience to re-verify, never the
   source of truth.
3. **Machine-readable metadata.** The header block above lets an agent filter and
   route without parsing prose. Keep its fields consistent across all docs.
4. **Loud deviation callouts.** State where this project breaks from the common
   pattern the agent's prior expects ("this is an *intrusive* list, not a
   container-of-pointers list"). The agent guesses the common case otherwise.
5. **Guardrails as imperatives.** "NEVER edit `generated/`." "Walk this list ONLY
   under the lock." Agents follow explicit DO/DON'T well; rely on it.
6. **Error signatures.** Include the literal failure string and its meaning so an
   agent that hits it can self-correct. Agents string-match; humans infer.
7. **One canonical term per concept.** Do not call it "renderer" here and "content
   process" there. Agents match strings; inconsistent vocabulary breaks cross-links.

**The tension to manage:** single-source-of-truth (good for humans and maintenance)
versus self-contained chunks (good for agents). Resolve it by keeping the
*authoritative* statement in one place, but giving every retrievable chunk enough
local context — its key term, its anchor, its status tag — to be used safely alone.
Controlled redundancy of agent-critical facts is a deliberate exception to DRY.

## The Docs as a Knowledge Base for Other Skills

The output is not only read by people learning the code. Other skills — digital
colleagues dispatched to **fix a bug, build a feature, or write a design document** —
read it to ground their work in the real codebase and then **act on it**. Acting on
docs raises the bar: a doc that is pleasant to read but cannot be safely used to
change code has failed this reader.

To serve consuming skills, the document set must provide:

1. **One discoverable entry point: `INDEX.md`.** A machine-readable router a skill
   reads first — concepts, flows, data structures, task→location, and commands as
   parseable tables, each pointing at the detailed doc. `CLAUDE.md` is auto-loaded by
   the harness and points to it.
2. **Trust gates for action.** The `✓ / ◐ / ?` tags are not decoration; they decide
   what a skill may do. Act on `✓`; re-verify `◐` against current code before
   editing; **never act on `?`.**
3. **An invariants registry.** The must-not-break rules, each with an anchor and the
   concept that explains it. A change that violates an invariant is a bug even if the
   tests pass. This is the single most valuable thing you can give a skill that edits
   code.
4. **Task recipes.** For each job a digital colleague does — fix a bug, build a
   feature, write a design doc, review a change, respond to an incident, generate
   tests, refactor/migrate, explain to a human, analyze impact — what to read, what
   to extract, which guardrails to honor, and what to write back. (See `INDEX.md`.)
5. **A consumer contract.** A versioned schema so any skill parses `INDEX.md` the
   same way, plus safety boundaries: what a skill may read, edit, or escalate, and
   the rule to re-verify before acting and write back after. (See `INDEX.md` →
   "Consumer Contract".)
6. **A write-back loop and drift control.** When a consuming skill changes the code
   or learns something, it updates the cited doc and its provenance. A CI check
   (`tools/check-doc-drift.sh`) flags when a change touches cited code, so drift is
   caught at the source, not months later. A knowledge base only the authors
   maintain rots between sessions; consumers and automation keep it true.

The design-doc case is the bridge to `docforge`: these docs are **code →
understanding**; a design doc is **design → code**. A design skill reads the
concepts, flows, and invariants for the area it touches, cites them with anchors, and
flags any invariant the design would change as a named migration risk.

## Definition of Done for the Whole Notes Directory

The directory is "professional" — not "finished," this is never finished — when all
of the following hold. The first group checks that the artifacts exist; the second
checks that they actually *work* on a reader. Both matter; outcomes matter more.

**Artifacts present:**

- [ ] Every doc opens with the standard header (type, audience, prerequisites,
      owner, verified commit).
- [ ] **OVERVIEW.md** is L3: positioning, measured map, entry points, and the *why*
      behind the top-level split.
- [ ] **At least one FLOWS.md flow** is L3: a real action, traced end-to-end, with a
      rendered diagram, a citable call-chain table, and its primary error branch.
- [ ] **At least three CONCEPTS.md entries** are L3, including the single hardest
      concept and at least one **key data structure with a worked API example**.
- [ ] **A common-tasks how-to** exists and works on a clean checkout.
- [ ] **API.md** lists the provided entry points (with at least one linked to a flow)
      and the consumed library interfaces, and maps at least one feature to its API.
- [ ] **CLAUDE.md** is ≤200 lines and names no concept/flow that does not exist in
      the detailed docs.
- [ ] **Every code claim** has a stable anchor (`file + symbol`) and a `✓ / ◐ / ?`
      tag.
- [ ] **OPEN-QUESTIONS.md** is non-empty and honest.

**Outcomes verified (the real test):**

- [ ] **Continuity:** a fresh reader, given only the entry point and the files it
      links, reaches the author's level without re-exploring. (Necessary, not
      sufficient — it proves *transfer*, not *value*.)
- [ ] **Cold-start quiz:** a newcomer can answer 5 pre-agreed questions about the
      codebase using only the docs (e.g., "which directory owns navigation?",
      "what protects the task list during a walk?").
- [ ] **Time-to-first-change:** a new hire can build, run, and land a one-line
      change using only the how-to, without asking a human.
- [ ] **Actionability (for consuming skills):** given only `INDEX.md`, a skill can,
      for a sample issue, locate the code (`file + symbol`), name the invariant it
      must not break, and cite the relevant flow — without re-exploring the source.
- [ ] **Traceability:** given a named feature, a reader can find its entry-point API
      in `API.md` and start a trace from it without searching the source.

## Amateur Tells: How to Spot Documentation That Will Not Help Anyone

If your draft does any of these, it is below the bar. Fix it before committing.

- **Narrates the author's journey.** "First I looked at X, then Y." Re-order around
  the *reader's* questions, not your reading order.
- **Documents the verbs but not the nouns.** Traces flows but never explains the
  load-bearing data structures the flows move through.
- **Hides the front doors.** Explains internals but never names the public API surface
  a reader would trace *from*, or the library interfaces the code depends on.
- **Lists files without saying why they matter.** A directory listing is not a map.
- **States what without why** (in an explanation doc). "Uses a red-black tree" —
  but *why*, and what breaks if you change it?
- **Fabricates a rationale or a rejected alternative.** If the *why* is not
  recoverable from the code or its history, say so. An invented reason is worse than
  an honest gap.
- **No code anchors.** A claim about behavior with no `file + symbol` is a rumor.
- **Confident everywhere, uncertain nowhere.** No `?` tags and an empty
  OPEN-QUESTIONS.md means gaps are hidden, not absent.
- **No provenance.** "This is how it works" — as of which commit?
- **A linear narrative that only works read in order.** It breaks the moment an
  agent retrieves one section. Make chunks self-contained.
- **Re-derives what upstream already documents well.** Link to "Life of a Pixel";
  do not regenerate it.
- **Too long.** Burying the answer or re-explaining derivable code is below the bar
  too — not only stubs. This is the most common failure of an AI author.
- **Readable but not actionable.** A skill can understand the doc but cannot safely
  change code from it — no invariants flagged, no anchors to act on, no trust tags.
  Understanding is necessary; for a knowledge base it is not sufficient.

## How to Use This File

1. **Before Phase 1:** read it once so you know the target.
2. **While drafting (Phases 3–5):** check each concept or flow against the relevant
   L3 description *as you write it*. Build quality in.
3. **Before Phase 6 and before any commit you call "done":** walk the *Definition of
   Done* checklist and the *Amateur Tells* list. Fix what fails.
4. **In review:** the human (ideally a non-native English reader, per
   `WRITING-STYLE.md`) grades each document L0–L3 and records it in
   `ONBOARD-CHECKLIST.md`.

This file defines *what good is*. `ONBOARD-GUIDE.md` defines *how to get there*.
`WRITING-STYLE.md` defines *how to write it clearly*. Read all three as one set.
