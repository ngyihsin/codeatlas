#!/usr/bin/env bash
#
# generate.sh — rebuild the GENERATED registry block in an instance's INDEX.md from
# the authored sources (CONCEPTS.md, FLOWS.md). The registry is a deterministic
# projection: a concept/flow list with each entry's anchor and status. Authored
# sections of INDEX.md (protocol, contract, recipes, the rich Knowledge Map tables)
# live outside the markers and are never touched.
#
# Usage:
#   generate.sh <instance-dir>           # rewrite the registry block in place
#   generate.sh --check <instance-dir>   # exit 1 if the block is out of date (CI gate)
#
set -euo pipefail

CHECK=0
INSTANCE="."
for a in "$@"; do
  case "$a" in
    --check) CHECK=1 ;;
    *) INSTANCE="$a" ;;
  esac
done

INDEX="$INSTANCE/INDEX.md"
[ -f "$INDEX" ] || { echo "generate: no INDEX.md in $INSTANCE"; exit 0; }

START='<!-- GENERATED:registry START — do not edit; run framework/tools/generate.sh -->'
END='<!-- GENERATED:registry END -->'

# Build the registry rows from the authored docs (deterministic projection).
build_block() {
  echo "$START"
  echo "### Concept & Flow Registry (generated)"
  echo
  echo "| Kind | Name | Anchor | Status |"
  echo "|---|---|---|---|"
  awk '
    function flush(){ if(name!=""){ printf("| %s | %s | %s | %s |\n", kind, name, (anchor==""?"—":anchor), (status==""?"—":status)) } }
    /^## Concept:/ { flush(); kind="concept"; name=$0; sub(/^## Concept: */,"",name); anchor=""; status=""; next }
    /^## Flow:/    { flush(); kind="flow";    name=$0; sub(/^## Flow: */,"",name);    anchor=""; status=""; next }
    /^## /         { flush(); kind=""; name=""; anchor=""; status=""; next }
    /\*\*Anchor:\*\*/  && anchor=="" { a=$0; sub(/.*\*\*Anchor:\*\* */,"",a);  sub(/ *·.*$/,"",a); anchor=a }
    /\*\*Trigger:\*\*/ && anchor=="" { a=$0; sub(/.*\*\*Trigger:\*\* */,"",a); anchor=a }
    /Status:/ && status=="" { if($0 ~ /✓/) status="✓"; else if($0 ~ /◐/) status="◐"; else if($0 ~ /\?/) status="?" }
    END{ flush() }
  ' "$INSTANCE/CONCEPTS.md" "$INSTANCE/FLOWS.md" 2>/dev/null
  echo "$END"
}

block="$(build_block)"

# Produce the would-be new INDEX: replace the marker region, or insert it before
# "## How This Index Stays True" (else append).
render() {
  if grep -qF "$START" "$INDEX"; then
    awk -v start="$START" -v end="$END" -v block="$block" '
      $0==start {print block; skip=1; next}
      $0==end {skip=0; next}
      skip!=1 {print}
    ' "$INDEX"
  elif grep -qF '## How This Index Stays True' "$INDEX"; then
    awk -v anchor='## How This Index Stays True' -v block="$block" '
      $0==anchor && !done {print block; print ""; done=1}
      {print}
    ' "$INDEX"
  else
    cat "$INDEX"; printf '\n%s\n' "$block"
  fi
}

new="$(render)"

if [ "$CHECK" -eq 1 ]; then
  if [ "$new" = "$(cat "$INDEX")" ]; then
    echo "generate --check: $INDEX registry is up to date."
    exit 0
  else
    echo "generate --check: $INDEX registry is STALE. Run: framework/tools/generate.sh $INSTANCE"
    exit 1
  fi
fi

printf '%s\n' "$new" > "$INDEX"
echo "generate: rewrote the registry block in $INDEX."
