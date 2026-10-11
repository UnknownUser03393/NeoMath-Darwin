"use client";

import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { FilePlus2, Pencil, X } from "lucide-react";
import { useNotebook } from "@/lib/notebook/commands";
import { FileNameDialog } from "@/components/notebook/FileNameDialog";
import {
  SIDE_PANEL_META,
  type SidePanelMode,
} from "@/lib/shell/sidePanelMode";
import {
  HelpPanel,
  SettingsPanel,
  VariablesPanel,
} from "./panelSkeletons";

type FileNameDialogState =
  | { mode: "new"; kind: "notebook" }
  | { mode: "new"; kind: "xdlt" }
  | { mode: "rename"; kind: "notebook"; from: string }
  | { mode: "rename"; kind: "xdlt"; from: string };

/** True when the viewport is below the mobile breakpoint (≤820px). */
function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(
    () => typeof window !== "undefined" && window.matchMedia(query).matches,
  );
  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);
  return matches;
}

function NotebookPanelBody({
  onSelectEditor,
}: {
  onSelectEditor: (kind: "notebook" | "xdlt") => void;
}) {
  const {
    state,
    createNewDerivation,
    openFile,
    renameFile,
    workspace,
    selectAndReveal,
    createNewXdlt,
    openXdltFile,
    renameXdltFile,
    xdltWorkspace,
    xdltFile,
  } = useNotebook();

  // The dialog's *intent* (which kind / rename target) and its *visibility*
  // are separate: closing only flips `dialogOpen`, so the fade-out keeps the
  // last title instead of flashing the "new notebook" fallback.
  const [dialogOpen, setDialogOpen] = useState(false);
  const [fileNameDialog, setFileNameDialog] =
    useState<FileNameDialogState | null>(null);

  const openDialog = (dialog: FileNameDialogState) => {
    setFileNameDialog(dialog);
    setDialogOpen(true);
  };

  const handleNew = () => openDialog({ mode: "new", kind: "notebook" });
  const handleNewXdlt = () => openDialog({ mode: "new", kind: "xdlt" });
  const handleRename = (fileName: string) =>
    openDialog({ mode: "rename", kind: "notebook", from: fileName });
  const handleRenameXdlt = (fileName: string) =>
    openDialog({ mode: "rename", kind: "xdlt", from: fileName });

  const existingFiles = [
    ...workspace.files.map((file) => file.fileName),
    ...xdltWorkspace.files.map((file) => file.fileName),
  ];

  const outline = state.document.cells.map((cell) => ({
    id: cell.id,
    icon:
      cell.kind === "markdown"
        ? "H1"
        : cell.executionState === "error"
          ? "!"
          : cell.kind === "transform"
            ? "↻"
            : "ƒ",
    text:
      cell.kind === "markdown"
        ? state.document.title
        : cell.label ?? (cell.source || "未命名单元格"),
    error: cell.executionState === "error",
  }));

  return (
    <>
      <button
        className="sidebar-new"
        onClick={handleNew}
        title="新建推导会保存到工作区"
      >
        <FilePlus2 size={14} />
        新建推导
      </button>
      <button
        className="sidebar-new"
        onClick={handleNewXdlt}
        title="新建 XDLT 文档会保存到工作区"
      >
        <FilePlus2 size={14} />
        新建 XDLT
      </button>

      <div className="sidebar-section-label">工作区</div>
      <div className="sidebar-group-label">推导 (.nm)</div>
      <nav className="file-list" aria-label="工作区推导文件">
        {workspace.loading ? (
          <p className="panel-hint">正在加载工作区…</p>
        ) : workspace.files.length === 0 ? (
          <p className="panel-hint">没有推导文件。点「新建推导」开始。</p>
        ) : (
          workspace.files.map((file) => {
            const active = state.fileName === file.fileName;
            return (
              <div
                key={file.fileName}
                className={`file-row ${active ? "active" : ""}`}
              >
                <button
                  className="file-item"
                  onClick={() => {
                    onSelectEditor("notebook");
                    void openFile(file.fileName);
                  }}
                  title={file.title}
                >
                  <span className="file-prefix">ƒ</span>
                  <span data-demo-id={`sidebar-file-${file.fileName}`}>{file.fileName}</span>
                </button>
                <button
                  className="file-rename"
                  onClick={() => handleRename(file.fileName)}
                  aria-label={`重命名 ${file.fileName}`}
                  title="重命名"
                >
                  <Pencil size={12} />
                </button>
              </div>
            );
          })
        )}
      </nav>

      <div className="sidebar-group-label">XDLT 文档 (.xdlt)</div>
      <nav className="file-list" aria-label="工作区 XDLT 文档">
        {xdltWorkspace.loading ? (
          <p className="panel-hint">正在加载工作区…</p>
        ) : xdltWorkspace.files.length === 0 ? (
          <p className="panel-hint">没有 XDLT 文档。点「新建 XDLT」开始。</p>
        ) : (
          xdltWorkspace.files.map((file) => {
            const active = xdltFile === file.fileName;
            return (
              <div
                key={file.fileName}
                className={`file-row ${active ? "active" : ""}`}
              >
                <button
                  className="file-item"
                  onClick={() => {
                    onSelectEditor("xdlt");
                    void openXdltFile(file.fileName);
                  }}
                  title={file.title}
                >
                  <span className="file-prefix">≐</span>
                  <span data-demo-id={`sidebar-file-${file.fileName}`}>{file.fileName}</span>
                </button>
                <button
                  className="file-rename"
                  onClick={() => handleRenameXdlt(file.fileName)}
                  aria-label={`重命名 ${file.fileName}`}
                  title="重命名"
                >
                  <Pencil size={12} />
                </button>
              </div>
            );
          })
        )}
      </nav>

      <div className="sidebar-heading outline-heading">执行轨迹</div>
      <nav className="outline-list" aria-label="执行轨迹">
        {outline.map((item) => (
          <button key={item.id} onClick={() => selectAndReveal(item.id)}>
            <span
              className={`outline-icon ${item.error ? "error" : item.icon === "✓" ? "success" : ""}`}
            >
              {item.icon}
            </span>
            <span>{item.text}</span>
          </button>
        ))}
      </nav>

      <FileNameDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        mode={fileNameDialog?.mode ?? "new"}
        kind={fileNameDialog?.kind ?? "notebook"}
        defaultValue={
          fileNameDialog?.mode === "rename"
            ? fileNameDialog.from.replace(/\.(nm|xdlt)$/, "")
            : undefined
        }
        renameFrom={
          fileNameDialog?.mode === "rename" ? fileNameDialog.from : undefined
        }
        existing={existingFiles}
        onSubmit={(name) => {
          const dialog = fileNameDialog;
          if (dialog?.mode === "rename") {
            if (dialog.kind === "notebook") {
              void renameFile(dialog.from, name);
            } else {
              void renameXdltFile(dialog.from, name);
            }
            return;
          }
          if (dialog?.kind === "xdlt") {
            onSelectEditor("xdlt");
            void createNewXdlt(name);
          } else {
            onSelectEditor("notebook");
            void createNewDerivation(name);
          }
        }}
      />
    </>
  );
}

function PanelBody({
  mode,
  onSelectEditor,
}: {
  mode: SidePanelMode;
  onSelectEditor: (kind: "notebook" | "xdlt") => void;
}) {
  switch (mode) {
    case "notebook":
      return <NotebookPanelBody onSelectEditor={onSelectEditor} />;
    case "variables":
      return <VariablesPanel />;
    case "help":
      return <HelpPanel />;
    case "settings":
      return <SettingsPanel />;
  }
}

export function NotebookSidebar({
  open,
  pristine,
  mode,
  onClose,
  onSelectEditor,
}: {
  open: boolean;
  pristine: boolean;
  mode: SidePanelMode;
  onClose: () => void;
  onSelectEditor: (kind: "notebook" | "xdlt") => void;
}) {
  const meta = SIDE_PANEL_META[mode];
  const isMobile = useMediaQuery("(max-width: 820px)");
  const reduce = useReducedMotion();

  return (
    <motion.aside
      className={`notebook-sidebar ${open ? "open" : ""} ${pristine ? "pristine" : ""}`}
      aria-label={meta.ariaLabel}
      data-side-panel={mode}
      initial={false}
      animate={
        isMobile
          ? { x: open && !pristine ? 0 : -240 }
          : { width: open ? 240 : 0 }
      }
      transition={
        reduce ? { duration: 0 } : { duration: 0.14, ease: "easeOut" }
      }
    >
      <div className="sidebar-heading">
        <span>{meta.heading}</span>
        <button
          className="sidebar-close"
          onClick={onClose}
          aria-label={`关闭 ${meta.label} 面板`}
          title="关闭面板"
        >
          <X size={15} />
        </button>
      </div>

      <PanelBody mode={mode} onSelectEditor={onSelectEditor} />
    </motion.aside>
  );
}
