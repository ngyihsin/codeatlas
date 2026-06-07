"""
kb.recipes — semantic search over the L3 recipe layer (gap G9).

Per docs/kb/leverage.md §G9, this is the *one* place semantic/vector search is
sanctioned (natural-language recipes, never raw source). The design is pluggable:

  - `Embedder`  — embed(text) -> vector. Default `HashEmbedder` is **dependency-free**
                  (normalized hashing bag-of-words): offline, deterministic, good enough
                  to rank a small recipe set and to keep CI hermetic. For true synonym-
                  level semantics, plug an ONNX MiniLM or an embedding-API embedder
                  behind the same interface (no other code changes).
  - store       — brute-force cosine over the in-memory recipe vectors. At recipe scale
                  (tens–hundreds) ANN is unnecessary; `sqlite-vec` is the drop-in backend
                  when the layer grows (zero-dep SQLite extension).

`find_recipe` uses this when available and falls back to keyword match, so behavior
degrades gracefully.
"""
from __future__ import annotations

import hashlib
import math

from .retrieve import _tokens   # shared tokenization (lowercase, stopword-filtered)


class Embedder:
    def embed(self, text: str) -> list[float]:
        raise NotImplementedError


class HashEmbedder(Embedder):
    """Normalized hashing bag-of-words. Dependency-free and deterministic (uses md5,
    not Python's per-process-salted hash). Captures token overlap as cosine similarity."""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for tok in _tokens(text):
            idx = int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim
            v[idx] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))   # inputs are L2-normalized


def _recipe_text(r: dict) -> str:
    parts = [str(r.get(k, "")) for k in ("title", "task", "when")]
    parts += [str(dp.get("q", "")) for dp in r.get("decision_points", []) if isinstance(dp, dict)]
    parts += [str(p) for p in r.get("pitfalls", [])]
    return " ".join(parts)


class RecipeIndex:
    """Vector index over recipes. Small N -> brute-force cosine (no ANN needed)."""

    def __init__(self, recipes: list[dict], embedder: Embedder | None = None):
        self.embedder = embedder or HashEmbedder()
        self.recipes = recipes
        self.vectors = [self.embedder.embed(_recipe_text(r)) for r in recipes]

    def search(self, query: str, k: int = 3) -> list[dict]:
        if not self.recipes:
            return []
        q = self.embedder.embed(query)
        scored = sorted(
            ((cosine(q, v), r) for v, r in zip(self.vectors, self.recipes)),
            key=lambda t: -t[0],
        )
        out = []
        for score, r in scored[:k]:
            if score <= 0:
                continue
            out.append({"id": r.get("id"), "title": r.get("title", ""),
                        "confidence": r.get("confidence", "draft"),
                        "score": round(score, 4)})
        return out
