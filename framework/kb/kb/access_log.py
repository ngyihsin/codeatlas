"""
kb.access_log — the cheap eval substrate (unified spec §6.3).

Every tools/call appends one JSON line to <kb_dir>/access_log.jsonl: which tool,
which argument keys (never values — queries can contain sensitive text), how many
rows came back. The report answers the questions the spec says to review weekly:
tool-selection distribution, empty-result rate per tool, total call volume.

Opt out with KB_ACCESS_LOG=0 (it is on by default: an eval layer that has to be
remembered is an eval layer that ends up empty).

  python -m kb.access_log report <kb_dir>
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys


def enabled() -> bool:
    return os.environ.get("KB_ACCESS_LOG", "1") != "0"


def log(kb_dir: str, tool: str, args: dict, n_results: int) -> None:
    if not enabled():
        return
    row = {"ts": datetime.datetime.now(datetime.timezone.utc)
           .strftime("%Y-%m-%dT%H:%M:%SZ"),
           "tool": tool, "arg_keys": sorted(args), "n": n_results,
           "empty": n_results == 0}
    try:
        with open(os.path.join(kb_dir, "access_log.jsonl"), "a",
                  encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except OSError:
        pass                    # logging must never break a tool call


def report(kb_dir: str) -> dict:
    path = os.path.join(kb_dir, "access_log.jsonl")
    if not os.path.isfile(path):
        return {"calls": 0}
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    by_tool: dict[str, dict] = {}
    for r in rows:
        t = by_tool.setdefault(r["tool"], {"calls": 0, "empty": 0})
        t["calls"] += 1
        t["empty"] += 1 if r.get("empty") else 0
    for t in by_tool.values():
        t["empty_rate"] = round(t["empty"] / t["calls"], 3)
    return {"calls": len(rows),
            "empty_rate": round(sum(1 for r in rows if r.get("empty")) / len(rows), 3),
            "by_tool": dict(sorted(by_tool.items(), key=lambda kv: -kv[1]["calls"]))}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="kb.access_log")
    sub = ap.add_subparsers(dest="subcmd", required=True)
    rp = sub.add_parser("report"); rp.add_argument("kb_dir")
    a = ap.parse_args(argv)
    print(json.dumps(report(a.kb_dir), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
