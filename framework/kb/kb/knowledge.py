"""
kb.knowledge — the L3 institutional layer: Cases and Features (unified spec §2.1).

Cases are curated incident/fix history ("how was Y fixed, what did we learn");
Features are curated capability records ("what does subsystem X provide"). Both are
YAML records under <kb_dir>/cases/ and <kb_dir>/features/ (same dir-of-YAML
convention as recipes/), human- or pipeline-curated, mirrored into retrieval
indexes here. YAML stays the source of truth; indexes are derived and rebuilt.

Retrieval is the spec's two-leg hybrid:
  - lexical leg: exact id / ticket-key match short-circuits to the top (a lookup
    like "QNN-1234" must behave like a lookup, not a similarity search), then
    token overlap;
  - vector leg: cosine over the spec's embedding composition —
      case:    title + root_cause + fix_summary + lessons
      feature: title + summary_full (fallback preview/fold)
    using the same pluggable embedder as recipes (MiniLM via $KB_MINILM_DIR,
    HashEmbedder fallback: offline, deterministic, CI-hermetic).

Confidence discipline (spec §1.3 + Appendix R.2): records default to
confidence: speculation; only humans set verified (via YAML edit + review).
"""
from __future__ import annotations

import os

from .recipes import Embedder, cosine, get_embedder


def _load_yaml_dir(kb_dir: str, sub: str) -> list[dict]:
    try:
        import yaml
    except ImportError:
        return []
    d = os.path.join(kb_dir, sub)
    if not os.path.isdir(d):
        return []
    out = []
    for fn in sorted(os.listdir(d)):
        if not fn.endswith((".yaml", ".yml")):
            continue
        doc = yaml.safe_load(open(os.path.join(d, fn), encoding="utf-8")) or {}
        if isinstance(doc, dict) and doc.get("id"):
            doc.setdefault("confidence", "speculation")
            out.append(doc)
    return out


def load_cases(kb_dir: str) -> list[dict]:
    return _load_yaml_dir(kb_dir, "cases")


def load_features(kb_dir: str) -> list[dict]:
    return _load_yaml_dir(kb_dir, "features")


def case_text(c: dict) -> str:
    lessons = c.get("lessons", []) or []
    return " ".join([str(c.get("title", "")), str(c.get("root_cause", "")),
                     str(c.get("fix_summary", ""))] + [str(l) for l in lessons])


def feature_text(f: dict) -> str:
    summary = f.get("summary_full") or f.get("summary_preview") or f.get("summary_fold", "")
    return f"{f.get('title', '')} {summary}"


def _row(kind: str, r: dict, score: float) -> dict:
    row = {"kind": kind, "id": r.get("id"), "title": r.get("title", ""),
           "status": r.get("status", ""), "confidence": r.get("confidence", "speculation"),
           "score": round(score, 4)}
    if r.get("url"):
        row["url"] = r["url"]
    if r.get("affected_symbols"):
        row["affected_symbols"] = r["affected_symbols"]
    return row


class KnowledgeIndex:
    """Hybrid index over one record kind ('case' | 'feature'). Small N ->
    brute-force cosine; sqlite-vec/FTS5 is the drop-in when the layer grows."""

    def __init__(self, records: list[dict], kind: str,
                 embedder: Embedder | None = None):
        self.records, self.kind = records, kind
        self.embedder = embedder or get_embedder()
        text = case_text if kind == "case" else feature_text
        self.vectors = [self.embedder.embed(text(r)) for r in records]

    def search(self, query: str, k: int = 3) -> list[dict]:
        if not self.records:
            return []
        q = query.strip()
        # Lexical leg 1: exact id / ticket-key lookup behaves like a lookup.
        exact = [r for r in self.records
                 if q.lower() in (str(r.get("id", "")).lower(),
                                  str(r.get("ticket", "")).lower())]
        if exact:
            return [_row(self.kind, r, 1.0) for r in exact[:k]]
        # Vector leg (the lexical token-overlap leg lives inside HashEmbedder's
        # cosine when no real model is configured — same signal, one code path).
        qv = self.embedder.embed(q)
        scored = sorted(((cosine(qv, v), r) for v, r in zip(self.vectors, self.records)),
                        key=lambda t: -t[0])
        return [_row(self.kind, r, s) for s, r in scored[:k] if s > 0]
