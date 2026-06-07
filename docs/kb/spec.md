# spec.md — Digital-Colleague Knowledge Base for ML/AI Frameworks

> **One-line goal.** Build a structured, machine-readable, human-verified knowledge base over
> large C/C++ ML-runtime codebases (QNN · SNPE · Hexagon NN · ExecuTorch · ONNX Runtime) so an
> AI "digital colleague" can reliably **locate code and apply the institutional knowledge**
> needed to change it correctly — design a feature or fix a bug — at low token cost and with
> traceable evidence.
>
> **Scope note (current).** The end-to-end *issue→code orchestration* (driving the KB from a
> Jira/GitHub ticket through an automated localize→repair→validate loop) is **deferred** — see
> §7. This document focuses on the **knowledge base itself**: the layers, retrieval, freshness,
> grounding, and the queries an agent uses to understand and safely change the code. The
> issue-resolution research is retained as forward-looking design context, clearly marked.

This is the **what & why**. `design.md` is the architecture; `implement.md` is the phased build
plan. All three are versioned with the `framework/kb/` code they describe.

---

## 0. Status of this document

It is grounded in two things: (a) an audit of what is already built in `framework/kb/`
(1,247 LOC across `l1/l2/lint/incremental/mcp_server`, 16 passing tests, 8 MCP tools, verified
on a real ONNX Runtime checkout), and (b) a 5-angle literature review (June 2026) whose load-
bearing, *falsifiable* findings are cited inline and listed in **§9 References**. Contested
findings are flagged `⚠contested` so we don't build on sand.

---

## 1. The problem

A digital colleague dropped into a 2M-line ML runtime faces two enemies: **not knowing where**
the relevant code is, and **not knowing why** it is shaped the way it is (the unwritten rules).
Naively "give the model the repo" fails three ways:

1. **Token cost / context limits** — you cannot paste 2M lines into context, and MCP tool
   sprawl alone can burn ~75k tokens at session start before any real work
   ([MCP context-bloat analysis][mcp-bloat]).
2. **Chunking severs meaning** — fixed-width embedding chunks split a function from its
   signature/definition; AST-aware chunking measurably beats line chunking (+4.3 Recall@5,
   +2.67 Pass@1) precisely because it keeps units intact ([cAST][cast]).
3. **The highest-value knowledge is not in the code** — registration is macro-generated (so
   parsers miss it), and the institutional "how to add an op safely" lives in people's heads.

The KB exists to convert this into a small set of **cheap, verified, always-fresh lookups** an
agent can query, plus the tacit-knowledge layer model progress cannot erode.

This is **not a chatbot wiki**. It is an **ETL pipeline judged on token cost, freshness, and
fix-success — not human readability.**

---

## 2. Users & the core workflows

**Primary user:** an autonomous/semi-autonomous coding agent ("digital colleague"). **Secondary
users:** the human RD who reviews generated knowledge, and the human who supervises the agent.

**What the agent does with the KB (current scope).** Before changing anything, an agent must
*understand* the code cheaply and correctly. The KB serves these query workflows:

| Agent need | KB capability | Example |
|---|---|---|
| "where does feature/op X live?" | op registry + symbol/structural lookup | `find_op("Clip")` → `math/clip.cc:13` |
| "what does this code do / why?" | grounded L2 summaries (fold/preview/full + citations) | `get_summary("math/clip.cc::Clip_6::Compute")` |
| "what calls this / what's the blast radius?" | call graph (precision-tagged) | `trace_callers("Compute")` |
| "what tests guard this code?" | tests index | `find_tests("Clip_6::Compute")` |
| "how is this kind of change done here?" | L3 recipes / decision trees | `find_recipe("add an op")` |
| "is this knowledge trustworthy & current?" | confidence ladder + freshness | `review_status(...)` |

So the KB's job (current scope) is to make these answers **accurate, grounded, fresh, and
token-cheap**.

**Forward-looking (deferred, §7) — issue→code resolution.** Once the KB is solid, the natural
consumer is an automated **localize → repair → validate** loop over a Jira/GitHub issue
([Agentless: 50.8% on SWE-bench Verified at ~$0.34/issue][agentless]). The research shows three
KB-shaped inputs would raise its success — a **code graph** for localization (LocAgent ~92.7%
file-level [LocAgent][locagent]), the **right tests** (agents without regression context broke
~6.5 pass-to-pass tests/patch [regression][regress]), and **prior-fix experience** (ExpeRepair
+~8 pts pass@1 [ExpeRepair][experepair]). We build the KB *so that* this is possible later, but
the orchestration is out of current scope.

---

## 3. The layered model (locked-in decisions, with evidence)

| Layer | Content | Source | Reviewer | Trust |
|---|---|---|---|---|
| **L1 Structural** | symbols, call graph, module boundaries, **op registry**, **tests index** | mechanical | none | ✓ mechanical |
| **L2 Explanation** | what each file/symbol/module does | LLM from code + git | module owner | ◐ until reviewed |
| **L3 Knowledge** | recipes, decision trees, pitfalls, **prior-fix memory** | human + LLM, PR-mined | senior RD | ? → battle-tested |

**Locked decisions** (each backed by the review):

1. **No chunk-level embeddings over source code.** Anthropic ships Claude Code with *no*
   embedding index — citing staleness, security of stored embeddings, and reliability — and
   reports ~5.5× fewer tokens than an indexing competitor ([Claude Code no-indexing][cc-noindex]).
   For exact identifiers, lexical BM25 beats dense (99.6% vs 99.0%, [MatClaw][matclaw]). We use
   **lexical + structural + agentic navigation** over code.
   - `⚠contested`: at least one controlled study found embeddings beat agent-led retrieval for
     code *completion* (41.7% vs 36.1%, [Reproduction-to-Replication][repro]). The disagreement
     is real and task-dependent; we therefore keep an embedding option *behind an interface*,
     used only where §3.4 allows.
2. **Pre-compute a *light* structural index** (L1) so automated runs don't cold-start. Stable
   **symbol IDs + character-range anchors, never line numbers** — the SCIP model, which survives
   reformatting and enables cross-repo joins ([SCIP][scip]).
3. **The op registry is the single highest-value table.** Registration is macro-generated;
   tree-sitter does not represent C/C++ macros ([tree-sitter-c #7][ts-macros]) and ctags expands
   macros only within one file ([ctags][ctags]) — so a hand-written **macro matcher** is not a
   hack, it is the *only* tool that recovers these symbols without a full build.
4. **Vector/semantic search only over the L3 recipe layer** (natural-language "how do I…"),
   never raw source. Embedding-model upgrades force a full reindex and HNSW recall decays with
   scale, so this layer is kept deliberately small with metadata pre-filtering
   ([HNSW at scale][hnsw]).

### 3.4 Retrieval policy (hybrid, by query type)

The review converges on **hybrid retrieval routed by intent** — no single method wins:

| Query type | Right tool | Evidence |
|---|---|---|
| exact symbol / API / op name | lexical (grep/BM25) + L1 index | BM25 ≥ dense ([MatClaw][matclaw]) |
| "where does X happen" (vocabulary mismatch) | structural graph + agentic nav; semantic as fallback | grep-first agents ([Augment][augment]); failure mode is vocab mismatch ([cc-noindex][cc-noindex]) |
| code localization for an issue | dependency-graph navigation | LocAgent 92.7% ([LocAgent][locagent]) |
| "how do I do X" / conceptual | semantic search over L3 recipes | GraphRAG/global wins ([GraphRAG][graphrag]) |
| global "how does subsystem Y work" | hierarchical summaries (L2 tree) | RAPTOR +20pts QuALITY ([RAPTOR][raptor]); GraphRAG community summaries ([GraphRAG][graphrag]) |

---

## 4. Functional requirements

**FR-1 (L1 op registry).** Extract every op registration → `ops.jsonl` with
`{op_name, version, provider, domain, macro, framework, kernel_path:line}`. Adding a framework =
adding a YAML pattern, no code change. *(Built; verified 378 ops/123 distinct on real ORT.)*

**FR-2 (L1 symbols + call graph).** Symbols with stable IDs + importance + churn; a call graph
**explicitly tagged with precision** (`xref:partial` for heuristic; `xref:precise` only from a
build-aware indexer). Indirect/virtual/dispatch edges are **candidate sets, not ground truth**
— static C/C++ call graphs over-approximate these ([LLVM call-graph][llvm-cg]). *(Built as
heuristic; precise tier is a gap — §6.)*

**FR-3 (L1 tests index).** Map each symbol/file → the tests that cover it (regression set) and
support locating/generating a reproduction test. *(Gap — load-bearing per [regression][regress].)*

**FR-4 (L2 explanations).** For each file/symbol/module, generate `fold`/`preview`/`full` with
`[Lxx]` evidence citations and a declared `evidence_level ∈ {code, inferred, speculation}`,
bottom-up (leaves from source, parents from children's previews). *(Built at file granularity;
per-symbol is a gap — §6.)*

**FR-5 (L2 grounding gate).** No summary enters the KB unless it passes a machine lint:
required fields, `fold ≤ 20` chars, every cited line exists, `code`-claims require ≥1 citation.
Lint runs as a **self-repair loop** (errors fed back to the generator). *(Built.)* This is
*architectural* grounding, which the review prefers over post-hoc detection because a verifier
that shares the generator's model self-confirms — the "hallucination barrier"
([self-correction barrier][barrier]).

**FR-6 (L3 recipes).** Decision-tree recipes ("add an op", "fix a dispatch bug"), retrievable by
task. Confidence ladder: `draft → reviewed → battle-tested` (a real ticket shipped using it).
*(Schema + one stub built; extraction is a gap — §6.)* The companion **prior-fix episodic
memory** (PR-mined `{issue → diff → outcome}`) is **deferred** with the resolution loop (§7).

**FR-7 (Retrieval API / MCP).** Serve the KB over MCP (JSON-RPC 2.0). Every tool is
**token-budgeted** (≤25 rows). Tools join L1+L2+L3 by `path`. *(Built: 8 tools, joined.)*
Adopt MCP's **tools-vs-resources** split and **cursor pagination** ([MCP spec 2025-06-18][mcp])
for budget control (§ gap: pagination + resources).

**FR-8 (Incremental freshness).** On a code change, recompute only the dirty sub-tree
(content-hash + early cutoff). Crucially, **invalidate derived/transitive facts** (call edges,
cross-references, parent summaries), not just the changed file — this is the hard part of
incremental indexing ([Glean ownership][glean]). *(Fold/preview firewall built; derived-fact
invalidation is a gap — §6.)*

**FR-9 (Issue→code workflow) — DEFERRED.** Accept a Jira/GitHub issue and drive
`localize → repair → validate`, returning a candidate patch + the evidence used. *Out of current
scope (§7); the KB is designed so this can be built on top later without rework.*

---

## 5. Non-functional requirements & success metrics

The KB is judged on **token cost, freshness, and fix-success** — not prose quality. Targets are
set *conservatively* because public SWE-bench numbers are inflated by test flaws and solution
leakage (~6–7 pts) and OpenAI has stopped reporting SWE-bench Verified for this reason
([why OpenAI dropped Verified][openai-drop]); we target **decontaminated** evaluation.

Active KB metrics (current scope):

| Metric | Definition | Target (v1) | Stretch |
|---|---|---|---|
| **Retrieval relevance** | NL query → correct symbol/file in top-5 | ≥ 70% top-5 | ≥ 85% ([LocAgent range][locagent]) |
| **Token cost / query** | tokens to answer a retrieval query | ≤ 5k median | ≤ 2k |
| **Grounding** | L2 summaries passing entailment check (cited line supports claim) | ≥ 95% lint-clean; ≥ 85% entailment | ≥ 95% entailment |
| **Coverage** | fraction of high-importance symbols with a reviewed L2 summary | ≥ 80% of top-quartile | ≥ 95% |
| **Freshness** | p95 staleness window after a merge | ≤ 1 build cycle | continuous |
| **Review throughput** | RD minutes to promote a module's L2 draft→reviewed | ≤ 10 min/module | ≤ 5 |

Deferred metric (with §7): **fix-success** — FAIL→PASS and no PASS→FAIL regressions on a
**private/decontaminated** set (target ≥25% v1 / ≥40% stretch). Listed here so the KB metrics
above are chosen to *support* it later.

**Quality-of-evaluation note.** Do **not** measure summary quality with BLEU/ROUGE — they are
empirically *uncorrelated* with human comprehension of code summaries ([human-comprehension
study][bleu]). Use claim-decomposition + source-entailment (RAGAS-style faithfulness, ⚠its
human agreement is only ~0.55 — treat as a screen, not an oracle [GroUSE][grouse]) and static-
analysis entity verification (ETF, ~73% F1 [ETF][etf]). For per-summary confidence, prefer
**token-logit calibration**, not the model's self-reported confidence, which is poorly
calibrated ([calibration study][calib]).

---

## 6. Gap analysis (toward production)

Ranked by leverage on the **KB itself** (current scope). G-IDs are stable (referenced from
`design.md`/`implement.md`); ordering reflects current priority.

| # | Gap | Why it matters | Evidence |
|---|---|---|---|
| ~~G5~~ ✅ | **L2 per-symbol summaries** (FR-4) — *done (M1.1)*: `--granularity symbol`, joined in MCP by symbol id, verified on ORT | symbol queries now get symbol-scoped answers | — |
| **G7** | **No faithfulness/eval harness** (NFR) | can't prove grounding or track drift | [ETF][etf], [QAFactEval][qafe] |
| **G4** | **Call graph is heuristic only** (FR-2) | "what calls this / blast radius" rides on the graph | [LocAgent][locagent]; precise tier = [scip-clang][scipclang] |
| **G6** | **Derived-fact invalidation missing** (FR-8) | stale call edges/summaries → wrong answers | [Glean][glean] |
| **G8** | **No human-review workflow/UI** for L2/L3 promotion | trust ladder is inert | 84% of SE researchers call human eval problematic ([survey][survey]) |
| **G9** | **L3 recipes: 1 stub, keyword search** | tacit layer is the moat | [GraphRAG][graphrag] |
| **G2** | **No tests index** (FR-3) | "what guards this code?" is a core KB query (and later, regression safety) | [regression][regress] |
| **G10** | **MCP: no pagination/resources, single transport** | budget + scale | [MCP spec][mcp] |

**Deferred with the issue→code loop (§7), not part of current scope:**

| # | Gap | Reactivate when |
|---|---|---|
| **G1** | No issue→code workflow (FR-9) | KB metrics (§5) are met and we add the resolution consumer |
| **G3** | No prior-fix/experience memory (FR-6) | building the repair step (+8 pts pass@1 [ExpeRepair][experepair]) |

---

## 7. Scope & non-goals

**In scope (current):** the KB pipeline (L1/L2/L3), retrieval (MCP), freshness, and the QC/eval
harness — i.e. everything needed to make the agent's *understand-the-code* queries (§2) accurate,
grounded, fresh, and cheap.

**Deferred (designed-for, not built now):** the **issue→code orchestration** that *consumes* the
KB — the Jira/GitHub adapter, the `localize → repair → validate` loop, patch generation, and the
prior-fix episodic memory (G1, G3). The architecture (`design.md §7`) keeps this as a clean
downstream consumer so it can be added later without reworking the KB.

**Non-goals (v1):** (a) being a general code-search product (we serve agents, not browsing
humans); (b) embedding all source (explicitly rejected, §3); (c) auto-merging patches without
human supervision; (d) replacing the build-aware indexer — we start with the macro-matcher +
ctags fallback and treat **scip-clang** as a precise-tier *upgrade*, not a v1 dependency, since
it requires a working `compile_commands.json` ([scip-clang][scipclang]).

---

## 8. Risks

- **R1 Over-trust of generated knowledge.** Mitigation: architectural grounding (FR-5),
  confidence ladder, human review gate; never auto-promote.
- **R2 Call-graph imprecision on dispatch/vtable code** (pervasive in ML kernels). Mitigation:
  tag edges as candidate sets; precise tier via scip-clang where a build exists ([LLVM][llvm-cg]).
- **R3 Eval contamination / vanity metrics.** Mitigation: private decontaminated eval set;
  no BLEU/ROUGE; entailment + execution as ground truth ([openai-drop][openai-drop]).
- **R4 LLM-as-judge bias** (position >10% swing, verbosity, self-preference, ⚠magnitude
  contested). Mitigation: execution-grounded validation over LLM judging; if judging, randomize
  order and use multi-persona rubrics ([judge biases][judge]).
- **R5 Freshness debt.** Mitigation: derived-fact invalidation (FR-8) + a drift sampler.

---

## 9. References

[scip]: https://sourcegraph.com/blog/announcing-scip "Announcing SCIP"
[scipclang]: https://sourcegraph.com/blog/announcing-scip-clang "scip-clang"
[ts-macros]: https://github.com/tree-sitter/tree-sitter-c/issues/7 "tree-sitter-c macros"
[ctags]: https://docs.ctags.io/en/latest/parser-cxx.html "Universal Ctags C++ parser"
[llvm-cg]: https://groups.google.com/g/llvm-dev/c/SWIiEBWaJVg "Conservative call graphs in LLVM"
[cast]: https://arxiv.org/abs/2506.15655 "cAST: AST chunking for code RAG"
[raptor]: https://arxiv.org/abs/2401.18059 "RAPTOR"
[graphrag]: https://arxiv.org/abs/2404.16130 "GraphRAG: Local to Global"
[locagent]: https://arxiv.org/abs/2503.09089 "LocAgent"
[augment]: https://jxnl.co/writing/2025/09/11/why-grep-beat-embeddings-in-our-swe-bench-agent-lessons-from-augment/ "Why grep beat embeddings"
[matclaw]: https://arxiv.org/abs/2604.02688 "MatClaw: BM25 vs dense"
[repro]: https://arxiv.org/pdf/2506.19724 "From Reproduction to Replication (contested)"
[cc-noindex]: https://vadim.blog/claude-code-no-indexing "Claude Code has no embedding index"
[agentless]: https://arxiv.org/abs/2407.01489 "Agentless"
[regress]: https://arxiv.org/abs/2510.18270 "Regression tests in SWE resolution"
[experepair]: https://arxiv.org/abs/2506.10484 "ExpeRepair dual-memory"
[openai-drop]: https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/ "Why OpenAI dropped SWE-bench Verified"
[bleu]: https://dl.acm.org/doi/10.1145/3387904.3389258 "Human comprehension vs BLEU/ROUGE"
[etf]: https://arxiv.org/abs/2410.14748 "Entity Tracing Framework"
[qafe]: https://ar5iv.labs.arxiv.org/html/2112.08542 "QAFactEval"
[grouse]: https://arxiv.org/html/2409.06595v3 "GroUSE: evaluating RAG evaluators"
[calib]: https://arxiv.org/abs/2404.19318 "Calibrated confidence for code summaries"
[barrier]: https://arxiv.org/html/2512.12117v1 "Citation-grounded comprehension / hallucination barrier"
[judge]: https://arxiv.org/pdf/2603.01865 "Position bias in code judging"
[survey]: https://arxiv.org/abs/2510.24367 "LLM-as-judge for SE"
[glean]: https://glean.software/blog/incremental/ "Glean incremental ownership"
[mcp]: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports "MCP spec 2025-06-18"
[mcp-bloat]: https://agentmarketcap.ai/blog/2026/04/08/mcp-context-bloat-enterprise-scale-tool-definitions-agent-context-budget "MCP context bloat"
[hnsw]: https://towardsdatascience.com/hnsw-at-scale-why-your-rag-system-gets-worse-as-the-vector-database-grows/ "HNSW at scale"
