# leverage.md — Build vs. Reuse: how we leverage existing projects

Companion to `spec.md`/`design.md`/`implement.md`. For each active gap we **opened the actual
projects** (repos/specs/`pyproject.toml`, verified 2026-06-07) and decided, with an integration
lens, whether to **REUSE** (call a library/tool), **TARGET** (emit/ingest a format/spec), or
**PATTERN** (imitate the algorithm, no dependency). The governing constraint is our
**dependency-light** identity: stdlib + PyYAML, LLM via the `claude` CLI subprocess. Anything that
drags in torch/LangChain/OpenAI-SDK/telemetry is rejected unless gated behind an optional extra.

## Master decision table

| Gap | Need | Decision | What we take | What we reject (and why) |
|---|---|---|---|---|
| **G4** | precise C/C++ call graph | **REUSE `scip-clang` + TARGET SCIP** | run the prebuilt binary; ingest `scip print --json` with stdlib `json` | protobuf runtime (no Py SCIP lib); stack-graphs (no C/C++, archived); Kythe/Glean (Bazel/Haskell, too heavy) |
| **G7** | faithfulness/eval | **PATTERN (reimplement)** | claim-decompose + per-claim NLI-entailment on `claude`; ETF entity pass | RAGAS (LangChain+OpenAI+embeddings), DeepEval (OpenAI SDK + default telemetry), QAFactEval (dependency-rotten) |
| **G9** | L3 semantic search | **REUSE `sqlite-vec`** + PATTERN L2 | sqlite-vec store (zero-dep, ~163 KB); MiniLM via ONNX or embed-API | GraphRAG (Azure, whole-corpus cost), RAPTOR-as-lib (torch+umap), full `sentence-transformers`/torch, LlamaIndex/Haystack frameworks |
| **G10** | MCP compliance | **TARGET (hand-rolled)** | implement 2025-06-18 wire shapes ourselves | MCP Python SDK/FastMCP (~14 deps; solves only ~1.5/4 of our items) |
| **G6** | derived-fact invalidation | **PATTERN** | Salsa early-cutoff + Glean ownership; **wire our existing `compute_dirty`** | Salsa/Bazel/Glean code (Rust/Go/Haskell — not importable) |
| **G5** | per-symbol L2 | **own work** | — | — |
| **G2** | tests index | **own + stdlib/ctags** | ctags/macro parse of test files; optional gcov/llvm-cov coverage | heavy coverage frameworks |

**Net new third-party dependencies this implies: exactly one mandatory** — `sqlite-vec` (a 163 KB
SQLite extension riding the stdlib `sqlite3`) — plus two **external tools invoked as subprocesses,
not imported** (`scip-clang`, and `scip`/`onnxruntime` only if used). Everything else is PATTERN
(code we write) or behind an optional `extras` install. This preserves the dependency-light goal.

---

## G4 — precise call graph: REUSE scip-clang, TARGET SCIP

**Decision.** Where a `compile_commands.json` exists, run **scip-clang** (Apache-2.0, Clang-21,
prebuilt **x86_64-Linux** binary — no build) to produce `index.scip`, then ingest via
`scip print --json index.scip` parsed with **stdlib `json`** (avoids the protobuf runtime — there
is *no maintained Python SCIP library*; issue #259 closed not-planned). Files outside the compile
DB keep the ctags/macro-matcher heuristic tier. The `precision` field on each edge distinguishes
`"precise"` vs `"heuristic"`.

**How a SCIP index becomes our `edges.jsonl`:**
1. `scip-clang --compdb-path=compile_commands.json` → `index.scip`
2. `scip print --json index.scip` → JSON
3. symbols → `symbols.jsonl` (`id=symbol` FQN string, `name=display_name`, `kind`, `path=document.relative_path`, `signature=signature_documentation`)
4. for each *reference* occurrence (no `Definition` role bit), the function whose `enclosing_range`
   contains the occurrence is the **caller**; the occurrence's `symbol` is the **callee** → emit
   `{caller, callee, precision:"precise"}`.

**Caveats (real):** requires a working `compile_commands.json` per project (the genuine cost);
prebuilt binaries don't cover arm64-Linux / x86_64-macOS; SCIP symbol strings are stable FQNs we
can adopt as canonical ids. Sources: [scip.proto], [SCIP symbol grammar], [scip CLI], [scip-clang],
[no-Python issue].

---

## G7 — faithfulness/eval: PATTERN reimplementation (~150 LOC)

**Decision.** Reimplement the claim-decompose + entailment algorithm (shared by RAGAS/DeepEval) on
our existing `claude` subprocess — *no framework*. RAGAS would pull LangChain + OpenAI SDK **and**
an embeddings model; DeepEval bundles the OpenAI SDK + pytest/OTel + **default-on Sentry/PostHog
telemetry**; QAFactEval pins `allennlp==1.1.0`/`torch<1.7` and is unmaintained. ETF (the only
*code-summary*-specific method, 73% F1) is **paper-only** — we reimplement its entity pass.

**Harness (`kb/eval.py`):**
1. parse claims + their `[Lxx]` refs from the summary (our lint already proves the lines exist).
2. **claim-decompose** — one `claude` call → atomic claims tagged with cited spans.
3. **per-claim entailment** — one `claude` call per claim: "given ONLY these cited lines, is the
   claim ENTAILED / NEUTRAL / CONTRADICTED?" via structured JSON output. A non-entailed claim is
   the *accuracy* failure the lint can't catch.
4. **ETF-style entity pass** (optional) — statically extract code entities, match summary entities,
   verify each against its cited span (catches wrong-method/param hallucinations).
5. **score** = entailed/total; **confidence** via self-consistency (K runs) + a post-hoc isotonic
   fit — because **the Claude backend exposes no logprobs**, calibration cannot use token
   probabilities.
6. **optional** `SummaC` (NLI, torch) behind an `extras` install as a non-LLM second opinion.

Sources: [RAGAS], [DeepEval], [SummaC], [QAFactEval issue], [ETF].

---

## G9 — L3 semantic search: REUSE sqlite-vec, PATTERN the hierarchy

**Decision.** Keep our own L2 hierarchy (borrow RAPTOR's *soft-clustering* idea and LlamaIndex's
*auto-merging retrieval* pattern in ~tens of lines — neither as a dependency; RAPTOR isn't on PyPI
and its clustering imports torch+umap+sklearn; GraphRAG is Azure-leaning with whole-corpus LLM
cost). Add semantic search **over the NL recipe layer only** (never source) with:
- **store:** **`sqlite-vec`** (MIT/Apache-2.0, ~163 KB wheel, zero Python deps, rides stdlib
  `sqlite3`) — by far the lightest option; brute-force cosine is fine at recipe scale (no ANN).
- **embeddings:** `all-MiniLM-L6-v2` (384-dim, ~80 MB) run via **ONNX Runtime** (no torch) for
  offline/no-key, or an **embedding API** for zero local ML deps. Avoid full `sentence-transformers`
  (pulls torch).

**Sketch:** embed each recipe's NL text → upsert into a `vec0` table in `recipes.sqlite` with a
pointer back to the recipe + its L2 parent; query embeds the task → `... WHERE embedding MATCH ?
ORDER BY distance LIMIT k`; keyword match stays as the fallback behind the same `find_recipe`
interface. Sources: [sqlite-vec], [RAPTOR], [GraphRAG].

---

## G10 — MCP compliance: TARGET (stay hand-rolled)

**Decision.** Implement the **MCP 2025-06-18** wire shapes by hand; do **not** adopt the Python
SDK. The SDK pulls ~14 required deps (pydantic/starlette/uvicorn/opentelemetry/pyjwt+crypto…),
negating our dependency-free server, and FastMCP gives us **none** of pagination/lazy-listing (it
registers tools eagerly; pagination is low-level `Server` only) — i.e. we'd pay the full dep cost
and still hand-roll the two items we most need. Reference servers (filesystem, git) confirm a
minimal tools-first server is idiomatic.

**Implement:** bump `protocolVersion` to `"2025-06-18"`; **opaque base64 offset cursors** with a
`nextCursor` for `tools/list` and for tool results (**fixes the current silent-truncation bug** —
today `hits[:BUDGET]` truncates with no cursor, so truncated is indistinguishable from complete);
`resources/list`+`resources/read` for the application-driven artifacts (`module_map.md`, per-module
summaries as `kb://summary/<path>`, `kb://ops`) while keeping the 8 lookups as model-driven tools;
a ~80-line **stdlib `http.server`** Streamable HTTP endpoint (POST→`handle`, localhost-bound,
validate `Origin`); lazy `TOOLS` built on first `tools/list`. Encode a build/sort epoch in cursors
and reject stale ones with `-32602`. Sources: [pagination spec], [resources spec], [transports
spec], [python-sdk], [reference servers].

---

## G6 — derived-fact invalidation: PATTERN (and wire our dead code)

**Decision.** All canonical systems (Salsa, Bazel, Turborepo, Glean) are Rust/Go/Haskell —
**PATTERN-only**. The primitives already exist in `incremental.py` (`input_hash`, `compute_dirty`,
`changed_symbols`) and are tested — but **`compute_dirty` is never called by the pipeline** (dead
code). The work is wiring, not new machinery:

1. **content-hash change detection** (Turborepo/Bazel): persist per-file source hashes; high-
   durability inputs (`registration_patterns.yaml`, vendored dirs) get a coarse counter (Salsa
   durability) so unchanged ones are skipped.
2. **edge invalidation by ownership** (Glean): edges are *owned by the caller file* — on change,
   delete edges whose caller is in a changed file and re-run `build_edges` **only over those
   files** (today `l1.build` rebuilds all edges every run).
3. **early cutoff / backdating** (Salsa): recompute a changed leaf; if its `fold`/`preview` is
   byte-identical, **do not propagate** (input changed, output didn't).
4. **caller cascade with firewall**: call the existing `compute_dirty(changed, edges,
   fold_changed)` and re-summarize only the dirty set — propagation continues up only through
   symbols whose fold changed.

**Caveat:** the firewall's correctness depends on edge accuracy; our heuristic edges can miss a
call, so a **periodic full rebuild** stays as a backstop. Sources: [Salsa algorithm], [Salsa
durability], [Glean incremental].

---

## Two findings about *our* code (from reading it, not the literature)

- **MCP silent truncation (bug).** `find_*` returns `hits[:BUDGET]` with no `nextCursor` — a
  truncated result is indistinguishable from a complete one. Fixed by the G10 cursor work.
- **`compute_dirty` is dead code.** The fold-firewall cascade is implemented and tested but never
  invoked by `l1.build`/`l2.build`; G6 is mostly wiring it in.

---

## References

[scip.proto]: https://raw.githubusercontent.com/sourcegraph/scip/main/scip.proto
[SCIP symbol grammar]: https://github.com/sourcegraph/scip/blob/main/docs/scip.md
[scip CLI]: https://github.com/sourcegraph/scip/blob/main/docs/CLI.md
[scip-clang]: https://github.com/sourcegraph/scip-clang
[no-Python issue]: https://github.com/sourcegraph/scip/issues/259
[RAGAS]: https://github.com/explodinggradients/ragas
[DeepEval]: https://github.com/confident-ai/deepeval
[SummaC]: https://github.com/tingofurro/summac
[QAFactEval issue]: https://github.com/salesforce/QAFactEval/issues/2
[ETF]: https://arxiv.org/abs/2410.14748
[sqlite-vec]: https://github.com/asg017/sqlite-vec
[RAPTOR]: https://github.com/parthsarthi03/raptor
[GraphRAG]: https://github.com/microsoft/graphrag
[pagination spec]: https://modelcontextprotocol.io/specification/2025-06-18/server/utilities/pagination
[resources spec]: https://modelcontextprotocol.io/specification/2025-06-18/server/resources
[transports spec]: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
[python-sdk]: https://github.com/modelcontextprotocol/python-sdk
[reference servers]: https://github.com/modelcontextprotocol/servers
[Salsa algorithm]: https://salsa-rs.github.io/salsa/reference/algorithm.html
[Salsa durability]: https://rust-analyzer.github.io/blog/2023/07/24/durable-incrementality.html
[Glean incremental]: https://glean.software/blog/incremental/
