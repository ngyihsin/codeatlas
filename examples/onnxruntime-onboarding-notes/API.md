# APIs & Interfaces — ONNX Runtime

**Doc type:** reference (interface surface + feature map)
**Audience:** a developer adding an op, adding a backend, or embedding ORT
**You are assumed to know:** the inference flow (`FLOWS.md`)
**Before you begin:** read `OVERVIEW.md`
**Owner:** _(example instance — unowned)_
**Source anchors verified against:** ORT `main @90c095d1e309` (GitHub, 2026) ◐
**Runtime verified against:** `onnxruntime` 1.26.0 (pip), 2026-06-06 ✓

> Anchors are `file → symbol`. Process/binary entry points (the session) are in
> `OVERVIEW.md` → Entry Points; this doc covers the *callable* surface and extension points.

## Provided API Surface (what ONNX Runtime exposes)

| API / Symbol | Kind | Anchor | Stability | Entry point? | Purpose |
|---|---|---|---|---|---|
| `InferenceSession` / `.run()` | Python API | `onnxruntime` pip module | public | **yes** ✓ run | Load + run a model |
| `OrtApi` (C API) | C ABI | `include/onnxruntime/core/session/onnxruntime_c_api.h → OrtApi` | public, stable ABI | yes | The ABI all bindings sit on |
| `IExecutionProvider` | C++ backend interface | `include/onnxruntime/core/framework/execution_provider.h → IExecutionProvider` | extension point | yes (add a backend) | Implement to add an accelerator |
| `OrtCustomOp` / `OrtCustomOpDomain` | C struct API | `onnxruntime.ai/docs/reference/operators/add-custom-op` | extension point | yes (add an op) | Register a custom operator |
| `RegisterCustomOpsLibrary()` | C API fn | `onnxruntime_c_api.h` (search `"RegisterCustomOpsLibrary"`) | public | yes | Load a shared lib of custom ops |
| `GraphOptimizationLevel` | enum | `onnxruntime_c_api.h` (search `"GraphOptimizationLevel"`) | public | no | `DISABLE_ALL`/`ENABLE_BASIC`/`EXTENDED`/`ALL` |

## Consumed Interfaces (libraries & internal modules)

The slice of each dependency the code calls directly. Not exhaustive.

| Library / Module | Interface used | Wrapped / adapted at | Why / for what |
|---|---|---|---|
| Protocol Buffers | ONNX model parse/serialize | `core/graph/` (model load) | The `.onnx` model format |
| MLAS (in-tree) + Eigen | GEMM / math kernels | `onnxruntime/core/mlas/`, CPU kernels | CPU compute |
| Per-EP accelerator SDKs (CUDA, TensorRT, **QNN**, CoreML…) | device runtime APIs | `core/providers/<ep>/` | Each EP adapts one accelerator |
| internal: partitioner → backend | `IExecutionProvider::GetCapability` / `Compile` | `core/framework/` | Assign + compile sub-graphs (see `CONCEPTS.md`) |
| internal: node → kernel | `KernelRegistryManager` | `core/framework/kernel_registry_manager.h` | Resolve `OpKernel` per node |

## Feature → API Map (what APIs power what features)

| Feature | Provided entry-point API | Key consumed interfaces | Flow |
|---|---|---|---|
| Run a model | `InferenceSession.run` | kernel registry; CPU/accelerator kernels | → `FLOWS.md` → "Life of an Inference" ✓ |
| **Add an operator** | `OrtCustomOp` (+ `RegisterCustomOpsLibrary`) **or** built-in kernel registration under `core/providers/<ep>/` | `KernelRegistryManager` | (kernel-resolution step of the flow) |
| **Add a backend (accelerator)** | implement `IExecutionProvider` (`GetCapability`/`Compile`/`GetKernelRegistry`) | the accelerator SDK | (partition step of the flow) |
| Tune optimization | `GraphOptimizationLevel` | `GraphTransformer` passes | (optimize step) |

## API Stability & Versioning
The **C API (`OrtApi`) is the stable ABI contract** — all language bindings depend on it and
it is versioned for backward compatibility. The **EP interface and kernel-registration macros
are internal extension points** that can change across releases (so out-of-tree EPs/kernels
must track the ORT version they build against). Runtime confirmed: `onnxruntime` **1.26.0**,
providers `['AzureExecutionProvider', 'CPUExecutionProvider']`.
