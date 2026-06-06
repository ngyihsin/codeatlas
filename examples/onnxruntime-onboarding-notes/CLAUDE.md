# CLAUDE.md — ONNX Runtime onboarding notes

> Lean per-session index (≤200 lines). Source anchors `◐` (ORT `main @90c095d1e309`);
> inference behavior `✓` (`onnxruntime` 1.26.0). Re-verify before acting.
>
> **Here to DO a task — add an op, add a backend, fix a bug?** Start at `INDEX.md`.

## Project in One Paragraph

ONNX Runtime loads an ONNX graph and runs it across pluggable hardware backends
("Execution Providers"). The runtime owns graph optimization and **partitioning**; each EP
only *proposes* sub-graphs it can run (`GetCapability`) and supplies kernels; anything no
accelerator claims falls back to the **CPU EP**, so a model always runs.

## Top-Level Architecture (5 lines)

- A session loads + optimizes + **partitions** the graph at init (cost paid once).
- Each EP proposes runnable sub-graphs via `IExecutionProvider::GetCapability`; ORT assigns.
- `KernelRegistryManager` resolves each assigned node → an `OpKernel`.
- `run()` executes kernels in order; unclaimed nodes run on the CPU EP.
- Two extension axes: **add an op** (kernel registry) vs **add a backend** (EP interface).

## Core Concepts You Must Know
- **`IExecutionProvider`** — the backend interface; ORT (not the EP) owns assignment. → CONCEPTS.md
- **kernel registry / `OpKernel`** — node → callable kernel; keyed by op+EP+dtype. → CONCEPTS.md
- **CPU EP fallback** — the universal safety net. → OVERVIEW / FLOWS

## Where to Look for What
| Task | Look in |
|---|---|
| Add a backend | `core/framework/execution_provider.h` |
| Add/resolve a kernel | `core/framework/kernel_registry_manager.h`, `core/providers/<ep>/` |
| Graph optimization | `core/optimizer/` (`GraphTransformer`) |
| Run orchestration | `core/session/inference_session.cc` |
| Protocol/replies (model format) | `core/graph/` (protobuf) |

## Run / Inspect (verified ✓ with onnxruntime 1.26.0)
```
pip install onnxruntime onnx numpy
python -c "import onnxruntime as o; print(o.get_available_providers())"
```
Full steps: `HOW-TO.md`. Provided/consumed APIs + add-op/add-backend: `API.md`.

## Conventions That Aren't Obvious
- `GetCapability` *proposes*; ORT *decides*. Don't claim what you can't run.
- Keep the CPU EP in the provider list (fallback).
- Adding an **op** ≠ adding a **backend** — different registries/interfaces.
- Partition/optimize happen at session init, not per `run()`.

## Pointers
- Consumer entry → `INDEX.md` · Concepts → `CONCEPTS.md` · Flow → `FLOWS.md` ·
  APIs → `API.md` · Tasks → `HOW-TO.md` · Map → `OVERVIEW.md`

---
_Illustrative reference instance. Source: ORT main @90c095d1e309; runtime: onnxruntime 1.26.0._
