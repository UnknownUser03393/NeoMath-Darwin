"use client";

import { AlertTriangle } from "lucide-react";
import { useNotebook } from "@/lib/notebook/commands";

/**
 * Discard-confirmation for closing a dirty tab. Rendered once at the app
 * shell level; it reads the pending-close tab from the notebook provider and
 * is a no-op (renders nothing) when no tab is awaiting confirmation.
 */
export function CloseTabDialog() {
  const {
    pendingCloseTabId,
    tabs,
    confirmCloseTab,
    cancelCloseTab,
  } = useNotebook();
  const tab = pendingCloseTabId
    ? tabs.find((item) => item.id === pendingCloseTabId)
    : undefined;
  if (!tab) return null;

  const title =
    tab.kind === "notebook"
      ? (tab.state.fileName ?? "未命名推导")
      : (tab.fileName ?? "未命名 XDLT");

  return (
    <div className="dialog-backdrop" role="presentation">
      <div
        className="close-tab-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-label="关闭未保存的标签"
      >
        <div className="close-tab-dialog-icon" aria-hidden="true">
          <AlertTriangle size={18} />
        </div>
        <div className="close-tab-dialog-body">
          <h3>关闭「{title}」？</h3>
          <p>该标签页有尚未保存的更改，关闭后将丢失。</p>
        </div>
        <div className="close-tab-dialog-actions">
          <button
            type="button"
            className="close-tab-dialog-cancel"
            onClick={cancelCloseTab}
          >
            取消
          </button>
          <button
            type="button"
            className="close-tab-dialog-confirm"
            onClick={confirmCloseTab}
          >
            放弃更改并关闭
          </button>
        </div>
      </div>
    </div>
  );
}
