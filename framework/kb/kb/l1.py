"""L1 — the structural layer.

Mechanically extracts, from a codebase, the navigation map agentic search needs:
  - symbols.jsonl   definitions (ctags), with PageRank importance + git churn
  - edges.jsonl     caller -> callee approximation (heuristic; tagged xref:partial)
  - ops.jsonl       op registrations from macros (registration_patterns.yaml) -- the
                    single most valuable table for ML-runtime work
  - module_map.md   human/agent readable top-level map

No LLM. Dependency-light: ctags (universal-ctags) for symbols, ripgrep optional, PyYAML
for the patterns. PageRank is a small pure-Python power iteration (no networkx).

CLI:
  python -m kb.l1 build <codebase> <out_dir> [--patterns FILE]
  python -m kb.l1 ops   <path> [-|<out.jsonl>] [--patterns FILE]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict, field

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

CODE_EXT = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hh", ".py", ".java",
            ".go", ".rs", ".js", ".ts", ".m", ".mm"}
CODE_KINDS = {"function", "method", "prototype", "class", "struct", "interface",
              "enum", "union", "typedef", "macro", "namespace", "trait"}
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATTERNS = os.path.join(os.path.dirname(HERE), "registration_patterns.yaml")


# --------------------------------------------------------------------------- ops
@dataclass
class Op:
    op_name: str
    provider: str
    domain: str
    version: str
    macro: str
    framework: str
    kernel_path: str
    line: int


def load_patterns(path: str | None = None) -> list[dict]:
    path = path or DEFAULT_PATTERNS
    if yaml is None:
        raise RuntimeError("PyYAML is required to load registration patterns")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    pats = data.get("patterns", [])
    for p in pats:
        p["_re"] = re.compile(p["regex"])
    return pats


def extract_ops(code_root: str, patterns: list[dict]) -> list[Op]:
    """Scan source files for op-registration macros defined in `patterns`."""
    ops: list[Op] = []
    for path in _iter_code_files(code_root):
        try:
            text = _read(path)
        except OSError:
            continue
        rel = os.path.relpath(path, code_root)
        for p in patterns:
            for m in p["_re"].finditer(text):
                g = m.groupdict()
                line = text.count("\n", 0, m.start()) + 1
                ops.append(Op(
                    op_name=g.get("op_name", "?"),
                    provider=g.get("provider") or p.get("provider", "?"),
                    domain=g.get("domain") or p.get("domain", ""),
                    version=g.get("version") or p.get("version", ""),
                    macro=p["macro"],
                    framework=p.get("framework", ""),
                    kernel_path=rel,
                    line=line,
                ))
    ops.sort(key=lambda o: (o.framework, o.provider, o.op_name, o.kernel_path, o.line))
    return ops


# ----------------------------------------------------------------------- symbols
@dataclass
class Symbol:
    id: str
    name: str
    kind: str
    path: str
    line: int
    language: str = ""
    scope: str = ""
    signature: str = ""
    importance: float = 0.0
    churn: int = 0
    last_author: str = ""
    last_modified: str = ""
    span_hash: str = ""     # staleness anchor (unified spec §1.4)


def compute_span_hashes(code_root: str, symbols: list["Symbol"]) -> None:
    """Fill span_hash in place. A symbol's span is [its line, next symbol's line)
    within its file — the same convention build_edges uses for bodies — so drift
    detection and the call graph key on identical text."""
    import hashlib
    by_path: dict[str, list[Symbol]] = {}
    for s in symbols:
        by_path.setdefault(s.path, []).append(s)
    for path, syms in by_path.items():
        try:
            lines = open(os.path.join(code_root, path), encoding="utf-8",
                         errors="replace").read().splitlines()
        except OSError:
            continue
        ordered = sorted(syms, key=lambda s: s.line)
        starts = sorted({s.line for s in ordered})
        nxt = {ln: starts[i + 1] for i, ln in enumerate(starts[:-1])}
        for s in ordered:
            # co-located tags (ctags plain + qualified) are one code object: the
            # span runs to the next *distinct* start line, not the twin tag.
            end = nxt.get(s.line, len(lines) + 1) - 1
            span = "\n".join(lines[max(s.line - 1, 0):max(end, s.line)])
            s.span_hash = hashlib.sha256(span.encode()).hexdigest()[:12]


def extract_symbols(code_root: str) -> list[Symbol]:
    """Definitions via universal-ctags (JSON). Returns [] if ctags is unavailable."""
    try:
        out = subprocess.run(
            ["ctags", "--output-format=json", "--fields=+nKlS", "--extras=+q",
             "-R", "-f", "-", code_root],
            capture_output=True, text=True, check=False,
        ).stdout
    except FileNotFoundError:
        return []
    syms: list[Symbol] = []
    for line in out.splitlines():
        try:
            t = json.loads(line)
        except ValueError:
            continue
        if t.get("_type") != "tag" or not t.get("name") or not t.get("path"):
            continue
        rel = os.path.relpath(t["path"], code_root)
        if os.path.splitext(rel)[1] not in CODE_EXT:   # same gate as file_hashes
            continue
        ln = int(t.get("line", 0) or 0)
        syms.append(Symbol(
            id=f"{rel}:{t['name']}:{ln}",
            name=t["name"], kind=t.get("kind", ""), path=rel, line=ln,
            language=t.get("language", ""), scope=t.get("scope", ""),
            signature=t.get("signature", ""),
        ))
    syms.sort(key=lambda s: (s.path, s.line, s.name))
    return syms


# ------------------------------------------------------------------------- edges
def build_edges(code_root: str, symbols: list[Symbol],
                only_paths: set[str] | None = None) -> list[dict]:
    """Heuristic call graph (xref:partial): within each file, approximate a function's
    body as [its line, next def's line) and emit an edge to every other known symbol
    referenced in that span. Cheap but useful for importance ranking; not LSP-accurate.

    `only_paths` restricts which *caller* files are scanned (callee resolution stays
    global) — used by the incremental rebuild to re-derive just the changed files.
    """
    by_path: dict[str, list[Symbol]] = {}
    for s in symbols:
        if s.kind in ("function", "method"):
            if only_paths is not None and s.path not in only_paths:
                continue
            by_path.setdefault(s.path, []).append(s)
    # name -> candidate symbol ids (for resolving references)
    name_to_ids: dict[str, list[str]] = {}
    for s in symbols:
        if s.kind in CODE_KINDS:
            name_to_ids.setdefault(s.name, []).append(s.id)

    edges: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for path, fns in by_path.items():
        fns = sorted(fns, key=lambda s: s.line)
        try:
            lines = _read(os.path.join(code_root, path)).splitlines()
        except OSError:
            continue
        for i, fn in enumerate(fns):
            start = fn.line
            end = fns[i + 1].line - 1 if i + 1 < len(fns) else len(lines)
            body = "\n".join(lines[start:end])  # exclude the signature line itself
            for name in set(re.findall(r"[A-Za-z_]\w{2,}", body)):
                if name == fn.name or name not in name_to_ids:
                    continue
                for cid in name_to_ids[name]:
                    if cid == fn.id:
                        continue
                    key = (fn.id, cid)
                    if key in seen:
                        continue
                    seen.add(key)
                    edges.append({"caller_id": fn.id, "callee_id": cid,
                                  "method": "heuristic", "xref": "partial"})
    edges.sort(key=lambda e: (e["caller_id"], e["callee_id"]))
    return edges


def pagerank(symbols: list[Symbol], edges: list[dict],
             damping: float = 0.85, iters: int = 30) -> dict[str, float]:
    """Pure-Python PageRank over the call graph (no networkx)."""
    nodes = [s.id for s in symbols]
    if not nodes:
        return {}
    idx = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)
    out: dict[int, list[int]] = {}
    for e in edges:
        a, b = idx.get(e["caller_id"]), idx.get(e["callee_id"])
        if a is not None and b is not None:
            out.setdefault(a, []).append(b)
    rank = [1.0 / n] * n
    for _ in range(iters):
        nxt = [(1.0 - damping) / n] * n
        dangling = 0.0
        for i in range(n):
            outs = out.get(i)
            if not outs:
                dangling += rank[i]
                continue
            share = damping * rank[i] / len(outs)
            for j in outs:
                nxt[j] += share
        # redistribute dangling mass uniformly
        nxt = [v + damping * dangling / n for v in nxt]
        rank = nxt
    return {nodes[i]: rank[i] for i in range(n)}


# -------------------------------------------------------------------------- churn
def git_churn(code_root: str) -> dict[str, dict]:
    """Per-file churn / last_author / last_modified from git log (best-effort)."""
    info: dict[str, dict] = {}
    try:
        log = subprocess.run(
            ["git", "-C", code_root, "log", "--no-merges", "--format=%H%x09%an%x09%ad",
             "--date=short", "--name-only"],
            capture_output=True, text=True, check=False,
        ).stdout
    except FileNotFoundError:
        return info
    author = date = ""
    for line in log.splitlines():
        if "\t" in line and len(line.split("\t")) == 3:
            _, author, date = line.split("\t")
        elif line.strip():
            d = info.setdefault(line.strip(), {"churn": 0, "last_author": "", "last_modified": ""})
            d["churn"] += 1
            if not d["last_modified"]:  # log is newest-first
                d["last_author"], d["last_modified"] = author, date
    return info


# ------------------------------------------------------------------------- tests
_TEST_MACRO = re.compile(r"\bTEST(?:_[FP])?\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)")
_IDENT = re.compile(r"[A-Za-z_]\w{2,}")


def _is_test_file(rel: str) -> bool:
    b = os.path.basename(rel).lower()
    return "test" in b or "/test" in ("/" + rel.lower()) or "gtest" in b


def extract_tests(code_root: str, symbols: list[Symbol], ops: list[Op]) -> list[dict]:
    """Map symbol/op -> the tests that exercise it (FR-3). Heuristic: a test file
    'covers' a project symbol/op whose name it references. Coarse but the question it
    answers — 'what guards this code?' — is load-bearing for safe change."""
    names = {s.name.split("::")[-1] for s in symbols if s.kind in CODE_KINDS
             and len(s.name) > 2}
    op_names = {o.op_name for o in ops}
    targets = names | op_names
    rows, seen = [], set()
    for full in _iter_code_files(code_root):
        rel = os.path.relpath(full, code_root)
        if not _is_test_file(rel):
            continue
        text = _read(full)
        suites = _TEST_MACRO.findall(text)
        anchor = rel + (f"::{suites[0][0]}.{suites[0][1]}" if suites else "")
        for nm in set(_IDENT.findall(text)) & targets:
            key = (nm, anchor)
            if key not in seen:
                seen.add(key)
                rows.append({"name": nm, "test": anchor, "path": rel, "kind": "regression"})
    rows.sort(key=lambda r: (r["name"], r["test"]))
    return rows


# ----------------------------------------------------- incremental edge ownership
def file_hashes(code_root: str) -> dict[str, str]:
    """Per-file content hash (Bazel/Turborepo content-addressing) for change detection."""
    import hashlib
    out: dict[str, str] = {}
    for full in _iter_code_files(code_root):
        rel = os.path.relpath(full, code_root)
        try:
            out[rel] = hashlib.sha256(open(full, "rb").read()).hexdigest()
        except OSError:
            pass
    return out


def rebuild_edges(code_root: str, symbols: list[Symbol], prev_edges: list[dict],
                  changed_paths: set[str]) -> list[dict]:
    """Glean-style derived-fact invalidation: edges are *owned by the caller file*.
    Keep edges whose caller file is unchanged (and still valid), re-derive edges for
    changed files only, and drop any edge dangling against the current symbol table.

    Invariant: with `changed_paths` covering every file actually edited and no new
    globally-referenced symbol names introduced, this equals a full `build_edges`.
    A periodic full rebuild is the backstop for the new-global-name case.
    """
    id_to_path = {s.id: s.path for s in symbols}   # names contain '::' — don't string-split ids
    changed = set(changed_paths)
    kept = [e for e in prev_edges
            if id_to_path.get(e["caller_id"]) not in changed
            and e["caller_id"] in id_to_path and e["callee_id"] in id_to_path]
    fresh = build_edges(code_root, symbols, only_paths=changed)
    return sorted(kept + fresh, key=lambda e: (e["caller_id"], e["callee_id"]))


# --------------------------------------------------------------------------- build
def build(code_root: str, out_dir: str, patterns_path: str | None = None) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    symbols = extract_symbols(code_root)
    compute_span_hashes(code_root, symbols)

    # Incremental edges: re-derive only changed files' edges when a prior build exists.
    hashes = file_hashes(code_root)
    cache_path = os.path.join(out_dir, "l1_cache.json")
    edges_path = os.path.join(out_dir, "edges.jsonl")
    prev_hashes: dict[str, str] = {}
    if os.path.isfile(cache_path):
        try:
            prev_hashes = json.load(open(cache_path, encoding="utf-8")).get("file_hashes", {})
        except ValueError:
            prev_hashes = {}
    mode = "full"
    if prev_hashes and os.path.isfile(edges_path):
        changed = {p for p, h in hashes.items() if prev_hashes.get(p) != h}
        changed |= (set(prev_hashes) - set(hashes))   # removed files own no edges
        prev_edges = [json.loads(l) for l in open(edges_path, encoding="utf-8") if l.strip()]
        edges = rebuild_edges(code_root, symbols, prev_edges, changed)
        mode = "incremental"
    else:
        edges = build_edges(code_root, symbols)
        changed = set(hashes)
    pr = pagerank(symbols, edges)
    churn = git_churn(code_root)
    for s in symbols:
        s.importance = round(pr.get(s.id, 0.0), 8)
        c = churn.get(s.path)
        if c:
            s.churn, s.last_author, s.last_modified = c["churn"], c["last_author"], c["last_modified"]
    ops = extract_ops(code_root, load_patterns(patterns_path))
    tests = extract_tests(code_root, symbols, ops)

    _write_jsonl(os.path.join(out_dir, "symbols.jsonl"), (asdict(s) for s in symbols))
    _write_jsonl(os.path.join(out_dir, "edges.jsonl"), edges)
    _write_jsonl(os.path.join(out_dir, "ops.jsonl"), (asdict(o) for o in ops))
    _write_jsonl(os.path.join(out_dir, "tests.jsonl"), tests)
    _write_module_map(os.path.join(out_dir, "module_map.md"), code_root, symbols, ops)
    json.dump({"file_hashes": hashes}, open(cache_path, "w", encoding="utf-8"))
    from . import index_db
    index_db.build(out_dir)      # refresh the derived sqlite mirror (spec R.4)
    return {"symbols": len(symbols), "edges": len(edges), "ops": len(ops),
            "tests": len(tests), "mode": mode, "changed": len(changed), "out": out_dir}


def _write_module_map(path: str, code_root: str, symbols: list[Symbol], ops: list[Op]) -> None:
    import collections
    dirs = collections.Counter()
    for s in symbols:
        top = s.path.split("/", 1)[0] if "/" in s.path else "(root)"
        dirs[top] += 1
    top_syms = sorted([s for s in symbols if s.kind in CODE_KINDS],
                      key=lambda s: -s.importance)[:20]
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Module Map (L1) — {os.path.basename(os.path.abspath(code_root))}\n\n")
        f.write(f"{len(symbols)} symbols · {len(ops)} op registrations. Generated by `kb.l1`.\n\n")
        f.write("## Directories\n\n| dir | symbols |\n|---|---|\n")
        for d, c in dirs.most_common():
            f.write(f"| `{d}/` | {c} |\n")
        f.write("\n## Most important symbols (PageRank)\n\n| symbol | kind | anchor | importance |\n|---|---|---|---|\n")
        for s in top_syms:
            f.write(f"| `{s.name}` | {s.kind} | `{s.path} → {s.name}` | {s.importance:.5f} |\n")
        if ops:
            f.write("\n## Registered ops\n\n| op | provider | framework | macro | anchor |\n|---|---|---|---|---|\n")
            for o in ops:
                f.write(f"| `{o.op_name}` | {o.provider} | {o.framework} | `{o.macro}` | `{o.kernel_path}:{o.line}` |\n")


# ------------------------------------------------------------------------- helpers
def _iter_code_files(root: str):
    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for fn in files:
            if os.path.splitext(fn)[1] in CODE_EXT:
                yield os.path.join(r, fn)


def _read(path: str) -> str:
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


def _write_jsonl(path: str, rows) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            row = {k: v for k, v in row.items() if not k.startswith("_")}
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _main(argv: list[str]) -> int:
    if not argv:
        print(__doc__); return 2
    cmd = argv[0]
    if cmd == "build":
        if len(argv) < 3:
            print("usage: kb.l1 build <codebase> <out_dir> [--patterns FILE]"); return 2
        pf = argv[argv.index("--patterns") + 1] if "--patterns" in argv else None
        stats = build(argv[1], argv[2], pf)
        print(json.dumps(stats)); return 0
    if cmd == "ops":
        if len(argv) < 2:
            print("usage: kb.l1 ops <path> [out.jsonl|-] [--patterns FILE]"); return 2
        pf = argv[argv.index("--patterns") + 1] if "--patterns" in argv else None
        ops = extract_ops(argv[1], load_patterns(pf))
        dest = argv[2] if len(argv) > 2 and not argv[2].startswith("--") else "-"
        lines = "\n".join(json.dumps(asdict(o), ensure_ascii=False, sort_keys=True) for o in ops)
        if dest == "-":
            print(lines)
        else:
            open(dest, "w", encoding="utf-8").write(lines + "\n")
        print(f"# {len(ops)} ops", file=sys.stderr); return 0
    print(f"unknown command: {cmd}"); return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
