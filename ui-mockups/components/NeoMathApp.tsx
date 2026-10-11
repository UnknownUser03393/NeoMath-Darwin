"use client";

import { useEffect, useState } from "react";
import { Sigma } from "lucide-react";
import { ActivityBar } from "./shell/ActivityBar";
import { NotebookSidebar } from "./shell/NotebookSidebar";
import { EditorTabs } from "./shell/EditorTabs";
import { CloseTabDialog } from "./shell/CloseTabDialog";
import { NotebookToolbar } from "./shell/NotebookToolbar";
import { NotebookCanvas } from "./notebook/NotebookCanvas";
import { DebugInspector } from "./debugger/DebugInspector";
import { XdltWorkspace } from "./xdlt/XdltWorkspace";
import { StatusBar, type XdltStatusInfo } from "./shell/StatusBar";
import {
  NotebookProvider,
  NotebookTabScope,
  XdltTabScope,
  useNotebook,
} from "@/lib/notebook/commands";
import {
  resolvePanelToggle,
  resolvePanelVisibility,
  type SidePanelMode,
  type SidePanelState,
} from "@/lib/shell/sidePanelMode";

function Workspace() {
  const {
    tabs,
    activeTabId,
    activateTab,
    closeTabById,
    dirtyTabIds,
    newTab,
    openNotebookView,
    openXdltView,
  } = useNotebook();
  const [panel, setPanel] = useState<SidePanelState>({
    open: true,
    mode: "notebook",
  });
  const [sidebarTouched, setSidebarTouched] = useState(false);
  const [xdltStatus, setXdltStatus] = useState<XdltStatusInfo | null>(null);

  // App-level shortcuts: Ctrl/Cmd+W closes the active tab, Ctrl+Tab cycles.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const mod = event.metaKey || event.ctrlKey;
      if (!mod) return;
      if (event.key === "Tab") {
        event.preventDefault();
        if (tabs.length < 2) return;
        const index = tabs.findIndex((tab) => tab.id === activeTabId);
        const next = event.shiftKey
          ? (index - 1 + tabs.length) % tabs.length
          : (index + 1) % tabs.length;
        activateTab(tabs[next].id);
        return;
      }
      if (event.key.toLowerCase() === "w") {
        event.preventDefault();
        if (activeTabId) closeTabById(activeTabId);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [tabs, activeTabId, activateTab, closeTabById]);

  const activeTab = tabs.find((tab) => tab.id === activeTabId);
  const activeIsXdlt = activeTab?.kind === "xdlt";

  const selectMode = (mode: SidePanelMode) => {
    setSidebarTouched(true);
    setPanel((current) => resolvePanelToggle(current, mode));
  };

  const selectEditor = (kind: "notebook" | "xdlt") => {
    setSidebarTouched(true);
    if (kind === "xdlt") {
      openXdltView();
    } else {
      openNotebookView();
    }
  };

  return (
    <main className="app-shell">
      <ActivityBar
        sidebarOpen={panel.open}
        activeMode={panel.mode}
        onSelectMode={selectMode}
      />
      <NotebookSidebar
        open={panel.open}
        pristine={!sidebarTouched}
        mode={panel.mode}
        onClose={() => {
          setSidebarTouched(true);
          setPanel((current) => resolvePanelVisibility(current, false));
        }}
        onSelectEditor={selectEditor}
      />
      <section className="workbench">
        <EditorTabs
          tabs={tabs}
          activeTabId={activeTabId}
          dirtyTabIds={dirtyTabIds}
          onSelect={activateTab}
          onClose={closeTabById}
          onNewTab={newTab}
        />
        <div className="editor-panes">
          {tabs.length === 0 && (
            <div className="editor-empty" role="tabpanel">
              <Sigma size={28} className="editor-empty-icon" aria-hidden="true" />
              <p>未打开任何标签页</p>
              <button
                type="button"
                className="editor-empty-new"
                onClick={newTab}
              >
                新建推导
              </button>
            </div>
          )}
          {tabs.map((tab) => {
            const active = tab.id === activeTabId;
            if (tab.kind === "notebook") {
              return (
                <NotebookTabScope key={tab.id} tab={tab}>
                  <div
                    className={`editor-pane editor-pane-notebook ${active ? "" : "hidden"}`}
                    role="tabpanel"
                    aria-hidden={!active}
                  >
                    <NotebookToolbar />
                    <div className="debug-workspace">
                      <NotebookCanvas />
                      <DebugInspector />
                    </div>
                  </div>
                </NotebookTabScope>
              );
            }
            return (
              <XdltTabScope key={tab.id} tab={tab}>
                <div
                  className={`editor-pane editor-pane-xdlt ${active ? "" : "hidden"}`}
                  role="tabpanel"
                  aria-hidden={!active}
                >
                  <XdltWorkspace hidden={!active} onStatus={setXdltStatus} />
                </div>
              </XdltTabScope>
            );
          })}
        </div>
        <StatusBar mode={activeIsXdlt ? "xdlt" : "notebook"} xdlt={xdltStatus} />
      </section>
      <CloseTabDialog />
    </main>
  );
}

export function NeoMathApp() {
  return (
    <NotebookProvider>
      <Workspace />
    </NotebookProvider>
  );
}
