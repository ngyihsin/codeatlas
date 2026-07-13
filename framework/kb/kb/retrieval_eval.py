"""
kb.retrieval_eval — ground-truth retrieval evaluation (unified spec §6.1).

kb.eval judges whether L2 *summaries* are faithful; this judges whether the KB
*retrieves* the right thing. A question set YAML defines per-codebase ground
truth across the spec's three classes:

  structural   "who calls X" — must hit a symbol            (via search_semantic)
  historical   "how was Y fixed" — must hit a case
  conceptual   paraphrase queries that must hit cases/features semantically

Schema (evalset.yaml):
  questions:
    - id: q1
      class: structural | historical | conceptual
      query: "free text, deliberately NOT copied from the stored records"
      expect: "substring matched against each hit's id/anchor/title"
      k: 5              # optional, default 5

Recall@k is tracked per class because they fail differently: structural misses
mean the lexical/graph leg is weak; conceptual misses mean the embedder is.

  python -m kb.retrieval_eval run <kb_dir> <evalset.yaml> [--k 5]
"""
from __future__ import annotations

import argparse
import json
import sys

CLASSES = ("structural", "historical", "conceptual")


def _hit(row: dict, expect: str) -> bool:
    hay = " ".join(str(row.get(f, "")) for f in ("id", "anchor", "title", "name"))
    return expect.lower() in hay.lower()


def run_evalset(kb, questions: list[dict], default_k: int = 5) -> dict:
    per_class = {c: {"n": 0, "hits": 0, "misses": []} for c in CLASSES}
    for q in questions:
        cls = q.get("class", "conceptual")
        if cls not in per_class:
            cls = "conceptual"
        k = int(q.get("k", default_k))
        rows = kb.search_semantic(q["query"], k=k)
        ok = any(_hit(r, q["expect"]) for r in rows)
        per_class[cls]["n"] += 1
        if ok:
            per_class[cls]["hits"] += 1
        else:
            per_class[cls]["misses"].append(q.get("id", q["query"][:40]))
    for c in per_class.values():
        c["recall_at_k"] = round(c["hits"] / c["n"], 3) if c["n"] else None
    total = sum(c["n"] for c in per_class.values())
    hits = sum(c["hits"] for c in per_class.values())
    return {"questions": total, "hits": hits,
            "recall_at_k": round(hits / total, 3) if total else None,
            "per_class": per_class}


def main(argv: list[str]) -> int:
    import yaml
    from .mcp_server import KB
    ap = argparse.ArgumentParser(prog="kb.retrieval_eval")
    sub = ap.add_subparsers(dest="subcmd", required=True)
    rn = sub.add_parser("run")
    rn.add_argument("kb_dir"); rn.add_argument("evalset")
    rn.add_argument("--k", type=int, default=5)
    a = ap.parse_args(argv)
    doc = yaml.safe_load(open(a.evalset, encoding="utf-8")) or {}
    rep = run_evalset(KB(a.kb_dir), doc.get("questions", []), default_k=a.k)
    print(json.dumps(rep, indent=1))
    return 0 if (rep["recall_at_k"] or 0) == 1.0 else 1   # CI-gateable


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
