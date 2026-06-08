"""
kb.retrieve — generic natural-language → code retrieval (hybrid, no embeddings).

Answers "which symbols/files are relevant to this query?" using the three signals the
research found beat flat dense retrieval for code (see docs/kb/spec.md §3.4):

  1. lexical    — query tokens vs. symbol names + path components + op names
                  (BM25/grep beats dense for identifiers).
  2. structural — expand top lexical hits along the call graph (callers/callees), so
                  related code surfaces even without a lexical match (LocAgent insight).
  3. importance — PageRank from L1 breaks ties toward load-bearing symbols.

Pure function over the L1 artifacts; no new dependencies. This is the reusable core the
deferred `localize(issue)` would specialize.
"""
from __future__ import annotations

import re

_STOP = {"the", "and", "for", "with", "this", "that", "are", "was", "how", "why",
         "where", "does", "use", "using", "from", "into", "out", "get", "set",
         "fix", "bug", "add", "new", "code", "function", "method", "class"}

_TOKEN = re.compile(r"[A-Za-z0-9]+")
_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+")


def _tokens(text: str) -> list[str]:
    return [t for t in (m.group(0).lower() for m in _TOKEN.finditer(text))
            if len(t) > 2 and t not in _STOP]


def _name_words(name: str) -> set[str]:
    # split CamelCase / snake_case into lowercase words for matching
    return {w.lower() for w in _CAMEL.findall(name) if len(w) > 2}


def relevant_code(query: str, symbols: list[dict], edges: list[dict],
                  ops: list[dict] | None = None,
                  summary_by_id: dict[str, dict] | None = None,
                  k: int = 5, expand: int = 3) -> list[dict]:
    """Return up to `k` ranked candidates: {anchor, symbol_id, kind, why, evidence,
    precision, summary?}. Deterministic; ties broken by importance then id."""
    qtok = set(_tokens(query))
    if not qtok:
        return []
    ops = ops or []
    summary_by_id = summary_by_id or {}

    # normalize importance to [0,1] for tie-breaking
    max_imp = max((s.get("importance", 0.0) for s in symbols), default=0.0) or 1.0

    scored: dict[str, dict] = {}          # symbol_id -> result row

    def consider(s: dict, base: float, why: str):
        sid = s.get("id")
        if not sid:
            return
        row = scored.get(sid)
        score = base + 2.0 * (s.get("importance", 0.0) / max_imp)
        if row is None or score > row["_score"]:
            scored[sid] = {
                "_score": score,
                "anchor": f"{s.get('path')} → {s.get('name')}",
                "symbol_id": sid, "kind": s.get("kind"),
                "why": why,
                "evidence": {"path": s.get("path"), "line": s.get("line")},
                "precision": "exact" if base >= 5 else "lexical",
            }

    # 1. lexical scoring over symbols
    lexical_hits: list[dict] = []
    for s in symbols:
        name = s.get("name", "")
        nl = name.lower()
        words = _name_words(name)
        path_l = s.get("path", "").lower()
        score = 0.0
        reasons = []
        for t in qtok:
            if t == nl:
                score += 5; reasons.append(f"name=={t}")
            elif t in words:
                score += 3; reasons.append(f"name~{t}")
            elif t in nl:
                score += 1.5; reasons.append(f"name has {t}")
            if t in path_l:
                score += 1; reasons.append(f"path has {t}")
        if score > 0:
            consider(s, score, ", ".join(dict.fromkeys(reasons)))
            lexical_hits.append(s)

    # 2. op-registry matches (the spec's #1 table) as first-class candidates
    for o in ops:
        on = (o.get("op_name") or "").lower()
        if any(t == on or t in on for t in qtok):
            sid = f"op:{o.get('op_name')}:{o.get('version')}"
            if sid not in scored or scored[sid]["_score"] < 4:
                scored[sid] = {
                    "_score": 4.0,
                    "anchor": f"{o.get('kernel_path')}:{o.get('line')}",
                    "symbol_id": sid, "kind": "op",
                    "why": f"op registration {o.get('op_name')} v{o.get('version')}",
                    "evidence": {"path": o.get("kernel_path"), "line": o.get("line")},
                    "precision": "exact",
                }

    # 3. structural expansion: pull neighbors of the strongest lexical hits
    if lexical_hits and expand:
        by_id = {s.get("id"): s for s in symbols}
        rev: dict[str, list[str]] = {}
        fwd: dict[str, list[str]] = {}
        for e in edges:
            fwd.setdefault(e["caller_id"], []).append(e["callee_id"])
            rev.setdefault(e["callee_id"], []).append(e["caller_id"])
        top = sorted(lexical_hits, key=lambda s: -scored[s["id"]]["_score"])[:expand]
        for hit in top:
            hid = hit["id"]
            for nid in fwd.get(hid, [])[:5]:
                if nid in by_id:
                    consider(by_id[nid], 0.8, f"called by {hit['name']}")
            for nid in rev.get(hid, [])[:5]:
                if nid in by_id:
                    consider(by_id[nid], 0.8, f"calls {hit['name']}")

    # attach L2 summary preview when available; rank and trim
    rows = sorted(scored.values(), key=lambda r: (-r["_score"], r["symbol_id"]))[:k]
    for r in rows:
        summ = summary_by_id.get(r["symbol_id"])
        if summ:
            r["summary"] = summ.get("preview")
            r["confidence"] = summ.get("confidence", "draft")
        r.pop("_score", None)
    return rows
