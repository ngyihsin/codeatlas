# Core Concepts — ONNX Runtime

> Source anchors `◐` verified against ORT `main @90c095d1e309` (GitHub, 2026); anchors are
> `file → symbol`. Re-verify against your checkout before acting.

---

## Concept: `IExecutionProvider` — the hardware backend interface

**Doc type:** explanation (core abstraction + API)
**Audience:** anyone adding or debugging a backend (EP), or wondering why a node ran on CPU
**You are assumed to know:** what a computation-graph node is
**Before you begin:** read `OVERVIEW.md`
**Owner:** _(example instance — unowned)_
**Anchor:** `include/onnxruntime/core/framework/execution_provider.h → IExecutionProvider` (search `"class IExecutionProvider"`)
**Source verified against:** ORT `main @90c095d1e309` ◐

### Concrete Example First

When you create a session with `providers=["QNNExecutionProvider","CPUExecutionProvider"]`,
ORT asks the QNN EP "which parts of this graph can you run?" (`GetCapability`), gives it
those sub-graphs to compile (`Compile`), and runs everything QNN declined on the CPU EP.
That negotiation is the whole job of `IExecutionProvider`.

### Plain-Language Explanation

An **Execution Provider (EP)** is a plug-in backend (CPU, CUDA, TensorRT, QNN, CoreML…).
The runtime owns the graph; each EP advertises what it can run and supplies the kernels.

### Key Interface (the methods you implement)

| Method | Role | Note |
|---|---|---|
| `GetCapability()` | Return the sub-graphs (`ComputeCapability`) this EP can run | EP *proposes*; it does **not** decide assignment |
| `Compile()` | Compile a fused node/sub-graph → `NodeComputeInfo` (create_state / compute / release_state) | For EPs that JIT/AOT-compile sub-graphs |
| `GetKernelRegistry()` | The EP's own `OpKernel` registry | For EPs that run op-by-op |

### Why It Is Shaped This Way

1. **The runtime owns partitioning, not the EP.** The header states it is *"ONNXRuntime's
   responsibility to do the partition and decide whether a node will be assigned to this
   execution provider."* **Why:** with N EPs of differing coverage and a priority order, only
   the runtime can resolve overlaps and guarantee a consistent assignment. ◐
   - *Consequence:* an EP that over-claims in `GetCapability` does not get to force
     assignment — but it can cause silent fallbacks elsewhere.
2. **Two execution styles via one interface.** `GetKernelRegistry` (op-by-op) and `Compile`
   (whole sub-graph) coexist, so both reference kernels and JIT/AOT accelerators fit. ◐

### The Invariant a Consuming Skill Must Not Break

**Every node must end up runnable, and the CPU EP is the guaranteed fallback.** If a new EP
claims a node in `GetCapability` but cannot actually produce a kernel/compiled blob, the node
neither falls back nor runs → session-init failure. So: *only claim in `GetCapability` what you
can truly execute.* The CPU EP must remain in the provider list as the safety net. ◐

### API Usage (worked example — selecting/falling back across EPs)

```python
import onnxruntime as ort
# Priority order: try QNN first, fall back to CPU for unclaimed nodes.
sess = ort.InferenceSession("model.onnx",
        providers=["QNNExecutionProvider", "CPUExecutionProvider"])
print(sess.get_providers())   # what actually got registered (verified-style call)
```

**Why shaped this way:** the list is a *priority order*; ORT calls each EP's `GetCapability`
in turn and assigns greedily, leaving the remainder to CPU. `get_providers()` reflects the
registered set (we ran this against `onnxruntime 1.26.0` and saw `['CPUExecutionProvider']`
when only CPU is available).

### Connections
- **Called by:** the partitioner during `InferenceSession` graph resolution (`core/framework`). ◐
- **Related concept:** the kernel registry (below) — how a node becomes a callable kernel.
- **Related flow:** `FLOWS.md → "Life of an inference"` (partition step).

### Deviation Callout (for agent readers)
`GetCapability` is a *proposal*, not a command. Reasoning that "my EP claimed the node so it
will run there" is wrong — the runtime may still assign elsewhere or fail; and claiming
without a real kernel breaks the run.

### Open Questions Raised
- ? Exact priority/greedy-assignment rules when two EPs claim overlapping sub-graphs. Not
  traced here.

---

## Concept: The kernel registry — turning a node into a callable `OpKernel`

**Anchor:** `onnxruntime/core/framework/kernel_registry_manager.h → KernelRegistryManager` (search `"class KernelRegistryManager"`) · **Source verified:** ORT `main @90c095d1e309` ◐

A node names an **op** (type + domain + opset version); a **kernel** is a concrete
implementation for an EP + data types. `KernelRegistryManager` resolves node → `OpKernel`.

- **Layered lookup:** custom (EP-type-specific) registries take priority over the common
  EP-type-specific registries. ◐
- **A kernel is keyed by** op type, domain, opset range, **EP type**, and type constraints —
  which is *why* the same op has separate CPU/CUDA/… kernels.
- **Adding an operator** = register a new `OpKernel` (built-in via the kernel-registration
  macros under `core/providers/<ep>/`, or external via a custom op — see `API.md`). This is a
  **different** extension point from adding an EP.
- **Invariant:** if no registry yields a kernel for an assigned node, session init fails with
  a "not implemented"/"kernel not found" error — the failure surfaced in `FLOWS.md`.

### Connections
- **Related concept:** `IExecutionProvider` (assignment happens before kernel resolution).
- **Related flow:** `FLOWS.md` (kernel-resolution step).

---

## Cross-Reference Index

| File / Path | Concept(s) |
|---|---|
| `core/framework/execution_provider.h` | `IExecutionProvider` |
| `core/framework/kernel_registry_manager.h` | kernel registry |
| `core/providers/cpu/` | reference kernels + fallback EP |
