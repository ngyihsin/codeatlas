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


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="kb.drift")
    sub = ap.add_subparsers(dest="subcmd", required=True)
    sp = sub.add_parser("sample")
    sp.add_argument("kb_dir"); sp.add_argument("code_root")
    sp.add_argument("--n", type=int, default=None)
    sp.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    if a.subcmd == "sample":
        rep = sample_drift(a.kb_dir, a.code_root, n=a.n, seed=a.seed)
        # keep stdout compact; full lists available via the API
        compact = {k: (len(v) if isinstance(v, list) else v) for k, v in rep.items()}
        print(json.dumps(compact))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
