# NeoMath.Darwin — UI Specification

**Version 0.1 · Design proposal · 2026-10-04**  
**Canvas-first mathematical reasoning for iPad**

> 一张可以自由书写、圈选、检查和回改的数学画布。让证据出现在笔迹旁边，而不是让人离开思考现场去操作一台调试机器。

| 文档属性 | 约定 |
| --- | --- |
| 主要平台 | iPadOS；按窗口空间适配，不按 iPad 型号分页面 |
| 原生方向 | SwiftUI 应用壳与状态驱动组件；笔迹与高频输入允许独立的原生画布实现 |
| 核心体验 | Infinite Canvas、Apple Pencil、圈选、实时关联高亮、右侧 Inspector、可回改笔迹 |
| 视觉方向 | 冷中性、清楚、原生、留白充分；内容稳定，控制层轻盈；丰富但有因果的动画 |
| 文案基准 | 英文用于设计稿与组件示例；配套中文本地化；内部状态名保持英文 |
| 功能依据 | `NEOMATH_DARWIN_FUNCTIONAL_SPEC.md`，2026-10-04 工作目录扫描 |
| 本文性质 | UI 与交互的目标规范，不是实现完成报告，不扩张已有数学能力 |
| 随附文件 | `NEOMATH_DARWIN_DESIGN_TOKENS.json`，本文数值的机器可读映射 |

## 0. 阅读规则与决策边界

### 0.1 三种依据必须分开

**[B] 功能基线**：来自功能文档；引用写作 `[B §4.4]`。其中“已有后端”“已有界面”“规划”仍保持原来的区别。

**[D] 本次设计决定**：本文规定应该怎样交互、呈现和降级。除特别声明为基线的内容外，本文所有尺寸、动画、页面、工作流和组件均属设计提案，不代表当前 React 或 Darwin 已实现。

**[P] 平台依据**：少量 Apple 官方资料，只用于 Pencil 事件与系统可访问性边界。文末列出已核对来源；未确定最低系统版本，也不凭 API 存在推断所有设备支持。

### 0.2 目标体验与实现阶段不混写

功能基线将 Pencil 批注、手写公式识别列为新增 P2；当前数学编辑仍是 textarea。本稿依据已讨论的产品方向，把 **Canvas + Pencil** 定为目标体验主轴，但不把它们改写成“已有能力”。手写识别是独立交付门槛。没有识别器时，仍能书写、批注、键盘输入和运行真实内核，不能用演示识别伪装上线。[B §5.3、§14.1、§14.4]

| 层 | 目标界面 | 基线状态 | 没有能力时 |
| --- | --- | --- | --- |
| 本机推导 | 状态、关系、精确反例、Probe、变换证书 | 桌面 C++ 已有，需 Darwin 迁移 | 源文可编辑；结果显示 Kernel unavailable |
| 空间画布 | 笔迹、公式对象、推导组、圈选、联动检查器 | 本次新增设计 | 键盘步骤视图仍可完成核心工作流 |
| 数学手写识别 | 笔迹 → 候选式 → 确认 → 步骤 | 未实现 | 保留笔迹；Offer “Type equation”，不制造候选 |
| XDLT 写作 | Source / Preview / Split、诊断、上下文 | 桌面实现，迁移路线待定 | 保留源码；逐能力报告不可用 |
| edlatex | 独立模型导入、结构检查、导出 | 后端已有 | 只读保留不支持节点，不能假装与 Notebook 等价 |
| Python、PDF、同步 | 显式执行、真实导出、文件状态 | 有缺口或未实现 | 不展示假运行、假导出、假同步成功 |

### 0.3 不在本文擅自决定的事项

最低 iPadOS 版本、发布渠道、收费方式、数学识别提供者、Python/SymPy 运行位置、远端服务、云同步方案与正式新文件后缀仍未确定。UI 对这些事项提供能力门控和失败状态；实现前须作独立技术决策。本文不引入题库、班级后台、账号首页或在线卡片市场。[B §2.2、§14、§15]

---

## 1. 产品性格与不可破坏的原则

### 1.1 第一眼应该是什么

打开文档首先看到数学内容和可继续书写的空间。顶部只有文档导航与少量动作；笔工具靠近手，检查器靠近当前问题；没有默认铺满屏幕的卡片、控制台、统计指标或 AI 对话。

**主视觉是“数学正在被理解”，不是“软件正在工作”。**

界面具有两种密度：书写时安静，检查时精确。用户打开 Inspector 后增加证据密度，但不更换整个应用的审美或操作体系。

### 1.2 六条硬规则

| ID | 规则 | 实际约束 |
| --- | --- | --- |
| UX-01 | 内容先于工具 | 文件侧栏默认收起；调试统计默认藏入详情；不把所有操作常驻顶栏 |
| UX-02 | 空间连续 | 选区、检查器、Witness、变换预览指向同一对象；打开面板不把书写位置推走 |
| UX-03 | 输入不等于结论 | 笔迹、识别候选、已提交公式、验证结果分别可见且可追溯 |
| UX-04 | 状态诚实 | 未知、不支持、未运行、过期、失败、演示数据不能显示绿色“等价” |
| UX-05 | 直接操作可撤销 | 移动、增删、替换、识别确认、变换应用都进入统一文档历史 |
| UX-06 | 强能力可发现 | Squeeze、Hover、外接键盘只加速操作，不是功能唯一入口 |

### 1.3 明确禁止的外观

不做米白纸张配衬线大标题与暖橙按钮；不做企业 Dashboard；不做 IDE Activity Bar 的等比例 iPad 移植；不做整屏磨砂玻璃、渐变大按钮、发光公式、成功撒花或红色整页错误。数学字体可以是适合公式排版的字体，但 UI 标题不因此改成衬线体。

---

## 2. 信息架构

### 2.1 全局层级

```text
Documents
  Recent / Browse / Examples
  New: Derivation / Writing
  Import

Document window
  Notebook: Canvas / Steps                 ← 同一文档的两种视图
    Canvas tools
    Inspector: Overview / Evidence / Details
    Transform preview
    Recognition review
    Presentation mode
  XDLT: Source / Preview / Split           ← 写作文档，不是 Notebook 的第三个视图
    Outline / Diagnostics / Context / Cards
  edlatex document                         ← 独立模型工作位
    Structured read/edit where supported
    Context / Migration report / Export

Settings
  Appearance / Input / Mathematics / Execution / AI / Files / About
```

Notebook 与 XDLT 共享文档外壳、保存提示和命令体系，不共享一套假想的万能 AST。`.nm`、`.edlatex.json` 和 XDLT 不靠重命名互转。[B §2.3、§7.2、§8.1]

### 2.2 导航规则

一个窗口聚焦一份文档；文档列表可切换文件。多窗口是增强能力，窗口自己的选区、视口、Inspector 和运行队列不能串到另一窗口。未实现安全文件协调前，不开放同一文档的并行可写窗口。[B §14.1、§15.2]

不设置全局底部 Tab Bar：Canvas / Steps 是当前文档的表现方式，不是五个独立产品模块。文件搜索作用于文档；画布内 Find 作用于已提交公式、标签与文字，不宣传搜索未识别笔迹。

### 2.3 屏幕与状态编号

| ID | 屏幕/关键状态 | 必须交付的变体 |
| --- | --- | --- |
| S01 | Documents | 首次空白、最近文档、提供者不可用、导入中 |
| S02 | Canvas / Idle | 空画布、已有推导、未选中、仅笔迹 |
| S03 | Canvas / Selected | 单式、多式、跨组、长式、选区部分在屏外 |
| S04 | Recognition review | 候选、歧义、失败、不可用、已过期 |
| S05 | Inspector | 初始状态、等价、条件、首错、上游影响、未知 |
| S06 | Witness & Probe | 自动证据、手动值、未定义、无法判断、请求失败 |
| S07 | Transform | 无参数、有参数、条件、不可用、预览过期 |
| S08 | Repair | 替换、从正确上游另建组、后续仍有问题 |
| S09 | Steps | 线性编辑、键盘弹起、结构重排、大字号 |
| S10 | Writing | Source、Preview、Split、诊断、执行被阻止 |
| S11 | Context & Cards | 条件冲突、缺失卡片、绑定未知、版本差异 |
| S12 | Files & Recovery | 保存失败、草稿恢复、版本冲突、迁移报告 |
| S13 | Export | 范围、含过期结果、unsupported、失败 |
| S14 | Settings | 本机能力、AI 无密钥、不可用后端、外观与输入 |
| S15 | Present | 单步揭示、证据放大、演示复位 |

---

## 3. 布局系统

所有几何数值均为本稿的 **pt 设计目标**，以扣除系统安全区后的实际可用宽高为输入。系统工具栏、窗口控制和键盘优先于自绘几何；不锁死系统栏高度。

### 3.1 标准宽屏：Canvas + Inspector

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ ‹ Documents     Lost roots ▾           Undo  Redo    Check ▾    Inspect  …  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                  ┌───────────────────────┐ │
│        Group A                                   │ Step 1 → 2        ×   │ │
│                                                  │ Lost solution         │ │
│  1     x(x − 1) = 0                              │                       │ │
│           │                                      │ Before     After      │ │
│           └─ Lost solution                       │ {0, 1}     {1}        │ │
│  2   ┌ x − 1 = 0 ─────────────┐                 │                       │ │
│      └────────────────────────┘                 │ Witness   x = 0       │ │
│  3     x = 1       Affected by step 2             │ True       False      │ │
│                                                  │ [Substitute]          │ │
│                                                  │ [Review this step]    │ │
│                                                  └───────────────────────┘ │
│         [Pen  Eraser  Select  Equation  +]             100%   Fit          │
└────────────────────────────────────────────────────────────────────────────┘
```

示意中的两式变化与反例取自基线丢根示例。实际呈现仅能在对应真实内核结果新鲜时显示这一结论。[B §2.1、§4.5]

### 3.2 宽度档与最小内容面积

| 档位 | 可用宽度 W | 文件侧栏 | Inspector | 主画布 |
| --- | --- | --- | --- | --- |
| Wide | W ≥ 1180 | 按需 244–280，默认 256 | 默认 344，可调 320–400 | 同时展开两侧后仍至少 520 |
| Regular | 900 ≤ W < 1180 | 抽屉 | 停靠 320–360，默认 344 | 至少 520；否则改为覆盖面板 |
| Narrow | 600 ≤ W < 900 | Sheet/抽屉 | 非模态底部检查面板 | 保留至少 280 高可交互区域，否则切换单面板 |
| Compact | W < 600 | 独立导航页 | Canvas / Inspect 单面板切换 | 不放缩窄版三栏；控件可换行 |

两个侧栏的宽度和分隔总和不能超过 `W - canvasMinimumWidth`。例如 W=1180、侧栏256、检查器344、两条1pt分隔时，画布剩578；拖宽任一侧栏后违反最小值，应先收起文件侧栏，而不是把公式区压碎。

断点加入 24pt 滞回区，避免调整窗口边缘时面板反复跳动。以上宽度不是 Apple 的系统断点，是 NeoMath 的布局决策。

### 3.3 高度与键盘

| 场景 | 行为 |
| --- | --- |
| 软键盘出现 | 保证插入点、当前公式与运行入口可见；输入工具条挂靠键盘可用区域，不覆盖候选栏 |
| 可用高度 < 520 | 工具条收为单行；Inspector 改成标签切换或更紧凑的覆盖层 |
| 底部面板展开后画布不足 280 高 | 不继续硬分上下两块；提供完整 Inspect 页面和明确 Back to canvas |
| 悬浮键盘 | 计算真实遮挡矩形；只移动必要视口，不把整个屏幕当成全宽键盘 |
| 横竖切换 | 保留当前世界坐标锚点；重新计算可见区域，不 Fit all、不清选区 |

窄窗底部检查面板以 72pt 摘要态和可展开详情态设计；详情默认约可用高度的 45%，必须受上表约束。底部面板打开时 Pencil 工具移到不重叠的侧缘或工具按钮，不同时堆叠三排底栏。

### 3.4 画布与面板的几何稳定

Inspector 初次打开时，以选中公式在屏幕中的位置为锚点，仅补偿必要的 camera translation；**不得修改公式世界坐标**。保持笔迹区域不被面板盖住即可，不能每点一式都强制居中。

正在落笔、拖动选区或组合输入时，延迟破坏性布局切换到手势/输入事务结束。用户主动滚动后，自动跟随暂停；显示轻量 `Return to selection` 入口。

### 3.5 间距与尺寸

| Token | 值 | 用途 |
| --- | --- | --- |
| spacing scale | 4 / 8 / 12 / 16 / 20 / 24 / 32 / 48 | 所有自定义间距只取该序列，必要的光学校正除外 |
| content inset | 24；紧凑档16 | 内容区左右内边距 |
| inspector padding | 20；紧凑档16 | 字段、证据区的内边距 |
| section gap | 24 | 状态、集合、反例、操作之间 |
| field gap | 12 | 同一语义组的字段 |
| hit target | ≥44×44 | 所有触摸与可触发 Pencil 控件；图标可为18–22 |
| inspector tab row | ≥44 | 非仅16pt高文字可点区域 |
| selected equation padding | 12 水平 / 10 垂直 | 选择框与公式的留白 |
| text step min height | 64 | 不是固定高度；根式、分式与大字号自然增长 |
| pen palette inset | 16 | 与安全区或其他面板的最小间距 |

---

## 4. 视觉设计系统

### 4.1 颜色

冷中性背景、单一蓝色强调、克制的语义色。UI 默认跟随系统深浅外观，并可在设置中独立选择。正式实现通过语义 token 取色，不在各页面散落十六进制常量。

| Token | Light | Dark | 角色 |
| --- | --- | --- | --- |
| surface.canvas | `#F7F9FC` | `#121417` | 画布，不使用纸纹 |
| surface.panel | `#FFFFFF` | `#1C1F25` | 检查器、正文、可读内容面 |
| surface.elevated | `#FFFFFF` | `#252A32` | 浮层、Popover、局部工具 |
| surface.subtle | `#EDF1F7` | `#292E38` | 次级分组、输入背景 |
| label.primary | `#1A1E27` | `#F2F5FA` | 主文案与公式 |
| label.secondary | `#5B6575` | `#B0B9C6` | 解释、字段名 |
| label.tertiary | `#606C7D` | `#9AA5B5` | 次要元数据，仍保持可读 |
| accent.foreground | `#245DD8` | `#A6C0FF` | 选择、链接、主要操作 |
| accent.onFill | `#FFFFFF` | `#10213D` | 实心主要按钮上的文字 |
| status.verified | `#187046` | `#73D8A0` | 有依据的验证结果 |
| status.caution | `#895B00` | `#F2C76E` | 条件、过期、上游影响 |
| status.fault | `#BD3545` | `#FF929B` | 已证明分叉、无效断言 |
| status.neutral | `#626C7B` | `#AFB9C8` | 未验证、未知、不支持 |
| separator.decorative | `#DCE2EB` | `#3B424E` | 非必要识别边界；不承担单独状态信息 |

状态底色由相应状态色与 panel 做不透明混色，Light 8%、Dark 12%；不要用半透明叠层让底下笔迹影响可读性。关键控件边界、焦点和选中框另用高对比色，不能依赖浅色 separator。

普通正文对比度目标≥4.5:1，必要图形/边界≥3:1；应在实际混合后的背景上验收。Token 数值只是基准，系统增强对比度优先。

### 4.2 材质与层级

L0 是不透明画布；L1 是内容与选择高亮；L2 是轻薄工具条；L3 是 Inspector / Popover；L4 是确认与系统文档面板。

材质只用于浮动工具外壳及少量导航区域。含有公式、条件与反例的阅读面保持足够不透明。开启 Reduce Transparency 时，工具层改为不透明 `surface.elevated`。不依靠透明度区分已验证和待验证。

自定义层的圆角：紧凑控件10、证据块14、检查器18、浮动工具条22。普通公式不是一张张常驻圆角卡片；只有选中、编辑或出现局部信息时才出现容器。

### 4.3 字体

| 角色 | 基准字号/行高 | 字重与约束 |
| --- | --- | --- |
| 文档窗口标题 | 17 / 22 | Semibold，跟随系统文本样式 |
| Library 页面标题 | 28 / 34 | Semibold，不用超大营销标题 |
| Inspector section | 15 / 20 | Semibold |
| 正文/说明 | 15 / 22 | Regular，可自然换行 |
| 控件文字 | 15 / 20 | Medium |
| Caption | 12 / 17 | Regular；不能作为唯一关键结论 |
| 画布公式 | 26 起，100% zoom | 数学排版字体；大小可调，不压扁或拉伸 |
| Inspector 公式 | 21 起 | 长式局部水平滚动或换成纵向比较 |
| Witness 数值 | 28 / 自然数学高度 | 固定位置，不用数字滚动动画 |
| XDLT 源码 | 15 / 23 | 等宽；中文回退字体行高一致 |

UI 使用平台系统无衬线字体及系统等宽字体。公式渲染应提供合法可分发的数学字形、无缺字回退和可读替代文本；本稿不绑定某一外部字体包。文档 UI 随 Dynamic Type 放大；自由笔迹不因系统字号改变被重排，提供 Steps/Inspect 的可访问阅读替代。

### 4.4 图标、强调与分隔

图标按平台原生线性风格，通常18–22pt。Check、Inspect、Transform 在空间允许时保留文字；没有确认兼容性之前不锁定某个新版本 symbol 名称。高频按钮选中态用实色/底色变化，不能把任何选中态都画成绿色。

画布默认纯色；Dot grid 为可选，24世界pt间距，屏幕密度自动抽稀。网格仅辅助排版，不被解释成坐标系；隐藏网格不改变内容或数学语义。

---

## 5. 画布对象与数学对象

### 5.1 五类对象

| 对象 | 用户意义 | 可编辑内容 | 是否进入数学内核 |
| --- | --- | --- | --- |
| Ink | 自由笔迹、草算、标注 | 笔画、颜色、几何 | 否 |
| Recognition draft | 某段笔迹的候选解释 | 候选、歧义、对应笔画 | 否；可独立预览但不能写入正式 Trace |
| Math step | 已确认的公式步骤 | accepted source、label、来源映射 | 是 |
| Derivation group | 有明确顺序的一组步骤 | stepOrder、起始条件、标题 | 按该组序列分析 |
| Text note | 正文说明 | 文字与排版 | 否 |

推导组在 UI 中可多个，但底层每次提交一条明确的线性序列；它不是把现有 Notebook 内核升级为任意二维数学解析器。跨组验证和条件继承必须显式指定，不靠距离猜测。

### 5.2 顺序不能由位置偷偷决定

`stepOrder` 是数学顺序；`position` 是画布排版。拖动步骤到画布另一侧、缩放、对齐、整理笔迹都不改变推导顺序，不重算数学。

改变顺序有两个明确入口：Steps 视图的重排柄；画布选区菜单 `Reorder steps…`。系统显示新编号预览及“Steps 2–5 will be rechecked”。确认后才改序并使受影响关系失效。

圈选多行笔迹时，可以按上到下给出 **建议** 分行顺序，但必须展示编号，允许拖动、更正或拆组，再创建 Math steps。不能把一个圈选区里的两个独立题目自动连成一条推导。

### 5.3 稳定身份与可见表示

每个 Math step 有稳定 `stepID`；Ink linkage 使用应用层稳定笔画身份，不假定底层绘图对象天然提供永久 ID。每个变换关系用 `relationID` 关联前后 `stepID`，Probe 绑定关系而不是“当前看起来的第二行”。[B §4.5、G15]

一个公式可以保留笔迹表示和排版表示。默认不以排版字形替换手写；选中笔迹时，Inspector 展示它对应的 accepted source。切换 `Ink / Typeset` 只切换当前可见表示，不产生第二份独立数学真值。

### 5.4 世界坐标与视口

“无限”指没有用户必须管理的固定页边界，不是申请无限尺寸的位图。实现需以世界坐标、分块笔迹存储和可见区域渲染为边界；相机变化不写回笔画坐标。

初始缩放100%；交互范围25%–400%。Fit selection / Fit group / Fit all 是显式命令。低于60%时隐藏非必要步骤小标签与工具，选中后或通过 Steps 仍可检查；不把字号缩到无法触摸却保留同样密集的按钮。

工具、选中状态标记和关键按钮按屏幕pt保持触达；笔迹与公式随世界缩放。长公式最多撑开对象本身，不撑开整个应用窗口。

---

## 6. Pencil、触摸与选区

### 6.1 输入优先级

| 输入 | 空白区域 | 已有内容 | 约束 |
| --- | --- | --- | --- |
| Pencil / Pen tool | 写字 | 继续笔迹或对绑定区域发起回改 | 不把普通圆圈偷当 lasso |
| Pencil / Select tool | 起圈选路径 | 选择笔画或公式 | 选区闭合后出现上下文动作 |
| 单指，Pencil-only默认 | 平移 | 轻点选择；拖动按当前工具语义 | 不误画手指笔迹 |
| 双指 | 平移/捏合缩放 | 同左 | 不默认旋转整个画布 |
| 无 Pencil，Draw with finger启用 | 手指绘图 | 手指绘图 | 平移固定改为双指，并首次轻提示 |
| 长按 / 指针右键 | 新建对象菜单 | 上下文菜单 | 所有关键动作有普通按钮替代 |
| 外接键盘 | 命令 | 文本编辑、导航、选择 | 输入法组合态优先 |

Pen、Eraser、Select、Equation 是主工具；颜色和笔宽放工具二级面板。数学默认单色笔；可以选其他色，但笔色不携带 Verified / Fault 语义。

### 6.2 Squeeze 与 Hover

Apple Pencil 的 squeeze 应按一次离散动作处理，并尊重系统偏好；不是要求用户一直捏住笔。SwiftUI 存在 `onPencilSqueeze` 事件入口，事件与 Hover 数据是否可得仍依设备与系统能力判断。[P1、P2]

**本应用约定**：当系统偏好允许上下文调色板时，squeeze 在当前选区附近打开 Palette，其中 `Inspect` 可将选区送到右侧检查器。已经打开检查器时，选区变化实时联动，无需重复 squeeze。也可在应用输入设置中提供明确、可撤销的 Inspect 快捷配置，但不得覆盖用户选择的系统动作。

没有 Hover 坐标时用选区边缘作为锚点；没有 squeeze 的设备用 `Inspect` 按钮、上下文菜单或键盘命令。不要通过笔尖压力触发检查或擦除，避免与自然书写冲突。

Hover 只预亮候选对象的细边，不改变实际选中步骤、不滚动检查器、不发网络请求。点击/落笔选择才建立正式 selection。

### 6.3 圈选后的动作

选中单个 Math step：`Inspect · Transform · Edit source · Duplicate · More`。

选中纯 Ink：`Recognize · Move · Copy · More`；识别器不可用时 Recognize 有明确原因，并提供 Type equation。选中混合内容：先显示“2 equations, 5 strokes”，动作按共同能力收敛，不能无提示丢掉不支持的对象。

Palette 与选区保持8–12pt空隙，避开手的覆盖区域与键盘；左右利手设置只影响工具摆位，不镜像公式、关系方向或阅读顺序。

### 6.4 选择与 Inspector 联动

点击公式：画布出现2pt accent轮廓和轻底色；Inspector 的目标标题与公式同步切换，关联字段保持固定槽位。点击相邻关系标记：同时弱高亮前式、强高亮后式，Inspector 切到这条关系。

只有具备可靠 source/ink 映射时才能高亮某个笔画或 token；没有精确映射时高亮整式，并写 `Equation-level match`，不能精确指向实际上并未定位的符号。

Pin inspector 锁定目标，只作为显式高级动作；锁定后始终显示 `Pinned to Step 2` 和解锁按钮。默认随选区，不允许悄悄看着旧步骤。


---

## 7. 手写识别、规范化与回改

### 7.1 四层流程

```text
Ink revision
    → Recognition draft（候选，可能错误）
    → Accepted source（用户确认，供内核解析）
    → Mathematical result（带来源、新鲜度、条件与证据）
```

四层使用不同状态文字。识别正确率、识别置信度都不能转换为数学 Verified；没有真实置信度字段时，不显示自造百分比。[B §4.1、§14.4]

### 7.2 Recognition review 面板

顶部显示 `Recognized equation` 与 `Not checked`。主体依次是选中笔迹缩略、排版候选、可编辑规范源文、歧义选择、`Use equation`。

| 状态 | 展示 | 操作 |
| --- | --- | --- |
| 识别进行中 | 保留笔迹；仅候选区域显示进度 | Cancel，不阻塞继续书写 |
| 候选唯一 | 显示排版式与可展开的 normalized source | Use equation / Edit |
| 存在歧义 | 对歧义范围高亮，如 x / ×、1 / l、− / = | 选择候选或键入，确认按钮不预选不确定项 |
| 无法分行 | 显示行框与顺序编号 | Split / Merge / Reorder |
| 识别失败 | `Couldn’t recognize this selection` | Select again / Type equation |
| 识别器不可用 | `Math recognition is unavailable` | Keep ink / Type equation |
| 笔迹已改变 | `Ink changed. Review the new recognition.` | 丢弃旧候选，重新识别 |

本地识别可在停止书写约300ms后更新候选预览；该数值是调度起点，不是识别耗时承诺。导入或选区中的笔迹不默认上传第三方。远端识别若日后加入，先显示提供者、将发送的选区和确认动作。

### 7.3 确认事务

Use equation 必须一次性记录：accepted source、原始识别输出、用户更正、对应 inkRevision、normalizationVersion、stepID、所属组与步骤顺序。若请求返回时笔迹revision不匹配，不允许确认旧候选。

确认后保留原笔迹，不自动“美化擦除”。排版内容出现在 Inspector 或用户选择的 Typeset 表示中；如确需替换画布可见笔迹，应是独立 `Show typeset version` 视图操作，原笔画仍可恢复。

### 7.4 回改已经验证的笔迹

用户改写与某 Math step 绑定的笔画时，立即把该对象标记为 `Ink changed · Review equation`。accepted source 暂不被猜测性修改；旧数学结果只能以明确标注的历史结果查看，不能继续作为新笔迹的绿色状态。

新识别候选随笔迹局部更新。确认后更新 accepted source，当前与受影响后续步骤进入 Stale，重算采用新快照。拒绝新识别时提供两个明确动作：恢复上次对应笔迹，或解除绑定并将新笔迹保留为普通注记；不得静默把不同笔迹仍绑定到旧公式。

移动、缩放、换笔色只属于几何/样式变化，不触发这个流程。批注笔迹与公式笔迹通过明确分层或对象身份区分；在旁边画箭头不能把整组公式都置为过期。

### 7.5 数学输入规范化边界

当前 C++ 输入只接受所列语法，变量为 x；不直接接受小数文本、任意变量或 LaTeX。这是数学能力，不因画布漂亮而改变。[B §4.1–§4.2]

| 用户可见输入 | 提案中的处理 | UI 要求 |
| --- | --- | --- |
| `−`、`×`、`÷` | 无歧义情况下映射到 `-`、`*`、`/` | 保留 rawSource 与映射位置；x与×歧义须确认 |
| 工具条分数 | 插入 `(numerator)/(denominator)` 模板 | 光标从分子到分母；不生成不可见的除法条件 |
| 工具条平方 | 插入 `^2` 或对选中表达式加括号后平方 | 不靠 Unicode 上标直接提交内核 |
| 根号 | 插入 `sqrt(...)` | 空槽与光标清楚；可解析不等于任意根式可求解 |
| `or` 分支 | 插入文本 ` or ` | 是一个方程步骤的分支，不是 UI 分组连线 |
| `0.5` | 默认保留并报告当前解析限制；可提示“改写为1/2” | 小数→有理数规范化是另一个需测试的适配能力；未交付前不自动转换 |
| `y`、矩阵、积分 | 保存原文，显示能力边界 | 不改成x，不删除，不虚构求解结果 |
| 粘贴 LaTeX | 原样保留；仅有显式转换器时提供转换预览 | 不能只去掉反斜杠后声称兼容 |

任何精确数字不得经 Double 中转再回写。规范化与识别一样有版本及测试，必须能把解析错误映射回用户实际看到的字符或笔迹范围。[B §4.3、§11.7]

---

## 8. Steps 视图与执行命令

### 8.1 Steps 是可靠的线性入口

Canvas / Steps 显示同一个文档、同一组稳定 stepID 和同一份 accepted source。切换只改变视图状态，不复制文档、不重新识别、不重跑数学。当前步骤保持选中，滚动位置各自记忆。

Steps 视图每行包括：步骤编号、可编辑公式、独立步骤状态、相邻关系摘要和更多操作。第一行标记 `Initial state`，不显示“等价变形”。公式下的结果默认紧凑，点击打开同一个 Inspector。[B §4.4、G12]

### 8.2 键盘编辑

Enter 在需要多行的字段中保留换行；Command+Enter 检查当前步骤；Shift+Enter 检查当前步骤，若没有需要暂停的问题，再进入下一步，无下一步时新建空步骤。若出现分叉、未知或不支持，保留当前焦点，明确显示原因，不假装已推进。

输入法组合态优先：组合候选确认不能触发文档运行或新建。数学文本编辑的原生撤销与结构命令需要统一事务边界，不能同时执行两个撤销栈。

### 8.3 命令的精确定义

| Command ID | 可见文案 | 范围与行为 |
| --- | --- | --- |
| `math.checkStep` | Check step | 从组首建立目标步骤所需上下文，检查选中步骤和其incoming relation；不把后续标为已通过 |
| `math.continue` | Continue checking | 从当前组第一条未检查/过期/已取消步骤继续；不是从屏幕选中位置猜起点 |
| `math.checkGroup` | Check group | 按顺序使用新鲜缓存或重新计算；遇已证明首错暂停，后续仅标记受影响，不虚构运行结果 |
| `math.recheckAll` | Recheck all | 当前文档所有组重检；每组都保留暂停与错误位置，显示组级进度 |
| `math.step` | Next step | 沿当前组执行游标只推进一步；起点在控制区可见 |
| `math.resetResults` | Clear check results | 清除显示结果/执行游标，不删除源文和笔迹；不是恢复示例原稿 |
| `task.stop` | Stop checking | 停止排队并取消等待；实际计算是否已终止按服务返回显示 |
| `example.restore` | Restore example | 新建或恢复内置模板副本；与清除结果不同 |

默认 Continue 遇 Root Fault、IndependentFault、Unsupported、Unverified 或运行失败暂停，提示“后续尚未完成检查”。高级 `Continue for inspection` 可用于在错误上下文下观察后续状态，必须保留 Tainted 提示，不提升整体结论。[B §4.4、§5.4、§18.2]

### 8.4 实时检查策略

首次输入只做局部输入反馈，不在用户还未写完等号时连续弹错。用户第一次主动检查某组后，可开启该组 `Live check`：已提交公式停改350ms后重算受影响范围，立即标出过期状态，计算期间保持其他内容可操作。

该设置只调度数学验证；绝不联动 XDLT Python 执行、AI 请求或远端识别。显式 Check 跳过防抖直接调度。350ms是客户端调度策略，不是后端耗时指标。

### 8.5 停止与旧结果

正在本机计算但服务无法抢占时，显示 `Stopped waiting. Computation may still be finishing.`，并丢弃其过期回写。不能把按钮变回三角形就声称计算已中止。新的请求必须拥有独立requestID，不接受旧请求的“迟到成功”。[B §4.8、G10、G20]

---

## 9. 可信状态显示规范

### 9.1 五个独立维度

| 维度 | 例子 | 不能与什么合并 |
| --- | --- | --- |
| 输入状态 | Draft、Accepted、Ink changed | 识别置信度与数学真值 |
| 任务状态 | Queued、Running、Cancelled、Failed | 未知数学与执行错误 |
| 新鲜度 | Fresh、Stale、Previous result | 旧成功与当前成功 |
| 数学状态/关系 | Verified、Equivalent、ConditionEquivalent、Implication、Fault、Unverified、Unsupported | 单步可求解与整条推导正确 |
| 来源 | C++ exact、SymPy、Python output、Demo、AI explanation | 程序输出/解释与数学证明 |

保存状态独立，不占用数学状态字段。一个结果可以“精确求解了这一式，但它来自丢根的上一步”；界面必须同时容纳这两件事。[B §4.4、§16.4]

### 9.2 主状态的显示优先顺序

先看是否尚未确认或有未提交回改；再看是否过期；再看当前任务；最后才展示新鲜数学结论。历史结果可展开，但不得继续留在当前画布的主状态位置。

来源标签始终附着于结果，不受主状态优先级覆盖。Demo、AI 和 Python output 无论内容是什么，都不能使用 C++ exact 的徽标。

### 9.3 Notebook 状态矩阵

| 服务语义 | 主文案（EN / 中文） | 视觉 | 必须同时表达 |
| --- | --- | --- | --- |
| 首个有效状态 | Initial state / 初始状态 | 中性图标与文字 | 本式解集和定义域；没有前式关系 |
| Equivalent | Equivalent / 等价 | 小型绿色关系标记 `⇔` | 前后式、条件与fresh状态 |
| ConditionEquivalent | Equivalent if… / 在以下条件下等价 | 条件标记、caution色 | 条件正文常显，不能只放tooltip |
| Source implies target | Forward implication / 仅前式推出后式 | 单向 `⇒`、caution | 方向文字，可能增解的实际结果另列 |
| Target implies source | Reverse implication / 仅后式推出前式 | 单向 `⇐`、caution | 方向文字，不能把图标镜像后省略说明 |
| Root Fault / Lost roots | Lost solution / 丢解 | fault色、分叉标记 | 第一处已证明分叉、丢失集合、Witness |
| Root Fault / Added roots | Added solution / 增解 | fault色、分叉标记 | 新增集合与代回原式的结果 |
| Domain shift | Domain changed / 定义域改变 | fault或实际关系级别 | 原/新定义域和差异，不强制改称“丢根” |
| Tainted | Affected by Step N / 受步骤N影响 | caution、虚线来源 | 本步本地关系可以成立；整条链仍有上游问题 |
| IndependentFault | Additional issue / 本步另有问题 | fault或服务明确级别 | 保留原始状态与reason，不擅自映射为成功 |
| Unverified | Couldn’t verify / 暂时无法验证 | 中性问号 | 原因、能力边界；不是数学错误 |
| Unsupported | Not supported / 当前不支持 | 中性能力标记 | 支持范围和可保留原文，不显示等价箭头 |
| Stale | Needs recheck / 需要重新检查 | caution、时钟 | 导致失效的步骤或条件 |
| Not run | Not checked / 尚未检查 | 中性空心点 | 可触发检查 |
| Runtime failed | Check failed / 检查失败 | 警告图标 | 服务错误与重试入口；不是反例 |

无理二次根不能表示时，应写“当前内核不能表示此解”，不能写“No solution”。真正空解集显示 `∅` 与“No real solutions”，它不是unknown。区间端点开闭、排除点与有理数精度完整保留。[B §4.2–§4.4]

### 9.4 整组摘要

默认显示 `12 steps · 8 checked · 1 divergence · 3 affected` 之类可解释计数；相邻关系与步骤数分别计数，不能以“8个已建立状态”冒充“7次等价全部通过”。只有所有目标步骤/关系新鲜、完成检查，且条件与整体关系满足时，才能给整体结论。

若只有条件等价，摘要写 `Checked under 2 conditions`；有Unknown时写 `Check incomplete`。首发不提供一个把所有结果平均的“数学正确率百分比”。

---

## 10. Inspector 详细规格

### 10.1 容器与内容顺序

默认标题是目标，如 `Step 1 → 2`，不是笼统的“Debugger”。右侧只有 Pin 与关闭。正文滚动，当前目标和状态摘要可保持在顶端；不要在底部再重复全部步骤状态。

顺序固定：**结论 → Before/After → 解集与定义域 → 条件 → Witness → 建议操作 → 技术详情**。没有数据的字段用明确占位“未计算/无法判断/不适用”，不能用空白引导用户误认为相同。

顶部提供 Overview / Evidence / Details 三个标签；Overview必须有关键反例摘要，不能为了标签整洁把决定性证据全部藏起来。窄面板与大字号时标签允许变为菜单，不压缩到文字重叠。

### 10.2 Before / After

宽度足够时并排两个字段；任一式溢出或大字号时改上下排列，始终保留 Before / After 文案。前式与后式不互相覆盖，不做会让两式混淆的字形插值。

在相同数学来源下比较 `Solution set` 与 `Domain`；差异位置可以高亮。集合元素用确切字符串，不通过排序浮点数来比较。上下文/非零条件显示作用域，例如 `For this transformation: x ≠ 0`，不能被理解为对原题隐式追加的全局限制。

### 10.3 首错示例内容

```text
Step 1 → 2
Lost solution

Before                 After
x(x − 1) = 0           x − 1 = 0

Solutions
{0, 1}                 {1}

Witness
x = 0
Before: True           After: False

Dividing by x removes the case x = 0.
[Substitute]           [Review this step]

C++ exact · Current result
```

文案以真实诊断为依据，不能从看到“除以x”就自行断言丢根。证据缺失时明确写 `No exact witness returned`，不能补造数值。[B §4.5–§4.6]

### 10.4 Witness 交互

点击 Witness 高亮前后式中的对应变量；按 `Substitute` 展开左右值、是否定义、是否成立。仅在映射精确时定位单个符号，否则定位整式。数值出现在固定 Witness 槽位，不飞入公式并把原式永久改写。

用户可复制“反例值”“前后式”“完整解释”。展示结果的任意一侧不支持求值时，只报告该侧未知，不将空返回变成false或Mock。

### 10.5 Probe 交互

Probe 输入显示 `Try x =`，接受当前能力支持的负数与分数。请求包含 documentID、semanticRevision、groupID、relationID、beforeStepID、afterStepID、probeValue。首行没有前式时，明确是 `Evaluate this equation`，不伪造两式比较。[B §4.5、G15]

返回分别展示：

| 结果 | 文案 | 不能替代成 |
| --- | --- | --- |
| 有定义且成立 | True / 成立 | “两式一定等价” |
| 有定义但不成立 | False / 不成立 | 未定义 |
| 不在定义域 | Undefined / 未定义 | False |
| 求值能力不足 | Unknown / 无法判断 | False或0 |
| 服务执行失败 | Evaluation failed / 代回失败 | 数学上的Unknown |

Probe只能说明这个值的表现；底部固定一句 `A single test value does not prove equivalence.`。自动Witness与手动Probe视觉上标明来源，手动值不覆盖原有自动证据。

### 10.6 Details

折叠项包括操作ID、规则、certificate status、claimedRelation、验证方法、引擎版本、source hash、输入范围、耗时、诊断码。首次打开不显示一整屏JSON；提供 `Copy diagnostics`，生成经过脱敏的结构化文本。

`certificate.verified` 只说明证书中的声明得到验证，不能单独驱动绿色等价样式。平方变换的有效单向证书仍显示单向关系。[B §4.6]

---

## 11. 变换、补全与修复

### 11.1 入口与面板

画布选区Palette、Inspector底部、Steps行菜单共同调用一个 Transform command。普通情况为锚定对象的Popover；窄窗变Sheet。没有三个互不一致的实现。

动作列表保留后端 `id / label / available / risk / reason / preview`；禁用项仍可阅读原因。不能从翻译后的中文label反推调用哪个intent。[B §4.7、G13]

### 11.2 每个操作的呈现

| ID | 文案 | 参数 | 预览必须包含 |
| --- | --- | --- | --- |
| factor | Factor | 无 | 实际可用的目标式；不暗示通用因式分解 |
| expand | Expand | 无 | 目标式与实际支持范围 |
| move_terms | Move terms to left | 无 | 右边为0的新式；不是任意拖项 |
| divide | Divide both sides | Divisor | 目标式、除数非零条件、解集/定义域变化 |
| multiply | Multiply both sides | Multiplier | 目标式、非零条件与可能增解 |
| square_both_sides | Square both sides | 无 | 前式、目标式、实际单向/条件关系 |
| solve | Solve | 无 | 当前可表示的精确解集表达式 |
| verify | Verify | 无 | 验证结果；不额外插入一个相同公式步骤 |

这些ID与范围来自C++基线；edlatex的13条规则另按自己的能力列表展示，不能混成Notebook的“全部可用变换”。[B §4.6、§7.4]

### 11.3 参数预览

面板从上到下：选中源式、操作名、参数字段、条件、目标式、关系摘要、`Add step`。除数为空、语法错、服务不可用或结果尚未返回时，Add step禁用并说明原因。

预览绑定source hash、参数hash、条件hash和requestID。任一改变，旧预览立即变为 `Updating preview`；用户不能在显示旧preview时提交新参数。

对会改变解集的操作，仍允许用户有意识地添加到草算中，但按钮改为 `Add with warning` 并清楚展示后果，不自动“帮用户”限制原题定义域来抹掉错误。无风险的点击也要验证目标式；预览本身不承诺整组正确。

### 11.4 应用事务

点击Add step时，在一个文档事务内插入新step及source、operation provenance和预览证书引用，然后对同一个提交快照发起验证；不依赖异步UI状态“应该已经写进数组”。新步骤的位置在当前组下一步，画布位置先预示再放入，原步骤不改。[B G18]

一次Undo移除整个新步骤及对应生成表示；Redo恢复source与provenance，但数学结果只有匹配版本/哈希才可复用。

### 11.5 修复不等于在错误后再写一行

首错的主要动作叫 `Review this step`，不是 `Auto-fix`。打开面板提供：

**Replace this step**：展示旧式与候选新式，解释来源于哪一个正确上游状态；确认后原stepID保留，source更新，后续全部重新处理新鲜度。

**Start a new group from Step N**：从正确前缀新建独立推导组，保留原错误组作比较；记录来源，但不宣称已有通用分支证明图。

**Edit manually**：返回笔迹回改或source编辑，保留故障定位。

例如把第2步 `x−1=0` 替换为 `x=0 or x=1`，原第3步 `x=1` 仍可能是丢解；新检查必须报告这个后续问题，不能以“已插入正确解”宣布整条推导修好。[B §5.6、G17]

### 11.6 删除、复制、移动

复制步骤生成新ID，默认没有当前验证结论。删除步骤时预告受影响的后续关系；画布仅隐藏Ink表示与删除Math step是两个不同菜单动作。`Delete step and linked ink` 要明确说明会删除两者并支持Undo。

普通移动对象只改变坐标；跨组移动数学步骤必须进入“Move to group”确认流程，展示新顺序与条件作用域。

---

## 12. 动画与反馈规范

### 12.1 动画原则

动画很多，但每一种回答一个问题：**选中了什么、它来自哪里、什么变了、哪些结果过期、操作有没有落地。** 不靠全屏loading、统一大弹簧或反复闪光表示“高级”。

内容反馈立即发生，动画不作为事务完成、请求提交或可操作性的前置条件。任何动画必须可打断；快速切换选择时向最新目标收敛，不排队播放旧选择。

### 12.2 Motion tokens

| Token | 目标时长 | 运动 | 用途 |
| --- | --- | --- | --- |
| motion.press | 90ms | ease-out；控件scale到0.98再恢复 | 可按反馈，输入层不缩放 |
| motion.hover | 100ms | opacity | 对象预亮，离开立即衰减 |
| motion.micro | 120ms | opacity / ≤4pt局部位移 | 标签、字段值切换 |
| motion.selection | 160ms | 选区轮廓bounds连续变化 | 同一上下文内的选区切换 |
| motion.content | 180ms | 交叉淡化，≤4pt垂直位移 | Inspector局部内容更新 |
| motion.panel | 260ms | 临界阻尼感的几何过渡，无明显回弹 | Panel进出、宽度变化 |
| motion.morph | 280ms | 同身份容器的形状/位置过渡 | 文档缩略→文档，候选容器→步骤 |
| motion.focus | 240ms | 可取消的camera translation | 用户主动Focus selection |
| motion.highlight | 600ms总计 | 一次低对比高亮后退回静态 | Witness关联、诊断定位 |
| motion.reduced | 80ms | 仅dissolve；也可立即替换 | Reduce Motion模式 |

时长是目标体验参数，不保证所有硬件上精确持续相同帧数。具体弹簧API/曲线由原型落地，不能把这里的ms当成某个平台spring参数直接照填。

### 12.3 动画目录

| ID | 触发 | 画面变化 | 中断/减少动态效果 |
| --- | --- | --- | --- |
| M01 | 打开文档 | 有可用缩略时同身份容器延展；工具稍后淡入 | 无快照用淡入；Reduced不做空间放大 |
| M02 | 圈选完成 | lasso收敛成选择轮廓；Palette由锚点出现 | 不补画虚假笔迹；Reduced直接替换轮廓 |
| M03 | Inspect打开 | Panel占位与画布camera补偿同步；选区仍在原屏幕锚点附近 | 落笔中延迟布局；Reduced瞬时布局+淡入 |
| M04 | 切换步骤 | 轮廓移到新对象；Inspector只更换字段内容 | 最新selection覆盖旧动画，不重播Panel进入 |
| M05 | Hover | 细边淡入；无Panel更新 | 离开清除，不粘住hover目标 |
| M06 | 识别完成 | 候选区域局部淡入；原笔迹不变 | 不把手写强行变成排版字 |
| M07 | 确认识别 | 候选容器收敛为已提交对象的状态提示 | source先提交；动画取消不撤销事务 |
| M08 | 回改笔迹 | 原成功徽标立即退出；出现Ink changed/Needs recheck | 不为等动画完成而保留旧绿色 |
| M09 | 检查中 | 超过180ms后出现局部进度图标 | 任务先完成则不显示spinner，不强制最短等待 |
| M10 | 检查完成 | 状态文字与小图标交叉淡化 | 不闪整行绿色，不滚动数字 |
| M11 | Witness代回 | 相关式与证据槽一次关联高亮 | 无映射则整式高亮；Reduced用静态边框 |
| M12 | 变换预览 | 目标式在独立槽位替换，条件区自然扩高 | 数学符号不做跨值插值 |
| M13 | 添加新步骤 | 预示位置的小占位变为实际新步骤；后续对象最小位移 | 先插入数据；不能等动画结束才提交 |
| M14 | 删除/撤销 | 同组局部重排，不让整张画布弹跳 | Undo取消正在离场的对应对象 |
| M15 | Canvas/Steps | 同stepID选择保持；容器过渡或淡化 | 不是把几百笔画逐个morph成字符 |
| M16 | 窗口变窄 | Inspector转底部或单面板，保留目标与tab | 正在编辑时保留焦点；Reduced直接切布局 |
| M17 | 保存确认 | 标题旁Saving→Saved局部替换 | 不出toast雨；失败提示常驻 |
| M18 | XDLT patch | 仅变化块更新；当前阅读锚点稳定 | 旧块明确Previous preview；不整页闪白 |
| M19 | 错误定位 | 用户点击后平移到目标，一次边框高亮 | 不抖动、不震屏；Reduced瞬移+边框 |
| M20 | Presentation单步 | 下一条结果揭示，证据逐层展开 | 不更改实际验证状态，退出回原视口 |

### 12.4 数学内容的特别禁令

不能把 `0` 滚动成 `1`、把 `=` morph成 `≠`来代替说明、把两式混合显示得像同一式，或用连续闪烁的绿勾表示“仍在计算”。模糊动画仅可用于非关键信息的控制层，最多1.5pt；公式、条件、Witness和源码不模糊。

状态失效即时更新数据语义；视觉最多在120ms内收敛为过期提示，但这一期间旧结果已经不能被复制或导出为当前验证结果。

### 12.5 Reduce Motion、Reduce Transparency与反馈

Reduce Motion下去掉camera自动飞行、scale、spring、视差和大范围形状变换，用80ms以内dissolve或立即布局；所有状态、定位、条件仍完整。系统减少动态效果会用淡化替代某些缩放/移动，本应用遵循同一可访问性方向。[P3]

触觉只在明确离散提交、吸附或错误动作后请求一次，并依设备与系统设置决定是否实际发生；不假定每台iPad都有同样的振动。不能每敲一个字符、每更新一次识别就触发反馈。[P1]

### 12.6 性能目标

目标是在设备支持的刷新率下保持直接操作流畅，60Hz与120Hz分别验收，不承诺所有硬件都120fps。主线程不做数学求解、识别或大文档解析；笔画渲染不等待Inspector。

UI操作可见反馈目标≤100ms；超过180ms的任务才显示局部进度；较长任务显示阶段与可用取消方式，不猜进度百分比。500ms MathCore预算不是整条iPad交互的完成承诺。[B §4.8、§12.3]


---

## 13. Documents、保存与恢复

### 13.1 文档入口

首次进入是安静的 Documents 页面，主操作 `New derivation`，次操作 `New writing document` 和 `Import`。下方提供四个真实内核教学示例，不放每日签到、推荐课程、功能广告或AI聊天欢迎语。

最近文档使用列表/网格切换：缩略图、标题、文档类型、修改时间与必要的保存问题。默认不为每份文档展示“大大的正确率”。缩略图是内容预览，不是数学结论证明。

新建立即获得可持久化草稿身份，不强制先输入文件名；顶部默认 `Untitled derivation`，标题菜单内重命名。新建空白、复制示例、导入文件都不能共用会被误覆盖的同一个documentID。[B §5.2、G06–G07]

### 13.2 示例

四个示例为 Lost roots、Squaring、Domain change、Transformations。模板只读，每次打开生成可编辑副本；数学结果由当前真实内核生成，不能沿用未核对的缓存。`Restore example` 重新读内置模板，不从已被自动保存修改的同名文件“复位”。[B §5.8、§14.5]

手写展示可以作为额外UI fixture，必须显式标记为设计样例。真实发行示例若未含手写识别链路，就展示排版/键入公式，不能播放伪识别结果。

### 13.3 保存状态

| 状态 | 顶部文案 | 行为 |
| --- | --- | --- |
| clean | Saved / 已保存 | 仅在当前持久化revision得到成功确认后显示 |
| dirty | Unsaved changes / 有未保存更改 | 保留编辑状态，排队保存 |
| saving | Saving… / 正在保存 | 不锁住输入；后续revision继续排队 |
| saveFailed | Couldn’t save / 保存失败 | 常驻可点击提示，Retry / Save a copy |
| providerUnavailable | Location unavailable / 保存位置不可用 | 本地恢复副本明确标注，不能声称原文件已保存 |
| conflict | Another version exists / 发现另一版本 | 保留双方副本，进入冲突处理 |
| recoveryCopySaved | Recovery copy saved locally / 恢复副本已保存在本机 | 与原目标位置保存成功不同 |

自动保存采用两段：完成笔画/编辑事务后进入本机恢复日志；约500ms空闲后合并写入文档目标。两者都必须等待真实写入确认，数值是调度提案，不是断电永不丢失的承诺。后台化、切文档、关闭窗口时尽力提交最新可持久化快照，并在失败时保留恢复记录。[B §16.2]

保存失败不是一个3秒后消失的toast；不能因为用户打开另一个面板就消失。按Save时文件未命名可进入命名/选择位置流程，但本地草稿不能因此丢失。

### 13.4 冲突与崩溃恢复

恢复页显示两份内容的标题、来源、修改时间和缩略差异，操作为 `Open recovered copy`、`Open saved version`、`Keep both`。不能仅按时间戳较新自动覆盖。

同一文档两个窗口中的选择/视口独立；源内容需要文件协调与冲突策略。协调未完成时，第二窗口只读或提示返回已有编辑窗口；不能让两个全局单例轮流写同一份状态。

### 13.5 新增画布数据的存储前置条件

旧`.nm`没有完整schema版本或画布/Pencil资产约定，不能把新增笔迹当临时ViewState丢在内存里。[B §8.1–§8.2、§16.1]

目标原生文档须分开保存：原始/接受的source、稳定步骤与组顺序、笔画数据与稳定身份、对象几何与ink映射、未知扩展字段；派生结果和窗口视口另列。可采用包结构或有版本的容器，但正式后缀、UTType和兼容策略要先确定，不在本稿冒充已经存在。

旧文件导入默认创建新副本并保留原件。向旧`.nm`导出时，若不能携带自由笔迹/布局，应显示 `This format won’t include canvas ink and layout`，允许取消；不能用一个没写明的降级导出覆盖原生文档。

### 13.6 Import report

按内容与版本识别`.nm`、`.neomath.json`、`.edlatex.json`、`.xdlt`、`.hw`、`content.edl`和`.card.json`。报告列出已保留、需重验、当前只读及未迁移内容；遇未来版本只读或拒绝，不能打开成空白然后自动保存。[B §8、§16.1]

旧缓存结果统一标 `Imported result · Needs recheck`，除非具备完整的source/engine/conditions/hash一致性证据。不因为旧JSON里写了success就恢复绿色状态。

---

## 14. XDLT 写作工作区

### 14.1 定位

XDLT 是有编译、引用、断言和执行能力的数学文档，不是无限画布中的一张普通便笺，也不是Notebook语法的另一种皮肤。共享原生外壳，编辑器与语义状态独立。[B §6]

### 14.2 三种视图

Source / Preview / Split 切换位于文档工具栏中。Split仅在源文最少360pt、预览最少400pt都可满足时开放；否则保留选择偏好，实际改为单视图并提示空间不足。用户缩放窗口后不丢源文选区或预览阅读锚点。

宽屏布局：可收起Outline，源文，预览；Diagnostics作为底部区域，默认只显示计数及最高级别。开发统计如patch数量、sessionID、缓存命中放Details，不占正文。[B §6.1、§14.2]

### 14.3 Source编辑器

至少支持等宽输入、稳定光标、选区、撤销、查找、复制、行号开关和诊断定位。语法高亮、自动缩进与折叠是新增编辑能力，按真实实现分别标记，不以“接入一个text editor”就声称有LSP。

字符/UTF-16/行范围映射必须明确。中文、组合字符、emoji、混合换行下点击诊断定位实际片段；不能把Python字符偏移直接当Swift字符串下标。[B §11.7]

提供插入菜单：Heading、Equation、Context、Theorem、Proof、Assertion、Code block。菜单插入该语言真实模板，不生成假语法。普通code fence与可执行`#exec`用不同文案，用户插入展示代码时不会意外授权执行。[B §6.2–§6.3]

### 14.4 Preview

渲染链路继续消费结构化的HTML/MathML等结果，不在Web层自行猜数学真值。公式编号与语义ID分开；点击引用跳到目标，有来源映射时可Reveal in source。[B §6.7、§6.10]

未知块/未知命令保留原文fallback并带可展开诊断。不得把无法渲染的块直接从成品页面删除。Source与Preview双向定位只在可靠sourceMap存在时开放，不假称所有区域都精确同步。[B §6.1、§6.4]

### 14.5 更新与新鲜度

编辑源文后立即标记受影响的预览/验证区域为updating；保留上次预览时在顶部显示 `Previous preview · Updating`。编译完成只接受当前documentID、sessionID、semanticRevision的结果。

补丁失败回退为同一最新revision的完整render，尽量恢复阅读锚点；不能用旧完整HTML覆盖新source。若全量回退也失败，保留旧预览且持续标明其版本，与当前源码区分。[B §6.1、§6.10]

预览成功不自动意味着断言都成立、代码已执行或文档是形式化证明。

### 14.6 Diagnostics

每项显示严重级别、自然语言、行/范围、代码与状态。点击定位source；画布/预览里只显示局部标记，不铺滿整页红底。最高层级异常可显示一个文档横幅，其余合并到列表。

| XDLT断言状态 | 可见文案 | 呈现要求 |
| --- | --- | --- |
| valid | Verified | 显示SymPy或真实verifier来源，不冒充C++ |
| valid-with-conditions | Verified with conditions | 条件常显 |
| invalid | Assertion does not hold | 给evidence和定位，不泛化成整篇写作错误 |
| unknown | Couldn’t determine | 中性未知，不用错误红叉 |
| unverified | Not verified | 尚未执行验证 |
| error | Verification error | 验证执行/类型/解析问题，与invalid分开 |

这六态必须穷尽处理，不能把后两态挤进四态卡片后直接忽略。[B §6.6]

### 14.7 可执行代码的UI隔离

打开、导入、预览、修改XDLT时 **execute=false**。安全的解析/排版与明确可用的断言验证可以各自调度，但不因此执行任意Python代码。本规则是Darwin新设计，修正基线中的默认execute=true行为，不声称现有Runner已安全沙箱化。[B §6.8、G21]

执行入口为 `Run selected block` 或 `Review and run blocks…`。首次运行显示所选exec IDs、语言、输入变量、执行后端、能访问的资源与已知限制、缓存策略和取消能力。后端隔离/权限机制未完成时，入口保持Unavailable，不能靠弹一个“信任此文件”对话框掩盖执行风险。

授权按文档、代码hash、runner与明确范围保存。代码或后端变化需要重新审查。缓存输出标 `Cached output`；代码变化后标 `Outdated output`。复制来的文档不继承来源机器的信任许可。

### 14.8 执行输出与长任务

text、JSON、math、image、table使用合适的查看器；stdout/stderr折叠。代码输出的公式是 `Program output`，不是形式化或精确验证证明；图像是执行资产，不因此称为交互式绘图系统。[B §6.8]

状态分别是queued/running/succeeded/failed/timed out/cancelled/blocked/unavailable。下游blocked必须指向具体失败或未运行块。客户端超时显示任务超时/连接状态，不能把一个仍在执行的合法任务无条件改称“离线”。[B G22]

---

## 15. Context、知识卡与 edlatex

### 15.1 Context面板

显示当前作用域、符号类型、属性、值、条件来源与继承关系。用户修改条件前，预览受影响断言/推导；确认后仅使依赖范围失效。全局、章节、组/步骤局部条件用明确标签分开。

冲突应定位来源，例如“x声明为Positive，但当前绑定为−1”。不要自动删除冲突的一侧。缺少后端时保留原始声明并只读提示。[B §6.5、§7.3]

Notebook当前只支持的x与XDLT/edlatex上下文词汇不同；UI按文档类型和backend capability提供编辑，不把多变量Context菜单直接当作C++求解能力。

### 15.2 Card面板

仅展示项目内已导入/可用卡片，不引入在线市场。列表包含title、id、version、来源和缺失状态。详情依次为参数、requirements、content/conclusion、dependencies、provenance。[B §6.9]

插入前显示reference / snapshot / fork的含义：引用来源版本；固定版本快照；生成有来源记录的本地分叉。fork文件工作流未实现时禁用而非只改一个provenance字段就显示“复制成功”。参数条件为unknown时，显示 `Requirements not established`，不是“已满足”。

缺失卡片不能导致正文引用消失；留可读占位、引用ID和导入/定位入口。

### 15.3 edlatex工作位

保留nodes/order、稳定ID、metadata与layout的独立关系。能编辑的节点显示原生结构编辑；不支持的节点以只读原文+类型提示呈现，仍参与保存往返。换模板不改变节点身份或数学顺序。[B §7.1]

edlatex规则变换保留其13种rule及条件，由自己的backend capability驱动。导入Notebook的操作是显式转换并提供报告，不是切换Canvas标签即可无损完成。

PDF基线返回PDF_UNAVAILABLE；UI不得把HTML浏览器打印或某个空文件冒充已有的edlatex PDF导出。[B §7.5]

---

## 16. 设置、AI、导出与课堂演示

### 16.1 Settings

| 分组 | 内容 | 约束 |
| --- | --- | --- |
| Appearance | System / Light / Dark，字号，画布网格 | 大字号不只放大文字却裁切控件 |
| Input | 利手、手指绘图、识别策略、Pencil快捷说明 | Squeeze不覆盖系统偏好，输入能力按设备显示 |
| Mathematics | 后端、版本、能力、限制、Live check | C++精确模式与其他后端明确分开 |
| Execution | 运行后端、文档授权、缓存管理 | 预览不自动执行；撤销授权有确认 |
| AI | 启用状态、provider/model、凭据、发送预览 | AI不是必需依赖，默认不自动发请求 |
| Files | 默认位置、恢复副本、迁移与导出偏好 | 保存位置说明必须符合真实存储 |
| About | 版本、开源信息、许可、诊断导出 | 不在正文工作区展示工程噪音 |

### 16.2 能力的可见状态

每个服务分别报告available/unavailable/requires configuration/not supported，伴随reason和可行操作。断网不让本机C++自动显示Offline；本机内核失败不回退到Mock绿色结果。用户主动进入演示数据模式时，整个相关区域持久标 `Demo data`。[B §5.9、G14]

能力说明至少包括Notebook支持语法、变量、求解边界、有效限制、识别、XDLT render/verify/execute、edlatex import/export与PDF。基线中的getCapabilities尚非完整统一注册表，界面所需统一能力模型属于新增适配契约。[B G31]

### 16.3 AI解释

入口放在已存在诊断下的 `Explain this result`，默认优先展示本地证据。发送前展示目标provider及内容范围；请求只包含明确投影的诊断/相关步骤，不默认发送整个文档库、文件路径或附件。[B §9]

AI段落标 `AI explanation`；失败时可展示真实的本地解释fallback并标来源。AI不写入MathState、solutionSet、domain、certificate或Verified，命令候选必须经用户确认、结构化白名单和内核验证。

没有密钥时可以正常使用数学核心，不能在主画布不断提示“配置AI才能开始”。凭据使用系统安全存储的设计目标，不进入文档、导出或诊断日志；具体集成需单独测试。[B §9.3]

### 16.4 Export

入口位于文档菜单。第一层选范围：当前推导组、所选内容、整个文档；第二层选受支持格式。Notebook原始source导出、XDLT source/HTML、edlatex JSON/HTML/LaTeX等按真实适配能力列出，不能把某模块的导出按钮复制到所有类型。[B §7.5、§8]

导出内容分为源文、可见笔迹、结果/证据三个可选择层；选择含结果时显示新鲜度与来源。当前源文只能搭配当前结果；过期结果默认排除，显式导出历史快照必须标明时间与source hash，不能让它看起来像对应当前推导。

UI允许呈现Unavailable格式的说明，但禁用执行。若新增PDF，需提供真实渲染和分页验收：长公式、分数/根号、字体、图片、表格、条件、浅深色、打印背景。画布PDF还须明确“当前视口/选择范围/内容分页”，不能默默截掉屏外笔迹。

只有目标文件写入确认后才显示 `Exported`。失败保留格式与范围选择，给重试，不打开一个空的分享面板冒充成功。[B §18.6]

### 16.5 Presentation mode

从文档菜单进入，隐藏文件侧栏与编辑工具，保留Next step、Evidence、Reset presentation、Exit。采用可调大字号和高对比内容面；默认不把应用所有按钮都粗暴缩放。

展示进度与数学执行状态分离：隐藏未揭示的结果不等于删除或重算；第一次需验证的内容仍由真内核产生。Reset presentation只重置揭示进度，Restore example才恢复模板。退出恢复原选择、视口和检查器开闭。[B §14.5]

---

## 17. 原生状态与组件契约

### 17.1 文档、派生结果、视图状态

```text
SourceDocument
  documentID / schemaVersion / documentKind
  source payloads + unknown extension fields
  groups[]: groupID, stepOrder[], assumptions
  steps[]: stepID, acceptedSource, provenance
  canvas objects + geometry + ink assets + ink linkage
  contentRevision / semanticRevision / per-object inkRevision

DerivedResults
  documentID / groupID / stepID or relationID
  semanticRevision / inputHash / assumptionsHash
  engineID / engineVersion / normalizationVersion
  taskState / freshness / resultType / diagnostics / evidence

WindowViewState
  windowID / documentID
  canvas camera / Steps scroll anchor / source selection
  selected object IDs / selected relationID
  inspector visibility / pinned target / active tab
  transient palette / preview revision / presentation cursor

SaveState
  latestContentRevision / durableLocalRevision / savedTargetRevision
  destination identity / pending write / failure / conflict
```

以上是新增设计契约，不是现有Bridge字段原样复制。自由笔迹、对象几何和绑定是用户资产，须持久化；相机、面板开闭才是ViewState。[B §15.2、§15.5]

### 17.2 revision规则

| 变化 | contentRevision | semanticRevision | inkRevision | 数学结果 |
| --- | --- | --- | --- | --- |
| accepted source改变 | +1 | +1 | 视情况 | 当前与后续依赖失效 |
| 条件/参数改变 | +1 | +1 | 不变 | 实际依赖失效 |
| 步骤数学顺序改变 | +1 | +1 | 不变 | 受影响关系失效 |
| 笔迹回改，尚未确认 | +1 | 不变 | +1 | 对应新笔迹的结果不能视为当前；旧accepted source结果仅历史可看 |
| 对象平移/缩放/换色 | +1 | 不变 | 几何/样式版本单列，不改内容笔迹版本 | 不重算数学 |
| 画布camera/面板开闭 | 不变 | 不变 | 不变 | 不重算、不触发文档dirty |
| XDLT纯布局改变 | +1 | 依据语义hash不变 | 不适用 | 不失效无关数学结果 |

任务接受条件：documentID、目标ID、requestID仍有效，输入语义hash、条件hash和engine身份匹配当前accepted source；绑定笔迹有未确认回改时，结果不能挂到新笔迹上。纯布局修改不应令相同数学请求全部作废，因此运行协议的revision明确指semanticRevision，不混用保存版本。

### 17.3 呈现决策伪代码

```text
presentation = project(
    acceptedInput,
    pendingInkEdit,
    taskState,
    freshness,
    stepMathState,
    incomingRelation,
    upstreamFault,
    provenance
)

// 必须穷尽类型；未知枚举降级为可读的未识别状态，而不是默认success。
// 颜色与文案只能由presentation映射，View不能自行猜数学含义。
// certificate verified ≠ equivalent；task succeeded ≠ mathematical valid。
```

服务新增未知状态时保留原始枚举、来源与reason，显示 `Result type not recognized`，不要让默认分支画绿勾。

### 17.4 组件目录

| Component | 输入 | 输出/动作 | 关键约束 |
| --- | --- | --- | --- |
| DocumentShell | document title, saveState, capabilities | navigation, document commands | 不持有数学真值 |
| CanvasViewport | scene, camera, selection | hit-test, camera, selection intents | 高频绘制不由整个页面重建驱动 |
| InkLayer | stroke data, tool mode, inkRevision | stroke transaction | 不发内核运行请求 |
| EquationObject | stepID, representation, presentation | select, edit, inspect | 几何与source分离 |
| DerivationRail | stepOrder, relation presentations | selectRelation, reorder | 连线方向来自顺序，不来自坐标猜测 |
| ContextPalette | selection, capabilities, anchor | commandID | 按空间裁剪与可访问替代 |
| RecognitionReview | inkRevision, candidates, mapping | confirm/reject/edit | 旧候选不能确认到新笔迹 |
| EvidenceInspector | explicit target, result projection | probe, transform, repair | 不读取模糊全局“当前行” |
| MathComparison | before/after typed data | copy, reveal | 自适应横/纵排；不混淆Undefined |
| TransformSheet | operationID, parameter, preview | commit transformation | 提交快照与预览哈希一致 |
| WritingWorkspace | source, session, compilation result | source edits, safe compile | parse/render与execute分开 |
| SaveStatusView | save state, durable revision | retry/save copy | 真实确认后才显示Saved |
| CapabilityNotice | featureID, availability, reason | configure/learn/type instead | 不因核心失败自动切Demo |

### 17.5 View组织建议

```text
App
  DocumentSession per document/window
    DocumentShell
      NotebookWorkspace
        CanvasWorkspace / StepsWorkspace
        EvidenceInspector
        RecognitionReview
        TransformSheet
      WritingWorkspace / EdlatexWorkspace
      SaveStatusView
      DocumentCommandRegistry
  CapabilityRegistry
  Settings
```

SwiftUI适合应用壳、面板、状态与可访问控件；高频笔画与复杂文本编辑可以封装原生专用视图。不要为了“全SwiftUI”把每个采样点变成页面级状态更新，也不因使用PencilKit就假定它负责公式识别。[P1；B §14.4、§15.4]

### 17.6 History与事务

事务最小单位分别为完整笔画、连续文本编辑会话、对象移动手势、结构重排、变换提交、识别确认、条件修改。Undo文案与动作类型一致，例如 `Undo Add Step`。

跨层动作一次Undo回到一致状态：识别确认撤销后step/source/ink绑定一起恢复；不能留下没有source的绿色结论或没有笔迹的引用。历史恢复的派生结果必须重新做新鲜度检查；只恢复相同文本不足以证明engine和条件也相同。

---

## 18. 命令、菜单与快捷键

以下是设计拟定绑定，交付时必须从同一个已注册command生成菜单、按钮、长按Command帮助和可访问动作，并验证与目标系统快捷键的冲突；未实现命令不显示假的快捷提示。[B G03–G04]

| 操作 | 拟定绑定 | 触摸入口 | 焦点条件 |
| --- | --- | --- | --- |
| New document | ⌘N | Documents / New | 不打断未处理的保存错误 |
| Open/import | ⌘O | Documents / Import | 进入真实文档选择流程 |
| Save now | ⌘S | 标题菜单 / Save | 必须等待写入确认 |
| Undo / Redo | ⌘Z / ⇧⌘Z | 顶部Undo / Redo | 文本、笔迹与结构事务协调 |
| Check step | ⌘Return | Check step | 已选中数学步骤 |
| Check and advance | ⇧Return | Check and next | 数学编辑器且非输入法组合态 |
| Check group / Continue | ⇧⌘Return | Check菜单 | 当前推导组 |
| Inspector toggle | ⇧⌘I | Inspect | 不篡改选区 |
| Find | ⌘F | 文档菜单 / Find | 在当前文档已支持文本范围内 |
| Close transient UI | Esc | Close / Cancel | 先关Popover/退出编辑，再处理更外层 |
| Delete selection | Delete / Backspace | 选区菜单 / Delete | 仅画布选择焦点；文本编辑时仍删除字符 |
| Duplicate | ⌘D | Duplicate | 仅对象选择焦点；命令注册时检查冲突 |
| Fit selection | 菜单显示，绑定待冲突检查 | 缩放菜单 / Fit selection | 有选区 |
| Stop checking | 菜单显示，绑定待冲突检查 | Stop checking | 确有活跃任务 |
| Next step | 菜单显示，绑定待冲突检查 | Next step | 有当前组执行游标 |

不把F5/F10作为iPad必要入口；不预占⌘Space等系统命令。帮助中的每个绑定必须通过真实键盘事件端到端验收。

---

## 19. 可访问性与特殊输入

### 19.1 VoiceOver

画布必须有线性等价路径：按推导组和stepOrder访问Steps/Inspector，不能要求屏幕阅读器用户在二维坐标中“摸”到每根笔画。纯自由笔迹标为Ink并可附手动描述，不假装已识别。[B §14.3、§18.5]

步骤读法示例：“步骤2，x减1等于0。与步骤1相比丢失解，x等于0。当前结果。动作：查看证据、编辑、变换。”Tainted读法包含来源步骤；条件式必须读出条件。

状态更新只在用户主动检查完成、焦点对象有重要变化、保存失败时做有节制的播报。后台每次局部解析、hover、光标移动不连续抢占语音。

### 19.2 色觉与对比

每种状态必须同时具有文字和至少一种图形/结构区别。绿色Verified、黄色Condition、红色Fault都不能只靠底色；关系方向必须能被读出。

增强对比度下加深分隔与选区边缘；Reduce Transparency与Reduce Motion独立响应。深色不是简单反相，笔迹和公式对比度分别验收。

### 19.3 Dynamic Type

Inspector与Steps大字号自然重排：并列比较转纵向、按钮换行、顶部控件进入菜单，不把文字截成仅首字。44pt是命中下限而非大字号行高上限。

自由笔迹不随字体设置变形；用户仍可zoom，并通过已提交公式的文本表示阅读。长条件、诊断和文件名应能展开全文，而非只有Tooltip。

### 19.4 触摸、指针与Switch Control

所有P0流程不需要键盘、hover或squeeze：新建、输入、检查、Probe、变换、修复、保存、撤销都能由可访问按钮完成。拖动动作提供Move/Reorder菜单替代；捏合有Zoom按钮替代；圈选有Steps列表多选替代。

用户选择、Pencil绘图与系统文本选择区分；公式和诊断可复制，不能因一层手势拦截使整个Inspector内容不可选。[B §14.3]

---

## 20. UI 验收矩阵

所有条目是待实现验收，不是本次已经在iPad完成的测试。交付截图必须包含状态数据，不能只给没有真实输入的“理想成功页”。

### 20.1 数学语义与失败用例

| ID | 输入/动作 | 必须观察到 |
| --- | --- | --- |
| Q01 | `x(x-1)=0` → `x-1=0` → `x=1` | 第2步首错、丢失0、后续影响来源，不把第3步本式可求解当整组正确 |
| Q02 | `sqrt(x)=x-2` → `x=(x-2)^2` | 依真实内核识别新增1；Probe x=1前式不成立、后式成立 |
| Q03 | `(x-1)/(x-1)=1` → `1=1`，Probe x=1 | Before为Undefined，不是False；定义域排除点可见 |
| Q04 | `x^2-2=0` | 当前能力无法表示无理根，不显示空解集或绿色等价 |
| Q05 | `x^3=1`、`y=1`、原始`0.5x=1` | 分别按实际能力/解析结果说明，不自动换变量或猜答案 |
| Q06 | `x^2+1=0` | 真正无实数解显示∅，不混为Unverified |
| Q07 | 除以x预览 | 非零条件常显，不静默将原题全局限制为x≠0 |
| Q08 | 有效平方证书 | 能显示certificate verified与单向蕴含，不画成无条件等价 |
| Q09 | API成功但业务ok=false | 失败状态，不画成功 |
| Q10 | Probe/null或补全空列表 | 明确无结果/不可用，不回退到Mock |
| Q11 | 新枚举IndependentFault或未知状态 | 保留语义和reason，不落入默认success |
| Q12 | 拟合不了的exact数、区间端点 | 原精度/边界保留，溢出不改成近似verified |

### 20.2 Canvas、识别与历史

| ID | 输入/动作 | 必须观察到 |
| --- | --- | --- |
| Q13 | 把第3式拖到第1式上方 | 顺序与数学结论不变，只有几何修改 |
| Q14 | 使用Reorder修改顺序 | 有编号预览，当前/后续关系正确失效 |
| Q15 | 圈选两道独立题 | 可拆组、改顺序；不自动连成一条推导 |
| Q16 | 识别后、返回前改写笔迹 | 旧候选不能提交，保持inkRevision一致 |
| Q17 | 修改已验证绑定笔迹 | 立即显示回改未确认，旧绿色状态不挂在新笔迹上 |
| Q18 | 在旁边添加普通注记 | 不使无关Math step失效 |
| Q19 | 点Use equation然后Undo | step/source/ink linkage一起恢复，不留孤儿对象 |
| Q20 | 识别器缺失 | 笔迹保留，Type equation可用，不显示假候选 |
| Q21 | x与×歧义 | 必须确认，不能未经选择提交乘法/变量 |
| Q22 | 无精确token映射的Witness | 只高亮整式，不伪造笔画级对应 |
| Q23 | 替换错误第2步，原第3步仍丢解 | 新检查继续指出后续错误，不显示“全部修复” |
| Q24 | Canvas↔Steps来回切换 | 相同stepID/source/result，不增文档副本、不重新识别 |

### 20.3 异步、保存与恢复

| ID | 输入/动作 | 必须观察到 |
| --- | --- | --- |
| Q25 | 检查过程中修改source | 迟到旧结果不覆盖新revision |
| Q26 | 连续快速更换选区 | Panel最终对应最新selection，无旧动画队列 |
| Q27 | 保存期间再编辑，旧保存晚返回 | savedTargetRevision准确；最新修改不伪装已保存 |
| Q28 | 提供者断开/空间不足 | 常驻失败、Retry/Save copy，已恢复本机与目标已保存分开 |
| Q29 | 新建未命名画布，写字后重启 | 草稿与笔画可恢复，状态反映实际持久化确认 |
| Q30 | 导入未知版本后关闭 | 原文件不被空白/降级覆盖 |
| Q31 | 同文档并行窗口 | 协调或只读保护，不相互覆盖 |
| Q32 | Stop后后端仍返回 | 不称已终止、不接受已失效返回 |
| Q33 | Undo/Redo跨笔画、文本、变换 | 事务顺序一致，不一次撤销两次 |
| Q34 | 向旧nm导出有画布笔迹文档 | 明确不支持内容，原生文档不被覆盖 |

### 20.4 XDLT、可访问性与适配

| ID | 输入/动作 | 必须观察到 |
| --- | --- | --- |
| Q35 | 导入含Python无限循环的XDLT并预览 | 不自动执行；运行需真实隔离能力与显式授权 |
| Q36 | 编辑后旧编译结果晚到 | 不覆盖最新revision；Previous preview标签准确 |
| Q37 | DOM patch失败 | 最新全量render回退，保留阅读锚点，无旧HTML倒灌 |
| Q38 | invalid/unknown/unverified/error断言 | 四种情形独立文案，另保留valid及有条件valid |
| Q39 | 卡片缺失、条件unknown | 原文/引用/来源保留，不写“已满足” |
| Q40 | PDF能力不可用 | 不能点击出假成功或空文件 |
| Q41 | 深浅主题、大字号、增强对比 | 文字可读，长式不撑开窗口，比较区可纵排 |
| Q42 | Reduce Motion/Transparency | 能完成同样动作，状态不缺失，没有自动飞行/透明干扰 |
| Q43 | 纯触摸、无Pencil/无键盘 | 所有核心流程可完成 |
| Q44 | VoiceOver | 按组/步骤访问，能听见条件、首错、Tainted来源与保存失败 |
| Q45 | 外接键盘+中文输入法 | 快捷键真实执行；候选确认不意外运行 |
| Q46 | 多种窗口宽高+软/浮动键盘 | 光标和Check仍可达，底部面板与工具不重叠 |
| Q47 | 200步、长公式、大笔迹与快速拖动 | 记录各层耗时；超限准确提示，不承诺不存在的内核容量 |
| Q48 | 断网但本机C++可用 | 正式检查仍可用；AI/远端服务分别说明状态 |

### 20.5 设计验收尺寸

以可用窗口宽度320、390、600、768、900、1024、1180、1366pt和高度480、600、900pt组成代表性测试组合；不要求所有笛卡尔组合都是真实设备，而是测试容器布局。特别测试断点±24pt、200%及最大可访问字号、键盘出现和Inspector开闭。

内容用例至少包含：空画布、仅笔迹、单式、50与200步、多组、长分式、负数有理数、超长条件、中文与数学混排、错误堆叠、缺失backend、保存失败。超出后端公开限制的文档可保存/阅读，但运行明确报告范围；不能悄悄分批后拼成一个未经证明的整体结论。

---

## 21. 设计交付与实施顺序

### 21.1 交付包A：可信核心

DocumentShell、Documents、Steps、EquationObject的键盘路径、Inspector、Witness/Probe、Transform、SaveState与History。以真实C++迁移、四个golden示例与保存失败验证闭环；没有Pencil也可完成数学任务。

### 21.2 交付包B：Canvas与原生笔迹

加入可持久化Ink、世界坐标、组顺序与场景映射、圈选、几何编辑、Pencil工具和适配布局。这个阶段明确是可书写的数学画布，不宣称已有手写识别；可以选择Ink后键入对应公式。画布资产存储与撤销必须先于视觉包装完成。

### 21.3 交付包C：手写语义闭环

接入经选型的识别器，完成Recognition review、歧义、确认、回改、原文映射与陈旧请求丢弃。完成这一包后才可把“手写公式检查”作为产品主能力。演示稿可以提前设计，发布承诺不能提前。

### 21.4 交付包D：写作与高级能力

XDLT编辑/预览与增量会话先行；断言、Context、Cards、edlatex、AI、执行与导出按真实后端能力逐个开放。Python与PDF缺失时仍能编辑保存源文，但不得宣称完整迁移。[B §17]

### 21.5 动画不留到最后统一添加

A阶段即接入press/selection/status/save反馈；B阶段实现panel几何与camera稳定；C阶段实现候选/回改过渡；D阶段实现局部preview更新。每次状态测试同时验收动画打断与Reduce Motion，避免后补一个全局`.animation`造成整页抖动。

### 21.6 关键设计稿必须有的画面

一组画面至少包括：Light与Dark主画布、宽窗三栏、窄窗检查、Pencil圈选Palette、识别歧义、Ink changed、丢根Inspector、Undefined Probe、有条件变换、修复后仍有后续错误、保存失败、XDLT执行被阻止、大字号与Reduce Motion说明。

不要只交付一张很漂亮的“所有状态都是成功”的首页。Prototype中的Mock可以用于设计测试，但必须以fixture标识隔离，不能进入真实验证服务的fallback链路。

---

## 22. 基线问题到UI规则的追踪

| 基线问题 | 本稿对应章节 | 阻止的错误 |
| --- | --- | --- |
| G03、G04 | §8、§18、Q45 | 假快捷键、Shift+Enter不推进 |
| G06、G07、G28 | §13、§17、Q27–Q29 | 假已保存、草稿丢失、保存策略混乱 |
| G08–G10、G29 | §7、§9、§17、Q16–Q17、Q25 | 旧数学结果冒充当前结果 |
| G11、G12 | §9–§10、Q04–Q06、Q11 | 不支持/首行被画成等价 |
| G13 | §11 | 补全字段丢失、按中文label猜intent |
| G14、G15、G16 | §5、§10、§16、Q10 | Mock混入正式结果、Probe目标不明确 |
| G17、G18 | §11、Q19、Q23 | 插入一行就宣称修复、提交时序竞态 |
| G19、G20 | §8、§12、Q32 | 假性能承诺、假计算中止 |
| G21、G22 | §14、Q35–Q37 | 预览自动执行、超时误报离线 |
| G23、G30 | §12、§14、§17 | 把缓存称完整增量parser、混淆数值来源 |
| G24、G25、G31 | §14–§16、§21 | 隐藏高级能力/缺口、伪PDF与假availability |
| G01、G02 | §2、§13、§15 | 文件类型混写、只改后缀称兼容 |
| G26、G32、G33 | §20–§21 | 界面接上方法名即声称完成；必须真实合同和用户路径验收 |

---

## 23. 参考资料与来源说明

### [B] 附件功能基线

`NEOMATH_DARWIN_FUNCTIONAL_SPEC.md`  
标题：NeoMath 全功能扫描与 NeoMath.Darwin iPadOS 产品参考文档。扫描日期：2026-10-04。

来源文件SHA-256：

```text
f8b06b196db698fffc6db87f84bdb7c645a6e629fb436809113c98bbaca49702
```

本文没有重新审计其仓库或复跑其258个Python测试、25个Node测试与C++测试。功能事实取自该扫描报告；本文新增的是界面、交互和验收提案。特别是手写识别、画布数据层、统一能力注册和新存储容器，并非据此证明已存在。

### [P1] Apple：Squeeze the most out of Apple Pencil，WWDC24

已核对官方讲解中的PKToolPicker自定义工具、Pencil Pro squeeze、Hover数据、系统偏好、离散动作与反馈限制。本文只据此说明平台输入边界，不据此宣称PencilKit自带数学识别。

```text
https://developer.apple.com/videos/play/wwdc2024/10214/
```

### [P2] Apple：onPencilSqueeze(perform:)

官方API说明：为Apple Pencil squeeze添加响应。具体采用方式与部署目标仍须工程核验；本文不锁定最低系统版本。

```text
https://developer.apple.com/documentation/swiftui/view/onpencilsqueeze%28perform%3A%29
```

### [P3] Apple：Reduce screen motion on your iPhone, iPad, or iPod touch

已核对官方支持说明中Reduce Motion下用dissolve替代部分缩放/滑动、减少视差与动画的行为。本文80ms等具体数值是自行提出的设计token，不是Apple强制值。

```text
https://support.apple.com/en-us/111781
```

平台资料核对日期：2026-10-04。尺寸、颜色、断点、快捷键提案及动画时长全部以本文的[D]设计决定为准，不冒充系统规范原文。

---

**最终体验目标：用户始终知道自己选中了哪一段数学、软件究竟理解了什么、什么结论已经得到证明，以及下一次落笔会改变什么。**
