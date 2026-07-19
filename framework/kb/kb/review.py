"""
kb.review — the human-review workflow (gap G8).

L2 summaries land as `confidence: draft`; an L2 is never auto-trusted. This is the
operational ladder that lets a module owner promote them:

    draft  --(module owner reviews evidence)-->  reviewed  --(shipped ticket)-->  battle-tested

The lint + eval harness guarantee a summary is *grounded* (citations exist and are
plausibly supported); a human still confirms *accuracy* before promotion. `battle-tested`
requires a linked ticket — confidence you only earn by shipping with it.

CLI:
  python -m kb.review list    <kb_dir> [--module PATH] [--status draft]
  python -m kb.review show    <kb_dir> <id>
  python -m kb.review promote <kb_dir> <id> --to reviewed|battle-tested
                                            --owner NAME [--ticket ID]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

from .lint import LINEREF

LADDER = ("draft", "reviewed", "battle-tested")


def _load(kb_dir: str) -> list[dict]:
    p = os.path.join(kb_dir, "summaries.jsonl")
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def _save(kb_dir: str, summaries: list[dict]) -> None:
    p = os.path.join(kb_dir, "summaries.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        for s in summaries:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")


def promote(summaries: list[dict], sid: str, to: str, owner: str,
            ticket: str | None = None, today: str | None = None) -> dict:
    """Promote one summary on the ladder. Pure (returns the updated record) so it is
    unit-testable; the CLI persists. Raises ValueError on bad input."""
    if to not in LADDER:
        raise ValueError(f"--to must be one of {LADDER}")
    if to == "battle-tested" and not ticket:
        raise ValueError("battle-tested requires a linked --ticket (a shipped change)")
    if not owner:
        raise ValueError("promotion requires --owner")
    for s in summaries:
        if s.get("id") == sid:
            cur = s.get("confidence", "draft")
            if cur not in LADDER or LADDER.index(to) != LADDER.index(cur) + 1:
                raise ValueError(
                    f"promotion must climb one rung at a time along {LADDER}; "
                    f"{cur!r} -> {to!r} is not allowed")
            s["confidence"] = to
            s["owner"] = owner
            s["reviewed_at"] = today or datetime.date.today().isoformat()
            if ticket:
                s["ticket"] = ticket
            return s
    raise KeyError(f"no summary with id {sid!r}")


def evidence_anchors(summary: dict) -> list[str]:
    """The cited source spans a reviewer should check before promoting."""
    refs = LINEREF.findall(str(summary.get("full", "")))
    path = summary.get("path", "?")
    return [f"{path}:L{a}" + (f"-{b}" if b else "") for a, b in refs]


def list_drafts(summaries: list[dict], module: str | None = None,
                status: str = "draft") -> list[dict]:
    out = []
    for s in summaries:
        if status and s.get("confidence", "draft") != status:
            continue
        if module and not str(s.get("path", "")).startswith(module):
            continue
        out.append({"id": s.get("id"), "fold": s.get("fold"),
                    "scope": s.get("scope", "file"),
                    "evidence": evidence_anchors(s)})
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="kb.review")
    sub = ap.add_subparsers(dest="subcmd", required=True)
    ls = sub.add_parser("list"); ls.add_argument("kb_dir")
    ls.add_argument("--module", default=None); ls.add_argument("--status", default="draft")
    sh = sub.add_parser("show"); sh.add_argument("kb_dir"); sh.add_argument("id")
    pr = sub.add_parser("promote"); pr.add_argument("kb_dir"); pr.add_argument("id")
    pr.add_argument("--to", required=True); pr.add_argument("--owner", required=True)
    pr.add_argument("--ticket", default=None)
    a = ap.parse_args(argv)

    summaries = _load(a.kb_dir)
    if a.subcmd == "list":
        for row in list_drafts(summaries, a.module, a.status):
            print(json.dumps(row, ensure_ascii=False))
        return 0
    if a.subcmd == "show":
        for s in summaries:
            if s.get("id") == a.id:
                print(json.dumps(s, ensure_ascii=False, indent=2)); return 0
        print(f"no summary with id {a.id!r}", file=sys.stderr); return 1
    if a.subcmd == "promote":
        try:
            rec = promote(summaries, a.id, a.to, a.owner, a.ticket)
        except (ValueError, KeyError) as e:
            print(f"error: {e}", file=sys.stderr); return 1
        _save(a.kb_dir, summaries)
        print(json.dumps({"promoted": rec["id"], "confidence": rec["confidence"],
                          "owner": rec["owner"], "reviewed_at": rec["reviewed_at"]}))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
