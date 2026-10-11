"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type Dispatch,
  type ReactNode,
} from "react";
import {
  createBlankNotebook,
  createDemoNotebook,
  defaultSelectedCell,
  DEMO_CATALOG,
} from "./demos";
import { initialNotebookState, type State } from "./notebookState";
import {
  createNotebookTab,
  createXdltTab,
  initialTabsState,
  projectedNotebookState,
  projectedXdltFile,
  projectedXdltSource,
  resolveNotebookTab,
  tabsReducer,
  type NotebookTab,
  type Tab,
  type TabAction,
  type XdltTab,
} from "./tabs";
import {
  listNotebooks,
  loadNotebookFile,
  saveNotebookFile,
  renameNotebookFile,
  seedNotebooks,
  rememberLastFile,
  listXdltDocuments,
  loadXdltDocument,
  saveXdltDocument,
  renameXdltDocument,
  seedXdltDocuments,
  rememberLastXdltFile,
  type NotebookFileMeta,
  type XdltFileMeta,
} from "./persistence";
import { loadSession, saveSession, type SessionTabRef } from "./sessionPersistence";
import {
  isMathCell,
  isRootFault,
  type CellKind,
  type CompletionItem,
  type ExecutionResult,
  type KernelStatus,
  type ProbeResult,
} from "./types";
import { buildRepairInsert } from "./repairFlow";
import {
  applyWitnessToProbe,
  type ApplyWitnessResult,
} from "./witnessProbe";
import { mathRuntime } from "@/lib/runtime";
import { BLANK_XDLT, DEMO_XDLT } from "@/lib/xdlt/demo";

/** Build a hydrated notebook tab state for a freshly opened document. */
function hydratedNotebookState(
  document: State["document"],
  fileName: string | null,
): State {
  return {
    document,
    fileName,
    selectedCellId: defaultSelectedCell(document),
    editingCellId: null,
    kernelRunning: false,
    hydrated: true,
  };
}

/** Last-persisted content fingerprint for a tab, used to derive dirty state. */
type SavedSig =
  | { kind: "notebook"; updatedAt: number | null }
  | { kind: "xdlt"; source: string };

/** A tab is dirty when it has no persisted fingerprint yet (unsaved canvas) or
    its live content differs from the last thing written to disk. */
function tabIsDirty(tab: Tab, sig: SavedSig | undefined): boolean {
  if (tab.kind === "notebook") {
    if (sig) return sig.updatedAt !== tab.state.document.updatedAt;
    return tab.state.fileName === null;
  }
  if (sig) return sig.source !== tab.source;
  return tab.fileName === null;
}

interface NotebookCommands {
  state: State;
  /** Accepts both notebook actions (routed to the active tab) and tab actions. */
  dispatch: Dispatch<TabAction>;
  kernelStatus: KernelStatus;
  kernelUrl: string;
  refreshKernel: () => Promise<void>;
  insertCell: (
    afterId: string | null,
    kind: CellKind,
    source?: string,
    label?: string,
  ) => string;
  /**
   * After a root fault: insert a repair math cell and surface completions
   * (preview pre-filled when the real completions path provides one).
   */
  insertRepairCell: (afterId: string) => Promise<{
    cellId: string;
    suggestion: CompletionItem | null;
    suggestions: CompletionItem[];
  }>;
  /** One-click: Witness value → Probe evaluation on the shipped runtime. */
  applyWitnessProbe: (witnessValue: string) => Promise<ApplyWitnessResult>;
  duplicateCell: (cellId: string) => void;
  runCell: (cellId: string, advance?: boolean) => Promise<ExecutionResult | null>;
  runAll: () => Promise<void>;
  stepNext: () => Promise<void>;
  continueExecution: () => Promise<void>;
  restartExecution: () => void;
  stop: () => void;
  reset: () => void;
  /** Create a new derivation file on disk and open it. */
  createNewDerivation: (name: string) => Promise<boolean>;
  /** Close the current derivation's tab (blank fallback when it's the last). */
  closeDocument: () => void;
  /** Open a workspace file by its fileName. */
  openFile: (fileName: string) => Promise<boolean>;
  /** Rename a workspace file on disk; updates any open tab for that file. */
  renameFile: (
    from: string,
    to: string,
  ) => Promise<{ ok: boolean; message?: string }>;
  selectAndReveal: (cellId: string) => void;
  saveNow: () => void;
  savedAt: number;
  workspace: { files: NotebookFileMeta[]; loading: boolean };
  refreshWorkspace: () => Promise<void>;
  /** Projected open XDLT document ("X.xdlt"), or null for an unsaved canvas. */
  xdltFile: string | null;
  /** Projected live XDLT source text; autosaved to xdltFile when one is open. */
  xdltSource: string;
  setXdltSource: (source: string) => void;
  createNewXdlt: (name: string) => Promise<boolean>;
  openXdltFile: (fileName: string) => Promise<boolean>;
  renameXdltFile: (
    from: string,
    to: string,
  ) => Promise<{ ok: boolean; message?: string }>;
  closeXdlt: () => void;
  xdltWorkspace: { files: XdltFileMeta[]; loading: boolean };
  refreshXdltWorkspace: () => Promise<void>;
  evaluateProbe: (value: string) => Promise<ProbeResult | null>;
  getCompletionsForSelection: () => Promise<CompletionItem[]>;
  applyCompletion: (command: string) => Promise<void>;
  /** Structured op from the palette — never free Chinese prose. */
  applyStructuredTransform: (
    op: import("./transforms").TransformOp,
    arg?: string,
  ) => Promise<{ ok: true } | { ok: false; message: string }>;
  derivationSource: () => string;
  /** All open tabs (both kinds). */
  tabs: Tab[];
  /** Active tab id, or null when all tabs are closed (empty editor). */
  activeTabId: string | null;
  activateTab: (tabId: string) => void;
  /** Close a tab for real; closing the last tab leaves an empty editor.
      Returns false when the tab is dirty and a discard-confirmation was raised. */
  closeTabById: (tabId: string) => boolean;
  /** Switch to the most recent notebook view, creating a blank one if none. */
  openNotebookView: () => void;
  /** Switch to the most recent XDLT view, creating a demo one if none. */
  openXdltView: () => void;
  /** Ids of tabs whose content differs from the last thing persisted. */
  dirtyTabIds: ReadonlySet<string>;
  /** Open a new blank tab matching the active tab's kind. */
  newTab: () => void;
  /** Id of the dirty tab awaiting discard confirmation, or null. */
  pendingCloseTabId: string | null;
  /** Discard the pending tab's changes and close it. */
  confirmCloseTab: () => void;
  /** Keep the pending tab open. */
  cancelCloseTab: () => void;
}

const NotebookContext = createContext<NotebookCommands | null>(null);

export function NotebookProvider({ children }: { children: ReactNode }) {
  const [tabsState, tabsDispatch] = useReducer(tabsReducer, initialTabsState);
  const dispatch = tabsDispatch;
  const [savedAt, setSavedAt] = useState(0);
  /** Per-tab fingerprints of the last content persisted to disk. */
  const [savedSigs, setSavedSigs] = useState<Record<string, SavedSig>>({});
  /** A dirty tab awaiting discard confirmation, or null. */
  const [pendingCloseTabId, setPendingCloseTabId] = useState<string | null>(
    null,
  );
  const [kernelStatus, setKernelStatus] = useState<KernelStatus>("checking");
  const [workspace, setWorkspace] = useState<{
    files: NotebookFileMeta[];
    loading: boolean;
  }>({ files: [], loading: true });
  const [xdltWorkspace, setXdltWorkspace] = useState<{
    files: XdltFileMeta[];
    loading: boolean;
  }>({ files: [], loading: true });

  const tabsStateRef = useRef(tabsState);
  useEffect(() => {
    tabsStateRef.current = tabsState;
  }, [tabsState]);

  // ── Projections ────────────────────────────────────────────────────────
  // Consumer components keep reading `state` / `xdltFile` / `xdltSource` —
  // these now resolve to the active tab (or the last tab of that kind).
  const state = useMemo(() => projectedNotebookState(tabsState), [tabsState]);
  const xdltFile = useMemo(() => projectedXdltFile(tabsState), [tabsState]);
  const xdltSource = useMemo(() => projectedXdltSource(tabsState), [tabsState]);

  const stateRef = useRef<State>(initialNotebookState);
  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  /** Record the fingerprint of content that was just persisted to disk. */
  const recordSavedTab = useCallback((tab: Tab) => {
    setSavedSigs((prev) => ({
      ...prev,
      [tab.id]:
        tab.kind === "notebook"
          ? { kind: "notebook", updatedAt: tab.state.document.updatedAt }
          : { kind: "xdlt", source: tab.source },
    }));
  }, []);

  const executionToken = useRef(0);
  const stopRequested = useRef(false);

  /** Re-open one session tab reference; null when its file vanished. */
  async function restoreSessionTab(ref: SessionTabRef): Promise<Tab | null> {
    if (ref.kind === "notebook") {
      if (ref.fileName) {
        const document = await loadNotebookFile(ref.fileName);
        if (document) {
          return createNotebookTab(hydratedNotebookState(document, ref.fileName));
        }
      }
      return createNotebookTab(hydratedNotebookState(createBlankNotebook(), null));
    }
    if (ref.fileName) {
      const source = await loadXdltDocument(ref.fileName);
      if (source !== null) {
        return createXdltTab(ref.fileName, source);
      }
    }
    return createXdltTab();
  }

  /** Seed demos once, then restore the session (or fall back to last file). */
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        // 1. Seed / list the notebook workspace
        const nbState = await listNotebooks();
        if (cancelled) return;
        if (nbState) {
          let files = nbState.files;
          if (!nbState.seeded) {
            await Promise.all(
              DEMO_CATALOG.map((demo) =>
                saveNotebookFile(demo.fileName, createDemoNotebook(demo.id)),
              ),
            );
            await seedNotebooks();
            const refreshed = await listNotebooks();
            if (refreshed) files = refreshed.files;
          }
          if (cancelled) return;
          setWorkspace({ files, loading: false });
        }

        // 2. Seed / list the XDLT workspace
        const xdState = await listXdltDocuments();
        if (cancelled) return;
        if (xdState) {
          let files = xdState.files;
          if (!xdState.seeded) {
            await saveXdltDocument("示例.xdlt", DEMO_XDLT);
            await seedXdltDocuments();
            const refreshed = await listXdltDocuments();
            if (refreshed) files = refreshed.files;
          }
          if (cancelled) return;
          setXdltWorkspace({ files, loading: false });
        }

        if (cancelled) return;

        // 3. Restore the persisted tab session, if any.
        const saved = loadSession();
        if (saved && saved.tabs.length > 0) {
          const opened: Tab[] = [];
          for (const ref of saved.tabs) {
            const tab = await restoreSessionTab(ref);
            if (tab) opened.push(tab);
          }
          if (cancelled) return;
          if (opened.length === 0) opened.push(createNotebookTab());
          const activeTabId =
            opened[Math.min(saved.activeTabIndex, opened.length - 1)]?.id ??
            opened[0].id;
          tabsDispatch({ type: "tab/replaceAll", tabs: opened, activeTabId });
          return;
        }

        // 4. Fallback: no saved session — open an empty editor (no tabs).
        if (cancelled) return;
        tabsDispatch({ type: "tab/replaceAll", tabs: [], activeTabId: null });
      } catch {
        // A malformed response or an unexpected bridge error must not leave
        // the sidebar's loading indicator on screen forever; the editor
        // stays empty either way.
        if (!cancelled) {
          setWorkspace({ files: [], loading: false });
          setXdltWorkspace({ files: [], loading: false });
          tabsDispatch({ type: "tab/replaceAll", tabs: [], activeTabId: null });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void mathRuntime.getKernelStatus().then((status) => {
      if (!cancelled) setKernelStatus(status);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshWorkspace = useCallback(async () => {
    const current = await listNotebooks();
    if (current) setWorkspace({ files: current.files, loading: false });
  }, []);

  const refreshXdltWorkspace = useCallback(async () => {
    const current = await listXdltDocuments();
    if (current) setXdltWorkspace({ files: current.files, loading: false });
  }, []);

  /** Autosave: per-tab debounced save, keyed off every tab's content so a
      save scheduled for a background tab is not cancelled by switching tabs. */
  useEffect(() => {
    const timers: number[] = [];
    for (const tab of tabsState.tabs) {
      if (tab.kind === "notebook") {
        const { fileName, document, hydrated } = tab.state;
        if (!hydrated || !fileName) continue;
        timers.push(
          window.setTimeout(() => {
            void saveNotebookFile(fileName, document);
            recordSavedTab(tab);
            setSavedAt(Date.now());
          }, 180),
        );
      } else if (tab.kind === "xdlt") {
        if (!tab.fileName) continue;
        timers.push(
          window.setTimeout(() => {
            void saveXdltDocument(tab.fileName, tab.source);
            recordSavedTab(tab);
            setSavedAt(Date.now());
          }, 180),
        );
      }
    }
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, [tabsState.tabs, recordSavedTab]);

  /** Persist the open tab set so a refresh restores it. */
  useEffect(() => {
    if (!tabsState.hydrated) return;
    const activeIndex = tabsState.tabs.findIndex(
      (t) => t.id === tabsState.activeTabId,
    );
    saveSession({
      tabs: tabsState.tabs.map((tab) =>
        tab.kind === "notebook"
          ? { kind: "notebook", fileName: tab.state.fileName }
          : { kind: "xdlt", fileName: tab.fileName },
      ),
      activeTabIndex: Math.max(0, activeIndex),
    });
  }, [tabsState.tabs, tabsState.activeTabId, tabsState.hydrated]);

  const refreshKernel = useCallback(async () => {
    setKernelStatus("checking");
    const status = await mathRuntime.refreshKernel();
    setKernelStatus(status);
  }, []);

  const insertCellInTab = useCallback(
    (
      tabId: string,
      afterId: string | null,
      kind: CellKind,
      source?: string,
      label?: string,
    ) => {
      const newId = `cell-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
      tabsDispatch({
        type: "tab/apply",
        tabId,
        action: { type: "cell/insertAfter", cellId: afterId, kind, newId, source, label },
      });
      window.setTimeout(() => document.getElementById(`editor-${newId}`)?.focus(), 30);
      return newId;
    },
    [],
  );

  const insertCell = useCallback(
    (afterId: string | null, kind: CellKind, source?: string, label?: string) => {
      const nbTab = resolveNotebookTab(tabsStateRef.current);
      if (!nbTab) return "";
      return insertCellInTab(nbTab.id, afterId, kind, source, label);
    },
    [insertCellInTab],
  );

  const insertRepairCell = useCallback(
    async (afterId: string) => {
      const snapshot = stateRef.current;
      const faultCell = snapshot.document.cells.find((item) => item.id === afterId);
      let completions: CompletionItem[] = [];
      if (faultCell && isMathCell(faultCell)) {
        const mathCells = snapshot.document.cells.filter(isMathCell);
        const index = mathCells.findIndex((item) => item.id === afterId);
        const lines = mathCells
          .slice(0, Math.max(0, index) + 1)
          .map((item) => item.source)
          .filter(Boolean);
        try {
          completions = await mathRuntime.getCompletions(
            lines.join("\n"),
            Math.max(0, index),
          );
        } catch (error) {
          console.warn("[NeoMath] repair completions failed", error);
          completions = [];
        }
      }
      const repair = buildRepairInsert(completions);
      const cellId = insertCell(
        afterId,
        "math",
        repair.source,
        repair.label,
      );
      return {
        cellId,
        suggestion: repair.suggestion,
        suggestions: repair.suggestions,
      };
    },
    [insertCell],
  );

  const applyWitnessProbe = useCallback(
    async (witnessValue: string) => {
      return applyWitnessToProbe(
        (value) => mathRuntime.evaluateProbe({
          source: stateRef.current.document.cells
            .filter(isMathCell)
            .map((cell) => cell.source)
            .filter(Boolean)
            .join("\n"),
          value,
        }),
        witnessValue,
      );
    },
    [],
  );

  const duplicateCell = useCallback((cellId: string) => {
    const newId = `cell-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    dispatch({ type: "cell/duplicate", cellId, newId });
    window.setTimeout(() => document.getElementById(`editor-${newId}`)?.focus(), 30);
  }, [dispatch]);

  const runCell = useCallback(
    async (
      cellId: string,
      advance = false,
      preserveStop = false,
    ): Promise<ExecutionResult | null> => {
      if (!preserveStop) stopRequested.current = false;
      // Capture the tab that started this run so a mid-flight tab switch
      // cannot route the completion into the wrong notebook.
      const runTabId = tabsStateRef.current.activeTabId;
      const runTab = tabsStateRef.current.tabs.find((t) => t.id === runTabId);
      if (runTab?.kind !== "notebook") return null;
      const snapshot = runTab.state;
      const cell = snapshot.document.cells.find((item) => item.id === cellId);
      if (!cell || !isMathCell(cell)) return null;
      const token = ++executionToken.current;
      tabsDispatch({
        type: "tab/apply",
        tabId: runTabId,
        action: { type: "cell/executionStarted", cellId },
      });
      const index = snapshot.document.cells.findIndex((item) => item.id === cellId);
      const previousMathCells = snapshot.document.cells
        .slice(0, index)
        .filter(isMathCell);
      const result = await mathRuntime.execute(cell, { previousMathCells });
      if (token !== executionToken.current) return null;
      const runTabNow = tabsStateRef.current.tabs.find((t) => t.id === runTabId);
      const maxCount = Math.max(
        0,
        ...(runTabNow?.kind === "notebook"
          ? runTabNow.state.document.cells.map((item) => item.executionCount ?? 0)
          : []),
      );
      tabsDispatch({
        type: "tab/apply",
        tabId: runTabId,
        action: {
          type: "cell/executionFinished",
          cellId,
          result,
          count: maxCount + 1,
        },
      });
      // Refresh status after first successful core contact
      void mathRuntime.getKernelStatus().then(setKernelStatus);
      if (advance) {
        const next =
          runTabNow?.kind === "notebook"
            ? runTabNow.state.document.cells[index + 1]
            : undefined;
        if (next) {
          tabsDispatch({
            type: "tab/apply",
            tabId: runTabId,
            action: { type: "cell/select", cellId: next.id },
          });
          tabsDispatch({
            type: "tab/apply",
            tabId: runTabId,
            action: { type: "cell/edit", cellId: next.id },
          });
          window.setTimeout(() => document.getElementById(`editor-${next.id}`)?.focus(), 20);
        } else {
          insertCellInTab(runTabId, cellId, "math");
        }
      }
      return result;
    },
    [insertCellInTab],
  );

  const selectAndReveal = useCallback((cellId: string) => {
    dispatch({ type: "cell/select", cellId });
    document.getElementById(`cell-${cellId}`)?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }, [dispatch]);

  const runAll = useCallback(async () => {
    stopRequested.current = false;
    const ids = stateRef.current.document.cells
      .filter(isMathCell)
      .map((cell) => cell.id);
    for (const id of ids) {
      if (stopRequested.current) break;
      const result = await runCell(id, false, true);
      if (result && isRootFault(result)) {
        selectAndReveal(id);
        break;
      }
    }
  }, [runCell, selectAndReveal]);

  const stepNext = useCallback(async () => {
    const snapshot = stateRef.current;
    const mathCells = snapshot.document.cells.filter(isMathCell);
    const target =
      mathCells.find((cell) => cell.executionState === "idle") ??
      mathCells.find((cell) => cell.id === snapshot.selectedCellId);
    if (!target) return;
    selectAndReveal(target.id);
    await runCell(target.id);
  }, [runCell, selectAndReveal]);

  const continueExecution = useCallback(async () => {
    stopRequested.current = false;
    const pendingIds = stateRef.current.document.cells
      .filter(isMathCell)
      .filter((cell) => cell.executionState === "idle")
      .map((cell) => cell.id);
    for (const id of pendingIds) {
      if (stopRequested.current) break;
      selectAndReveal(id);
      const result = await runCell(id, false, true);
      if (result && isRootFault(result)) break;
    }
  }, [runCell, selectAndReveal]);

  const restartExecution = useCallback(() => {
    stopRequested.current = true;
    executionToken.current += 1;
    dispatch({ type: "execution/restart" });
    window.setTimeout(() => {
      const first = stateRef.current.document.cells.find(isMathCell);
      if (first) selectAndReveal(first.id);
    }, 0);
  }, [dispatch, selectAndReveal]);

  const stop = useCallback(() => {
    stopRequested.current = true;
    executionToken.current += 1;
    dispatch({ type: "execution/stop" });
  }, [dispatch]);

  const openFile = useCallback(async (fileName: string) => {
    const document = await loadNotebookFile(fileName);
    if (!document) return false;
    executionToken.current += 1;
    stopRequested.current = true;
    // tab/open reuses an already-open tab for the same file.
    tabsDispatch({
      type: "tab/open",
      tab: createNotebookTab(hydratedNotebookState(document, fileName)),
    });
    rememberLastFile(fileName);
    setSavedAt(Date.now());
    return true;
  }, []);

  const createNewDerivation = useCallback(
    async (name: string) => {
      const clean = name.trim() || "未命名推导";
      const fileName = clean.endsWith(".nm") ? clean : `${clean}.nm`;
      const document = { ...createBlankNotebook(), title: clean, fileName };
      executionToken.current += 1;
      stopRequested.current = true;
      const ok = await saveNotebookFile(fileName, document);
      const nbTab = createNotebookTab(
        hydratedNotebookState(document, fileName),
      );
      tabsDispatch({ type: "tab/open", tab: nbTab });
      rememberLastFile(fileName);
      await refreshWorkspace();
      setSavedAt(Date.now());
      // Select the first equation cell; MathCellEditor autoFocuses when it
      // becomes selected-and-editing, so the user can start typing at once.
      window.setTimeout(() => {
        const firstMath = nbTab.state.document.cells.find(isMathCell);
        if (firstMath) {
          tabsDispatch({
            type: "tab/apply",
            tabId: nbTab.id,
            action: { type: "cell/select", cellId: firstMath.id },
          });
          tabsDispatch({
            type: "tab/apply",
            tabId: nbTab.id,
            action: { type: "cell/edit", cellId: firstMath.id },
          });
        }
      }, 30);
      return ok;
    },
    [refreshWorkspace],
  );

  const renameFile = useCallback(
    async (from: string, to: string) => {
      const clean = to.trim() || "未命名推导";
      const next = clean.endsWith(".nm") ? clean : `${clean}.nm`;
      if (next === from) return { ok: true };
      const result = await renameNotebookFile(from, next);
      if (!result.ok) {
        return { ok: false, message: result.message ?? "重命名失败。" };
      }
      for (const tab of tabsStateRef.current.tabs) {
        if (tab.kind === "notebook" && tab.state.fileName === from) {
          const document = { ...tab.state.document, fileName: next, title: clean };
          tabsDispatch({
            type: "tab/apply",
            tabId: tab.id,
            action: { type: "document/load", document, fileName: next },
          });
          rememberLastFile(next);
        }
      }
      await refreshWorkspace();
      setSavedAt(Date.now());
      return { ok: true };
    },
    [refreshWorkspace],
  );

  /** Tab ids with unsaved changes, recomputed whenever content or saved
      fingerprints change. */
  const dirtyTabIds = useMemo(() => {
    const ids = new Set<string>();
    for (const tab of tabsState.tabs) {
      if (tabIsDirty(tab, savedSigs[tab.id])) ids.add(tab.id);
    }
    return ids;
  }, [tabsState.tabs, savedSigs]);

  const closeTabById = useCallback(
    (tabId: string): boolean => {
      const tab = tabsStateRef.current.tabs.find((t) => t.id === tabId);
      if (!tab) return true;
      // Dirty tabs wait for a discard confirmation before actually closing.
      if (tabIsDirty(tab, savedSigs[tabId])) {
        setPendingCloseTabId(tabId);
        return false;
      }
      executionToken.current += 1;
      stopRequested.current = true;
      tabsDispatch({ type: "tab/close", tabId });
      setSavedSigs((prev) => {
        const next = { ...prev };
        delete next[tabId];
        return next;
      });
      return true;
    },
    [savedSigs],
  );

  const confirmCloseTab = useCallback(() => {
    const tabId = pendingCloseTabId;
    setPendingCloseTabId(null);
    if (!tabId) return;
    executionToken.current += 1;
    stopRequested.current = true;
    tabsDispatch({ type: "tab/close", tabId });
    setSavedSigs((prev) => {
      const next = { ...prev };
      delete next[tabId];
      return next;
    });
  }, [pendingCloseTabId]);

  const cancelCloseTab = useCallback(() => {
    setPendingCloseTabId(null);
  }, []);

  /** Open a new blank tab matching the active tab's kind. */
  const newTab = useCallback(() => {
    const tabs = tabsStateRef.current;
    const active = tabs.tabs.find((t) => t.id === tabs.activeTabId);
    if (active?.kind === "xdlt") {
      tabsDispatch({ type: "tab/open", tab: createXdltTab(null, BLANK_XDLT) });
    } else {
      tabsDispatch({
        type: "tab/open",
        tab: createNotebookTab(
          hydratedNotebookState(createBlankNotebook(), null),
        ),
      });
    }
  }, []);

  /** Close the active derivation's tab. */
  const closeDocument = useCallback(() => {
    const nbTab = resolveNotebookTab(tabsStateRef.current);
    if (nbTab && closeTabById(nbTab.id)) {
      rememberLastFile(null);
      setSavedAt(Date.now());
    }
  }, [closeTabById]);

  const openXdltFile = useCallback(async (fileName: string) => {
    const source = await loadXdltDocument(fileName);
    if (source === null) return false;
    // tab/open reuses an already-open tab for the same file.
    tabsDispatch({ type: "tab/open", tab: createXdltTab(fileName, source) });
    rememberLastXdltFile(fileName);
    setSavedAt(Date.now());
    return true;
  }, []);

  const createNewXdlt = useCallback(
    async (name: string) => {
      const clean = name.trim() || "未命名 XDLT";
      const fileName = clean.endsWith(".xdlt") ? clean : `${clean}.xdlt`;
      tabsDispatch({ type: "tab/open", tab: createXdltTab(fileName, BLANK_XDLT) });
      const ok = await saveXdltDocument(fileName, BLANK_XDLT);
      rememberLastXdltFile(fileName);
      await refreshXdltWorkspace();
      setSavedAt(Date.now());
      return ok;
    },
    [refreshXdltWorkspace],
  );

  const renameXdltFile = useCallback(
    async (from: string, to: string) => {
      const clean = to.trim() || "未命名 XDLT";
      const next = clean.endsWith(".xdlt") ? clean : `${clean}.xdlt`;
      if (next === from) return { ok: true };
      const result = await renameXdltDocument(from, next);
      if (!result.ok) {
        return { ok: false, message: result.message ?? "重命名失败。" };
      }
      for (const tab of tabsStateRef.current.tabs) {
        if (tab.kind === "xdlt" && tab.fileName === from) {
          tabsDispatch({ type: "tab/updateXdlt", tabId: tab.id, fileName: next });
          rememberLastXdltFile(next);
        }
      }
      await refreshXdltWorkspace();
      setSavedAt(Date.now());
      return { ok: true };
    },
    [refreshXdltWorkspace],
  );

  const setXdltSource = useCallback((source: string) => {
    const tabs = tabsStateRef.current;
    const active = tabs.tabs.find((t) => t.id === tabs.activeTabId);
    const target =
      active?.kind === "xdlt"
        ? active
        : tabs.tabs.find((t) => t.id === tabs.lastXdltTabId && t.kind === "xdlt");
    if (target) {
      tabsDispatch({ type: "tab/updateXdlt", tabId: target.id, source });
    }
  }, []);

  /** Close the active XDLT tab. */
  const closeXdlt = useCallback(() => {
    const tabs = tabsStateRef.current;
    const active = tabs.tabs.find((t) => t.id === tabs.activeTabId);
    const target =
      active?.kind === "xdlt"
        ? active
        : tabs.tabs.find((t) => t.kind === "xdlt");
    if (target && closeTabById(target.id)) {
      rememberLastXdltFile(null);
      setSavedAt(Date.now());
    }
  }, [closeTabById]);

  const activateTab = useCallback((tabId: string) => {
    tabsDispatch({ type: "tab/activate", tabId });
  }, []);

  const openNotebookView = useCallback(() => {
    const tabs = tabsStateRef.current;
    const active = tabs.tabs.find((t) => t.id === tabs.activeTabId);
    if (active?.kind === "notebook") return;
    const last = tabs.tabs.find(
      (t) => t.id === tabs.lastNotebookTabId && t.kind === "notebook",
    );
    if (last) {
      tabsDispatch({ type: "tab/activate", tabId: last.id });
      return;
    }
    const any = tabs.tabs.find((t) => t.kind === "notebook");
    if (any) {
      tabsDispatch({ type: "tab/activate", tabId: any.id });
      return;
    }
    const blank = createNotebookTab(
      hydratedNotebookState(createBlankNotebook(), null),
    );
    tabsDispatch({ type: "tab/open", tab: blank });
  }, []);

  const openXdltView = useCallback(() => {
    const tabs = tabsStateRef.current;
    const active = tabs.tabs.find((t) => t.id === tabs.activeTabId);
    if (active?.kind === "xdlt") return;
    const last = tabs.tabs.find(
      (t) => t.id === tabs.lastXdltTabId && t.kind === "xdlt",
    );
    if (last) {
      tabsDispatch({ type: "tab/activate", tabId: last.id });
      return;
    }
    const any = tabs.tabs.find((t) => t.kind === "xdlt");
    if (any) {
      tabsDispatch({ type: "tab/activate", tabId: any.id });
      return;
    }
    const demo = createXdltTab();
    tabsDispatch({ type: "tab/open", tab: demo });
  }, []);

  /** Reload the active notebook from disk (discard unsaved edits); an unsaved
      blank canvas starts over fresh. */
  const reset = useCallback(() => {
    executionToken.current += 1;
    stopRequested.current = true;
    const nbTab = resolveNotebookTab(tabsStateRef.current);
    if (!nbTab) return;
    const fileName = nbTab.state.fileName;
    if (fileName) {
      void loadNotebookFile(fileName).then((document) => {
        if (document) {
          tabsDispatch({
            type: "tab/apply",
            tabId: nbTab.id,
            action: { type: "document/load", document, fileName },
          });
          setSavedAt(Date.now());
        }
      });
    } else {
      tabsDispatch({
        type: "tab/apply",
        tabId: nbTab.id,
        action: {
          type: "document/load",
          document: createBlankNotebook(),
          fileName: null,
        },
      });
      setSavedAt(Date.now());
    }
  }, []);

  const saveNow = useCallback(async () => {
    for (const tab of tabsStateRef.current.tabs) {
      if (tab.kind === "notebook" && tab.state.fileName) {
        await saveNotebookFile(tab.state.fileName, tab.state.document);
        recordSavedTab(tab);
      } else if (tab.kind === "xdlt" && tab.fileName) {
        await saveXdltDocument(tab.fileName, tab.source);
        recordSavedTab(tab);
      }
    }
    setSavedAt(Date.now());
  }, [recordSavedTab]);

  const derivationSource = useCallback(() => {
    return stateRef.current.document.cells
      .filter(isMathCell)
      .map((cell) => cell.source)
      .filter(Boolean)
      .join("\n");
  }, []);

  const evaluateProbe = useCallback(async (value: string) => {
    const source = derivationSource();
    if (!source || !value.trim()) return null;
    return mathRuntime.evaluateProbe({ source, value: value.trim() });
  }, [derivationSource]);

  const getCompletionsForSelection = useCallback(async () => {
    const snapshot = stateRef.current;
    const cell = snapshot.document.cells.find(
      (item) => item.id === snapshot.selectedCellId,
    );
    if (!cell || !isMathCell(cell) || cell.kind === "transform") return [];
    const index = snapshot.document.cells
      .filter(isMathCell)
      .findIndex((item) => item.id === cell.id);
    const lines = snapshot.document.cells
      .filter(isMathCell)
      .slice(0, index + 1)
      .map((item) => item.source);
    return mathRuntime.getCompletions(lines.join("\n"), Math.max(0, index));
  }, []);

  const applyStructuredTransform = useCallback(
    async (op: import("./transforms").TransformOp, arg?: string) => {
      const {
        formatTransformLabel,
        normalizeTransformArg,
      } = await import("./transforms");
      const snapshot = stateRef.current;
      const mathCells = snapshot.document.cells.filter(isMathCell);
      const selected = mathCells.find(
        (cell) => cell.id === snapshot.selectedCellId,
      );
      // Base = selected if it has source, else last non-empty math cell.
      const base =
        selected?.source.trim()
          ? selected
          : [...mathCells].reverse().find((cell) => cell.source.trim());
      if (!base) {
        return { ok: false as const, message: "请先写好上一步方程，再点操作。" };
      }
      const normalizedArg =
        arg !== undefined ? normalizeTransformArg(arg) : undefined;
      const result = await mathRuntime.applyStructuredTransform(
        base.source,
        op,
        normalizedArg,
      );
      if (!result.ok) {
        return { ok: false as const, message: result.message };
      }
      const label = formatTransformLabel(op, normalizedArg);
      const newId = insertCell(base.id, "math", result.line, label);
      await runCell(newId);
      selectAndReveal(newId);
      return { ok: true as const };
    },
    [insertCell, runCell, selectAndReveal],
  );

  const applyCompletion = useCallback(
    async (command: string) => {
      // Kernel completions are short keywords; route into structured ops.
      if (/因式|factor/i.test(command)) {
        await applyStructuredTransform("factor");
        return;
      }
      if (/展开|expand/i.test(command)) {
        await applyStructuredTransform("expand");
        return;
      }
      if (/平方|square/i.test(command)) {
        await applyStructuredTransform("square_both_sides");
        return;
      }
      const div = command.match(/(?:除以|divide(?:\s+by)?)\s*(.+)$/i);
      if (div) {
        await applyStructuredTransform("divide", div[1]);
        return;
      }
      // Unknown chip text: do not invent a Chinese transform cell.
      console.warn("[NeoMath] unsupported completion command", command);
    },
    [applyStructuredTransform],
  );

  const value = useMemo(
    () => ({
      state,
      dispatch,
      kernelStatus,
      kernelUrl: mathRuntime.coreBaseUrl(),
      refreshKernel,
      insertCell,
      insertRepairCell,
      applyWitnessProbe,
      duplicateCell,
      runCell,
      runAll,
      stepNext,
      continueExecution,
      restartExecution,
      stop,
      reset,
      createNewDerivation,
      closeDocument,
      openFile,
      renameFile,
      selectAndReveal,
      saveNow,
      savedAt,
      workspace,
      refreshWorkspace,
      xdltFile,
      xdltSource,
      setXdltSource,
      createNewXdlt,
      openXdltFile,
      renameXdltFile,
      closeXdlt,
      xdltWorkspace,
      refreshXdltWorkspace,
      evaluateProbe,
      getCompletionsForSelection,
      applyCompletion,
      applyStructuredTransform,
      derivationSource,
      tabs: tabsState.tabs,
      activeTabId: tabsState.activeTabId,
      activateTab,
      closeTabById,
      openNotebookView,
      openXdltView,
      dirtyTabIds,
      newTab,
      pendingCloseTabId,
      confirmCloseTab,
      cancelCloseTab,
    }),
    [
      state,
      dispatch,
      kernelStatus,
      refreshKernel,
      insertCell,
      insertRepairCell,
      applyWitnessProbe,
      duplicateCell,
      runCell,
      runAll,
      stepNext,
      continueExecution,
      restartExecution,
      stop,
      reset,
      createNewDerivation,
      closeDocument,
      openFile,
      renameFile,
      selectAndReveal,
      saveNow,
      savedAt,
      workspace,
      refreshWorkspace,
      xdltFile,
      xdltSource,
      setXdltSource,
      createNewXdlt,
      openXdltFile,
      renameXdltFile,
      closeXdlt,
      xdltWorkspace,
      refreshXdltWorkspace,
      evaluateProbe,
      getCompletionsForSelection,
      applyCompletion,
      applyStructuredTransform,
      derivationSource,
      tabsState.tabs,
      tabsState.activeTabId,
      activateTab,
      closeTabById,
      openNotebookView,
      openXdltView,
      dirtyTabIds,
      newTab,
      pendingCloseTabId,
      confirmCloseTab,
      cancelCloseTab,
    ],
  );

  return (
    <NotebookContext.Provider value={value}>{children}</NotebookContext.Provider>
  );
}

export function useNotebook() {
  const context = useContext(NotebookContext);
  if (!context) throw new Error("useNotebook must be used inside NotebookProvider");
  return context;
}

/**
 * Scoped provider for a single notebook tab. Renders the pane's components
 * against the tab's own State and routes their dispatches to that tab, while
 * inheriting every command from the parent provider.
 *
 * Used to keep all notebook panes mounted (display:none when inactive) so
 * scroll position, selection and the editing cell survive tab switches.
 */
export function NotebookTabScope({
  tab,
  children,
}: {
  tab: NotebookTab;
  children: ReactNode;
}) {
  const parent = useNotebook();
  const scopedValue = useMemo(() => {
    const scopedDispatch: Dispatch<TabAction> = (action) => {
      if (action.type.startsWith("tab/")) {
        parent.dispatch(action);
      } else {
        parent.dispatch({ type: "tab/apply", tabId: tab.id, action });
      }
    };
    return {
      ...parent,
      state: tab.state,
      dispatch: scopedDispatch,
    };
  }, [parent, tab.state, tab.id]);
  return (
    <NotebookContext.Provider value={scopedValue}>
      {children}
    </NotebookContext.Provider>
  );
}

/**
 * Scoped provider for a single XDLT tab. Binds xdltFile / xdltSource /
 * setXdltSource to the tab so its session is created once on mount and edits
 * write back to that tab only.
 */
export function XdltTabScope({
  tab,
  children,
}: {
  tab: XdltTab;
  children: ReactNode;
}) {
  const parent = useNotebook();
  const scopedValue = useMemo(() => {
    const scopedSetXdltSource = (source: string) => {
      parent.dispatch({ type: "tab/updateXdlt", tabId: tab.id, source });
    };
    return {
      ...parent,
      xdltFile: tab.fileName,
      xdltSource: tab.source,
      setXdltSource: scopedSetXdltSource,
    };
  }, [parent, tab.fileName, tab.source, tab.id]);
  return (
    <NotebookContext.Provider value={scopedValue}>
      {children}
    </NotebookContext.Provider>
  );
}
