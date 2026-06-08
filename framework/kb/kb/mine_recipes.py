"""
kb.mine_recipes — mine candidate L3 recipes from git history (gap G9, #2).

The L3 recipe layer is the institutional moat, but recipes are expensive to author by hand.
This turns the prior `find_recipe` scaffold into a real *miner*: it clusters past commits by
the area of the tree they touch, distils the recurring intent from their subjects, and emits
**candidate recipes** for a human to review and promote.

Deliberately conservative, per spec §3 (L3 is human-curated):
  - Output is `confidence: "draft"`, `source: "mined"` — never auto-merged into the live
    recipe set. The reviewer CLI (`kb.review`) promotes them up the ladder.
  - Evidence is the list of commits behind each cluster, so a reviewer can trace the claim.
  - Pure `mine(commits)` is unit-tested; the CLI just feeds it `git log`.

CLI:
  python -m kb.mine_recipes <repo_dir> [--limit N] [--min-cluster M] [--out FILE.jsonl]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter

from .retrieve import _tokens   # lowercase, stopword-filtered tokenization


def _theme(files: list[str]) -> str:
    """The two-level path prefix most files share (e.g. 'framework/kb'). The cluster key."""
    pref: Counter[str] = Counter()
    for f in files:
        parts = [p for p in f.split("/") if p]
        if len(parts) >= 2:
            pref["/".join(parts[:2])] += 1
        elif parts:
            pref[parts[0]] += 1
    return pref.most_common(1)[0][0] if pref else ""


def _common_keywords(subjects: list[str], top: int = 6) -> list[str]:
    """Tokens that recur across >=2 of the cluster's commit subjects — the recurring intent."""
    c: Counter[str] = Counter()
    for s in subjects:
        for t in set(_tokens(s)):
            c[t] += 1
    return [w for w, n in c.most_common(top) if n >= 2]


def mine(commits: list[dict], min_cluster: int = 3) -> list[dict]:
    """Cluster commits by touched area into candidate recipe drafts.

    `commits`: [{"sha", "subject", "files": [paths]}]. Returns recipe dicts sorted by
    cluster size (strongest signal first)."""
    buckets: dict[str, list[dict]] = {}
    for c in commits:
        theme = _theme(c.get("files", []))
        if theme:
            buckets.setdefault(theme, []).append(c)

    recipes = []
    for theme, cs in buckets.items():
        if len(cs) < min_cluster:
            continue
        kws = _common_keywords([c.get("subject", "") for c in cs])
        files = sorted({f for c in cs for f in c.get("files", [])})
        recipes.append({
            "id": "mined:" + theme.replace("/", "-"),
            "title": f"How changes to {theme} are usually made",
            "task": (("e.g. " + ", ".join(kws)) if kws else f"changes under {theme}"),
            "when": " ".join(kws) or theme,
            "confidence": "draft",
            "source": "mined",
            "evidence": [c["sha"][:10] for c in cs],
            "hot_files": files[:8],
            "decision_points": [],     # for a human to fill in during review
            "pitfalls": [],
        })
    recipes.sort(key=lambda r: -len(r["evidence"]))
    return recipes


def read_commits(repo: str, limit: int = 500) -> list[dict]:
    """Commit records from `git log` (subject + touched files), newest first."""
    out = subprocess.run(
        ["git", "-C", repo, "log", "--no-merges", f"-n{limit}",
         "--pretty=format:\x1eCOMMIT\x1f%H\x1f%s", "--name-only"],
        capture_output=True, text=True, check=True).stdout
    commits = []
    for rec in out.split("\x1eCOMMIT\x1f"):
        if not rec.strip():
            continue
        head, *rest = rec.split("\n")
        sha, _, subject = head.partition("\x1f")
        files = [ln for ln in rest if ln.strip()]
        commits.append({"sha": sha, "subject": subject, "files": files})
    return commits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kb.mine_recipes")
    ap.add_argument("repo")
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--min-cluster", type=int, default=3)
    ap.add_argument("--out", help="write candidate drafts as JSONL (default: print JSON)")
    a = ap.parse_args(argv)
    recipes = mine(read_commits(a.repo, a.limit), a.min_cluster)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            for r in recipes:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(json.dumps({"mined": len(recipes), "out": a.out}))
    else:
        print(json.dumps(recipes, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
