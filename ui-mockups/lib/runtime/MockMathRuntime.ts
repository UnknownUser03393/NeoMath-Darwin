import type {
  CompletionItem,
  DiagnosticResult,
  EquivalenceResult,
  ExecutionContext,
  KernelStatus,
  MathCell,
  MathResult,
  ProbeRequest,
  ProbeResult,
  UnsupportedResult,
} from "@/lib/notebook/types";
import { toLatex } from "@/lib/notebook/formula";
import type { TransformOp } from "@/lib/notebook/transforms";
import type { MathRuntime, StructuredTransformResult } from "./MathRuntime";

const delay = (duration: number) =>
  new Promise<void>((resolve) => window.setTimeout(resolve, duration));

const normalize = (source: string) =>
  source
    .trim()
    .replace(/\s+/g, "")
    .replaceAll("−", "-")
    .replaceAll("×", "*")
    .toLowerCase();

export class MockMathRuntime implements MathRuntime {
  async ping(): Promise<boolean> {
    return false;
  }

  async getKernelStatus(): Promise<KernelStatus> {
    return "offline";
  }

  async evaluateProbe(request: ProbeRequest): Promise<ProbeResult | null> {
    const value = request.value.trim();
    if (!value) return null;
    // Offline demos only special-case the lost-root witness.
    if (value === "0" && request.source.includes("x - 1 = 0")) {
      return {
        value,
        previousDefined: true,
        currentDefined: true,
        previousHolds: true,
        currentHolds: false,
        previousEval: "0 = 0　成立",
        currentEval: "−1 = 0　不成立",
        reason: "solutions_lost",
      };
    }
    if (value === "1" && request.source.includes("sqrt")) {
      return {
        value,
        previousDefined: true,
        currentDefined: true,
        previousHolds: false,
        currentHolds: true,
        previousEval: "1 = −1　不成立",
        currentEval: "1 = 1　成立",
        reason: "solutions_gained",
      };
    }
    return {
      value,
      previousEval: "离线演示无法完整代回",
      currentEval: "请连接 MathCore 获取精确 Probe",
      reason: "offline",
    };
  }

  async getCompletions(source: string, _step: number): Promise<CompletionItem[]> {
    void _step;
    const n = normalize(source);
    if (n.includes("x^2-4=0") || n.includes("x²-4=0")) {
      return [
        {
          label: "因式分解",
          command: "因式分解",
          preview: "(x - 2)(x + 2) = 0",
        },
      ];
    }
    return [];
  }

  async applyStructuredTransform(
    baseLine: string,
    op: TransformOp,
    arg?: string,
  ): Promise<StructuredTransformResult> {
    const base = normalize(baseLine);
    const a = (arg ?? "").trim();
    if ((op === "divide" || op === "multiply") && !a) {
      return {
        ok: false,
        message: "请填写数学式参数（如 10 或 x），不要写中文句子",
      };
    }
    if (op === "factor" && (base.includes("x^2-4=0") || base.includes("x²-4=0"))) {
      return { ok: true, line: "(x - 2)(x + 2) = 0" };
    }
    if (op === "expand" && base.includes("(x-2)(x+2)=0")) {
      return { ok: true, line: "x^2 - 4 = 0" };
    }
    if (op === "divide" && base.includes("x(x-1)=0") && normalize(a) === "x") {
      return { ok: true, line: "x - 1 = 0" };
    }
    if (op === "square_both_sides" && base.includes("sqrt(x)=x-2")) {
      return { ok: true, line: "x = (x - 2)^2" };
    }
    if (op === "solve" && base.includes("x-1=0")) {
      return { ok: true, line: "x = 1" };
    }
    return {
      ok: false,
      message: `离线演示暂不支持对该式做「${op}」${a ? `（${a}）` : ""}。请连接 MathCore，或新建下一步。`,
    };
  }

  async execute(cell: MathCell, context: ExecutionContext) {
    const input = normalize(cell.source);
    const prev = context.previousMathCells.map((c) => normalize(c.source));

    await delay(280);

    // --- lost root story ---
    if (input === "x(x-1)=0" || input === "x*(x-1)=0") {
      if (prev.length === 0) {
        return {
          type: "math",
          latex: toLatex("x*(x - 1) = 0"),
          solutionSet: "{ 0, 1 }",
          domain: "ℝ",
          method: "exact",
          duration: "1.2 ms",
          trustLevel: "exact",
        } satisfies MathResult;
      }
      return {
        type: "equivalence",
        title: "等价变换",
        latex: "x = 0 \\quad\\text{或}\\quad x = 1",
        solutionSet: "解集保持不变",
        domain: "ℝ",
        duration: "1.0 ms",
      } satisfies EquivalenceResult;
    }

    if (input === "x-1=0" && prev.some((p) => p.includes("x(x-1)=0") || p.includes("x*(x-1)=0"))) {
      return {
        type: "diagnostic",
        code: "LOST ROOT",
        title: "这一步不等价",
        previousSet: "{ 0, 1 }",
        currentSet: "{ 1 }",
        domain: "ℝ",
        lost: ["0"],
        summary: "从 x(x − 1) = 0 直接写成 x − 1 = 0，丢掉了 x = 0 这个合法解。",
        witness: {
          value: "x = 0",
          original: "0 · (−1) = 0　成立",
          transformed: "−1 = 0　不成立",
        },
        details:
          "原方程的解集是 {0, 1}。删掉因式 x 等价于默认 x ≠ 0，因此只保留了子集。",
        repairHint: "改回 x(x − 1) = 0，或写成 x = 0 或 x = 1",
        duration: "1.4 ms",
      } satisfies DiagnosticResult;
    }

    if (input === "x=1" && prev.some((p) => p === "x-1=0")) {
      return {
        type: "diagnostic",
        code: "TAINTED",
        title: "受前面步骤影响",
        previousSet: "{ 1 }",
        currentSet: "{ 1 }",
        domain: "ℝ",
        lost: [],
        summary: "这一步本身像在求解，但它建立在已经丢根的推导上。",
        witness: {
          value: "x = 0",
          original: "原式在 x = 0 成立",
          transformed: "当前链已丢失该解",
        },
        details: "先修复引入分叉的步骤，再继续求解。",
        duration: "0.8 ms",
      } satisfies DiagnosticResult;
    }

    // transform / 除以 x
    if (
      cell.kind === "transform" &&
      (input.includes("除以x") || input.includes("同除以x") || input === "/x")
    ) {
      return {
        type: "diagnostic",
        code: "LOST ROOT",
        title: "这一步不等价",
        previousSet: "{ 0, 1 }",
        currentSet: "{ 1 }",
        domain: "ℝ",
        lost: ["0"],
        summary: "除数 x 可能为 0。直接除以 x 会移除这个合法分支。",
        witness: {
          value: "x = 0",
          original: "0² = 0　成立",
          transformed: "0 = 1　不成立",
        },
        details:
          "“两边除以 x”隐含前提 x ≠ 0；原方程并没有这个前提，因此变换只保留了原解集的子集。",
        repairHint: "改用因式分解：x(x − 1) = 0",
        duration: "1.5 ms",
      } satisfies DiagnosticResult;
    }

    // legacy sample x^2 = x
    if (input === "x^2=x" || input === "x²=x") {
      return {
        type: "math",
        latex: toLatex("x^2 = x"),
        solutionSet: "{ 0, 1 }",
        domain: "ℝ",
        method: "exact",
        duration: "1.6 ms",
      } satisfies MathResult;
    }

    // --- extraneous root ---
    if (input === "sqrt(x)=x-2") {
      return {
        type: "math",
        latex: toLatex("sqrt(x) = x - 2"),
        solutionSet: "{ 4 }",
        domain: "x ≥ 0",
        method: "exact",
        duration: "2.1 ms",
      } satisfies MathResult;
    }
    if (input === "x=(x-2)^2" && prev.some((p) => p.includes("sqrt"))) {
      return {
        type: "diagnostic",
        code: "EXTRANEOUS ROOT",
        title: "这一步可能增根",
        previousSet: "{ 4 }",
        currentSet: "{ 1, 4 }",
        domain: "ℝ",
        lost: [],
        gained: ["1"],
        summary: "两边平方只保证单向蕴含，x = 1 满足平方后方程，但不满足原式。",
        witness: {
          value: "x = 1",
          original: "1 = −1　不成立",
          transformed: "1 = 1　成立",
        },
        details: "平方映射不是单射；需要把候选解代回原方程检验。",
        repairHint: "对每个候选根代回 sqrt(x) = x − 2 检验",
        duration: "1.8 ms",
      } satisfies DiagnosticResult;
    }
    if (input === "x^2-5x+4=0") {
      return {
        type: "diagnostic",
        code: "TAINTED",
        title: "受前面步骤影响",
        previousSet: "{ 1, 4 }",
        currentSet: "{ 1, 4 }",
        domain: "ℝ",
        lost: [],
        gained: ["1"],
        summary: "展开整理在代数上成立，但建立在已增根的平方步骤之上。",
        witness: {
          value: "x = 1",
          original: "原式不成立",
          transformed: "多项式成立",
        },
        details: "先处理平方步骤引入的增根。",
        duration: "1.0 ms",
      } satisfies DiagnosticResult;
    }
    if (input === "x=1orx=4" || input === "x=1∨x=4") {
      return {
        type: "diagnostic",
        code: "TAINTED",
        title: "受前面步骤影响",
        previousSet: "{ 1, 4 }",
        currentSet: "{ 1, 4 }",
        domain: "ℝ",
        lost: [],
        gained: ["1"],
        summary: "列出的解包含增根 x = 1，需代回原式剔除。",
        witness: {
          value: "x = 1",
          original: "√1 = 1 − 2 → 不成立",
          transformed: "候选解被保留",
        },
        details: "检验后应只保留 x = 4。",
        duration: "0.9 ms",
      } satisfies DiagnosticResult;
    }

    // --- domain expansion ---
    if (input === "(x-1)/(x-1)=1") {
      return {
        type: "math",
        latex: "\\dfrac{x - 1}{x - 1} = 1",
        solutionSet: "ℝ \\ { 1 }",
        domain: "ℝ \\ { 1 }",
        method: "exact",
        duration: "1.3 ms",
      } satisfies MathResult;
    }
    if (input === "1=1" && prev.some((p) => p.includes("(x-1)/(x-1)"))) {
      return {
        type: "diagnostic",
        code: "DOMAIN SHIFT",
        title: "定义域被扩大",
        previousSet: "ℝ \\ { 1 }",
        currentSet: "ℝ",
        domain: "ℝ",
        lost: [],
        gained: ["1"],
        summary: "约去 (x − 1) 后，x = 1 从「无定义」变成了恒成立。",
        witness: {
          value: "x = 1",
          original: "0/0　未定义",
          transformed: "1 = 1　成立",
        },
        details: "化简分式必须保留原定义域约束。",
        repairHint: "在约分后注明 x ≠ 1",
        duration: "1.1 ms",
      } satisfies DiagnosticResult;
    }

    // --- semantic completion ---
    if (input === "x^2-4=0") {
      return {
        type: "math",
        latex: toLatex("x^2 - 4 = 0"),
        solutionSet: "{ -2, 2 }",
        domain: "ℝ",
        method: "exact",
        duration: "1.0 ms",
      } satisfies MathResult;
    }
    if (
      cell.kind === "transform" &&
      (input.includes("因式分解") || input.includes("factor"))
    ) {
      return {
        type: "equivalence",
        title: "等价变换",
        latex: toLatex("(x - 2)*(x + 2) = 0"),
        solutionSet: "解集保持不变",
        domain: "ℝ",
        duration: "1.2 ms",
        trustLevel: "certificate",
      } satisfies EquivalenceResult;
    }

    return {
      type: "unsupported",
      title: "离线演示范围外",
      message:
        "当前未连接 MathCore。离线模式支持四个内置 Demo 的关键步骤。请启动桌面应用或 python -m neomath --serve。",
    } satisfies UnsupportedResult;
  }
}
