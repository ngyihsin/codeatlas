"""
kb.compdb — derive `compile_commands.json` without asking the user to run a build.

The precise tier (kb.scip_ingest) is clang-grade *because* it replays the real compile
flags; the flags have to come from the build system, and only the build system can
interpret its own files (CMakeLists.txt is a program, not data — reading it statically
is a losing game). So instead of parsing build files ourselves, this module runs the
cheapest command that makes the build system tell us, in fidelity order:

  1. cmake-configure   CMakeLists.txt: `cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON`
                       at CONFIGURE time — no compilation happens. Full fidelity.
  2. meson-setup       meson.build: `meson setup` emits compile_commands.json natively.
  3. make-dry-run      Makefile: parse compiler invocations out of `make -nB`
                       (what `compiledb` does). Fidelity = whatever make prints.
  4. synthesized       no build system / configure failed: walk the tree, guess
                       include dirs, emit `clang++ -std=c++17 -I…` entries.
                       Clang still parses every file, but flags are GUESSED —
                       config macros may be wrong. Honest tier: the result dict
                       says method=synthesized; treat edges as near-precise, not
                       ground truth.

Usage:
  python -m kb.compdb <code_root> <out_dir>            # writes <out_dir>/compile_commands.json
  python -m kb.scip_ingest build <code_root> auto <out_dir>   # derives it, then indexes
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys

C_EXT = {".c"}
CXX_EXT = {".cc", ".cpp", ".cxx"}
_COMPILERS = {"cc", "gcc", "clang", "c++", "g++", "clang++"}
_SKIP_DIRS = {".git", "build", "third_party", "vendor", "node_modules", "__pycache__"}


def detect(code_root: str) -> str | None:
    """Which build system owns this tree? (cmake > meson > make, like fidelity order)"""
    if os.path.isfile(os.path.join(code_root, "CMakeLists.txt")):
        return "cmake"
    if os.path.isfile(os.path.join(code_root, "meson.build")):
        return "meson"
    for mk in ("Makefile", "makefile", "GNUmakefile"):
        if os.path.isfile(os.path.join(code_root, mk)):
            return "make"
    return None


# --------------------------------------------------------------- 1/2: configure-only
def from_cmake(code_root: str, out_dir: str) -> str | None:
    """Configure (never build) with compile-commands export. Returns path or None."""
    if not shutil.which("cmake"):
        return None
    build_dir = os.path.join(out_dir, "_compdb_build")
    cmd = ["cmake", "-S", code_root, "-B", build_dir,
           "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"]
    if shutil.which("ninja"):
        cmd += ["-G", "Ninja"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    path = os.path.join(build_dir, "compile_commands.json")
    if r.returncode != 0 or not os.path.isfile(path):
        return None                      # missing deps etc. — fall through to synth
    return path


def from_meson(code_root: str, out_dir: str) -> str | None:
    if not shutil.which("meson"):
        return None
    build_dir = os.path.join(out_dir, "_compdb_build")
    r = subprocess.run(["meson", "setup", build_dir, code_root],
                       capture_output=True, text=True)
    path = os.path.join(build_dir, "compile_commands.json")
    return path if r.returncode == 0 and os.path.isfile(path) else None


# ------------------------------------------------------------------ 3: make dry-run
def parse_make_output(text: str, code_root: str) -> list[dict]:
    """Extract compiler invocations from `make -n` output (pure; unit-testable)."""
    entries = []
    for line in text.splitlines():
        try:
            toks = shlex.split(line.strip())
        except ValueError:
            continue
        if not toks or os.path.basename(toks[0]) not in _COMPILERS or "-c" not in toks:
            continue
        src = next((t for t in toks
                    if os.path.splitext(t)[1] in (C_EXT | CXX_EXT)), None)
        if src:
            entries.append({"directory": os.path.abspath(code_root),
                            "command": line.strip(), "file": src})
    return entries


def from_make_dry_run(code_root: str, out_dir: str) -> str | None:
    if not shutil.which("make"):
        return None
    r = subprocess.run(["make", "-nB"], cwd=code_root, capture_output=True, text=True)
    entries = parse_make_output(r.stdout, code_root)
    if not entries:
        return None
    return _write(out_dir, entries)


# ---------------------------------------------------------------- 4: honest fallback
def synthesize(code_root: str, out_dir: str) -> str | None:
    """No build system cooperated: clang parses everything, but flags are guessed."""
    root = os.path.abspath(code_root)
    sources, includes = [], {root}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        if os.path.basename(dirpath) == "include":
            includes.add(dirpath)
        for fn in filenames:
            if os.path.splitext(fn)[1] in (C_EXT | CXX_EXT):
                sources.append(os.path.join(dirpath, fn))
    if not sources:
        return None
    inc = [f"-I{d}" for d in sorted(includes)]
    entries = []
    for src in sorted(sources):
        cxx = os.path.splitext(src)[1] in CXX_EXT
        args = (["clang++", "-std=c++17"] if cxx else ["clang", "-std=c11"]) \
            + inc + ["-c", src]
        entries.append({"directory": root, "arguments": args, "file": src})
    return _write(out_dir, entries)


def _write(out_dir: str, entries: list[dict]) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "compile_commands.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=1)
    return path


# --------------------------------------------------------------------- orchestrator
def ensure(code_root: str, out_dir: str) -> dict:
    """Best compile_commands.json we can get, cheapest-accurate first.

    Returns {"compdb": path, "method": …, "entries": N}. method=synthesized means
    flags were guessed — clang-parsed, but NOT full clang-grade fidelity.
    """
    if not os.path.isdir(code_root):
        raise SystemExit(f"code_root not found: {code_root}")
    tried, system = [], detect(code_root)
    for method, fn in (("cmake-configure", from_cmake),
                       ("meson-setup", from_meson),
                       ("make-dry-run", from_make_dry_run)):
        if system == method.split("-")[0]:
            path = fn(code_root, out_dir)
            if path:
                return _result(path, method)
            tried.append(method)
    path = synthesize(code_root, out_dir)
    if not path:
        raise SystemExit(f"no C/C++ sources found under {code_root}")
    res = _result(path, "synthesized")
    res["tried"] = tried
    return res


def _result(path: str, method: str) -> dict:
    with open(path, encoding="utf-8") as f:
        n = len(json.load(f))
    return {"compdb": path, "method": method, "entries": n}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="kb.compdb", description=__doc__)
    ap.add_argument("code_root")
    ap.add_argument("out_dir")
    a = ap.parse_args(argv)
    print(json.dumps(ensure(a.code_root, a.out_dir)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
