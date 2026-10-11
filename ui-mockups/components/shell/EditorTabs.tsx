"use client";

import { useEffect, useRef } from "react";
import { Code2, Plus, Sigma, X } from "lucide-react";
import type { Tab } from "@/lib/notebook/tabs";

interface EditorTabsProps {
  tabs: Tab[];
  /** Active tab id, or null when no tabs are open. */
  activeTabId: string | null;
  /** Ids of tabs with unsaved changes; rendered as a dot before the title. */
  dirtyTabIds: ReadonlySet<string>;
  onSelect: (tabId: string) => void;
  /** Close the given tab for real (blank fallback when it's the last). */
  onClose: (tabId: string) => void;
  /** Open a new blank tab matching the active tab's kind. */
  onNewTab: () => void;
}

function tabTitle(tab: Tab): string {
  if (tab.kind === "notebook") {
    return tab.state.fileName ?? "未命名推导";
  }
  return tab.fileName ?? "XDLT 编辑器";
}

/**
 * VS Code style editor tab strip: one row of file tabs, the active tab
 * merges into the editor surface below. Renders whatever tabs the provider
 * holds; the strip scrolls horizontally when there are too many to fit, and
 * the active tab scrolls into view when it changes.
 */
export function EditorTabs({
  tabs,
  activeTabId,
  dirtyTabIds,
  onSelect,
  onClose,
  onNewTab,
}: EditorTabsProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const activeRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    const active = activeRef.current;
    if (!container || !active) return;
    const target = active.offsetLeft - container.offsetLeft - 8;
    container.scrollTo({ left: Math.max(0, target), behavior: "smooth" });
  }, [activeTabId]);

  return (
    <div
      className="editor-tabs"
      role="tablist"
      aria-label="编辑器标签"
      ref={containerRef}
    >
      {tabs.map((tab) => {
        const active = tab.id === activeTabId;
        const dirty = dirtyTabIds.has(tab.id);
        const title = tabTitle(tab);
        return (
          <div
            key={tab.id}
            role="tab"
            aria-selected={active}
            className={`editor-tab ${active ? "active" : ""}`}
            ref={active ? activeRef : undefined}
          >
            <button
              type="button"
              className="editor-tab-main"
              onClick={() => onSelect(tab.id)}
              title={dirty ? `${title}（未保存）` : title}
            >
              {dirty && <span className="editor-tab-dirty" aria-label="未保存" />}
              {tab.kind === "notebook" ? (
                <Sigma size={13} />
              ) : (
                <Code2 size={13} />
              )}
              <span>{title}</span>
            </button>
            <button
              type="button"
              className="editor-tab-close"
              onClick={() => onClose(tab.id)}
              aria-label="关闭标签"
              title="关闭标签"
            >
              <X size={11} />
            </button>
          </div>
        );
      })}
      <button
        type="button"
        className="editor-tabs-new"
        onClick={onNewTab}
        aria-label="新建标签"
        title="新建标签"
      >
        <Plus size={14} />
      </button>
      <div className="editor-tabs-spacer" />
    </div>
  );
}
