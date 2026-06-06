# How-To: Common Tasks — ExecuTorch

**Doc type:** how-to (procedural)
**Audience:** an engineer lowering/running a model, or extending ExecuTorch
**You are assumed to know:** PyTorch; for the runtime, CMake + C++
**Before you begin:** Python + PyTorch (heavy); for the runtime, the ExecuTorch build prereqs
**Owner:** _(example instance — unowned)_
**Status:** ◐ documented, **not run in this environment** (the `executorch` wheel pulls full
PyTorch). Steps below follow the official docs at `main @0d904b6bae60`; verify on your host.

> Procedural steps only — for *why*, see `CONCEPTS.md`.

## Task 1: Install the AOT toolchain (documented — ◐)
```
$ pip install executorch        # NOTE: pulls torch and is large; not executed here
$ python -c "import executorch; print(executorch.__version__)"   # expect 1.3.x
```

## Task 2: Lower a model to `.pte` (documented — ◐)
```python
import torch
from executorch.exir import to_edge
from torch.export import export

class M(torch.nn.Module):
    def forward(self, x): return x + x

ep = export(M(), (torch.ones(2),))
edge = to_edge(ep)
# Optional: delegate subgraphs to a backend, e.g. XNNPACK:
#   from executorch.backends.xnnpack.partition.xnnpack_partitioner import XnnpackPartitioner
#   edge = edge.to_backend(XnnpackPartitioner())
prog = edge.to_executorch()
with open("m.pte", "wb") as f:
    f.write(prog.buffer)
```
- **Common failure (per docs):** a partitioner tags a subgraph the backend can't compile →
  `to_backend` raises during lowering (no silent CPU fallback for delegated ops).

## Task 3: Run a `.pte` on the runtime (documented — ◐)
- Build the C++ runtime (CMake) and load `m.pte` via the executor; or use the Python runtime
  binding to `Method::execute`. See `runtime/executor/`.

## Task 4: Add an operator (kernel) (documented — ◐)
- Register a custom kernel with `EXECUTORCH_LIBRARY(op_name, "schema", fn)` or via a YAML
  entry processed by `gen_selected_ops`/`generate_bindings_for_kernels` (selective build).
- This is the **add-op** axis; adding a delegate is the `Partitioner`+`BackendInterface` axis.

## Task 5: Add a backend (delegate) (documented — ◐)
- AOT: implement a `Partitioner.partition()` + the backend's `preprocess(edge_program, specs)`.
- Runtime: implement `BackendInterface` (`is_available`/`init`/`execute`) and
  `register_backend`. See `backends/<name>/` for a template (e.g. `qualcomm` = QNN).

## When a Command Here Stops Working
ExecuTorch moves fast; pin the version you verify against. Because nothing here was executed in
this environment, treat all steps as `◐` until you run them on a host with PyTorch.
