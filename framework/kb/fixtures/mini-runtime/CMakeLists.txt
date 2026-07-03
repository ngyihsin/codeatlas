# Minimal build file so kb.compdb can exercise the cmake-configure path.
# Configure-only: kb.compdb never compiles these sources.
cmake_minimum_required(VERSION 3.16)
project(mini_runtime CXX)
add_library(mini_runtime OBJECT
  cpu/elementwise_ops.cc
  et/custom_ops.cpp
  qnn/relu_builder.cc
  tests/elementwise_test.cc)
target_include_directories(mini_runtime PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
