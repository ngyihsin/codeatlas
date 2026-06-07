# Digital-Colleague KB — design docs

The master design set for the ML/AI-framework knowledge base that digital colleagues use to
**resolve Jira issues** (design a feature, fix a bug) over large C/C++ ML runtimes (QNN · SNPE ·
Hexagon NN · ExecuTorch · ONNX Runtime).

Read in order:

| Doc | Question it answers |
|---|---|
| [**spec.md**](spec.md) | *What & why* — problem, the Jira→fix north-star, layered model, requirements, success metrics, **gap analysis**, risks |
| [**design.md**](design.md) | *How* — the five planes (ingest/knowledge/freshness/serving/consume), data contracts, the localize→repair→validate loop, mapping to current code |
| [**implement.md**](implement.md) | *The plan* — phased milestones with exit gates, sequenced by leverage on the north-star |

**Grounding.** Every load-bearing decision is backed by a June-2026 literature review (cited
inline; contested findings flagged `⚠contested`) **and** an audit of the running code in
[`../../framework/kb/`](../../framework/kb/). The implementation digest and earlier research live
in [`../research/`](../research/).

**Current state in one line:** L1 (op registry + symbols/graph), L2 (agent-generated, lint-gated
summaries), incremental firewall, and an 8-tool MCP server are built and verified on real ONNX
Runtime; the **issue→code workflow, tests index, precise call graph, and eval/review harness are
the gaps** — see `spec.md §6` and `implement.md`.
