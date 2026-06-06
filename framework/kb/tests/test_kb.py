"""Tests for the kb pipeline. Run: cd framework/kb && python -m pytest -q"""
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kb import l1, lint, incremental                       # noqa: E402
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
