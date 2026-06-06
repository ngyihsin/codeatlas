# APIs & Interfaces — pybind11

**Doc type:** reference (interface surface + feature map)
**Audience:** a developer learning what pybind11 exposes and what it is built on
**You are assumed to know:** C++ and that Python objects are `PyObject*`
**Before you begin:** read `OVERVIEW.md`
**Owner:** _(example instance — unowned)_
**Last verified against commit:** 6079989 (pybind11 3.1.0)   **Status:** ◐ Read-only
**Last verified date:** 2026-06-06

> Illustrative reference instance. Anchors are `file → symbol`; re-verify before use.
> pybind11 is unusual: its *provided* API is the binding DSL, and its single most
> important *consumed* interface is the CPython C-API — pybind11 is essentially a C++
> adapter over it. (Being header-only, it has no separate process entry point, so its
> public API *is* its entry-point list — `OVERVIEW.md` → Entry Points points here.)

## Provided API Surface (what pybind11 exposes)

| API / Symbol | Kind | Anchor | Stability | Entry point? | Purpose |
|---|---|---|---|---|---|
| `PYBIND11_MODULE(name, m)` | macro | `include/pybind11/detail/common.h` (search `"define PYBIND11_MODULE"`) | public | **yes** | Defines the module; expands to CPython `PyInit_<name>` |
| `module_::def(name, fn, …)` | method | `include/pybind11/pybind11.h` (search `"class module_"`) | public | **yes** → FLOWS "Calling a Bound C++ Function from Python" | Bind a C++ function as a Python callable |
| `class_<T>(m, "Name")` | template | `include/pybind11/pybind11.h` (search `"class class_"`) | public | yes | Bind a C++ class as a Python type |
| `PYBIND11_TYPE_CASTER(T, name)` | macro | `include/pybind11/cast.h` (search `"PYBIND11_TYPE_CASTER"`) | public | no | Declare a custom type conversion |
| `pybind11_add_module(target …)` | CMake function | `tools/pybind11NewTools.cmake` (search `"function(pybind11_add_module"`) | public | yes (build entry) | Build a Python extension target |

## Consumed Interfaces (libraries & internal modules)

The slice of each dependency — and each major internal module boundary — that the code
calls directly. Not exhaustive: only directly-used interfaces.

| Library / Module | Interface used (the subset) | Wrapped / adapted at | Why / for what |
|---|---|---|---|
| **CPython C-API** | `PyObject`, refcounting (`Py_INCREF`/`Py_DECREF`), the GIL (`PyGILState_Ensure`), type creation (`PyType_FromSpec`), the call protocol (`PyCFunction`/`tp_call`) | `include/pybind11/pytypes.h` (handles/refs), `include/pybind11/gil.h` (GIL), `include/pybind11/detail/class.h → make_new_python_type` (type creation), `include/pybind11/detail/type_caster_base.h` (cast/instance registration) | Everything — pybind11 is an adapter over the CPython C-API |
| CMake (build system) | targets, `find_package`, suffix/flags | `tools/pybind11NewTools.cmake`, `tools/pybind11Common.cmake` | Building extension modules portably |
| NumPy C-API (optional) | array buffer protocol | `include/pybind11/numpy.h` | Only if `numpy.h` is included — array casters |
| internal: dispatcher → conversion | `type_caster<T>`: `load` (Py→C++) / `cast` (C++→Py) | `include/pybind11/cast.h` — detailed in `CONCEPTS.md` → `type_caster` | The contract every type crossing the boundary implements |
| internal: value → holder | holder interface (`std::unique_ptr` / `shared_ptr` wrappers) | `include/pybind11/detail/struct_smart_holder.h` (and `value_and_holder.h`) | How a bound object owns its C++ instance |

## Feature → API Map

| Feature | Provided entry-point API | Key consumed interfaces | Flow |
|---|---|---|---|
| Expose a C++ function | `m.def(...)` | CPython `PyCFunction` / module API; `type_caster` per arg | → `FLOWS.md` → "Calling a Bound C++ Function from Python" |
| Expose a C++ class | `class_<T>` | CPython type creation (`make_new_python_type`); `internals` registry | — (not yet traced) |
| Convert a custom type | `PYBIND11_TYPE_CASTER` + `type_caster<T>` | CPython object protocol | see `CONCEPTS.md` → `type_caster` |
| Build the extension | `pybind11_add_module` | CMake + Python discovery | → `HOW-TO.md` |

## API Stability & Versioning

The binding API is header-only and broadly source-stable across minor versions. The
load-bearing constraint is **ABI**: modules sharing bound types must be built with a
compatible pybind11 version and compiler ABI, enforced by the tag baked into
`internals` (see `CONCEPTS.md` → `type_caster`). The CPython C-API it consumes is
itself versioned and changes across Python releases — a common source of build breaks.
