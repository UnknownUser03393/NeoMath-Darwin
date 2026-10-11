import { createBlankNotebook, defaultSelectedCell } from "./demos";
import {
  isMathCell,
  type CellKind,
  type ExecutionResult,
  type NotebookCell,
  type NotebookDocument,
} from "./types";

export interface State {
  document: NotebookDocument;
  /** The open file ("X.nm") on disk, or null for an unsaved blank canvas. */
  fileName: string | null;
  selectedCellId: string | null;
  editingCellId: string | null;
  kernelRunning: boolean;
  hydrated: boolean;
}

export type Direction = "up" | "down";

export type Action =
  | { type: "hydrate"; document: NotebookDocument; fileName: string | null }
  | { type: "cell/select"; cellId: string | null }
  | { type: "cell/edit"; cellId: string | null }
  | { type: "cell/updateSource"; cellId: string; source: string }
  | {
      type: "cell/insertAfter";
      cellId: string | null;
      kind: CellKind;
      newId: string;
      source?: string;
      label?: string;
    }
  | { type: "cell/delete"; cellId: string }
  | { type: "cell/duplicate"; cellId: string; newId: string }
  | { type: "cell/move"; cellId: string; direction: Direction }
  | { type: "cell/toggleOutput"; cellId: string }
  | { type: "cell/executionStarted"; cellId: string }
  | {
      type: "cell/executionFinished";
      cellId: string;
      result: ExecutionResult;
      count: number;
    }
  | { type: "execution/stop" }
  | { type: "execution/restart" }
  | { type: "document/load"; document: NotebookDocument; fileName: string | null };

export const initialNotebookState: State = {
  document: createBlankNotebook(),
  fileName: null,
  selectedCellId: null,
  editingCellId: null,
  kernelRunning: false,
  hydrated: false,
};

export const touch = (state: State, cells: NotebookCell[]): State => ({
  ...state,
  document: { ...state.document, cells, updatedAt: Date.now() },
});

export function notebookReducer(state: State, action: Action): State {
  const cells = state.document.cells;
  switch (action.type) {
    case "hydrate":
      return {
        ...state,
        document: action.document,
        fileName: action.fileName,
        selectedCellId: defaultSelectedCell(action.document),
        hydrated: true,
      };
    case "cell/select":
      return { ...state, selectedCellId: action.cellId };
    case "cell/edit":
      return { ...state, editingCellId: action.cellId };
    case "cell/updateSource":
      return touch(
        state,
        cells.map((cell) =>
          cell.id === action.cellId
            ? { ...cell, source: action.source, result: undefined }
            : cell,
        ),
      );
    case "cell/insertAfter": {
      const newCell: NotebookCell =
        action.kind === "markdown"
          ? {
              id: action.newId,
              kind: "markdown",
              source: action.source ?? "在这里写下说明…",
              executionState: "idle",
              outputCollapsed: false,
            }
          : {
              id: action.newId,
              kind: action.kind,
              source: action.source ?? "",
              executionState: "idle",
              outputCollapsed: false,
              label:
                action.label ??
                (action.source === undefined ? "修复推导" : undefined),
            };
      const index = action.cellId
        ? cells.findIndex((cell) => cell.id === action.cellId)
        : cells.length - 1;
      const next = [...cells];
      next.splice(index + 1, 0, newCell);
      return {
        ...touch(state, next),
        selectedCellId: action.newId,
        editingCellId: action.newId,
      };
    }
    case "cell/delete": {
      if (cells.length <= 1) return state;
      const index = cells.findIndex((cell) => cell.id === action.cellId);
      const next = cells.filter((cell) => cell.id !== action.cellId);
      const fallback = next[Math.min(index, next.length - 1)]?.id ?? null;
      return {
        ...touch(state, next),
        selectedCellId: fallback,
        editingCellId: null,
      };
    }
    case "cell/duplicate": {
      const index = cells.findIndex((cell) => cell.id === action.cellId);
      if (index < 0) return state;
      const clone = {
        ...cells[index],
        id: action.newId,
        executionCount: undefined,
        executionState: "idle" as const,
        ...(isMathCell(cells[index]) ? { result: undefined } : {}),
      };
      const next = [...cells];
      next.splice(index + 1, 0, clone);
      return {
        ...touch(state, next),
        selectedCellId: action.newId,
        editingCellId: action.newId,
      };
    }
    case "cell/move": {
      const index = cells.findIndex((cell) => cell.id === action.cellId);
      const target = action.direction === "up" ? index - 1 : index + 1;
      if (index < 0 || target < 0 || target >= cells.length) return state;
      const next = [...cells];
      [next[index], next[target]] = [next[target], next[index]];
      return touch(state, next);
    }
    case "cell/toggleOutput":
      return touch(
        state,
        cells.map((cell) =>
          cell.id === action.cellId
            ? { ...cell, outputCollapsed: !cell.outputCollapsed }
            : cell,
        ),
      );
    case "cell/executionStarted":
      return {
        ...touch(
          state,
          cells.map((cell) =>
            cell.id === action.cellId
              ? { ...cell, executionState: "running" as const }
              : cell,
          ),
        ),
        kernelRunning: true,
      };
    case "cell/executionFinished":
      return {
        ...touch(
          state,
          cells.map((cell) =>
            cell.id === action.cellId
              ? {
                  ...cell,
                  executionState:
                    action.result.type === "diagnostic" ||
                    action.result.type === "unsupported"
                      ? ("error" as const)
                      : ("success" as const),
                  executionCount: action.count,
                  outputCollapsed: false,
                  ...(isMathCell(cell) ? { result: action.result } : {}),
                }
              : cell,
          ),
        ),
        kernelRunning: false,
      };
    case "execution/stop":
      return {
        ...touch(
          state,
          cells.map((cell) =>
            cell.executionState === "running" ||
            cell.executionState === "queued"
              ? { ...cell, executionState: "idle" as const }
              : cell,
          ),
        ),
        kernelRunning: false,
      };
    case "execution/restart":
      return {
        ...touch(
          state,
          cells.map((cell) =>
            isMathCell(cell)
              ? {
                  ...cell,
                  executionState: "idle" as const,
                  executionCount: undefined,
                  result: undefined,
                }
              : cell,
          ),
        ),
        selectedCellId:
          cells.find((cell) => isMathCell(cell))?.id ?? state.selectedCellId,
        editingCellId: null,
        kernelRunning: false,
      };
    case "document/load":
      return {
        ...state,
        document: action.document,
        fileName: action.fileName,
        selectedCellId: defaultSelectedCell(action.document),
        editingCellId: null,
        kernelRunning: false,
      };
  }
}
