#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
BUILD=$(mktemp -d /tmp/neomath-native-tests.XXXXXX)
trap 'rm -rf "$BUILD"' EXIT
xcrun clang++ -std=c++20 -fobjc-arc -framework Foundation \
  -I "$ROOT/desktop/cpp/include" -I "$ROOT/iPad/NeoMathDarwin/Core" \
  "$ROOT/iPad/NeoMathDarwinTests/BridgeTests.mm" \
  "$ROOT/iPad/NeoMathDarwin/Core/MathCoreBridge.mm" \
  "$ROOT/desktop/cpp/src/exact/rational.cpp" \
  "$ROOT/desktop/cpp/src/syntax/parser.cpp" \
  "$ROOT/desktop/cpp/src/algebra/polynomial.cpp" \
  "$ROOT/desktop/cpp/src/semantics/engine.cpp" -o "$BUILD/bridge-tests"
"$BUILD/bridge-tests"
xcrun clang++ -std=c++20 -I "$ROOT/desktop/cpp/include" -I "$ROOT/desktop/cpp/third_party" \
  "$ROOT/desktop/cpp/tests/core_tests.cpp" \
  "$ROOT/desktop/cpp/src/exact/rational.cpp" \
  "$ROOT/desktop/cpp/src/syntax/parser.cpp" \
  "$ROOT/desktop/cpp/src/algebra/polynomial.cpp" \
  "$ROOT/desktop/cpp/src/semantics/engine.cpp" -o "$BUILD/core-tests"
"$BUILD/core-tests"
xcrun clang++ -std=c++20 -fobjc-arc -framework Foundation -dynamiclib \
  -I "$ROOT/desktop/cpp/include" \
  "$ROOT/iPad/NeoMathDarwin/Core/MathCoreBridge.mm" \
  "$ROOT/desktop/cpp/src/exact/rational.cpp" \
  "$ROOT/desktop/cpp/src/syntax/parser.cpp" \
  "$ROOT/desktop/cpp/src/algebra/polynomial.cpp" \
  "$ROOT/desktop/cpp/src/semantics/engine.cpp" -o "$BUILD/libMathCoreTest.dylib"
xcrun swiftc -parse-as-library -import-objc-header "$ROOT/iPad/NeoMathDarwin/Core/MathCoreBridge.h" \
  "$ROOT/iPad/NeoMathDarwin/MathDisplay.swift" \
  "$ROOT/iPad/NeoMathDarwin/BackendClient.swift" \
  "$ROOT/iPad/NeoMathDarwin/BackendTrace.swift" \
  "$ROOT/iPad/NeoMathDarwin/LiveSource.swift" \
  "$ROOT/iPad/NeoMathDarwin/Notebook.swift" \
  "$ROOT/iPad/NeoMathDarwin/DocumentTransfer.swift" \
  "$ROOT/iPad/NeoMathDarwinTests/DocumentTests.swift" \
  -L "$BUILD" -lMathCoreTest -o "$BUILD/document-tests"
"$BUILD/document-tests"
