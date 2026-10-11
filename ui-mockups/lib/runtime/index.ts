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
import { CoreMathRuntime, coreUrl } from "./CoreMathRuntime";
import type { MathRuntime, StructuredTransformResult } from "./MathRuntime";
import { MockMathRuntime } from "./MockMathRuntime";

/**
 * Uses the real C++ MathCore when the local gateway answers a health probe;
 * otherwise stays on the offline mock so demos still run. Once the core is
 * up, real errors are surfaced instead of silently degrading to canned results.
 */
class FallbackMathRuntime implements MathRuntime {
  private core = new CoreMathRuntime();
  private mock = new MockMathRuntime();
  private coreAvailable: boolean | null = null;

  private async ensureProbed(): Promise<boolean> {
    if (this.coreAvailable === null) {
      this.coreAvailable = await this.core.ping();
      console.info(
        this.coreAvailable
          ? "[NeoMath] connected to C++ MathCore"
          : "[NeoMath] MathCore unreachable, using offline demo runtime",
      );
    }
    return this.coreAvailable;
  }

  /** Force a re-check (settings panel refresh). */
  async refreshKernel(): Promise<KernelStatus> {
    this.coreAvailable = null;
    return this.getKernelStatus();
  }

  async ping(): Promise<boolean> {
    return this.ensureProbed();
  }

  async getKernelStatus(): Promise<KernelStatus> {
    return (await this.ensureProbed()) ? "core" : "offline";
  }

  coreBaseUrl(): string {
    const url = coreUrl();
    return url === "" ? "(同进程 / 内嵌)" : url;
  }

  async evaluateProbe(request: ProbeRequest): Promise<ProbeResult | null> {
    if (await this.ensureProbed()) {
      try {
        const result = await this.core.evaluateProbe(request);
        if (result) return result;
      } catch (error) {
        this.coreAvailable = false;
        console.warn("[NeoMath] probe failed, offline fallback", error);
      }
    }
    return this.mock.evaluateProbe(request);
  }

  async getCompletions(source: string, step: number): Promise<CompletionItem[]> {
    if (await this.ensureProbed()) {
      try {
        const items = await this.core.getCompletions(source, step);
        if (items.length) return items;
      } catch (error) {
        this.coreAvailable = false;
        console.warn("[NeoMath] completions failed", error);
      }
    }
    return this.mock.getCompletions(source, step);
  }

  async applyStructuredTransform(
    baseLine: string,
    op: TransformOp,
    arg?: string,
  ): Promise<StructuredTransformResult> {
    if (await this.ensureProbed()) {
      try {
        return await this.core.applyStructuredTransform(baseLine, op, arg);
      } catch (error) {
        this.coreAvailable = false;
        console.warn("[NeoMath] structured transform failed", error);
      }
    }
    return this.mock.applyStructuredTransform(baseLine, op, arg);
  }

  async execute(
    cell: MathCell,
    context: ExecutionContext,
  ): Promise<ExecutionResult> {
    if (await this.ensureProbed()) {
      try {
        return await this.core.execute(cell, context);
      } catch (error) {
        this.coreAvailable = false;
        console.warn("[NeoMath] lost MathCore connection", error);
      }
    }
    return this.mock.execute(cell, context);
  }
}

const shared = new FallbackMathRuntime();

export const createMathRuntime = (): MathRuntime => shared;

/** Singleton with extra product helpers (status, probe, completions). */
export const mathRuntime = shared;
