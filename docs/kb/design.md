# design.md — Architecture of the Digital-Colleague KB

Companion to `spec.md` (the what/why) and `implement.md` (the plan). This document is the
**how**: planes, data contracts, algorithms, and the issue→code agent loop. Citations refer to
`spec.md §9 References`; new ones are listed in §10.

---

## 1. Architecture at a glance

Five planes. Data flows left-to-right; the agent only ever touches the **Serving** plane.

```
┌─ INGEST ──────────┐ ┌─ KNOWLEDGE ────────────────┐ ┌─ FRESHNESS ─┐ ┌─ SERVING ─────┐ ┌─ CONSUME ──┐
│ source tree (git) │ │ L1 structural (mechanical) │ │ content-hash│ │ MCP server    │ │ digital     │
│ compile_commands? │→│ L2 explanation (LLM+gate)  │→│ early cutoff│→│ tools/        │→│ colleague   │
│ git history (PRs) │ │ L3 knowledge (human+mined) │ │ derived-fact│ │ resources     │ │ (agent)     │
│ Jira (issues)     │ │ QC/eval harness            │ │ invalidate  │ │ token budget  │ │ + RD review │
└───────────────────┘ └────────────────────────────┘ └─────────────┘ └───────────────┘ └────────────┘
        │                          │                                                          │
        └──────────────────────────┴── joined by stable {path, symbol-id} anchors ───────────┘
```

**Design invariant: everything joins on a stable anchor.** L1 symbols, L2 summaries, L3 recipes,
and the tests index all carry `path` (and, at symbol granularity, a SCIP-style symbol id). This
is the single most important contract — it is what makes the layers *compose* instead of being
disconnected artifacts. Anchors are `path → symbol` or character ranges, **never line numbers**,
because line anchors break on reformat ([SCIP][scip]).

---

## 2. INGEST plane

| Input | Extractor | Notes |
|---|---|---|
| source tree | macro-matcher (regex/YAML) + ctags | build-free, always available |
| `compile_commands.json` *(optional)* | **scip-clang** (precise tier) | build-aware; resolves macros + types ([scip-clang][scipclang]) |
| git history | churn/blame + PR miner | feeds importance; PR-mining for L3 recipes |
| Jira *(⏸ deferred, §7)* | issue adapter | normalizes issue → `{title, body, repro?, component}` |

**Two-tier indexing is the production pattern, not a compromise.** Neither tier alone is
complete: tree-sitter/ctags miss macro-generated and cross-file symbols
([tree-sitter-c][ts-macros], [ctags][ctags]); a Clang-frontend indexer resolves them but needs
a working build and still over-approximates indirect calls ([LLVM][llvm-cg]). So:

- **Tier A (build-free, default):** macro-matcher for the op registry (the one thing *only* this
  recovers without a build), ctags for symbols, heuristic body-span call graph tagged
  `xref:partial`.
- **Tier B (build-aware, upgrade):** scip-clang via `compile_commands.json` → precise
  go-to-def/find-refs/cross-TU edges tagged `xref:precise`. Parallel, crash-isolated workers let
  it survive a bad TU on huge trees ([scip-clang][scipclang]). **Ingested via `scip print --json`
  + stdlib `json`** (no protobuf dep) — see `leverage.md §G4` for the build-vs-reuse rationale.

The agent always sees a `precision` field and treats `xref:partial` indirect edges as candidate
sets.

---

## 3. KNOWLEDGE plane

### 3.1 L1 — structural (mechanical, trust = ✓)

Artifacts (JSONL, one record per line):

```jsonc
// symbols.jsonl
{"id":"math/clip.cc::Clip_6::Compute", "name":"Compute", "kind":"method",
 "path":"math/clip.cc", "range":[78,0,119,1], "scope":"Clip_6",
 "signature":"Status Compute(OpKernelContext*) const", "importance":0.91, "churn":12}
// edges.jsonl
{"caller":"…::Compute", "callee":"onnxruntime::concurrency::ThreadPool::TryBatchParallelFor",
 "precision":"partial"}
// ops.jsonl   (the spec's #1 table)
{"op_name":"Clip","version":"6","provider":"kCpuExecutionProvider","domain":"kOnnxDomain",
 "macro":"ONNX_CPU_OPERATOR_VERSIONED_KERNEL","framework":"onnxruntime","kernel_path":"math/clip.cc","line":13}
// tests.jsonl   (NEW — FR-3)
{"symbol":"math/clip.cc::Clip_6::Compute","test":"providers/cpu/math/clip_test.cc::ClipTest.Float",
 "kind":"regression"}
```

`importance` = pure-Python PageRank over the call graph; `churn` from git. Both are used to rank
retrieval results and to budget which symbols get an expensive per-symbol L2 summary.

**The tests index (FR-3, G2)** is built by (a) parsing test files for the symbols/ops they
exercise (the same macro/ctags machinery) and (b) optional coverage instrumentation. It answers
"if I touch `Clip_6::Compute`, which tests guard it?" — the regression set whose absence causes
~6.5 broken tests/patch ([regress][regress]).

### 3.2 L2 — explanation (LLM + gate, trust = ◐ → ✓ on review)

**Generation is bottom-up** (RAPTOR-shaped [RAPTOR][raptor]):

- **leaf** (symbol or file) summarized from *full source* → `evidence_level: code`, must cite
  real `[Lxx]`.
- **parent** (file→module→subsystem) summarized from *children's previews* (sentences) with
  inline provenance `(child/path)` → `evidence_level: inferred`, no fabricated lines.

Granularity upgrade (G5): leaves move from **file-level to per-symbol**, budgeted by
`importance` (summarize the top-N symbols fully; cheap fold-only for the long tail) so cost stays
bounded.

```jsonc
// summaries.jsonl
{"id":"math/clip.cc::Clip_6::Compute", "path":"math/clip.cc", "scope":"symbol",
 "fold":"fp16 clip compute", "preview":"Clamps each element to [min,max] in 16384-elt parallel chunks.",
 "full":"… via Eigen cwiseMax/cwiseMin [L90-93]; bounds from scalar inputs [L104-113].",
 "evidence_level":"code", "confidence":"draft", "owner":"team-cpu"}
```

**The grounding gate (FR-5)** is a *closed control loop*, not a one-shot filter:

```
generate ─► parse ─► lint(summary, source) ─clean─► land as draft
                         │ errors
                         └─► feed errors back to generator ─► retry (≤N) ─► else quarantine
```

This is **architectural grounding** — the gate is a *different mechanism* (static check that a
cited line exists) than the generator, which is essential: a verifier that shares the
generator's model self-confirms (the "hallucination barrier" [barrier][barrier]). The lint
guarantees citations *exist*; the **entailment check** (§5) and **human review** (§6) guarantee
they're *accurate*.

### 3.3 L3 — knowledge (human + mined, trust = ? → battle-tested)

Recipes are **decision trees, not checklists**:

```jsonc
{"id":"add-an-op", "title":"Add a new operator to a backend", "task":"add op|register kernel",
 "when":"new operator needed in CPU/QNN/ET provider", "confidence":"reviewed",
 "decision_points":[{"q":"element-wise?","yes":"derive ElementWiseKernel","no":"…"},
                    {"q":"needs fp16?","yes":"also update MLAS fallback or it silently downcasts"}],
 "steps":[…], "pitfalls":[…], "provenance":["PR#1234","JIRA-1100"]}
```

**Prior-fix memory (FR-6, G3)** is the episodic half: PR-mined `{issue → diff → tests touched →
outcome}` records, retrieved per issue. ExpeRepair shows this dual memory (episodic
demonstrations + semantic reflective insights) adds ~8 points pass@1 ([ExpeRepair][experepair]).

**This is the *only* place semantic/vector search is allowed** (FR/§3.4): recipes and prior-fix
records are natural-language and benefit from it; raw source never is. The vector index is kept
small with metadata pre-filtering because embedding-model upgrades force a full reindex and HNSW
recall decays with corpus size ([HNSW][hnsw]).

---

## 4. FRESHNESS plane

The unifying primitive across Bazel, Turborepo, and Salsa is **content-addressing + early
cutoff**: key every derived result on the *content/version* of its inputs, and stop propagation
when a recomputed value is byte-identical to the prior one ([Salsa early cutoff][salsa],
[Bazel][bazel]).

```
input_hash(node) = sha256(own_source ⊕ sorted(child_previews))   # order-independent
```

**Two firewalls:**

1. **Summary firewall (built).** A parent re-summarizes only when a child's *preview* changes
   (not its 20-char fold — too coarse, would let real changes pass silently). Preview-keyed is
   the balance between cost and staleness.
2. **Derived-fact invalidation (G6, the production gap).** When a file changes, we must
   invalidate not just its own facts but the **transitive derived facts** — call edges into/out
   of it, cross-references, and any parent summary built on it. This is the genuinely hard part
   of incremental indexing; Glean solves it by propagating new *ownership* of derived facts back
   through stacked DBs ([Glean][glean]). Concretely: `reverse_edges` already exists; we extend
   the dirty-set BFS to also re-emit the call/xref edges touching any changed symbol, and mark
   dependent summaries dirty.

A **drift sampler** periodically re-derives a random slice and diffs against the cache to detect
silent staleness (mirrors codeatlas Phase-7 drift control).

---

## 5. QC / eval harness (cross-cutting)

Three checks, increasing cost, gating promotion:

| Check | What | Cost | Source |
|---|---|---|---|
| **lint** (built) | fields, fold≤20, citations exist, code⇒cited | free | architectural grounding |
| **entailment** (G7) | does the cited line *support* the claim? claim-decompose + NLI/QA | 1 LLM/claim | RAGAS-style ⚠screen-only ([GroUSE][grouse]); QAFactEval ([qafe][qafe]) |
| **entity-trace** (G7) | extract code entities statically, verify each appears/aligns | static + 1 LLM | ETF ~73% F1 ([etf][etf]) |

**Confidence** is attached from **token-logit calibration** (Platt-scaled first-token
probabilities), *not* the model's self-reported confidence, which is poorly calibrated
([calib][calib]).

**We do not use BLEU/ROUGE** (uncorrelated with code-summary comprehension [bleu][bleu]) and we
**prefer execution over LLM-judging** for patch validation (LLM judges carry position/verbosity/
self-preference bias, ⚠magnitude contested [judge][judge]). Where judging is unavoidable, we
randomize presentation order and use multi-persona rubrics.

---

## 6. SERVING plane (MCP)

Dependency-free JSON-RPC 2.0. Current tools (built), all token-budgeted (≤25 rows), joined by
`path`:

`find_symbol`(+L2 join) · `find_op` · `get_summary` · `trace_callers` · `find_recipe` ·
`get_recipe_steps` · `what_changed` · `review_status`

**Planned (current scope):**

- `find_tests(symbol)` → tests guarding a symbol (FR-3) — a core KB query ("what guards this?").
- `relevant_code(query)` → ranked `{file, symbol, why, evidence}` for a natural-language query
  (generic retrieval; the same machinery the deferred `localize` would reuse).
- Adopt MCP's **tools (model-controlled) vs resources (app-controlled, read-only)** split and
  **cursor pagination** (`nextCursor`) so large result sets and static context don't front-load
  the budget ([MCP spec 2025-06-18][mcp]). Add **Streamable HTTP** transport alongside stdio for
  multi-client serving; keep schemas **lazily loaded** to avoid the ~75k-token startup tax
  ([context bloat][mcp-bloat]).

---

## 7. CONSUME plane — the issue→code loop (FR-9) · ⏸ DEFERRED

> This plane is **out of current scope** (see `spec.md §7`). It is documented so the KB above is
> built to support it cleanly later — as a downstream consumer that only talks to the MCP tools,
> requiring no rework of the KB. Skip on a first read focused on the knowledge base itself.

The reproducible spine is **localize → repair → validate** ([Agentless][agentless]); the KB
makes each step cheaper/more accurate.

```
JIRA-1234 ──► LOCALIZE ───────────► REPAIR ──────────────► VALIDATE ───────► PATCH + evidence
              find_prior_fix          get_summary(symbol)    run find_tests       │
              localize(issue):        get_recipe_steps       (regression set)     │
                hybrid retrieve       trace_callers          generate repro test  │
                (lexical+graph+L3)    (blast radius)         re-rank candidates ──┘
                rank by importance    sample K patches       majority vote
```

- **Localize** uses hybrid retrieval (§spec 3.4): lexical for identifiers in the issue, the
  dependency graph for navigation (LocAgent-style, the strongest signal [locagent][locagent]),
  and semantic over L3 for "how-to" framing. Returns top-5 with *why* + evidence anchors.
- **Repair** reads the per-symbol L2 summary (cheap, grounded) + the matching recipe's decision
  tree + the call-graph blast radius, then samples K candidate diffs.
- **Validate** runs the **regression set from the tests index** (so the patch doesn't break
  PASS→PASS, the #1 rejection cause [regress][regress]) and a **generated reproduction test**,
  re-ranking candidates by majority vote ([Agentless][agentless]). Iterate (RepoCoder-style:
  the draft becomes the next query [RepoCoder][repocoder]).

The agent never auto-merges; it returns the patch + the exact KB evidence it used, for human
supervision.

---

## 8. Data contracts (summary)

| Artifact | Key | Producer | Consumers |
|---|---|---|---|
| `symbols.jsonl` | symbol id, `path` | L1 | find_symbol, localize, freshness |
| `edges.jsonl` | (caller,callee,precision) | L1 | trace_callers, localize |
| `ops.jsonl` | op_name+version+provider | L1 macro-matcher | find_op |
| `tests.jsonl` | symbol→test | L1 tests-indexer | find_tests, validate |
| `summaries.jsonl` | id/`path`, scope | L2 generator | find_symbol, get_summary |
| `quarantine.jsonl` | id + lint errors | L2 gate | human review |
| `recipes/*.yaml` | recipe id | L3 human+miner | find_recipe |
| `fixes.jsonl` | issue→diff | L3 PR-miner | find_prior_fix |
| `l2_cache.json` | node→input_hash | freshness | incremental rebuild |

---

## 9. Mapping to current code

| Component | Status | File |
|---|---|---|
| op macro-matcher | ✅ | `kb/l1.py`, `registration_patterns.yaml` |
| symbols/edges/PageRank/churn | ✅ heuristic (`xref:partial`) | `kb/l1.py` |
| L2 generator (agent-spawn, self-repair) | ✅ file-level | `kb/l2.py` |
| L2 lint gate | ✅ | `kb/lint.py` |
| summary firewall | ✅ preview-keyed | `kb/incremental.py` |
| MCP server (8 tools, joined) | ✅ | `kb/mcp_server.py` |
| L3 recipe schema + find_recipe | ◐ stub + keyword | `fixtures/recipes/`, `kb/mcp_server.py` |
| per-symbol L2, eval/entailment harness, scip-clang tier, derived-fact invalidation, tests index, review workflow, L3 semantic | ❌ current scope | *to build — see `implement.md`* |
| issue→code loop (localize/repair/validate), prior-fix memory, Jira adapter | ⏸ deferred | *future consumer — §7* |

---

## 10. References (new)

[salsa]: https://rust-analyzer.github.io/blog/2023/07/24/durable-incrementality.html "Salsa durable incrementality"
[bazel]: https://bazel.build/remote/caching "Bazel remote caching"
[repocoder]: https://arxiv.org/abs/2303.12570 "RepoCoder"

All other citations resolve against `spec.md §9 References`.
