# Worked Reference Instance — ONNX Runtime Onboarding Notes

A third **filled L3 example** of the `docforge-onboard` template, and the first on an
**ML inference runtime/compiler**: [ONNX Runtime](https://github.com/microsoft/onnxruntime).
It demonstrates the structure the research report
(`docs/research/digital-colleague-kb.md`) identified as universal across ML runtimes —
**graph IR → op/kernel registry → ExecutionProvider (backend) → partitioner → graph
transforms → memory plan → execute** — and the two extension axes a digital colleague is
usually asked to work on: **add an operator** and **add a backend (EP)**.

> **Verification (two levels, 2026-06-06):**
> - **Behavior — `✓` run.** `onnxruntime 1.26.0` (pip) was actually run: providers listed,
>   and a real `Add([2,3],[4,5]) → [6,8]` inference on `CPUExecutionProvider`.
> - **Source anchors — `◐` read.** Symbols/files were confirmed against ONNX Runtime
>   `main @90c095d1e309` (GitHub, 2026) during the research pass (e.g. `execution_provider.h`
>   quoted directly); not re-fetched per file in this session. Anchors use
>   `file → symbol`, never line numbers. Re-verify against your checkout before acting.

## What's here

| File | Role | Demonstrates |
|---|---|---|
| `CLAUDE.md` | Auto-loaded lean index | ≤200-line boot context |
| `INDEX.md` | Consuming-skill entry | Map, invariants registry, task recipes (incl. add-op / add-EP) |
| `OVERVIEW.md` | What ORT is + structural map | L3 reference for a large C++ ML runtime |
| `CONCEPTS.md` | `IExecutionProvider` + the kernel registry | L3 **data-structure/API** entries with *why* |
| `FLOWS.md` | "Life of an inference" | L3 **flow** (partition → kernel → execute) + fallback branch |
| `API.md` | Provided API + consumed libs + feature→API | The **add-op / add-backend** entry points |
| `HOW-TO.md` | pip-run / build / custom op | L3 **how-to**, pip path run-verified |

## Why ONNX Runtime as the ML-runtime exemplar
- **Open source, runnable without a full build** (pip wheel) → behavior verifiable now;
  the giant C++ build is documented but optional.
- Its `IExecutionProvider` + kernel registry + `GraphTransformer` map cleanly onto QNN /
  SNPE / ExecuTorch / Hexagon (same pipeline, different names) — so this instance doubles as
  the **template** for documenting the gated/licensed runtimes in-house.
