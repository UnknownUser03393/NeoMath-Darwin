"use client";

import type { ExecutionResult } from "@/lib/notebook/types";
import { DiagnosticOutput } from "./DiagnosticOutput";
import { EquivalenceOutput } from "./EquivalenceOutput";
import { MathOutput } from "./MathOutput";

export function ExecutionOutput({
  result,
  cellId,
}: {
  result: ExecutionResult;
  cellId?: string;
}) {
  switch (result.type) {
    case "math":
      return <MathOutput result={result} />;
    case "diagnostic":
      return <DiagnosticOutput result={result} cellId={cellId} />;
    case "equivalence":
      return <EquivalenceOutput result={result} />;
    case "unsupported":
      return (
        <div className="unsupported-output" role="alert">
          <strong>{result.title}</strong>
          <p>{result.message}</p>
        </div>
      );
  }
}
