# Core Concepts — ExecuTorch

> Source anchors `◐` verified against ExecuTorch `main @0d904b6bae60` (GitHub, 2026);
> anchors are `file → symbol`. Behavior not run here. Re-verify against your checkout.

---

## Concept: `BackendInterface` — the delegate/backend contract

**Doc type:** explanation (core abstraction + API)
**Audience:** anyone adding or debugging a hardware delegate
**You are assumed to know:** what a delegated subgraph is
**Before you begin:** read `OVERVIEW.md`
**Owner:** _(example instance — unowned)_
**Anchor:** `runtime/backend/interface.h → BackendInterface` (search `"class BackendInterface"`)
**Source verified against:** ExecuTorch `main @0d904b6bae60` ◐

### Concrete Example First

The XNNPACK / Core ML / **Qualcomm QNN** delegates each implement one class. AOT,
`preprocess()` compiles a tagged subgraph into a binary blob baked into the `.pte`; on device,
`init()` is handed that blob and `execute()` runs it. That AOT-blob → runtime-init/execute
handshake is the whole delegate contract.

### Plain-Language Explanation

A **backend (delegate)** runs a whole tagged subgraph on an accelerator. It has an **AOT
half** (compile to a blob) and a **runtime half** (load + run the blob).

### Key Interface

**Runtime half** (`runtime/backend/interface.h`):
| Method | Role |
|---|---|
| `is_available()` | Can this backend run on the current device? |
| `init(BackendInitContext&, FreeableBuffer* processed, ArrayRef<CompileSpec>)` | Receive the AOT blob (`processed`) → a `DelegateHandle` |
| `execute(BackendExecutionContext&, DelegateHandle*, Span<EValue*>)` | Run the delegated subgraph |
| `register_backend(const Backend&)` | Register the delegate by id |

**AOT half** (`exir`): `preprocess(edge_program, compile_specs)` compiles a tagged subgraph
into the binary blob that `init()` later receives.

### Why It Is Shaped This Way

1. **AOT/runtime split.** Heavy compilation runs on a host (`preprocess`), the device only
   does `init`+`execute` — so the on-device runtime stays tiny and dependency-light, the whole
   point of edge. ◐
2. **Opaque `processed` blob.** The runtime treats the backend's output as an opaque buffer →
   each accelerator owns its own compiled format without the core runtime knowing it. ◐

### The Invariant a Consuming Skill Must Not Break

**The AOT-produced blob and the runtime backend must agree on format and `backend_id`, and a
delegate must only claim subgraphs it can actually compile + run.** A subgraph tagged for a
backend whose `preprocess` fails (or whose runtime `init` can't read the blob) does **not**
fall back — it breaks the build/`.pte` or the device run. Non-delegated ops fall back to
portable kernels; *delegated* ops do not. ◐

### Connections
- **Pairs with:** `Partitioner` (below) — partition decides *what* a backend gets.
- **Related flow:** `FLOWS.md → "Lowering & delegation"` (the `to_backend`/`preprocess` step).

### Deviation Callout (for agent readers)
Unlike ONNX Runtime's CPU-EP fallback, a **delegated** subgraph has *no* runtime fallback in
ExecuTorch — partition/compile errors surface AOT or at load, not as a silent CPU re-run.

### Open Questions Raised
- ? Exact `CompileSpec` schema per backend and how version skew between the AOT blob and the
  runtime delegate is detected. Not traced here.

---

## Concept: `Partitioner` — tagging subgraphs for a backend

**Anchor:** `exir` → `Partitioner.partition()` (docs: `docs/source/compiler-delegate-and-partitioner.md`) · **Source verified:** `main @0d904b6bae60` ◐

A `Partitioner` subclass implements `partition()`, which **tags nodes** of the `EdgeProgram`
for a backend and returns a `PartitionResult`; `to_backend(backend_id, CompileSpec)` then
lowers each tagged subgraph by calling that backend's `preprocess()`.

- **Why separate from the backend:** the same backend can be driven by different partition
  policies (whole-model vs op-subset), and partition decisions are graph-level while
  compilation is backend-specific. ◐
- **Invariant:** only tag what the backend's `preprocess` can compile — over-tagging fails
  lowering (see the `BackendInterface` invariant). ◐
- **This is the "add a backend" axis**; the "add an operator" axis is the kernel registry
  (`EXECUTORCH_LIBRARY`) — see `API.md`.

### Connections
- **Pairs with:** `BackendInterface`. **Related flow:** `FLOWS.md` (partition step).

---

## Cross-Reference Index
| File / Path | Concept(s) |
|---|---|
| `runtime/backend/interface.h` | `BackendInterface` |
| `exir/` (`docs/source/compiler-delegate-and-partitioner.md`) | `Partitioner` |
| `kernels/`, `runtime/kernel/` | operator kernels (add-op axis) |
