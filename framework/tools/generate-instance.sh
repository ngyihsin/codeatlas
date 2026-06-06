#!/usr/bin/env bash
#
# generate-instance.sh — bootstrap a draft onboarding instance from a real checkout.
#
# This is the DETERMINISTIC half of the auto-generation pipeline (see framework/GENERATION.md):
# it copies the scaffold, builds the L1 symbol index, and seeds the parts that can be derived
# mechanically — structural map, entry-point candidates, candidate concepts (top symbols by
# reference frequency), and provenance — into DRAFT-SEED.md, with everything marked ◐/TODO.
# The JUDGMENT half (which concepts matter, the *why*, the flows) is left for the generator
# agent + the owner review (◐ → ✓). It never fabricates understanding; it stages facts.
#
# Usage:
#   generate-instance.sh <codebase> <out_instance_dir> [scaffold_dir]
#
set -euo pipefail

CODE="${1:?usage: generate-instance.sh <codebase> <out_instance_dir> [scaffold_dir]}"
OUT="${2:?need an output instance dir}"
HERE="$(cd "$(dirname "$0")" && pwd)"                 # framework/tools
SCAFFOLD="${3:-$(cd "$HERE/../../scaffold" && pwd)}"  # repo scaffold/
FRAMEWORK="$(cd "$HERE/.." && pwd)"                   # framework/

[ -d "$CODE" ] || { echo "generate-instance: codebase not found: $CODE" >&2; exit 2; }
[ -d "$SCAFFOLD" ] || { echo "generate-instance: scaffold not found: $SCAFFOLD" >&2; exit 2; }
[ -e "$OUT" ] && { echo "generate-instance: $OUT already exists — refusing to overwrite" >&2; exit 2; }

mkdir -p "$OUT"
cp -R "$SCAFFOLD"/. "$OUT"/

# 1. Provenance: pin the codebase commit + the framework version.
sha="$(git -C "$CODE" rev-parse --short HEAD 2>/dev/null || echo "unknown")"
fver="$(cat "$FRAMEWORK/VERSION" 2>/dev/null || echo unknown)"
date="$(date -u +%F)"

# 2. L1 symbol index + repo map (best-effort; needs ctags+rg).
if command -v ctags >/dev/null 2>&1 && command -v rg >/dev/null 2>&1; then
  "$HERE/build-symbol-index.sh" "$CODE" "$OUT/.docforge/symbols" 200 >/dev/null 2>&1 || true
  idx_note="built (.docforge/symbols/repomap.md, symbols.tsv, tags.jsonl)"
else
  idx_note="SKIPPED — install universal-ctags + ripgrep, then run build-symbol-index.sh"
fi

# 3. Seed the deterministic facts into DRAFT-SEED.md (structural map, entry points, concepts).
python3 - "$CODE" "$OUT" "$sha" "$fver" "$date" "$idx_note" <<'PY'
import os, sys, subprocess, collections
code, out, sha, fver, date, idx_note = sys.argv[1:7]

# structural map: top dirs by file count (git if available, else walk)
counts = collections.Counter()
try:
    files = subprocess.check_output(["git","-C",code,"ls-files"], text=True).splitlines()
except Exception:
    files = []
    for r,_,fs in os.walk(code):
        if "/.git" in r: continue
        for f in fs: files.append(os.path.relpath(os.path.join(r,f), code))
for f in files:
    top = f.split("/",1)[0] if "/" in f else "(root)"
    counts[top] += 1
top_dirs = counts.most_common(12)

# entry-point candidates: functions named main + likely files (skip vendored/test/example dirs)
EXCLUDE = ("deps/", "third_party/", "vendor/", "node_modules/", "external/",
           "test/", "tests/", "examples/", "example/", "benchmark")
def vendored(path): return any(seg in path for seg in EXCLUDE)
entry_syms, entry_files = [], []
sym = os.path.join(out, ".docforge/symbols/symbols.tsv")
if os.path.exists(sym):
    for line in open(sym, encoding="utf-8", errors="ignore"):
        p = line.rstrip("\n").split("\t")
        if len(p) >= 3 and p[0] == "main" and p[1] in ("function","method") and not vendored(p[2]):
            entry_syms.append(f"{p[2]} → main ({p[1]})")
for f in files:
    b = os.path.basename(f).lower()
    if b in ("main.c","main.cc","main.cpp","main.py","__main__.py","cli.py","server.c","app.py") and not vendored(f):
        entry_files.append(f)

# candidate concepts: top repo-map rows (already ranked by build-symbol-index)
concepts = []
rm = os.path.join(out, ".docforge/symbols/repomap.md")
if os.path.exists(rm):
    for line in open(rm, encoding="utf-8", errors="ignore"):
        line=line.strip()
        if line.startswith("| ") and "`" in line and "anchor" not in line and "---" not in line:
            concepts.append(line)
        if len(concepts) >= 20: break

with open(os.path.join(out, "DRAFT-SEED.md"), "w") as f:
    f.write(f"""# DRAFT SEED (auto-generated — ◐, not reviewed)

> Produced by `generate-instance.sh`. These are **mechanically derived facts**, not
> understanding. The generator agent folds them into `OVERVIEW.md` / `CONCEPTS.md` /
> `FLOWS.md` / `API.md` / `INDEX.md`, raises them to L3, and the **owner reviews `◐ → ✓`**
> (see `.docforge/framework/GENERATION.md`). Delete this file once folded in.

**Codebase commit:** {sha}  ·  **Framework version:** {fver}  ·  **Seeded:** {date}
**Symbol index:** {idx_note}

## Structural map (top directories by file count) — seeds OVERVIEW.md
""")
    for d,c in top_dirs:
        f.write(f"- `{d}/` — {c} files  _(label its role; mark 🔴/🟡/⚪/🟢)_\n")
    f.write("\n## Entry-point candidates — seeds OVERVIEW.md → Entry Points\n")
    for s in entry_syms[:10]: f.write(f"- {s}\n")
    for fl in entry_files[:10]: f.write(f"- `{fl}`\n")
    if not entry_syms and not entry_files: f.write("- _(none auto-detected; find the real entry point)_\n")
    f.write("\n## Candidate concepts — most-referenced symbols (pick 3–7 to deep-dive in CONCEPTS.md)\n")
    f.write("See full ranking in `.docforge/symbols/repomap.md`. Top rows:\n\n")
    f.write("| # | refs | symbol | kind | anchor |\n|---|---|---|---|---|\n")
    for row in concepts:
        f.write(row + "\n")
    f.write("""
## Next (generator agent + owner)
1. Fold the structural map + entry points into `OVERVIEW.md`.
2. Pick the load-bearing concepts above; deep-dive each in `CONCEPTS.md` (data structure +
   *why* + worked API call); use `find-symbol.sh` to confirm/refresh each `file → symbol`.
3. Trace one user-visible flow into `FLOWS.md` (+ its error branch).
4. Fill `API.md` (provided surface + consumed interfaces + feature→API) and the `INDEX.md`
   Knowledge Map + invariants registry; run `check-index.sh`.
5. Tag every claim ◐ until verified; record `Last verified against commit:` = the sha above.
6. Owner reviews each entry `◐ → ✓`; then delete this DRAFT-SEED.md.
""")
print(f"seeded DRAFT-SEED.md ({len(top_dirs)} dirs, {len(concepts)} candidate concepts)")
PY

# 4. Stamp provenance into the HANDOFF state block.
if [ -f "$OUT/HANDOFF.md" ]; then
  sed -i "s/^template_version: .*/template_version: $fver/" "$OUT/HANDOFF.md" 2>/dev/null || true
fi

echo "generate-instance: drafted $OUT  (codebase @$sha, framework $fver)"
echo "  next: run the generator agent over DRAFT-SEED.md, then owner review (◐ → ✓)."
echo "  see GENERATION.md for the pipeline."
