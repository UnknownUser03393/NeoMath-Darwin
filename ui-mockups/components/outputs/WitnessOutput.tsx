"use client";

import { TestTube2, X } from "lucide-react";
import type { DiagnosticResult } from "@/lib/notebook/types";

export function WitnessOutput({
  witness,
}: {
  witness: DiagnosticResult["witness"];
}) {
  return (
    <div className="witness-output">
      <div className="witness-heading">
        <TestTube2 size={14} />
        反例 / WITNESS
      </div>
      <div className="witness-value">{witness.value}</div>
      <div className="witness-checks">
        <div>
          <span>原式</span>
          <strong>{witness.original}</strong>
        </div>
        <div className="failed">
          <span>新式</span>
          <strong>{witness.transformed}</strong>
          <X size={14} aria-label="不成立" />
        </div>
      </div>
    </div>
  );
}
