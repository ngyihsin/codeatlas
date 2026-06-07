# Digital-Colleague KB — Design Spec (digest) & Implementation Status

**Source:** `digital-colleague-kb-spec.md` (Google Drive, owner changyihsin@gmail.com,
2026-06-01). This is a faithful in-repo digest of that spec plus a map to its implementation
in this repo (`framework/kb/`). The full prose spec lives in Drive; this captures the
load-bearing decisions and tracks what is built.

## The problem (Part 0)
Not a chatbot wiki — a structured, machine-readable, human-verified knowledge layer over very
large C/C++ ML-runtime codebases (QNN / SNPE / Hexagon NN / ExecuTorch / ONNX Runtime), so an
agent can locate code **and apply the institutional knowledge** to change it correctly. Judged
on token cost + freshness, not human readability.

## Locked-in decisions (Part 1 — the retrieval debate)
1. **No chunk-level embeddings over source code** (chunking severs a call from its definition).
2. **Pre-compute a *light* structural index** (symbols, call graph, op registry) so automated
   runs don't cold-start every time.
3. **The highest-value layer is tacit knowledge** (recipes/pitfalls) — not in the code at all;
   this is the moat model progress can't erode.
4. **Vector search only over the L3 recipe layer** (natural-language "how to do X"), never raw
   source.

## Three layers (Part 2)
| Layer | Content | Source | Reviewer |
|---|---|---|---|
| L1 Structural | symbols, call graph, module boundaries, **op registry** | mechanical | none |
| L2 Explanation | what each function/file/module does | LLM from code+git | module owner |
| L3 Knowledge | patterns, recipes, decision trees, pitfalls | human + LLM | senior RD |

- **L1 trap:** op registration is macro-generated → a hand-written **macro matcher**
  (`registration_patterns.yaml`) producing `ops.jsonl` is the single most valuable table.
- **L2 anti-bluff:** full code / bounded scope / bottom-up; `[code:Lxx]` vs `[inferred]`;
  machine-checkable lint before human review; granularity `fold/preview/full`.
- **L3 tacit extraction:** PR-mining → react-to-draft → deep interview (Critical Decision
  Method); output is a **decision tree**, not a checklist; top confidence = `battle-tested`
  (a real ticket shipped using it).
- **Incremental (Part 3):** content hash + **fold-summary firewall** (Bazel-style); only
  behavior-changing recomputes reach a human; drift sampling mirrors codeatlas Phase-7.
- **Retrieval API (Part 4):** an MCP server, every tool token-budgeted.
- **Confidence (Part 5):** maps to codeatlas `✓ / ◐ / ?`.
- **Build order (Part 6):** PoC-first on `executorch/backends/qualcomm/`.

## Implementation status (→ `framework/kb/`)
| Spec element | Built | Where |
|---|---|---|
| L1 op matcher → `ops.jsonl` | ✅ (real ORT: 378 ops/123 distinct) | `kb/l1.py`, `registration_patterns.yaml` |
| L1 symbols / call graph / PageRank / churn / module_map | ✅ (call graph `xref:partial`) | `kb/l1.py` |
| L2 evidence lint | ✅ | `kb/lint.py` |
| L2 LLM summary runner (fold/preview/full) | ✅ spawns an AI agent per node; lint self-repair loop; real ORT run | `kb/l2.py` |
| Incremental hash + fold firewall | ✅ | `kb/incremental.py` |
| MCP retrieval server (token-budgeted) | ✅ | `kb/mcp_server.py` |
| L3 recipe/decision-tree + `find_recipe` | ◐ schema + stub | `fixtures/recipes/`, `kb/mcp_server.py` |
| L3 extraction prompts (PR-mine / interview) | ◐ in spec appendices B–D | Drive spec |

**Reconciliation:** spec writes `.codeatlas/`; framework uses `.docforge/` (same cache). Spec
prefers tree-sitter+clangd for L1; the prototype uses ctags + macro matcher + heuristic call
graph (tagged `xref:partial`, the spec's allowed fallback) — clangd/tree-sitter are the
accuracy upgrade. Verified via `framework/kb` pytest (14/14) + real ONNX Runtime runs of both
the L1 op matcher and the L2 generator (Claude Code spawned per node, lint-clean drafts).
