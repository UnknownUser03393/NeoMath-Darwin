import type { TransformOp } from "@/lib/notebook/transforms";
import type {
  CompletionItem,
  ExecutionContext,
  ExecutionResult,
  KernelStatus,
  MathCell,
  ProbeRequest,
  ProbeResult,
} from "@/lib/notebook/types";

export type StructuredTransformResult =
  | { ok: true; line: string }
  | { ok: false; message: string };

export interface MathRuntime {
  execute(
    cell: MathCell,
    context: ExecutionContext,
  ): Promise<ExecutionResult>;
  ping(): Promise<boolean>;
  getKernelStatus(): Promise<KernelStatus>;
  evaluateProbe(request: ProbeRequest): Promise<ProbeResult | null>;
  getCompletions(source: string, step: number): Promise<CompletionItem[]>;
  /** Apply a catalog op + optional math arg; never free Chinese. */
  applyStructuredTransform(
    baseLine: string,
    op: TransformOp,
    arg?: string,
  ): Promise<StructuredTransformResult>;
}
