# CLAUDE.md — ExecuTorch onboarding notes

> Lean per-session index (≤200 lines). Source anchors `◐` (ExecuTorch `main @0d904b6bae60`);
> behavior not run here. Re-verify before acting.
>
> **Here to DO a task — add a delegate, add an op, fix a bug?** Start at `INDEX.md`.

## Project in One Paragraph

ExecuTorch is PyTorch's on-device runtime. It lowers an exported model **ahead of time** into a
compact `.pte` — a partitioner tags subgraphs for hardware **delegates**, each backend's
`preprocess` compiles them into opaque blobs — and a tiny C++ runtime loads the `.pte` and runs
delegates (`init`/`execute`) plus portable kernels for the rest.

## Top-Level Architecture (5 lines)

- AOT host: `torch.export` → `to_edge` → `Partitioner.partition` tags subgraphs.
- `to_backend` calls each backend's `preprocess` → opaque compiled blob.
- `to_executorch` memory-plans + serializes a self-contained `.pte`.
- Device: load `.pte`; `BackendInterface.init(blob)`/`execute` per delegate.
- Non-delegated ops run on portable/optimized kernels; **delegated ops have no CPU fallback**.

## Core Concepts You Must Know
- **`BackendInterface`** — delegate contract (AOT `preprocess` → runtime `init`/`execute`). → CONCEPTS.md
- **`Partitioner`** — tags subgraphs for a backend; over-tagging fails lowering. → CONCEPTS.md
- **AOT vs on-device split** — most work is AOT; runtime is tiny. → OVERVIEW

## Where to Look for What
| Task | Look in |
|---|---|
| Add a delegate | `backends/<name>/` + `runtime/backend/interface.h` |
| Add a kernel | `kernels/`, `EXECUTORCH_LIBRARY` |
| Lowering / partition | `exir/` |
| On-device execution | `runtime/executor/` |

## Conventions That Aren't Obvious
- Adding a **delegate** (whole subgraph) ≠ adding a **kernel** (one op).
- Delegated subgraphs do **not** fall back to CPU — failures surface AOT or at load.
- Selective build omits unlisted ops → register what the model needs.
- Most cost is AOT; debug device failures by inspecting how it was lowered.

## Pointers
- Consumer entry → `INDEX.md` · Concepts → `CONCEPTS.md` · Flow → `FLOWS.md` ·
  APIs → `API.md` · Tasks → `HOW-TO.md` · Map → `OVERVIEW.md`

---
_Illustrative reference instance. Source: ExecuTorch main @0d904b6bae60; behavior not run here._
