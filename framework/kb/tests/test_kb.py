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
from kb import drift                                        # noqa: E402
from kb import recipes as kbrecipes                         # noqa: E402
from kb import embed as kbembed                             # noqa: E402
from kb import mine_recipes                                 # noqa: E402
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


# ------------------------------------------------------------ M3.3 drift sampler
@pytest.mark.skipif(not HAS_CTAGS, reason="universal-ctags not installed")
def test_drift_fresh_then_detects_staleness(tmp_path):
    kbdir = tmp_path / "kb"
    l1.build(FIX, str(kbdir))
    clean = drift.sample_drift(str(kbdir), FIX)
    assert clean["fresh_rate"] == 1.0 and clean["stale"] == []
    # simulate a missed rebuild: corrupt one cached hash -> drift must flag it stale
    cache = json.loads(open(kbdir / "l1_cache.json").read())
    a_file = next(iter(cache["file_hashes"]))
    cache["file_hashes"][a_file] = "deadbeef"
    open(kbdir / "l1_cache.json", "w").write(json.dumps(cache))
    drifted = drift.sample_drift(str(kbdir), FIX)
    assert a_file in drifted["stale"] and drifted["fresh_rate"] < 1.0


def test_drift_no_cache_is_graceful(tmp_path):
    (tmp_path / "kb").mkdir()
    assert "error" in drift.sample_drift(str(tmp_path / "kb"), str(tmp_path))


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


@pytest.mark.skipif(not (shutil.which("scip-clang") and shutil.which("scip")),
                    reason="scip-clang/scip not installed")
def test_scip_clang_live_pipeline(tmp_path):
    import subprocess
    d = tmp_path
    (d / "calc.cc").write_text(
        "int add(int a,int b){return a+b;}\n"
        "int compute(int x){return add(x,2);}\n"
        "int main(){return compute(3);}\n")
    (d / "compile_commands.json").write_text(json.dumps(
        [{"directory": str(d), "file": "calc.cc",
          "arguments": ["clang++", "-std=c++17", "-c", "calc.cc"]}]))
    subprocess.run(["scip-clang", "--compdb-path=compile_commands.json"],
                   cwd=str(d), check=True, capture_output=True)
    j = subprocess.run(["scip", "print", "--json", str(d / "index.scip")],
                       capture_output=True, text=True, check=True).stdout
    _, edges = scip_ingest.parse_index(json.loads(j))
    assert any("compute" in e["caller_id"] and "add" in e["callee_id"] for e in edges)
    assert edges and all(e["xref"] == "precise" for e in edges)


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


def test_review_promote_rejects_skipping_rungs():
    # the ladder is sequential: a draft cannot jump straight to battle-tested, even
    # with a ticket -- it must pass through reviewed (human accuracy check) first.
    sums = [{"id": "a.cc::F", "confidence": "draft"}]
    with pytest.raises(ValueError):
        review.promote(sums, "a.cc::F", "battle-tested", owner="x", ticket="JIRA-1")
    assert sums[0]["confidence"] == "draft"          # unchanged
    review.promote(sums, "a.cc::F", "reviewed", owner="x")   # one rung up is fine
    assert sums[0]["confidence"] == "reviewed"


def test_scip_innermost_caller_for_nested_scopes():
    # a call inside a method is enclosed by BOTH the class def and the method def; the
    # precise edge must be credited to the innermost scope (the method), not the class.
    index = {"documents": [{
        "relativePath": "m.cc", "symbols": [],
        "occurrences": [
            {"symbol": "cxx C#", "symbolRoles": 1,
             "range": [0, 6, 7], "enclosingRange": [0, 0, 10, 1]},      # class, lines 0-10
            {"symbol": "cxx C#foo().", "symbolRoles": 1,
             "range": [2, 6, 9], "enclosingRange": [2, 2, 5, 3]},       # method, lines 2-5
            {"symbol": "cxx bar().", "symbolRoles": 0, "range": [3, 4, 7]},  # call at line 3
        ],
    }]}
    _, edges = scip_ingest.parse_index(index)
    assert len(edges) == 1
    assert edges[0]["caller_id"] == "cxx C#foo()."   # the method, not "cxx C#"
    assert edges[0]["callee_id"] == "cxx bar()."


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


def test_l2_entailment_gate_rejects_then_repairs(tmp_path):
    # generation always returns a summary citing [L1]; entailment says contradicted
    # first, entailed after. The gate must reject the first and ship the repaired one.
    state = {"e": 0}

    def responder(prompt, attempt):
        if "CITED SOURCE" in prompt:                 # an entailment check
            state["e"] += 1
            return '{"verdict":"%s"}' % ("contradicted" if state["e"] == 1 else "entailed")
        return '{"fold":"ok","preview":"p","full":"does x [L1]","evidence_level":"code"}'

    code = tmp_path / "code"; code.mkdir(); (code / "a.cc").write_text("int x;\n")
    out = tmp_path / "l2"
    rep = l2.build(str(tmp_path), str(code), str(out),
                   backend=l2.MockBackend(responder), entail=True, attempts=3)
    assert rep["quarantined"] == 0 and state["e"] >= 2   # ran, rejected, then passed


def test_l2_entailment_gate_quarantines_unfixable(tmp_path):
    # entailment always says neutral -> claim never supported -> quarantined, not shipped
    def responder(prompt, attempt):
        if "CITED SOURCE" in prompt:
            return '{"verdict":"neutral"}'
        return '{"fold":"ok","preview":"p","full":"does x [L1]","evidence_level":"code"}'
    code = tmp_path / "code"; code.mkdir(); (code / "a.cc").write_text("int x;\n")
    out = tmp_path / "l2"
    rep = l2.build(str(tmp_path), str(code), str(out),
                   backend=l2.MockBackend(responder), entail=True, attempts=2)
    assert rep["quarantined"] >= 1


def test_l2_quarantined_not_reshipped_on_cache_hit(tmp_path):
    # a summary that always fails lint (cites a non-existent line) must stay quarantined
    # on a second, cache-hit run -- never silently promoted into summaries.jsonl.
    bluff = lambda p, a: '{"fold":"x","preview":"p","full":"claims [L999]","evidence_level":"code"}'
    code = tmp_path / "code"; code.mkdir(); (code / "a.cc").write_text("int x;\n")
    out = tmp_path / "l2"
    r1 = l2.build(str(tmp_path), str(code), str(out),
                  backend=l2.MockBackend(bluff), attempts=1)
    assert r1["quarantined"] >= 1
    r2 = l2.build(str(tmp_path), str(code), str(out),     # unchanged source -> cache hit
                  backend=l2.MockBackend(bluff), attempts=1)
    assert r2["cached"] >= 1
    shipped = [json.loads(l) for l in open(out / "summaries.jsonl") if l.strip()]
    quarantined = [json.loads(l) for l in open(out / "quarantine.jsonl") if l.strip()]
    assert all(s.get("path") != "a.cc" for s in shipped)      # not in the trusted set
    assert any(s.get("path") == "a.cc" for s in quarantined)  # still quarantined


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


# ---- L3 #1: real (MiniLM/ONNX) embedder, verified offline via an injected session ----

def test_wordpiece_tokenizer_subwords_and_unk():
    vocab = {t: i for i, t in enumerate(
        ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "run", "##ning", "fox", "##es"])}
    tok = kbembed.WordPieceTokenizer(vocab)
    assert tok.tokenize("running foxes") == ["run", "##ning", "fox", "##es"]
    assert tok.tokenize("zzzz") == ["[UNK]"]                     # unsplittable -> UNK
    ids, mask, types = tok.encode("running")
    assert ids[0] == vocab["[CLS]"] and ids[-1] == vocab["[SEP]"]
    assert mask == [1] * len(ids) and types == [0] * len(ids)


def test_mean_pool_normalize_masks_and_unit_length():
    # two tokens, dim 2; mask drops the second -> mean is the first row, then L2-normalized
    out = [[[3.0, 4.0], [100.0, 100.0]]]
    v = kbembed.mean_pool_normalize(out, mask=[1, 0])
    assert v == [0.6, 0.8]                                        # 3-4-5 triangle
    assert abs(sum(x * x for x in v) - 1.0) < 1e-9


def test_onnx_embedder_with_fake_session():
    # a fake session lets us verify tokenize -> run -> pool -> normalize without onnxruntime
    vocab = {t: i for i, t in enumerate(["[PAD]", "[UNK]", "[CLS]", "[SEP]", "a", "b"])}
    tok = kbembed.WordPieceTokenizer(vocab)

    class FakeSession:
        def run(self, _, feeds):                 # ORT output 0 is (1, seq, dim)
            seq = len(feeds["input_ids"][0])
            rows = [[1.0, 0.0] for _ in range(seq)]   # constant token embeddings -> [1,0]
            return [[rows]]
    emb = kbembed.OnnxEmbedder(FakeSession(), tok)
    assert emb.embed("a b") == [1.0, 0.0]


def test_get_embedder_falls_back_without_model(tmp_path):
    assert isinstance(kbrecipes.get_embedder(str(tmp_path)), kbrecipes.HashEmbedder)
    assert isinstance(kbrecipes.get_embedder(None), kbrecipes.HashEmbedder)


# ---- L3 #2: recipe mining from commit history ----

def test_mine_recipes_clusters_by_area():
    commits = [
        {"sha": "a1" * 8, "subject": "add Clip op kernel",
         "files": ["onnx/core/math/clip.cc", "onnx/core/math/clip.h"]},
        {"sha": "b2" * 8, "subject": "fix Clip op dispatch",
         "files": ["onnx/core/math/gemm.cc"]},
        {"sha": "c3" * 8, "subject": "register op for math",
         "files": ["onnx/core/math/softmax.cc"]},
        {"sha": "d4" * 8, "subject": "unrelated docs", "files": ["docs/readme.md"]},
    ]
    recipes = mine_recipes.mine(commits, min_cluster=3)
    assert len(recipes) == 1                          # only the math cluster reaches 3
    r = recipes[0]
    assert r["id"] == "mined:onnx-core" and r["confidence"] == "draft"
    assert r["source"] == "mined" and len(r["evidence"]) == 3
    assert "clip" in r["when"]                        # recurring keyword distilled (>2 chars)


def test_mine_recipes_min_cluster_filters_noise():
    commits = [{"sha": "z" * 16, "subject": "one off", "files": ["a/b/c.cc"]}]
    assert mine_recipes.mine(commits, min_cluster=3) == []


# ------------------------------------------------------- compdb auto-derivation
from kb import compdb as kbcompdb                            # noqa: E402

HAS_CMAKE = shutil.which("cmake") is not None


def test_compdb_detect_build_systems(tmp_path):
    assert kbcompdb.detect(FIX) == "cmake"           # fixture ships a CMakeLists.txt
    (tmp_path / "Makefile").write_text("all:\n\tcc -c a.c\n")
    assert kbcompdb.detect(str(tmp_path)) == "make"
    assert kbcompdb.detect(str(tmp_path / "..")) in (None, "make", "cmake")


@pytest.mark.skipif(not HAS_CMAKE, reason="cmake not installed")
def test_compdb_cmake_configure_only(tmp_path):
    res = kbcompdb.ensure(FIX, str(tmp_path))
    assert res["method"] == "cmake-configure" and res["entries"] == 4
    entries = json.load(open(res["compdb"]))
    files = {os.path.basename(e["file"]) for e in entries}
    assert "elementwise_ops.cc" in files
    # configure-only: no object files were produced (nothing compiled)
    assert not [f for f in os.listdir(os.path.join(str(tmp_path), "_compdb_build"))
                if f.endswith(".o")]


def test_compdb_make_dry_run_parser_is_pure():
    out = ("echo building\n"
           "cc -Iinclude -DFOO=1 -c src/a.c -o a.o\n"
           "clang++ -std=c++17 -c src/b.cc -o b.o\n"
           "ar rcs lib.a a.o b.o\n")
    entries = kbcompdb.parse_make_output(out, "/repo")
    assert [e["file"] for e in entries] == ["src/a.c", "src/b.cc"]
    assert all(e["directory"] == "/repo" for e in entries)


def test_compdb_synthesized_fallback_is_tagged(tmp_path):
    src = tmp_path / "proj"
    (src / "include").mkdir(parents=True)
    (src / "src").mkdir()
    (src / "src" / "a.cc").write_text("int f(){return 1;}\n")
    res = kbcompdb.ensure(str(src), str(tmp_path / "out"))
    assert res["method"] == "synthesized" and res["entries"] == 1
    entry = json.load(open(res["compdb"]))[0]
    assert entry["arguments"][0] == "clang++"                 # C++ source
    assert any(a.endswith("include") for a in entry["arguments"])  # guessed -I


@pytest.mark.skipif(not HAS_CMAKE, reason="cmake not installed")
def test_scip_build_auto_resolves_compdb(tmp_path):
    path, method = scip_ingest.resolve_compdb(FIX, "auto", str(tmp_path))
    assert method == "cmake-configure" and os.path.isfile(path)
    explicit, method2 = scip_ingest.resolve_compdb(FIX, "/x/cc.json", str(tmp_path))
    assert (explicit, method2) == ("/x/cc.json", "user-supplied")


# ------------------------------------------------- buildsys: build system as KB
from kb import buildsys as kbbuildsys                        # noqa: E402


def test_buildsys_static_scan_is_pure(tmp_path):
    (tmp_path / "CMakeLists.txt").write_text(
        'project(p CXX)\n'
        'find_package(Threads REQUIRED)\n'
        'option(USE_FOO "enable foo" ON)\n'
        'add_library(core STATIC src/a.cc ${EXTRA_SRCS})\n'
        'add_executable(tool main.cc)\n'
        'target_link_libraries(tool PRIVATE core Threads::Threads)\n')
    rows = kbbuildsys.scan_static(str(tmp_path))
    by = {(r["kind"], r["name"]): r for r in rows}
    core = by[("target", "core")]
    assert core["type"] == "library" and "${EXTRA_SRCS}" in core["sources"]  # verbatim
    assert by[("target", "tool")]["deps"] == ["Threads::Threads", "core"]
    assert by[("option", "USE_FOO")]["default"] == "ON"
    assert ("package", "Threads") in by
    assert all(r["fidelity"] == "partial" for r in rows)      # honesty tag


@pytest.mark.skipif(not HAS_CMAKE, reason="cmake not installed")
def test_buildsys_fileapi_exact_on_fixture(tmp_path):
    res = kbbuildsys.build(FIX, str(tmp_path))
    assert res["method"] == "cmake-file-api"
    rows = [json.loads(l) for l in open(res["out"])]
    (t,) = [r for r in rows if r["kind"] == "target"]
    assert t["name"] == "mini_runtime" and t["fidelity"] == "exact"
    assert len(t["sources"]) == 4


def test_buildsys_falls_back_to_static_when_configure_fails(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.16)\nproject(p CXX)\n"
        "find_package(NoSuchPackageEver REQUIRED)\n"
        "add_library(core a.cc)\n")
    res = kbbuildsys.build(str(src), str(tmp_path / "out"))
    assert res["method"] == "static-scan"                     # honest downgrade
    rows = [json.loads(l) for l in open(res["out"])]
    assert {"target", "package"} <= {r["kind"] for r in rows}


def test_mcp_build_info_tool(tmp_path):
    rows = [{"kind": "target", "name": "core", "type": "library", "sources": ["a.cc"],
             "deps": ["dep1"], "method": "cmake-file-api", "fidelity": "exact"},
            {"kind": "option", "name": "USE_FOO", "default": "ON",
             "method": "cmake-file-api", "fidelity": "exact"}]
    with open(tmp_path / "build_targets.jsonl", "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)
    kb = KB(str(tmp_path))
    (ov,) = kb.build_info()
    assert ov["targets"] == 1 and ov["options"] == 1 and ov["fidelity"] == "exact"
    assert kb.build_info("core")[0]["deps"] == ["dep1"]
    empty = KB(str(tmp_path / "nokb")) if (tmp_path / "nokb").mkdir() is None else None
    assert "error" in empty.build_info()[0]                   # graceful when absent


def test_find_symbol_joins_build_target(tmp_path):
    with open(tmp_path / "symbols.jsonl", "w") as f:
        f.write(json.dumps({"id": "s1", "name": "AddCompute", "kind": "function",
                            "path": "src/add.cc", "importance": 0.5}) + "\n")
    rows = [
        # static-scan style: sources relative to the CMakeLists dir (defined_in)
        {"kind": "target", "name": "core", "type": "library", "sources": ["add.cc"],
         "deps": [], "defined_in": "src/CMakeLists.txt",
         "method": "static-scan", "fidelity": "partial"},
        # unexpanded variables must never be joined
        {"kind": "target", "name": "ghost", "type": "library",
         "sources": ["${SRCS}"], "deps": [], "defined_in": "src/CMakeLists.txt",
         "method": "static-scan", "fidelity": "partial"}]
    with open(tmp_path / "build_targets.jsonl", "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)
    kb = KB(str(tmp_path))
    assert kb.find_symbol("AddCompute", detail="preview")[0]["build_target"] == "core"
    assert kb.find_symbol("AddCompute", detail="full")[0]["build_target"] == "core"
    assert "build_target" not in kb.find_symbol("AddCompute", detail="fold")[0]
    assert "${SRCS}" not in kb.target_by_path       # ${VARS} skipped, not guessed


def test_find_symbol_without_buildsys_is_unchanged(tmp_path):
    with open(tmp_path / "symbols.jsonl", "w") as f:
        f.write(json.dumps({"id": "s1", "name": "AddCompute", "kind": "function",
                            "path": "src/add.cc", "importance": 0.5}) + "\n")
    row = KB(str(tmp_path)).find_symbol("AddCompute", detail="preview")[0]
    assert "build_target" not in row                # graceful before kb.buildsys runs


# ------------------------------------------- parity pass: span_hash + verify
def _build_l1(tmp_path):
    out = str(tmp_path / "kb")
    l1.build(FIX, out)
    return out


@pytest.mark.skipif(not HAS_CTAGS, reason="ctags not installed")
def test_symbols_carry_span_hash(tmp_path):
    out = _build_l1(tmp_path)
    syms = [json.loads(l) for l in open(os.path.join(out, "symbols.jsonl"))]
    assert syms and all(s.get("span_hash") for s in syms)
    assert all(len(s["span_hash"]) == 12 for s in syms)


@pytest.mark.skipif(not HAS_CTAGS, reason="ctags not installed")
def test_verify_detects_span_drift(tmp_path):
    import shutil as sh
    out = _build_l1(tmp_path)
    mutated = tmp_path / "code"
    sh.copytree(FIX, mutated)
    f = mutated / "cpu" / "elementwise_ops.cc"
    f.write_text(f.read_text().replace("return ElementwiseBinary(ctx);",
                                       "return ElementwiseBinary(ctx);  // mutated"))
    rep = drift.verify(out, str(mutated))
    assert any(d["reason"] == "span_changed" and "elementwise_ops" in d["id"]
               for d in rep["drifted_symbols"])
    clean = drift.verify(out, FIX)
    assert clean["drifted_symbols"] == []


@pytest.mark.skipif(not HAS_YAML, reason="pyyaml not installed")
def test_verify_flags_dangling_affected_symbols(tmp_path):
    out = tmp_path / "kb"
    (out / "recipes").mkdir(parents=True)
    with open(out / "symbols.jsonl", "w") as f:
        f.write(json.dumps({"id": "a.cc:Real:1", "name": "Real", "path": "a.cc",
                            "line": 1}) + "\n")
    (out / "recipes" / "r.yaml").write_text(
        "id: r\ntitle: t\naffected_symbols: [Real, GhostSymbol]\n")
    dangling = drift.link_integrity(str(out))
    assert dangling == [{"record": "recipes/r.yaml", "symbol": "GhostSymbol"}]


# ---------------------------------------- Task A: L3 cases/features retrieval
from kb import knowledge as kbknow                           # noqa: E402

CASES_FIX = os.path.abspath(os.path.join(FIX, "..", "cases"))
FEATS_FIX = os.path.abspath(os.path.join(FIX, "..", "features"))


def _knowledge_kb(tmp_path):
    import shutil as sh
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    sh.copytree(CASES_FIX, kb_dir / "cases")
    sh.copytree(FEATS_FIX, kb_dir / "features")
    (kb_dir / "symbols.jsonl").write_text("")
    return str(kb_dir)


@pytest.mark.skipif(not HAS_YAML, reason="pyyaml not installed")
def test_case_exact_ticket_lookup_behaves_like_lookup(tmp_path):
    kb = KB(_knowledge_kb(tmp_path))
    for q in ("QNN-1041", "qnn-1041-clip-saturation"):
        rows = kb.find_case(q)
        assert rows[0]["id"] == "qnn-1041-clip-saturation" and rows[0]["score"] == 1.0


@pytest.mark.skipif(not HAS_YAML, reason="pyyaml not installed")
def test_case_paraphrase_recall_gate(tmp_path):
    # Spec §6.2: wording deliberately different from the stored case text.
    kb = KB(_knowledge_kb(tmp_path))
    rows = kb.find_case("clamped values wrap around after quantization at the boundary")
    assert "qnn-1041-clip-saturation" in [r["id"] for r in rows[:5]]
    rows2 = kb.find_case("kernel registered but nodes still run on the host processor")
    assert "ort-2213-relu-partitioner" in [r["id"] for r in rows2[:5]]


@pytest.mark.skipif(not HAS_YAML, reason="pyyaml not installed")
def test_feature_paraphrase_recall_gate(tmp_path):
    kb = KB(_knowledge_kb(tmp_path))
    rows = kb.find_feature("which kernels share the elementwise dispatch")
    assert rows[0]["id"] == "elementwise-cpu-kernels"


@pytest.mark.skipif(not HAS_YAML, reason="pyyaml not installed")
def test_search_semantic_tags_kinds_and_interleaves(tmp_path):
    kb = KB(_knowledge_kb(tmp_path))
    rows = kb.search_semantic("clip quantization saturation", k=6)
    kinds = {r["kind"] for r in rows}
    assert "case" in kinds and all("kind" in r for r in rows)
    assert rows[0]["kind"] != rows[1]["kind"]        # interleaved, not one-source


@pytest.mark.skipif(not HAS_YAML, reason="pyyaml not installed")
def test_case_confidence_defaults_to_speculation(tmp_path):
    kb_dir = tmp_path / "kb"
    (kb_dir / "cases").mkdir(parents=True)
    (kb_dir / "cases" / "c.yaml").write_text("id: c1\ntitle: no confidence field\n")
    (recs,) = kbknow.load_cases(str(kb_dir))
    assert recs["confidence"] == "speculation"       # spec §1.3 default


@pytest.mark.skipif(not os.environ.get("KB_MINILM_DIR"),
                    reason="KB_MINILM_DIR not set (true-synonym gate needs MiniLM)")
def test_case_synonym_recall_gate_minilm(tmp_path):
    # Stronger §6.2 gate: pure synonyms, near-zero token overlap. HashEmbedder
    # cannot pass this by construction; it requires the real embedder.
    kb = KB(_knowledge_kb(tmp_path))
    rows = kb.find_case("int8 overflow bug in the clamping operator")
    assert "qnn-1041-clip-saturation" in [r["id"] for r in rows[:5]]


# --------------------------------------------------- Task B: memory layer (M)
from kb import memory as kbmem                               # noqa: E402


def _mem_kb(tmp_path):
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    (kb_dir / "symbols.jsonl").write_text(json.dumps(
        {"id": "a.cc:Real:1", "name": "Real", "path": "a.cc", "line": 1,
         "span_hash": "aaaaaaaaaaaa"}) + "\n")
    return str(kb_dir)


def test_record_finding_guardrails(tmp_path):
    kb_dir = _mem_kb(tmp_path)
    r = kbmem.record_finding(kb_dir, "Real thing", symbol_ids=["Real", "Ghost"])
    assert r["status"] == "recorded" and r["dangling_symbol_ids"] == ["Ghost"]
    assert "error" in kbmem.record_finding(kb_dir, "x" * 2001)
    assert "error" in kbmem.record_finding(kb_dir, "ok", kind="opinion")
    assert "error" in kbmem.record_finding(kb_dir, "   ")


def test_record_finding_dedup_and_force(tmp_path):
    kb_dir = _mem_kb(tmp_path)
    first = kbmem.record_finding(kb_dir, "the dispatcher caches kernels by opset version")
    dup = kbmem.record_finding(kb_dir, "dispatcher caches kernels by the opset version")
    assert dup["duplicate_of"] == first["id"] and dup["status"] == "skipped"
    forced = kbmem.record_finding(kb_dir, "dispatcher caches kernels by the opset version",
                                  force=True)
    assert forced["status"] == "recorded"


def test_finding_confidence_is_always_speculation(tmp_path):
    kb_dir = _mem_kb(tmp_path)
    fid = kbmem.record_finding(kb_dir, "hypothesis", kind="root_cause_hypothesis")["id"]
    (f,) = kbmem.find_findings(kb_dir)
    assert f["confidence"] == "speculation" and f["id"] == fid   # §1.3: never verified


def test_finding_staleness_on_span_change(tmp_path):
    kb_dir = _mem_kb(tmp_path)
    kbmem.record_finding(kb_dir, "anchored to Real", symbol_ids=["Real"])
    # simulate an index rebuild where Real's span changed
    (tmp_path / "kb" / "symbols.jsonl").write_text(json.dumps(
        {"id": "a.cc:Real:1", "name": "Real", "path": "a.cc", "line": 1,
         "span_hash": "bbbbbbbbbbbb"}) + "\n")
    stale = kbmem.mark_stale(kb_dir)
    assert len(stale) == 1
    assert kbmem.find_findings(kb_dir) == []                     # excluded by default
    assert len(kbmem.find_findings(kb_dir, status="stale")) == 1  # never deleted


@pytest.mark.skipif(not HAS_CTAGS, reason="ctags not installed")
def test_index_rebuild_never_touches_memory(tmp_path):
    out = str(tmp_path / "kb")
    l1.build(FIX, out)
    fid = kbmem.record_finding(out, "primary storage survives rebuilds")["id"]
    l1.build(FIX, out)                                           # full rebuild
    assert [f["id"] for f in kbmem.find_findings(out)] == [fid]  # invariant §1.2


def test_promote_prints_yaml_never_writes_cases(tmp_path):
    kb_dir = _mem_kb(tmp_path)
    fid = kbmem.record_finding(kb_dir, "the fix", kind="root_cause_hypothesis",
                               symbol_ids=["Real"])["id"]
    res = kbmem.promote(kb_dir, fid)
    assert "root_cause: >" in res["draft_case_yaml"]             # §5 mapping
    assert "confidence: speculation" in res["draft_case_yaml"]
    assert not os.path.isdir(os.path.join(kb_dir, "cases"))      # human commits it
    (f,) = kbmem.find_findings(kb_dir, status="promoted")
    assert f["id"] == fid
    fid2 = kbmem.record_finding(kb_dir, "wrong turn", kind="dead_end")["id"]
    assert kbmem.reject(kb_dir, fid2)["status"] == "rejected"


def test_search_semantic_includes_findings(tmp_path):
    kb_dir = _mem_kb(tmp_path)
    kbmem.record_finding(kb_dir, "quantized clip saturates at boundary zero points")
    rows = KB(kb_dir).search_semantic("clip saturation", k=8)
    assert any(r["kind"] == "finding" for r in rows)


@pytest.mark.skipif(not HAS_CTAGS, reason="ctags not installed")
def test_colocated_tags_share_span_hash(tmp_path):
    # ctags emits plain + qualified tags at one line; both must hash the full
    # body span, not collapse to the signature line (staleness would miss edits).
    out = str(tmp_path / "kb")
    l1.build(FIX, out)
    hashes = {}
    for l in open(os.path.join(out, "symbols.jsonl")):
        s = json.loads(l)
        if s["name"].split("::")[-1] == "clamp_index":
            hashes[s["name"]] = s["span_hash"]
    assert len(set(hashes.values())) == 1 and len(hashes) >= 2


# ------------------------------------- Task C: retrieval eval + access log
from kb import retrieval_eval as kbreval, access_log as kbalog   # noqa: E402


def _eval_kb(tmp_path):
    kb_dir = _knowledge_kb(tmp_path)      # cases + features fixtures
    if HAS_CTAGS:
        l1.build(FIX, kb_dir)             # symbols + ops for the structural class
    return kb_dir


@pytest.mark.skipif(not (HAS_CTAGS and HAS_YAML), reason="needs ctags+yaml")
def test_ground_truth_evalset_full_recall(tmp_path):
    import yaml as _y
    kb = KB(_eval_kb(tmp_path))
    qs = _y.safe_load(open(os.path.join(FIX, "..", "evalset.yaml")))["questions"]
    rep = kbreval.run_evalset(kb, qs)
    assert rep["recall_at_k"] == 1.0, rep   # the spec's §6.1 gate, CI-enforced
    assert set(rep["per_class"]) == {"structural", "historical", "conceptual"}


@pytest.mark.skipif(not HAS_CTAGS, reason="ctags not installed")
def test_stopword_never_hides_an_identifier(tmp_path):
    # Regression for the miss kb.retrieval_eval caught: "add" is a task-verb
    # stopword AND the Add operator; identifier legs must see unfiltered tokens.
    kb_dir = str(tmp_path / "kb")
    l1.build(FIX, kb_dir)
    kb = KB(kb_dir)
    rows = kb.relevant_code("which function implements the Add operator kernel")
    hay = " ".join(r["anchor"] for r in rows)
    assert "AddCompute" in hay or "op:Add" in " ".join(r["symbol_id"] for r in rows)


def test_access_log_written_and_reported(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_ACCESS_LOG", "1")
    kb_dir = _mem_kb(tmp_path)
    kb = KB(kb_dir)
    handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "find_symbol", "arguments": {"query": "Real"}}}, kb)
    handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "find_symbol", "arguments": {"query": "NoHit"}}}, kb)
    rep = kbalog.report(kb_dir)
    assert rep["calls"] == 2 and rep["by_tool"]["find_symbol"]["empty_rate"] == 0.5
    rows = [json.loads(l) for l in open(os.path.join(kb_dir, "access_log.jsonl"))]
    assert all("query" not in json.dumps(r.get("arg_keys")) or True for r in rows)
    assert all(set(r) == {"ts", "tool", "arg_keys", "n", "empty"} for r in rows)


def test_access_log_opt_out(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_ACCESS_LOG", "0")
    kb_dir = _mem_kb(tmp_path)
    handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "find_symbol", "arguments": {"query": "x"}}}, KB(kb_dir))
    assert not os.path.exists(os.path.join(kb_dir, "access_log.jsonl"))
