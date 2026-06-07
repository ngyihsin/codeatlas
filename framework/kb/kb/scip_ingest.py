"""
kb.scip_ingest — precise C/C++ call-graph tier from SCIP (gap G4).

Per docs/kb/leverage.md §G4: where a `compile_commands.json` exists, run the prebuilt
**scip-clang** binary (Clang frontend — resolves macros + types) to produce `index.scip`,
then ingest `scip print --json index.scip` with the **stdlib json** module (there is no
maintained Python SCIP library, so we avoid the protobuf runtime). Edges from this tier
are tagged `xref:precise`; files outside the compile DB keep the l1 heuristic
(`xref:partial`). Indirect/virtual edges remain candidate sets (static C/C++ call graphs
over-approximate them).

The SCIP→edges rule (Sourcegraph SCIP schema): a *reference* occurrence (Definition role
bit unset) whose containing function is the definition whose `enclosingRange` contains it
→ that function is the caller, the occurrence's symbol is the callee.

CLI:
  python -m kb.scip_ingest from-json <index.json> <out_dir>     # ingest a print --json
  python -m kb.scip_ingest build <code_root> <compile_commands.json> <out_dir>
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

_DEFINITION = 0x1   # SymbolRole.Definition bit


def _span(rng: list[int] | None) -> tuple[int, int] | None:
    """SCIP range -> (start_line, end_line), 0-based. [sl,sc,el,ec] or [sl,sc,ec]."""
    if not rng:
        return None
    sl = rng[0]
    el = rng[2] if len(rng) >= 4 else rng[0]
    return sl, el


def parse_index(index: dict) -> tuple[list[dict], list[dict]]:
    """Convert a `scip print --json` Index dict into (symbols, precise edges)."""
    symbols: list[dict] = []
    # per file: list of (callee_symbol, def_start, def_end) for function-like defs
    defs_by_path: dict[str, list[tuple[str, int, int]]] = {}
    refs: list[tuple[str, str, int]] = []   # (path, callee_symbol, ref_line)

    for doc in index.get("documents", []):
        path = doc.get("relativePath") or doc.get("relative_path") or ""
        for si in doc.get("symbols", []):
            sym = si.get("symbol")
            if sym:
                symbols.append({
                    "id": sym, "name": si.get("displayName") or si.get("display_name") or sym,
                    "kind": si.get("kind", ""), "path": path,
                    "signature": (si.get("signatureDocumentation", {}) or {}).get("text", ""),
                })
        for occ in doc.get("occurrences", []):
            roles = occ.get("symbolRoles") or occ.get("symbol_roles") or 0
            sym = occ.get("symbol", "")
            span = _span(occ.get("range"))
            if span is None or not sym or sym.startswith("local "):
                continue
            if roles & _DEFINITION:
                enc = _span(occ.get("enclosingRange") or occ.get("enclosing_range")) or span
                defs_by_path.setdefault(path, []).append((sym, enc[0], enc[1]))
            else:
                refs.append((path, sym, span[0]))

    edges, seen = [], set()
    for path, callee, line in refs:
        for caller, lo, hi in defs_by_path.get(path, ()):
            if lo <= line <= hi and caller != callee:
                key = (caller, callee)
                if key not in seen:
                    seen.add(key)
                    edges.append({"caller_id": caller, "callee_id": callee,
                                  "method": "scip-clang", "xref": "precise"})
                break
    edges.sort(key=lambda e: (e["caller_id"], e["callee_id"]))
    return symbols, edges


def ingest_json(scip_json_path: str) -> tuple[list[dict], list[dict]]:
    return parse_index(json.load(open(scip_json_path, encoding="utf-8")))


def _write(out_dir: str, symbols: list[dict], edges: list[dict]) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "edges.precise.jsonl"), "w", encoding="utf-8") as f:
        for e in edges:
            f.write(json.dumps(e, sort_keys=True) + "\n")
    with open(os.path.join(out_dir, "symbols.scip.jsonl"), "w", encoding="utf-8") as f:
        for s in symbols:
            f.write(json.dumps(s, ensure_ascii=False, sort_keys=True) + "\n")
    return {"symbols": len(symbols), "precise_edges": len(edges), "out": out_dir}


def build(code_root: str, compdb: str, out_dir: str) -> dict:
    """Run scip-clang + scip, then ingest. Requires both binaries on PATH."""
    if not shutil.which("scip-clang"):
        raise SystemExit("scip-clang not on PATH — install the prebuilt binary "
                         "(x86_64 Linux) or use `from-json` with a precomputed index")
    if not shutil.which("scip"):
        raise SystemExit("scip CLI not on PATH (needed for `scip print --json`)")
    scip_path = os.path.join(out_dir, "index.scip")
    os.makedirs(out_dir, exist_ok=True)
    subprocess.run(["scip-clang", f"--compdb-path={compdb}"], cwd=code_root, check=True)
    # scip-clang writes index.scip in cwd; move it under out_dir
    produced = os.path.join(code_root, "index.scip")
    if os.path.exists(produced):
        shutil.move(produced, scip_path)
    jtxt = subprocess.run(["scip", "print", "--json", scip_path],
                          capture_output=True, text=True, check=True).stdout
    symbols, edges = parse_index(json.loads(jtxt))
    return _write(out_dir, symbols, edges)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="kb.scip_ingest")
    sub = ap.add_subparsers(dest="subcmd", required=True)
    fj = sub.add_parser("from-json"); fj.add_argument("index_json"); fj.add_argument("out_dir")
    bd = sub.add_parser("build"); bd.add_argument("code_root"); bd.add_argument("compdb")
    bd.add_argument("out_dir")
    a = ap.parse_args(argv)
    if a.subcmd == "from-json":
        symbols, edges = ingest_json(a.index_json)
        print(json.dumps(_write(a.out_dir, symbols, edges))); return 0
    if a.subcmd == "build":
        print(json.dumps(build(a.code_root, a.compdb, a.out_dir))); return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
