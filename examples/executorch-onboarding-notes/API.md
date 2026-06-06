# APIs & Interfaces — ExecuTorch

**Doc type:** reference (interface surface + feature map)
**Audience:** a developer adding a delegate, adding an operator, or lowering a model
**You are assumed to know:** the lowering flow (`FLOWS.md`)
**Before you begin:** read `OVERVIEW.md`
**Owner:** _(example instance — unowned)_
**Source anchors verified against:** ExecuTorch `main @0d904b6bae60` (GitHub, 2026) ◐
**Behavior:** not run here ◐

> Anchors are `file → symbol`. Process entry points are in `OVERVIEW.md`; this is the
> *callable* surface + extension points.

## Provided API Surface (what ExecuTorch exposes)

| API / Symbol | Kind | Anchor | Stability | Entry point? | Purpose |
|---|---|---|---|---|---|
| `to_edge(...)` | Python AOT | `exir → to_edge` | public | **yes** | ExportedProgram → EdgeProgram |
| `to_backend(backend_id, CompileSpec)` | Python AOT | `exir → to_backend` | public | **yes** (delegate) | Lower tagged subgraphs to a backend |
| `to_executorch()` | Python AOT | `exir → to_executorch` | public | yes | Memory-plan + emit `.pte` |
| `Partitioner.partition()` | Python extension pt | `exir` (docs: compiler-delegate-and-partitioner.md) | extension | yes (add backend) | Tag subgraphs for a backend |
| `BackendInterface` | C++ runtime iface | `runtime/backend/interface.h → BackendInterface` | extension | yes (add backend) | Runtime half of a delegate |
| `EXECUTORCH_LIBRARY(...)` | C++ macro | `docs/source/kernel-library-custom-aten-kernel.md` | extension | yes (add op) | Register a custom kernel |
| `Method::execute` | C++ runtime | `runtime/executor → Method::execute` | public | yes | Run a `.pte` Method on device |

## Consumed Interfaces (libraries & internal modules)

| Library / Module | Interface used | Wrapped / adapted at | Why / for what |
|---|---|---|---|
| PyTorch (`torch.export`) | ExportedProgram / ATen ops | `exir/` | The AOT source program |
| Accelerator SDKs (XNNPACK, Core ML, **QNN**, Vulkan) | device compile/run APIs | `backends/<name>/` | One delegate adapts one accelerator |
| FlatBuffers | `.pte` serialization | program emitter | Self-contained model artifact |
| internal: partition → backend | `Partitioner.partition` → `preprocess` | `exir` | Tag then compile subgraphs |
| internal: runtime → delegate | `BackendInterface::init`/`execute` | `runtime/backend/interface.h` | Run delegated subgraphs from the blob |

## Feature → API Map

| Feature | Provided entry-point API | Key consumed interfaces | Flow |
|---|---|---|---|
| Lower a model for a device | `to_edge` → `to_backend` → `to_executorch` | partitioner + backend `preprocess` | → `FLOWS.md` ◐ |
| **Add a backend (delegate)** | `Partitioner` + `BackendInterface` (`preprocess`/`init`/`execute`) | accelerator SDK | (partition + preprocess steps) |
| **Add an operator (kernel)** | `EXECUTORCH_LIBRARY` (or YAML + `gen_selected_ops`) | runtime kernel registry | (kernel dispatch) |
| Run on device | `Method::execute` | the `.pte` + delegates | (runtime steps) |

## API Stability & Versioning
The **`.pte` artifact + the runtime ABI** are the stability contract a device depends on; the
**AOT lowering API and the backend/kernel extension points** evolve across releases (so
out-of-tree delegates/kernels must track the ExecuTorch version they build against). The AOT
toolchain ships as `executorch` on PyPI (1.3.1 latest at time of writing; **not run here** —
it pulls full PyTorch).
