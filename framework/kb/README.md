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
| **L2 summary generator** (spawns an AI agent per node) | `kb/l2.py` | `python -m kb.l2 build <l1_dir> <code> <out> --backend claude [--granularity symbol --top-n N]` | ✅ real run over ONNX Runtime; file- and **per-symbol** summaries; lint self-repair loop; bluffs quarantined |
| **Incremental hash + fold firewall** | `kb/incremental.py` | `python -m kb.incremental demo` | ✅ recompute only the dirty sub-tree; cascade stops at stable folds |
| **MCP retrieval server** (token-budgeted) | `kb/mcp_server.py` | `KB_DIR=<out> python -m kb.mcp_server` | ✅ `find_symbol` (joins L2)/`find_op`/`get_summary`/`trace_callers`/`find_recipe`/`get_recipe_steps`/`what_changed`/`review_status` |
| **L3 recipe / decision-tree** | `fixtures/recipes/*.yaml` + `find_recipe` | via MCP | ◐ schema + stub (extraction needs PRs/humans — prompts in the spec appendices) |

## The L2 generator (`kb/l2.py`)

L1 is mechanical; L2 turns it into reviewed-quality English. The generator is a plain
orchestrator that **spawns an AI-agent executable per node** and feeds it the real source —
the model is a pluggable dependency, not baked in:

- `--backend claude` → spawns `claude -p … --output-format json --tools ""` (headless, tools
  off: pure text-gen). Parses the result envelope; surfaces spawn/timeout/protocol errors.
- `--backend cmd --cmd "TEMPLATE"` → **any** other agent executable (prompt on `{prompt}` or
  stdin) — bring your own model.

It is **bottom-up**: a *file* (leaf) is summarized from its full source and must cite real
`[Lxx]` lines (`evidence_level: code`); a *module* is summarized only from its children's
`fold`s (`evidence_level: inferred`, no fabricated lines) — cheap, and what the firewall keys
on. The lint is wired in as a **closed control loop**: every summary is linted, and on failure
the exact errors are fed back to the agent to fix; only lint-clean summaries land in
`summaries.jsonl` (confidence `draft`, never auto-trusted), and incorrigible bluffs go to
`quarantine.jsonl` for a human. Re-runs are incremental (content-hashed), so only the changed
sub-tree costs anything.

```
python -m kb.l2 build <l1_dir> <codebase> <out> --backend claude --only math/ --limit 50
# -> summaries.jsonl (drafts) + quarantine.jsonl + l2_cache.json
```

## How the layers connect (the retrieval path)

The layers compose through the MCP server, joined by file `path` — this is what makes it a KB
and not three disconnected artifacts:

```
L1  symbols/edges/ops.jsonl ─┐
L2  summaries.jsonl ─────────┤→  KB (join by path)  →  MCP tools  →  agent
L3  recipes/*.yaml ──────────┘
```

- `find_symbol(name, detail=preview)` returns the symbol **and its file's generated L2 summary**
  (evidence_level + `draft`/`reviewed` confidence), falling back to the bare L1 signature when no
  summary exists yet — so it degrades gracefully before L2 has run.
- `find_op(name)` exposes the op registry (`ops.jsonl`) with `kernel_path:line` anchors.
- `get_summary(path)` returns a file or `module:<dir>` explanation directly.
- `review_status(symbol)` reports the real L2 review state, not a hardcoded string.

A worked agent flow ("add an op"): `find_recipe` (the how) → `find_op`/`find_symbol` (a worked
example + its L2 summary) → `get_summary` (the file/module context) → `trace_callers` (blast
radius) → edit. All token-budgeted (≤25 rows/call).

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
python -m kb.l2 build  <out_dir> <codebase> <l2_dir> --backend claude   # generate summaries
python -m kb.lint      summaries.jsonl --code <codebase> --symbols <out_dir>/symbols.jsonl
KB_DIR=<out_dir> python -m kb.mcp_server        # then speak MCP JSON-RPC on stdin
python -m kb.l2 build  <out_dir> <codebase> <l2_dir> --backend claude --granularity symbol
python -m pytest -q                             # 45 tests
```

## Verification (production-quality gate)

- **`pytest`: 45/45 pass** (ops extraction, pagerank distribution, lint good/bad, hash
  stability, firewall cascade, MCP tools, unknown-tool error, L2 generate / self-repair /
  quarantine / incremental-skip, **end-to-end generator→MCP wiring + L1-only fallback**). L2
  tests use a deterministic `MockBackend` — CI never spawns an agent or hits the network.
- **Real-source run:** the op matcher extracted **378 registrations / 123 distinct ops** from a
  sparse checkout of ONNX Runtime's CPU provider (`Conv`, `Gemm`, `MatMul`, `Softmax`, …) with
  correct versions + `file:line` anchors.
- **L2 real run:** `kb.l2 --backend claude` spawned Claude Code over ONNX Runtime's `math/clip`
  files and produced lint-clean draft summaries with **real** line citations
  (`[L13-18]`, `[L90-93]`); the module synthesis correctly emitted `inferred` with no fabricated
  lines. A second run was fully cache-served ($0) — the freshness firewall.
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
- **L2 summaries:** lint + schema + the **generator** (`kb/l2.py`) are all here — it spawns an
  agent per node and self-repairs against the lint. The remaining work is human: module owners
  promote `draft` → `reviewed` (the lint guarantees claims are *anchored*, not that they are
  *right* — citation existence is machine-checkable; citation accuracy is the review's job).
- **L3 / find_recipe:** keyword match today; the spec's one sanctioned place for **semantic
  search** (over recipes, never raw source) is the upgrade.

## Layout
```
framework/kb/
  registration_patterns.yaml   # op macros per framework (data-driven)
  kb/l1.py kb/l2.py kb/lint.py kb/incremental.py kb/mcp_server.py
  fixtures/mini-runtime/        # tiny C++ exercising each op macro (deterministic tests)
  fixtures/recipes/add-an-op.yaml
  tests/test_kb.py
```
