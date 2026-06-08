// Fixture: ExecuTorch custom kernel registration.
#include <executorch/runtime/kernel/kernel_includes.h>
namespace my_ns {
Tensor& my_add_out(const Tensor& a, const Tensor& b, Tensor& out) { return out; }
}  // namespace my_ns
EXECUTORCH_LIBRARY(my_ns, "my_add.out", my_ns::my_add_out);
