import type { NotebookDocument } from "./types";

export type DemoId =
  | "lost-root"
  | "extraneous-root"
  | "domain-expansion"
  | "semantic-completion";

export interface DemoMeta {
  id: DemoId;
  fileName: string;
  title: string;
  prefix: string;
  blurb: string;
}

export const DEMO_CATALOG: DemoMeta[] = [
  {
    id: "lost-root",
    fileName: "丢根.nm",
    title: "方程变形中的丢根",
    prefix: "×",
    blurb: "两边同除以 x 会悄悄丢掉 x = 0",
  },
  {
    id: "extraneous-root",
    fileName: "平方增根.nm",
    title: "平方带来的增根",
    prefix: "±",
    blurb: "两边平方只保证单向蕴含，可能引入新解",
  },
  {
    id: "domain-expansion",
    fileName: "定义域扩大.nm",
    title: "约分与定义域扩大",
    prefix: "∈",
    blurb: "约去 (x−1) 会把原式无定义的点放进来",
  },
  {
    id: "semantic-completion",
    fileName: "语义补全.nm",
    title: "语义补全与因式分解",
    prefix: "∴",
    blurb: "从当前方程状态给出可验证的变形，而不是字符串模板",
  },
];

const idle = {
  executionState: "idle" as const,
  outputCollapsed: false,
};

/** Fresh notebook documents for the four built-in demos (ASCII sources for MathCore). */
export function createDemoNotebook(id: DemoId): NotebookDocument {
  const now = Date.now();
  switch (id) {
    case "lost-root":
      return {
        id: "demo-lost-root",
        title: "方程变形中的丢根",
        fileName: "丢根.nm",
        updatedAt: now,
        cells: [
          {
            id: "intro",
            kind: "markdown",
            source:
              "# 方程变形中的丢根",
            ...idle,
          },
          {
            id: "step-1",
            kind: "math",
            label: "原方程",
            source: "x(x - 1) = 0",
            ...idle,
          },
          {
            id: "step-2",
            kind: "math",
            label: "错误变形",
            source: "x - 1 = 0",
            ...idle,
          },
          {
            id: "step-3",
            kind: "math",
            label: "继续求解",
            source: "x = 1",
            ...idle,
          },
        ],
      };
    case "extraneous-root":
      return {
        id: "demo-extraneous-root",
        title: "平方带来的增根",
        fileName: "平方增根.nm",
        updatedAt: now,
        cells: [
          {
            id: "intro",
            kind: "markdown",
            source:
              "# 平方带来的增根\n两边平方可以把根式方程变成多项式，但只保证「新方程的解 ⊇ 原方程的解」。多出来的解需要代回检验。",
            ...idle,
          },
          {
            id: "step-1",
            kind: "math",
            label: "原方程",
            source: "sqrt(x) = x - 2",
            ...idle,
          },
          {
            id: "step-2",
            kind: "math",
            label: "两边平方",
            source: "x = (x - 2)^2",
            ...idle,
          },
          {
            id: "step-3",
            kind: "math",
            label: "展开整理",
            source: "x^2 - 5x + 4 = 0",
            ...idle,
          },
          {
            id: "step-4",
            kind: "math",
            label: "求解",
            source: "x = 1 or x = 4",
            ...idle,
          },
        ],
      };
    case "domain-expansion":
      return {
        id: "demo-domain-expansion",
        title: "约分与定义域扩大",
        fileName: "定义域扩大.nm",
        updatedAt: now,
        cells: [
          {
            id: "intro",
            kind: "markdown",
            source:
              "# 约分与定义域扩大\n约去分子分母的公共因式看起来「化简」了，却可能把原来无定义的点悄悄放进定义域。",
            ...idle,
          },
          {
            id: "step-1",
            kind: "math",
            label: "原方程",
            source: "(x - 1) / (x - 1) = 1",
            ...idle,
          },
          {
            id: "step-2",
            kind: "math",
            label: "约分后",
            source: "1 = 1",
            ...idle,
          },
        ],
      };
    case "semantic-completion":
      return {
        id: "demo-semantic-completion",
        title: "语义补全与因式分解",
        fileName: "语义补全.nm",
        updatedAt: now,
        cells: [
          {
            id: "intro",
            kind: "markdown",
            source:
              "# 语义补全\n对下面的方程运行「因式分解」变形（或使用工具栏旁的补全）。C++ 内核会验证变换证书，而不是只做字符串替换。",
            ...idle,
          },
          {
            id: "step-1",
            kind: "math",
            label: "原方程",
            source: "x^2 - 4 = 0",
            ...idle,
          },
          {
            id: "step-2",
            kind: "transform",
            label: "语义变形",
            source: "因式分解",
            ...idle,
          },
        ],
      };
  }
}

/** A blank derivation the user owns: an editable intro plus one empty
    first equation. Not tied to any demo (demoId will be null). */
export function createBlankNotebook(): NotebookDocument {
  const now = Date.now();
  return {
    id: `blank-${now}`,
    title: "未命名推导",
    fileName: "未命名推导.nm",
    updatedAt: now,
    cells: [
      {
        id: "intro",
        kind: "markdown",
        source: "# 未命名推导",
        ...idle,
      },
      {
        id: "step-1",
        kind: "math",
        label: "原方程",
        source: "",
        ...idle,
      },
    ],
  };
}

export function createSampleNotebook(): NotebookDocument {
  return createDemoNotebook("lost-root");
}

export function demoIdFromDocument(document: NotebookDocument): DemoId | null {
  const match = DEMO_CATALOG.find(
    (demo) =>
      document.id === `demo-${demo.id}` || document.fileName === demo.fileName,
  );
  return match?.id ?? null;
}

export function defaultSelectedCell(document: NotebookDocument): string | null {
  const firstMath = document.cells.find(
    (cell) => cell.kind === "math" || cell.kind === "transform",
  );
  return firstMath?.id ?? document.cells[0]?.id ?? null;
}
