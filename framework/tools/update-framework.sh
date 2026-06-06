#!/usr/bin/env bash
#
# update-framework.sh — refresh an instance's read-only framework cache to a version.
#
# Copies the framework/ plane into <instance>/.docforge/framework/ and records the
# version. It touches ONLY the cache — your authored, generated, and state files are
# never modified. After running, bump `template_version` in HANDOFF.md and read the
# CHANGELOG migration notes for the versions you crossed.
#
# Usage:
#   update-framework.sh <instance-dir> [framework-src-dir]
#     framework-src-dir defaults to this script's framework/ directory.
#
set -euo pipefail

INSTANCE="${1:?usage: update-framework.sh <instance-dir> [framework-src-dir]}"
FRAMEWORK_SRC="${2:-$(cd "$(dirname "$0")/.." && pwd)}"
DEST="$INSTANCE/.docforge/framework"

[ -f "$FRAMEWORK_SRC/STANDARD.md" ] || { echo "update: $FRAMEWORK_SRC does not look like a framework/ dir"; exit 1; }
mkdir -p "$DEST"

if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete "$FRAMEWORK_SRC"/ "$DEST"/
else
  rm -rf "$DEST"; mkdir -p "$DEST"; cp -R "$FRAMEWORK_SRC"/. "$DEST"/
fi

# VERSION lives inside framework/, so it travels with the cache and a self-refresh
# (source == an existing cache) still resolves the real version.
ver="$(cat "$FRAMEWORK_SRC/VERSION" 2>/dev/null || echo unknown)"
printf '%s\n' "$ver" > "$INSTANCE/.docforge/FRAMEWORK_VERSION"

echo "Updated framework cache: $DEST (version $ver)."
echo "Next:"
echo "  1. Set 'template_version: $ver' in the $INSTANCE/HANDOFF.md state block"
echo "  2. Read CHANGELOG.md migration notes for the versions you crossed"
echo "  3. Run: framework/tools/check-index.sh $INSTANCE"
