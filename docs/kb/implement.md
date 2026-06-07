# implement.md — Phased Build Plan

Companion to `spec.md` (what/why) and `design.md` (how). This is the **plan**: ordered
milestones, each with concrete tasks mapped to files, an explicit **exit gate**, and the
verification that proves it. Sequencing is by **leverage on the north-star** (resolve a Jira
issue), not by layer tidiness — we build the thinnest end-to-end "Jira → patch" slice first,
then deepen.

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

## Phase 1 — Thin vertical slice: "Jira → localized patch" (the product)

**Goal:** the smallest end-to-end path that resolves a real issue, so we have something to
*measure* and improve. This front-loads the highest-leverage gaps (G1, G2, G4-localize).

### M1.1 — Tests index (G2, FR-3) · M
- Build `tests.jsonl`: parse test files with the existing ctags/macro machinery to map
  `symbol/op → test`; mark `kind: regression`. `kb/l1.py` (+`extract_tests`).
- New MCP tool `find_tests(symbol)` → regression set. `kb/mcp_server.py`
- **Exit:** on real ORT, `find_tests("Clip_6::Compute")` returns the Clip test(s); test asserts
  a known symbol→test link resolves.

### M1.2 — `localize(issue)` tool (G1/G4) · L
- Hybrid retrieval (design §3.4): lexical match of issue tokens against `symbols`/`ops`; expand
  along `edges` (graph nav, the strongest localizer [LocAgent][locagent]); rank by `importance`.
  Return top-5 `{path, symbol, why, evidence, precision}`. New `kb/localize.py` + MCP tool.
- **Exit:** on a small **hand-built, decontaminated** issue set (5–10 ORT issues with known
  fix-files), file-in-top-5 ≥ 70% (spec target). Report the number with the eval harness (M3.1).

### M1.3 — `resolve` orchestrator (G1, FR-9) · L
- Wire **localize → repair → validate** (design §7) as a script that, given an issue, calls the
  MCP tools, asks the agent backend for K candidate patches, runs `find_tests` regression +
  a generated reproduction test, and majority-votes ([Agentless][agentless]). `kb/resolve.py`.
- Patch is **never auto-merged** — output is `{patch, evidence, tests_run}` for human review.
- **Exit:** end-to-end on ≥1 real ORT issue: produces a patch whose repro test goes FAIL→PASS
  with no PASS→FAIL regressions, captured as run evidence (per `/verify`).

**Phase-1 exit gate:** one real Jira-style issue resolved end-to-end with regression safety, and
a localization number on the decontaminated set. *This is the first defensible "it works" claim.*

---

## Phase 2 — Accuracy: make the signals trustworthy

The slice exists; now raise its hit-rate where the research says it matters most.

### M2.1 — Per-symbol L2 summaries (G5, FR-4) · L
- Move L2 leaves from file-level to **symbol-level**, budgeted by `importance` (full summary for
  top-N symbols/file; fold-only for the tail to bound cost). `kb/l2.py` (`build_leaf_prompt`
  takes a symbol range; orchestration iterates symbols, not files).
- MCP `find_symbol` already joins by `path`; extend the join to symbol-id so a symbol query
  returns *its own* summary, not the whole file's.
- **Exit:** `find_symbol("Clip_6::Compute")` returns a symbol-scoped, lint-clean summary; test
  asserts `scope=="symbol"`.

### M2.2 — Precise call-graph tier via scip-clang (G4, FR-2) · XL *(needs a build)*
- Add an optional ingest: if `compile_commands.json` is present, run **scip-clang**, convert SCIP
  occurrences → `edges.jsonl` tagged `xref:precise` (macros + types resolved [scipclang][scipclang]).
  `kb/scip_ingest.py`. Falls back to Tier-A heuristic when absent.
- Keep indirect/virtual edges tagged as **candidate sets** ([LLVM][llvm-cg]).
- **Exit:** on an ORT build, a known virtual-dispatch call resolves to ≥1 precise edge; `localize`
  accuracy on the decontaminated set improves vs M1.2 (report delta).

### M2.3 — Derived-fact invalidation (G6, FR-8) · M
- Extend the dirty-set logic: on a changed file, also invalidate/re-emit the **call & xref edges**
  touching its symbols and mark dependent summaries dirty — not just the file's own facts
  ([Glean][glean]). `kb/incremental.py` (+`dirty_edges`, `dirty_dependents`).
- **Exit:** a unit test where editing a callee's signature marks the caller's edge *and* the
  caller's summary dirty; the firewall still stops where previews are unchanged.

---

## Phase 3 — Trust: prove grounding, enable review

Knowledge an RD can't trust (or promote) is inert. This phase makes trust measurable and
operational.

### M3.1 — Faithfulness/eval harness (G7, NFR) · L
- `kb/eval.py`: (a) **entailment** check — decompose `full` into claims, verify each against the
  cited source span (RAGAS-style, treated as a *screen* given ~0.55 human agreement
  [grouse][grouse]); (b) **entity-trace** — static-extract code entities, verify alignment (ETF
  ~73% F1 [etf][etf]); (c) **calibrated confidence** from token logits, not self-report
  ([calib][calib]).
- Metrics dashboard: lint-clean %, entailment %, localization@5, fix-success on the
  decontaminated set. **No BLEU/ROUGE** ([bleu][bleu]).
- **Exit:** harness runs in CI on the fixture KB; reports entailment ≥85% on the seed summaries;
  fix-success tracked over time.

### M3.2 — Human-review workflow (G8) · M
- Promotion pipeline: `draft → reviewed → battle-tested`. A reviewer CLI/endpoint lists a
  module's drafts with their evidence anchors, accepts/edits/rejects, and stamps `owner` +
  `reviewed_at`. `review_status` already surfaces state. Promotion of an L3 recipe to
  `battle-tested` requires a linked shipped ticket.
- **Exit:** an RD can promote a module's L2 drafts in ≤10 min (spec target); a promoted summary
  flips `review_status` to `reviewed`.

### M3.3 — Prior-fix / experience memory (G3, FR-6) · L
- PR-miner: walk git history for `issue ↔ merged diff ↔ tests touched ↔ outcome` →
  `fixes.jsonl`; MCP `find_prior_fix(issue)`. Feed hits into `resolve` repair (ExpeRepair: +8 pts
  [experepair][experepair]). `kb/mine_fixes.py`.
- **Exit:** `find_prior_fix` returns a relevant past diff for a held-out issue; `resolve` shows a
  measurable fix-success lift when memory is enabled vs ablated (mirror the ExpeRepair ablation).

---

## Phase 4 — Scale & serving hardening

### M4.1 — MCP scale features (G10) · M
- Add **cursor pagination** (`nextCursor`) and the **tools-vs-resources** split (static context
  as read-only resources); **Streamable HTTP** transport beside stdio; **lazy schema loading**
  to avoid the ~75k-token startup tax ([mcp][mcp], [mcp-bloat][mcp-bloat]). `kb/mcp_server.py`.
- **Exit:** a paginated `find_symbol` over a large result set stays within the row budget per
  page; HTTP transport answers `initialize`/`tools/call`.

### M4.2 — L3 semantic search (G9) · M
- Replace `find_recipe` keyword match with embeddings **over the recipe/fixes layer only** (the
  one sanctioned place [§spec 3]), small index + metadata pre-filter ([hnsw][hnsw]). Behind the
  same interface so keyword remains the fallback.
- **Exit:** a paraphrased task ("introduce a new kernel") retrieves `add-an-op`; index rebuild is
  scripted and its "time since full reindex" is tracked.

### M4.3 — Drift sampler & freshness SLO (FR-8) · S
- Periodic random re-derivation + diff vs cache to catch silent staleness; emit a freshness
  metric. **Exit:** sampler flags an intentionally-stale node in a test.

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
| **1** | tests-index, localize, resolve | **1 real issue resolved end-to-end, regression-safe** | L–XL |
| 2 | per-symbol L2, scip-clang, derived invalidation | localization accuracy ↑ vs Phase-1 baseline | XL |
| 3 | eval harness, review workflow, prior-fix memory | entailment ≥85%; fix-success lift from memory | L–XL |
| 4 | MCP scale, L3 semantic, drift | within token budget at scale; freshness SLO met | M |

**Definition of "production-ready" (v1):** Phases 1–3 complete, metrics in `spec.md §5` met on a
**private, decontaminated** eval set (not the public SWE-bench leaderboard, which is inflated
~6–7 pts by test flaws/leakage [openai-drop][openai-drop]), every generated artifact behind the
grounding gate + human-review ladder, and the whole KB rebuildable deterministically.

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
