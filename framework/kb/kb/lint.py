"""L2 lint — make a summary impossible to bluff, before a human ever reads it.

The spec's L2 failure mode is a summary that *reads* confident but is wrong. This linter
runs before human review and rejects summaries that can't be true, so reviewers only ever
see machine-plausible ones:

  - required fields present; `fold` <= 20 chars; `evidence_level` in {code,inferred,speculation}
  - every cited line ref `[L42]` / `[L42-58]` must exist in the symbol's source
  - if `evidence_level: code` then at least one line ref must appear  (code claim w/o evidence)
  - symbols named in backticks inside `full` should exist in the L1 symbol table (if given)

CLI:
  python -m kb.lint <summaries.(yaml|jsonl)> [--symbols symbols.jsonl] [--code ROOT]
  exit 0 = all clean; exit 1 = at least one summary failed.
"""
from __future__ import annotations

import json
import os
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

REQUIRED = ["fold", "preview", "full", "evidence_level"]
EVIDENCE = {"code", "inferred", "speculation"}
LINEREF = re.compile(r"\[L(\d+)(?:-(\d+))?\]")
BACKTICK = re.compile(r"`([A-Za-z_]\w+)`")


def lint_summary(s: dict, source_lines: int | None = None,
                 symbol_names: set[str] | None = None) -> list[str]:
    """Return a list of error strings for one summary ({} ok)."""
    errs: list[str] = []
    sid = s.get("id") or s.get("symbol") or s.get("fold") or "<unknown>"

    for field in REQUIRED:
        if not s.get(field):
            errs.append(f"{sid}: missing required field '{field}'")

    fold = s.get("fold", "")
    if isinstance(fold, str) and len(fold) > 20:
        errs.append(f"{sid}: fold is {len(fold)} chars (max 20): {fold!r}")

    ev = s.get("evidence_level")
    if ev and ev not in EVIDENCE:
        errs.append(f"{sid}: evidence_level '{ev}' not in {sorted(EVIDENCE)}")

    # collect text that may carry claims + line refs
    text_fields = [s.get("full", ""), s.get("preview", "")]
    for k in ("invariants", "known_pitfalls"):
        v = s.get(k) or []
        if isinstance(v, list):
            text_fields.extend(str(x) for x in v)
    blob = "\n".join(text_fields)

    refs = LINEREF.findall(blob)
    if ev == "code" and not refs:
        errs.append(f"{sid}: evidence_level 'code' but no [Lxx] line reference (unverifiable)")
    if source_lines is not None:
        for a, b in refs:
            lo = int(a); hi = int(b) if b else lo
            if lo < 1 or hi > source_lines or lo > hi:
                errs.append(f"{sid}: line ref [L{a}{'-'+b if b else ''}] outside source (1..{source_lines})")

    if symbol_names is not None:
        for name in set(BACKTICK.findall(str(s.get("full", "")))):
            # only flag identifier-looking tokens that claim to be code symbols
            if name not in symbol_names and "_" not in name and not name[0].islower():
                continue  # likely prose/Type word; don't over-flag
            if name not in symbol_names:
                errs.append(f"{sid}: `{name}` in full not found in symbol table")
    return errs


def _load_records(path: str) -> list[dict]:
    text = open(path, encoding="utf-8").read()
    if path.endswith(".jsonl"):
        return [json.loads(l) for l in text.splitlines() if l.strip()]
    if yaml is None:
        raise RuntimeError("PyYAML required for .yaml summaries")
    data = yaml.safe_load(text)
    if isinstance(data, dict):
        # allow a top-level mapping of id -> summary, or a single summary
        return list(data.values()) if all(isinstance(v, dict) for v in data.values()) else [data]
    return list(data or [])


def _source_line_count(code_root: str | None, rel_path: str | None) -> int | None:
    if not code_root or not rel_path:
        return None
    p = os.path.join(code_root, rel_path)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8", errors="ignore") as f:
        return sum(1 for _ in f)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__); return 2
    path = argv[0]
    code = argv[argv.index("--code") + 1] if "--code" in argv else None
    sym_names = None
    if "--symbols" in argv:
        sp = argv[argv.index("--symbols") + 1]
        sym_names = {json.loads(l).get("name")
                     for l in open(sp, encoding="utf-8") if l.strip()}

    records = _load_records(path)
    total_err = 0
    for s in records:
        lines = _source_line_count(code, s.get("path"))
        errs = lint_summary(s, lines, sym_names)
        for e in errs:
            print("FAIL " + e)
        total_err += len(errs)
    if total_err:
        print(f"\nlint: {total_err} problem(s) in {len(records)} summary(ies)")
        return 1
    print(f"lint: {len(records)} summary(ies) clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
