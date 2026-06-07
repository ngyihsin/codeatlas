# Digital-Colleague KB — design docs

The master design set for the ML/AI-framework knowledge base that digital colleagues use to
**locate code and apply institutional knowledge** to change it correctly (design a feature, fix a
bug) over large C/C++ ML runtimes (QNN · SNPE · Hexagon NN · ExecuTorch · ONNX Runtime).

> **Current scope:** the **knowledge base itself** — layers, retrieval, freshness, grounding,
> eval. The end-to-end **issue→code (Jira) resolution loop is deferred** (designed-for, not built
> now); see `spec.md §7` and `implement.md` Phase F.

Read in order:

| Doc | Question it answers |
|---|---|
| [**spec.md**](spec.md) | *What & why* — problem, the agent query workflows, layered model, requirements, KB success metrics, **gap analysis**, risks |
| [**design.md**](design.md) | *How* — the five planes (ingest/knowledge/freshness/serving/consume), data contracts, retrieval routing, freshness engine, mapping to current code |
| [**implement.md**](implement.md) | *The plan* — phased milestones with exit gates, sequenced by leverage on the KB (Phase F = deferred resolution loop) |
| [**leverage.md**](leverage.md) | *Build vs. reuse* — per-gap decisions (REUSE/TARGET/PATTERN) from inspecting the actual projects (scip-clang, RAGAS, sqlite-vec, MCP SDK, Salsa/Glean…), with licenses and dependency cost |

**Grounding.** Every load-bearing decision is backed by a June-2026 literature review (cited
inline; contested findings flagged `⚠contested`) **and** an audit of the running code in
[`../../framework/kb/`](../../framework/kb/). The implementation digest and earlier research live
in [`../research/`](../research/).

**Current state in one line:** L1 (op registry + symbols/graph), L2 (agent-generated, lint-gated
summaries), incremental firewall, and an 8-tool MCP server are built and verified on real ONNX
Runtime; the active gaps are **per-symbol L2, eval/grounding harness, precise call graph,
derived-fact invalidation, review workflow, and L3 recipe extraction** (the issue→code loop is
deferred) — see `spec.md §6` and `implement.md`.
