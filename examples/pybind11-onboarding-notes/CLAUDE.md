# CLAUDE.md — pybind11 onboarding notes

> Lean per-session index (≤200 lines). Illustrative reference instance — all code
> claims are `◐`; re-verify against your checkout.
>
> **Here to DO a task — fix a bug, build a feature, write a design doc?** Start at
> `INDEX.md` (machine-readable map, invariants registry, task recipes).

## Project in One Paragraph

pybind11 is a header-only C++11 library that exposes C++ to Python (and back). You
declare bindings in C++ (`PYBIND11_MODULE`, `m.def`, `class_`); pybind11 generates the
CPython glue using templates and RTTI. The distinctive trait: every value crossing the
boundary goes through a `type_caster<T>`, and all bound types live in one shared,
ABI-tagged `internals` registry.

## Top-Level Architecture (5 lines)

- It is header-only: the code is in `include/pybind11/`; there is no compiled lib.
- `PYBIND11_MODULE` expands to CPython's `PyInit_<name>` module-init function.
- Calls from Python hit the **dispatcher** (`pybind11.h`), which resolves overloads.
- `type_caster<T>` (`cast.h`) converts each argument and the return value.
- Bound classes and live instances are tracked in `internals` (`detail/internals.h`).

## Core Concepts You Must Know

- **`type_caster<T>`** — converts C++ ↔ Python (`load` = Py→C++, `cast` = C++→Py). → CONCEPTS.md
- **`internals` registry** — one shared, ABI-tagged map of bound types/instances. → CONCEPTS.md
- **`handle` vs `object`** — borrowed vs owning Python references. → CONCEPTS.md
- **The GIL** — hold it whenever you touch a Python object. → CONCEPTS.md

## Where to Look for What

| Task | Look in |
|---|---|
| Public API (def, class_, module_) | `include/pybind11/pybind11.h` |
| Type conversion | `include/pybind11/cast.h` |
| Reference semantics / Python wrappers | `include/pybind11/pytypes.h` |
| Bound-type registry | `include/pybind11/detail/internals.h` |
| GIL scopes | `include/pybind11/gil.h` |
| CMake helpers | `tools/pybind11NewTools.cmake` |

## Build / Test / Run (CMake)

```
$ cmake -S . -B build -DPYBIND11_TEST=ON     # configure
$ cmake --build build -j                      # build the test modules
$ python3 -m pytest tests/test_methods_and_attributes.py -v   # one test
```

Full steps, consumer CMakeLists, and error strings: `HOW-TO.md`.

## Project Conventions That Aren't Obvious

- **Header-only:** edits take effect only after the *consumer* recompiles.
- **GIL required:** never touch a `PyObject` without the GIL.
- **References:** use `reinterpret_borrow` / `reinterpret_steal`; do not hand-roll
  refcounts.
- **RTTI / visibility:** bound types are keyed by `std::type_index`; keep symbol
  visibility consistent across translation units.
- **CMake, not make:** use `pybind11_add_module` to build extension targets.

## Pointers to Detailed Docs

- **Knowledge-base entry for other skills** → `INDEX.md`
- **Common tasks (CMake)** → `HOW-TO.md`
- **Structure** → `OVERVIEW.md`
- **Concepts (deep dives)** → `CONCEPTS.md`
- **Flows** → `FLOWS.md`

## Behavioral Reminders

1. Code is truth; when code and these notes disagree, the code wins.
2. Tag every claim ✓ / ◐ / ? — here, treat everything as ◐ until you re-verify.
3. Cite `file → symbol`, not line numbers.

---

_Illustrative reference instance. Last revised: example — set a real commit before use._
