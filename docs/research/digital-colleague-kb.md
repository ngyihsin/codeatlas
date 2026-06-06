# Digital-Colleague Knowledge Base for Large Codebases — Research & Architecture

**Doc type:** explanation (research / architecture review)
**Audience:** ML-systems engineers extending docforge-onboard toward "digital colleagues"
**Status:** ◐ literature synthesis (figures from search snippets; see Method)
**Date:** 2026-06-06

> **Goal.** Design an *automatically generated, human-reviewed* knowledge base that lets
> AI "digital colleagues" understand a very large codebase and then act on it — handle
> Jira tickets, develop features, fix bugs — for ML runtime/compiler codebases (QNN,
> SNPE, Hexagon NN, ExecuTorch, ONNX Runtime). It must be cheap in **context/tokens**,
> **auto-generated**, and **owner-reviewed**.

## TL;DR

Design the KB around three properties: **layered, structured, verifiable.**
- **Structured + entry-point maps make *localization* cheap and accurate** — and
  localization quality is the dominant variable in agentic SWE.
- **Layered retrieval (index → drill-down) + on-demand structural search controls tokens** —
  do *not* stuff the repo into context, and do *not* embed the whole repo.
- **Auto-generate drafts → owner review → executable/drift checks** maintains trust;
  grounding alone is never claimed sufficient.

docforge-onboard already provides ~half the substrate (token-budgeted INDEX, invariants
registry, `✓/◐/?` tags + provenance, stable `file → symbol` anchors, agent-reader rules,
task recipes, drift CI). What to **add**: an auto-generation pipeline, a structured
code-graph index layer, a hierarchical-summary layer, and an ML-runtime template.

## Method & confidence

`WebSearch` worked; `WebFetch` was 403-blocked this session, so most figures come from
search-result snippets of the cited primary sources, not full-text PDFs. Vendor
self-reports (Anthropic, GraphRAG, AutoCodeRover repo) and preprints (RANGER, "Navigation
Paradox") are flagged. Confirm exact numbers against primary PDFs before external use.

## 1. Findings by facet (with trade-offs)

### 1.1 Token / context efficiency
- **RAPTOR** (ICLR 2024, arXiv:2401.18059): recursive cluster+summarize tree; QuALITY
  82.6% vs 62.3% prior. Good for cross-file/global understanding; needs offline build.
- **GraphRAG** (Microsoft, 2024; arXiv:2404.16130): KG + hierarchical community summaries;
  wins ~70–80% on *global* questions, per-query tokens 2–70% of full-text summarization —
  but **expensive up-front indexing**, and only wins on *global/sensemaking* queries
  (vector RAG is fine + cheaper for local lookups).
- **Aider repo map** (2023): tree-sitter symbols + PageRank ranked into a **token budget**
  (default ~1k). The closest practical pattern to "million-line repo comprehension."
- **Anthropic Contextual Retrieval** (2024): prepend a doc-aware blurb per chunk;
  retrieval failures −49%–67% (vendor numbers).
- **Agentic on-demand (grep/LSP/AST)** vs vector RAG: coding-agent vendors (Cline,
  Claude Code) deliberately **don't embed the codebase** — chunking severs a function from
  its callers, the index goes stale every commit, and embeddings copy proprietary code.
  **Caveat:** "RAG is dead for code" is experiential, not benchmarked; grep/LSP *is*
  retrieval.
- **Long-context is unreliable**: "Lost in the Middle" (TACL 2024, arXiv:2307.03172) U-shaped
  accuracy; NIAH degrades >64k and is prompt-sensitive (Claude 2.1 ~27% vs ~98% on the same
  test) → **you cannot just stuff the repo**.

### 1.2 Structured code knowledge
- **CPG / Joern** (IEEE S&P 2014): AST+CFG+PDG unified, queryable, fuzzy-parse (no build).
- **SCIP** (Sourcegraph, 2022): replaces LSIF; ~5–8× smaller, ~3× faster; human-readable
  symbol IDs → cross-repo resolution.
- **GitHub Stack Graphs** (2022, arXiv:2211.01224): name-binding as path-finding;
  file-incremental, no build/CI.
- **tree-sitter**: incremental, error-tolerant parsing + query engine; substrate for the
  above and Aider's repo map.
- **Structural/graph retrieval beats embeddings for code**: CodexGraph (NAACL 2024,
  arXiv:2408.03910) 27.9% EM / 67.98% edit-sim on CrossCodeEval-Lite, beating BM25/embeddings;
  RANGER (2025 preprint, arXiv:2509.25257) beats SOTA embeddings on NDCG@10/Recall@10.
- **Stable symbol anchors survive edits** where line numbers don't → our anchor design.

### 1.3 Agentic ticket/bug/feature automation
| System | Mechanism | Score (subset, model, date) |
|---|---|---|
| SWE-bench (arXiv:2310.06770) | 2,294 real issues | original best 1.96% (2023) |
| SWE-agent (arXiv:2405.15793) | Agent-Computer Interface | 12.5% full, GPT-4T, 2024-05 |
| **Agentless** (arXiv:2407.01489) | **localize→repair→validate**, no agent loop | 32% Lite, GPT-4o, ~$0.70, 2024-07 |
| AutoCodeRover (arXiv:2404.05427) | AST search + SBFL | ~22% Lite (v1) |
| CodePlan (arXiv:2309.12499, FSE'24) | dependency-graph plan | 5/7 repos vs 0/7 baseline |
| OpenHands | CodeAct agent | ~53% Verified, 2024-11 |

- **Load-bearing mechanism = fault localization + patch validation.** AST/SBFL/dependency
  graphs shrink the search space; run regression + generated reproduction tests before
  selecting a patch.
- **Warning:** OpenAI declared **SWE-bench Verified contaminated** (2026-02): 59.4% of
  audited failures had test/description defects; models reproduce gold patches. → **Build an
  internal eval on your own tickets.**

### 1.4 Auto-generation + review + anti-drift
- **DeepWiki** (Cognition): repo → navigable wiki with line-links; still warns LLM hallucination
  applies → verify load-bearing claims at source.
- **Hallucination is real and unbounded**: package hallucination 19.7%, 43% recurring
  ("slopsquatting", arXiv:2406.10279); code-hallucination taxonomies (CodeHalu, AAAI'25).
- **Grounding lowers it**: RAG cut hallucinated steps ~21% → <7.5% (NAACL 2024,
  aclanthology.org/2024.naacl-industry.19) — the strongest single datapoint.
- **No canonical rate**: domain spread ~1.5% (clinical) to 45–75% (multi-doc summarization).
- **Anti-staleness**: executable docs (doctest / `pytest --doctest-modules`, most proven) +
  AST-anchored drift linters in CI.
- **Review gate**: CODEOWNERS; **Diátaxis** to type docs.
- **Convergent rule: grounding + a human-approval gate, neither alone.**

## 2. ML runtime/compiler: one pipeline, many names

(Confirmed from ONNX Runtime headers, ExecuTorch docs, Hexagon `hexagon_nn.h` — direct
source; QNN/SNPE from official titles/snippets, pages 403-gated.)

| Stage | ONNX Runtime | ExecuTorch | QNN | SNPE | Hexagon NN |
|---|---|---|---|---|---|
| Graph IR | ONNX Graph | Edge/ExportedProgram | QNN graph | DLC | node-id graph |
| **Op/kernel registry** | `KernelRegistryManager` | `EXECUTORCH_LIBRARY` | op package | UDO package | `ops.def` |
| **Backend / EP / delegate** | `IExecutionProvider` | `BackendInterface`+`Partitioner` | `libQnn*.so` | runtimes | host API + DSP skel |
| Partitioner | `GetCapability()` | `Partitioner.partition()` | converter/EP | converter | manual append |
| Lowering / opt passes | `GraphTransformer` (4 levels) | `to_backend`/`preprocess` | converter+graph prep | converter+quant | `hexagon_nn_prepare` |
| Memory planning | allocators/arena | memory-planning pass | graph finalize | runtime | prepare |
| Execute | `Compile`→`NodeComputeInfo` | `execute()` | QnnGraph execute | runtime execute | `hexagon_nn_execute` |

**Two universal extension axes (document each separately):**
- **Add an operator** = touch the op/kernel registry.
- **Add a backend** = implement the EP/delegate interface + a partitioner.

Key **invariants**: quantization rules, data layout, backend ABI, DSP/HTP memory & threading.

## 3. Recommended end-to-end architecture (tuned for ML runtimes)

**Retrieval layers (token-controlled):**
- **L0 doc instance** (= docforge-onboard instance): OVERVIEW / CONCEPTS (data structures +
  *why*) / FLOWS ("Life of an inference", "Life of a lowering") / API (registry + EP
  interface) / INDEX (machine map + invariants), all token-budgeted, anchored, tagged.
- **L1 structured code graph** (new): tree-sitter + LSP/SCIP symbol graph + call/dependency
  graph → feeds anchors and **localization**. Generated, not hand-maintained.
- **L2 hierarchical summaries** (new, RAPTOR/GraphRAG-style): module → subsystem → global,
  for global questions, token-tiered.
- **Retrieval policy:** INDEX route → grep/LSP/graph → read source by anchor. No whole-repo
  embedding; contextual-retrieval embeddings only as a recall fallback.

**Generation pipeline:** generator agent runs the onboarding phases → drafts (`◐`) →
CODEOWNERS owner review (`◐→✓`) → merge; drift CI (`check-doc-drift` + doctest-style
executable how-tos) regenerates affected sections on code change.

**Agent task loop (tickets):** localize (L1 graph + INDEX entry points + invariants) → plan
(CodePlan-style dependency-aware) → patch → validate (regression + generated reproduction
tests, Agentless-style) → open PR for human review.

**Trust loop:** `✓/◐/?` gate actions; invariants registry as guardrails; commit provenance +
drift detection.

## 4. docforge-onboard: have vs add

| Capability | Have | Add |
|---|---|---|
| Token-budgeted machine index | ✅ INDEX / CLAUDE.md + **L2 `build-summary-tree.sh`** (global→subsystem→module skeleton; prototyped) | upgrade: LLM/embedding abstractive summaries (RAPTOR/GraphRAG) |
| Structured localization | ✅ stable anchors + **L1 symbol index/repo-map + `find-symbol`** (ctags+rg; prototyped in `framework/tools/`) | richer upgrade: tree-sitter/LSP/SCIP/stack-graphs |
| Trust / anti-drift | ✅ tags + provenance + drift CI | **executable (doctest-style) how-tos** |
| Auto-generation + review | ✅ **`generate-instance.sh` (deterministic draft) + `GENERATION.md` pipeline** (generator-agent loop + CODEOWNERS gate + drift CI); prototyped | upgrade: a fully autonomous generator agent run in CI |
| Ticket automation | ✅ task recipes | **localize→plan→patch→validate loop + internal eval** |
| ML-runtime specialization | ◐ generic template | **7-stage + 2-axis template + example instance** |
| Multi-department | ✅ framework/instance planes | cross-department meta-index |

## 5. Open problems / risks
1. Hallucination has no fixed rate; vendor numbers self-reported → grounding + human gate + eval.
2. SWE-bench Verified contaminated (2026) → build an internal benchmark on real tickets.
3. "Agentic > RAG for code" is asserted, not benchmarked → use hybrids (graph + BM25/embeddings).
4. Graph index adds build/latency cost → hybrid retrieval.
5. QNN/SNPE docs gated/licensed → generate inside the org; re-verify anchors on the real source.
6. Long-context unreliable → route + read on demand, don't stuff.

## 6. Suggested next steps
1. Build an **ML-runtime example instance** on ONNX Runtime (open source, runnable) — done as
   `examples/onnxruntime-onboarding-notes/` (anchors vs ORT `main`; behavior verified via
   `onnxruntime` pip).
2. ~~Add an **L1 code-graph tool**~~ — **done (prototype):** `framework/tools/build-symbol-index.sh`
   (symbol table + token-budgeted repo map) and `find-symbol.sh` (localize a symbol → `file →
   symbol` anchor + refs), via universal-ctags + ripgrep. Validated against real Redis/pybind11
   source (resolves the very anchors the example instances cite). Next: upgrade to
   tree-sitter/LSP/SCIP for scope-accurate, cross-repo resolution.
3. ~~Prototype the **generator agent + drift/doctest CI**~~ — **done (prototype):**
   `framework/tools/generate-instance.sh` drafts an instance from a checkout (scaffold + L1
   index + seeded structural map/entry points/candidate concepts/provenance), and
   `framework/GENERATION.md` specifies the generate → owner-review (CODEOWNERS, `◐→✓`) →
   drift-CI loop. Next: wire a fully autonomous generator-agent run in CI.
4. Build an **internal SWE-bench-style eval** from your own tickets; measure localization
   accuracy and patch pass-rate.

## Sources (selected; dates inline; verify figures against primary PDFs)
RAPTOR arXiv:2401.18059 · GraphRAG MS-Research blog 2024-07 + arXiv:2404.16130 · Aider repo
map aider.chat/2023/10/22/repomap.html · Contextual Retrieval anthropic.com/news/contextual-retrieval
2024-09 · Lost in the Middle arXiv:2307.03172 · NIAH github.com/gkamradt/LLMTest_NeedleInAHaystack ·
CPG IEEE S&P 2014 · SCIP sourcegraph.com/blog/announcing-scip 2022 · Stack Graphs arXiv:2211.01224 ·
tree-sitter tree-sitter.github.io · CodexGraph arXiv:2408.03910 · RANGER arXiv:2509.25257 (preprint) ·
SWE-bench arXiv:2310.06770 · SWE-agent arXiv:2405.15793 · Agentless arXiv:2407.01489 · AutoCodeRover
arXiv:2404.05427 · CodePlan arXiv:2309.12499 · OpenHands openhands.dev/blog · SWE-bench Verified
contamination openai.com/index/why-we-no-longer-evaluate-swe-bench-verified 2026-02 · RAG-vs-hallucination
aclanthology.org/2024.naacl-industry.19 · slopsquatting arXiv:2406.10279 · CodeHalu arXiv:2405.00253
(AAAI'25) · Diátaxis diataxis.fr · doctest docs.pytest.org · ONNX Runtime `execution_provider.h` /
graph-optimizations docs · ExecuTorch `compiler-delegate-and-partitioner.md` · Hexagon `hexagon_nn.h`
(MACE mirror) · QNN/SNPE docs.qualcomm.com / developer.qualcomm.com (403-gated)
