// Fixture: CPU operator kernels (ONNX Runtime-style registration macros).
#include "framework.h"

namespace onnxruntime {

// A plain helper function (for symbol/edge extraction).
static int clamp_index(int i, int n) {
  if (i < 0) return 0;
  return i < n ? i : n - 1;
}

Status AbsCompute(OpKernelContext* ctx) {
  return ElementwiseUnary(ctx, clamp_index);
}

Status AddCompute(OpKernelContext* ctx) {
  return ElementwiseBinary(ctx);
}

// Registration macros — these are what ops.jsonl must capture.
ONNX_CPU_OPERATOR_KERNEL(Abs, 6, KernelDefBuilder().TypeConstraint("T", float), AbsCompute);

ONNX_OPERATOR_KERNEL_EX(Add, kOnnxDomain, 14, kCpuExecutionProvider,
                        KernelDefBuilder().TypeConstraint("T", float), AddCompute);

}  // namespace onnxruntime
