"""
kb.buildsys — the build system as KB knowledge (targets, deps, options), for C/C++.

kb.compdb answers "what flags compile this file?"; this module answers "what IS the
build?" — which targets exist, which sources belong to which target, what links
against what, which build options and packages the tree declares. That is exactly
the map an agent needs before touching a build ("where do I add my new kernel's
.cc?", "what does this library pull in?").

We do NOT reimplement the CMake language (it is Turing-complete; the only correct
interpreter is CMake itself). Two tiers, honest about fidelity:

  1. cmake-file-api  (fidelity: exact)   CMake's official machine-readable answer:
     drop a query file under <build>/.cmake/api/v1/query/ before the SAME
     configure-only run kb.compdb already does, and CMake replies with a full JSON
     codemodel — every target, type, sources, dependencies. Zero parsing of
     CMakeLists on our side.
  2. static-scan     (fidelity: partial) when configure is impossible: a
     structural scan of CMakeLists.txt/*.cmake for add_library/add_executable/
     target_link_libraries/option/find_package. Unexpanded ${VARS} are kept
     verbatim rather than guessed.

Output: <out_dir>/build_targets.jsonl — rows {"kind": "target"|"option"|"package"},
served by the MCP `build_info` tool.

  python -m kb.buildsys <code_root> <out_dir>
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

_TIDY = {"STATIC", "SHARED", "OBJECT", "MODULE", "INTERFACE", "ALIAS", "IMPORTED",
         "PRIVATE", "PUBLIC", "EXCLUDE_FROM_ALL", "GLOBAL"}


# ------------------------------------------------------------- 1: CMake File API
def fileapi_write_query(build_dir: str) -> None:
    """Ask CMake for the codemodel; call BEFORE `cmake -S … -B build_dir`."""
    qdir = os.path.join(build_dir, ".cmake", "api", "v1", "query")
    os.makedirs(qdir, exist_ok=True)
    open(os.path.join(qdir, "codemodel-v2"), "w").close()


def fileapi_parse(build_dir: str) -> list[dict] | None:
    """Read CMake's reply into target rows. None if no reply exists."""
    reply = os.path.join(build_dir, ".cmake", "api", "v1", "reply")
    cms = sorted(glob.glob(os.path.join(reply, "codemodel-v2-*.json")))
    if not cms:
        return None
    cm = json.load(open(cms[-1], encoding="utf-8"))
    rows = []
    for cfg in cm.get("configurations", [])[:1]:          # single-config generators
        for t in cfg.get("targets", []):
            tj = json.load(open(os.path.join(reply, t["jsonFile"]), encoding="utf-8"))
            rows.append({
                "kind": "target", "name": tj.get("name"),
                "type": tj.get("type", "").replace("_LIBRARY", "").lower(),
                "sources": [s["path"] for s in tj.get("sources", [])],
                "deps": [d["id"].split("::@")[0] for d in tj.get("dependencies", [])],
                "method": "cmake-file-api", "fidelity": "exact"})
    return rows or None


# ------------------------------------------------------------- 2: static fallback
_CMD = re.compile(r"(?im)^\s*(add_library|add_executable|target_link_libraries"
                  r"|option|find_package)\s*\(\s*([^)]*)\)", re.DOTALL)


def scan_static(code_root: str) -> list[dict]:
    """Structural scan of CMake files — no evaluation, ${VARS} left verbatim."""
    rows, seen_pkg = [], set()
    files = sorted(glob.glob(os.path.join(code_root, "**", "CMakeLists.txt"),
                             recursive=True) +
                   glob.glob(os.path.join(code_root, "**", "*.cmake"), recursive=True))
    for path in files:
        rel = os.path.relpath(path, code_root)
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for m in _CMD.finditer(text):
            cmd, args = m.group(1).lower(), m.group(2).split()
            if not args:
                continue
            if cmd in ("add_library", "add_executable"):
                body = [a for a in args[1:] if a.upper() not in _TIDY]
                rows.append({"kind": "target", "name": args[0],
                             "type": "executable" if cmd == "add_executable"
                             else "library",
                             "sources": body, "deps": [], "defined_in": rel,
                             "method": "static-scan", "fidelity": "partial"})
            elif cmd == "target_link_libraries":
                deps = [a for a in args[1:] if a.upper() not in _TIDY]
                for r in rows:
                    if r["kind"] == "target" and r["name"] == args[0]:
                        r["deps"] = sorted(set(r["deps"]) | set(deps))
                        break
                else:
                    rows.append({"kind": "target", "name": args[0], "type": "unknown",
                                 "sources": [], "deps": deps, "defined_in": rel,
                                 "method": "static-scan", "fidelity": "partial"})
            elif cmd == "option":
                rows.append({"kind": "option", "name": args[0],
                             "default": args[-1] if len(args) > 1 else "",
                             "defined_in": rel,
                             "method": "static-scan", "fidelity": "partial"})
            elif cmd == "find_package" and args[0] not in seen_pkg:
                seen_pkg.add(args[0])
                rows.append({"kind": "package", "name": args[0], "defined_in": rel,
                             "method": "static-scan", "fidelity": "partial"})
    return rows


# ------------------------------------------------------------------ orchestrator
def build(code_root: str, out_dir: str) -> dict:
    """File API if a configure succeeds (via kb.compdb's configure-only run,
    which now plants the query), else the static scan. Writes build_targets.jsonl."""
    if not os.path.isdir(code_root):
        raise SystemExit(f"code_root not found: {code_root}")
    rows = None
    build_dir = os.path.join(out_dir, "_compdb_build")
    if os.path.isfile(os.path.join(code_root, "CMakeLists.txt")):
        rows = fileapi_parse(build_dir)          # a prior compdb run already replied?
        if rows is None:
            from kb import compdb
            fileapi_write_query(build_dir)
            if compdb.from_cmake(code_root, out_dir):
                rows = fileapi_parse(build_dir)
    if rows is None:
        rows = scan_static(code_root)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "build_targets.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    method = rows[0]["method"] if rows else "none"
    return {"rows": len(rows), "method": method, "out": path}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="kb.buildsys", description=__doc__)
    ap.add_argument("code_root")
    ap.add_argument("out_dir")
    a = ap.parse_args(argv)
    print(json.dumps(build(a.code_root, a.out_dir)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
