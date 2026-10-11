set(NEOMATH_CORE_SOURCES
    src/exact/rational.cpp
    src/syntax/parser.cpp
    src/algebra/polynomial.cpp
    src/semantics/engine.cpp
)

add_library(neomath_mathcore OBJECT ${NEOMATH_CORE_SOURCES})
target_include_directories(neomath_mathcore PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_features(neomath_mathcore PUBLIC cxx_std_20)
set_target_properties(neomath_mathcore PROPERTIES POSITION_INDEPENDENT_CODE ON)

if(MSVC)
    target_compile_options(neomath_mathcore PRIVATE /W4 /permissive- /utf-8)
else()
    target_compile_options(neomath_mathcore PRIVATE -Wall -Wextra -Wpedantic)
endif()

pybind11_add_module(neomath_core
    bindings/module.cpp
    bindings/api.cpp
    bindings/converters.cpp
    bindings/exception_translation.cpp
)
target_link_libraries(neomath_core PRIVATE neomath_mathcore)
target_include_directories(neomath_core PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include ${CMAKE_CURRENT_SOURCE_DIR}/bindings)
install(TARGETS neomath_core LIBRARY DESTINATION . RUNTIME DESTINATION .)

if(NEOMATH_BUILD_TESTS)
    enable_testing()
    add_executable(neomath_core_tests tests/core_tests.cpp)
    target_link_libraries(neomath_core_tests PRIVATE neomath_mathcore)
    target_include_directories(neomath_core_tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/third_party)
    add_test(NAME neomath_core_tests COMMAND neomath_core_tests)
endif()
