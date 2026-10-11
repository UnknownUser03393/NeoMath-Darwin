# xdlt Draft 0.3 implementation plan

## Scope

Implement the first usable Draft 0.3 `.hw` parser surface inside the existing desktop Python package, without breaking the current `edlatex` compatibility path.

The implementation target is Phase A plus a small Semantic IR bridge:

- lossless block parser for headings, paragraphs, comments, display math, fenced code, and universal `#kind:id(args) { ... }` semantic blocks;
- same-indent semantic block closure, including RawBody brace safety for `#exec` and `#raw`;
- named display equations such as `$$ #eq:a(numbered=true)`;
- source ranges and diagnostics for malformed or unterminated constructs;
- structured output suitable for later Semantic IR, LSP, and renderer work;
- bridge/export entry point and focused pytest coverage.

## Files to add or change

- Add `desktop/src/neomath/xdlt/` package:
  - `nodes.py`: dataclasses for CST/AST-like nodes, semantic headers, diagnostics, source ranges, body modes.
  - `parser.py`: line-oriented parser with a block stack and body-mode handling.
  - `semantic.py`: minimal lowering to Draft 0.3-shaped document/semantic entities and duplicate ID diagnostics.
  - `__init__.py`: public API.
- Update `desktop/src/neomath/bridge.py` with `parseXdltDocument(payload)` returning nodes, diagnostics, and minimal semantic IR.
- Add `desktop/tests/python/test_xdlt_parser.py` covering the conformance cases from the draft that fit this milestone.
- Optionally update `desktop/src/neomath/edlatex/__init__.py` only if a public re-export is useful; otherwise keep old `parse_content_edl` untouched.

## Key implementation details

- Use a line scanner, not a regex-only parser. Regex may be used for small token recognizers, but the parser state is line/body-mode driven.
- At line start, distinguish headings from semantic candidates exactly as the spec says: `#` plus whitespace is heading; `#` plus identifier start is semantic syntax.
- Parse semantic headers into `kind`, optional `id`, optional argument source, `canonicalId`, and body mode from a core registry.
- Close semantic blocks only when `indent(line) == openerIndent` and `trim(line) == "}"`.
- For RawBody blocks, do not parse nested `.hw`; preserve raw body and expose a deindented body field.
- For DocumentBody blocks, recursively parse nested `.hw` content.
- Preserve unknown extension blocks as explicit unknown semantic nodes instead of dropping them.
- Treat malformed blocks as recoverable nodes with diagnostics, preserving source.

## Verification

Run from `desktop/`:

```bat
python -m pytest tests/python/test_xdlt_parser.py tests/python/test_edlatex_model.py
```

If the native extension is already built and broader tests are practical, run:

```bat
python -m pytest tests/python
```
