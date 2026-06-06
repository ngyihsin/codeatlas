# Flows — ONNX Runtime

> Source anchors `◐` (ORT `main @90c095d1e309`); the observable behavior of this flow was
> run-verified `✓` against `onnxruntime 1.26.0`. Anchors are `file → symbol`.

---

## Flow: Life of an Inference (`session.run`)

**Doc type:** explanation (traced flow)
**Audience:** a developer debugging why a node ran on a given EP, or a wrong/failed result
**Before you begin:** read `CONCEPTS.md → IExecutionProvider`
**Owner:** _(example instance — unowned)_
**Trigger:** an app calls `InferenceSession.run(outputs, feeds)` (or the C API `OrtApi::Run`)
**Source verified against:** ORT `main @90c095d1e309` ◐
**Behavior verified against:** `onnxruntime` 1.26.0 (pip), 2026-06-06 ✓ — built a tiny `Add`
model and ran it: `Add([2,3],[4,5]) → [6,8]` on `CPUExecutionProvider`.

> One canonical path: a session that is already initialized runs one inference. The required
> error/early-exit branch is "no kernel for an assigned node".

### In one line

ORT loads + optimizes + partitions the graph at **session init**, then `run()` executes the
assigned kernels in order, routing each node to its EP and falling back to CPU.

### Sequence Diagram

```mermaid
sequenceDiagram
    participant App
    participant Sess as InferenceSession
    participant Opt as GraphTransformer passes
    participant Part as Partitioner
    participant EP as ExecutionProvider(s)
    participant KR as KernelRegistryManager
    participant Exec as Executor

    App->>Sess: create(model, providers=[...])  (init)
    Sess->>Opt: apply optimizations (level)
    Sess->>Part: partition graph
    Part->>EP: GetCapability(graph)
    EP-->>Part: ComputeCapability (claimed subgraphs)
    Part->>Sess: assign nodes (unclaimed → CPU EP)
    Sess->>KR: resolve OpKernel per node
    App->>Sess: run(outputs, feeds)
    Sess->>Exec: execute assigned kernels in order
    Exec-->>App: output tensors
```

**Diagram verification:** ◐ source-read for the call chain; the end-to-end *result* is ✓ run.

### Call Chain

| # | Anchor (file → symbol) | What happens | Verification |
|---|---|---|---|
| 1 | `core/session/inference_session.cc → InferenceSession::Initialize` | Load model (protobuf) into the in-memory graph | ◐ |
| 2 | `core/optimizer/graph_transformer.h → GraphTransformer` (apply) | Run optimization passes per session level | ◐ |
| 3 | `core/framework → partitioner` (uses `IExecutionProvider::GetCapability`) | Each EP proposes sub-graphs; ORT assigns | ◐ |
| 4 | `core/framework/kernel_registry_manager.h → KernelRegistryManager` | Resolve each assigned node → `OpKernel` | ◐ |
| 5 | `core/session/inference_session.cc → InferenceSession::Run` | Execute kernels in topological order | ✓ behavior (ran `Add`) |
| 6 | `core/providers/cpu/...` (the `Add` kernel) | Compute on CPU EP | ✓ behavior (`[6,8]`) |

### Cross-Module / Boundaries
| Step → Step | Boundary | Mechanism |
|---|---|---|
| 3 | runtime ↔ EP | `IExecutionProvider::GetCapability` (EP proposes, ORT decides) |
| 3 → 4 | partition → kernels | assigned EP type selects which registry yields the kernel |
| 5 → 6 | executor → accelerator | for `Compile` EPs, a fused `NodeComputeInfo`; for op-by-op EPs, an `OpKernel` |

Most cost is paid **once at init** (steps 1–4); `run()` (5–6) is the hot path.

### Primary Error / Early-Exit Branch (required for L3)
- **Where it diverges:** step 4 — an assigned node has **no kernel** in any registry for its
  EP type / type constraints / opset.
- **What triggers it:** an unsupported op, an unsupported dtype, or an EP that claimed a node
  in `GetCapability` but has no real kernel.
- **Literal error signal:** session creation fails with a "kernel not found" / "not
  implemented for the current execution provider" style error (Fatal at init, not at `run`).
- **The benign branch (verified):** a node no accelerator EP claims simply **falls back to the
  CPU EP** and runs — which is why a model still runs end-to-end. (Our `Add` ran on CPU.)

### Related Concepts
- `CONCEPTS.md → IExecutionProvider` (step 3) and the kernel registry (step 4).

### Notes
- **Partition/optimize happen at init, not per run** — a surprising-but-important cost model:
  first session creation is slow; `run()` is fast.
