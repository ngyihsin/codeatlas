"""MCP retrieval server — the agent's token-budgeted door to the KB.

A dependency-free JSON-RPC 2.0 server over stdio implementing the MCP methods
`initialize`, `tools/list`, `tools/call`. Every tool returns compact, budgeted results
(summaries/anchors, never whole files) so the agent never greps + cats blindly.

Tools (from the spec's retrieval API):
  find_symbol(query, detail)        — symbols matching a name, at the requested detail
  trace_callers(symbol, depth)      — who calls this (bounded BFS over the call graph)
  find_recipe(task)                 — L3 recipe lookup (keyword today; embeddings later)
  get_recipe_steps(recipe_id)       — the full recipe / decision tree
  what_changed(symbol)              — churn / last_modified (drift signal)
  review_status(symbol)             — verified | speculation | drifted

Backed by a KB directory (symbols.jsonl, edges.jsonl, ops.jsonl, recipes/*.yaml) built by
`kb.l1`. Point it with $KB_DIR or argv[1].

Run / verify:
  KB_DIR=/path/to/kb python -m kb.mcp_server     # then write JSON-RPC lines to stdin
"""
from __future__ import annotations

import json
import os
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

BUDGET = 25  # max rows any tool returns, to bound tokens


class KB:
    def __init__(self, kb_dir: str):
        self.dir = kb_dir
        self.symbols = self._jsonl("symbols.jsonl")
        self.edges = self._jsonl("edges.jsonl")
        self.ops = self._jsonl("ops.jsonl")
        self.recipes = self._recipes()

    def _jsonl(self, name: str) -> list[dict]:
        p = os.path.join(self.dir, name)
        if not os.path.isfile(p):
            return []
        return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]

    def _recipes(self) -> list[dict]:
        d = os.path.join(self.dir, "recipes")
        out = []
        if os.path.isdir(d) and yaml is not None:
            for fn in sorted(os.listdir(d)):
                if fn.endswith((".yaml", ".yml")):
                    r = yaml.safe_load(open(os.path.join(d, fn), encoding="utf-8")) or {}
                    r.setdefault("id", os.path.splitext(fn)[0])
                    out.append(r)
        return out

    # ---- tools ----
    def find_symbol(self, query: str, detail: str = "fold") -> list[dict]:
        q = query.lower()
        hits = [s for s in self.symbols if q in s.get("name", "").lower()]
        hits.sort(key=lambda s: -s.get("importance", 0))
        rows = []
        for s in hits[:BUDGET]:
            anchor = f"{s['path']} → {s['name']}"
            if detail == "fold":
                rows.append({"anchor": anchor, "kind": s.get("kind")})
            elif detail == "preview":
                rows.append({"anchor": anchor, "kind": s.get("kind"),
                             "signature": s.get("signature", ""),
                             "importance": s.get("importance", 0)})
            else:  # full
                rows.append(s)
        return rows

    def trace_callers(self, symbol: str, depth: int = 1) -> list[dict]:
        ids = [s["id"] for s in self.symbols if s.get("name") == symbol or s.get("id") == symbol]
        rev: dict[str, list[str]] = {}
        for e in self.edges:
            rev.setdefault(e["callee_id"], []).append(e["caller_id"])
        seen, frontier, out = set(ids), list(ids), []
        for _ in range(max(1, depth)):
            nxt = []
            for cid in frontier:
                for caller in rev.get(cid, []):
                    if caller not in seen:
                        seen.add(caller); nxt.append(caller)
                        out.append({"caller": caller, "of": cid})
                        if len(out) >= BUDGET:
                            return out
            frontier = nxt
        return out

    def find_recipe(self, task: str) -> list[dict]:
        # keyword match over task/when/title; spec: upgrade to semantic search over L3.
        q = set(task.lower().split())
        scored = []
        for r in self.recipes:
            hay = " ".join(str(r.get(k, "")) for k in ("title", "task", "when")).lower()
            score = sum(1 for w in q if w in hay)
            if score:
                scored.append((score, r))
        scored.sort(key=lambda x: -x[0])
        return [{"id": r["id"], "title": r.get("title", ""), "confidence": r.get("confidence", "draft")}
                for _, r in scored[:3]]

    def get_recipe_steps(self, recipe_id: str) -> dict:
        for r in self.recipes:
            if r.get("id") == recipe_id:
                return r
        return {"error": f"recipe '{recipe_id}' not found"}

    def what_changed(self, symbol: str) -> list[dict]:
        return [{"anchor": f"{s['path']} → {s['name']}", "churn": s.get("churn", 0),
                 "last_author": s.get("last_author", ""), "last_modified": s.get("last_modified", "")}
                for s in self.symbols if s.get("name") == symbol][:BUDGET]

    def review_status(self, symbol: str) -> list[dict]:
        # L1 facts are mechanical; until L2/L3 attach a status, report xref confidence.
        return [{"anchor": f"{s['path']} → {s['name']}",
                 "status": "mechanical (L1)", "importance": s.get("importance", 0)}
                for s in self.symbols if s.get("name") == symbol][:BUDGET]


TOOLS = [
    {"name": "find_symbol", "description": "Find symbols by name; detail=fold|preview|full.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"}, "detail": {"type": "string", "enum": ["fold", "preview", "full"]}},
         "required": ["query"]}},
    {"name": "trace_callers", "description": "Who calls this symbol (bounded BFS).",
     "inputSchema": {"type": "object", "properties": {
         "symbol": {"type": "string"}, "depth": {"type": "integer"}}, "required": ["symbol"]}},
    {"name": "find_recipe", "description": "Find an L3 recipe for a task.",
     "inputSchema": {"type": "object", "properties": {"task": {"type": "string"}}, "required": ["task"]}},
    {"name": "get_recipe_steps", "description": "Full recipe / decision tree by id.",
     "inputSchema": {"type": "object", "properties": {"recipe_id": {"type": "string"}}, "required": ["recipe_id"]}},
    {"name": "what_changed", "description": "Churn / last-modified for a symbol.",
     "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}},
    {"name": "review_status", "description": "Verification status for a symbol.",
     "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}},
]


def handle(req: dict, kb: KB) -> dict | None:
    mid = req.get("id")
    method = req.get("method", "")
    if method == "initialize":
        return _ok(mid, {"protocolVersion": "2024-11-05",
                         "capabilities": {"tools": {}},
                         "serverInfo": {"name": "codeatlas-kb", "version": "0.1.0"}})
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return _ok(mid, {"tools": TOOLS})
    if method == "tools/call":
        params = req.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {})
        fn = getattr(kb, name, None)
        if not callable(fn) or name not in {t["name"] for t in TOOLS}:
            return _err(mid, -32601, f"unknown tool: {name}")
        try:
            result = fn(**args)
        except TypeError as e:
            return _err(mid, -32602, f"bad arguments: {e}")
        return _ok(mid, {"content": [{"type": "text",
                                      "text": json.dumps(result, ensure_ascii=False)}]})
    return _err(mid, -32601, f"unknown method: {method}")


def _ok(mid, result):
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _err(mid, code, msg):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": msg}}


def main(argv: list[str]) -> int:
    kb_dir = (argv[0] if argv else None) or os.environ.get("KB_DIR")
    if not kb_dir:
        print("set KB_DIR or pass a kb dir", file=sys.stderr); return 2
    kb = KB(kb_dir)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            sys.stdout.write(json.dumps(_err(None, -32700, "parse error")) + "\n"); sys.stdout.flush()
            continue
        resp = handle(req, kb)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n"); sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
