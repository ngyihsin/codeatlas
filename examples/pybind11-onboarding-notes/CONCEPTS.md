# Core Concepts — pybind11

> Illustrative reference instance. Every code claim is `◐` (read-only) and anchored
> by `file → symbol (search "…")`. Re-verify against your checkout before acting.

---

## Concept: `type_caster<T>` — the C++ ↔ Python boundary

**Doc type:** explanation (core abstraction + data structure)
**Audience:** anyone adding a binding, a custom conversion, or debugging a TypeError
**You are assumed to know:** C++ templates, and that Python values are `PyObject*`
**Before you begin:** none
**Owner:** _(example instance — unowned)_
**Anchor:** `include/pybind11/cast.h → type_caster` (search `"class type_caster"`)
**Last verified against commit:** 6079989 (pybind11 3.1.0)   **Status:** ◐ Read-only
**Last verified date:** 2026-06-06

### Concrete Example First

When Python calls `m.add(2, 3)` on a bound C++ `int add(int,int)`, pybind11 turns the
Python `2` and `3` into C++ `int`s with `type_caster<int>::load()`, calls `add`, then
turns the C++ result back into a Python `int` with `type_caster<int>::cast()`. Every
value crossing the boundary goes through a `type_caster`.

### Plain-Language Explanation

A `type_caster<T>` is a small template that knows how to translate one C++ type `T` to
and from a Python object. It has two directions:

- **`load(handle src, bool convert)`** — Python → C++. Tries to read a C++ `T` out of
  a Python object. Returns `false` if the Python object is not convertible (this is
  how overload resolution rejects a candidate).
- **`cast(T src, return_value_policy, handle parent)`** — C++ → Python. Builds a
  Python object from a C++ value.

Built-in casters exist for numbers, strings, STL containers (`stl.h`), NumPy arrays
(`numpy.h`), and so on. For **bound C++ classes**, a generic caster
(`type_caster_base<T>`) looks the type up in a global registry (the `internals`) to
find its Python type and any existing wrapper instance. You can write your own caster
to support a custom type.

### Key Data Structure: the `internals` registry

Anchor: `include/pybind11/detail/internals.h → internals` (search `"struct internals"`).

Bound types and live instances are tracked in one process-wide `internals` struct,
fetched via `get_internals()`. The load-bearing fields:

| Field | Role | Invariant / lifetime |
|---|---|---|
| `registered_types_cpp` | map `std::type_index → type_info*` (C++ type → its pybind metadata) | keyed by RTTI; one entry per bound C++ type |
| `registered_types_py` | map `PyTypeObject* → type_info*` (Python type → C++ metadata) | the reverse direction of the above |
| `registered_instances` | multimap `void* → instance*` (C++ pointer → Python wrapper) | lets the same C++ object reuse one Python wrapper |
| `direct_conversions` | per-type extra conversion functions | consulted during `load` |
| ABI fields (`PYBIND11_INTERNALS_ID`, build-ABI tag) | identify a compatible `internals` | must match across modules sharing types |

### Why It Is Shaped This Way

1. **A single shared registry** — so a C++ object returned by one module can be
   recognized and wrapped consistently by another, and so the *same* C++ pointer maps
   to the *same* Python object (identity is preserved). **Why it matters:** without a
   shared registry, two extension modules could not pass bound objects to each other.
   ◐
   - *Rejected alternative (recoverable from the design):* per-module type tables.
     Simpler, but bound objects could not cross module boundaries, and object identity
     would break. The shared registry trades some ABI fragility for cross-module
     interop.
2. **Keyed by `std::type_index`** — RTTI gives a stable, compiler-provided identity
   for each C++ type, so casters in different translation units agree on what `T` is.
   ◐
3. **ABI-tagged** — the registry is only shared between modules built with a
   compatible pybind11 version and compiler ABI. The tag is baked into the module so
   incompatible modules get *separate* internals instead of corrupting one. ◐

### The Invariant a Consuming Skill Must Not Break

**Only access Python objects (and the `internals`) while holding the GIL, and respect
borrowed-vs-owned references.** Two related rules:

- **GIL:** any read/write of a `PyObject` — including every `type_caster` operation —
  requires the Global Interpreter Lock. Release it with `gil_scoped_release` only
  around pure-C++ work, and re-acquire with `gil_scoped_acquire` before touching
  Python again. (`include/pybind11/gil.h`.) ◐
- **References:** a `handle` is a **borrowed** reference (no refcount change); an
  `object` **owns** its reference (incref on copy, decref on destroy). Use
  `reinterpret_borrow<object>` / `reinterpret_steal<object>` to convert correctly.
  Mishandling this leaks memory or crashes the interpreter. (`include/pybind11/
  pytypes.h → handle`, `object`.) ◐

A segfault with no Python traceback is almost always one of these two. **Do not touch
`PyObject`s without the GIL, and do not hand-roll refcounting.** See the invariants
registry in `INDEX.md`.

### API Usage (worked example)

A minimal custom caster: teach pybind11 to convert a C++ `Point{int x,y;}` to/from a
Python 2-tuple.

```cpp
#include <pybind11/pybind11.h>
namespace py = pybind11;

struct Point { int x, y; };

namespace pybind11 { namespace detail {
template <> struct type_caster<Point> {
    PYBIND11_TYPE_CASTER(Point, const_name("Point"));   // declares `value` + name

    // Python -> C++: return false if not a 2-tuple of ints (overload rejects it).
    bool load(handle src, bool /*convert*/) {
        if (!py::isinstance<py::tuple>(src)) return false;
        auto t = py::reinterpret_borrow<py::tuple>(src);   // borrowed: GIL held here
        if (t.size() != 2) return false;
        value.x = t[0].cast<int>();
        value.y = t[1].cast<int>();
        return true;
    }

    // C++ -> Python: build an owning object.
    static handle cast(const Point &p, return_value_policy, handle) {
        return py::make_tuple(p.x, p.y).release();         // release(): hand off ownership
    }
}; }}
```

**Why the calls are shaped this way:** `load` returns `bool` precisely so overload
resolution can try the next candidate when conversion fails — that is the dispatcher's
contract. `reinterpret_borrow` is correct because the dispatcher already holds a
reference to `src` (and the GIL); `make_tuple(...).release()` transfers ownership to
the caller, matching the C-API convention that a returned `PyObject*` is a new
reference.

### Connections

- **Called by:** the dispatcher in `include/pybind11/pybind11.h` (search
  `"dispatcher"`) via `argument_loader` (`cast.h`). ◐
- **Calls into:** `get_internals()` (`detail/internals.h`) for bound-class lookup. ◐
- **Related concept:** `handle` / `object` reference semantics (`pytypes.h`).
- **Related flow:** `FLOWS.md → "Calling a Bound C++ Function from Python"`.

### Deviation Callout (for agent readers)

A `type_caster` is **not** a simple value converter you can call anytime. Its
operations assume the **GIL is held** and run inside the dispatcher's reference-managed
context. Reasoning that treats casting as a free function ignoring the GIL is wrong.

### Open Questions Raised

- ? Exact ABI-compatibility rules (which compiler/flag differences force separate
  `internals`) and how `PYBIND11_INTERNALS_VERSION` bumps interact with mixed-version
  modules. Not traced here.

---

## Concept: `handle` vs `object` — borrowed vs owned references (brief)

**Anchor:** `include/pybind11/pytypes.h → handle`, `object` · **Status:** ◐

`handle` wraps a `PyObject*` **without** owning it (no refcount change). `object`
derives from `handle` but **owns** the reference: it increfs on copy and decrefs on
destruction.

- **Why two types:** the compiler enforces ownership intent. Passing a `handle` where
  an `object` is needed is a borrow that may dangle; the type distinction makes the
  refcounting contract explicit. ◐
- **Invariant:** convert raw `PyObject*` with `reinterpret_borrow` (you do not own it)
  or `reinterpret_steal` (you do); never construct `object` from a raw pointer
  directly. ◐

---

## Cross-Reference Index

| File / Path | Concept(s) |
|---|---|
| `include/pybind11/cast.h` | `type_caster<T>` |
| `include/pybind11/detail/internals.h` | the `internals` registry |
| `include/pybind11/detail/type_caster_base.h` | generic caster for bound classes |
| `include/pybind11/pytypes.h` | `handle` / `object` reference semantics |
| `include/pybind11/gil.h` | GIL scopes |
