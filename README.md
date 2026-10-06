# NeoMath Darwin

Darwin UI connected to the original Python HTTP bridge and C++ MathCore in `D:\Development\NeoMath`. No mock kernel is used by the app.

## Run locally

```powershell
npm run backend
# In a second terminal (reuse an existing Vite server if present):
npm run dev
```

Open `http://localhost:8443`. The backend command reuses a healthy original service on port 8765, or runs `python -m neomath --serve` from the original source tree. Python must already have the original `neomath_core` extension and dependencies installed. Override the source path with `scripts/start-backend.ps1 -NeoMathRoot <path>`.

Vite development and preview servers proxy `/api` to `http://127.0.0.1:8765`. Set `NEOMATH_BACKEND_URL` before starting Vite to change the proxy target. For a static deployment, configure the host to proxy `/api` to NeoMath, or build with `VITE_NEOMATH_API_URL=https://your-backend/api`. The original backend is a local desktop service; keep it bound to loopback unless a separate authenticated gateway is provided.

## Connected workflows

- Math renders with bundled KaTeX fonts/CSS throughout the canvas, steps, inspector, completion suggestions and live editor previews. The display converter supports nested fractions, roots, powers, sets and disjunctions without modifying MathCore source. XDLT MathML and opaque TeX also use KaTeX in the sandboxed preview.

- Original `.nm` workspace list and loading; new derivations; `.nm` / JSON import creates a new copy. Original XDLT workspace files are listed alongside notebooks, and new writing documents use `.xdlt`.
- Title, equation and text editing; queued autosave and explicit save using `saveNotebook`; original cell metadata is preserved.
- Live Preview is the default document view: one CodeMirror body renders inactive equations with KaTeX and reveals source where the cursor or selection enters. Prose renders in place with its `#` marker hidden until editing. Clear insertion cursors and clickable empty-expression slots help finish equations. Ctrl+Space opens a caret-anchored list of available transformations: arrows select, Enter inserts the next step and focuses it, Escape closes. Inline diagnostics name lost/gained roots, domain changes and syntax problems; valid steps have no traffic-light badges. The header contains view selection, Check, Inspect and More; Auto check, explicit save and cell editing are under More. Ctrl+Enter checks, Ctrl+S saves, Ctrl+Z / Ctrl+Shift+Z undo and redo. Editor history and scroll survive view switches. Existing multiline prose, cell metadata and transformation cells are retained; rendering and selection changes do not save or check math.
- Ink is stored per notebook in the optional `darwinInk` field; undo/redo changes are saved with the document. Existing prototype browser ink is left untouched.
- Auto check is enabled by default: opening or editing equations schedules analysis after 250 ms. IME composition pauses checks; rapid changes are coalesced, old requests are cancelled, stale replies are ignored. Manual Check and Ctrl+Enter remain available, and Auto check can be disabled.
- `parseDocument` provides syntax diagnostics and expected tokens. First analysis uses `runTrace`; later checks use `replay` from the earliest changed equation, preserving the unchanged prefix and reporting actual backend `cacheHits` and duration. Metadata, prose and ink edits do not recheck mathematics. Imported transformation prefixes are also reused.
- Semantic completions (Ctrl+Space), structured transformations, first-fault navigation, explanations with the original local/Qwen fallback, and `.nm` export are available. Mathematical truth continues to come from C++ MathCore.
- Automatic witnesses come from trace relations; manual probes call `evaluateProbe` on the selected derivation prefix.
- Settings reads original backend workspace and AI configuration; model edits use `saveSettings`.

- XDLT source editing, automatic compilation, assertion verification and executable blocks use `createXdltSession` / `updateXdltSession` / `destroyXdltSession`. Updates apply DOM patches with full-HTML recovery if preview revisions diverge. The preview runs in an iframe with scripts disabled; clicking a rendered node selects its source range. Debug shows dependency graph, semantic data, invalidation and reuse statistics. Source is autosaved via `saveXdltDocument`; `.xdlt` and `.hw` import create a new workspace copy.

The original backend reparses changed source. MathCore replay reuses evaluated prefix states, and XDLT sessions reuse verification/execution results and emit render patches. These are not claims of an incremental AST parser: the UI reports the original `reusedParsing` flag. The original HTTP gateway now also exposes its existing C++ `parse_document` operation via a small `parseDocument` bridge method.

Notebook markdown cells still render as plain text. Ink is an annotation, not handwriting recognition. Advanced edLatex context inspection, AI intent entry, knowledge-card authoring and the original step debugger have not all been migrated into Darwin; see [BACKEND_FEATURES.md](BACKEND_FEATURES.md).

```powershell
npm run typecheck
npm test
npm run build
node scripts/browser-smoke.mjs
node scripts/browser-incremental.mjs
```
