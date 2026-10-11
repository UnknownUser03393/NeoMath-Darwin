"use client";

import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Plus,
  Wrench,
} from "lucide-react";
import { useState } from "react";
import type { DiagnosticResult } from "@/lib/notebook/types";
import { useNotebook } from "@/lib/notebook/commands";
import { WitnessOutput } from "./WitnessOutput";

export function DiagnosticOutput({
  result,
  cellId,
}: {
  result: DiagnosticResult;
  cellId?: string;
}) {
  const { insertRepairCell, selectAndReveal, applyWitnessProbe } = useNotebook();
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [witnessOpen, setWitnessOpen] = useState(true);
  const [probeLine, setProbeLine] = useState<string | null>(null);

  const insertFix = () => {
    if (!cellId) return;
    void insertRepairCell(cellId).then((repair) => {
      if (repair.cellId) selectAndReveal(repair.cellId);
    });
  };

  const applyWitness = () => {
    void applyWitnessProbe(result.witness.value).then((applied) => {
      if (applied.ok) {
        setProbeLine(
          `x = ${applied.value} · ${applied.result.previousEval} / ${applied.result.currentEval}`,
        );
      } else {
        setProbeLine(applied.error);
      }
    });
  };

  return (
    <div className="diagnostic-output" role="alert" aria-live="assertive">
      <div className="diagnostic-header">
        <span className="diagnostic-code">
          <AlertTriangle size={14} />
          {result.code}
        </span>
        <strong>{result.title}</strong>
      </div>
      <div className="set-diff" aria-label="解集差异">
        <div>
          <span>此前</span>
          <strong>{result.previousSet}</strong>
        </div>
        <div>
          <span>此后</span>
          <strong>{result.currentSet}</strong>
        </div>
        <div className="lost-value">
          <span>{result.lost.length ? "丢失" : "新增"}</span>
          <strong>
            {result.lost.length ? "− " : "+ "}
            {(result.lost.length ? result.lost : (result.gained ?? [])).join(", ") || "—"}
          </strong>
        </div>
      </div>
      <p className="diagnostic-summary">{result.summary}</p>
      {result.repairHint && (
        <p className="repair-hint">
          <Wrench size={13} />
          {result.repairHint}
        </p>
      )}
      <button
        className="details-toggle"
        onClick={() => setWitnessOpen((open) => !open)}
        aria-expanded={witnessOpen}
      >
        {witnessOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        反例 Witness
      </button>
      {witnessOpen && <WitnessOutput witness={result.witness} />}
      <button
        type="button"
        className="diag-action witness-apply"
        onClick={applyWitness}
        disabled={result.witness.value === "—"}
      >
        一键代回 Witness
      </button>
      {probeLine && (
        <p className="witness-probe-summary" role="status">
          {probeLine}
        </p>
      )}
      <button
        className="details-toggle"
        onClick={() => setDetailsOpen((open) => !open)}
        aria-expanded={detailsOpen}
      >
        {detailsOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        为什么会这样？
      </button>
      {detailsOpen && <p className="diagnostic-details">{result.details}</p>}
      {cellId && (
        <div className="diagnostic-actions">
          <button type="button" className="diag-action primary" onClick={insertFix}>
            <Plus size={14} />
            插入修复 Cell
          </button>
          <button
            type="button"
            className="diag-action"
            onClick={() => {
              setWitnessOpen(true);
              selectAndReveal(cellId);
            }}
          >
            查看 Witness
          </button>
        </div>
      )}
    </div>
  );
}
