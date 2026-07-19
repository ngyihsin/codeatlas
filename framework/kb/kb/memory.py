"""
kb.memory — the M layer: agent findings write-back (unified spec §2.2, §4.2, §5).

L1–L3 are what the KB *knows*; this is what agents *learned the hard way* —
gotchas, dead ends, root-cause hypotheses. Uncurated, speculation by default,
promotable to an L3 case by a human. Two invariants from the spec:

  - PRIMARY storage: memory.sqlite is never derived and never touched by index
    rebuilds (kb.l1 writes only its own artifacts). WAL mode for concurrent
    writers (an HTTP team server implies them).
  - Agents can never set confidence='verified' (§1.3). record_finding hardcodes
    'speculation'; promotion prints draft YAML for a human, it never writes
    cases/ itself (§5).

Staleness: findings capture symbol_span_hashes at write time; kb.drift verify
calls mark_stale() to flip findings whose anchor symbols changed or vanished.
Stale findings drop out of default retrieval but are never deleted.

CLI (curation, §5):
  python -m kb.memory list <kb_dir> [--status active|stale|promoted|rejected]
  python -m kb.memory show <kb_dir> <id>
  python -m kb.memory promote <kb_dir> <id> --confirm    # prints draft Case YAML
  python -m kb.memory reject  <kb_dir> <id> --confirm
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sqlite3
import sys
import uuid

TEXT_CAP = 2000
KINDS = ("observation", "gotcha", "dead_end", "root_cause_hypothesis")
_DUP_JACCARD = 0.6

_SCHEMA = """
CREATE TABLE IF NOT EXISTS findings (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  author TEXT NOT NULL,
  codebase TEXT NOT NULL,
  text TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'observation'
    CHECK(kind IN ('observation','gotcha','dead_end','root_cause_hypothesis')),
  symbol_ids TEXT,
  symbol_span_hashes TEXT,
  confidence TEXT NOT NULL DEFAULT 'speculation',
  status TEXT NOT NULL DEFAULT 'active'
    CHECK(status IN ('active','stale','promoted','rejected')),
  promoted_case_id TEXT
);
"""


def _db(kb_dir: str) -> sqlite3.Connection:
    os.makedirs(kb_dir, exist_ok=True)
    con = sqlite3.connect(os.path.join(kb_dir, "memory.sqlite"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(_SCHEMA)
    try:                                       # FTS5 mirror for find_findings
        con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS findings_fts "
                    "USING fts5(id UNINDEXED, text, kind)")
    except sqlite3.OperationalError:           # FTS5-less build: LIKE fallback
        pass
    con.commit()
    return con


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _tokens(text: str) -> set[str]:
    return {t for t in "".join(c if c.isalnum() else " " for c in text.lower()).split()
            if len(t) > 2}


def _known_symbols(kb_dir: str) -> dict[str, str]:
    """symbol identifier (id, name, leaf) -> span_hash, from symbols.jsonl."""
    path = os.path.join(kb_dir, "symbols.jsonl")
    out: dict[str, str] = {}
    if os.path.isfile(path):
        for l in open(path, encoding="utf-8"):
            if l.strip():
                s = json.loads(l)
                h = s.get("span_hash", "")
                for key in (s.get("id"), s.get("name"),
                            (s.get("name") or "").split("::")[-1]):
                    if key:
                        out.setdefault(key, h)
    return out


def record_finding(kb_dir: str, text: str, symbol_ids: list[str] | None = None,
                   kind: str = "observation", author: str = "agent",
                   codebase: str = "", force: bool = False) -> dict:
    """Store one finding. Guardrails (§4.2): length cap, kind whitelist, symbol
    validation (unknown ids stored but flagged dangling), near-duplicate check
    that returns duplicate_of instead of blind-inserting (force=True overrides)."""
    if not text or not text.strip():
        return {"error": "empty finding text"}
    if len(text) > TEXT_CAP:
        return {"error": f"finding text exceeds {TEXT_CAP} chars ({len(text)}) — "
                         "distill it; step-by-step logs don't belong in memory"}
    if kind not in KINDS:
        return {"error": f"kind must be one of {list(KINDS)}"}
    symbol_ids = symbol_ids or []
    known = _known_symbols(kb_dir)
    dangling = [s for s in symbol_ids if s not in known]
    span_hashes = {s: known[s] for s in symbol_ids if s in known and known[s]}

    con = _db(kb_dir)
    try:
        if not force:
            new_toks = _tokens(text)
            for row in con.execute(
                    "SELECT id, text FROM findings WHERE status='active'"):
                old_toks = _tokens(row["text"])
                union = new_toks | old_toks
                if union and len(new_toks & old_toks) / len(union) >= _DUP_JACCARD:
                    return {"duplicate_of": row["id"], "status": "skipped",
                            "hint": "pass force=True if this is genuinely new"}
        fid = "finding-" + uuid.uuid4().hex[:8]
        with con:                              # transactional (concurrent writers)
            con.execute(
                "INSERT INTO findings (id, created_at, author, codebase, text, kind,"
                " symbol_ids, symbol_span_hashes) VALUES (?,?,?,?,?,?,?,?)",
                (fid, _now(), author, codebase, text.strip(), kind,
                 json.dumps(symbol_ids), json.dumps(span_hashes)))
            try:
                con.execute("INSERT INTO findings_fts (id, text, kind) VALUES (?,?,?)",
                            (fid, text.strip(), kind))
            except sqlite3.OperationalError:
                pass
        out = {"id": fid, "status": "recorded"}
        if dangling:
            out["dangling_symbol_ids"] = dangling
        return out
    finally:
        con.close()


def find_findings(kb_dir: str, query: str = "", symbol: str = "",
                  status: str = "active", limit: int = 10) -> list[dict]:
    con = _db(kb_dir)
    try:
        ids = None
        if query:
            try:
                fts_q = " OR ".join(_tokens(query)) or query
                ids = [r["id"] for r in con.execute(
                    "SELECT id FROM findings_fts WHERE findings_fts MATCH ?", (fts_q,))]
            except sqlite3.OperationalError:
                ids = [r["id"] for r in con.execute(
                    "SELECT id FROM findings WHERE text LIKE ?", (f"%{query}%",))]
        sql, params = "SELECT * FROM findings WHERE 1=1", []
        if status:
            sql += " AND status=?"; params.append(status)
        if symbol:
            sql += " AND symbol_ids LIKE ?"; params.append(f'%"{symbol}"%')
        rows = [dict(r) for r in con.execute(sql + " ORDER BY created_at DESC", params)]
        if ids is not None:
            order = {fid: i for i, fid in enumerate(ids)}
            rows = sorted((r for r in rows if r["id"] in order),
                          key=lambda r: order[r["id"]])
        out = []
        for r in rows[:limit]:
            out.append({"kind": "finding", "id": r["id"], "finding_kind": r["kind"],
                        "text": r["text"], "confidence": r["confidence"],
                        "status": r["status"], "created_at": r["created_at"],
                        "symbol_ids": json.loads(r["symbol_ids"] or "[]")})
        return out
    finally:
        con.close()


def mark_stale(kb_dir: str) -> list[str]:
    """Verify #3 (§3): active findings whose anchor symbols changed or vanished
    become status='stale' — excluded from default retrieval, never deleted."""
    if not os.path.isfile(os.path.join(kb_dir, "memory.sqlite")):
        return []
    current = _known_symbols(kb_dir)
    con = _db(kb_dir)
    try:
        stale = []
        for r in con.execute("SELECT id, symbol_span_hashes FROM findings "
                             "WHERE status='active'"):
            anchors = json.loads(r["symbol_span_hashes"] or "{}")
            if anchors and any(current.get(sym) != h for sym, h in anchors.items()):
                stale.append(r["id"])
        if stale:
            with con:
                con.executemany("UPDATE findings SET status='stale' WHERE id=?",
                                [(i,) for i in stale])
        return stale
    finally:
        con.close()


# ------------------------------------------------------------- curation (§5)
def _get(con: sqlite3.Connection, fid: str) -> dict | None:
    r = con.execute("SELECT * FROM findings WHERE id=?", (fid,)).fetchone()
    return dict(r) if r else None


def promote(kb_dir: str, fid: str) -> dict:
    """Print draft Case YAML and mark promoted. NEVER writes cases/ itself —
    the human reviews, edits, and commits the YAML (§5)."""
    con = _db(kb_dir)
    try:
        f = _get(con, fid)
        if not f:
            return {"error": f"no finding {fid}"}
        case_id = f"case-from-{fid}"
        field = "root_cause" if f["kind"] == "root_cause_hypothesis" else "summary"
        yaml_draft = "\n".join([
            f"id: {case_id}",
            "title: TODO (one line, written by a human)",
            "status: draft",
            f"{field}: >\n  " + f["text"].replace("\n", "\n  "),
            f"affected_symbols: {json.loads(f['symbol_ids'] or '[]')}",
            "confidence: speculation   # stays speculation until a human verifies",
        ])
        with con:
            con.execute("UPDATE findings SET status='promoted', promoted_case_id=? "
                        "WHERE id=?", (case_id, fid))
        return {"id": fid, "status": "promoted", "draft_case_yaml": yaml_draft}
    finally:
        con.close()


def reject(kb_dir: str, fid: str) -> dict:
    con = _db(kb_dir)
    try:
        if not _get(con, fid):
            return {"error": f"no finding {fid}"}
        with con:
            con.execute("UPDATE findings SET status='rejected' WHERE id=?", (fid,))
        return {"id": fid, "status": "rejected"}
    finally:
        con.close()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="kb.memory", description=__doc__)
    sub = ap.add_subparsers(dest="subcmd", required=True)
    ls = sub.add_parser("list"); ls.add_argument("kb_dir")
    ls.add_argument("--status", default="active")
    sh = sub.add_parser("show"); sh.add_argument("kb_dir"); sh.add_argument("id")
    pr = sub.add_parser("promote"); pr.add_argument("kb_dir"); pr.add_argument("id")
    pr.add_argument("--confirm", action="store_true")
    rj = sub.add_parser("reject"); rj.add_argument("kb_dir"); rj.add_argument("id")
    rj.add_argument("--confirm", action="store_true")
    a = ap.parse_args(argv)
    if a.subcmd == "list":
        print(json.dumps(find_findings(a.kb_dir, status=a.status, limit=100), indent=1))
    elif a.subcmd == "show":
        con = _db(a.kb_dir)
        print(json.dumps(_get(con, a.id) or {"error": "not found"}, indent=1))
        con.close()
    elif a.subcmd in ("promote", "reject"):
        if not a.confirm:
            print(json.dumps({"error": f"{a.subcmd} is a curation action — "
                                       "re-run with --confirm"}))
            return 1
        res = (promote if a.subcmd == "promote" else reject)(a.kb_dir, a.id)
        if "draft_case_yaml" in res:
            print(res.pop("draft_case_yaml"))
            print("---")
        print(json.dumps(res))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
