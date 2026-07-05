"""MCP retrieval server — the agent's token-budgeted door to the KB.

A dependency-free JSON-RPC 2.0 server over stdio implementing the MCP methods
`initialize`, `tools/list`, `tools/call`. Every tool returns compact, budgeted results
(summaries/anchors, never whole files) so the agent never greps + cats blindly.

Tools (from the spec's retrieval API):
  find_symbol(query, detail)        — symbols by name, with the joined L2 summary if generated
  find_op(name)                     — op registry lookup (the spec's #1 artifact)
  get_summary(path)                 — the L2 explanation for a file or module path
  trace_callers(symbol, depth)      — who calls this (bounded BFS over the call graph)
  find_recipe(task)                 — L3 recipe lookup (keyword today; embeddings later)
  get_recipe_steps(recipe_id)       — the full recipe / decision tree
  what_changed(symbol)              — churn / last_modified (drift signal)
  review_status(symbol)             — L2 draft|reviewed if summarized, else mechanical (L1)

Backed by a KB directory built by `kb.l1` (symbols/edges/ops.jsonl, recipes/*.yaml) and
`kb.l2` (summaries.jsonl, joined to symbols by path). Point it with $KB_DIR or argv[1].

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
        # Precise scip-clang edges (if ingested) take precedence over heuristic ones.
        precise = self._jsonl("edges.precise.jsonl")
        if precise:
            seen = {(e["caller_id"], e["callee_id"]) for e in precise}
            self.edges = precise + [e for e in self.edges
                                    if (e["caller_id"], e["callee_id"]) not in seen]
        self.ops = self._jsonl("ops.jsonl")
        self.tests = self._jsonl("tests.jsonl")
        self.build_rows = self._jsonl("build_targets.jsonl")   # kb.buildsys (optional)
        # Join build targets to symbols by source path ("which target owns this file?").
        # File-API sources are relative to the code root already; static-scan sources
        # are relative to their CMakeLists dir (defined_in). ${VARS} can't be joined.
        self.target_by_path: dict[str, str] = {}
        for r in self.build_rows:
            if r.get("kind") != "target":
                continue
            base = os.path.dirname(r.get("defined_in", ""))
            for src in r.get("sources", []):
                if "$" in src:
                    continue
                p = os.path.normpath(os.path.join(base, src) if base else src)
                self.target_by_path.setdefault(p, r["name"])
        self.recipes = self._recipes()
        # L2: join generated summaries to symbols/files by path (seam fix).
        self.summaries = self._jsonl("summaries.jsonl")
        self.summary_by_path: dict[str, dict] = {}
        self.summary_by_id: dict[str, dict] = {}
        for s in self.summaries:
            if s.get("path"):
                self.summary_by_path.setdefault(s["path"], s)
            if s.get("id"):
                self.summary_by_id[s["id"]] = s

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
        for s in hits:
            anchor = f"{s['path']} → {s['name']}"
            # Prefer a symbol-scoped L2 summary (joined by symbol id); fall back to the
            # file-level summary; fall back to the bare L1 signature if neither exists.
            summ = self.summary_by_id.get(s.get("id")) or self.summary_by_path.get(s.get("path"))
            if detail == "fold":
                row = {"anchor": anchor, "kind": s.get("kind")}
                if summ:
                    row["fold"] = summ.get("fold")
                rows.append(row)
            elif detail == "preview":
                row = {"anchor": anchor, "kind": s.get("kind"),
                       "signature": s.get("signature", ""),
                       "importance": s.get("importance", 0)}
                if summ:  # the generated, lint-verified explanation
                    row["summary"] = summ.get("preview")
                    row["scope"] = summ.get("scope", "file")
                    row["evidence_level"] = summ.get("evidence_level")
                    row["confidence"] = summ.get("confidence", "draft")
                tgt = self.target_by_path.get(s.get("path"))
                if tgt:  # which build target owns this symbol's file (kb.buildsys)
                    row["build_target"] = tgt
                rows.append(row)
            else:  # full
                row = dict(s)
                if summ:
                    row["l2"] = {k: summ.get(k) for k in
                                 ("full", "evidence_level", "confidence")}
                tgt = self.target_by_path.get(s.get("path"))
                if tgt:
                    row["build_target"] = tgt
                rows.append(row)
        return rows

    def find_op(self, name: str) -> list[dict]:
        # The spec's #1 artifact, finally reachable: query the op registry.
        q = name.lower()
        hits = [o for o in self.ops if q in o.get("op_name", "").lower()]
        return [{"op": o.get("op_name"), "version": o.get("version"),
                 "provider": o.get("provider"), "framework": o.get("framework"),
                 "anchor": f"{o.get('kernel_path')}:{o.get('line')}"}
                for o in hits]

    def get_summary(self, path: str) -> dict:
        # Direct access to a file/module L2 explanation (e.g. "math/clip.cc" or "module:math").
        s = self.summary_by_path.get(path) or self.summary_by_id.get(path)
        return s or {"error": f"no L2 summary for {path!r} (not generated yet)"}

    def find_tests(self, symbol: str) -> list[dict]:
        # Which tests guard a symbol/op? (the regression set for safe change)
        leaf = symbol.split("::")[-1]
        hits = [t for t in self.tests if t.get("name") in (symbol, leaf)]
        return [{"test": t["test"], "guards": t["name"], "kind": t.get("kind", "regression")}
                for t in hits]

    def relevant_code(self, query: str, k: int = 5) -> list[dict]:
        # Hybrid NL→code retrieval (lexical + call-graph expansion + importance).
        from .retrieve import relevant_code as _rc
        return _rc(query, self.symbols, self.edges, self.ops,
                   self.summary_by_id, k=min(k, BUDGET))

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
        # Semantic (vector) search over the L3 recipe layer; keyword as graceful fallback.
        if getattr(self, "_recipe_index", None) is None:
            try:
                from .recipes import RecipeIndex
                self._recipe_index = RecipeIndex(self.recipes)
            except Exception:
                self._recipe_index = False
        if self._recipe_index:
            hits = self._recipe_index.search(task, k=3)
            if hits:
                return hits
        q = set(task.lower().split())          # fallback: keyword over title/task/when
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

    # ---- resources (application-driven, read-only context) ----
    def list_resources(self) -> list[dict]:
        out = [{"uri": "kb://ops", "name": "Op registry",
                "mimeType": "application/jsonl", "size": len(self.ops)}]
        if os.path.isfile(os.path.join(self.dir, "module_map.md")):
            out.append({"uri": "kb://module_map", "name": "Module map",
                        "mimeType": "text/markdown"})
        for s in self.summaries:
            if s.get("path"):
                out.append({"uri": f"kb://summary/{s['id']}", "name": s.get("fold", s["id"]),
                            "mimeType": "text/plain"})
        return out

    def read_resource(self, uri: str) -> dict:
        if uri == "kb://ops":
            return {"uri": uri, "mimeType": "application/jsonl",
                    "text": "\n".join(json.dumps(o) for o in self.ops)}
        if uri == "kb://module_map":
            p = os.path.join(self.dir, "module_map.md")
            return {"uri": uri, "mimeType": "text/markdown",
                    "text": open(p, encoding="utf-8").read() if os.path.isfile(p) else ""}
        if uri.startswith("kb://summary/"):
            sid = uri[len("kb://summary/"):]
            s = self.summary_by_id.get(sid)
            return {"uri": uri, "mimeType": "text/plain",
                    "text": json.dumps(s) if s else ""}
        return {"error": f"unknown resource {uri!r}"}

    def what_changed(self, symbol: str) -> list[dict]:
        return [{"anchor": f"{s['path']} → {s['name']}", "churn": s.get("churn", 0),
                 "last_author": s.get("last_author", ""), "last_modified": s.get("last_modified", "")}
                for s in self.symbols if s.get("name") == symbol]

    def review_status(self, symbol: str) -> list[dict]:
        # Reflect the real L2 review state. Match by name, qualified-name leaf, or id;
        # prefer the symbol-scoped summary (by id) over the file summary (by path).
        out = []
        for s in self.symbols:
            nm = s.get("name", "")
            if symbol not in (nm, nm.split("::")[-1], s.get("id")):
                continue
            summ = self.summary_by_id.get(s.get("id")) or self.summary_by_path.get(s.get("path"))
            status = (f"L2 {summ.get('confidence', 'draft')} ({summ.get('evidence_level')})"
                      if summ else "mechanical (L1)")
            out.append({"anchor": f"{s['path']} → {s['name']}", "status": status,
                        "importance": s.get("importance", 0)})
        return out

    def build_info(self, name: str = "") -> list[dict]:
        # The build system as knowledge (kb.buildsys): targets/options/packages.
        # No name -> compact overview; name -> matching rows with full detail.
        if not self.build_rows:
            return [{"error": "no build_targets.jsonl — run: python -m kb.buildsys "
                              "<code_root> <kb_dir>"}]
        if name:
            q = name.lower()
            return [r for r in self.build_rows if q in r.get("name", "").lower()]
        targets = [r for r in self.build_rows if r["kind"] == "target"]
        return [{"targets": len(targets),
                 "options": sum(r["kind"] == "option" for r in self.build_rows),
                 "packages": sum(r["kind"] == "package" for r in self.build_rows),
                 "fidelity": self.build_rows[0].get("fidelity"),
                 "method": self.build_rows[0].get("method"),
                 "target_names": [t["name"] for t in targets]}]


TOOLS = [
    {"name": "find_symbol", "description": "Find symbols by name; detail=fold|preview|full.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"}, "detail": {"type": "string", "enum": ["fold", "preview", "full"]}},
         "required": ["query"]}},
    {"name": "trace_callers", "description": "Who calls this symbol (bounded BFS).",
     "inputSchema": {"type": "object", "properties": {
         "symbol": {"type": "string"}, "depth": {"type": "integer"}}, "required": ["symbol"]}},
    {"name": "relevant_code", "description": "Rank symbols/ops relevant to a natural-language query.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"}, "k": {"type": "integer"}}, "required": ["query"]}},
    {"name": "find_op", "description": "Find op registrations by name (the op registry).",
     "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "get_summary", "description": "Get the L2 explanation for a file or module path.",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "find_tests", "description": "Tests that guard a symbol/op (the regression set).",
     "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}},
    {"name": "find_recipe", "description": "Find an L3 recipe for a task.",
     "inputSchema": {"type": "object", "properties": {"task": {"type": "string"}}, "required": ["task"]}},
    {"name": "get_recipe_steps", "description": "Full recipe / decision tree by id.",
     "inputSchema": {"type": "object", "properties": {"recipe_id": {"type": "string"}}, "required": ["recipe_id"]}},
    {"name": "what_changed", "description": "Churn / last-modified for a symbol.",
     "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}},
    {"name": "build_info", "description": "Build-system map: targets/deps/options (kb.buildsys).",
     "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}}},
    {"name": "review_status", "description": "Verification status for a symbol.",
     "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}},
]


PROTOCOL_VERSION = "2025-06-18"
_PAGE = 50          # items per page for list endpoints


def _encode_cursor(offset: int) -> str:
    import base64
    return base64.urlsafe_b64encode(json.dumps({"o": offset}).encode()).decode()


def _decode_cursor(cursor: str | None) -> int | None:
    if not cursor:
        return 0
    try:
        import base64
        return int(json.loads(base64.urlsafe_b64decode(cursor.encode())).get("o", 0))
    except Exception:
        return None      # invalid cursor -> caller gets -32602


def _paginate(items: list, offset: int, size: int) -> tuple[list, str | None]:
    page = items[offset:offset + size]
    nxt = _encode_cursor(offset + size) if offset + size < len(items) else None
    return page, nxt


def handle(req: dict, kb: KB) -> dict | None:
    mid = req.get("id")
    method = req.get("method", "")
    if method == "initialize":
        return _ok(mid, {"protocolVersion": PROTOCOL_VERSION,
                         "capabilities": {"tools": {"listChanged": False},
                                          "resources": {"listChanged": False}},
                         "serverInfo": {"name": "codeatlas-kb", "version": "0.2.0"}})
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None

    if method == "tools/list":
        off = _decode_cursor(req.get("params", {}).get("cursor"))
        if off is None:
            return _err(mid, -32602, "invalid cursor")
        page, nxt = _paginate(TOOLS, off, _PAGE)
        return _ok(mid, {"tools": page, **({"nextCursor": nxt} if nxt else {})})

    if method == "resources/list":
        off = _decode_cursor(req.get("params", {}).get("cursor"))
        if off is None:
            return _err(mid, -32602, "invalid cursor")
        page, nxt = _paginate(kb.list_resources(), off, _PAGE)
        return _ok(mid, {"resources": page, **({"nextCursor": nxt} if nxt else {})})

    if method == "resources/read":
        uri = req.get("params", {}).get("uri", "")
        res = kb.read_resource(uri)
        if "error" in res:
            return _err(mid, -32602, res["error"])
        return _ok(mid, {"contents": [res]})

    if method == "tools/call":
        params = req.get("params", {})
        name = params.get("name")
        args = dict(params.get("arguments", {}))
        cursor = args.pop("cursor", None)          # paginate large tool results
        fn = getattr(kb, name, None)
        if not callable(fn) or name not in {t["name"] for t in TOOLS}:
            return _err(mid, -32601, f"unknown tool: {name}")
        try:
            result = fn(**args)
        except TypeError as e:
            return _err(mid, -32602, f"bad arguments: {e}")
        if isinstance(result, list):               # honest pagination: total + nextCursor
            off = _decode_cursor(cursor)
            if off is None:
                return _err(mid, -32602, "invalid cursor")
            page, nxt = _paginate(result, off, BUDGET)
            out = {"content": [{"type": "text", "text": json.dumps(page, ensure_ascii=False)}],
                   "total": len(result), "returned": len(page)}
            if nxt:
                out["nextCursor"] = nxt            # fixes silent truncation
            return _ok(mid, out)
        return _ok(mid, {"content": [{"type": "text",
                                      "text": json.dumps(result, ensure_ascii=False)}]})
    return _err(mid, -32601, f"unknown method: {method}")


def _ok(mid, result):
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _err(mid, code, msg):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": msg}}


def serve_http(kb: KB, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Streamable-HTTP-style transport (MCP 2025-06-18): one endpoint, POST per message,
    JSON response (or 202 for notifications). Localhost-bound; validates Origin to avoid
    DNS-rebinding. Dependency-free (stdlib http.server)."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):            # quiet
            pass

        def _bad(self, code, msg):
            self.send_response(code); self.end_headers()
            self.wfile.write(msg.encode())

        def do_POST(self):
            origin = self.headers.get("Origin", "")
            if origin and not (origin.startswith("http://127.0.0.1")
                               or origin.startswith("http://localhost")):
                return self._bad(403, "forbidden origin")
            n = int(self.headers.get("Content-Length", 0))
            try:
                req = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                body = json.dumps(_err(None, -32700, "parse error")).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body))); self.end_headers()
                return self.wfile.write(body)
            resp = handle(req, kb)
            if resp is None:                  # notification -> 202, no body
                return self._bad(202, "")
            body = json.dumps(resp, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body))); self.end_headers()
            self.wfile.write(body)

        def do_GET(self):                     # no server-initiated stream
            self._bad(405, "method not allowed")

    ThreadingHTTPServer((host, port), H).serve_forever()


def main(argv: list[str]) -> int:
    if "--http" in argv:
        i = argv.index("--http")
        port = int(argv[i + 1]) if i + 1 < len(argv) else 8765
        argv = argv[:i] + argv[i + 2:]
    else:
        port = None
    kb_dir = (argv[0] if argv else None) or os.environ.get("KB_DIR")
    if not kb_dir:
        print("set KB_DIR or pass a kb dir", file=sys.stderr); return 2
    kb = KB(kb_dir)
    if port is not None:
        print(f"codeatlas-kb MCP on http://127.0.0.1:{port} (POST JSON-RPC)", file=sys.stderr)
        serve_http(kb, port=port)
        return 0
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
