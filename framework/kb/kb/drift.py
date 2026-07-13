"""
kb.drift — freshness sampler (FR-8 / Phase 3 M3.3).

The incremental firewall keeps the KB fresh *when a rebuild runs*, but a KB can still
drift if rebuilds are skipped or a heuristic edge was missed. This samples files,
re-hashes them, and compares against the L1 content-hash cache to surface silent
staleness — the backstop the leverage analysis (Glean ownership) calls for.

Reports a freshness rate (an SLO signal): fraction of sampled files whose on-disk
content still matches what the KB was built from. Stale/missing/new-uncached files are
the ones a rebuild must touch.

CLI:
  python -m kb.drift sample <kb_dir> <code_root> [--n N] [--seed S]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys

from . import l1


def _hash(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def sample_drift(kb_dir: str, code_root: str, n: int | None = None,
                 seed: int = 0) -> dict:
    cache_path = os.path.join(kb_dir, "l1_cache.json")
    if not os.path.isfile(cache_path):
        return {"error": "no l1_cache.json — build L1 first"}
    cache = json.load(open(cache_path, encoding="utf-8")).get("file_hashes", {})
    files = list(cache)
    random.Random(seed).shuffle(files)
    if n:
        files = files[:n]

    stale, missing = [], []
    for rel in files:
        full = os.path.join(code_root, rel)
        if not os.path.isfile(full):
            missing.append(rel)
        elif _hash(full) != cache[rel]:
            stale.append(rel)

    disk = {os.path.relpath(f, code_root) for f in l1._iter_code_files(code_root)}
    new_uncached = sorted(disk - set(cache))

    sampled = len(files)
    fresh = sampled - len(stale) - len(missing)
    return {
        "sampled": sampled,
        "stale": sorted(stale),
        "missing": sorted(missing),
        "new_uncached": len(new_uncached),
        "fresh_rate": (fresh / sampled) if sampled else None,
    }


def symbol_drift(kb_dir: str, code_root: str) -> list[dict]:
    """Spec verify #1 at symbol granularity: recompute each symbol's span text at
    its recorded location and compare to the stored span_hash. Cheap (no ctags
    re-run): a shifted/edited body changes the span text and shows up here."""
    import hashlib
    sym_path = os.path.join(kb_dir, "symbols.jsonl")
    if not os.path.isfile(sym_path):
        return []
    symbols = [json.loads(l) for l in open(sym_path, encoding="utf-8") if l.strip()]
    by_path: dict[str, list[dict]] = {}
    for s in symbols:
        if s.get("span_hash"):
            by_path.setdefault(s["path"], []).append(s)
    drifted = []
    for path, syms in by_path.items():
        full = os.path.join(code_root, path)
        if not os.path.isfile(full):
            drifted += [{"id": s["id"], "reason": "file_missing"} for s in syms]
            continue
        lines = open(full, encoding="utf-8", errors="replace").read().splitlines()
        ordered = sorted(syms, key=lambda s: s["line"])
        for i, s in enumerate(ordered):
            end = ordered[i + 1]["line"] - 1 if i + 1 < len(ordered) else len(lines)
            span = "\n".join(lines[max(s["line"] - 1, 0):max(end, s["line"])])
            if hashlib.sha256(span.encode()).hexdigest()[:12] != s["span_hash"]:
                drifted.append({"id": s["id"], "reason": "span_changed"})
    return drifted


def link_integrity(kb_dir: str) -> list[dict]:
    """Spec verify #2: every affected_symbols entry in L3 YAML (recipes today;
    cases/features when present) must resolve against symbols.jsonl. Dangling
    links are flagged, never silently dropped."""
    sym_path = os.path.join(kb_dir, "symbols.jsonl")
    known: set[str] = set()
    if os.path.isfile(sym_path):
        for l in open(sym_path, encoding="utf-8"):
            if l.strip():
                s = json.loads(l)
                known |= {s.get("id", ""), s.get("name", ""),
                          s.get("name", "").split("::")[-1]}
    dangling = []
    try:
        import yaml
    except ImportError:
        return []
    for sub in ("recipes", "cases", "features"):
        d = os.path.join(kb_dir, sub)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith((".yaml", ".yml")):
                continue
            doc = yaml.safe_load(open(os.path.join(d, fn), encoding="utf-8")) or {}
            for ref in doc.get("affected_symbols", []) or []:
                if ref not in known:
                    dangling.append({"record": f"{sub}/{fn}", "symbol": ref})
    return dangling


def verify(kb_dir: str, code_root: str) -> dict:
    """Consolidated verify (unified spec §3): file freshness + symbol span drift
    + L3 link integrity. Finding staleness joins here with the memory layer."""
    report = {
        "files": sample_drift(kb_dir, code_root),
        "drifted_symbols": symbol_drift(kb_dir, code_root),
        "dangling_links": link_integrity(kb_dir),
    }
    try:                                    # memory layer optional (Task B)
        from . import memory
        report["stale_findings"] = memory.mark_stale(kb_dir)
    except ImportError:
        pass
    return report


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="kb.drift")
    sub = ap.add_subparsers(dest="subcmd", required=True)
    sp = sub.add_parser("sample")
    sp.add_argument("kb_dir"); sp.add_argument("code_root")
    sp.add_argument("--n", type=int, default=None)
    sp.add_argument("--seed", type=int, default=0)
    vf = sub.add_parser("verify")
    vf.add_argument("kb_dir"); vf.add_argument("code_root")
    a = ap.parse_args(argv)
    if a.subcmd == "sample":
        rep = sample_drift(a.kb_dir, a.code_root, n=a.n, seed=a.seed)
        # keep stdout compact; full lists available via the API
        compact = {k: (len(v) if isinstance(v, list) else v) for k, v in rep.items()}
        print(json.dumps(compact))
        return 0
    if a.subcmd == "verify":
        print(json.dumps(verify(a.kb_dir, a.code_root)))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
