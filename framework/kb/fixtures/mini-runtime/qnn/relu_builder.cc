// Fixture: QNN op builder registration (Qualcomm-style macro).
#include "qnn_builder.h"
namespace qnn {
class ReluOpBuilder : public OpBuilder {
  Status Build(QnnModel* model) override { return model->AddRelu(); }
};
REGISTER_QNN_OP_BUILDER(Relu, ReluOpBuilder);
}  // namespace qnn
