#!/usr/bin/env bash
#
# check-doc-drift.sh — flag notes whose cited code paths changed in the codebase.
#
# Turns drift control from a chore (remembering to run Phase 7) into a gate. Run it
# in CI on every pull request, or locally before trusting the docs. It does NOT prove
# the docs are correct — it proves which docs cite code that moved, so a human or an
# agent re-verifies exactly those and nothing else.
#
# Usage:
#   NOTES_DIR=<notes dir> CODEBASE=<codebase repo> ./check-doc-drift.sh [BASE_REF]
#
#   BASE_REF   git ref to diff the codebase against (default: origin/main)
#   NOTES_DIR  the notes directory (default: this script's parent directory)
#   CODEBASE   the codebase git repo to check (default: current directory)
#
# Exit codes: 0 = no cited path changed; 1 = drift suspected (cited paths changed).
#
set -euo pipefail

NOTES_DIR="${NOTES_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
CODEBASE="${CODEBASE:-.}"
BASE_REF="${1:-origin/main}"

# 1. Files changed in the codebase since BASE_REF.
changed="$(git -C "$CODEBASE" diff --name-only "${BASE_REF}...HEAD" | sort -u)"

# 2. Code paths cited anywhere in the notes. Anchors look like `path/to/file → Sym`
#    or `path/to/file.ext:10-20`; keep the path part, drop the symbol / line suffix.
cited="$(grep -rhoE '`[^`]+`' "$NOTES_DIR" --include='*.md' 2>/dev/null \
  | sed -E 's/`//g; s/ *(→|:| \(search).*$//' \
  | grep -E '^[A-Za-z0-9._/-]+/[A-Za-z0-9._-]+\.[A-Za-z0-9]+$' \
  | sort -u)"

# 3. Intersection = cited files that changed.
drift="$(comm -12 <(printf '%s\n' "$changed") <(printf '%s\n' "$cited") || true)"

if [ -z "$drift" ]; then
  echo "OK: no cited code path changed since ${BASE_REF}."
  exit 0
fi

echo "DRIFT SUSPECTED — these cited paths changed since ${BASE_REF}:"
echo "$drift" | sed 's/^/  /'
echo
echo "Notes that cite them (re-verify and update 'Last verified against commit'):"
for f in $drift; do
  grep -rl --include='*.md' -F "$f" "$NOTES_DIR" | sed "s|^|  ${f}  ←  |"
done
exit 1
