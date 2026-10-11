"use client";

import { Plus } from "lucide-react";
import { useNotebook } from "@/lib/notebook/commands";
import { isMathCell } from "@/lib/notebook/types";
import { NotebookCellView } from "./NotebookCell";
import { CompletionBar } from "./CompletionBar";
import { TransformPalette } from "./TransformPalette";

export function NotebookCanvas() {
  const { state, insertCell } = useNotebook();
  const intro = state.document.cells.find((cell) => cell.kind === "markdown");
  const introLines = intro?.source.split("\n") ?? [];
  const description = introLines.slice(1).join(" ");
  const mathSteps = state.document.cells.filter(isMathCell);

  return (
    <div className="canvas-scroll debugger-canvas-scroll">
      <section className="derivation-program" data-demo-id="derivation-program" aria-label={state.document.title}>
        <header className="program-header">
          <h1>{state.document.title}</h1>
          {description && <p>{description}</p>}
        </header>

        <div className="program-column-head" aria-hidden="true">
          <span>行</span>
          <span>推导步骤</span>
          <span>验证状态</span>
        </div>

        <div className="step-sequence">
          {mathSteps.map((cell, index) => (
            <NotebookCellView
              key={cell.id}
              cell={cell}
              index={index}
              isSelected={state.selectedCellId === cell.id}
              isEditing={state.editingCellId === cell.id}
            />
          ))}
        </div>

        <button
          className="append-step"
          data-demo-id="append-step"
          onClick={() => insertCell(mathSteps.at(-1)?.id ?? null, "math")}
        >
          <Plus size={14} />
          新建
        </button>
        <TransformPalette />
        <CompletionBar />
      </section>
    </div>
  );
}