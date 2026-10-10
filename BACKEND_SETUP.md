# Bundled NeoMath backend

`backend/` is a source snapshot of the current `D:\Development\NeoMath\desktop` backend. It includes the Python HTTP bridge, SymPy CAS worker, C++ MathCore and bindings, Writing/XDLT/edLatex support, packaged UI assets, and backend regression tests. Build products, Python caches, local settings and user documents are excluded.

## macOS / iOS Simulator

Run these commands from the NeoMath-Darwin repository root. Use Python 3.11 or newer; the native extension requires a C++20 compiler and CMake 3.20 or newer.

```sh
xcode-select --install # only if Command Line Tools are not installed
python3 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ./backend
python -m neomath --serve --host 127.0.0.1 --port 8765
```

`pip install ./backend` builds `neomath_core` for the Mac's Python/architecture and installs the Python package plus `sympy>=1.14`. Do not copy a Windows `.pyd` to macOS. CMake and pybind11 are supplied by the isolated Python build environment.

Use `http://127.0.0.1:8765/api` as the native app API base when the iOS Simulator runs on the same Mac. Confirm the server with:

```sh
curl http://127.0.0.1:8765/api/health
curl -X POST http://127.0.0.1:8765/api/runTrace \
  -H 'Content-Type: application/json' \
  -d '{"engine":"auto","document":{"source":"x^2=2\nx=±sqrt(2)"}}'
```

The second response should select `sympy` and return the complete real solution set. Send `engine: "auto"` for notebook math requests (`parseDocument`, `analyzeDocument`, `runTrace`, `replay`, `getCompletions`, `executeTransformation`, `evaluateProbe`); `engine: "core"` forces C++ and `engine: "sympy"` forces CAS. The HTTP envelope is `{ok, result, error}`. Verification limitations remain explicit; a symbolic expression or calculus output is not a proof of a complete solution set.

For a physical iPhone, run the server with `--host 0.0.0.0` and use the Mac's LAN address instead. Native HTTP access also depends on the app's local-network/transport configuration. This snapshot has been validated on Windows; macOS builds and Simulator connectivity still require verification on the Mac.

## Regression checks

After installing the package, from the repository root:

```sh
python -m pip install pytest
PYTHONPATH=backend/src python -m pytest backend/tests tests/audit_math_semantics.py
```

The original backend overview is in `backend/README.md`. References there to the old `ui-mockups` development tree concern the upstream desktop UI; this repository's frontend is the React/Vite app at the repository root.
