"use client";

import { useState } from "react";
import { AlertCircle, ChevronDown, Sigma } from "lucide-react";
import { useNotebook } from "@/lib/notebook/commands";
import {
  TRANSFORM_CATALOG,
  type TransformOp,
  type TransformSpec,
} from "@/lib/notebook/transforms";
import { isMathCell } from "@/lib/notebook/types";

const specByOp = (op: TransformOp): TransformSpec =>
  TRANSFORM_CATALOG.find((item) => item.op === op) as TransformSpec;

/** 「双向运算」= 对等式两边同时做同一件事（平方 / 除以 / 乘以）。 */
const BOTH_SIDES: TransformSpec[] = [
  specByOp("square_both_sides"),
  specByOp("divide"),
  specByOp("multiply"),
];

/**
 * Structured transform toolbar.
 * Ops are buttons; divide/multiply args are math, never Chinese prose.
 */
export function TransformPalette() {
  const { state, applyStructuredTransform } = useNotebook();
  const [busyOp, setBusyOp] = useState<TransformOp | null>(null);
  const [argOp, setArgOp] = useState<TransformOp | null>(null);
  const [argValue, setArgValue] = useState("");
  const [error, setError] = useState("");
  const [bothSidesOpen, setBothSidesOpen] = useState(false);

  const mathCells = state.document.cells.filter(isMathCell);
  const selected = mathCells.find((cell) => cell.id === state.selectedCellId);
  const base = selected?.source.trim()
    ? selected
    : [...mathCells].reverse().find((cell) => cell.source.trim());
  const canApply = Boolean(base?.source.trim()) && !state.kernelRunning;

  const run = async (op: TransformOp, arg?: string) => {
    setError("");
    setBusyOp(op);
    try {
      const result = await applyStructuredTransform(op, arg);
      if (!result.ok) {
        setError(result.message);
        return;
      }
      setArgOp(null);
      setArgValue("");
      setBothSidesOpen(false);
    } finally {
      setBusyOp(null);
    }
  };

  const onPick = (spec: TransformSpec) => {
    setError("");
    if (!canApply) {
      setError("请先写好上一步方程，再选操作。");
      return;
    }
    if (spec.needsArg) {
      setArgOp(spec.op);
      setArgValue("");
      return;
    }
    void run(spec.op);
  };

  const mainChips: Array<TransformSpec | { kind: "bothSides" }> = [
    specByOp("factor"),
    specByOp("expand"),
    { kind: "bothSides" },
    specByOp("move_terms"),
    specByOp("solve"),
  ];

  return (
    <div className="transform-palette" role="region" aria-label="工具栏">
      <div className="transform-palette-head">
        <div>
          <strong>工具栏</strong>
        </div>
      </div>

      <div className="transform-base" title={base?.source || undefined}>
        <Sigma size={13} />
        <code>{base?.source.trim() || "未选择上一步"}</code>
      </div>

      <div className="transform-chips">
        {mainChips.map((chip) =>
          "kind" in chip ? (
            <button
              key="bothSides"
              type="button"
              className={`transform-chip group ${bothSidesOpen ? "active" : ""}`}
              disabled={!canApply || busyOp !== null}
              onClick={() => setBothSidesOpen((open) => !open)}
            >
              双向运算
              <ChevronDown size={12} className="group-chevron" />
            </button>
          ) : (
            <button
              key={chip.op}
              type="button"
              className={`transform-chip ${argOp === chip.op ? "active" : ""}`}
              disabled={!canApply || busyOp !== null}
              title={chip.hint}
              onClick={() => onPick(chip)}
            >
              {busyOp === chip.op ? "…" : chip.label}
            </button>
          ),
        )}
      </div>

      {bothSidesOpen && (
        <div className="transform-subchips">
          {BOTH_SIDES.map((spec) => (
            <button
              key={spec.op}
              type="button"
              className={`transform-chip ${argOp === spec.op ? "active" : ""}`}
              disabled={!canApply || busyOp !== null}
              title={spec.hint}
              onClick={() => onPick(spec)}
            >
              {busyOp === spec.op ? "…" : spec.label}
            </button>
          ))}
        </div>
      )}

      {argOp && (
        <div className="transform-arg-row">
          <label htmlFor="transform-arg">
            {argOp === "divide" ? "除数（数学式）" : "乘数（数学式）"}
          </label>
          <input
            id="transform-arg"
            className="transform-arg-input"
            value={argValue}
            autoFocus
            placeholder={
              TRANSFORM_CATALOG.find((item) => item.op === argOp)
                ?.argPlaceholder ?? "x 或 10"
            }
            onChange={(event) => setArgValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void run(argOp, argValue);
              }
              if (event.key === "Escape") {
                setArgOp(null);
                setArgValue("");
              }
            }}
          />
          <button
            type="button"
            className="transform-arg-apply"
            disabled={!argValue.trim() || busyOp !== null}
            onClick={() => void run(argOp, argValue)}
          >
            应用并验证
          </button>
          <button
            type="button"
            className="transform-arg-cancel"
            onClick={() => {
              setArgOp(null);
              setArgValue("");
            }}
          >
            取消
          </button>
        </div>
      )}

      {error && (
        <div className="transform-error" role="alert">
          <AlertCircle size={14} />
          {error}
        </div>
      )}
    </div>
  );
}
