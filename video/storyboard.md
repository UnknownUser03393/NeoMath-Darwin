# NeoMath 演示视频 — 分镜脚本

## 总览

| # | 场景 | 时间 | 来源 | 主要内容 |
|---|------|------|------|----------|
| 01 | Hook | 0:00–0:12 | recording.html | 标题 + 核心问题 |
| 02 | Problem | 0:12–0:32 | recording.html | 丢根问题动画演示 |
| 03 | Workflow | 0:32–0:48 | recording.html | 调试循环 |
| 04 | Hero Demo | 0:48–1:35 | 真实 UI | Lost Root Demo 完整流程 |
| 05 | Completion | 1:35–1:58 | 真实 UI | 语义补全 + Certificate |
| 06 | XDLT | 1:58–2:23 | 真实 UI | .hw 编辑 + 增量编译 |
| 07 | Trust | 2:23–2:48 | recording.html | AI ≠ Math Truth |
| 08 | Engineering | 2:48–3:08 | recording.html | 测试/性能数据 |
| 09 | AI Collab | 3:08–3:32 | recording.html + IDE | AI 协作过程 |
| 10 | Reflection | 3:32–3:50 | recording.html | 总结 + 结束 |

总时长：约 3:50

---

## Scene 01 — Hook (0:00–0:12)

**画面来源：** recording.html `?scene=hook`

**Step 0 (0:00–0:06):**
- NeoMath 大标题渐入
- "The Debugger for Mathematics" 紧随
- 分隔线
- "把数学当程序运行，把错误当 Bug 调试。"

**Step 1 (0:06–0:12):**
- "答案错了，究竟是从哪一步开始错的？"

**旁白：** 自我介绍 + 项目名称

---

## Scene 02 — Problem (0:12–0:32)

**画面来源：** recording.html `?scene=problem`

**Step 0 (0:12–0:17):**
- x(x − 1) = 0
- ↓ 两边除以 x
- x − 1 = 0

**Step 1 (0:17–0:22):**
- 解集对比框：{0, 1} → {1}

**Step 2 (0:22–0:27):**
- LOST ROOT 标记 + "x = 0 在变形中丢失"

**Step 3 (0:27–0:32):**
- Witness x = 0
- 原式 ✓ 成立
- 新式 ✕ 不成立

**旁白：** 解释丢根问题，为什么搜题工具不够

---

## Scene 03 — Workflow (0:32–0:48)

**画面来源：** recording.html `?scene=workflow`

**Step 0 (0:32–0:36):** Write + Complete
**Step 1 (0:36–0:39):** → Run
**Step 2 (0:39–0:42):** → Break (高亮)
**Step 3 (0:42–0:48):** → Explain → Fix → Replay

**旁白：** 借用调试器思路

---

## Scene 04 — Hero Product Demo (0:48–1:35)

**画面来源：** 真实 NeoMath UI（record-product.mjs）

**操作序列：**
1. (0:48–0:54) 打开 Lost Root Demo，等待加载
2. (0:54–1:00) 点击 Continue (F5)，等待 Root Fault
3. (1:00–1:10) 聚焦 Diagnostic 面板，查看解集 diff
4. (1:10–1:20) 聚焦 Witness 区域
5. (1:20–1:30) 点击"一键代回 Witness"
6. (1:30–1:35) 聚焦验证结果

**旁白：** 逐步解说操作和结果

---

## Scene 05 — Semantic Completion (1:35–1:58)

**画面来源：** 真实 NeoMath UI（record-product.mjs）

**操作序列：**
1. (1:35–1:40) 切换到语义补全 Demo
2. (1:40–1:48) 运行，展示补全建议
3. (1:48–1:53) 选择因式分解
4. (1:53–1:58) 展示结果 + Certificate

**旁白：** 不只检测错误，还能验证变形

---

## Scene 06 — XDLT (1:58–2:23)

**画面来源：** 真实 NeoMath UI（record-product.mjs）

**操作序列：**
1. (1:58–2:05) 切换到 XDLT 模式
2. (2:05–2:13) 展示 .hw 源码 + 预览
3. (2:13–2:18) 做一个小编辑
4. (2:18–2:23) 展示 Debug Panel 更新

**旁白：** 数学写作 = 可编译的源码

---

## Scene 07 — Trust Model (2:23–2:48)

**画面来源：** recording.html `?scene=trust-model`

**Step 0 (2:23–2:30):** AI ≠ Math Truth
**Step 1 (2:30–2:36):** AI 框 + 箭头
**Step 2 (2:36–2:48):** Validation Boundary + C++ MathCore 框 + 结论

**旁白：** AI 不判断对错，数学结论来自确定性内核

---

## Scene 08 — Engineering (2:48–3:08)

**画面来源：** recording.html `?scene=engineering`

**Step 0 (2:48–2:52):** 标题
**Step 1 (2:52–3:08):** 四个指标卡片渐入

**旁白：** 258 tests, 10000 differential, P95 latency, incremental replay

---

## Scene 09 — AI Collaboration (3:08–3:32)

**画面来源：**
- (3:08–3:16) recording.html `?scene=ai-collaboration`
- (3:16–3:32) 真实 IDE 录像（record-ide.mjs）

**旁白：** 人 + AI 协作循环，真实开发过程

---

## Scene 10 — Reflection (3:32–3:50)

**画面来源：** recording.html `?scene=reflection` → `?scene=end`

**Step 0 (3:32–3:38):** AI 可以生成代码…但可靠性需要边界
**Step 1 (3:38–3:44):** 不能证明 → Unverified
**End (3:44–3:50):** NeoMath 标题 + 姓名 · 年级

**旁白：** 总结感悟 + 致谢
