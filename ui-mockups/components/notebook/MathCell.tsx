"use client";

import { useState } from "react";
import { FlaskConical, Play, Split, Wrench } from "lucide-react";
import { useNotebook } from "@/lib/notebook/commands";
import { analysisFromResult, type MathCell } from "@/lib/notebook/types";
import { summarizeProbeResult } from "@/lib/notebook/witnessProbe";
import { MathCellEditor } from "./MathCellEditor";

export function MathCellView({ cell }: { cell: MathCell }) {
  const { state, dispatch, runCell, insertRepairCell, applyWitnessProbe } =
    useNotebook();
  const analysis = analysisFromResult(cell.result);
  const diagnostic = cell.result?.type === "diagnostic" ? cell.result : null;
  const [probeSummary, setProbeSummary] = useState<string | null>(null);
  const [probeBusy, setProbeBusy] = useState(false);
  const [repairHint, setRepairHint] = useState<string | null>(null);

  const onApplyWitness = async () => {
    if (!diagnostic) return;
    setProbeBusy(true);
    try {
      const applied = await applyWitnessProbe(diagnostic.witness.value);
      if (applied.ok) {
        setProbeSummary(
          `x = ${applied.value} · ${summarizeProbeResult(applied.result)} · ${applied.result.previousEval} / ${applied.result.currentEval}`,
        );
      } else {
        setProbeSummary(applied.error);
      }
    } finally {
      setProbeBusy(false);
    }
  };

  const onInsertRepair = async () => {
    const result = await insertRepairCell(cell.id);
    if (result.suggestion) {
      const preview = result.suggestion.preview?.trim();
      setRepairHint(
        preview
          ? `已插入建议：${result.suggestion.label}${preview ? ` → ${preview}` : ""}`
          : `已插入建议：${result.suggestion.label}`,
      );
    } else if (result.suggestions.length === 0) {
      setRepairHint("已插入修复单元格。当前步骤没有可用的自动变形建议，请新建下一步。");
    } else {
      setRepairHint(
        `已插入修复单元格，并附带 ${result.suggestions.length} 条可验证变形建议。`,
      );
    }
  };

  return (
    <div className="step-main">
      <div className="step-operation">
        <span className="step-label">{cell.label || "推导"}</span>
        <MathCellEditor
          id={cell.id}
          value={cell.source}
          autoFocus={
            state.selectedCellId === cell.id && state.editingCellId === cell.id
          }
          onChange={(source) =>
            dispatch({ type: "cell/updateSource", cellId: cell.id, source })
          }
          onRun={() => void runCell(cell.id)}
          onEscape={() => {
            dispatch({ type: "cell/edit", cellId: null });
            document.getElementById(`cell-${cell.id}`)?.focus();
          }}
          onFocus={() => {
            dispatch({ type: "cell/select", cellId: cell.id });
            dispatch({ type: "cell/edit", cellId: cell.id });
          }}
        />
        <button
          className="step-run"
          data-demo-id="step-run"
          onClick={() => void runCell(cell.id)}
          aria-label="验证此步"
          title="验证此步"
          disabled={state.kernelRunning}
        >
          <Play size={13} fill="currentColor" />
        </button>
      </div>

      {diagnostic ? (
        <div className="step-break-banner" data-demo-id="step-break-banner">
          <div className="break-symbol"><Split size={16} /></div>
          <div>
            <span>{diagnostic.code}</span>
            <strong>{diagnostic.summary}</strong>
            <p data-demo-id="diagnostic-summary">
              解集 {diagnostic.previousSet} → {diagnostic.currentSet}
              <b> · Witness {diagnostic.witness.value}</b>
            </p>
            {probeSummary && (
              <p className="witness-probe-summary" data-demo-id="witness-probe-summary" role="status">
                {probeSummary}
              </p>
            )}
            {repairHint && (
              <p className="repair-suggestion-hint" role="status">
                {repairHint}
              </p>
            )}
          </div>
          <div className="break-actions">
            <button
              type="button"
              className="witness-apply"
              data-demo-id="witness-apply"
              onClick={() => void onApplyWitness()}
              disabled={probeBusy || diagnostic.witness.value === "—"}
              title="把 Witness 填入 Probe 并代回验证"
            >
              <FlaskConical size={13} />
              {probeBusy ? "代回中…" : "一键代回"}
            </button>
            <button type="button" onClick={() => void onInsertRepair()}>
              <Wrench size={13} />
              在此修复
            </button>
          </div>
        </div>
      ) : analysis ? (
        <div className="step-result-strip" data-demo-id="step-result-strip">
          <span>解集 <strong>{analysis.solutionSet}</strong></span>
          <span>定义域 <strong>{analysis.domain}</strong></span>
          <span className="verified-copy">✓ 等价变形</span>
        </div>
      ) : null}
    </div>
  );
}