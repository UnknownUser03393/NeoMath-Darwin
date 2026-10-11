"use client";

import { useEffect, useRef, useState } from "react";
import { xdltBridge } from "@/lib/xdlt/bridge";
import { XdltSessionManager } from "@/lib/xdlt/session";
import { applyXdltPatches } from "@/lib/xdlt/patchRuntime";
import type { XdltDiagnostic } from "@/lib/xdlt/types";
import { useNotebook } from "@/lib/notebook/commands";
import { XdltDebugPanel, type XdltDebugState } from "./XdltDebugPanel";
import type { XdltStatusInfo } from "../shell/StatusBar";

/**
 * Minimal XDLT editor -> preview loop.
 *
 * The source text lives in the notebook provider (autosaved to the open
 * `.xdlt` file); this component owns the compilation session. First compile
 * mounts the full fragment; subsequent edits go through session.update ->
 * RenderPatch[] -> applyXdltPatches on the preview DOM. The debug panel
 * exposes incremental metrics.
 */
export function XdltWorkspace({
  onStatus,
  hidden = false,
}: {
  onStatus?: (status: XdltStatusInfo) => void;
  /** True when the pane is not the active tab; suppresses status callbacks. */
  hidden?: boolean;
}) {
  const { xdltFile, xdltSource, setXdltSource } = useNotebook();
  const [previewHtml, setPreviewHtml] = useState("");
  const [diagnostics, setDiagnostics] = useState<XdltDiagnostic[]>([]);
  const [debug, setDebug] = useState<XdltDebugState | null>(null);
  const previewRef = useRef<HTMLDivElement | null>(null);

  // The preview div is owned imperatively, not by React. React 19 rewrites
  // `dangerouslySetInnerHTML` unconditionally whenever the inline prop object is
  // recreated (i.e. on every re-render), which would wipe out the direct DOM
  // patches applied by onUpdate before their result survives. So we keep the
  // div childless for React and only set innerHTML here, when the full
  // `previewHtml` actually changes (first compile / patch fallback).
  useEffect(() => {
    if (previewRef.current && previewHtml) {
      previewRef.current.innerHTML = previewHtml;
    }
  }, [previewHtml]);
  const managerRef = useRef<XdltSessionManager | null>(null);
  const onStatusRef = useRef(onStatus);
  useEffect(() => {
    onStatusRef.current = onStatus;
  }, [onStatus]);
  const hiddenRef = useRef(hidden);
  useEffect(() => {
    hiddenRef.current = hidden;
  }, [hidden]);
  const [css, setCss] = useState("");
  const xdltSourceRef = useRef(xdltSource);
  useEffect(() => {
    xdltSourceRef.current = xdltSource;
  }, [xdltSource]);

  useEffect(() => {
    let cancelled = false;
    xdltBridge
      .referenceCss()
      .then((sheet) => {
        if (!cancelled) setCss(sheet);
      })
      .catch((error) => console.error("[xdlt] reference css failed:", error));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const manager = new XdltSessionManager(
      {
        onCompile: (result) => {
          setDiagnostics(result.diagnostics);
          setPreviewHtml(result.html);
          setDebug({
            sessionId: manager.id,
            patchCount: 0,
            invalidated: [],
            stats: null,
            roundTripMs: null,
            fallback: false,
            patches: [],
          });
          if (!hiddenRef.current) {
            onStatusRef.current?.({
              roundTripMs: null,
              patchCount: 0,
              diagnostics: result.diagnostics.length,
              errors: result.diagnostics.filter((d) => d.severity === "error")
                .length,
              fallback: false,
            });
          }
        },
        onUpdate: (result, meta) => {
          setDiagnostics(result.diagnostics);
          let fallback = result.stats?.patchFallback ?? false;
          let fallbackReason: string | undefined;
          if (previewRef.current) {
            const outcome = applyXdltPatches(previewRef.current, result.htmlPatches, {
              fullHtml: result.html,
              onFallback: (reason) => {
                fallbackReason = reason;
              },
            });
            if (outcome.fallback) {
              fallback = true;
              // Keep React and the DOM in sync after a full render.
              setPreviewHtml(result.html);
            }
          }
          setDebug({
            sessionId: manager.id,
            patchCount: result.htmlPatches.length,
            invalidated: result.invalidatedSemanticIds,
            stats: result.stats,
            roundTripMs: meta.roundTripMs,
            fallback,
            fallbackReason,
            patches: result.htmlPatches,
          });
          if (!hiddenRef.current) {
            onStatusRef.current?.({
              roundTripMs: meta.roundTripMs,
              patchCount: result.htmlPatches.length,
              diagnostics: result.diagnostics.length,
              errors: result.diagnostics.filter((d) => d.severity === "error")
                .length,
              fallback,
            });
          }
          if (fallbackReason) {
            console.warn("[xdlt] patch fallback:", fallbackReason);
          }
        },
        onError: (error) => {
          // Transport / fatal failure (e.g. backend unreachable): surface it
          // in the diagnostics panel instead of an unhandled rejection.
          console.error("[xdlt] session error:", error);
          const message =
            error instanceof Error ? error.message : "XDLT 内核不可达";
          setDiagnostics([
            {
              severity: "error",
              code: "OFFLINE",
              message,
            },
          ]);
          if (!hiddenRef.current) {
            onStatusRef.current?.({
              roundTripMs: null,
              patchCount: 0,
              diagnostics: 1,
              errors: 1,
              fallback: false,
            });
          }
        },
      },
      100,
    );
    managerRef.current = manager;
    void manager.open(xdltSourceRef.current, { execute: true, verify: true });
    return () => {
      void manager.close();
      managerRef.current = null;
    };
    // The session is created once per mount and is bound to this pane's tab
    // (via XdltTabScope); each tab gets its own pane, so no recompile-on-file
    // switch is needed here.
  }, []);

  const onEdit = (value: string) => {
    setXdltSource(value);
    managerRef.current?.edit(value, { execute: true, verify: true });
  };

  const runNow = () => {
    managerRef.current?.flush(xdltSource, { execute: true, verify: true });
  };

  return (
    <div className="xdlt-workspace" data-demo-id="xdlt-workspace">
      <div className="xdlt-editor-pane">
        <div className="pane-bar">
          <span className="pane-title">{xdltFile ?? "XDLT Source"}</span>
          <button className="xdlt-run-button" data-demo-id="xdlt-run-button" onClick={runNow} title="立即编译">
            编译
          </button>
        </div>
        <textarea
          className="xdlt-editor"
          data-demo-id="xdlt-editor"
          value={xdltSource}
          onChange={(event) => onEdit(event.target.value)}
          spellCheck={false}
          aria-label="XDLT 源码"
        />
        <div className="xdlt-diagnostics">
          {diagnostics.map((diagnostic, index) => (
            <div
              key={index}
              className={`xdlt-diagnostic-line xdlt-diagnostic-${diagnostic.severity}`}
            >
              <span className="xdlt-diag-code">
                {diagnostic.severity.toUpperCase()} {diagnostic.code}
              </span>
              <span>{diagnostic.message}</span>
              {diagnostic.range && (
                <span className="xdlt-diag-range">
                  [{diagnostic.range.start}..{diagnostic.range.end})
                </span>
              )}
            </div>
          ))}
          {diagnostics.length === 0 && (
            <div className="xdlt-diagnostics-empty">无诊断</div>
          )}
        </div>
      </div>
      <div className="xdlt-preview-pane">
        <div className="pane-bar">
          <span className="pane-title">Preview</span>
        </div>
        <style>{css}</style>
        <div ref={previewRef} className="xdlt-preview-root" data-demo-id="xdlt-preview" />
      </div>
      <XdltDebugPanel debug={debug} />
    </div>
  );
}
