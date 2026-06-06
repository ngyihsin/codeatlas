# How-To: Common Tasks — pybind11 (CMake)

**Doc type:** how-to (procedural)
**Audience:** a new hire building and testing pybind11, or consuming it via CMake
**You are assumed to know:** a C++ toolchain, a Python with dev headers, CMake basics
**Before you begin:** a clean checkout of `pybind/pybind11`; CMake ≥ 3.15; a C++11
compiler; Python (with development headers) and `pytest`
**Owner:** _(example instance — unowned)_
**Last verified against commit:** 6079989 (pybind11 3.1.0)   **Status:** ◐ Read-only

> Procedural steps only — for *why*, see `CONCEPTS.md`. This codebase is **CMake**, not
> `make`. Confirm commands on your checkout; promote to `✓` once you run them.

## Prerequisites: One-Time Setup

| Tool | Version | Check |
|---|---|---|
| CMake | 3.15+ | `cmake --version` |
| C++ compiler | C++11+ (gcc/clang/MSVC) | `c++ --version` |
| Python (with headers) | 3.x + dev package | `python3 -c "import sysconfig; print(sysconfig.get_path('include'))"` |
| pytest | recent | `python3 -m pytest --version` |

On Debian/Ubuntu: `apt-get install cmake g++ python3-dev python3-pytest`.

## Task 1: Configure and Build (the tests)

pybind11 is header-only, so "build" means building its **test extension modules**.

```
$ cmake -S . -B build -DPYBIND11_TEST=ON
# Expected (last lines): -- Configuring done / -- Generating done / -- Build files written to: build

$ cmake --build build -j
# Expected: compiles tests/*.cpp into pybind11_tests<suffix>.so under build/tests/
```

- **Time:** the first configure is quick; compiling all test modules takes a few
  minutes (heavy templates).
- **Common failure:** `Could NOT find Python (missing: Python_INCLUDE_DIRS ...)` →
  install the Python dev headers (`python3-dev`) or pass
  `-DPython_EXECUTABLE=$(which python3)`.

## Task 2: "Run" — Build and Import a Module

The real use of pybind11 is consuming it from another CMake project:

```cmake
# CMakeLists.txt of a consumer
cmake_minimum_required(VERSION 3.15)
project(example LANGUAGES CXX)
find_package(pybind11 CONFIG REQUIRED)      # or add_subdirectory(extern/pybind11)
pybind11_add_module(example example.cpp)    # builds example<suffix>.so
```

```cpp
// example.cpp
#include <pybind11/pybind11.h>
int add(int a, int b) { return a + b; }
PYBIND11_MODULE(example, m) { m.def("add", &add); }
```

```
$ cmake -S . -B build && cmake --build build
$ cd build && python3 -c "import example; print(example.add(2, 3))"
# Expected: 5
```

- **Common failure:** `ImportError: dynamic module does not define module export
  function (PyInit_example)` → the module name in `PYBIND11_MODULE(example, …)` must
  match the importable name and the compiled file name.

## Task 3: Run a Single Test

```
$ python3 -m pytest tests/test_methods_and_attributes.py -k "static" -v
# Expected: a short pass list ending in "passed"
```

- **Note:** the test modules must be built first (Task 1); pytest imports them from
  `build/tests/`. Run pytest with that on `PYTHONPATH`, or use the CMake `pytest`
  target: `cmake --build build --target pytest`.
- **Common failure:** `ModuleNotFoundError: No module named 'pybind11_tests'` → you
  did not build the tests, or `PYTHONPATH` does not include `build/tests`.

## Task 4: Make and Land a One-Line Change

1. Edit an error message: `include/pybind11/detail/type_caster_base.h` (search the
   "incompatible function arguments" message) or a caster in `cast.h`. Use a stable
   anchor, not a line number.
2. Rebuild the tests: `cmake --build build -j`
3. Run the affected test: `python3 -m pytest tests/test_builtin_casters.py -v`
4. Submit: push a branch and open a PR on GitHub. pybind11 expects the test suite to
   pass on CI across compilers and Python versions.

- **Common failure:** your header edit "has no effect" → you edited a header but did
  not rebuild the test module that includes it; templates are recompiled per
  consumer, so rebuild.

## Task 5: Debug

```
# Build with debug info and no optimization:
$ cmake -S . -B build-dbg -DPYBIND11_TEST=ON -DCMAKE_BUILD_TYPE=Debug
$ cmake --build build-dbg -j
$ gdb --args python3 -m pytest tests/test_methods_and_attributes.py
```

- **Most useful for a newcomer:** put a breakpoint in the dispatcher
  (`pybind11.h`, search `"dispatcher"`) to watch overload resolution.
- **Common failure:** segfault with no Python traceback → almost always a **GIL** or
  **reference-count** mistake; see the invariants in `INDEX.md`.

## When a Command Here Stops Working

CMake options and header layout drift between versions. If a step fails on a clean
checkout and is not listed above, it is stale — fix it and update
`Last verified against commit:`.
