# CodeAtlas Unified Architecture Spec (v1)

**Purpose**: A single, generalized specification that the personal
CodeAtlas implements. It consolidates (a) the proven layered
architecture, (b) semantic retrieval over institutional knowledge
(cases/features), and (c) the agent memory layer (`record_finding`
write-back). Any deployment-specific implementation (e.g. an internal
company instance) is treated as *one implementation of this spec* with
its own connectors and LLM providers plugged in.

**Clean-room rule**: This spec defines concepts, schemas, and
interfaces. Implementations MUST NOT share code files across
IP boundaries. Anything organization-specific (internal LLM gateways,
internal system names, org-specific codebase registries) lives behind
the pluggable interfaces in §7 and never in this spec.

---

## 1. Layered model

| Layer | Name | Content | Source of truth | Mutability |
|---|---|---|---|---|
| L1 | Structural | Symbols, call edges, reference edges, build-target mapping | Source tree (derived via parsers) | Rebuilt on demand |
| L2 | Semantic | LLM-generated summaries (fold / preview / full tiers) | Derived from L1 + source | Regenerated when span_hash changes |
| L3 | Institutional | Features, Cases, Docs — mined from issue trackers, review systems, wikis, local docs | YAML files (`features.yaml`, `cases.yaml`, `docs.yaml`) | Human/pipeline curated |
| M | Memory | Agent findings — uncurated observations, gotchas, dead ends, hypotheses | `memory.sqlite` (PRIMARY data) | Agent-written, human-curated, promotable to L3 |

Design invariants:

1. **Knowledge vs. memory separation.** L1–L3 describe the codebase's
   current facts and curated history. M is uncurated agent experience.
   Different lifecycles, different trust levels, different storage.
2. **Derived vs. primary storage.** `index.sqlite` is fully derived
   (rebuildable from source + YAML at any time). `memory.sqlite` is
   primary — an index rebuild must never touch it.
3. **Confidence discipline.** `Confidence = "verified" | "speculation"
   | "read_only"`, default `"speculation"`. Agents can never set
   `"verified"`. Applies to all four layers.
4. **Staleness anchors.** Every record that references code carries
   `span_hash` (symbols) or `symbol_span_hashes` (findings) plus
   `verified_at_commit`, enabling drift detection in `verify`.

## 2. Storage layout

```
.codeatlas-data/<codebase>/
  draft/                     # pipeline intermediates (symbols.jsonl)
  index.sqlite               # DERIVED: L1 + L2 + L3 mirrors + vec tables
  memory.sqlite              # PRIMARY: findings (WAL mode)
features.yaml, cases.yaml, docs.yaml   # L3 source of truth
```

### 2.1 index.sqlite (derived)

Tables (superset of current implementations):

- `symbols` (+ `symbols_fts`, `vec_symbols`) — as today, including
  `runs_on` generalized to `hardware_tag TEXT` (values are
  deployment-defined, e.g. `dsp|host|npu|gpu`; spec does not enumerate).
- `symbol_edges (from_id, to_id, edge_type)` — `calls` and
  `references` edge types, never mixed in one query.
  **Normative:** the JSON `callers`/`callees`/`referenced_by` columns
  on `symbols` are a read-only derived cache generated from
  `symbol_edges` at index time. `symbol_edges` is the single source
  of truth for graph queries.
- `docs` (+ `docs_fts`, `vec_docs`) — as today.
- **NEW** `cases` (+ `cases_fts`, `vec_cases`) — mirror of
  `cases.yaml` essential queryable fields (id, title, status,
  root_cause, fix_summary, lessons, affected_symbols,
  affected_modules, url, confidence). YAML remains source of truth;
  table is dropped/rebuilt by `index`.
- **NEW** `features` (+ `features_fts`, `vec_features`) — same
  pattern (id, title, status, summary tiers, affected_*, url).

Embedding text composition:

- Case: `title + root_cause + fix_summary + "\n".join(lessons)`
- Feature: `title + summary_full` (fallback preview/fold)
- Content-hash stored alongside `embedding_id`; `sync`/`embed`
  re-embeds only on hash change (incremental discipline).

### 2.2 memory.sqlite (primary)

```sql
CREATE TABLE findings (
  id TEXT PRIMARY KEY,              -- "finding-" + short uuid
  created_at TEXT NOT NULL,         -- ISO 8601 UTC
  author TEXT NOT NULL,             -- agent/session identifier
  codebase TEXT NOT NULL,
  text TEXT NOT NULL,               -- length-capped (default 2000)
  kind TEXT NOT NULL DEFAULT 'observation'
    CHECK(kind IN ('observation','gotcha','dead_end',
                   'root_cause_hypothesis')),
  symbol_ids TEXT,                  -- JSON array
  symbol_span_hashes TEXT,          -- JSON obj: symbol_id -> span_hash
  confidence TEXT NOT NULL DEFAULT 'speculation',
  status TEXT NOT NULL DEFAULT 'active'
    CHECK(status IN ('active','stale','promoted','rejected')),
  promoted_case_id TEXT
);
-- + findings_fts (FTS5 over text, kind). Embeddings: deferred until
-- usage data justifies the cost.
```

WAL mode; transactional writes (HTTP team-server implies concurrent
writers).

## 3. Pipelines

```
CODE PIPELINE      extract -> summarize -> enrich -> index -> embed
                   (parsers)   (LLM)      (LSP/idx)  (sqlite) (vec)

KNOWLEDGE PIPELINE ingest -> index -> embed
                   (connectors -> features/cases/docs.yaml)

MEMORY PATH        record_finding (MCP write) -> memory.sqlite
                   forge findings promote -> draft Case YAML (human commits)

MAINTENANCE        warm-index | sync (incremental) | verify (drift +
                   link integrity + finding staleness)
```

`verify` responsibilities (consolidated):

1. Symbol drift: span_hash vs. current source.
2. **Link integrity (NEW):** every `affected_symbols` entry in
   cases/features/docs validated against `symbols`; dangling links
   flagged via `parse_warning` / confidence downgrade.
3. **Finding staleness (NEW):** for each active finding, compare
   `symbol_span_hashes` to current symbols; on change or
   disappearance, `status='stale'`. Stale findings are excluded from
   default retrieval, never deleted.

## 4. MCP surface

### 4.1 Read tools (existing 11, with upgrades)

- `find_symbol`, `get_callers`, `get_callees`, `get_call_chain`,
  `get_references`, `get_source` — unchanged contracts.
  `get_source` keeps the `local_file -> embedded -> unavailable`
  origin fallback.
- `search_semantic(query, ...)` — **upgraded:** ranked results now
  span symbols + docs + **cases + features**, each tagged
  `kind: 'symbol'|'doc'|'case'|'feature'`. Symbol hits keep
  `expand=True` neighbor/knowledge enrichment; case/feature hits
  carry id, title, url, summary at requested `detail_level`.
- `find_case` / `find_feature` — **upgraded:** two-stage hybrid
  (FTS + vector -> cross-encoder rerank), with the legacy exact
  field-match preserved inside the lexical leg (ticket-key lookups
  behave identically).
- `find_doc`, `find_knowledge` — `find_knowledge` **extended** to
  include findings (`kind: 'finding'`), clearly labeled so agents
  weight speculation appropriately.

### 4.2 Write tools (new, exactly two)

- `record_finding(text, symbol_ids=[], kind='observation',
  codebase='', force=False) -> {id, dangling_symbol_ids,
  duplicate_of?, status}`
  Guardrails: length cap; symbol_ids validated (unknown ids stored
  but flagged `dangling=true`); FTS near-duplicate check returns
  `duplicate_of` instead of blind insert (`force=True` overrides).
- `find_findings(query='', symbol='', status='active', limit=10,
  codebase='')`

Docstring discipline (normative): tool descriptions are the router.
`record_finding`'s docstring must state WHEN to record (non-obvious
discoveries, dead ends, gotchas, root-cause hypotheses — things a
future session would waste time re-deriving) and WHEN NOT to (facts
already indexed, trivial observations, step-by-step logs).

### 4.3 Transport & security

- `stdio` (default, per-client subprocess) and `streamable-http`
  (shared team server).
- **Normative for HTTP:** bearer-token auth required before any
  non-loopback binding; DNS-rebinding protection stays ON unless the
  deployment explicitly documents why not. (Indexes contain full
  `source_text` — treat the server as holding the codebase itself.)
- Instructions string (`REGISTERED CODEBASES`) must refresh on a
  schedule or on registry change for long-running HTTP servers, not
  only at startup.

## 5. Human curation CLI

```
forge findings list [--status ...] [--codebase X]
forge findings show <id>
forge findings promote <id> --confirm   # prints draft Case YAML,
                                        # marks promoted; NEVER writes
                                        # cases.yaml itself
forge findings reject <id> --confirm    # status change, not deletion
```

Promotion mapping: `text -> summary`, `root_cause_hypothesis ->
root_cause`, `symbol_ids -> affected_symbols`, confidence stays
`speculation` until a human edits the YAML.

## 6. Evaluation layer (required, not optional)

1. **Ground-truth question set** per codebase: structural
   ("who calls X on the DSP path"), historical ("how was Y fixed"),
   conceptual (paraphrase queries that must hit cases). Track
   recall@k per question class.
2. **Paraphrase recall gate:** at least one test per record type
   proving semantic (not lexical) recall — query wording deliberately
   different from stored wording, assert top-5 hit.
3. **Access-log mining:** `access_log.py` JSON-lines are the cheap
   eval substrate — tool-selection distribution, empty-result rate,
   retry patterns per session. Review weekly.

## 7. Pluggable interfaces (where implementations diverge)

| Interface | Personal impl | Deployment-specific impl |
|---|---|---|
| LLM provider (summarize/embed) | Anthropic API / local | Any internal gateway |
| Connectors (ingest) | GitHub/GitLab/Jira-cloud/local md | Any internal tracker/review/wiki |
| Hardware tags | free-form | deployment-defined vocab |
| Codebase registry | `forge.codebases.yaml` | same format, different content |
| Auth | bearer token | org SSO/token service |

Everything above this table is shared spec; everything in the right
column stays out of the personal repo.

## 8. Implementation roadmap (personal version)

1. **Parity pass** — bring personal repo to §2.1/§4.1 baseline
   (whatever subset is missing: edges table as truth, confidence
   fields, detail tiers, expand=True enrichment).
2. **Task A: semantic cases/features** — schema + embed + retrieval
   upgrade + paraphrase gates. (Prompt exists.)
3. **Task B: memory layer** — memory.sqlite + record_finding/
   find_findings + curation CLI + verify staleness. (Prompt exists.)
4. **Task C: eval harness** — ground-truth set + recall@k runner +
   access-log report.
5. **Task D: HTTP hardening** — bearer auth + instructions refresh.

A and B are independent (parallelizable). C should land before any
cross-team/user-facing claims about retrieval quality. D gates any
shared-server deployment.

## 9. Out of scope (v1)

Finding embeddings; auto-writing YAML; multi-tenant auth; web UI;
write access to L1/L2; cross-codebase federated search.

---

# Appendix R — Reconciliation with `framework/kb` (this repo)

This appendix records where the spec and the `framework/kb`
implementation diverge as of the spec's adoption, and which side each
divergence resolves to. It is maintenance guidance, not part of the
normative spec.

## R.1 Tool-name mapping

§4.1's "existing 11" names describe a different personal
implementation. `framework/kb`'s 11 tools map onto the spec surface as
follows; the **contract** (inputs/outputs/budgets) is what the spec
governs, and either name set is conformant:

| Spec name | framework/kb name | Note |
|---|---|---|
| `find_symbol` | `find_symbol` | identical |
| `get_callers` / `get_callees` / `get_call_chain` | `trace_callers` | one bounded-BFS tool covers all three |
| `get_references` | — (subset of `trace_callers` via edges) | `references` edge type is a parity-pass item |
| `get_source` | — | not exposed; agents read files directly (KB is not the source mirror here) |
| `search_semantic` | `relevant_code` (symbols) + `find_recipe` (L3) | unification into one kind-tagged tool is Task A |
| `find_case` / `find_feature` | — | Task A |
| `find_doc` / `find_knowledge` | `get_summary` / `find_recipe` | partial; findings kind is Task B |
| — | `find_op`, `find_tests`, `what_changed`, `review_status`, `build_info` | framework/kb extras the spec should absorb (see R.3) |

## R.2 Confidence: two axes, not one vocabulary

The spec's `verified | speculation | read_only` (§1.3) and
framework/kb's `draft | reviewed | battle-tested` are different axes:

- **Evidence provenance** (spec): how the claim was established.
- **Review maturity** (framework/kb): how far a human has vetted it.

Resolution: keep both. A record carries
`confidence: verified|speculation|read_only` (agent-settable only to
`speculation`/`read_only`) *and* `review: draft|reviewed|battle-tested`
(human-promoted via the review ladder). framework/kb's existing rule
"generated content lands as `draft`, never auto-trusted" is exactly
§1.3's "agents can never set `verified`".

## R.3 The op registry is an L1 table

`ops.jsonl` (macro-generated op registrations with `kernel_path:line`
anchors) is framework/kb's proven first artifact (378 registrations on
real ONNX Runtime) and is missing from §2.1. It is adopted as an L1
table: `ops` (+ `ops_fts`) with the same derived/rebuildable
discipline. Likewise `tests` (symbol→test mapping) and
`build_targets` (§1's build-target mapping, implemented via the CMake
File API with a static-scan fallback and per-row fidelity tags).

## R.4 Storage: JSONL today, sqlite when Task A lands

framework/kb persists L1/L2 as JSONL and searches in-memory
(brute-force cosine — exact at current scale). The spec's
`index.sqlite` (+FTS5, +vec) becomes the target at Task A, when
cases/features make lexical+vector hybrid retrieval real. JSONL
artifacts remain the pipeline interchange format; `index.sqlite` is
derived from them, preserving invariant §1.2.

## R.5 Hash granularity

framework/kb hashes per-file; the spec requires per-symbol
`span_hash` (§1.4) for finding staleness. Parity pass adds
`span_hash` to `symbols.jsonl` (hash of the symbol's source span),
keeping the file hash for the incremental build firewall.
