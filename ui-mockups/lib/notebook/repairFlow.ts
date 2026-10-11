/**
 * Insert-repair after a root fault: create a math cell and surface the
 * best completion / suggested next step from the real completions path.
 */

import type { CompletionItem } from "./types";

/**
 * Prefer a completion that carries a concrete equation preview (ready to
 * drop into the repair cell). Fall back to the first available item.
 */
export function selectRepairSuggestion(
  completions: readonly CompletionItem[],
): CompletionItem | null {
  if (!completions.length) return null;
  const withPreview = completions.find(
    (item) => typeof item.preview === "string" && item.preview.trim().length > 0,
  );
  return withPreview ?? completions[0] ?? null;
}

/** Source line for the new repair cell (preview equation when present). */
export function repairCellSourceFromSuggestion(
  suggestion: CompletionItem | null,
): string {
  if (!suggestion) return "";
  const preview = suggestion.preview?.trim();
  if (preview) return preview;
  return "";
}

export function repairCellLabelFromSuggestion(
  suggestion: CompletionItem | null,
): string {
  if (!suggestion) return "修复推导";
  const label = suggestion.label?.trim();
  return label ? `建议：${label}` : "修复推导";
}

/**
 * Build the payload for inserting a repair cell after a root-fault step.
 * Completions must come from the shipped runtime (`getCompletions`).
 */
export function buildRepairInsert(
  completions: readonly CompletionItem[],
): {
  source: string;
  label: string;
  suggestion: CompletionItem | null;
  suggestions: CompletionItem[];
} {
  const suggestion = selectRepairSuggestion(completions);
  return {
    source: repairCellSourceFromSuggestion(suggestion),
    label: repairCellLabelFromSuggestion(suggestion),
    suggestion,
    suggestions: [...completions],
  };
}
