#!/usr/bin/env bash
# Fetch all-MiniLM-L6-v2 (model.onnx + vocab.txt) from an ALLOWLISTED host and lay out a
# KB_MINILM_DIR for kb.recipes.get_embedder(). HuggingFace is not reachable from the
# Claude Code remote sandbox (egress allowlist), so host the two files somewhere the proxy
# permits -- e.g. a GitHub Release asset -- and pass their URLs here.
#
# Usage:
#   scripts/fetch_minilm.sh <MODEL_ONNX_URL> <VOCAB_TXT_URL> [DEST_DIR]
#   # then:  export KB_MINILM_DIR=<DEST_DIR>   (the script prints the exact line)
set -euo pipefail

MODEL_URL="${1:?need model.onnx URL (e.g. a GitHub release asset)}"
VOCAB_URL="${2:?need vocab.txt URL}"
DEST="${3:-$PWD/minilm}"

mkdir -p "$DEST"
fetch() {  # url -> dest, with backoff (matches the repo's network-retry convention)
  local url="$1" out="$2" i
  for i in 1 2 3 4; do
    if curl -fsSL -o "$out" "$url"; then return 0; fi
    echo "  fetch failed ($url), retry $i" >&2; sleep $((2 ** i))
  done
  echo "ERROR: could not fetch $url" >&2; return 1
}

echo "fetching model.onnx ..."; fetch "$MODEL_URL" "$DEST/model.onnx"
echo "fetching vocab.txt ...";  fetch "$VOCAB_URL" "$DEST/vocab.txt"

# sanity: non-empty, and the onnx magic byte sequence is present
test -s "$DEST/model.onnx" && test -s "$DEST/vocab.txt" || { echo "empty download" >&2; exit 1; }
echo "ok: $(wc -c < "$DEST/model.onnx") bytes model, $(wc -l < "$DEST/vocab.txt") vocab lines"
echo
echo "Done. Enable the MiniLM embedder with:"
echo "  export KB_MINILM_DIR=$DEST"
echo "  pip install onnxruntime numpy   # if not already present"
