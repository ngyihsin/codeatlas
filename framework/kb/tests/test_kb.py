"""Tests for the kb pipeline. Run: cd framework/kb && python -m pytest -q"""
import json
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kb import l1, lint, incremental, l2                    # noqa: E402
from kb.mcp_server import KB, handle                        # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fixtures", "mini-runtime")
FIX = os.path.abspath(FIX)
HAS_CTAGS = shutil.which("ctags") is not None


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
