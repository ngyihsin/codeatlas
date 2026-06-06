# Worked Reference Instance — ExecuTorch Onboarding Notes

A second **ML-runtime** L3 example (after ONNX Runtime), chosen to prove the template
**reuses across runtimes**: ExecuTorch expresses the same universal pipeline
(graph IR → op/kernel registry → backend/delegate + partitioner → lowering → memory plan →
execute) with PyTorch-edge names, and exposes the same two extension axes — **add an
operator** and **add a backend (delegate)**.

> **Verification (2026-06-06):**
> - **Source anchors — `◐` read.** Confirmed against ExecuTorch `main @0d904b6bae60`
>   (GitHub): the delegate/partitioner and kernel-registration docs were fetched directly in
>   the research pass. Anchors use `file → symbol`, never line numbers.
> - **Behavior — not run here.** ExecuTorch's pip package (1.3.1) pulls full PyTorch; an
>   end-to-end export→delegate→`.pte`→runtime cycle was **not executed** in this environment,
>   so runtime claims stay `◐`. The ONNX Runtime instance is the run-verified ML-runtime
>   example; this one is the **cross-runtime template** check.

## What's here

| File | Role | Demonstrates |
|---|---|---|
| `CLAUDE.md` | Auto-loaded lean index | ≤200-line boot context |
| `INDEX.md` | Consuming-skill entry | Map, invariants registry, add-op / add-backend recipes |
| `OVERVIEW.md` | What ExecuTorch is + structural map | L3 reference for an edge ML runtime |
| `CONCEPTS.md` | `BackendInterface` + `Partitioner` | L3 data-structure/API entries with *why* |
| `FLOWS.md` | "Lowering & delegation" (`to_edge`→`to_backend`→`.pte`) | L3 flow + error branch |
| `API.md` | AOT + runtime API, consumed libs, feature→API | The **add-op / add-backend** entry points |
| `HOW-TO.md` | export / lower / run (documented) | L3 how-to (behavior `◐`, not run here) |

## Why ExecuTorch alongside ONNX Runtime
The two share one shape but differ in emphasis: ORT partitions/optimizes **at session init
on-device**; ExecuTorch does most lowering/delegation **ahead-of-time (AOT)** into a `.pte`,
with a tiny on-device runtime. Documenting both shows the template captures the *same
concepts* (backend interface, partitioner, kernel registry, the two axes) regardless of where
the work happens — which is exactly what's needed to template QNN/SNPE/Hexagon next.
