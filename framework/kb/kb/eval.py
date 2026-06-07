"""
kb.eval — the faithfulness / grounding harness (gap G7).

The lint (kb.lint) proves a citation *exists*; this proves it is *accurate* — that the
cited `[Lxx]` lines actually SUPPORT the claim. Per docs/kb/leverage.md §G7 this is a
dependency-light PATTERN reimplementation of claim-decompose + per-claim NLI-entailment
(the algorithm shared by RAGAS/DeepEval) running on our `claude` subprocess backend —
no RAGAS/torch/OpenAI. Because the Claude backend exposes no logprobs, confidence comes
from self-consistency (K samples) rather than token probabilities.

What it reports (no BLEU/ROUGE — empirically uncorrelated with code-summary quality):
  - lint_clean_rate   : fraction passing the existence/format gate
  - entailment_rate   : fraction of checkable claims SUPPORTED by their cited lines
  - coverage          : fraction of top-importance symbols that have an L2 summary

CLI:
  python -m kb.eval run <summaries.jsonl> --code ROOT [--backend claude|mock] [--samples K]
  python -m kb.eval coverage <summaries.jsonl> --symbols symbols.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

from .l2 import Backend, ClaudeCodeBackend, MockBackend, parse_summary
from .lint import LINEREF, lint_summary

_SENT = re.compile(r"[^.!?]+[.!?]?")   # sentences incl. an unterminated trailing one

_ENTAIL_SYSTEM = (
    "You verify whether a claim about source code is supported by specific cited lines. "
    "Use ONLY the provided lines as evidence. Output ONLY a JSON object."
)


def split_claims(full: str) -> list[tuple[str, list[tuple[int, int]]]]:
    """Sentences of `full` that carry ≥1 [Lxx] citation, with their line ranges.
    Deterministic — no LLM needed to decompose."""
    out = []
    for m in _SENT.finditer(full or ""):
        sent = m.group(0).strip()
        refs = [(int(a), int(b) if b else int(a)) for a, b in LINEREF.findall(sent)]
        if refs:
            out.append((sent, refs))
    return out


def _cited_source(code_root: str, rel_path: str,
                  ranges: list[tuple[int, int]]) -> str:
    p = os.path.join(code_root, rel_path)
    try:
        lines = open(p, encoding="utf-8", errors="ignore").read().splitlines()
    except OSError:
        return ""
    return cited_from_text("\n".join(lines), ranges)


def cited_from_text(source_text: str, ranges: list[tuple[int, int]]) -> str:
    """The cited lines (numbered) from in-memory source — used by the L2 entailment gate."""
    lines = source_text.splitlines()
    chunks = []
    for lo, hi in ranges:
        for n in range(lo, min(hi, len(lines)) + 1):
            if 1 <= n <= len(lines):
                chunks.append(f"{n:>4}| {lines[n - 1]}")
    return "\n".join(chunks)


def unsupported_claims(full: str, source_text: str, backend: Backend,
                       samples: int = 1) -> list[str]:
    """Claims in `full` whose cited lines do NOT entail them (the L2 gate's input)."""
    bad = []
    for sent, ranges in split_claims(full):
        cited = cited_from_text(source_text, ranges)
        if not cited:
            continue
        if entail_claim(backend, sent, cited, samples)["verdict"] != "entailed":
            bad.append(sent)
    return bad


def _entail_once(backend: Backend, claim: str, cited: str) -> str:
    prompt = (
        "Is the CLAIM supported by the CITED SOURCE lines?\n\n"
        f"CLAIM: {claim}\n\nCITED SOURCE:\n{cited}\n\n"
        'Answer ONLY: {"verdict":"entailed|neutral|contradicted","confidence":0-1,'
        '"rationale":"<short>"}'
    )
    raw = backend.generate(prompt, system=_ENTAIL_SYSTEM)
    try:
        return str(parse_summary(raw).get("verdict", "neutral")).lower()
    except Exception:
        return "neutral"


def entail_claim(backend: Backend, claim: str, cited: str, samples: int = 1) -> dict:
    """Verdict for one claim, with self-consistency confidence over `samples` runs."""
    votes = [_entail_once(backend, claim, cited) for _ in range(max(1, samples))]
    verdict = max(set(votes), key=votes.count)
    return {"verdict": verdict, "confidence": votes.count(verdict) / len(votes),
            "claim": claim}


def evaluate_summary(summary: dict, code_root: str, backend: Backend,
                     samples: int = 1) -> dict:
    """Entailment over one summary's cited claims. Modules (no citations) are n/a."""
    claims = split_claims(str(summary.get("full", "")))
    rel = summary.get("path")
    results = []
    for sent, ranges in claims:
        cited = _cited_source(code_root, rel, ranges) if rel else ""
        if not cited:
            results.append({"verdict": "no-source", "claim": sent, "confidence": 0.0})
            continue
        results.append(entail_claim(backend, sent, cited, samples))
    checkable = [r for r in results if r["verdict"] in ("entailed", "neutral",
                                                        "contradicted")]
    entailed = [r for r in checkable if r["verdict"] == "entailed"]
    return {
        "id": summary.get("id"),
        "claims": len(results),
        "checkable": len(checkable),
        "entailed": len(entailed),
        "faithfulness": (len(entailed) / len(checkable)) if checkable else None,
        "results": results,
    }


def coverage(summaries: list[dict], symbols: list[dict], quantile: float = 0.75) -> dict:
    """Fraction of top-importance symbols that have a symbol-scoped L2 summary."""
    code = [s for s in symbols if s.get("kind") in ("function", "method", "class", "struct")]
    if not code:
        return {"covered": 0, "total": 0, "coverage": None}
    imps = sorted((s.get("importance", 0.0) for s in code))
    cutoff = imps[int(quantile * (len(imps) - 1))]
    top = [s for s in code if s.get("importance", 0.0) >= cutoff]
    have = {s.get("id") for s in summaries if s.get("scope") == "symbol"}
    covered = sum(1 for s in top if s.get("id") in have)
    return {"covered": covered, "total": len(top),
            "coverage": covered / len(top) if top else None}


def run(summaries_path: str, code_root: str, backend: Backend,
        samples: int = 1, symbols_path: str | None = None) -> dict:
    summaries = [json.loads(l) for l in open(summaries_path, encoding="utf-8") if l.strip()]
    lint_clean = sum(1 for s in summaries if not lint_summary(s))
    per = [evaluate_summary(s, code_root, backend, samples) for s in summaries]
    checkable = sum(p["checkable"] for p in per)
    entailed = sum(p["entailed"] for p in per)
    report = {
        "summaries": len(summaries),
        "lint_clean": lint_clean,
        "lint_clean_rate": lint_clean / len(summaries) if summaries else None,
        "claims_checkable": checkable,
        "entailed": entailed,
        "entailment_rate": (entailed / checkable) if checkable else None,
        "per_summary": per,
    }
    if symbols_path and os.path.isfile(symbols_path):
        syms = [json.loads(l) for l in open(symbols_path, encoding="utf-8") if l.strip()]
        report["coverage"] = coverage(summaries, syms)
    return report


def _make_backend(name: str, timeout: int) -> Backend:
    if name == "claude":
        return ClaudeCodeBackend(timeout=timeout)
    if name == "mock":           # deterministic stub: everything entailed (CI only)
        return MockBackend(lambda p, a: '{"verdict":"entailed","confidence":1.0,"rationale":"ok"}')
    raise SystemExit(f"unknown backend: {name}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="kb.eval")
    sub = ap.add_subparsers(dest="subcmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("summaries"); r.add_argument("--code", required=True)
    r.add_argument("--symbols", default=None)
    r.add_argument("--backend", default="claude", choices=["claude", "mock"])
    r.add_argument("--samples", type=int, default=1)
    r.add_argument("--timeout", type=int, default=120)
    c = sub.add_parser("coverage")
    c.add_argument("summaries"); c.add_argument("--symbols", required=True)
    a = ap.parse_args(argv)
    if a.subcmd == "run":
        rep = run(a.summaries, a.code, _make_backend(a.backend, a.timeout),
                  samples=a.samples, symbols_path=a.symbols)
        rep.pop("per_summary", None)  # keep stdout compact; full detail via API
        print(json.dumps(rep)); return 0
    if a.subcmd == "coverage":
        sums = [json.loads(l) for l in open(a.summaries, encoding="utf-8") if l.strip()]
        syms = [json.loads(l) for l in open(a.symbols, encoding="utf-8") if l.strip()]
        print(json.dumps(coverage(sums, syms))); return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
