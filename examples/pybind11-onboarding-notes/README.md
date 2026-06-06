# Worked Reference Instance — pybind11 Onboarding Notes

A second **filled, end-to-end L3 example** of the `docforge-onboard` template — this
one for a **C++ + Python codebase built with CMake**:
[pybind11](https://github.com/pybind/pybind11). Where the Redis instance shows a pure
C systems codebase, this one shows a **polyglot library**: a header-only C++ side, a
Python test/packaging side, and CMake glue tying them together.

> **Read this caveat first.** Anchors were **verified against `pybind/pybind11`
> @`6079989` (v3.1.0) on 2026-06-06**: every cited file and symbol was confirmed
> present. Behavioral claims (a flow's mechanism, an invariant) were **read, not run**,
> so they stay tagged `◐`. Anchors use `file → symbol (search "…")`, never line
> numbers. Two things moved in the 3.x line and are corrected here: `PYBIND11_MODULE`
> is defined in `detail/common.h` (not `pybind11.h`), and the smart-holder is the
> default (`detail/struct_smart_holder.h`). Re-verify against *your* checkout's commit
> before acting; this is the honesty discipline `STANDARD.md` requires.

## What's here

| File | Role | Demonstrates |
|---|---|---|
| `CLAUDE.md` | Auto-loaded lean index | The ≤200-line per-session boot context |
| `INDEX.md` | Entry point for consuming skills | Machine-readable map, invariants registry, task recipes |
| `OVERVIEW.md` | What pybind11 is + structural map | L3 reference for a **header-only + CMake** project |
| `CONCEPTS.md` | Type casters + the `internals` registry | L3 **data-structure** entry: fields, *why*, API usage |
| `FLOWS.md` | "Calling a Bound C++ Function from Python" | L3 **flow** across the C++/Python boundary |
| `HOW-TO.md` | Configure / build / test with **CMake** | L3 **how-to**: CMake commands, with error strings |
| `API.md` | Binding API + the CPython C-API it consumes | L3 **API/interface** surface — the consumed-interface case |

## Why pybind11 for the C++/Python/CMake example

- **Two languages on purpose.** The docs must explain the C++ side (templates, RTTI),
  the Python side (refcounting, the GIL), and how a value crosses between them. That
  is exactly what a polyglot codebase's onboarding notes must do.
- **CMake is first-class.** pybind11 ships CMake helpers (`pybind11_add_module`,
  `find_package(pybind11)`); the HOW-TO is genuinely CMake-driven, not `make`.
- **Header-only.** A good contrast to Redis: "where is the code" is `include/`, and
  "building" means building the *tests* or a *consumer*, not the library.
