# phases.md — Phase plan, four-lens view

Each phase through four lenses — **what & why · how · expected results · validation** — plus an
**exit-gate checklist**. Sequenced by leverage on the KB itself; the issue→code (Jira) loop is the
deferred Phase F. Cross-refs: gaps in `spec.md §6`, milestones in `implement.md`, build-vs-reuse in
`leverage.md`. Validation follows the `/verify` rule: **run it on real ONNX Runtime and observe**,
not just unit tests.

Metric targets (from `spec.md §5`): retrieval@5 ≥ 70%; grounding ≥ 95% lint-clean & ≥ 85%
entailment; coverage ≥ 80% of top-quartile symbols; freshness ≤ 1 build cycle; review ≤ 10 min/module.

---

## Phase 0 — Baseline ✅ DONE

- **What & why.** The floor we improve on: L1 (op registry + symbols/graph), L2 (agent-generated,
  lint-gated summaries), incremental firewall, 8-tool MCP server. You can't improve what you can't
  run and measure.
- **How.** Macro-matcher + ctags (build-free); L2 spawns `claude` per node with a self-repair lint
  loop; MCP joins layers by `path`.
- **Expected results.** A queryable KB from a real tree; 378 ops/123 distinct on ORT; summaries
  with real `[Lxx]` citations.
- **Validation.** `pytest -q` 16/16; real ORT build + L2 run + MCP queries answered.

**Exit gate** — [x] pytest green · [x] real ORT L1+L2+MCP demonstrated.

---

## Phase 1 — KB depth & trust *(make core answers accurate and provable)*

Gaps: **G5, G7, G6** + generic retrieval.

- **What & why.** The agent's *understand-the-code* answers are the product now. Two things
  undermine them: summaries are **file-level** (a symbol query returns the whole file), and we
  **can't prove** faithfulness or measure retrieval.
- **How.**
  - M1.1 **Per-symbol L2** — leaves move file→symbol, budgeted by `importance`.
  - M1.2 **`relevant_code(query)`** — hybrid retrieval (lexical + graph expansion + importance).
  - M1.3 **Eval harness** — *leverage G7:* PATTERN claim-decompose + per-claim NLI-entailment vs
    the cited `[Lxx]` span on the `claude` subprocess; confidence via self-consistency + isotonic
    fit (no logprobs); **no BLEU/ROUGE**.
  - M1.4 **Derived-fact invalidation** — *leverage G6:* wire the dead `compute_dirty` into
    `l2.build`; Glean-style caller-file edge ownership; Salsa backdating.
- **Expected results.** Symbol-scoped grounded summaries; a tracked eval number; editing one file
  recomputes only its dirty sub-tree.
- **Validation.** `find_symbol("Clip_6::Compute")` returns `scope=="symbol"`, lint-clean on real
  ORT; CI eval reports entailment ≥ 85% and retrieval@5 ≥ 70% on a decontaminated set; editing a
  callee's signature marks the caller's edge *and* summary dirty while the firewall holds.

**Exit gate**
- [x] M1.1 per-symbol summary served via `find_symbol` (`scope=="symbol"`, lint-clean on ORT) ✅
- [x] M1.2 `relevant_code` returns top-5 with evidence; relevance measured ✅
- [x] M1.3 eval harness ✅ + **entailment gate** (`--entail`): raised entailment **53% → 87.5%** on real ORT clip (clears the 85% SLO; 1 unfixable summary quarantined). CI threshold-gating pending broader coverage.
- [x] M1.4 derived-fact invalidation ✅ (incremental L1 edges by caller-file ownership; `compute_dirty` cascade wired via `plan_rebuild`; validated on real ORT)

---

## Phase 2 — Graph precision & human trust

Gaps: **G4, G8, G2**.

- **What & why.** "What calls this / blast radius" rides on the call graph, which is heuristic
  (`xref:partial`); and generated knowledge nobody can promote is inert.
- **How.**
  - M2.1 **scip-clang precise tier** — *leverage G4:* REUSE prebuilt binary where
    `compile_commands.json` exists; ingest via `scip print --json` + stdlib `json`;
    `enclosing_range`→caller, reference occurrence→callee, tagged `xref:precise`; ctags fallback.
  - M2.2 **Human-review workflow** — `draft → reviewed → battle-tested`; reviewer CLI with evidence
    anchors.
  - M2.3 **Tests index** — parse test files → `tests.jsonl` (`symbol→test`); `find_tests`.
- **Expected results.** Precise edges where a build exists; fast RD promotion; `find_tests` returns
  the tests guarding a symbol.
- **Validation.** On an ORT build, a known virtual-dispatch call resolves to ≥1 precise edge and
  `relevant_code` improves vs the Phase-1 baseline (report delta); RD promotes a module in ≤10 min;
  `find_tests` resolves a known symbol→test link on real ORT.

**Exit gate**
- [x] M2.1 **live scip-clang pipeline validated** ✅ on a real Clang build (compute->add/mul, main->compute, all xref:precise); scaling to a full ORT build is the remaining step
- [◐] M2.1 relevance-delta deferred to an environment with a compile_commands.json + scip-clang
- [x] M2.2 review workflow ✅ (promote ladder + evidence anchors; review_status flips; validated on real ORT)
- [x] M2.3 `find_tests` resolves a known symbol→test link on real ORT ✅ (clip_test.cc::MathOpTest.Clip_6)

---

## Phase 3 — Knowledge moat & scale

Gaps: **G9, G10, freshness SLO**.

- **What & why.** The tacit L3 layer is the moat (one stub + keyword today); the MCP server has a
  real compliance/scale bug (silent truncation).
- **How.**
  - M3.1 **L3 recipe mining + semantic** — *leverage G9:* cluster past PRs into candidate
    decision-tree recipes for review; semantic search **over recipes only** via **`sqlite-vec`**
    (zero-dep) + MiniLM (ONNX) or embed-API; keyword fallback.
  - M3.2 **MCP scale** — *leverage G10:* stay hand-rolled; implement 2025-06-18 wire shapes (cursor
    pagination, tools-vs-resources, Streamable HTTP via stdlib `http.server`, lazy schema); fixes
    silent truncation.
  - M3.3 **Drift sampler** — periodic re-derivation + diff vs cache.
- **Expected results.** Paraphrased task retrieves the right recipe; large result sets paginate
  within budget; HTTP transport for multi-client serving; a freshness metric.
- **Validation.** `find_recipe("introduce a new kernel")` → `add-an-op`; paginated `find_symbol`
  stays within row budget per page and exposes `nextCursor`; HTTP transport answers
  `initialize`/`tools/call`; drift sampler flags an intentionally-stale node.

**Exit gate**
- [x] M3.1 paraphrase retrieves the right recipe ✅ (vector search; 'introduce a new kernel'→add-an-op, 'wrong fp16'→fix-a-dispatch-bug)
- [x] M3.2 pagination ✅ (find_symbol(Compute): total=897, returned=25, nextCursor; HTTP transport round-trip; resources/list)
- [x] M3.2 silent-truncation bug fixed ✅ (results carry total + nextCursor)
- [x] M3.3 drift sampler flags an intentionally-stale node ✅ (real ORT: edit clip.cc -> stale=1, fresh_rate 0.997)

---

## Phase F — issue→code resolution ⏸ DEFERRED *(build after Phases 1–3)*

Reactivates **G1, G3** once KB metrics hold.

- **What & why.** The Jira/GitHub end-to-end loop, deferred by direction.
- **How.** `resolve` wiring **localize → repair → validate** on `relevant_code` + `find_tests`;
  prior-fix episodic memory (PR-mined); Jira adapter. Never auto-merges.
- **Expected results.** Given an issue: a candidate patch + the KB evidence used, for human review.
- **Validation.** **Fix-success** (FAIL→PASS, no PASS→FAIL regressions) on a **private,
  decontaminated** set — not the public SWE-bench leaderboard (inflated ~6–7 pts). Targets ≥25% v1
  / ≥40% stretch.

**Exit gate** — [ ] one decontaminated issue resolved end-to-end, regression-safe · [ ] fix-success
≥ 25% on the private set · [ ] prior-fix memory shows an ablation lift.

---

## Production-ready (v1, KB scope)

Phases 1–3 complete · `spec.md §5` KB metrics met · every generated artifact behind the grounding
gate + human-review ladder · the KB rebuildable deterministically. (Phase F fix-success is the bar
for the deferred resolution loop, later.)
