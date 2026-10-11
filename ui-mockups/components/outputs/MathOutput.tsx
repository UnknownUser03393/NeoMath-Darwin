"use client";

import type { MathResult } from "@/lib/notebook/types";
import { Formula } from "./Formula";

export function MathOutput({ result }: { result: MathResult }) {
  return (
    <div className="math-output">
      <Formula latex={result.latex} />
      <div className="solution-line">
        <span>解集</span>
        <strong>{result.solutionSet}</strong>
      </div>
      {result.domain && (
        <div className="solution-line domain-line">
          <span>定义域</span>
          <strong>{result.domain}</strong>
        </div>
      )}
      <div className="execution-meta">
        <span className="valid-mark" aria-hidden="true">
          ✓
        </span>
        {result.method} <span>·</span> {result.duration}
      </div>
    </div>
  );
}
