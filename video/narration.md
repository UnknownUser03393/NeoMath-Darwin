# NeoMath 演示视频 — 旁白文稿

目标时长：3:50（允许 3:30 ~ 4:20）
语言：中文自然口语

---

## 00:00–00:12 · Scene 01 — Hook
画面：recording.html `hook` 场景。NeoMath 标题 → 副标题 → 标语 → 核心问题。
操作：step 0 → step 1

旁白：
大家好，我是于东海，南京外国语学校初一。
我做的项目叫 NeoMath——一个数学动态调试环境。

---

## 00:12–00:32 · Scene 02 — Problem
画面：recording.html `problem` 场景。数学推导动画展示丢根过程。
操作：step 0（方程）→ step 1（解集对比）→ step 2（LOST ROOT）→ step 3（验证）

旁白：
做数学推导的时候，最难发现的错误不是算错一个数字，
而是在两行之间悄悄丢掉一个根、增加一个根，或者改变了定义域。

比如 x 乘以 x 减一等于零，两边除以 x 之后——
解集从零和一，变成了只有一。
零就这样丢了。

普通的搜题工具通常只给你最终答案，
却说不清到底是哪一步出了问题。

---

## 00:32–00:48 · Scene 03 — Workflow
画面：recording.html `workflow` 场景。调试循环逐步展开。
操作：step 0 → step 1 → step 2 → step 3

旁白：
所以我借用了程序调试器的思路。

把每一步推导看成一个程序状态，
把数学错误看成 Bug。

写推导、运行、在错误处中断、解释原因、修复、然后增量回放。

---

## 00:48–01:35 · Scene 04 — Hero Product Demo
画面：真实 NeoMath UI（record-product.mjs 录制）
操作：
- 打开 Lost Root Demo
- 点击 Continue (F5)
- 等待 Root Fault 出现
- 聚焦 Diagnostic 面板
- 查看解集差异：{0,1} → {1}
- 聚焦 Witness: x = 0
- 点击"一键代回 Witness"
- 查看验证结果：原式成立、新式不成立

旁白：
现在我们来实际运行一下。

这里有三步推导：x 乘以 x 减一等于零，x 减一等于零，x 等于一。
点运行。

它在第二步暂停了——检测到 Root Fault，也就是丢根。

看这里：此前的解集是零和一，此后只剩一了。

下面有一个 Witness，也就是反例——x 等于零。

我点一键代回：
x 等于零代入原式，零乘以负一等于零，成立。
代入新式，零减一等于零，不成立。

这就是一个你可以亲手验算的、具体的反例。

---

## 01:35–01:58 · Scene 05 — One More Capability
画面：真实 NeoMath UI（语义补全 Demo）
操作：
- 切换到语义补全 Demo
- 运行
- 展示 Completion Bar 或 Transform Palette
- 选择因式分解
- 展示变换结果和 Certificate

旁白：
NeoMath 不只能检测错误。

比如 x 的平方减四等于零——
我可以用语义补全来分解它。

这不是字符串替换：
C++ 内核会生成因式分解结果，
并输出一个 Transformation Certificate——变换证书，
证明这一步变形是等价的。

---

## 01:58–02:23 · Scene 06 — XDLT
画面：真实 NeoMath UI（XDLT 工作区）
操作：
- 切换到 XDLT 模式
- 展示 .hw 源码
- 做一个小编辑
- 展示预览更新 + Debug Panel（patch / latency）

旁白：
我还尝试了另一件事——
把数学写作本身做成一种可编译的语言。

左边是 .hw 源文件，右边是实时预览。
我修改一处内容——编译器只重算被影响的节点，
debug 面板里能看到哪些节点被重新验证、延迟是多少。

文档不再是排版结果，而是带语义的源码。

---

## 02:23–02:48 · Scene 07 — Trust Model
画面：recording.html `trust-model` 场景
操作：step 0 → step 1 → step 2

旁白：
这里我要特别说一下 AI 在这个项目里的角色。

我没有让大模型直接判断数学对错。

AI 可以帮忙把学生的自然语言翻译成操作意图，
也可以帮忙解释结果。

但是——
解集、定义域、反例、变换证书，
这些数学结论全部来自本地的 C++ 数学内核。

所有 AI 建议必须穿过验证边界，
由确定性代码验证之后才会被采纳。

---

## 02:48–03:08 · Scene 08 — Engineering Evidence
画面：recording.html `engineering` 场景
操作：step 0 → step 1

旁白：
支撑这些功能的是工程上的验证。

258 个 Python 测试，全部通过。
一万组 SymPy 差分验证，零差异。
二百步推导的端到端延迟，P95 大约三毫秒。
增量回放只重算改变的一步，其余一百九十九个状态直接复用。

---

## 03:08–03:32 · Scene 09 — AI Collaboration
画面：先 recording.html `ai-collaboration`，然后切真实 IDE 录像
操作：
- 展示协作循环图
- 切换到 IDE 画面
- 展示真实 AI 编程过程

旁白：
最后说说我是怎么开发这个项目的。

整个过程是人和 AI 编程工具的协作循环——
我提出想法，AI Agent 生成代码，
然后运行测试，根据结果继续迭代。

比如这段——我让 Agent 帮我写一个新的测试用例，
它分析了现有代码，写了实现，测试通过了。

AI 是真正的生产力工具，
但它生成的每一行代码最终都要通过测试来验证。

---

## 03:32–03:50 · Scene 10 — Reflection
画面：recording.html `reflection` → `end` 场景
操作：reflection step 0 → step 1 → end step 0

旁白：
这个项目让我意识到：
AI 最有价值的地方，
未必是替人给出答案，
而是帮我们构建更可靠的工具。

NeoMath 目前只覆盖有限的一元实数代数。
不能证明的内容，它会明确返回 Unverified——
而不是假装自己知道。

谢谢大家。
