"use client";

import type { XdltHtmlPatch, XdltPatchStats } from "@/lib/xdlt/types";

export interface XdltDebugState {
  sessionId: string | null;
  patchCount: number;
  invalidated: string[];
  stats: XdltPatchStats | null;
  roundTripMs: number | null;
  fallback: boolean;
  fallbackReason?: string;
  patches: XdltHtmlPatch[];
}

interface Props {
  debug: XdltDebugState | null;
}

function Row({
  label,
  value,
  fault = false,
}: {
  label: string;
  value: string;
  fault?: boolean;
}) {
  return (
    <div className="xdlt-debug-row">
      <span className="xdlt-debug-label">{label}</span>
      <span className={`xdlt-debug-value ${fault ? "fault" : ""}`}>{value}</span>
    </div>
  );
}

export function XdltDebugPanel({ debug }: Props) {
  if (!debug) return null;
  return (
    <div className="xdlt-debug-panel" aria-label="XDLT 增量调试">
      <div className="pane-bar">
        <span className="pane-title">XDLT</span>
      </div>

      <section className="xdlt-debug-section">
        <h4>Session</h4>
        <Row
          label="id"
          value={debug.sessionId ? debug.sessionId.slice(0, 8) : "-"}
        />
      </section>

      <section className="xdlt-debug-section">
        <h4>Compilation</h4>
        <Row label="patches" value={String(debug.patchCount)} />
        <Row label="invalidated" value={String(debug.invalidated.length)} />
        <Row
          label="round trip"
          value={debug.roundTripMs != null ? `${Math.round(debug.roundTripMs)}ms` : "-"}
        />
        <Row
          label="fallback"
          fault={debug.fallback}
          value={
            debug.fallback
              ? `yes${debug.fallbackReason ? `: ${debug.fallbackReason}` : ""}`
              : "no"
          }
        />
      </section>

      <section className="xdlt-debug-section">
        <h4>Cache</h4>
        <Row
          label="verify"
          value={
            debug.stats
              ? `${debug.stats.reusedVerification} reused / ${debug.stats.recomputedVerification} recomputed`
              : "-"
          }
        />
        <Row
          label="exec"
          value={
            debug.stats
              ? `${debug.stats.reusedExecution} reused / ${debug.stats.recomputedExecution} recomputed`
              : "-"
          }
        />
      </section>

      {debug.invalidated.length > 0 && (
        <section className="xdlt-debug-section">
          <h4>Invalidated</h4>
          <div className="xdlt-debug-list">
            {debug.invalidated.map((id) => (
              <div key={id} className="xdlt-debug-item">
                {id}
              </div>
            ))}
          </div>
        </section>
      )}

      {debug.patches.length > 0 && (
        <section className="xdlt-debug-section">
          <h4>Patches</h4>
          <div className="xdlt-debug-list">
            {debug.patches.map((patch, index) => (
              <div key={index} className="xdlt-debug-item">
                {patch.op} {patch.renderId ?? patch.parentRenderId ?? ""}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
