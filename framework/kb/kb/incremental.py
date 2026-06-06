"""Incremental rebuild — recompute only what actually changed (Bazel-style).

The spec's key cost lever for L2: most commits touch a handful of symbols, so don't redo
everything. Two mechanisms:

  1. Content hash: input_hash(symbol) = sha256(own source + each callee's *fold* summary).
     If a symbol's source is untouched and none of its callees' folds changed, its hash is
     unchanged -> skip it.
  2. Fold-summary firewall: after recomputing a changed symbol, propagate dirtiness to its
     callers ONLY if its *fold* (outward-facing behavior) changed. An internal refactor that
     leaves the fold identical stops the cascade.

This module owns the deterministic dirty-set logic (verifiable without an LLM); the actual
re-summarization is L2's job. `fold_changed` is the set of recomputed symbols whose fold
actually changed (supplied by the L2 runner).

CLI (demo/verify the propagation):
  python -m kb.incremental demo
"""
from __future__ import annotations

import hashlib
import json
import sys


def input_hash(own_source: str, callee_folds: list[str]) -> str:
    """Stable content hash of a symbol's summarization inputs."""
    h = hashlib.sha256()
    h.update(own_source.encode("utf-8", "ignore"))
    for fold in sorted(callee_folds):  # order-independent
        h.update(b"\x00")
        h.update(fold.encode("utf-8", "ignore"))
    return h.hexdigest()


def reverse_edges(edges: list[dict]) -> dict[str, set[str]]:
    """callee_id -> {caller_id}."""
    rev: dict[str, set[str]] = {}
    for e in edges:
        rev.setdefault(e["callee_id"], set()).add(e["caller_id"])
    return rev


def compute_dirty(changed: set[str], edges: list[dict], fold_changed: set[str]) -> set[str]:
    """Symbols that must be recomputed.

    Start from `changed` (source edited). Walk *up* to callers, but a caller is only pulled
    in when a callee it depends on is in `fold_changed` (the firewall): an internal-only
    change (fold stable) does not propagate.
    """
    rev = reverse_edges(edges)
    dirty = set(changed)
    queue = [s for s in changed if s in fold_changed]
    while queue:
        node = queue.pop()
        for caller in rev.get(node, ()):  # behavior of `node` changed -> callers are stale
            if caller not in dirty:
                dirty.add(caller)
                if caller in fold_changed:
                    queue.append(caller)
    return dirty


def changed_symbols(symbols: list[dict], changed_paths: set[str]) -> set[str]:
    """Symbol ids whose defining file is in the changed set."""
    return {s["id"] for s in symbols if s.get("path") in changed_paths}


def _demo() -> int:
    # a -> b -> c -> d   (a calls b, etc.)  plus  e -> c
    edges = [
        {"caller_id": "a", "callee_id": "b"},
        {"caller_id": "b", "callee_id": "c"},
        {"caller_id": "c", "callee_id": "d"},
        {"caller_id": "e", "callee_id": "c"},
    ]
    print("graph: a->b->c->d, e->c")

    # Case 1: leaf d changed AND its fold changed -> propagate up to c, then c's callers
    # (b and e), then a. All reachable callers are stale.
    d1 = compute_dirty({"d"}, edges, fold_changed={"d", "c", "b", "a", "e"})
    print("1) d changed, folds all change  -> dirty:", sorted(d1))
    assert d1 == {"a", "b", "c", "d", "e"}, d1

    # Case 2: d changed but its fold is STABLE (internal refactor) -> firewall stops at d.
    d2 = compute_dirty({"d"}, edges, fold_changed=set())
    print("2) d changed, fold stable        -> dirty:", sorted(d2), "(firewall stops cascade)")
    assert d2 == {"d"}, d2

    # Case 3: c changed + only c's fold changed -> c's DIRECT callers (b, e) become stale,
    # but the cascade stops there (b's fold hasn't changed) so a is NOT pulled in; d (a
    # callee) is untouched. This is the firewall limiting blast radius.
    d3 = compute_dirty({"c"}, edges, fold_changed={"c"})
    print("3) c changed, only c.fold changes-> dirty:", sorted(d3), "(stops at direct callers)")
    assert d3 == {"b", "c", "e"}, d3

    # content hash: stable when inputs identical, different when source changes
    h1 = input_hash("int f(){return 1;}", ["adds one"])
    h2 = input_hash("int f(){return 1;}", ["adds one"])
    h3 = input_hash("int f(){return 2;}", ["adds one"])
    assert h1 == h2 and h1 != h3
    print("4) input_hash stable on identical inputs, changes on edit: OK")
    print("\nincremental: all invariants hold")
    return 0


def main(argv: list[str]) -> int:
    if argv and argv[0] == "demo":
        return _demo()
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
