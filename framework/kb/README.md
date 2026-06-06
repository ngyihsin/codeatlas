# kb — L1/L2/L3 knowledge-base pipeline (ML-runtime codebases)

The runnable implementation of `docs/research/digital-colleague-kb-spec.md`: a structured,
machine-readable, human-reviewed knowledge layer over large C/C++ ML-runtime codebases, so AI
"digital colleagues" can locate code and apply the institutional knowledge needed to change it.
It is an **ETL pipeline, not a doc set** — judged on token cost + freshness.

> Dependency-light: Python 3.9+, `PyYAML`; `universal-ctags` + `ripgrep` for L1. No vector DB
> over source code (by design — see the spec's retrieval ruling).

## What it provides (and how it maps to the gap table)

| Layer / gap | Module | CLI | Status |
|---|---|---|---|
| **L1 op registry → `ops.jsonl`** (the spec's #1 artifact) | `kb/l1.py` | `python -m kb.l1 build <code> <out>` | ✅ verified on real ONNX Runtime (378 ops / 123 distinct, 7 macros) |
| L1 symbols / call graph / importance / churn | `kb/l1.py` | same | ✅ `symbols.jsonl`, `edges.jsonl` (xref:partial), `module_map.md` |
| **L2 evidence lint** (make bluffing impossible) | `kb/lint.py` | `python -m kb.lint <summaries> --code <root>` | ✅ rejects fold>20, code-claim-without-`[Lxx]`, out-of-range refs |
| **Incremental hash + fold firewall** | `kb/incremental.py` | `python -m kb.incremental demo` | ✅ recompute only the dirty sub-tree; cascade stops at stable folds |
| **MCP retrieval server** (token-budgeted) | `kb/mcp_server.py` | `KB_DIR=<out> python -m kb.mcp_server` | ✅ `find_symbol`/`trace_callers`/`find_recipe`/`get_recipe_steps`/`what_changed`/`review_status` |
| **L3 recipe / decision-tree** | `fixtures/recipes/*.yaml` + `find_recipe` | via MCP | ◐ schema + stub (extraction needs PRs/humans — prompts in the spec appendices) |

## The op matcher (`ops.jsonl`)

Op registration is macro-generated, so parsers miss it. `registration_patterns.yaml` lists each
framework's macros as named-group regexes → `{op_name, provider, domain, version, macro,
framework, kernel_path, line}`. **Add a framework by adding a YAML entry — no code change.**
Covers ONNX Runtime (`ONNX_(CPU_)?OPERATOR_(VERSIONED_)?(TYPED_)?KERNEL(_EX)?`), ExecuTorch
(`EXECUTORCH_LIBRARY`), and QNN (`REGISTER_QNN_OP_BUILDER`).

```
python -m kb.l1 ops /path/to/onnxruntime/core/providers/cpu -   # prints ops.jsonl
```

## Quick start

```
python -m kb.l1 build  <codebase> <out_dir>     # symbols/edges/ops/module_map
python -m kb.lint      summaries.yaml --code <codebase> --symbols <out>/symbols.jsonl
KB_DIR=<out_dir> python -m kb.mcp_server        # then speak MCP JSON-RPC on stdin
python -m pytest -q                             # 9 tests
```

## Verification (production-quality gate)

- **`pytest`: 9/9 pass** (ops extraction, pagerank distribution, lint good/bad, hash stability,
  firewall cascade, MCP tools, unknown-tool error).
- **Real-source run:** the op matcher extracted **378 registrations / 123 distinct ops** from a
  sparse checkout of ONNX Runtime's CPU provider (`Conv`, `Gemm`, `MatMul`, `Softmax`, …) with
  correct versions + `file:line` anchors.
- **MCP server** answered `initialize`/`tools/list`/`tools/call` over a built KB.

## Reconciliation with the spec

- **Confidence model:** the spec's `verified|speculation` / `draft|reviewed|battle-tested` maps
  onto codeatlas `✓ / ◐ / ?`. Generated content lands in a draft area, promoted on review.
- **Path naming:** the spec writes `.codeatlas/`; this framework now uses `.docforge/` — treat
  them as the same cache location.
- **L1 extractor:** the spec prefers tree-sitter + clangd (scope-accurate, macro expansion).
  This prototype uses **ctags + a macro matcher + a heuristic call graph** (tagged
  `xref:partial`, exactly the spec's pragmatic fallback). Upgrade path: clangd via
  `compile_commands.json` for an accurate call graph; tree-sitter for richer structure.
- **L2 summaries:** the lint + schema are here; the LLM summarization *runner* is the remaining
  piece (the spec's leaf/synthesis prompts are in its appendices). It plugs in above this lint.
- **L3 / find_recipe:** keyword match today; the spec's one sanctioned place for **semantic
  search** (over recipes, never raw source) is the upgrade.

## Layout
```
framework/kb/
  registration_patterns.yaml   # op macros per framework (data-driven)
  kb/l1.py kb/lint.py kb/incremental.py kb/mcp_server.py
  fixtures/mini-runtime/        # tiny C++ exercising each op macro (deterministic tests)
  fixtures/recipes/add-an-op.yaml
  tests/test_kb.py
```
