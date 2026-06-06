# Core Concepts — Redis

> Illustrative reference instance. Every code claim is `◐` (read-only) and anchored
> by `file → symbol (search "…")`. Re-verify against your checkout before acting.

---

## Concept: `dict` — the hash table with incremental rehashing

**Doc type:** explanation (data structure)
**Audience:** a developer who will touch the keyspace, a data type, or expiration
**You are assumed to know:** what a hash table and a hash collision are
**Before you begin:** none
**Owner:** _(example instance — unowned)_
**Anchor:** `src/dict.c` / `src/dict.h` → `dict` (search `"struct dict"`)
**Last verified against commit:** 4625b89 (redis unstable)   **Status:** ◐ Read-only
**Last verified date:** 2026-06-06

### Concrete Example First

Every key you store lives in a `dict`. `SET user:42 alice` ultimately calls
`dictAdd(db->dict, "user:42", robj*)` (`src/db.c → dbAdd`), and `GET user:42` calls
`dictFind(db->dict, "user:42")` (`src/db.c → lookupKey`). The keyspace *is* a `dict`.

### Plain-Language Explanation

A `dict` is Redis's hash table: an array of buckets, each holding a linked list of
entries that hashed to that bucket. Keys and values are `void *`, so the same `dict`
stores the keyspace, hash fields, expiration times, and more.

The interesting part is **how it grows**. When a hash table fills up, it must move
every entry into a larger bucket array. For a table with millions of keys, doing that
in one step would freeze the single-threaded server for a long pause. Redis avoids
the pause by rehashing **incrementally**: it keeps two bucket arrays during a resize
and moves a few buckets at a time, spread across many normal operations.

### Key Data Structure

Anchor: `src/dict.h → dict` (search `"struct dict"`).

The design rests on **two hash tables and a rehash cursor**. Field names differ by
version — Redis ≤6.2 uses a `dictht ht[2]` array of `dictht` structs; Redis ≥7.0
inlines them as `ht_table[2]` / `ht_used[2]` / `ht_size_exp[2]`. The *shape* is the
same:

| Element | Role | Invariant / lifetime |
|---|---|---|
| two bucket arrays (`ht[0]`, `ht[1]`) | the "current" table and, during a resize, the "new" larger table | `ht[1]` is empty/unused except while rehashing |
| `rehashidx` | the next bucket index in `ht[0]` to migrate; `-1` when not rehashing | `>= 0` exactly while a rehash is in progress |
| per-table `used` / `size` | entry count and bucket count | `size` is always a power of two; `sizemask = size - 1` |
| `dictType *type` | callbacks: hash function, key compare, key/val destructors | set at creation, immutable |
| `dictEntry` | one key/value pair plus `next` (separate chaining) | lives in `ht[0]` *or* `ht[1]`, never both |

### Why It Is Shaped This Way

1. **Two tables instead of one** — so a resize does not need to move every entry at
   once. The new, larger array is `ht[1]`; entries migrate from `ht[0]` to `ht[1]`
   gradually. **Why it matters:** the server is single-threaded, so a one-shot O(N)
   rehash of a huge table would stall every client. ◐
   - *Rejected alternative (recoverable from the design):* resize in place with one
     big rehash. Simpler, but it reintroduces the latency spike Redis exists to
     avoid. The two-table design trades a little memory and lookup complexity for
     bounded per-operation latency.
2. **`rehashidx` as a cursor** — rehashing is resumable. Each step migrates the
   buckets from `rehashidx` forward, advancing the cursor, until `ht[0]` is empty.
   `dictRehash(d, n)` does bounded work: at most `n` buckets, visiting at most
   `n * 10` empty slots before yielding. ◐
3. **Power-of-two sizing** — so `hash & sizemask` replaces the slower `hash % size`.
   ◐
4. **Separate chaining** — collisions extend a linked list rather than probing, which
   keeps deletion and the incremental migration simple. ◐

### The Invariant a Consuming Skill Must Not Break

**During a rehash, entries exist in both tables, so every operation must check both —
and inserts go only into `ht[1]`.**

- Lookups (`dictFind`) and deletes scan `ht[0]`; if `dictIsRehashing(d)`, they also
  scan `ht[1]`. ◐
- Inserts (`dictAdd`) place new entries into `ht[1]` while rehashing, so `ht[0]`
  only ever shrinks. ◐

Code that reads or mutates a `dict` directly (instead of through the `dict*` API) and
forgets the second table will silently lose keys during a resize. **Do not bypass the
API.** See the invariants registry in `INDEX.md`.

### API Usage (worked example)

Look up a key, honoring incremental rehashing automatically:

```c
#include "dict.h"

/* db->dict is the keyspace dict; sds key is a Redis string. */
dictEntry *de = dictFind(db->dict, key);   /* checks ht[0], and ht[1] if rehashing */
if (de != NULL) {
    robj *val = dictGetVal(de);            /* the stored value object              */
    /* ... use val ... */
}

/* Insert. While rehashing, dictAdd writes into ht[1]; you never manage that. */
if (dictAdd(db->dict, key, val) != DICT_OK) {
    /* key already existed */
}
```

**Why the calls are shaped this way:** you never touch `ht[0]` / `ht[1]` or
`rehashidx` yourself. `dictFind` and `dictAdd` consult both tables and advance the
rehash one step (`_dictRehashStep`) on each call. That single-step-per-operation is
*how* the migration spreads its cost across many commands. Bypassing the API to read
the bucket array directly is the classic way to break the dual-table invariant above.

### Connections

- **Called by:** `src/db.c → lookupKey`, `dbAdd`, `dbDelete` (the keyspace); every
  `t_*.c` data-type file for its own dicts. ◐
- **Calls into:** the `dictType` callbacks (hash, compare, destructors). ◐
- **Related concept:** `redisObject` (the values stored as `dictEntry` values) —
  see below.
- **Related flow:** `FLOWS.md → "Life of a GET"` (step where `dictFind` runs).

### Deviation Callout (for agent readers)

This is **separate chaining with two live tables during resize**, not a standard
single-array open-addressing hash map. Any reasoning that assumes one bucket array
is wrong whenever `rehashidx >= 0`.

### Open Questions Raised

- ? Exact resize trigger thresholds and how `dict_can_resize` interacts with a forked
  child during persistence (copy-on-write avoidance). Not traced here.

---

## Concept: `redisObject` — the boxed value (brief)

**Anchor:** `src/object.h → redisObject` (search `"struct redisObject"`) · **Status:** ◐

Every value Redis stores is a `redisObject` (`robj`): a small box with `type` (string,
list, hash, …), `encoding` (how it is physically stored, e.g. `int`, `embstr`, `raw`),
a 24-bit `lru` field for eviction, a `refcount`, and a `void *ptr` to the payload.

- **Why a box:** one uniform handle for many types and physical encodings, so the
  command core can pass values around without knowing their representation. ◐
- **Encoding (verified by running @4625b89):** `SET n 12345; OBJECT ENCODING n` → `int`;
  a long string → `raw`. The `type`/`encoding` boxing is confirmed. ✓
- **Invariant — version-sensitive:** shared immutable objects (small integers in
  `shared.integers`, `src/server.c`) historically have `refcount == OBJ_SHARED_REFCOUNT`.
  But **running @4625b89, `SET k 100; OBJECT REFCOUNT k` returned `1`, not the shared
  sentinel** — in the 8.x `kvobj` refactor the value is embedded in the key entry, so a
  keyspace string value is not the global shared object. The shared-object machinery
  still exists (used elsewhere, e.g. replies); treat "keyspace small ints are shared"
  as **not holding** on the 8.x line. ◐
- **Related:** stored as the value of each key entry (`kvobj`) in the keyspace.

---

## Cross-Reference Index

| File / Path | Concept(s) |
|---|---|
| `src/dict.c`, `src/dict.h` | `dict` / incremental rehashing |
| `src/object.h → redisObject` | `redisObject` |
| `src/db.c` | uses `dict` (keyspace) |
| `src/object.c` | `redisObject` lifecycle |
