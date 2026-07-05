# kb — L1/L2/L3 knowledge-base pipeline (ML-runtime codebases)

The runnable implementation of `docs/research/digital-colleague-kb-spec.md`: a structured,
machine-readable, human-reviewed knowledge layer over large C/C++ ML-runtime codebases, so AI
"digital colleagues" can locate code and apply the institutional knowledge needed to change it.
It is an **ETL pipeline, not a doc set** — judged on token cost + freshness.

> Dependency-light: Python 3.9+, `PyYAML` (`requirements.txt`); `universal-ctags` + `ripgrep`
> for L1; optional `numpy`+`onnxruntime` for the MiniLM embedder (`requirements-minilm.txt`).
> No vector DB over source code (by design — see the spec's retrieval ruling).

## Try it in 2 minutes (no agent, no network)

The repo ships a tiny C++ fixture (`fixtures/mini-runtime/`) so you can build and query a
real KB without ONNX Runtime or an LLM.

```bash
cd framework/kb

# 0. Setup. System tools (not pip): universal-ctags + ripgrep on PATH.
#    Python deps in a virtualenv:
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt                      # PyYAML (the only core dep)
#    optional real MiniLM embedder: pip install -r requirements-minilm.txt

# 1. Build L1 (symbols, call graph, op registry, tests index) over the fixture
python -m kb.l1 build fixtures/mini-runtime /tmp/demo_kb
#  -> {"symbols": 17, "edges": 10, "ops": 4, "tests": 4, ...}   writes /tmp/demo_kb/*.jsonl

# 2. Query it programmatically (this is exactly what the MCP tools call under the hood)
python - <<'PY'
from kb.mcp_server import KB
kb = KB("/tmp/demo_kb")
print(kb.find_op("Add"))                              # Add @ cpu/elementwise_ops.cc:23
print(kb.find_symbol("AddCompute", detail="preview"))
PY

# 3. Or drive it as an MCP server over stdio (JSON-RPC, one message per line)
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"find_op","arguments":{"name":"Relu"}}}' \
  | KB_DIR=/tmp/demo_kb python -m kb.mcp_server
```

That's the core loop: **build → query**. L2 summaries (English explanations) are the one
step that needs an agent backend — see *Running on your own codebase* below.

## What it provides (and how it maps to the gap table)

| Layer / gap | Module | CLI | Status |
|---|---|---|---|
| **L1 op registry → `ops.jsonl`** (the spec's #1 artifact) | `kb/l1.py` | `python -m kb.l1 build <code> <out>` | ✅ verified on real ONNX Runtime (378 ops / 123 distinct, 7 macros) |
| L1 symbols / call graph / importance / churn | `kb/l1.py` | same | ✅ `symbols.jsonl`, `edges.jsonl` (xref:partial), `module_map.md` |
| **L2 evidence lint** (make bluffing impossible) | `kb/lint.py` | `python -m kb.lint <summaries> --code <root>` | ✅ rejects fold>20, code-claim-without-`[Lxx]`, out-of-range refs |
| **L2 summary generator** (spawns an AI agent per node) | `kb/l2.py` | `python -m kb.l2 build <l1_dir> <code> <out> --backend claude [--granularity symbol --top-n N]` | ✅ real run over ONNX Runtime; file- and **per-symbol** summaries; lint self-repair loop; bluffs quarantined |
| **Incremental hash + fold firewall** | `kb/incremental.py` | `python -m kb.incremental demo` | ✅ recompute only the dirty sub-tree; cascade stops at stable folds |
| **MCP retrieval server** (MCP 2025-06-18, paginated) | `kb/mcp_server.py` | `KB_DIR=<out> python -m kb.mcp_server [--http PORT]` | ✅ 11 tools (`find_symbol`+L2 / `relevant_code` / `find_op` / `get_summary` / `find_tests` / `trace_callers` / `find_recipe` / `get_recipe_steps` / `what_changed` / `review_status` / `build_info`) + resources + cursor pagination (no silent truncation) |
| **L1 tests index** | `kb/l1.py` | same build | ✅ `tests.jsonl`; `find_tests(symbol)` (real ORT: Clip→clip_test.cc) |
| **L1 incremental edges** (Glean ownership) | `kb/l1.py`, `kb/incremental.py` | same build | ✅ per-file hashes; re-derive changed files only; `kb.incremental plan` |
| **L2 faithfulness/eval harness** | `kb/eval.py` | `python -m kb.eval run <summaries> --code <root>` | ✅ claim-decompose + per-claim entailment; coverage; no BLEU/ROUGE |
| **Human-review ladder** | `kb/review.py` | `python -m kb.review promote …` | ✅ draft→reviewed→battle-tested + evidence anchors |
| **Drift sampler** | `kb/drift.py` | `python -m kb.drift sample <kb> <code>` | ✅ fresh_rate SLO; flags silent staleness |
| **L3 recipe semantic search** | `kb/recipes.py` + `kb/embed.py` + `find_recipe` | via MCP | ✅ vector search; **MiniLM/ONNX embedder** (`KB_MINILM_DIR`, HashEmbedder fallback); sqlite-vec still a future drop-in |
| **L3 recipe mining** | `kb/mine_recipes.py` | `python -m kb.mine_recipes <repo>` | ✅ clusters git history into candidate `draft` recipes for review |
| **Build-system knowledge** (targets/deps/options) | `kb/buildsys.py` | `python -m kb.buildsys <code> <out>` | ✅ CMake **File API** (exact; same configure-only run as compdb) with a static structural scan fallback (tagged partial); served via `build_info` |
| **Precise call-graph tier** | `kb/scip_ingest.py` + `kb/compdb.py` | `python -m kb.scip_ingest build <code> auto <out>` | ✅ live scip-clang validated; innermost-scope caller resolution; `auto` derives `compile_commands.json` itself (CMake configure-only / Meson / make dry-run / synthesized fallback) |

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

## Running on your own codebase

```bash
cd framework/kb
CODE=/path/to/onnxruntime/onnxruntime/core/providers/cpu    # any C/C++ tree

# 1. L1 — mechanical structure (fast, no LLM): symbols, edges, ops, tests, module_map
python -m kb.l1 build $CODE /tmp/kb

# 2. L2 — English summaries. This is the step that needs an agent backend:
#      --backend claude                    spawns headless `claude`
#      --backend cmd --cmd "your-agent {prompt}"   bring your own model
python -m kb.l2 build /tmp/kb $CODE /tmp/kb --backend claude \
       --granularity symbol --only math/ --limit 20
#      add --entail for the per-claim entailment gate (higher faithfulness, more LLM calls)

# 3. Check / measure / serve
python -m kb.lint /tmp/kb/summaries.jsonl --code $CODE --symbols /tmp/kb/symbols.jsonl
python -m kb.eval run /tmp/kb/summaries.jsonl --code $CODE --backend claude   # entailment %
KB_DIR=/tmp/kb python -m kb.mcp_server                       # serve to an agent over MCP

# 4. Trust & freshness
python -m kb.review promote /tmp/kb <symbol-id> --to reviewed --owner you
python -m kb.drift  sample  /tmp/kb $CODE                    # fresh_rate SLO
python -m kb.mine_recipes /path/to/repo                      # candidate L3 recipes from git log
python -m kb.buildsys $CODE /tmp/kb                          # build-system map -> build_info tool
```

Optional upgrades (graceful fallback if absent): set `KB_MINILM_DIR` to a MiniLM/ONNX model
dir for semantic recipe search (`scripts/fetch_minilm.sh` lays one out); add precise
clang-grade edges with `python -m kb.scip_ingest build $CODE auto /tmp/kb` — `auto` makes
`kb.compdb` derive `compile_commands.json` from the tree's own build system (CMake
**configure-only**, no compilation; Meson; `make -n` dry-run; or a flag-guessed synthesized
fallback, honestly tagged) so there is no manual build step. Needs `scip-clang` + `scip`
on PATH for the indexing itself.

Run the tests: `python -m pytest -q`  (65 pass; 1 skipped without scip-clang).

## Verification (production-quality gate)

- **`pytest`: 65 pass, 1 skipped** (ops extraction, pagerank distribution, lint good/bad, hash
  stability, firewall cascade, MCP tools + pagination, L2 generate / self-repair / quarantine /
  entailment-gate / cache-integrity, scip innermost-caller, buildsys (File API / static scan / fallback-on-configure-failure / MCP build_info), compdb auto-derivation (cmake
  configure-only / make dry-run parser / synthesized fallback), embedder + recipe mining,
  **end-to-end generator→MCP wiring + L1-only fallback**). The one skip is the live scip-clang test when the
  binary is absent. L2/eval tests use a deterministic `MockBackend` — CI never spawns an agent or
  hits the network.
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
  The default tier uses **ctags + a macro matcher + a heuristic call graph** (tagged
  `xref:partial`, exactly the spec's pragmatic fallback). The clang-grade tier is
  **scip-clang** (same Clang frontend as clangd, but emits a persistable index), and
  `kb.compdb` derives the `compile_commands.json` it needs from the tree's own build system —
  no manual build step. Remaining upgrade: tree-sitter for richer structure.
- **L2 summaries:** lint + schema + the **generator** (`kb/l2.py`) are all here — it spawns an
  agent per node and self-repairs against the lint. The remaining work is human: module owners
  promote `draft` → `reviewed` (the lint guarantees claims are *anchored*, not that they are
  *right* — citation existence is machine-checkable; citation accuracy is the review's job).
- **L3 / find_recipe:** vector search over the recipe layer (the spec's one sanctioned place for
  **semantic search** — over recipes, never raw source), with a real MiniLM/ONNX embedder behind
  `KB_MINILM_DIR` and a dependency-free hashing embedder as the default/fallback; `kb.mine_recipes`
  seeds candidate recipes from git history. sqlite-vec stays a future drop-in (brute-force cosine
  is exact at recipe scale).

## Layout
```
framework/kb/
  registration_patterns.yaml    # op macros per framework (data-driven)
  kb/
    l1.py            # L1: ops/symbols/edges/tests/pagerank/churn + incremental build
    l2.py            # L2: agent-per-node summary generator + lint/entailment self-repair loop
    lint.py          # L2 evidence lint (fold size, [Lxx] required, in-range refs)
    incremental.py   # content-hash + fold firewall; dirty-set cascade (plan_rebuild)
    retrieve.py      # relevant_code: hybrid lexical + graph + importance retrieval
    eval.py          # faithfulness harness: claim-decompose + per-claim entailment, coverage
    review.py        # human-review ladder: draft -> reviewed -> battle-tested + evidence anchors
    drift.py         # freshness sampler (fresh_rate SLO; flags silent staleness)
    recipes.py       # L3 vector search (get_embedder: MiniLM/ONNX or HashEmbedder)
    embed.py         # MiniLM/ONNX embedder + self-contained WordPiece tokenizer
    mine_recipes.py  # mine candidate L3 recipes from git history
    compdb.py        # derive compile_commands.json (cmake configure-only/meson/make -n/synth)
    buildsys.py      # build-system map: CMake File API (exact) / static scan (partial)
    scip_ingest.py   # precise (xref:precise) call-graph tier from scip-clang
    mcp_server.py    # MCP 2025-06-18 server: 11 tools + resources + pagination (stdio/HTTP)
  scripts/fetch_minilm.sh       # lay out KB_MINILM_DIR from allowlisted URLs (route B)
  fixtures/mini-runtime/        # tiny C++ exercising each op macro (deterministic tests)
  fixtures/recipes/*.yaml       # seed L3 recipes (add-an-op, fix-a-dispatch-bug)
  tests/test_kb.py              # 65 tests
```
