"use client";

import { Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { useNotebook } from "@/lib/notebook/commands";
import { isMathCell, type CompletionItem } from "@/lib/notebook/types";

/**
 * Light semantic-completion strip under the canvas when the selected math
 * cell has available completions (e.g. factor x^2 - 4 = 0).
 */
export function CompletionBar() {
  const {
    state,
    getCompletionsForSelection,
    applyCompletion,
  } = useNotebook();
  const [items, setItems] = useState<CompletionItem[]>([]);
  const [busy, setBusy] = useState(false);

  const selected = state.document.cells.find(
    (cell) => cell.id === state.selectedCellId,
  );
  const selectedSource = selected && isMathCell(selected) ? selected.source : "";
  const eligible =
    selected &&
    isMathCell(selected) &&
    selected.kind === "math" &&
    selectedSource.trim().length > 0;

  useEffect(() => {
    let cancelled = false;
    const handle = window.setTimeout(() => {
      if (!eligible) {
        setItems([]);
        return;
      }
      void getCompletionsForSelection().then((next) => {
        if (!cancelled) setItems(next);
      });
    }, 200);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
  }, [eligible, selected?.id, selectedSource, getCompletionsForSelection]);

  if (!items.length) return null;

  return (
    <div className="completion-bar" role="region" aria-label="语义补全" data-demo-id="completion-bar">
      <div className="completion-bar-label">
        <Sparkles size={14} />
        语义补全
      </div>
      <div className="completion-bar-items">
        {items.map((item) => (
          <button
            key={item.command}
            type="button"
            className="completion-chip"
            data-demo-id={`completion-chip-${item.command}`}
            disabled={busy || state.kernelRunning}
            onClick={() => {
              setBusy(true);
              void applyCompletion(item.command).finally(() => setBusy(false));
            }}
            title={item.preview || item.command}
          >
            <strong>{item.label}</strong>
            {item.preview && <span>{item.preview}</span>}
          </button>
        ))}
      </div>
    </div>
  );
}
