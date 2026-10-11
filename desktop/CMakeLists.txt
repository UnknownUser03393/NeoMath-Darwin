cmake_minimum_required(VERSION 3.20)
project(NeoMath VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(NEOMATH_BUILD_TESTS "Build standalone C++ tests" ON)
include(CTest)

find_package(Python COMPONENTS Interpreter Development.Module REQUIRED)
find_package(pybind11 CONFIG REQUIRED)

add_subdirectory(cpp)
