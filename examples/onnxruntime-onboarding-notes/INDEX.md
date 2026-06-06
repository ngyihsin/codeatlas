# Knowledge Base Index — ONNX Runtime (Entry Point for Consuming Skills)

**Doc type:** reference (machine-readable routing + action contract)
**Audience:** an agent/skill doing a task on ONNX Runtime; humans wanting the map
**Before you begin:** none
**Owner:** _(example instance — unowned)_
**Source anchors verified against:** ORT `main @90c095d1e309` (GitHub, 2026) ◐
**Runtime verified against:** `onnxruntime` 1.26.0 (pip), 2026-06-06 ✓
**Index schema:** v1

> Illustrative reference instance. Source anchors `◐` (read); the inference flow is `✓`
> (run). Re-verify before acting. To *build* these notes you'd read `AGENT-warm-up.md`;
> this is the *consume* entry.

## Consumption Protocol (read before acting)
1. Route by task → a recipe below.
2. Trust gates: act on `✓`; re-verify `◐` against current code before editing; never act on `?`.
3. Re-verify anchors against your checkout/version (source: ORT main; runtime: 1.26.0).
4. Honor the invariants registry — a violation breaks the run even if a build succeeds.
5. Write back any correction with updated provenance.

## Knowledge Map

### Concepts
| Concept | Anchor | Status | What breaks without it | Use when |
|---|---|---|---|---|
| `IExecutionProvider` (backend interface) | `core/framework/execution_provider.h` → `IExecutionProvider` | ◐ | You think an EP decides assignment, or claim nodes you can't run | Adding/debugging a backend |
| kernel registry → `OpKernel` | `core/framework/kernel_registry_manager.h` → `KernelRegistryManager` | ◐ | You confuse "add an op" with "add a backend" | Adding an operator; "kernel not found" |

→ Detail: `CONCEPTS.md`

### Flows
| Flow | Trigger | Error / early-exit branch | Status | Use when |
|---|---|---|---|---|
| Life of an Inference | `session.run` | step 4: no kernel for an assigned node → session-init failure | ✓ behavior / ◐ chain | A wrong/failed result, or wrong EP |

→ Detail: `FLOWS.md`

### Key Data Structures
| Structure | Anchor | Invariants documented in |
|---|---|---|
| `IExecutionProvider` | `core/framework/execution_provider.h` | `CONCEPTS.md` → `IExecutionProvider` |
| `KernelRegistryManager` / `OpKernel` | `core/framework/kernel_registry_manager.h` | `CONCEPTS.md` → kernel registry |

### APIs, Entry Points & Interfaces
Provided surface (sessions, custom op, custom EP, optimization levels) and consumed
interfaces (protobuf, MLAS/Eigen, per-EP SDKs) are authored in **`API.md`** — single source
of truth. Process entry points: `OVERVIEW.md` → Entry Points.

### Task → Location Map
| To change… | Look in | Owner |
|---|---|---|
| Add an operator (kernel) | `core/providers/<ep>/` registration, or custom op (`API.md`) | — |
| Add a backend / accelerator | implement `core/framework/execution_provider.h` `IExecutionProvider` | — |
| Graph optimization passes | `core/optimizer/` (`GraphTransformer`) | — |
| Session orchestration | `core/session/inference_session.cc` | — |

### Invariants / Must-Not-Break Registry
| Invariant | Enforced / relied on at | Explained in | Status |
|---|---|---|---|
| ORT (not the EP) owns partitioning; `GetCapability` only *proposes* | `core/framework/execution_provider.h` → `GetCapability` | `CONCEPTS.md` → `IExecutionProvider` | ◐ |
| Only claim in `GetCapability` what you can actually run; else session-init fails | `core/framework` partitioner | `CONCEPTS.md` → `IExecutionProvider` | ◐ |
| CPU EP must stay in the provider list as the universal fallback | `core/providers/cpu/` | `OVERVIEW.md`, `FLOWS.md` | ✓ (ran on CPU) |
| Every assigned node must resolve to a kernel, or init fails | `core/framework/kernel_registry_manager.h` | `CONCEPTS.md` → kernel registry | ◐ |

### Commands
| Need | Command | Verified |
|---|---|---|
| Install + run | `pip install onnxruntime onnx numpy` then run a session | ✓ |
| List EPs | `python -c "import onnxruntime as o; print(o.get_available_providers())"` | ✓ |
| Build from source | `./build.sh --config Release --build_shared_lib --parallel` | ◐ (not run) |

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
| Edit code | Only on `✓` or re-verified `◐`; never on `?`. |
| Break an invariant | Escalate as a design change with the anchor as a named risk. |
| Before editing | Re-verify against ORT main / your version; code wins. |
| After editing | Write back: update the cited doc + provenance. |
| Push / PR | Not granted by this KB; follow the host project's rules. |

## Task Recipes

### Recipe: Add an Operator (kernel)
1. **Read:** `CONCEPTS.md → kernel registry`; a sibling kernel under `core/providers/cpu/`; or
   the custom-op API in `API.md`.
2. **Extract:** op type + domain + opset + dtype constraints + the EP type you target.
3. **Guardrails:** register for the right EP; keep CPU fallback working; don't claim it in an
   EP's `GetCapability` unless that EP truly implements it.
4. **Write back:** add a kernel/registry note + an INDEX row.

### Recipe: Add a Backend (Execution Provider)
1. **Read:** `CONCEPTS.md → IExecutionProvider`; `FLOWS.md` partition step; the invariants.
2. **Extract:** which sub-graphs you can run (`GetCapability`), op-by-op (`GetKernelRegistry`)
   vs whole-subgraph (`Compile`).
3. **Guardrails:** ORT owns assignment; only claim what you can execute; never remove CPU
   fallback.
4. **Write back:** document the new EP as a Concept + INDEX row + feature→API entry.

### Recipe: Fix a Bug / Ticket · Triage · Test-gen · Refactor · Impact
Same structure as the master `INDEX.md`. For ORT the load-bearing inputs are the **invariants
registry**, the **partition/kernel-resolution** steps of the flow, and **which EP** a node
landed on. Impact note: a change to `KernelRegistryManager` or `IExecutionProvider` reaches
*every* model run — maximum blast radius.

## How This Index Stays True
Derived from `CONCEPTS.md`, `FLOWS.md`, `HOW-TO.md`, `API.md`; refresh when they change. Run
`../../framework/tools/check-doc-drift.sh` against an ORT checkout to find rows citing changed
code; run `../../framework/tools/check-index.sh examples/onnxruntime-onboarding-notes` to
confirm coverage.
