cmake_minimum_required(VERSION 3.1)
project(AddEmptyBlocks)

# support C++14 features used by LLVM 10.0.0
set(CMAKE_CXX_STANDARD 14)
SET(CMAKE_CXX_FLAGS "-D__GLIBCXX_USE_CXX11_ABI=0 -fno-rtti")

find_package(LLVM REQUIRED CONFIG)
add_definitions(${LLVM_DEFINITIONS})
include_directories(${LLVM_INCLUDE_DIRS})
link_directories(${LLVM_LIBRARY_DIRS})

add_subdirectory(addEmptyBlocks)  # Use your pass name here.
