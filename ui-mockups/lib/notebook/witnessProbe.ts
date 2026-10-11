/**
 * Witness → Probe apply path. Pure parse + orchestration over a probe
 * evaluator so tests drive the same helpers the UI buttons call.
 */

import type { ProbeResult } from "./types";

/** Extract rational text from Witness display forms like "x = 0" or "0". */
export function parseWitnessValue(witnessValue: string): string | null {
  const raw = witnessValue.trim();
  if (!raw || raw === "—") return null;
  const match = raw.match(/^(?:x\s*=\s*)?(.+)$/i);
  const value = (match?.[1] ?? raw).trim();
  if (!value || value === "—") return null;
  return value;
}

export type ApplyWitnessResult =
  | { ok: true; value: string; result: ProbeResult }
  | { ok: false; value?: string; error: string };

/**
 * One user action: parse Witness → evaluateProbe → return hold/fail text.
 * `evaluateProbe` must be the shipped notebook runtime path (mock or core).
 */
export async function applyWitnessToProbe(
  evaluateProbe: (value: string) => Promise<ProbeResult | null>,
  witnessValue: string,
): Promise<ApplyWitnessResult> {
  const value = parseWitnessValue(witnessValue);
  if (!value) {
    return { ok: false, error: "当前诊断没有可用的 Witness 值。" };
  }
  const result = await evaluateProbe(value);
  if (!result) {
    return {
      ok: false,
      value,
      error: "Probe 未能返回结果。请确认推导已运行，并连接 MathCore 或使用离线演示。",
    };
  }
  return { ok: true, value, result };
}

/** Short status for inspector strip: holds / fails / offline. */
export function summarizeProbeResult(result: ProbeResult): string {
  if (result.reason === "offline") {
    return "离线演示 · 请连接 MathCore 获取精确代回";
  }
  const prev =
    result.previousHolds === true
      ? "前式成立"
      : result.previousHolds === false
        ? "前式不成立"
        : result.previousDefined === false
          ? "前式无定义"
          : "前式已检查";
  const curr =
    result.currentHolds === true
      ? "后式成立"
      : result.currentHolds === false
        ? "后式不成立"
        : result.currentDefined === false
          ? "后式无定义"
          : "后式已检查";
  return `${prev} → ${curr}`;
}
