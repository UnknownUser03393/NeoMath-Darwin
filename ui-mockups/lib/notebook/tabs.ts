import {
  initialNotebookState,
  notebookReducer,
  type Action,
  type State,
} from "./notebookState";
import { createBlankNotebook } from "./demos";
import { DEMO_XDLT } from "@/lib/xdlt/demo";

// ── Tab types ──────────────────────────────────────────────────────────

export type Tab = NotebookTab | XdltTab;

export interface NotebookTab {
  id: string;
  kind: "notebook";
  state: State;
}

export interface XdltTab {
  id: string;
  kind: "xdlt";
  fileName: string | null;
  source: string;
}

// ── Tabs state ─────────────────────────────────────────────────────────

export interface TabsState {
  tabs: Tab[];
  /** Active tab id, or null when all tabs are closed (empty editor). */
  activeTabId: string | null;
  /** Last-selected notebook tab id, for projecting state when xdlt is active. */
  lastNotebookTabId: string | null;
  /** Last-selected xdlt tab id, for projecting xdlt data when notebook is active. */
  lastXdltTabId: string | null;
  hydrated: boolean;
}

// ── Tab management actions ─────────────────────────────────────────────

export type TabManagementAction =
  | { type: "tab/open"; tab: Tab }
  | { type: "tab/close"; tabId: string }
  | { type: "tab/activate"; tabId: string }
  | { type: "tab/apply"; tabId: string; action: Action }
  | { type: "tab/updateXdlt"; tabId: string; fileName?: string | null; source?: string }
  | { type: "tab/replaceAll"; tabs: Tab[]; activeTabId: string | null };

export type TabAction = Action | TabManagementAction;

// ── Helpers ────────────────────────────────────────────────────────────

let nextTabId = 1;
export function freshTabId(): string {
  return `tab-${Date.now()}-${nextTabId++}`;
}

export function createNotebookTab(state?: State): NotebookTab {
  return {
    id: freshTabId(),
    kind: "notebook",
    state: state ?? {
      ...initialNotebookState,
      document: createBlankNotebook(),
      fileName: null,
    },
  };
}

export function createXdltTab(
  fileName: string | null = null,
  source: string = DEMO_XDLT,
): XdltTab {
  return {
    id: freshTabId(),
    kind: "xdlt",
    fileName,
    source,
  };
}

// ── Initial state ──────────────────────────────────────────────────────
// No tabs open on boot; the app renders an empty editor until a session is
// restored or the user opens a file explicitly.

export const initialTabsState: TabsState = {
  tabs: [],
  activeTabId: null,
  lastNotebookTabId: null,
  lastXdltTabId: null,
  hydrated: false,
};

// ── Selectors ──────────────────────────────────────────────────────────

/** Find the notebook tab that should receive dispatched actions. */
export function resolveNotebookTab(state: TabsState): NotebookTab | null {
  const active = state.tabs.find((t) => t.id === state.activeTabId);
  if (active?.kind === "notebook") return active;

  if (state.lastNotebookTabId) {
    const last = state.tabs.find(
      (t) => t.id === state.lastNotebookTabId && t.kind === "notebook",
    ) as NotebookTab | undefined;
    if (last) return last;
  }

  const any = state.tabs.find((t) => t.kind === "notebook") as
    | NotebookTab
    | undefined;
  return any ?? null;
}

/** Projected notebook state: always resolves to a valid State. */
export function projectedNotebookState(state: TabsState): State {
  const nb = resolveNotebookTab(state);
  return nb?.state ?? initialNotebookState;
}

/** Resolve the xdlt tab that should feed xdltFile / xdltSource. */
function resolveXdltTab(state: TabsState): XdltTab | null {
  const active = state.tabs.find((t) => t.id === state.activeTabId);
  if (active?.kind === "xdlt") return active;

  if (state.lastXdltTabId) {
    const last = state.tabs.find(
      (t) => t.id === state.lastXdltTabId && t.kind === "xdlt",
    ) as XdltTab | undefined;
    if (last) return last;
  }

  const any = state.tabs.find((t) => t.kind === "xdlt") as
    | XdltTab
    | undefined;
  return any ?? null;
}

export function projectedXdltFile(state: TabsState): string | null {
  return resolveXdltTab(state)?.fileName ?? null;
}

export function projectedXdltSource(state: TabsState): string {
  return resolveXdltTab(state)?.source ?? DEMO_XDLT;
}

// ── Reducer ────────────────────────────────────────────────────────────

export function tabsReducer(
  state: TabsState,
  action: TabAction,
): TabsState {
  // Tab management actions
  switch (action.type) {
    case "tab/open": {
      return openTab(state, action.tab);
    }
    case "tab/close": {
      return closeTab(state, action.tabId);
    }
    case "tab/activate": {
      const tab = state.tabs.find((t) => t.id === action.tabId);
      if (!tab) return state;
      return {
        ...state,
        activeTabId: action.tabId,
        lastNotebookTabId:
          tab.kind === "notebook"
            ? action.tabId
            : state.lastNotebookTabId,
        lastXdltTabId:
          tab.kind === "xdlt" ? action.tabId : state.lastXdltTabId,
      };
    }
    case "tab/apply": {
      const tabIndex = state.tabs.findIndex((t) => t.id === action.tabId);
      if (tabIndex < 0 || state.tabs[tabIndex].kind !== "notebook")
        return state;
      const tab = state.tabs[tabIndex] as NotebookTab;
      const newState = notebookReducer(tab.state, action.action);
      if (newState === tab.state) return state;
      const newTabs = [...state.tabs];
      newTabs[tabIndex] = { ...tab, state: newState };
      return { ...state, tabs: newTabs };
    }
    case "tab/updateXdlt": {
      const tabIndex = state.tabs.findIndex((t) => t.id === action.tabId);
      if (tabIndex < 0 || state.tabs[tabIndex].kind !== "xdlt") return state;
      const tab = state.tabs[tabIndex] as XdltTab;
      const next = {
        ...tab,
        ...(action.fileName !== undefined ? { fileName: action.fileName } : {}),
        ...(action.source !== undefined ? { source: action.source } : {}),
      };
      if (next.fileName === tab.fileName && next.source === tab.source)
        return state;
      const newTabs = [...state.tabs];
      newTabs[tabIndex] = next;
      return { ...state, tabs: newTabs };
    }
    case "tab/replaceAll": {
      const lastNb =
        [...action.tabs].reverse().find((t) => t.kind === "notebook")?.id ??
        null;
      const lastXd =
        [...action.tabs].reverse().find((t) => t.kind === "xdlt")?.id ?? null;
      return {
        tabs: action.tabs,
        activeTabId: action.activeTabId,
        lastNotebookTabId: lastNb,
        lastXdltTabId: lastXd,
        hydrated: true,
      };
    }
    default: {
      // Route notebook actions to the resolved notebook tab
      const target = resolveNotebookTab(state);
      if (!target) return state;
      const newState = notebookReducer(target.state, action);
      if (newState === target.state) return state;
      const idx = state.tabs.findIndex((t) => t.id === target.id);
      const newTabs = [...state.tabs];
      newTabs[idx] = { ...target, state: newState };
      return { ...state, tabs: newTabs };
    }
  }
}

// ── Tab open / close helpers ───────────────────────────────────────────

function openTab(state: TabsState, tab: Tab): TabsState {
  // Reuse existing tab by fileName match
  if (tab.kind === "notebook") {
    const existing = state.tabs.find(
      (t) =>
        t.kind === "notebook" &&
        t.state.fileName !== null &&
        t.state.fileName === tab.state.fileName,
    ) as NotebookTab | undefined;
    if (existing) {
      // Update existing tab state (e.g. if file was reloaded)
      const idx = state.tabs.findIndex((t) => t.id === existing.id);
      const newTabs = [...state.tabs];
      newTabs[idx] = tab;
      return {
        ...state,
        tabs: newTabs,
        activeTabId: existing.id,
        lastNotebookTabId: existing.id,
      };
    }
  } else {
    const existing = state.tabs.find(
      (t) =>
        t.kind === "xdlt" &&
        t.fileName !== null &&
        t.fileName === tab.fileName,
    ) as XdltTab | undefined;
    if (existing) {
      const idx = state.tabs.findIndex((t) => t.id === existing.id);
      const newTabs = [...state.tabs];
      newTabs[idx] = tab;
      return {
        ...state,
        tabs: newTabs,
        activeTabId: existing.id,
        lastXdltTabId: existing.id,
      };
    }
  }

  // Append new tab
  return {
    ...state,
    tabs: [...state.tabs, tab],
    activeTabId: tab.id,
    lastNotebookTabId:
      tab.kind === "notebook" ? tab.id : state.lastNotebookTabId,
    lastXdltTabId:
      tab.kind === "xdlt" ? tab.id : state.lastXdltTabId,
  };
}

function closeTab(state: TabsState, tabId: string): TabsState {
  const newTabs = state.tabs.filter((t) => t.id !== tabId);

  if (newTabs.length === 0) {
    // Allow zero tabs: closing the last tab leaves an empty editor.
    return {
      ...state,
      tabs: [],
      activeTabId: null,
      lastNotebookTabId: null,
      lastXdltTabId: null,
    };
  }

  let newActiveId = state.activeTabId;
  let lastNbId = state.lastNotebookTabId;
  let lastXdId = state.lastXdltTabId;

  if (state.activeTabId === tabId) {
    const closedIdx = state.tabs.findIndex((t) => t.id === tabId);
    const newIdx = Math.min(closedIdx, newTabs.length - 1);
    newActiveId = newTabs[newIdx].id;
  }

  // Update last- pointers if the closed tab was the last of its kind
  if (tabId === state.lastNotebookTabId) {
    lastNbId =
      newTabs.find((t) => t.kind === "notebook")?.id ?? null;
  }
  if (tabId === state.lastXdltTabId) {
    lastXdId =
      newTabs.find((t) => t.kind === "xdlt")?.id ?? null;
  }

  const newActive = newTabs.find((t) => t.id === newActiveId);
  if (newActive?.kind === "notebook") {
    lastNbId = newActiveId;
  } else if (newActive?.kind === "xdlt") {
    lastXdId = newActiveId;
  }

  return {
    ...state,
    tabs: newTabs,
    activeTabId: newActiveId,
    lastNotebookTabId: lastNbId,
    lastXdltTabId: lastXdId,
  };
}
