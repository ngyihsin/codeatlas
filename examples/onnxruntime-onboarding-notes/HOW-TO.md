# How-To: Common Tasks — ONNX Runtime

**Doc type:** how-to (procedural)
**Audience:** a new hire running, extending, or building ONNX Runtime
**You are assumed to know:** Python; for source builds, CMake + a C++ toolchain
**Before you begin:** Python 3.x; for builds, the ORT build prerequisites
**Owner:** _(example instance — unowned)_
**Verified by running (2026-06-06):** Tasks 1–2 executed with `onnxruntime` 1.26.0 (pip). The
from-source build (Task 4) is **documented but not run here** (heavy) → `◐`.

> Procedural steps only — for *why*, see `CONCEPTS.md`.

## Task 1: Install + run an inference (verified ✓)

```
$ pip install onnxruntime onnx numpy
$ python3 - <<'PY'
import onnxruntime as ort, onnx, numpy as np
from onnx import helper, TensorProto
g = helper.make_graph(
    [helper.make_node("Add", ["A","B"], ["C"])], "g",
    [helper.make_tensor_value_info("A", TensorProto.FLOAT, [2]),
     helper.make_tensor_value_info("B", TensorProto.FLOAT, [2])],
    [helper.make_tensor_value_info("C", TensorProto.FLOAT, [2])])
m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 17)])
s = ort.InferenceSession(m.SerializeToString(), providers=["CPUExecutionProvider"])
print(s.run(["C"], {"A": np.array([2,3],"f4"), "B": np.array([4,5],"f4")})[0])
PY
# Expected (verified): [6. 8.]
```

## Task 2: List available Execution Providers (verified ✓)

```
$ python3 -c "import onnxruntime as ort; print(ort.get_available_providers())"
# Expected (this env): ['AzureExecutionProvider', 'CPUExecutionProvider']
# (a GPU/NPU wheel adds e.g. 'CUDAExecutionProvider', 'QNNExecutionProvider')
```

- **Common failure:** you asked for `CUDAExecutionProvider` but the **CPU-only** wheel is
  installed → ORT silently falls back to CPU. Check `get_available_providers()` first.

## Task 3: Inspect optimization level

```
$ python3 - <<'PY'
import onnxruntime as ort
o = ort.SessionOptions()
o.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
print(o.graph_optimization_level)
PY
```

Levels map to the `GraphTransformer` passes (`DISABLE_ALL`/`ENABLE_BASIC`/`EXTENDED`/`ALL`).

## Task 4: Build from source (documented, not run here — ◐)

```
$ git clone --recursive https://github.com/microsoft/onnxruntime
$ cd onnxruntime && ./build.sh --config Release --build_shared_lib --parallel
# Heavy: pulls submodules, builds the C++ core + chosen EPs. Use --use_cuda / --use_qnn etc.
```

- This was **not executed** in this instance (large build). The pip wheel covers Tasks 1–3.

## Task 5: Add a custom operator (documented — ◐)

1. Implement an `OrtCustomOp` (with `CreateKernel` + `KernelCompute`) in a shared library.
2. Group ops into an `OrtCustomOpDomain`; load via `RegisterCustomOpsLibrary()`.
3. Reference: `onnxruntime.ai/docs/reference/operators/add-custom-op`.
- This is the **add-an-operator** axis (kernel registry); adding a *backend* is the
  `IExecutionProvider` axis — see `API.md` / `CONCEPTS.md`.

## When a Command Here Stops Working
Pin the `onnxruntime` version you verified against (here 1.26.0). EP availability depends on
the wheel/build; `get_available_providers()` is the source of truth.
