#!/usr/bin/env bash
#
# check-index.sh — verify an instance's INDEX.md Knowledge Map covers every concept
# and flow authored in CONCEPTS.md / FLOWS.md.
#
# This tool does NOT modify any file. The Knowledge Map in INDEX.md is authored — the
# single source of truth — and this linter guards its completeness so a consuming
# skill never reads an INDEX that is missing a concept or flow. Run it in CI and after
# adding a concept or flow.
#
# Usage:
#   check-index.sh <instance-dir>          # exit 1 if a concept/flow is missing from INDEX
#   check-index.sh --check <instance-dir>  # same (--check accepted for CI symmetry)
#
set -euo pipefail

INSTANCE="."
for a in "$@"; do
  case "$a" in
    --check) : ;;            # this tool always checks; flag accepted for symmetry
    *) INSTANCE="$a" ;;
  esac
done

C="$INSTANCE/CONCEPTS.md"
F="$INSTANCE/FLOWS.md"
I="$INSTANCE/INDEX.md"

[ -f "$I" ] || { echo "check-index: no INDEX.md in $INSTANCE — skipping"; exit 0; }

# Normalize: lowercase, drop backticks / underscores / asterisks. Applied to both the
# key and the index text so the comparison is robust to markdown emphasis.
norm() { tr 'A-Z' 'a-z' | tr -d '`_*'; }

idx_norm="$(norm < "$I")"
missing=0

# For each "## Concept:" / "## Flow:" heading, take its first backtick-quoted token as
# a stable key (e.g. `dict`, `type_caster<T>`, `GET`) and require it to appear in the
# INDEX. Placeholder headings with no backtick token (e.g. the scaffold's
# "_<Name>_") are skipped — there is nothing concrete to verify yet.
check_kind() {
  local src="$1" prefix="$2" kind="$3"
  if [ ! -f "$src" ]; then
    echo "check-index: WARNING: $src not found; cannot verify $kind coverage." >&2
    return 0
  fi
  local heading name key
  while IFS= read -r heading; do
    name="${heading#"$prefix"}"
    key="$(printf '%s' "$name" | grep -oE '`[^`]+`' | head -n1 | norm || true)"
    [ -z "$key" ] && continue
    case "$idx_norm" in
      *"$key"*) : ;;
      *) echo "  MISSING from INDEX.md ($kind): $name"; missing=$((missing + 1)) ;;
    esac
  done < <(grep -E "^$prefix" "$src" || true)
}

check_kind "$C" '## Concept: ' "concept"
check_kind "$F" '## Flow: ' "flow"

if [ "$missing" -gt 0 ]; then
  echo "check-index: $missing authored entr(y/ies) missing from $I Knowledge Map."
  echo "  Add them to INDEX.md (the Knowledge Map is the single source of truth)."
  exit 1
fi
echo "check-index: $I covers all authored concepts and flows."
