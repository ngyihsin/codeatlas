"""
kb.index_db — derived index.sqlite mirror (unified spec §2.1, Appendix R.4).

The JSONL artifacts stay the pipeline interchange format and the rebuild source
of truth; index.sqlite is a DERIVED cache over the scale-sensitive artifact —
the edge list (2.7M rows on PyTorch's ATen, ~7s to JSON-parse on every KB open,
vs. milliseconds to open a sqlite file with both-direction indexes).

What lives here (phase 1): `symbol_edges` with precise-over-heuristic
precedence resolved AT BUILD TIME — per the spec's normative rule, the edge
table is the single source of truth for graph queries; consumers never re-merge.
Symbols/ops/tests/summaries stay in-memory JSONL loads (0.3s at 58k symbols);
they migrate only when they measurably hurt.

Freshness: a `meta` stamp records (size, mtime) of every source JSONL. KB uses
the mirror only when the stamp matches — a stale mirror silently falls back to
JSONL, never serves old edges. kb.l1 and kb.scip_ingest rebuild the mirror as
the last step of their own writes.

  python -m kb.index_db build <kb_dir>
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

_SOURCES = ("edges.jsonl", "edges.precise.jsonl")


def _stamp(kb_dir: str) -> str:
    parts = []
    for name in _SOURCES:
        p = os.path.join(kb_dir, name)
        if os.path.isfile(p):
            st = os.stat(p)
            parts.append(f"{name}:{st.st_size}:{int(st.st_mtime)}")
        else:
            parts.append(f"{name}:absent")
    return ";".join(parts)


def db_path(kb_dir: str) -> str:
    return os.path.join(kb_dir, "index.sqlite")


def build(kb_dir: str) -> dict:
    """(Re)build the derived mirror from the JSONL artifacts. Idempotent;
    drops and recreates — index.sqlite must always be reproducible (§1.2)."""
    edges_p = os.path.join(kb_dir, "edges.jsonl")
    precise_p = os.path.join(kb_dir, "edges.precise.jsonl")
    tmp = db_path(kb_dir) + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    con = sqlite3.connect(tmp)
    try:
        con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        con.execute("CREATE TABLE symbol_edges (caller_id TEXT, callee_id TEXT,"
                    " xref TEXT, method TEXT)")
        n = 0

        def rows(path):
            if os.path.isfile(path):
                for l in open(path, encoding="utf-8"):
                    if l.strip():
                        yield json.loads(l)

        # Precise edges first; heuristic edges only where no precise pair exists
        # (same precedence KB.__init__ used to compute per-process, now baked in).
        seen: set[tuple] = set()
        batch = []
        for src in (precise_p, edges_p):
            for e in rows(src):
                key = (e.get("caller_id"), e.get("callee_id"))
                if key in seen:
                    continue
                seen.add(key)
                batch.append((e.get("caller_id"), e.get("callee_id"),
                              e.get("xref", ""), e.get("method", "")))
                if len(batch) >= 50000:
                    con.executemany("INSERT INTO symbol_edges VALUES (?,?,?,?)", batch)
                    n += len(batch); batch = []
        if batch:
            con.executemany("INSERT INTO symbol_edges VALUES (?,?,?,?)", batch)
            n += len(batch)
        con.execute("CREATE INDEX ix_edges_caller ON symbol_edges(caller_id)")
        con.execute("CREATE INDEX ix_edges_callee ON symbol_edges(callee_id)")
        con.execute("INSERT INTO meta VALUES ('stamp', ?)", (_stamp(kb_dir),))
        con.commit()
    finally:
        con.close()
    os.replace(tmp, db_path(kb_dir))     # atomic swap: readers never see partial
    return {"edges": n, "out": db_path(kb_dir)}


def fresh(kb_dir: str) -> bool:
    """True iff the mirror exists and its stamp matches the current JSONLs."""
    p = db_path(kb_dir)
    if not os.path.isfile(p):
        return False
    try:
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        row = con.execute("SELECT value FROM meta WHERE key='stamp'").fetchone()
        con.close()
    except sqlite3.Error:
        return False
    return bool(row) and row[0] == _stamp(kb_dir)


def connect_ro(kb_dir: str) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{db_path(kb_dir)}?mode=ro", uri=True,
                          check_same_thread=False)
    return con


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="kb.index_db")
    sub = ap.add_subparsers(dest="subcmd", required=True)
    bd = sub.add_parser("build"); bd.add_argument("kb_dir")
    a = ap.parse_args(argv)
    print(json.dumps(build(a.kb_dir)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
