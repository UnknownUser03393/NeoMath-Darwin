# NeoMath Software Verification Report

- Overall: **PASS**
- Scope: software only
- Git commit: `NO_COMMIT`
- Python: `3.14.3`
- C++ tests: 10
- Python tests: 31
- Differential: 10000 checked / 0 differences
- Native extension: 409088 bytes
- Release directory: 32794335 bytes
- Desktop UI interactions: 18 passed
- Submission ZIP: not in scope
- Secret scan: PASS

## Phases

- [PASS] C++ Format Check (0.070s)
- [PASS] C++ Configure (10.620s)
- [PASS] C++ Build (0.057s)
- [PASS] C++ Unit Tests (0.064s)
- [PASS] Python Extension Build (7.123s)
- [PASS] Python Tests (0.720s)
- [PASS] Golden Tests (0.657s)
- [PASS] Differential 10,000 (9.574s)
- [PASS] Benchmark (0.449s)
- [PASS] Ruff (0.122s)
- [PASS] Type Check (0.260s)
- [PASS] Secret Scan (0.324s)
- [PASS] PyInstaller + Desktop UI Smoke (16.343s)

## Known limitations

- Exact Rational arithmetic uses checked int64 storage (63-bit positive magnitude).
- Quadratic equations return exact rational roots only; irrational roots are Unverified.
- Replay caching is bounded and process-local; a restart or unmatched prefix falls back to full recomputation.
- Stop is best-effort at operation boundaries; each core analysis also has a 500 ms limit.
- V1 supports one real variable (x), not multivariable, trigonometric, logarithmic, or calculus input.
