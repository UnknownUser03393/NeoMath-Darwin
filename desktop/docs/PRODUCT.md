# NeoMath 产品定义

## 一句话定位

NeoMath 是面向中学生的**单变量实数代数推导调试器**——把每一行数学推导当作可运行的数学状态，
在步骤间发现语义分叉时，给出**能亲手代回去验证的精确反例**，而不是画一个红叉。

---

## 产品形态

NeoMath 是一个桌面应用（Windows 10/11 x64），通过 pywebview 提供原生窗口，
内核是 C++20 MathCore（精确有理数计算），React UI 以 AOT 静态构建方式嵌入。

用户界面有两个核心页面：

1. **Notebook 页**：数学推导调试器。每个 Cell 是一行数学命题，运行后展示解集、定义域、
   等价性诊断和 Witness 反例。四个内置 Demo 展示核心工作流。
2. **XDLT 页**：可编译数学写作环境。左侧 `.hw` 源码编辑器 → 右侧实时 HTML 预览。
   定理、证明、断言验证、可执行代码块在同一份源码中表达。

---

## 工作流

```text
Write → Complete → Run → Break → Explain → Fix → Replay
 写推导    语义补全     运行     首错即停     教学解释     插入修复     增量重放
```

| 环节 | 做什么 | 真值来源 | 关键输出 |
|---|---|---|---|
| Write | 逐行输入数学命题（等式 / 表达式） | — | AST |
| Complete | 按 `Ctrl+Space` 获得语义补全建议 | C++ MathCore 状态分析 | 变换候选列表 |
| Run | 解析、求定义域、求解集、判等价 | C++ MathCore | 每步 MathState |
| Break | 停在第一个可证明的语义分叉 | C++ MathCore | Root Fault + Tainted |
| Explain | 翻译诊断为 ≤ 120 字学生语言 | 本地模板 / AI 措辞 | Diagnostic 文本 |
| Fix | 一键修复或变换面板操作 | C++ MathCore 验证 | 新 Cell + Certificate |
| Replay | 修改后增量重放，复用未变状态 | C++ MathCore Trace 缓存 | cacheHits |

---

## 目标用户

| 角色 | 典型场景 | 核心价值 |
|---|---|---|
| **中学生**（主要） | 课后自查一元代数推导，理解"为什么错" | 每一步都可验证，错误能亲眼看到 Witness |
| **数学教师** | 课堂演示丢根 / 增根 / 定义域扩大的精确语义 | 不是空口说"你错了"，而是有数学证据 |
| **竞赛 / 自学** | 训练严谨推导习惯 | 条件等价、证书、Unverified 边界培养数学严谨性 |
| **开发者 / 研究者** | 学习可编译数学写作 | `.hw` 语言 + 增量编译器 + 知识卡 + 可执行块 |

---

## 核心价值主张

不是"告诉学生答案"，也不是"告诉学生错了"——而是：

> **给出一个精确有理数，让学生亲手代回验证，亲眼看到在哪一步、为什么、值是多少。**

三个差异化：
1. **Witness 是可验证的**：来自解集 / 定义域的精确差集，不是随机抽样或概率建议
2. **语义分叉有分类**：丢根 / 增根 / 定义域扩大——每类有精确的数学定义和检测机制
3. **AI 有边界**：AI 只改写措辞，不碰数学真值——即便是离线，核心功能完全不受影响

---

## 定位边界（NOT）

NeoMath **不是**：

| 不是 | 替代工具 |
|---|---|
| 拍照搜题工具 | Photomath, Gauthmath |
| 通用 CAS（计算机代数系统） | Mathematica, Maple |
| 标准答案生成器 | Wolfram Alpha |
| 完整 LaTeX 编辑器 | Overleaf, TeXShop |
| 形式化证明助手 | Lean, Coq |
| 通用数学教育平台 | Khan Academy |

**能力边界内的行为**：
- 支持范围：单变量 `x`、有理系数、次数 ≤ 2、简单分式、`sqrt(linear) = linear`
- 超出范围时：明确返回 `Unverified` 或 `Unsupported`，并给出改写建议
- 绝不把启发式结果包装成 `Verified`

---

## 创新点

1. **推导即程序**：把丢根 / 增根 / 定义域扩大定义为可证明的语义分叉
2. **精确反例代替红叉**：Witness 来自差集的精确有理数，能亲手代回
3. **AI 不碰数学真值**：一切数学结论由 C++ 本地计算，AI 只改措辞
4. **数学写作可编译**：`.hw` 语言 + 增量编译器 + 补丁级预览
5. **增量重放**：改一处只重算受影响子树

---

## 当前状态

- C++ MathCore：✅ 可用，8 个 API 方法通过 pybind11 暴露
- edlatex 文档模型：✅ Phase 1-4 完成
- XDLT 编译器：✅ 主要完成（parser → semantic → graph → verify → render → exec → cards → session）
- XDLT UI：✅ 已接线（workspace + 补丁运行时 + 调试面板）
- 测试：258 pytest + 12 Catch2 + 24 node:test + 10,000 SymPy 差分（0 差异）
- 下一步：Phase 5 数学调试器、Phase 6 扩展后端

详见 [EDLATEX_PLAN.md](../EDLATEX_PLAN.md)。
