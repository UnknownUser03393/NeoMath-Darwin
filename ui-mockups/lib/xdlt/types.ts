/**
 * XDLT bridge wire types. Mirrors the backend bridge/result payloads.
 */

export interface XdltDiagnostic {
  severity: string;
  code: string;
  message: string;
  range?: { start: number; end: number };
}

export interface XdltSourceMapEntry {
  renderId: string;
  semanticId: string | null;
  sourceRange: { start: number; end: number };
}

export interface XdltCompileResult {
  html: string;
  diagnostics: XdltDiagnostic[];
  assets: Array<{ kind: string; url: string }>;
  sourceMap: XdltSourceMapEntry[];
  renderDocument: unknown;
  graph: unknown;
}

export interface XdltPatchStats {
  reusedVerification: number;
  recomputedVerification: number;
  reusedExecution: number;
  recomputedExecution: number;
  reusedParsing: boolean;
  patchFallback: boolean;
}

export interface XdltIncrementalResult extends XdltCompileResult {
  patches: Array<{ op: string; renderId?: string }>;
  htmlPatches: XdltHtmlPatch[];
  invalidatedSemanticIds: string[];
  stats: XdltPatchStats;
}

/** Backend HTML patch protocol (lowered from RenderPatch). */
export interface XdltHtmlPatch {
  op: "replace" | "remove" | "insert" | "replace-document";
  renderId?: string;
  anchor?: string;
  parentRenderId?: string;
  parentAnchor?: string;
  index?: number;
  html?: string;
}

export interface XdltCreateEnvelope {
  ok: boolean;
  sessionId: string;
  result: XdltCompileResult;
  error?: { code?: string; message?: string };
}

export interface XdltUpdateEnvelope {
  ok: boolean;
  sessionId: string;
  result: XdltIncrementalResult;
  error?: { code?: string; message?: string };
}
