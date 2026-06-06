#!/usr/bin/env bash
#
# find-symbol.sh — L1 localization primitive: resolve a symbol to its definition anchor(s)
# and reference sites, in the framework's `file → symbol` anchor form. This is what a digital
# colleague calls to *locate* code before reading it — the cheap, structured alternative to
# loading the repo into context (see docs/research/digital-colleague-kb.md).
#
# Uses a prebuilt index (<codebase>/.docforge/symbols/tags.jsonl from build-symbol-index.sh)
# if present; otherwise runs ctags on the fly. References come from ripgrep.
#
# Usage: find-symbol.sh <codebase> <symbol-name> [max_refs]
#
set -euo pipefail

CODE="${1:?usage: find-symbol.sh <codebase> <symbol-name> [max_refs]}"
NAME="${2:?need a symbol name}"
MAXREFS="${3:-8}"

resolve() {  # $1 = path to a ctags JSON-lines file; prints definition anchors for $NAME
  python3 - "$NAME" "$CODE" "$1" <<'PY'
import json, os, sys
name, code, fp = sys.argv[1], os.path.abspath(sys.argv[2]), sys.argv[3]
for line in open(fp, encoding="utf-8", errors="ignore"):
    try:
        t = json.loads(line)
    except ValueError:
        continue
    if t.get("_type") == "tag" and t.get("name") == name and t.get("path"):
        rel = os.path.relpath(os.path.abspath(t["path"]), code)
        scope = f", scope {t['scope']}" if t.get("scope") else ""
        print(f"  {rel} → {name}  ({t.get('kind','')}{scope})  line {t.get('line','?')}")
PY
}

IDX="$CODE/.docforge/symbols/tags.jsonl"
if [ -f "$IDX" ]; then
  defs="$(resolve "$IDX")"
else
  tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
  ctags --output-format=json --fields=+nKlS --extras=+q -R -f - "$CODE" 2>/dev/null > "$tmp"
  defs="$(resolve "$tmp")"
fi

echo "== definition(s) of '$NAME' =="
[ -n "$defs" ] && printf '%s\n' "$defs" || echo "  (no definition found by ctags)"

echo "== references (showing up to $MAXREFS) =="
rg -n --no-heading -g '!.git' "\b${NAME}\b" "$CODE" 2>/dev/null | head -n "$MAXREFS" | sed 's/^/  /' || true

echo "== anchor (paste into docs) =="
if [ -n "$defs" ]; then
  printf '%s\n' "$defs" | head -1 | sed -E 's/^  ([^ ]+ \xe2\x86\x92 [^ ]+).*/  `\1`/'
else
  echo "  (none)"
fi
