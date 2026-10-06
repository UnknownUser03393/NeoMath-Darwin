# Original NeoMath integration coverage

| Feature | Darwin entry point | Original API / status |
| --- | --- | --- |
| Syntax parsing and errors | Automatic check / editor | `parseDocument`, added as a forwarding HTTP method to the existing C++ parser |
| Mathematical analysis | Check / automatic after editing | `runTrace` initially, `replay(changedStep)` subsequently |
| Reuse measurements | Check status | Actual `metrics.cacheHits` and `durationMs`, not a frontend estimate |
| Auto check controls | Workspace toolbar | 250 ms debounce, IME pause, cancellation, stale result rejection |
| Live Preview | Default document view | CodeMirror single-body editing, selection-aware KaTeX replacements, prose, diagnostic markers, persistent source history, save, current-step completion and transformation popups |
| Error dependency connectors | Live Preview | Measured row anchors, one SVG overlay/path, fault-owned trunks and rounded child branches; linear trace `root_fault`/`parse_error` → subsequent `tainted` steps, cleared on edit/recheck |
| Solutions, domains and trust | Inspector | Actual trace states and diagnostics |
| First fault | Toolbar | Backend `breakpointStep`; navigates to the faulty step |
| Witness and manual probe | Evidence tab | Trace relation probes / `evaluateProbe` |
| Semantic completion | Editor / Ctrl+Space | `getCompletions`, including available/risk/preview fields |
| Algebraic transformations | Editor operation picker | `executeTransformation`, inserts the returned equation |
| Teaching explanation | Editor Explain | `requestAiExplanation`, original local/Qwen fallback and source attribution |
| Notebook list/load/save/import/export | Documents / document menu | `listNotebooks`, `loadNotebook`, `saveNotebook`; imported files use new names |
| Per-document ink | Canvas | Optional `darwinInk` field in the original `.nm` storage |
| Settings | Settings page | `getSettings`, model edits via `saveSettings` |
| Original writing files | Writing section | `listXdltDocuments`, `loadXdltDocument`, `saveXdltDocument` |
| Incremental writing sessions | XDLT editor | `createXdltSession`, `updateXdltSession`, `destroyXdltSession`; serial updates and restart recovery |
| Assertion verification and executable blocks | XDLT toolbar toggles | Original session `verify` / `execute` options |
| Dependency diagnostics and reuse | XDLT Debug | Backend graph, semantic document, invalidated IDs and stats |
| Incremental preview | XDLT iframe | Original HTML patches; full render recovery after skipped revisions / invalid targets |
| Preview to source navigation | Click rendered content | Backend source map; Unicode code-point offsets converted to JS selection offsets |

## Backend limits and remaining UI work

Changing source still invokes the original parser. MathCore caches evaluated prefix states; XDLT sessions cache verification/execution and compute preview diffs. Neither changed-source path is advertised here as partial AST reparsing.

Not all original features have a Darwin interface yet: full F5/F10 execution controls, one-click certified repair workflows, edLatex context/scopes/conflict inspection, PDF/LaTeX export of edLatex documents, AI intent compilation, knowledge-card authoring, value/environment editors, and notebook/workspace filename renaming. The corresponding backend methods are not treated as migrated merely because a generic HTTP client could call them.

The integration tests run an actual original Python/C++ gateway in a temporary data directory. Browser tests cover auto replay prefix reuse, metadata/IME/debounce/stale-response behavior, parse error recovery, semantic completion and transformations, explanations, XDLT verification reuse and DOM patches, plus the original persistence/ink/responsive/error-retry checks.
