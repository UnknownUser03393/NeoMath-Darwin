# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

NeoMath is a math derivation debugger for students — C++20 MathCore + Python (pybind11) + React UI. It treats each line of math derivation as a runnable state: parse, compute domain/solution set, transform, verify. When adjacent steps are no longer equivalent, it produces a precise rational counterexample (Witness) instead of a red X.

The second subsystem is XDLT (`.hw` language): a semantic math-writing language with an incremental compiler (`parser → semantic → graph → verify → render → exec → cards → session`).

**Hard constraint**: C++ is the sole source of math truth. Python orchestrates; the UI renders C++ results and never duplicates solving logic. AI (OpenAI-compatible client, default provider DashScope Qwen) may only rephrase explanations and generate transformation candidates — it never modifies MathState directly.

## Build, test, lint commands

All commands assume Windows 10/11 x64 with VS C++ Build Tools. The project has three independent layers.

### C++ MathCore (`desktop/cpp/`)

Configure, build, and test via CMake from `desktop/`:

```bat
cmake -S . -B build/verify --fresh -G Ninja -DCMAKE_BUILD_TYPE=Release -DNEOMATH_BUILD_TESTS=ON
cmake --build build/verify --parallel
ctest --test-dir build/verify --output-on-failure
```

C++ tests use Catch2 (vendored single-header in `cpp/third_party/catch2/`). 12 test cases covering rational arithmetic, parsing, polynomials, demo traces, transforms, solver, limits, and replay.

### Python (`desktop/`)

First-time setup:

```bat
cd desktop
bootstrap.bat          # creates .venv, pip install -e ".[dev]" (builds neomath_core.pyd)
```

Run the app:

```bat
run.bat                                             # GUI via pywebview
python run.py --demo lost-root --headless            # headless demo
python -m neomath --serve                            # HTTP API server on 127.0.0.1:8765
python -m neomath --ui notebook                      # notebook UI
```

Run tests:

```bat
python -m pytest -q                                  # all 258 tests
python -m pytest tests/python/test_xdlt_parser.py -q # single file
python -m pytest tests/python/test_xdlt_parser.py::TestName -q  # single test
python -m pytest tests/golden -q                     # golden solution-set tests (14 cases)
```

Lint and type-check:

```bat
python -m ruff check src tests tools scripts
python -m mypy src/neomath
```

Differential validation (10,000 SymPy oracle comparisons):

```bat
python tools/differential/run_differential.py --cases 10000 --seed 20260724
```

Benchmarks:

```bat
python tools/benchmark/run_benchmarks.py
```

Full verification pipeline (C++ format → build → ctest → extension build → pytest → golden → differential → benchmark → ruff → mypy → secret scan → release build):

```bat
scripts\verify_all.bat
```

### React UI (`ui-mockups/`)

Requires Node >= 22.13.

```bash
npm ci                   # install deps (pnpm-lock.yaml also present)
npm run build:spa        # AOT build into ../desktop/src/neomath/ui/notebook/
npm run dev:spa          # dev server on :5174, proxies /api → 127.0.0.1:8765
npm run lint             # ESLint
npm test                 # node:test (24 tests: sessions, patches, HTML, sidebar)
```

For dev with hot reload: start `python -m neomath --serve` in one terminal, `npm run dev:spa` in another.

## Architecture

### Three-layer stack (strict responsibility discipline)

```
React UI (ui-mockups/)  ←  AOT SPA, render-only, no math logic
    │  HTTP 127.0.0.1:8765 (/api/*)
Python (desktop/src/neomath/)  ←  orchestration, persistence, XDLT compiler, AI facade
    │  pybind11 (CoreMathRuntime releases GIL during compute)
C++ MathCore (desktop/cpp/)  ←  sole source of math truth
```

### C++ MathCore (`desktop/cpp/`)

Four source modules, all under `include/neomath/` and `src/`:

| Module | Header | Responsibility |
|---|---|---|
| `exact/rational` | `rational.hpp` | `Rational` (int64, checked, denominator > 0, 0 = 0/1); `pow`, `exactSquareRoot` |
| `syntax/ast` | `ast.hpp` | Immutable `std::variant` AST (`Expression`), `Predicate`, `ParseError`, `ExecutionLimits` |
| `syntax/parser` | — | Recursive-descent parser with implicit multiplication and `sqrt(...)` |
| `algebra/polynomial` | `polynomial.hpp` | Sparse exact-coefficient `Polynomial`, `RationalFunction`, `rationalRoots` (degree ≤ 2) |
| `semantics/engine` | `engine.hpp` | `MathState`, `ExecutionTrace`, `SolutionSet`, `DomainSet`; trace, replay, probe, transforms |

The `bindings/` directory is pure glue: `module.cpp` (PYBIND11_MODULE), `api.cpp` (8 exported functions with GIL release + timing + trace cache), `converters.cpp` (C++ → Python dict marshalling), `exception_translation.cpp`.

The 8 exported API methods: `parse_document`, `analyze_document`, `run_trace`, `replay`, `get_completions`, `execute_transformation`, `evaluate_probe`, `get_capabilities`.

### Python layer (`desktop/src/neomath/`)

Key modules at the top level:

- `bridge.py` — `NeoMathCoreClient`: the **only** module allowed to import `neomath_core`. Facade over all 8 C++ API methods.
- `server.py` — `ThreadingHTTPServer` on `127.0.0.1:8765`, `POST /api/<method>` for each `EXPOSED_METHODS` entry + `GET /api/health`. Serves AOT static UI from `ui/notebook/`.
- `app.py` — `NeoMathApplication`: pywebview lifecycle, multiprocessing, headless mode, demo selection.
- `notebook_workspace.py`, `xdlt_workspace.py` — workspace managers for the two UI tabs.

Subpackages:

- `ai/` — OpenAI-compatible client (`openai_client.py`), fallback templates, schemas. AI only touches explanation text and transformation **candidates**.
- `edlatex/` — Document model, context/scoping, derivation rules/graph, multi-backend render (HTML/LaTeX/JSON).
- `xdlt/` — The `.hw` compiler pipeline:
  - `math/` — lexer, parser, AST, semantic lower for math sub-language
  - `parser.py`, `semantic.py`, `resolve.py` — top-level `.hw` parsing and reference resolution
  - `graph/` — dependency graph with node-level hashing and incremental invalidation
  - `verification/` — SymPy-based assertion verification (four states: valid / valid-with-conditions / invalid / unknown)
  - `execution/` — Python runner with result caching and provenance
  - `cards/` — Knowledge card registry, binding, conditions
  - `render/` — HTML build, numbering, diagnostics, incremental diff/patch
  - `session/` — `CompilationSession`: edit → incremental recompile → patch-level HTML diff
  - `sel/` — Structured Expression Language for assertions and value environment
  - `values/` — Value environment, conversion, resolution

### React UI (`ui-mockups/`)

Two entry points sharing the same `components/` and `lib/`:

1. **SPA** (`spa/`) — AOT build target. `spa/index.html` sets `__NEOMATH_EMBEDDED__` and `__NEOMATH_CORE_URL__=""` so the UI talks to same-origin Python server.
2. **Next.js** (`app/`) — Full-stack path (vinext adapter, Cloudflare Workers).

Key directories:

- `components/notebook/` — `NotebookCanvas`, `NotebookCell`, `MathCell`, `MathCellEditor`, `CompletionBar`, `TransformPalette`
- `components/xdlt/` — `XdltWorkspace`, `XdltDebugPanel`
- `components/outputs/` — `DiagnosticOutput`, `EquivalenceOutput`, `MathOutput`, `WitnessOutput`
- `lib/runtime/` — `CoreMathRuntime.ts` (HTTP bridge), `MockMathRuntime.ts` (offline demo fallback), `FallbackMathRuntime` (auto-detects backend availability)
- `lib/xdlt/` — `bridge.ts` (XDLT session HTTP client), `session.ts`, `patchRuntime.ts`

The runtime bridge detects backend availability via `GET /api/health`. When the Python backend is unreachable, it falls back to `MockMathRuntime` so the four built-in demos still work.

### Data flow for a notebook run

1. UI calls `POST /api/runTrace` with document text
2. Python `NeoMathCoreClient.run_trace()` calls C++ `run_trace` via pybind11 (GIL released)
3. C++ returns `ExecutionTrace` (per-step `MathState` with solution sets, domains, diagnostics)
4. Python converts to JSON response
5. UI renders `MathOutput`, `EquivalenceOutput`, `DiagnosticOutput`, `WitnessOutput` per cell

Replay: UI sends changed step index + updated text → C++ reuses cached states for unchanged prefix (`cacheHits`), re-computes only affected suffix.

## Key invariants (enforced in C++, not convention)

- Rational numbers: denominator always positive, auto-reduced, zero = `0/1`; all operations checked for overflow
- No floating-point in equivalence/root/solution-set decisions
- Equation state carries both domain and solution set; canceling denominators does not silently restore excluded points
- Adjacent steps are equivalent only when both solution set AND domain match; conditional equivalence is annotated separately
- First provable divergence is Root Fault; dependent steps are Tainted
- Probe/Witness values are exact rationals from solution-set or domain-set differences
- Scope: single-variable real algebra, degree ≤ 2, rational coefficients. Beyond capability → `Unverified` (never faked)

## Tests by layer

| Layer | Framework | Count | Key files |
|---|---|---|---|
| C++ | Catch2 | 12 cases | `cpp/tests/core_tests.cpp` |
| Python unit | pytest | 258 tests | `tests/python/` (16 files), `tests/golden/`, `tests/integration/` |
| Python diff | custom | 10,000 cases | `tools/differential/run_differential.py` |
| UI | node:test | 24 tests | `ui-mockups/tests/*.test.mjs` |
