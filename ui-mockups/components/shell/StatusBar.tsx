"use client";

import { useNotebook } from "@/lib/notebook/commands";
import { isMathCell, isRootFault } from "@/lib/notebook/types";

export interface XdltStatusInfo {
  roundTripMs: number | null;
  patchCount: number;
  diagnostics: number;
  errors: number;
  fallback: boolean;
}

/**
 * IDE status bar — one thin row of live state. Left: mode + engine.
 * Right: diagnostics / steps + encoding. No color except real faults.
 */
export function StatusBar({
  mode,
  xdlt,
}: {
  mode: "notebook" | "xdlt";
  xdlt?: XdltStatusInfo | null;
}) {
  const { state, kernelStatus } = useNotebook();

  const kernelLabel =
    kernelStatus === "core"
      ? "MathCore"
      : kernelStatus === "checking"
        ? "MathCore…"
        : "演示内核";

  const steps = state.document.cells.filter(isMathCell);
  const verified = steps.filter((cell) => cell.executionState === "success").length;
  const fault = steps.find((cell) => isRootFault(cell.result));

  return (
    <footer className="status-bar" aria-label="状态栏">
      <span className="status-mode">{mode === "xdlt" ? "XDLT" : "Notebook"}</span>
      {mode === "xdlt" ? (
        <>
          <span className={`status-item ${xdlt?.fallback ? "fault" : ""}`}>
            {xdlt?.fallback ? "✗ Full render" : "✓ Incremental"}
          </span>
          <span className="status-item mono" data-demo-id="xdlt-latency">
            {xdlt?.roundTripMs != null ? `${Math.round(xdlt.roundTripMs)}ms` : "—"}
          </span>
          <span className="status-item optional mono">
            patches {xdlt?.patchCount ?? 0}
          </span>
        </>
      ) : (
        <>
          <span className="status-item">{kernelLabel}</span>
          <span data-demo-id="kernel-status" className={`status-item ${fault ? "fault" : ""}`}>
            {fault ? `断点 · 步骤 ${steps.indexOf(fault) + 1}` : `${verified}/${steps.length} 已验证`}
          </span>
        </>
      )}
      <span className="status-spacer" />
      {mode === "xdlt" ? (
        <span className={`status-item mono ${xdlt && xdlt.errors > 0 ? "fault" : ""}`}>
          diagnostics {xdlt?.diagnostics ?? 0}
        </span>
      ) : (
        <span className="status-item optional mono">
          {state.document.fileName}
        </span>
      )}
      <span className="status-item mono">UTF-8</span>
    </footer>
  );
}
