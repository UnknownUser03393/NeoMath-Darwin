"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Check, Circle, LoaderCircle, OctagonAlert, Trash2 } from "lucide-react";
import { useNotebook } from "@/lib/notebook/commands";
import { isRootFault, type NotebookCell } from "@/lib/notebook/types";
import { MathCellView } from "./MathCell";

interface Props {
  cell: NotebookCell;
  index: number;
  isSelected: boolean;
  isEditing: boolean;
}

export function NotebookCellView({ cell, index, isSelected }: Props) {
  const { dispatch } = useNotebook();
  const reduce = useReducedMotion();
  if (cell.kind === "markdown") return null;

  const fault = isRootFault(cell.result);
  const status = fault
    ? "breakpoint"
    : cell.executionState === "success"
      ? "verified"
      : cell.executionState === "running"
        ? "running"
        : cell.executionState === "error"
          ? "unsupported"
          : "pending";

  return (
    <article
      id={`cell-${cell.id}`}
      className={`debug-step ${isSelected ? "selected" : ""} ${status}`}
      tabIndex={0}
      onClick={() => dispatch({ type: "cell/select", cellId: cell.id })}
      aria-label={`推导步骤 ${index + 1}`}
    >
      <div className="step-gutter">
        <span className="step-line-number">{String(index + 1).padStart(2, "0")}</span>
        <span className="step-node" aria-hidden="true">
          {status === "breakpoint" ? (
            <OctagonAlert size={18} fill="currentColor" />
          ) : status === "verified" ? (
            <Check size={15} strokeWidth={3} />
          ) : status === "running" ? (
            <motion.span
              style={{ display: "inline-flex" }}
              initial={false}
              animate={{ rotate: reduce ? 0 : 360 }}
              transition={{ repeat: Infinity, duration: 0.9, ease: "linear" }}
            >
              <LoaderCircle size={17} />
            </motion.span>
          ) : (
            <Circle size={13} />
          )}
        </span>
        <button
          type="button"
          className="step-delete"
          onClick={() => dispatch({ type: "cell/delete", cellId: cell.id })}
          aria-label={`删除步骤 ${index + 1}`}
          title="删除此步"
        >
          <Trash2 size={13} />
        </button>
      </div>
      <MathCellView cell={cell} />
      <div className="step-status-label">
        {status === "breakpoint"
          ? "PAUSED"
          : status === "verified"
            ? "EQUIVALENT"
            : status === "running"
              ? "CHECKING"
              : status === "unsupported"
                ? "UNSUPPORTED"
                : "NOT RUN"}
      </div>
    </article>
  );
}
