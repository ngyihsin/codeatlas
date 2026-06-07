"""Tests for the kb pipeline. Run: cd framework/kb && python -m pytest -q"""
import json
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kb import l1, lint, incremental, l2, retrieve          # noqa: E402
from kb import eval as kbeval                               # noqa: E402
from kb import review                                       # noqa: E402
from kb import scip_ingest                                  # noqa: E402
from kb import recipes as kbrecipes                         # noqa: E402
from kb.mcp_server import KB, handle, BUDGET, serve_http    # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fixtures", "mini-runtime")
FIX = os.path.abspath(FIX)
HAS_CTAGS = shutil.which("ctags") is not None
RECIPES = os.path.abspath(os.path.join(FIX, "..", "recipes"))
try:
    import yaml as _yaml                                     # noqa: F401
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# ------------------------------------------------------------------- L1 ops
def test_extract_ops_all_frameworks():
    ops = l1.extract_ops(FIX, l1.load_patterns())
    by_name = {o.op_name: o for o in ops}
    assert set(by_name) == {"Abs", "Add", "Relu", "my_add.out"}
    assert by_name["Add"].provider == "kCpuExecutionProvider"
    assert by_name["Add"].version == "14"
    assert by_name["Add"].macro == "ONNX_OPERATOR_KERNEL_EX"
    assert by_name["Relu"].framework == "qnn"
    assert by_name["my_add.out"].framework == "executorch"
    # anchors point at real files
    for o in ops:
        assert os.path.isfile(os.path.join(FIX, o.kernel_path))


def test_ops_pattern_is_data_driven():
    # adding a framework = adding a YAML entry, no code change
    pats = l1.load_patterns()
    assert {p["macro"] for p in pats} >= {"ONNX_OPERATOR_KERNEL_EX", "EXECUTORCH_LIBRARY",
                                          "REGISTER_QNN_OP_BUILDER"}


# --------------------------------------------------------------- L1 symbols/graph
@pytest.mark.skipif(not HAS_CTAGS, reason="universal-ctags not installed")
def test_symbols_and_pagerank():
    syms = l1.extract_symbols(FIX)
    names = {s.name for s in syms}
    assert {"clamp_index", "AbsCompute", "AddCompute"} <= names
    edges = l1.build_edges(FIX, syms)
    pr = l1.pagerank(syms, edges)
    assert abs(sum(pr.values()) - 1.0) < 1e-6      # PageRank is a distribution
    assert all(v >= 0 for v in pr.values())


# --------------------------------------------------------------------- L2 lint
def test_lint_passes_good():
    good = {"id": "x", "path": "cpu/elementwise_ops.cc", "fold": "clamp to range",
            "preview": "clamps [L7-9]", "full": "returns clamped value [L7-9]",
            "evidence_level": "code"}
    assert lint.lint_summary(good, source_lines=26) == []


def test_lint_catches_bluffs():
    bad = {"id": "x", "fold": "x" * 40, "preview": "p",
           "full": "does magic", "evidence_level": "code"}   # no line ref, fold too long
    errs = lint.lint_summary(bad, source_lines=26)
    joined = " ".join(errs)
    assert "fold is" in joined
    assert "no [Lxx]" in joined
    # out-of-range line ref
    bad2 = {"id": "y", "fold": "ok", "preview": "p", "full": "see [L999]",
            "evidence_level": "code"}
    assert any("outside source" in e for e in lint.lint_summary(bad2, source_lines=26))


# ------------------------------------------------------------------ incremental
def test_input_hash_stability():
    h = lambda src, f: incremental.input_hash(src, f)
    assert h("a", ["f1"]) == h("a", ["f1"])
    assert h("a", ["f1"]) != h("b", ["f1"])
    assert h("a", ["f1"]) != h("a", ["f2"])
    assert h("a", ["f1", "f2"]) == h("a", ["f2", "f1"])    # order-independent


def test_firewall_stops_cascade():
    edges = [{"caller_id": "a", "callee_id": "b"}, {"caller_id": "b", "callee_id": "c"}]
    # c changed but its fold is stable -> nothing propagates past c
    assert incremental.compute_dirty({"c"}, edges, fold_changed=set()) == {"c"}
    # c's fold changed -> b becomes stale; b's fold stable -> a is spared
    assert incremental.compute_dirty({"c"}, edges, fold_changed={"c"}) == {"b", "c"}
    # full cascade when every fold changes
    assert incremental.compute_dirty({"c"}, edges, fold_changed={"a", "b", "c"}) == {"a", "b", "c"}


# ---------------------------------------------------- M3.1 recipe semantic search
def test_recipe_hash_embedder_is_normalized_and_deterministic():
    import math as _m
    e = kbrecipes.HashEmbedder(dim=64)
    v = e.embed("add a new operator kernel")
    assert abs(_m.sqrt(sum(x * x for x in v)) - 1.0) < 1e-9
    assert e.embed("clip clamp") == e.embed("clip clamp")


def test_recipe_index_ranks_by_intent():
    recs = [
        {"id": "add-an-op", "title": "Add a new operator to a backend",
         "task": "add op register kernel", "when": "new operator needed"},
        {"id": "fix-a-dispatch-bug", "title": "Diagnose wrong-output dispatch bug",
         "task": "fix dispatch wrong output type mismatch",
         "when": "op produces wrong results for some dtype"},
    ]
    idx = kbrecipes.RecipeIndex(recs)
    assert idx.search("introduce a new operator kernel")[0]["id"] == "add-an-op"
    assert idx.search("wrong output for a dtype, dispatch")[0]["id"] == "fix-a-dispatch-bug"


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
def test_find_recipe_semantic_via_mcp(tmp_path):
    kbdir = tmp_path / "kb"
    (kbdir / "recipes").mkdir(parents=True)
    for fn in ("add-an-op.yaml", "fix-a-dispatch-bug.yaml"):
        shutil.copy(os.path.join(RECIPES, fn), kbdir / "recipes")
    kb = KB(str(kbdir))
    assert kb.find_recipe("introduce a new kernel into a backend")[0]["id"] == "add-an-op"
    assert kb.find_recipe("op gives wrong output for fp16")[0]["id"] == "fix-a-dispatch-bug"


# --------------------------------------------------- M2.1 scip-clang precise tier
# A synthetic SCIP `print --json` index mirroring the Sourcegraph schema (we can't
# build ORT / run scip-clang here, so the ingest logic is verified against a fixture).
_SCIP_INDEX = {
    "documents": [{
        "relativePath": "m/clip.cc",
        "symbols": [
            {"symbol": "cxx . . `Clip`#Compute().", "displayName": "Compute", "kind": 6},
            {"symbol": "cxx . . `Eigen`#clamp().", "displayName": "clamp", "kind": 6},
        ],
        "occurrences": [
            {"symbol": "cxx . . `Clip`#Compute().", "range": [10, 0, 40, 1],
             "symbolRoles": 1, "enclosingRange": [10, 0, 40, 1]},          # definition
            {"symbol": "cxx . . `Eigen`#clamp().", "range": [20, 4, 20, 9],
             "symbolRoles": 0},                                            # reference (a call)
            {"symbol": "local 1", "range": [21, 4, 21, 9], "symbolRoles": 0},  # ignored
        ],
    }],
}


def test_scip_parse_index_builds_precise_edges():
    symbols, edges = scip_ingest.parse_index(_SCIP_INDEX)
    assert {s["name"] for s in symbols} == {"Compute", "clamp"}
    assert len(edges) == 1
    e = edges[0]
    assert e["caller_id"] == "cxx . . `Clip`#Compute()."          # encloses the ref
    assert e["callee_id"] == "cxx . . `Eigen`#clamp()."
    assert e["xref"] == "precise" and e["method"] == "scip-clang"


def test_scip_precise_edges_take_precedence_in_mcp(tmp_path):
    kbdir = tmp_path / "kb"
    kbdir.mkdir()
    (kbdir / "symbols.jsonl").write_text(
        json.dumps({"id": "A", "name": "A", "path": "x.cc", "kind": "function"}) + "\n")
    (kbdir / "edges.jsonl").write_text(
        json.dumps({"caller_id": "A", "callee_id": "B", "xref": "partial"}) + "\n")
    (kbdir / "edges.precise.jsonl").write_text(
        json.dumps({"caller_id": "A", "callee_id": "B", "xref": "precise"}) + "\n")
    kb = KB(str(kbdir))
    ab = [e for e in kb.edges if e["caller_id"] == "A" and e["callee_id"] == "B"]
    assert len(ab) == 1 and ab[0]["xref"] == "precise"     # precise wins, no duplicate


def test_scip_build_without_binary_is_graceful():
    with pytest.raises(SystemExit):           # scip-clang not on PATH -> clear error
        scip_ingest.build("/nonexistent", "/nope.json", "/tmp/none")


# ----------------------------------------------------- M2.2 human-review workflow
def test_review_promote_ladder_and_rules():
    sums = [{"id": "a.cc::F", "fold": "f", "full": "does x [L3]", "path": "a.cc",
             "confidence": "draft"}]
    rec = review.promote(sums, "a.cc::F", "reviewed", owner="team-cpu", today="2026-06-07")
    assert rec["confidence"] == "reviewed" and rec["owner"] == "team-cpu"
    assert rec["reviewed_at"] == "2026-06-07"
    # battle-tested needs a ticket; missing -> error
    with pytest.raises(ValueError):
        review.promote(sums, "a.cc::F", "battle-tested", owner="x")
    rec2 = review.promote(sums, "a.cc::F", "battle-tested", owner="x", ticket="JIRA-9")
    assert rec2["confidence"] == "battle-tested" and rec2["ticket"] == "JIRA-9"
    with pytest.raises(KeyError):
        review.promote(sums, "missing", "reviewed", owner="x")


def test_review_evidence_anchors_and_listing():
    sums = [{"id": "a.cc::F", "fold": "f", "full": "y [L3] and [L7-9]", "path": "a.cc",
             "confidence": "draft", "scope": "symbol"},
            {"id": "b.cc::G", "fold": "g", "full": "z [L1]", "path": "b.cc",
             "confidence": "reviewed"}]
    assert review.evidence_anchors(sums[0]) == ["a.cc:L3", "a.cc:L7-9"]
    drafts = review.list_drafts(sums, status="draft")
    assert len(drafts) == 1 and drafts[0]["id"] == "a.cc::F"


@pytest.mark.skipif(not HAS_CTAGS, reason="universal-ctags not installed")
def test_review_promotion_flips_mcp_review_status(tmp_path):
    kbdir = tmp_path / "kb"
    l1.build(FIX, str(kbdir))
    l2.build(str(kbdir), FIX, str(kbdir), backend=l2.MockBackend(_clean_reply),
             granularity="symbol", top_n=3)
    sums = review._load(str(kbdir))
    sym = next(s for s in sums if s.get("scope") == "symbol")
    review.promote(sums, sym["id"], "reviewed", owner="team-cpu")
    review._save(str(kbdir), sums)
    kb = KB(str(kbdir))                                   # reload
    name = sym["id"].split(":")[-2] if sym["id"].count(":") >= 2 else sym["id"]
    statuses = [r["status"] for r in kb.review_status(name)]
    assert any(s.startswith("L2 reviewed") for s in statuses)


# ----------------------------------------------------------- M2.3 tests index
@pytest.mark.skipif(not HAS_CTAGS, reason="universal-ctags not installed")
def test_tests_index_and_find_tests(tmp_path):
    out = tmp_path / "kb"
    rep = l1.build(FIX, str(out))
    assert rep["tests"] >= 1                          # the fixture test file is indexed
    kb = KB(str(out))
    hits = kb.find_tests("AddCompute")
    assert hits and any("elementwise_test" in h["test"] for h in hits)
    assert all(h["kind"] == "regression" for h in hits)
    # qualified name resolves via its leaf
    assert kb.find_tests("onnxruntime::AddCompute")


# ------------------------------------------------- M1.4 derived-fact invalidation
@pytest.mark.skipif(not HAS_CTAGS, reason="universal-ctags not installed")
def test_rebuild_edges_equals_full_when_disk_unchanged():
    syms = l1.extract_symbols(FIX)
    full = l1.build_edges(FIX, syms)
    # re-deriving any subset of caller files + keeping the rest reproduces the full graph
    some = {syms[0].path} if syms else set()
    merged = l1.rebuild_edges(FIX, syms, full, some)
    assert merged == full


@pytest.mark.skipif(not HAS_CTAGS, reason="universal-ctags not installed")
def test_l1_build_incremental_mode(tmp_path):
    out = tmp_path / "kb"
    r1 = l1.build(FIX, str(out))
    assert r1["mode"] == "full"
    e1 = [json.loads(l) for l in open(out / "edges.jsonl")]
    r2 = l1.build(FIX, str(out))                 # nothing changed on disk
    assert r2["mode"] == "incremental" and r2["changed"] == 0
    e2 = [json.loads(l) for l in open(out / "edges.jsonl")]
    assert e1 == e2                              # incremental no-op reproduces edges


@pytest.mark.skipif(not HAS_CTAGS, reason="universal-ctags not installed")
def test_plan_rebuild_wires_compute_dirty(tmp_path):
    out = tmp_path / "kb"
    l1.build(FIX, str(out))
    # pick a real file that has symbols
    syms = [json.loads(l) for l in open(out / "symbols.jsonl")]
    a_path = next(s["path"] for s in syms if s.get("kind") in ("function", "method"))
    plan = incremental.plan_rebuild(str(out), {a_path})
    assert plan["changed_symbols"] >= 1
    assert all(":" in d for d in plan["dirty_summaries"])    # symbol ids
    assert plan["edges_to_rederive"] >= 0


# -------------------------------------------------------------------- MCP server
@pytest.mark.skipif(not HAS_CTAGS, reason="universal-ctags not installed")
def test_mcp_tools(tmp_path):
    out = tmp_path / "kb"
    l1.build(FIX, str(out))
    (out / "recipes").mkdir()
    shutil.copy(os.path.join(FIX, "..", "recipes", "add-an-op.yaml"), out / "recipes")
    kb = KB(str(out))

    # tools/list
    r = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, kb)
    names = {t["name"] for t in r["result"]["tools"]}
    assert {"find_symbol", "trace_callers", "find_recipe", "get_recipe_steps"} <= names

    # find_recipe routes the task to the recipe
    assert kb.find_recipe("add a new op kernel")[0]["id"] == "add-an-op"
    # get_recipe_steps returns the decision tree
    assert "decision_points" in kb.get_recipe_steps("add-an-op")
    # find_symbol is token-budgeted (compact rows, not raw files)
    rows = kb.find_symbol("Compute", detail="fold")
    assert rows and all(set(r) <= {"anchor", "kind"} for r in rows)


# ----------------------------------------------------------- M3.2 MCP scale
def _kb_with_many_symbols(tmp_path, n):
    kbdir = tmp_path / "kb"; kbdir.mkdir()
    with open(kbdir / "symbols.jsonl", "w") as f:
        for i in range(n):
            f.write(json.dumps({"id": f"x.cc:Foo{i}:{i}", "name": f"Foo{i}",
                                "path": "x.cc", "kind": "function", "importance": 0.0}) + "\n")
    return KB(str(kbdir))


def test_mcp_pagination_reports_total_and_cursor(tmp_path):
    kb = _kb_with_many_symbols(tmp_path, BUDGET + 10)
    r = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "find_symbol", "arguments": {"query": "foo"}}}, kb)
    res = r["result"]
    assert res["total"] == BUDGET + 10                 # honest total, not silently truncated
    assert res["returned"] == BUDGET and "nextCursor" in res
    page1 = json.loads(res["content"][0]["text"])
    # follow the cursor for the next page
    r2 = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                 "params": {"name": "find_symbol",
                            "arguments": {"query": "foo", "cursor": res["nextCursor"]}}}, kb)
    page2 = json.loads(r2["result"]["content"][0]["text"])
    assert len(page2) == 10 and page1 != page2 and "nextCursor" not in r2["result"]


def test_mcp_invalid_cursor_errors(tmp_path):
    kb = _kb_with_many_symbols(tmp_path, 3)
    r = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list",
                "params": {"cursor": "!!!not-base64!!!"}}, kb)
    assert r["error"]["code"] == -32602


def test_mcp_initialize_version_and_capabilities(tmp_path):
    kb = _kb_with_many_symbols(tmp_path, 1)
    r = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"}, kb)
    assert r["result"]["protocolVersion"] == "2025-06-18"
    assert "resources" in r["result"]["capabilities"]


@pytest.mark.skipif(not HAS_CTAGS, reason="universal-ctags not installed")
def test_mcp_resources_list_and_read(tmp_path):
    kbdir = tmp_path / "kb"
    l1.build(FIX, str(kbdir))
    kb = KB(str(kbdir))
    rl = handle({"jsonrpc": "2.0", "id": 1, "method": "resources/list"}, kb)
    uris = {r["uri"] for r in rl["result"]["resources"]}
    assert "kb://ops" in uris and "kb://module_map" in uris
    rd = handle({"jsonrpc": "2.0", "id": 2, "method": "resources/read",
                 "params": {"uri": "kb://module_map"}}, kb)
    assert "Module Map" in rd["result"]["contents"][0]["text"]
    bad = handle({"jsonrpc": "2.0", "id": 3, "method": "resources/read",
                  "params": {"uri": "kb://nope"}}, kb)
    assert bad["error"]["code"] == -32602


def test_mcp_http_transport_roundtrip(tmp_path):
    import socket, threading, urllib.request, time
    kb = _kb_with_many_symbols(tmp_path, 2)
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    threading.Thread(target=serve_http, args=(kb, "127.0.0.1", port), daemon=True).start()
    url = f"http://127.0.0.1:{port}/mcp"
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}).encode()
    last = None
    for _ in range(50):                       # wait for server to come up
        try:
            req = urllib.request.Request(url, data=body,
                                         headers={"Content-Type": "application/json"})
            last = json.loads(urllib.request.urlopen(req, timeout=2).read())
            break
        except Exception:
            time.sleep(0.05)
    assert last and last["result"]["protocolVersion"] == "2025-06-18"


def test_mcp_unknown_tool_errors():
    kb = KB(os.devnull + "_nope")   # empty KB
    r = handle({"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                "params": {"name": "drop_table", "arguments": {}}}, kb)
    assert r["error"]["code"] == -32601


# ---------------------------------------------------------------- L2 generator
# Deterministic backends: no subprocess, no network. They stand in for the agent.
def _clean_reply(prompt, attempt):
    # a leaf prompt shows numbered source starting at "   1|"; cite L1 (always valid)
    return '{"fold":"src file","preview":"a file","full":"does things [L1]",' \
           '"evidence_level":"code"}'


def test_l2_generates_clean_summary(tmp_path):
    code = tmp_path / "code"; code.mkdir()
    (code / "a.cc").write_text("int main() { return 0; }\n")
    out = tmp_path / "l2"
    report = l2.build(str(tmp_path), str(code), str(out),
                      backend=l2.MockBackend(_clean_reply))
    assert report["generated"] >= 1 and report["quarantined"] == 0
    lines = [json.loads(l) for l in open(out / "summaries.jsonl")]
    leaf = [s for s in lines if s.get("path") == "a.cc"][0]
    assert leaf["confidence"] == "draft"          # never auto-trusted
    assert lint.lint_summary(leaf, source_lines=1) == []   # what landed is lint-clean


def test_l2_self_repairs_a_bluff(tmp_path):
    # first reply bluffs (fold too long + out-of-range cite); second is clean.
    replies = ['{"fold":"way too long a fold here","preview":"p",'
               '"full":"x [L999]","evidence_level":"code"}',
               '{"fold":"ok","preview":"p","full":"y [L1]","evidence_level":"code"}']
    seen = {}

    def responder(prompt, attempt):
        # key by leaf vs module so each node gets its own 2-step sequence
        node = "leaf" if "Summarize this source file" in prompt else "mod"
        i = seen.get(node, 0); seen[node] = i + 1
        return replies[min(i, len(replies) - 1)]

    code = tmp_path / "code"; code.mkdir()
    (code / "a.cc").write_text("int x;\n")
    out = tmp_path / "l2"
    report = l2.build(str(tmp_path), str(code), str(out),
                      backend=l2.MockBackend(responder), attempts=3)
    assert report["quarantined"] == 0           # the bluff was repaired, not shipped
    leaf = [json.loads(l) for l in open(out / "summaries.jsonl")
            if '"a.cc"' in l][0]
    assert leaf["fold"] == "ok" and "[L1]" in leaf["full"]


def test_l2_quarantines_incorrigible_bluff(tmp_path):
    # always bluffs -> never passes lint -> quarantined, never in summaries.jsonl
    bluff = lambda p, a: '{"fold":"x","preview":"p","full":"no cite here",' \
                         '"evidence_level":"code"}'
    code = tmp_path / "code"; code.mkdir()
    (code / "a.cc").write_text("int x;\n")
    out = tmp_path / "l2"
    report = l2.build(str(tmp_path), str(code), str(out),
                      backend=l2.MockBackend(bluff), attempts=2)
    assert report["quarantined"] >= 1
    q = [json.loads(l) for l in open(out / "quarantine.jsonl")]
    assert any("no [Lxx]" in " ".join(s["_errors"]) for s in q)
    leaf_clean = [l for l in open(out / "summaries.jsonl") if '"a.cc"' in l]
    assert leaf_clean == []                     # the bluff never reached the trusted set


def test_l2_incremental_skips_unchanged(tmp_path):
    code = tmp_path / "code"; code.mkdir()
    (code / "a.cc").write_text("int x;\n")
    out = tmp_path / "l2"
    b1 = l2.MockBackend(_clean_reply)
    r1 = l2.build(str(tmp_path), str(code), str(out), backend=b1)
    assert r1["generated"] >= 1
    # second run, nothing changed -> all cached, zero new generations
    b2 = l2.MockBackend(_clean_reply)
    r2 = l2.build(str(tmp_path), str(code), str(out), backend=b2)
    assert r2["generated"] == 0 and r2["cached"] >= 1 and b2.calls == 0


def test_l2_parse_summary_tolerates_fences():
    s = l2.parse_summary('```json\n{"fold":"a","x":1}\n```')
    assert s["fold"] == "a" and s["x"] == 1


# ----------------------------------------------- END-TO-END: generator -> agent
@pytest.mark.skipif(not HAS_CTAGS, reason="universal-ctags not installed")
def test_l2_summaries_reach_agent_via_mcp(tmp_path):
    """The whole point: a generated summary must actually surface through MCP."""
    kbdir = tmp_path / "kb"
    l1.build(FIX, str(kbdir))
    # generate L2 INTO the same kb dir so the MCP server loads summaries.jsonl with L1
    l2.build(str(kbdir), FIX, str(kbdir), backend=l2.MockBackend(_clean_reply))
    kb = KB(str(kbdir))

    # seam 1+3+4: find_symbol now carries the generated L2 summary (joined by path)
    rows = kb.find_symbol("Compute", detail="preview")
    assert rows and any(r.get("summary") for r in rows), \
        "L2 summary did not reach find_symbol"
    # seam 2: the op registry is finally reachable
    ops = kb.find_op("Add")
    add = [o for o in ops if o["op"] == "Add"]
    assert add and ":" in add[0]["anchor"]
    # get_summary returns the file explanation directly
    assert "preview" in kb.get_summary("cpu/elementwise_ops.cc")
    # seam 5: review_status reflects the real L2 draft state, not a hardcoded string
    rs = kb.review_status("AddCompute")
    assert rs and rs[0]["status"].startswith("L2 ")
    # graceful fallback: a path with no summary says so, doesn't crash
    assert "error" in kb.get_summary("does/not/exist.cc")


@pytest.mark.skipif(not HAS_CTAGS, reason="universal-ctags not installed")
def test_l2_per_symbol_summaries_join_in_mcp(tmp_path):
    """M1.1: symbol-granularity L2 produces symbol-scoped summaries that find_symbol
    surfaces joined by symbol id (not the whole-file summary)."""
    kbdir = tmp_path / "kb"
    l1.build(FIX, str(kbdir))
    rep = l2.build(str(kbdir), FIX, str(kbdir),
                   backend=l2.MockBackend(_clean_reply),
                   granularity="symbol", top_n=3)
    assert rep["generated"] >= 1
    sums = [json.loads(l) for l in open(kbdir / "summaries.jsonl")]
    sym_sums = [s for s in sums if s.get("scope") == "symbol"]
    assert sym_sums, "no symbol-scoped summaries produced"
    assert all(s["id"].count(":") >= 2 for s in sym_sums)     # path:name:line ids
    # what landed is lint-clean against the real file
    for s in sym_sums:
        n = sum(1 for _ in open(os.path.join(FIX, s["path"]), errors="ignore"))
        assert lint.lint_summary(s, source_lines=n) == []
    # MCP joins the symbol summary by id, reporting scope=symbol
    kb = KB(str(kbdir))
    rows = kb.find_symbol("Compute", detail="preview")
    assert any(r.get("scope") == "symbol" and r.get("summary") for r in rows)


def test_l2_symbol_spans_partition_file():
    syms = [{"id": "f:a:1", "line": 1}, {"id": "f:b:10", "line": 10},
            {"id": "f:c:20", "line": 20}]
    spans = l2.symbol_spans(syms, total_lines=30)
    assert spans["f:a:1"] == (1, 9) and spans["f:b:10"] == (10, 19)
    assert spans["f:c:20"] == (20, 30)            # last symbol runs to EOF


# ---------------------------------------------------------- M1.2 relevant_code
def test_retrieve_lexical_and_op_and_graph():
    symbols = [
        {"id": "m/clip.cc:Clip:1", "name": "Clip", "kind": "class", "path": "m/clip.cc",
         "line": 1, "importance": 0.9},
        {"id": "m/clip.cc:ComputeImpl:5", "name": "ComputeImpl", "kind": "method",
         "path": "m/clip.cc", "line": 5, "importance": 0.2},
        {"id": "m/gemm.cc:Gemm:1", "name": "Gemm", "kind": "class", "path": "m/gemm.cc",
         "line": 1, "importance": 0.5},
    ]
    edges = [{"caller_id": "m/clip.cc:ComputeImpl:5", "callee_id": "m/clip.cc:Clip:1"}]
    ops = [{"op_name": "Clip", "version": "6", "kernel_path": "m/clip.cc", "line": 13}]
    rows = retrieve.relevant_code("how does clip clamp values", symbols, edges, ops, k=5)
    ids = [r["symbol_id"] for r in rows]
    assert "m/clip.cc:Clip:1" in ids                      # lexical hit
    assert any(r["kind"] == "op" for r in rows)           # op registry surfaced
    # structural expansion pulled the caller of the Clip hit
    assert any("ComputeImpl" in r["anchor"] for r in rows)
    assert all("why" in r and "evidence" in r for r in rows)


def test_retrieve_empty_query_is_safe():
    assert retrieve.relevant_code("the and for", [], [], []) == []


@pytest.mark.skipif(not HAS_CTAGS, reason="universal-ctags not installed")
def test_relevant_code_via_mcp(tmp_path):
    kbdir = tmp_path / "kb"
    l1.build(FIX, str(kbdir))
    kb = KB(str(kbdir))
    r = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "relevant_code", "arguments": {"query": "clamp"}}}, kb)
    rows = json.loads(r["result"]["content"][0]["text"])
    assert rows and all("why" in row for row in rows)


# --------------------------------------------------------------- M1.3 eval harness
def test_eval_split_claims():
    claims = kbeval.split_claims("Does A [L1]. Plain sentence here. Range [L7-9] x.")
    assert [r for _, r in claims] == [[(1, 1)], [(7, 9)]]   # only cited sentences


def test_eval_entailment_pass_and_fail():
    summ = {"id": "x", "path": "cpu/elementwise_ops.cc", "fold": "x", "preview": "p",
            "full": "clamps value to range [L7-9]", "evidence_level": "code"}
    ok = l2.MockBackend(lambda p, a: '{"verdict":"entailed","confidence":1.0}')
    assert kbeval.evaluate_summary(summ, FIX, ok)["faithfulness"] == 1.0
    bad = l2.MockBackend(lambda p, a: '{"verdict":"contradicted","confidence":1.0}')
    r = kbeval.evaluate_summary(summ, FIX, bad)
    assert r["faithfulness"] == 0.0 and r["entailed"] == 0      # accuracy failure caught


def test_eval_self_consistency_majority():
    votes = iter(["entailed", "contradicted", "entailed"])
    be = l2.MockBackend(lambda p, a: '{"verdict":"%s"}' % next(votes))
    res = kbeval.entail_claim(be, "claim", "  1| code", samples=3)
    assert res["verdict"] == "entailed" and abs(res["confidence"] - 2 / 3) < 1e-9


def test_eval_coverage():
    syms = [{"id": "a", "kind": "function", "importance": 0.9},
            {"id": "b", "kind": "function", "importance": 0.1}]
    cov = kbeval.coverage([{"id": "a", "scope": "symbol"}], syms, quantile=0.5)
    assert cov["covered"] == 1 and cov["total"] >= 1


def test_mcp_find_symbol_without_l2_falls_back(tmp_path):
    """No summaries.jsonl yet -> find_symbol still works on L1 alone (no crash)."""
    kbdir = tmp_path / "kb"
    l1_min = kbdir
    os.makedirs(l1_min)
    # minimal L1: one symbol, no summaries file
    (kbdir / "symbols.jsonl").write_text(
        json.dumps({"id": "a.cc:f", "name": "frobnicate", "path": "a.cc",
                    "kind": "function", "importance": 1.0, "signature": "void frobnicate()"}) + "\n")
    kb = KB(str(kbdir))
    rows = kb.find_symbol("frob", detail="preview")
    assert rows and "summary" not in rows[0]          # degrades, no L2 key invented
    assert kb.review_status("frobnicate")[0]["status"] == "mechanical (L1)"
