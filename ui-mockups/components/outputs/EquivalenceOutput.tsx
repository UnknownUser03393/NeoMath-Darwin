"use client";

import { Check } from "lucide-react";
import type { EquivalenceResult } from "@/lib/notebook/types";
import { Formula } from "./Formula";

export function EquivalenceOutput({
  result,
}: {
  result: EquivalenceResult;
}) {
  return (
    <div className="equivalence-output">
      <div className="equivalence-title">
        <span>
          <Check size={14} strokeWidth={2.4} />
        </span>
        {result.title}
      </div>
      <Formula latex={result.latex} className="compact" />
      <div className="solution-unchanged">
        <span className="set-symbol">{"{=}"}</span>
        {result.solutionSet}
      </div>
    </div>
  );
}
