"""
kb.embed — a real (MiniLM/ONNX) embedder behind the L3 `Embedder` interface (gap G9, #1).

`recipes.HashEmbedder` (lexical hashing) is the dependency-free default; this adds true
synonym-level semantics via **all-MiniLM-L6-v2 run through ONNX Runtime** (no torch). Per
docs/kb/leverage.md §G9 the embedding model is a drop-in behind the same `embed(text)`
interface — nothing else changes.

Design notes so this stays testable and dependency-light:
  - `onnxruntime` / `numpy` are imported only inside `OnnxEmbedder.from_dir` — CI and the
    default path never import them.
  - `OnnxEmbedder` takes an injectable `session` (anything with `.run(None, feeds)`), so the
    tokenizer + mean-pooling + normalization are all unit-tested offline with a fake session;
    the real path is the standard `ort.InferenceSession(...).run(...)` call.
  - Tokenization is a self-contained WordPiece (the MiniLM/BERT-uncased scheme) reading a
    plain `vocab.txt`, so there is no `transformers`/`tokenizers` dependency.

Provide a model directory (containing `model.onnx` + `vocab.txt`) via `KB_MINILM_DIR` or to
`recipes.get_embedder(model_dir=...)`; absent that, the layer transparently uses HashEmbedder.
"""
from __future__ import annotations

import math
import re

_PUNCT = re.compile(r"[^\w]|_")          # split punctuation off, BERT-style
_WORD = re.compile(r"\w+|[^\w\s]")


class WordPieceTokenizer:
    """Greedy WordPiece over a bert-base-uncased style vocab. Lowercases; emits
    [CLS] … [SEP] with the `##` continuation convention; unknown words -> [UNK]."""

    def __init__(self, vocab: dict[str, int], *, unk="[UNK]", cls="[CLS]",
                 sep="[SEP]", max_chars=100):
        self.vocab = vocab
        self.unk, self.cls, self.sep = unk, cls, sep
        self.max_chars = max_chars

    @classmethod
    def from_file(cls, path: str) -> "WordPieceTokenizer":
        vocab = {}
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                vocab[line.rstrip("\n")] = i
        return cls(vocab)

    def _wordpiece(self, word: str) -> list[str]:
        if len(word) > self.max_chars:
            return [self.unk]
        out, start, n = [], 0, len(word)
        while start < n:
            end = n
            cur = None
            while start < end:
                piece = word[start:end]
                if start > 0:
                    piece = "##" + piece
                if piece in self.vocab:
                    cur = piece
                    break
                end -= 1
            if cur is None:
                return [self.unk]      # one unsplittable piece -> whole word is UNK
            out.append(cur)
            start = end
        return out

    def tokenize(self, text: str) -> list[str]:
        toks: list[str] = []
        for word in _WORD.findall(text.lower()):
            toks.extend(self._wordpiece(word))
        return toks

    def encode(self, text: str, max_len: int = 256) -> tuple[list[int], list[int], list[int]]:
        """-> (input_ids, attention_mask, token_type_ids), with [CLS]/[SEP], truncated."""
        pieces = [self.cls] + self.tokenize(text)[: max_len - 2] + [self.sep]
        unk_id = self.vocab.get(self.unk, 0)
        ids = [self.vocab.get(p, unk_id) for p in pieces]
        return ids, [1] * len(ids), [0] * len(ids)


def mean_pool_normalize(last_hidden, mask: list[int]) -> list[float]:
    """Attention-masked mean pooling over tokens, then L2 normalize. Pure Python so it
    works on both numpy output (real ORT) and nested lists (the test fake). `last_hidden`
    is shape (1, seq, dim)."""
    rows = last_hidden[0]
    denom = sum(mask) or 1
    dim = len(rows[0])
    sums = [0.0] * dim
    for t, m in enumerate(mask):
        if m:
            r = rows[t]
            for d in range(dim):
                sums[d] += float(r[d])
    vec = [s / denom for s in sums]
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class OnnxEmbedder:
    """embed(text) -> L2-normalized sentence vector via a MiniLM ONNX session.

    `session.run(None, feeds)` must return the token embeddings (1, seq, dim) as output 0.
    `input_names` limits which feeds are passed (some MiniLM exports omit token_type_ids)."""

    def __init__(self, session, tokenizer: WordPieceTokenizer, *, array=None,
                 input_names: set[str] | None = None, max_len: int = 256):
        self.session = session
        self.tok = tokenizer
        self.max_len = max_len
        self._array = array or (lambda x: x)
        self._inputs = input_names

    def embed(self, text: str) -> list[float]:
        ids, mask, types = self.tok.encode(text, self.max_len)
        feeds = {"input_ids": self._array([ids]),
                 "attention_mask": self._array([mask]),
                 "token_type_ids": self._array([types])}
        if self._inputs is not None:
            feeds = {k: v for k, v in feeds.items() if k in self._inputs}
        out = self.session.run(None, feeds)[0]
        return mean_pool_normalize(out, mask)

    @classmethod
    def from_dir(cls, model_dir: str) -> "OnnxEmbedder":
        import os
        import numpy as np
        import onnxruntime as ort
        sess = ort.InferenceSession(os.path.join(model_dir, "model.onnx"),
                                    providers=["CPUExecutionProvider"])
        tok = WordPieceTokenizer.from_file(os.path.join(model_dir, "vocab.txt"))
        names = {i.name for i in sess.get_inputs()}
        return cls(sess, tok, array=lambda x: np.array(x, dtype=np.int64),
                   input_names=names)
