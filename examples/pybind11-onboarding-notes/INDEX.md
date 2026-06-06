# Knowledge Base Index — pybind11 (Entry Point for Consuming Skills)

**Doc type:** reference (machine-readable routing + action contract)
**Audience:** an agent or skill here to do a task on pybind11; humans wanting the map
**Before you begin:** none
**Owner:** _(example instance — unowned)_
**Last verified against commit:** 6079989 (pybind11 3.1.0)   **Status:** ◐ Read-only
**Index schema:** v1 — column meanings stable within a major version

> Illustrative reference instance, **verified against `pybind11` @`6079989` (v3.1.0,
> 2026-06-06)**: anchors confirmed present, and a real module was **built and run** —
> `add(2,3)`→`5` and the TypeError branch reproduced (✓). Rows whose behavior was not
> executed (e.g. the test-suite commands, `PYBIND11_TYPE_CASTER`) stay `◐`. Re-verify
> before acting. To *build* these notes you would read `AGENT-warm-up.md`; this is the
> *consume* entry.

## Consumption Protocol (read before acting)

1. **Route by task** — jump to the matching recipe below.
2. **Trust gates:** act on `✓`; re-verify `◐` against current code before editing;
   **never act on `?`.** Here, treat all rows as `◐`.
3. **Re-verify before editing:** `git log <Last verified commit>..HEAD -- <path>`.
   Code wins over docs.
4. **Honor invariants** in the registry below — a violation crashes the interpreter
   even when tests look green.
5. **Write back** any correction, with updated provenance.

## Knowledge Map

### Concepts

| Concept | Anchor | Status | What breaks without it | Use when |
|---|---|---|---|---|
| `type_caster<T>` | `include/pybind11/cast.h` → `type_caster` (search `"class type_caster"`) | ◐ | You expect a value to cross C++/Python without conversion | Any binding, custom conversion, or TypeError |
| `internals` registry | `include/pybind11/detail/internals.h` → `internals` | ◐ | You assume per-module type tables; cross-module objects break | Bound-class lookup, ABI/identity issues |
| `handle` vs `object` | `include/pybind11/pytypes.h` → `handle` | ◐ | You leak or crash via wrong refcounting | Any code holding Python references |
| The GIL | `include/pybind11/gil.h` → `gil_scoped_acquire` | ◐ | Segfaults touching Python without the lock | Any code touching `PyObject`s |

→ Detail: `CONCEPTS.md`

### Flows

| Flow | Trigger | Error / early-exit branch | Status | Use when |
|---|---|---|---|---|
| Calling a Bound C++ Function from Python | Python calls a `m.def` function | `pybind11.h` → dispatcher (TypeError "incompatible function arguments") | ◐ | Debugging arg conversion or overload resolution |

→ Detail: `FLOWS.md`

### Key Data Structures

| Structure | Anchor | Invariants documented in |
|---|---|---|
| `internals` | `include/pybind11/detail/internals.h` → `internals` | `CONCEPTS.md` → `type_caster` |
| `handle` / `object` | `include/pybind11/pytypes.h` → `handle` | `CONCEPTS.md` → `handle` vs `object` |

### APIs, Entry Points & Interfaces

The provided API surface (the binding DSL: `PYBIND11_MODULE`, `def`, `class_`, the
`pybind11_add_module` CMake function) and the consumed interfaces (dominated by the
CPython C-API) and feature→API map are authored in **`API.md`** — the single source of
truth. Being header-only, pybind11's API *is* its entry-point list.

### Task → Location Map

| To change… | Look in | Owner |
|---|---|---|
| The public binding API | `include/pybind11/pybind11.h` | — |
| How a type converts | `include/pybind11/cast.h` (or a `type_caster` specialization) | — |
| Reference / Python-object wrappers | `include/pybind11/pytypes.h` | — |
| The bound-type registry / ABI | `include/pybind11/detail/internals.h` | — |
| CMake build behavior | `tools/pybind11NewTools.cmake`, `tools/pybind11Common.cmake` | — |

### Invariants / Must-Not-Break Registry

| Invariant (what must stay true) | Enforced / relied on at | Explained in | Status |
|---|---|---|---|
| Hold the GIL before touching any `PyObject` (incl. every caster op) | `include/pybind11/gil.h` | `CONCEPTS.md` → `type_caster` | ◐ |
| `handle` = borrowed ref, `object` = owning ref; use `reinterpret_borrow`/`steal` | `include/pybind11/pytypes.h` → `handle`,`object` | `CONCEPTS.md` → `handle` vs `object` | ◐ |
| One ABI-tagged `internals` per interpreter; don't bypass `get_internals()` | `include/pybind11/detail/internals.h` → `get_internals` | `CONCEPTS.md` → `type_caster` | ◐ |
| Bound types are keyed by `std::type_index`; keep symbol visibility consistent | `include/pybind11/detail/type_caster_base.h` | `OVERVIEW.md` notes | ◐ |
| `type_caster::load` returns `bool` so overload resolution can reject a candidate | `include/pybind11/cast.h` → `type_caster::load` | `FLOWS.md` | ◐ |

### Commands (CMake)

| Need | Command | Verified |
|---|---|---|
| Configure | `cmake -S . -B build -DPYBIND11_TEST=ON` | ◐ |
| Build tests | `cmake --build build -j` | ◐ |
| Run one test | `python3 -m pytest tests/test_methods_and_attributes.py -v` | ◐ |

→ Full procedures, consumer `CMakeLists.txt`, and failure strings: `HOW-TO.md`

## Consumer Contract

### Schema

Anchors are `path → Symbol (search "…")` — never bare line numbers. Status is exactly
one of `✓ / ◐ / ?`. Every Concepts/Flows row links to a section that exists. Invariants
rows are rule + enforcing anchor + explaining doc + status.

### Safety Boundaries

| Action | Rule |
|---|---|
| Read | Always allowed. |
| Edit code | Only on `✓` or re-verified `◐`; never on `?`. |
| Break an invariant | Escalate as a design change with the anchor as a named risk. |
| Before editing | Re-verify the anchor against the recorded commit; code wins. |
| After editing | Write back: update the cited doc and its provenance. |
| Push / PR | Not granted by this KB; follow the host project's rules. |

## Task Recipes

Each recipe = read → extract → guardrails → write back. Worked against this instance.

### Recipe: Fix an Issue / Bug (example: "binding crashes on return")

1. **Read:** `FLOWS.md` (the cast-back step 6); `CONCEPTS.md → type_caster` and
   `handle`/`object`; the GIL and reference invariants.
2. **Extract:** the failing caster anchor; the ownership rule for the return value
   (`return_value_policy`); whether the GIL is held.
3. **Guardrails:** never touch `PyObject`s without the GIL; use
   `reinterpret_borrow`/`steal`; keep every registry invariant.
4. **Write back:** if the crash reveals a doc error, fix it + provenance.

### Recipe: Develop a Feature (example: support a new C++ type)

1. **Read:** `CONCEPTS.md → type_caster` (the custom-caster API example); a sibling
   caster in `cast.h` or `stl.h`.
2. **Extract:** the `load`/`cast` contract; `PYBIND11_TYPE_CASTER`; the GIL/ref rules.
3. **Guardrails:** `load` must return `bool`; `cast` must return a correctly-owned
   `handle`; hold the GIL.
4. **Write back:** add a Concept entry and an INDEX row for the new caster.

### Recipe: Write a Design Document (example: change the internals/ABI scheme)

1. **Read:** `CONCEPTS.md → type_caster` (the `internals` data structure); every
   invariants-registry row touching ABI and the registry.
2. **Extract and cite:** the single-shared-registry invariant and the cross-module
   interop it enables; the ABI-tag mechanism.
3. **Guardrails:** the shared-registry/ABI invariant is load-bearing — a design that
   changes it is a **migration** affecting every extension module; call it out with
   the anchor as a named risk.
4. **Write back:** link the design from `CONCEPTS.md → type_caster`.

### Recipe: Review · Incident/Debug · Generate Tests · Refactor · Explain · Impact Analysis

Same structure as the master `INDEX.md` in the template. For pybind11 the load-bearing
inputs are always the **GIL** and **reference-ownership** invariants, plus the
**ABI/internals** rule. Example impact analysis: a change to `type_caster<T>::load`
reaches *every* bound function call (all argument conversion flows through it) — blast
radius is the entire binding surface; treat with maximum care.

## How This Index Stays True

Derived from `CONCEPTS.md`, `FLOWS.md`, and `HOW-TO.md`; refresh when they change.
Run `../../framework/tools/check-doc-drift.sh` (pointed at a pybind11 checkout) to find
which rows cite changed code. If a row points at a section or symbol that no longer
exists (headers move between versions), the index has drifted — fix it before a skill
acts on it.
