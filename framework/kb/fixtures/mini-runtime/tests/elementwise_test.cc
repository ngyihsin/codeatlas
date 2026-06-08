// Tiny gtest-style fixture exercising the mini-runtime ops, so the L1 tests index
// (kb.l1 extract_tests) has a deterministic symbol->test link to resolve.
#include "gtest/gtest.h"

TEST(ElementwiseTest, AddClampsToRange) {
  // references AddCompute + the Add op so the tests index links them here
  EXPECT_EQ(AddCompute(2, 3), 5);
}

TEST(ElementwiseTest, AbsIsNonNegative) {
  EXPECT_GE(AbsCompute(-4), 0);
}
