# implement.md — Phased Build Plan

Companion to `spec.md` (what/why) and `design.md` (how). This is the **plan**: ordered
milestones, each with concrete tasks mapped to files, an explicit **exit gate**, and the
verification that proves it. Sequencing is by **leverage on the KB itself** (current scope) —
make the agent's *understand-the-code* answers accurate, grounded, fresh, and cheap, then deepen
graph precision, trust, and scale. The **issue→code resolution loop (Jira) is deferred** to
Phase F; we build the KB so it can be added later without rework.

Legend: ✅ done · ◐ partial · ❌ not started. Effort is rough (S ≤1d, M ≤3d, L ≤1wk, XL >1wk).

---

## Milestone 0 — Baseline (DONE)

What already exists and is verified on real ONNX Runtime — the floor we build on.

- ✅ L1 op matcher → `ops.jsonl` (378 ops/123 distinct, real anchors). `kb/l1.py`
- ✅ L1 symbols / call graph (`xref:partial`) / PageRank / churn. `kb/l1.py`
- ✅ L2 generator: spawns Claude Code per node, self-repairs against lint, quarantines. `kb/l2.py`
- ✅ L2 lint gate. `kb/lint.py`
- ✅ Incremental preview-keyed summary firewall. `kb/incremental.py`
- ✅ MCP: 8 tools, joined by `path`. `kb/mcp_server.py`
- ✅ 16 tests; CI runs them with a deterministic MockBackend (no spawn/network).

**Exit gate (met):** `pytest -q` green; real ORT L1 build + L2 run + MCP query demonstrated.

---

## Phase 1 — KB depth & trust (make the core answers accurate and provable)

**Goal:** raise the quality of the agent's *understand-the-code* answers and make grounding
**measurable**. These are the highest-leverage KB-internal gaps (G5, G7, G6) plus the generic
retrieval entry point we use to measure relevance.

### M1.1 — Per-symbol L2 summaries (G5, FR-4) · L
- Move L2 leaves from file-level to **symbol-level**, budgeted by `importance` (full summary for
  top-N symbols/file; fold-only for the tail to bound cost). `kb/l2.py` (`build_leaf_prompt`
  takes a symbol range; orchestration iterates symbols, not files).
- Extend the MCP join from `path` to **symbol-id** so a symbol query returns *its own* summary.
- **Exit:** `find_symbol("Clip_6::Compute")` returns a symbol-scoped, lint-clean summary; test
  asserts `scope=="symbol"`.

### M1.2 — Generic retrieval `relevant_code(query)` (FR-7) · M
- Hybrid retrieval (design §3.4): lexical match of query tokens against `symbols`/`ops`; expand
  along `edges` (graph nav, the strongest signal [LocAgent][locagent]); rank by `importance`.
  Return top-5 `{path, symbol, why, evidence, precision}`. `kb/retrieve.py` + MCP tool. *(This is
  the reusable core the deferred `localize` would specialize — built now to measure relevance.)*
- **Exit:** on a small **decontaminated** NL-query set (10 queries with known target symbols),
  top-5 ≥ 70% (spec §5), reported via the eval harness (M1.3).

### M1.3 — Faithfulness/eval harness (G7, NFR) · L
- `kb/eval.py`: (a) **entailment** — decompose `full` into claims, verify each against the cited
  source span (RAGAS-style, a *screen* given ~0.55 human agreement [grouse][grouse]);
  (b) **entity-trace** — static-extract code entities, verify alignment (ETF ~73% F1 [etf][etf]);
  (c) **calibrated confidence** from token logits, not self-report ([calib][calib]).
- Metrics: lint-clean %, entailment %, retrieval@5, coverage. **No BLEU/ROUGE** ([bleu][bleu]).
- **Leverage (`leverage.md` G7):** PATTERN reimplementation on the `claude` subprocess — *no*
  RAGAS/DeepEval (LangChain/OpenAI-SDK/telemetry). ETF entity pass reimplemented (paper-only).
  No logprobs → confidence via self-consistency + isotonic fit. `SummaC` optional behind `extras`.
- **Exit:** harness runs in CI on the fixture KB; entailment ≥85% on seed summaries; metrics
  tracked over time.

### M1.4 — Derived-fact invalidation (G6, FR-8) · M
- Extend the dirty-set logic: on a changed file, also invalidate/re-emit the **call & xref edges**
  touching its symbols and mark dependent summaries dirty — not just the file's own facts
  ([Glean][glean]). `kb/incremental.py` (+`dirty_edges`, `dirty_dependents`).
- **Leverage (`leverage.md` G6):** mostly *wiring* — `compute_dirty` already exists and is tested
  but is **dead code** (never called by the pipeline). Wire it into `l2.build`; make
  `l1.build_edges` incremental with Glean-style caller-file ownership; persist per-file source
  hashes; keep a periodic full rebuild as a backstop (heuristic edges can miss a call).
- **Exit:** a unit test where editing a callee's signature marks the caller's edge *and* the
  caller's summary dirty; the firewall still stops where previews are unchanged.

**Phase-1 exit gate:** symbol-scoped grounded summaries served via MCP, an eval harness in CI
reporting entailment ≥85% and retrieval@5 on a decontaminated set, and correct incremental
invalidation of derived facts. *This is the first defensible "the KB is accurate and provable"
claim.*

---

## Phase 2 — Graph precision & human trust

### M2.1 — Precise call-graph tier via scip-clang (G4, FR-2) · XL *(needs a build)*
- Add an optional ingest: if `compile_commands.json` is present, run **scip-clang**, convert SCIP
  occurrences → `edges.jsonl` tagged `xref:precise` (macros + types resolved [scipclang][scipclang]).
  `kb/scip_ingest.py`. Falls back to Tier-A heuristic when absent.
- **Leverage (`leverage.md` G4):** REUSE the prebuilt `scip-clang` binary (x86_64-Linux, no
  build); ingest via `scip print --json` + **stdlib `json`** (no protobuf dep — there is no
  maintained Python SCIP lib). `enclosing_range` → caller; reference occurrence → callee.
- Keep indirect/virtual edges tagged as **candidate sets** ([LLVM][llvm-cg]).
- **Exit:** on an ORT build, a known virtual-dispatch call resolves to ≥1 precise edge;
  `relevant_code` accuracy on the decontaminated set improves vs M1.2 (report delta).

### M2.2 — Human-review workflow (G8) · M
- Promotion pipeline: `draft → reviewed → battle-tested`. A reviewer CLI/endpoint lists a
  module's drafts with their evidence anchors, accepts/edits/rejects, and stamps `owner` +
  `reviewed_at`. `review_status` already surfaces state. Promotion of an L3 recipe to
  `battle-tested` requires a linked shipped ticket.
- **Exit:** an RD can promote a module's L2 drafts in ≤10 min (spec target); a promoted summary
  flips `review_status` to `reviewed`.

### M2.3 — Tests index (G2, FR-3) · M
- Build `tests.jsonl`: parse test files with the existing ctags/macro machinery to map
  `symbol/op → test`. `kb/l1.py` (+`extract_tests`). New MCP tool `find_tests(symbol)`.
- **Exit:** on real ORT, `find_tests("Clip_6::Compute")` returns the Clip test(s); test asserts
  a known symbol→test link resolves. *(Also the regression set the deferred validate step needs.)*

---

## Phase 3 — Knowledge moat & scale

### M3.1 — L3 recipe extraction + semantic search (G9) · L
- Recipe miner: cluster related past PRs/changes into candidate decision-tree recipes for human
  review (the tacit moat); land as `draft`, promote on RD review. `kb/mine_recipes.py`.
- Replace `find_recipe` keyword match with embeddings **over the recipe layer only** (the one
  sanctioned place [§spec 3]), small index + metadata pre-filter ([hnsw][hnsw]); keyword remains
  the fallback behind the same interface.
- **Leverage (`leverage.md` G9):** REUSE **`sqlite-vec`** (zero-dep, ~163 KB, rides stdlib
  `sqlite3`); embed recipe NL text with `all-MiniLM-L6-v2` via **ONNX Runtime** (no torch) or an
  embedding API. Keep our own L2 hierarchy (RAPTOR/GraphRAG are concept-only).
- **Exit:** a paraphrased task ("introduce a new kernel") retrieves `add-an-op`; index rebuild is
  scripted and "time since full reindex" is tracked.

### M3.2 — MCP scale features (G10) · M
- Add **cursor pagination** (`nextCursor`) and the **tools-vs-resources** split (static context
  as read-only resources); **Streamable HTTP** transport beside stdio; **lazy schema loading**
  to avoid the ~75k-token startup tax ([mcp][mcp], [mcp-bloat][mcp-bloat]). `kb/mcp_server.py`.
- **Leverage (`leverage.md` G10):** stay **hand-rolled** (the Python SDK pulls ~14 deps and gives
  us neither pagination nor lazy-listing); implement the 2025-06-18 wire shapes ourselves via
  stdlib `http.server`. **Fixes a real bug:** today `hits[:BUDGET]` truncates with no `nextCursor`
  (truncated looks identical to complete).
- **Exit:** a paginated `find_symbol` over a large result set stays within the row budget per
  page; HTTP transport answers `initialize`/`tools/call`.

### M3.3 — Drift sampler & freshness SLO (FR-8) · S
- Periodic random re-derivation + diff vs cache to catch silent staleness; emit a freshness
  metric. **Exit:** sampler flags an intentionally-stale node in a test.

---

## Deferred Phase F — issue→code resolution (NOT in current scope)

Documented for continuity; build only after Phases 1–3 meet the §5 KB metrics. Reactivates G1/G3.

- **MF.1 — `resolve` orchestrator (G1, FR-9):** wire **localize → repair → validate**
  ([Agentless][agentless]) on top of `relevant_code` (M1.2) + `find_tests` (M2.3); sample K
  patches, run regression + generated repro test, majority-vote. Never auto-merge. `kb/resolve.py`.
- **MF.2 — prior-fix / experience memory (G3, FR-6):** PR-miner → `fixes.jsonl`;
  `find_prior_fix(issue)`; feed into repair (+~8 pts [experepair][experepair]). `kb/mine_fixes.py`.
- **MF.3 — Jira/GitHub adapter:** normalize a ticket → issue record; surface the patch + evidence
  for human supervision.

---

## Cross-cutting engineering hygiene (do alongside, not after)

- **CI:** keep all LLM-dependent steps behind `MockBackend`; never spawn an agent or hit network
  in CI. Add `eval.py` as a non-blocking report job first, blocking once thresholds hold.
- **Secrets discipline:** the "What NOT to capture" rule is absolute — no keys/tokens/PII/internal
  hostnames/customer data ever written to any artifact. Add a pre-write scrubber + a CI grep gate.
- **`.gitignore`:** add `.pytest_cache/` (currently tracked), keep `__pycache__/`, `.docforge/`.
- **Determinism:** every artifact is reproducible from `(source rev, patterns, prompts)`; record
  these in a `manifest.json` per build so a KB can be rebuilt and diffed.

---

## Sequenced summary & exit gates

| Phase | Milestones | Headline exit gate | Effort |
|---|---|---|---|
| 0 | baseline | ✅ pytest green + real ORT demo | done |
| **1** | per-symbol L2, `relevant_code`, eval harness, derived invalidation | **symbol-scoped grounded answers; entailment ≥85% + retrieval@5 in CI** | L–XL |
| 2 | scip-clang precise graph, review workflow, tests index | precise edges where build exists; RD can promote drafts; `find_tests` works | XL |
| 3 | L3 recipe mining + semantic, MCP scale, drift | paraphrase retrieves recipe; within budget at scale; freshness SLO | L |
| ⏸ F | resolve loop, prior-fix memory, Jira adapter | *deferred — build after Phases 1–3* | — |

**Definition of "production-ready" (v1, KB scope):** Phases 1–3 complete, the **KB metrics** in
`spec.md §5` met (retrieval relevance, grounding/entailment, coverage, freshness, token cost,
review throughput), every generated artifact behind the grounding gate + human-review ladder, and
the whole KB rebuildable deterministically. The deferred issue→code metric (fix-success on a
private, decontaminated set — *not* the public SWE-bench leaderboard, inflated ~6–7 pts by test
flaws/leakage [openai-drop][openai-drop]) is the bar for Phase F, later.

---

## References

Citations resolve against `spec.md §9` and `design.md §10`. The load-bearing ones for this plan:
[Agentless][agentless] (localize→repair→validate), [LocAgent][locagent] (graph localization),
[regress][regress] (regression safety), [ExpeRepair][experepair] (experience memory),
[scip-clang][scipclang] (precise tier), [Glean][glean] (derived-fact invalidation),
[ETF][etf]/[GroUSE][grouse]/[calib][calib] (grounding & confidence), [MCP][mcp] (serving),
[openai-drop][openai-drop] (eval honesty).

[agentless]: https://arxiv.org/abs/2407.01489
[locagent]: https://arxiv.org/abs/2503.09089
[regress]: https://arxiv.org/abs/2510.18270
[experepair]: https://arxiv.org/abs/2506.10484
[scipclang]: https://sourcegraph.com/blog/announcing-scip-clang
[glean]: https://glean.software/blog/incremental/
[etf]: https://arxiv.org/abs/2410.14748
[grouse]: https://arxiv.org/html/2409.06595v3
[calib]: https://arxiv.org/abs/2404.19318
[mcp]: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
[mcp-bloat]: https://agentmarketcap.ai/blog/2026/04/08/mcp-context-bloat-enterprise-scale-tool-definitions-agent-context-budget
[hnsw]: https://towardsdatascience.com/hnsw-at-scale-why-your-rag-system-gets-worse-as-the-vector-database-grows/
[bleu]: https://dl.acm.org/doi/10.1145/3387904.3389258
[llvm-cg]: https://groups.google.com/g/llvm-dev/c/SWIiEBWaJVg
[openai-drop]: https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/
