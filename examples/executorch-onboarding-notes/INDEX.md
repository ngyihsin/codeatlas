# Knowledge Base Index — ExecuTorch (Entry Point for Consuming Skills)

**Doc type:** reference (machine-readable routing + action contract)
**Audience:** an agent/skill doing a task on ExecuTorch; humans wanting the map
**Before you begin:** none
**Owner:** _(example instance — unowned)_
**Source anchors verified against:** ExecuTorch `main @0d904b6bae60` (GitHub, 2026) ◐
**Behavior:** not run here ◐
**Index schema:** v1

> Illustrative reference instance. All rows `◐` (source-read; not run — pip pulls full
> PyTorch). Re-verify before acting. To *build* these notes you'd read `AGENT-warm-up.md`;
> this is the *consume* entry.

## Consumption Protocol (read before acting)
1. Route by task → a recipe below.
2. Trust gates: act on `✓`; re-verify `◐` against current code before editing; never act on `?`.
   (Here everything is `◐` — re-verify against your checkout/version.)
3. Honor the invariants registry — a violation breaks lowering or device load.
4. Write back any correction with updated provenance.

## Knowledge Map

### Concepts
| Concept | Anchor | Status | What breaks without it | Use when |
|---|---|---|---|---|
| `BackendInterface` (delegate contract) | `runtime/backend/interface.h` → `BackendInterface` | ◐ | You expect a delegated op to fall back to CPU (it doesn't) | Adding/debugging a delegate |
| `Partitioner` (tag subgraphs) | `exir` → `Partitioner.partition` | ◐ | You over-tag and lowering fails | Choosing what a backend runs |

→ Detail: `CONCEPTS.md`

### Flows
| Flow | Trigger | Error / early-exit branch | Status | Use when |
|---|---|---|---|---|
| Lowering & delegation (`to_edge`→`to_backend`→`.pte`) | lower a model AOT | step 3: backend `preprocess` can't compile a tagged subgraph (AOT failure) | ◐ | A subgraph not delegated, or a `.pte` that won't run |

→ Detail: `FLOWS.md`

### Key Data Structures
| Structure | Anchor | Invariants documented in |
|---|---|---|
| `BackendInterface` | `runtime/backend/interface.h` | `CONCEPTS.md` → `BackendInterface` |
| `Partitioner` / `PartitionResult` | `exir` | `CONCEPTS.md` → `Partitioner` |

### APIs, Entry Points & Interfaces
AOT (`to_edge`/`to_backend`/`to_executorch`), runtime (`Method::execute`), and the add-op
(`EXECUTORCH_LIBRARY`) / add-backend (`Partitioner`+`BackendInterface`) extension points are
in **`API.md`** — single source of truth.

### Task → Location Map
| To change… | Look in | Owner |
|---|---|---|
| Add an operator (kernel) | `kernels/`, `EXECUTORCH_LIBRARY` | — |
| Add a backend (delegate) | `backends/<name>/` + `runtime/backend/interface.h` | — |
| Lowering / partition | `exir/` | — |
| On-device execution | `runtime/executor/` | — |

### Invariants / Must-Not-Break Registry
| Invariant | Enforced / relied on at | Explained in | Status |
|---|---|---|---|
| A delegate only tags/claims subgraphs it can `preprocess` + run; else AOT/load fails | `exir` partition + backend `preprocess` | `CONCEPTS.md` → `Partitioner` | ◐ |
| Delegated subgraphs have **no runtime CPU fallback** (only non-delegated ops do) | `runtime/backend/interface.h` | `CONCEPTS.md`, `FLOWS.md` | ◐ |
| AOT blob format + `backend_id` must match the runtime delegate | `BackendInterface::init` | `CONCEPTS.md` → `BackendInterface` | ◐ |
| Selective build: required ops must be registered or the runtime can't run the `.pte` | `runtime/kernel/`, `EXECUTORCH_LIBRARY` | `OVERVIEW.md` | ◐ |

### Commands
| Need | Command | Verified |
|---|---|---|
| Install AOT toolchain | `pip install executorch` (pulls PyTorch) | ◐ not run |
| Lower a model | `to_edge(...).to_backend(...).to_executorch()` | ◐ |
| Run `.pte` | C++ runtime / `Method::execute` | ◐ |

→ Full procedures: `HOW-TO.md`

## Consumer Contract
### Schema
Anchors are `path → Symbol (search "…")`, never line numbers. Status is one of `✓ / ◐ / ?`.
Concepts/Flows rows resolve to sections that exist. Invariants rows are rule + anchor +
explaining doc + status.

### Safety Boundaries
| Action | Rule |
|---|---|
| Read | Always allowed. |
| Edit code | Only on `✓` or re-verified `◐`; never on `?`. Here all rows are `◐` → re-verify first. |
| Break an invariant | Escalate as a design change with the anchor as a named risk. |
| Before editing | Re-verify against ExecuTorch main / your version; code wins. |
| After editing | Write back: update the cited doc + provenance. |
| Push / PR | Not granted by this KB; follow the host project's rules. |

## Task Recipes

### Recipe: Add a Backend (Delegate)
1. **Read:** `CONCEPTS.md → BackendInterface` and `Partitioner`; `FLOWS.md`; the invariants.
2. **Extract:** which subgraphs to tag (`partition`), what `preprocess` emits, and the runtime
   `init`/`execute` contract.
3. **Guardrails:** only tag what you can compile + run; match blob format + `backend_id`;
   remember there is no CPU fallback for delegated ops.
4. **Write back:** document the new delegate as a Concept + INDEX row + feature→API entry.

### Recipe: Add an Operator (kernel)
1. **Read:** `API.md` (`EXECUTORCH_LIBRARY`); `OVERVIEW.md` (selective build).
2. **Extract:** op schema + the kernel function; whether it's in the model's selected ops.
3. **Guardrails:** register it (selective build will omit unlisted ops → runtime can't run).
4. **Write back:** add a kernel note + INDEX row.

### Recipe: Fix a Bug / Ticket · Triage · Test-gen · Refactor · Impact
Same structure as the master `INDEX.md`. For ExecuTorch the load-bearing inputs are the
**invariants registry**, the **AOT lowering/partition** steps, and **whether the failure is AOT
or on-device**. Impact note: a change to `BackendInterface` or the partition API reaches every
delegate and every `.pte` — maximum blast radius.

## How This Index Stays True
Derived from `CONCEPTS.md`, `FLOWS.md`, `HOW-TO.md`, `API.md`; refresh when they change. Run
`../../framework/tools/check-index.sh examples/executorch-onboarding-notes` to confirm coverage.
