"use client";

import {
  FastForward,
  RotateCcw,
  Save,
  Square,
  StepForward,
} from "lucide-react";
import { useNotebook } from "@/lib/notebook/commands";
import { isMathCell, isRootFault } from "@/lib/notebook/types";

export function NotebookToolbar() {
  const {
    state,
    continueExecution,
    stepNext,
    restartExecution,
    stop,
    saveNow,
  } = useNotebook();
  const steps = state.document.cells.filter(isMathCell);
  const completed = steps.filter((cell) => cell.executionState === "success").length;
  const breakpoint = steps.find((cell) => isRootFault(cell.result));
  const hasStarted = steps.some((cell) => cell.executionState !== "idle");
  const hasPending = steps.some((cell) => cell.executionState === "idle");

  return (
    <div className="debug-toolbar" role="toolbar" aria-label="推导调试工具栏">
      <button
        className="debug-command primary"
        data-demo-id="toolbar-continue"
        onClick={() => void continueExecution()}
        disabled={state.kernelRunning || !hasPending}
        title="运行到第一处语义分叉"
      >
        <FastForward size={15} fill="currentColor" />
        {hasStarted ? "继续" : "开始调试"}
        <kbd>F5</kbd>
      </button>
      <button
        className="debug-command"
        data-demo-id="toolbar-step"
        onClick={() => void stepNext()}
        disabled={state.kernelRunning || !hasPending}
        title="只验证下一步"
      >
        <StepForward size={15} />
        单步
        <kbd>F10</kbd>
      </button>
      {state.kernelRunning ? (
        <button className="debug-command danger" onClick={stop}>
          <Square size={13} fill="currentColor" />
          停止
        </button>
      ) : (
        <button className="debug-command" data-demo-id="toolbar-restart" onClick={restartExecution} disabled={!hasStarted}>
          <RotateCcw size={14} />
          重新开始
        </button>
      )}
      <span className="debug-toolbar-separator" />
      <div data-demo-id="session-state" className={`session-state ${breakpoint ? "paused" : hasPending ? "ready" : "done"}`}>
        <span className="session-state-dot" />
        {breakpoint
          ? `已在步骤 ${steps.indexOf(breakpoint) + 1} 暂停`
          : hasPending
            ? `待验证 ${steps.length - completed} 步`
            : "推导验证完成"}
      </div>
      <div className="debug-toolbar-spacer" />
      <button className="icon-command" onClick={saveNow} aria-label="保存" title="保存">
        <Save size={15} />
      </button>
    </div>
  );
}
