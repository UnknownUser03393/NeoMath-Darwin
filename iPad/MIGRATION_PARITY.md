# Darwin 原版对照 · 2026-10-11

依据：`origin/main` 的 `src/App.tsx`、`Documents.tsx`、`CanvasView.tsx`、`BackendInspector.tsx`、`MathTools.tsx` 和 `NEOMATH_DARWIN_UI_SPEC.md`。准确提交号见 `Reference/upstream-commit.txt`。

首次交付把原设计缩成了基础编辑表单。它丢失了信息架构和交互层级，不能作为设计迁移的验收结果。本轮纠正如下。

| 原版内容 | 初版问题 | 当前实现与验收 |
| --- | --- | --- |
| Documents 首页 | 换成了系统侧栏 | 恢复原版 Examples → Writing → Recent 分区、搜索、列表/网格、全部公式预览；移除擅加的分类页签，已实际操作 |
| 文档头部 | 标题重复、视图占独立一行 | Documents 返回、标题菜单、View/Check/Inspect/More；窄宽度自然换行 |
| Live Preview | 删除，所有公式常驻输入框 | 恢复默认预览，未编辑公式数学排版，点击揭示源文并聚焦；Done 恢复排版；已实测 |
| Canvas | 普通垂直列表 | 1600×至少1200 世界坐标画布，原版112pt步骤节奏，双向平移和25%–400%缩放 |
| 数学排版 | 系统圆体显示原始字符串 | 原生 SwiftMath，公式、根式、分式、集合、候选式和 Inspector 共用排版；已修正单行裁切 |
| 关系与联动 | 只放一行错误文字 | 关系标记位于前后两式之间，前式弱高亮/后式强高亮；选择公式/关系联动 Inspector；已实测 |
| 工具层 | 简化到一排按钮 | Pen/Eraser/Select/Equation/+ 与独立缩放/Fit/Grid 工具层；缩放与Fit已实测 |
| Inspector | 单一字段列表、窄屏模态弹窗 | Overview/Evidence/Details，方程比较、Before/After解集、Witness、Substitute、Probe、Pin、Transform；横屏344pt停靠、竖屏非模态摘要/展开面板 |
| Witness | 有字段但没有原版证据层级 | 自动x=0显示前True/后False；Evidence手动Probe实际操作通过 |
| Transform | 四个英文命令直接插入 | 核心语义候选、数学预览、风险和不可用状态；实际验证插入与撤销，原文已恢复 |
| 配色和材质 | 系统默认配色、默认点阵 | 严格使用规范§4.1的冷中性色token，点阵默认关闭，仅工具层使用材质 |
| 文件与笔迹 | 原生基本保存 | 保留`.nm`扩展元数据、浏览器旧笔迹字段、独立PencilKit数据；已有用户笔迹保留 |

## 本轮补齐

- Live Preview 改为单一原生 UITextView body：活动行源文、非活动行数学排版、多行选择、稳定步骤 ID、IME 暂停检查、光标锚定候选、占位符及依赖连接线。候选触摸操作及方向键选择/Enter 插入已实测并撤销还原；Ctrl+Space 已在后续专项验收中实际触发，详见下节。
- 移植原版 `math-format.ts` 的显示格式转换，覆盖嵌套根式、分式、幂、函数、区间和集合；不在 UI 计算数学结果。
- 结构化变换支持参数与失败反馈；原生 trace 使用现有 C++ replay，并展示真实缓存命中。后端模式接入 runTrace/replay、变换、Notebook 保存/刷新、AI 解释与配置。
- Writing 工作位已接入原版 create/update/destroy 编译会话、增量 HTML 补丁、源码映射、自动编译、保存、验证、执行和 Debug 信息。预览使用原 lockfile 的 KaTeX 0.19.0 与字体。
- Inspector 补齐步骤值、验证方法与限制、引擎/可信度、解释来源、源文定位和异步结果防过期。旧浏览器笔迹映射到 PencilKit，保留原元数据。
- 重复构建/测试/安装/截图及本机后端启动封装到 `scripts/neomath`，从任意目录可调用。

## c269779 真后端接通与验收

最新 `main` 已建立本地基线，现有根目录文件、旧 `desktop/` 和原生项目改动保留；操作前快照在 `/tmp/neomath-before-c269779`。没有重置或提交本地工作。

- 按 `BACKEND_SETUP.md` 构建安装 `backend/` 的 Python、C++ 扩展和 SymPy 1.14.0；以 `backend/.venv/bin/python -m neomath --serve --host 127.0.0.1 --port 8765` 运行真实服务。工作区 `/tmp/neomath-ipad-acceptance`，原生模拟器已启用该 API。
- health 成功；`engine: auto` 的 `x^2=2 → x=±sqrt(2)` 实际选择 SymPy，返回两根完整解集和等价关系；模拟器 Overview/Details 显示相同解集、引擎及验证限制。
- 模拟器参数变换：选第一式、multiply、输入 3、应用后插入 `3*x^2=6`；结果为等价且解集不变。Undo 还原原始两式，手动 Check 后再次得到完整解集。divide 参数 0 显示 `CAS_INPUT: 不能除以零`，没有插入步骤。
- Writing 新建独立验收文档，实际编辑公式与上下文，自动编译预览更新；删除上下文后重新加入 x 符号正常增量编译。`claim x > 0` 显示黄色 `status: unknown`。Save marker 4 保存、关闭、重开源文一致，API 读回逐字匹配，当前文件还保留既有 `#assert:error { claim x = 0 }` 解析错误验收块，SHA256 为 `8c7d0b154cbb9daa9c84b64ccad93e649b5026dd7f0323d3355b0895ca77bfb1`。
- `sin(x)=x` 的真实 Unknown 在模拟器显示 Unverified、ConditionSet 和 verification unknown。`x=)` 显示错误原因及 Unknown。已验证的 `x=1` 改为 `x^50+x+1=0` 后，检查期间清除旧状态，真实六秒 worker 超时显示 CAS_TIMEOUT；关闭提示后检查器仍显示超时，不保留绿勾或成功状态。
- 所有 Notebook 数学 API 自动规范为 `engine: auto`、`document.source`；Swift 客户端真实集成测试覆盖 CAS、Unknown、参数、拒绝除零、超时和旧状态清除。没有 mock 后端。

实际修复：顶层 source 导致 CAS 空结果；空/不完整 trace 被接受；未知集合误回退为 ℝ；重查/取消/异常残留旧结果；Writing 并发保存顺序；编译等待或失败仍显示旧预览；XDLT 新增上下文符号导致旧依赖图 KeyError；Windows 专用扩展后缀测试。新增回归验证增量编译结果与完整编译一致。

真实 API 证据：`Reference/backend-acceptance-c269779.json`。截图：`acceptance-writing-c269779.png`、`acceptance-unknown-c269779.png`、`acceptance-timeout-c269779.png`。

## 全页面实际操作复验 · 2026-10-11

参照 `c269779` 原始源码和隔离运行的原版 React 页面（`http://127.0.0.1:5174`），在同一个 iPad Pro 11-inch M4 / iOS 18.6 模拟器实际操作以下页面。数学请求均访问真实 `http://127.0.0.1:8765/api`，`engine: auto`，未使用 mock。测试仅添加隔离工作区的验收文档，保留原有文档、笔迹和未提交改动。

| 页面 / 入口 | 实际完成的操作与可见结果 |
| --- | --- |
| Documents | 全部八个原版示例分别打开；中文、英文搜索过滤；Recent 列表和网格切换、Refresh；数学预览、更新时间；New derivation 以 `x = 1` 创建；New writing document 直接创建 UUID 文件并打开 |
| Settings | 完整独立页面；System → Dark → Light → System 均显示正确选择；真实 Connect/refresh 展示隔离 Workspace 和离线解释状态；保存后显示 Saved；返回原页面 |
| Document editor | 修改标题和每式源码；添加 Equation、Text、删除、Undo/Redo；关闭和重新打开仍保留标题与内容；正负根通过实际 Shift 键输入，自动检查后两根完整；输入期间保留光标和 marked text |
| Live Preview | 原位源文与排版切换；底部状态栏、Transform 和 Complete 常驻；光标位置补全；方向键/Enter 实际选择求导并插入结果；Esc 关闭且不改变源码 |
| Steps | 有序数学卡片、首式 Initial state、关系状态；选择第二式联动 Overview 的 Before/After 与真实解集；竖屏折叠工具栏、展开工具栏和非模态 Inspector 摘要/完整面板 |
| Canvas | Select 选公式和关系，Pin/Unpin；Equation 编辑、Add 菜单；Zoom in/out、Fit、Grid；开启 finger drawing 后 Pen 实际画线、Undo 消失、Redo 恢复、Eraser 实际擦除，再恢复 finger drawing 关闭 |
| Inspector Overview | 解集、Lost/Gained、定义域对照；丢解的 0、平方增解的 1、约分导致域扩大和 Undefined → True 均显示真实证据；Substitute 代入前后公式；Explain 展示真实 local 来源 |
| Inspector Evidence / Details | 手动 Probe 1/2，显示实际左右值与布尔结果；真实引擎、trust、verification method/limitations；Unknown 显示 Unverified，原因不再声称 SymPy 已验证 |
| Transform palette | multiply 参数 3，应用 `3*x^2=6`、Undo、重新 Check；divide 参数 0 拒绝且不插入；differentiate 与 integrate 实际执行，分别插入 `3*x^2+cos(x)` 和 `x^4/4-cos(x)`；候选明确区分等价、计算结果及定义域/根风险 |
| Writing | 自动编译、Auto compile 关闭后 Pending 并隐藏旧预览、重新开启立即编译；Verify assertions、Run exec 开关；保存并重开逐字一致；预览点击数学块定位并选中完整源块；Debug 显示 revision 3、reusedParsing 1、reusedVerification 1；竖屏操作条自然两行、全部按钮可见 |
| 系统文件 Import / Export | 实际 Export `.nm` 到 On My iPad；通过 Import 系统文件选择器选中该文件；新副本保留导数前后两式；文件实际存在并含原始 JSON 元数据 |

八个示例结果：正负无理根和三次方程由 SymPy 给出完整根；不等式给出真实区间；函数恒等式和独立求导表达式因 backend verification 为 unknown 保守显示 Unverified；Lost roots、Squaring 和 Domain change 给出真实 Core 关系、丢/增解与反例。不能因表达式已计算就显示“验证成功”。

本轮修复还包括：

- 恢复原首页分区、八个完整预览和按钮层级；恢复 Steps 卡片、完整文档编辑面板、独立 Settings，工具栏可折叠。
- health 改用 GET；更新时间真实排序；设置保存显示 Saved；导出默认名使用当前 `.nm` 文件名。
- Writing update 响应没有 sessionId 时保留现有会话，避免每次编辑重新 create；本地维护连续 revision，使增量 HTML patches 实际生效；过期 WKWebView 回调不能覆盖当前预览。
- 保存显式等待队列；重新开启 Auto compile 立即编译当前待编译源文；区分 Pending/Compiled/Compiling。
- 文档输入保留选区、组合文字期间不覆盖 UITextView；编辑面板活动字段可直接打开 Transform，支持 Ctrl/Command+Enter 检查；不完整或 Unknown 的说明不再残留成功文案。
- Fit 取消会互相回写的缩放动画，原子设置缩放和原点，复验分式左侧不再裁切；无穷端点始终使用开括号；Inspector 显示 domainExpanded/domainShrunk。

当前截图：`Reference/parity-documents.png`、`parity-settings-dark.png`、`parity-steps-inspector.png`、`parity-canvas-domain.png`、`parity-writing-portrait.png`、`parity-writing-source-map.png`。它们来自实际模拟器，没有用设计 mock 替代。

最终回归：原 C++ 12 个用例及桥接、Swift 文档测试通过；真实 Swift HTTP 客户端 health、完整 CAS 根、Unknown 原因、参数、除零与真实 worker timeout 通过；真实 API acceptance 的七个数学入口及 XDLT 增量与既有保存文件逐字读回通过；模拟器 Debug 和设备 Release 构建通过。325 个后端测试已在上一轮通过，本轮 UI 修复未改后端数学实现。

## Ctrl+Space 专项验收 · 2026-10-11

原生 `LiveBodyTextView` 增加物理 Control+Space 按键处理，保留 UIKeyCommand 优先路由；不往源文插入空格，组合输入期间不触发补全，带其他修饰键的输入继续交给系统。候选 Esc、插入完成和外部关闭后恢复编辑器 first responder，允许连续键盘操作。

这台 Mac 的「Select the previous input source」默认占用 Ctrl+Space。复现日志只有 Control（HID 224），没有 Space（HID 44），证明空格被宿主系统截走。通过 System Settings 暂时关闭该冲突后，实际输入收到 HID 44 + Control，候选成功打开。验收结束已恢复该 Mac 设置为 enabled，未永久修改用户输入法快捷键；Simulator 的显式 Send Keyboard Input to Device 也不能绕过此次宿主拦截。以后在这台 Mac 做快捷键验收，须暂时释放宿主 Ctrl+Space。原生 App 无法接收被 macOS 截走的组合键。

最终构建的真实模拟器操作（整个流程没有点击 Complete）：

1. 在 `x^3+sin(x)` 源文内放置光标，按 Ctrl+Space 打开五项真实后端候选。
2. Esc 关闭，然后不点击源文，直接 Ctrl+Space 再次打开；源文仍逐字为 `x^3+sin(x)`。
3. ↓↓↓、Enter 选择求导，插入且保存 `3*x^2 + cos(x)`；原式无多余空格。
4. 插入后不点击编辑器，再次 Ctrl+Space 成功打开候选；Esc 关闭不修改两式。

截图 `Reference/acceptance-ctrl-space.png` 为最终构建用快捷键打开的真实候选。原生模拟器 Debug、设备 Release 构建通过。真实硬件键盘和中文 IME 仍需设备验收，不将模拟器结果扩大为这些硬件条件已通过。

## Mac 快捷键冲突已永久解除 · 2026-10-11

按用户后续明确要求，将 Mac「Select the previous input source」从 Ctrl+Space 改为 **Ctrl+Shift+Space**，保持 enabled。设置页面实际显示 `⌃⇧Space`，保存后的 preferences 参数为 `[32,49,393216]`；仅修改这一条（60），其他快捷键保持原值。上节“临时关闭后恢复”的记录是此前验收历史，当前不再占用 Ctrl+Space，验收后保留新组合。

本次重新实际操作模拟器：源文内 Ctrl+Space 打开真实后端五项候选 → Esc → 不点击编辑器直接 Ctrl+Space 再打开 → ↓↓↓↓ / Enter 插入 `x^4/4 - cos(x)` → 无需点击直接 Ctrl+Space 再打开。没有点击 Complete。原有导数步骤保留，隔离验收文档为三式。模拟器 Capture Keyboard 保持开启，便于直接使用快捷键。

截图：`Reference/acceptance-ctrl-space-permanent.png`。没有 Apple Pencil 时，Settings → Draw with finger 开启后可在 Canvas 的 Pen 工具下手指绘画；Select、Equation、公式编辑、补全与变换均可触控。

## 仍未验证与产品限制

- 在线 Qwen API 未配置，在线模型调用未验收；本次数学和 Writing 走实际本机后端。
- URLSession 网络传输级 15 秒超时、真实设备/LAN 连接、服务端多客户端同时编辑同一文件尚未验收。本次超时验收是实际 SymPy worker 六秒计算超时。
- 全部 Dynamic Type、极窄多任务窗口、真实 Apple Pencil/硬件键盘及中文 IME 组合输入仍需设备验收；Ctrl+Space、方向键/Enter、Esc 已专项验收；Mac 宿主的输入源快捷键冲突现已按用户要求永久解除。
- 离线原生 C++ 仍使用保留的旧 desktop 核心；连接后端 auto 的支持范围已实际验证，不能将其能力等同于离线核心。
- 混合公式/笔迹圈选、自由公式拖动、Pencil squeeze/hover、无限画布和正式 Presentation 在当前 origin/main 也没有完整实现，属于后续产品功能。

## 验证记录

- 原 C++ 12 个测试，桥接 trace/replay/witness/probe/参数变换与候选，以及 Swift 文档、源文投影、显示格式和后端结果归一化回归。
- 新版后端及数学语义审计：325 个测试通过（包括新增符号增量编译回归）；原生 C++/桥接/Swift 回归及真实后端 Swift 客户端集成通过。
- iPad Pro 11-inch M4 / iOS18.6 实际 UI：Documents、默认 Live Preview 原位编辑、光标候选数学预览、依赖连接线、关系选择、Overview/Evidence、Probe、缩放/Fit、变换插入/撤销。
- Writing 实测：编译、断言验证、Python 执行、预览定位源文、编辑后自动编译与保存、后端读回确认。测试使用隔离 `/tmp/neomath-ipad-acceptance`。
- 验收保留模拟器现有文档和笔迹。

## 2026-10-11 配色和动效补迁

按 src/index.css 恢复 90ms 按压缩放、400ms 页面淡入/24pt 位移、260ms 面板缓动；覆盖页导航、视图模式、动作折叠、文档编辑和 Inspector 展开。主题及 Inspector 使用 matchedGeometryEffect 滑动选中块，Canvas 工具恢复只展开当前工具标签及滑动选中块。补齐 onAccent、neutral、dot 明暗色值，修正深色 New derivation 文字颜色，Backend 输入框/按钮恢复 subtle 背景与 accent 按钮。所有新增运动尊重 Reduce Motion。

模拟器 Debug 构建成功；实际操作深色主题、返回 Documents、打开 Lost roots、展开 Inspector、Overview→Evidence、Pen→Eraser→Select。截图 acceptance-motion-color-dark.png。本次没有逐帧录像对比，也没有重新验收 Writing 和所有弹层的动效，不能视为完整视觉一致性验收。

### 第二轮配色复验

Steps 状态底色恢复原版 light 8% / dark 12% 混合比例及按压样式；Transform 建议卡恢复 subtle/10pt 圆角及按压样式，解释结果恢复 subtle 卡片。参数区域切换和解释内容有 180ms 过渡，遵循 Reduce Motion。Writing UIKit 源码显式使用 ink/accent 动态色，预览遵循原版白色纸面。

模拟器最新 Debug 构建成功。实际打开 Transform→multiply 参数框→Cancel、切换 Steps；切换 Light 并检查 Settings；搜索 F72 打开真实 XDLT，查看编译结果及 Unknown 黄标、开 Debug、返回保存、改 Dark 重开同一文档。源码一致，明暗文字清晰。截图 acceptance-writing-color-light.png / acceptance-writing-color-dark.png。此次未逐帧录像验收，也未穷举所有弹层。

## 用户截图反馈：减少拥挤

Writing 导航栏改为文档标题（优先正文一级标题）、Compile、保存、Writing options；New、Auto compile、Verify assertions、Run exec、Debug 移至选项菜单，全部保留原绑定和编译回调。Inspector 去掉 Before/After 的内层底色卡片，缩减外层内边距，减少视觉嵌套。

模拟器最新构建通过；实际打开 F72 文档，确认正文标题、当前编译预览；打开选项菜单确认三个开关与 Debug；返回并打开用户已有 x=5+10→x=15，Inspect step 2 看到等价、解集及定义域，正文未改动。截图 acceptance-writing-spacious.png / acceptance-inspector-spacious.png。此次以 11-inch 横屏验收，窄窗口未复验。用户截图底部灰色菜单为系统快捷键 HUD，实际新截图无该遮挡。

## 最新：恢复用户输入法并移除信息冗余

覆盖早期永久改键记录：Mac symbolichotkeys 60 已恢复 enabled true / [32,49,262144]（Ctrl+Space），activateSettings 已执行；App 补全使用 Ctrl+.，移除 CtrlSpace/CommandSpace 的 keyCommands。模拟器 Capture Keyboard 为 1 时 Ctrl+. 实际打开真实后端候选（未点击 Complete）。宿主语言切换未实际确认。

移除顶部 Check finished 耗时缓存状态、Live 底部 Checked/core/Saved；保留 Inspector Details 中数学状态。见证默认不显示左右数值，Substitute 后展开。Edit document 改为独立 large sheet，真实 UI 打开确认 Title、三个源文与预览、Done、添加操作完整。构建通过；文档内容未改动。

## 2026-10-11 iPad 公式模板输入

新增原生 MathInput：分数、根号、幂、括号、函数和关系符模板，自动选中 □ 空位，前后空位导航与 Exit 退出括号。选中表达式可包装为模板。保留普通表达式输入及即时排版预览。Live Preview 可直接点击排版公式进入编辑；Canvas 选择公式同样打开编辑器。新增邻近工作区的 Simplify、Move terms、Solve 与 Both sides 参数弹层，复用真实后端变换和撤销历史；应用后自动选中新步骤。没有新增 crossfade，没有改变 Ctrl+. 补全或 Mac 输入法快捷键。

实际模拟器验收（iPad Pro 11-inch M4 / iOS 18.6）：

- 输入 x、点 x²、点 =、输入 2 得到 x^2=2；直接 Solve 真实后端得到 x=-sqrt(2) or x=sqrt(2)，Inspector Equivalent，两侧解集一致。
- 点分数模板、填 x、Next blank 填 2，得到 (x)/(2)=1；Both sides → Divide 参数 4 → Apply 插入 (x / 2) / (4) = (1) / (4)。撤销、重做及 Inspector Equivalent 通过。
- 保存后终止进程、安装最新构建、重新打开同一文档，两条分数源文完整恢复；只读检查 Documents/NeoMath-notebooks.json 与此前快照一致。随后直接 Solve 添加 x = 2，Edit equation 打开的是新插入的 x = 2，自动选中通过；新结果也已落盘。
- 实际点击排版分数打开编辑；根号模板填 2、Exit、追加 +1 得到 x=sqrt(2)+1，排版正确。完整软键盘在横屏、竖屏下实际展开，预览、模板、空位导航和 Done 可见。

模拟器 Debug 和签名真机 Debug 构建成功；新版已安装至连接的 iPad。自动启动被 iPad 锁屏拒绝，因此本轮真机触控流程尚未复验。模板包装任意选区与所有函数组合未穷举；Writing 正文输入未改动。输入仍使用普通表达式文本加模板，不是完整二维结构光标编辑器。

### 交互复改：页内连续编辑（10:30）

公式编辑改为工作区底部紧凑面板，移除数学编辑 large sheet；保留上方推导并高亮当前公式。提供常用数字和符号的触控键盘，复杂输入可切换系统键盘。Next step 复制当前公式并立即编辑新步骤；空白或未填完模板时禁用。新增 Select all 和删除键；撤销新步骤时清理失效编辑目标。Add equation 也进入该编辑区。数学输入仍为表达式文本加模板，不声称支持直接点击排版中的分子/指数编辑。

实际模拟器操作：全程点按钮输入 x^2=2，Next step 后点按钮输入 x=±sqrt(2)，Check/Inspector 返回 SymPy Equivalent 与相同解集；另一独立文档点按钮完成分数两个空位、退出括号和等号，得到 (x)/(2)=1，Solve 得到 x = 2。系统键盘/数学键盘切换通过，横竖屏布局检查通过。终止进程并安装最新构建后重开，两条分数推导内容一致。新建第三步后 Undo 恢复两步并关闭失效编辑区，操作栏正常恢复。

模拟器及签名 iPad 构建通过，新版安装成功。截图 /tmp/neomath-inline-math-input.png。真机触控与窄分屏窗口未在本轮验证。

### Writing / XDLT 公式输入与窄屏布局（2026-10-11 11:25）

Writing Source 增加 Equation：光标位于独立 $$ 公式块时编辑块内容，否则在当前选区插入公式块；Apply 自动维护分隔符，Cancel 不改正文。页内复用紧凑数学键盘，Writing 模板使用 LaTeX 的 frac/sqrt/pm 等命令，推导页保持普通表达式语法。窄于 1000pt 的窗口使用 Write / Preview 分段切换，宽屏仍为双栏。重新编译时保留旧预览并明确标记待更新，禁用旧预览的源码定位；编译失败仍清空结果并显示错误。没有新增 crossfade。

模拟器实际点按：新建 Writing，在正文末尾插入 x^2=2，自动编译与 Saved 状态通过；重启后重新打开相同文档内容一致。将光标置于公式内部，再用数学键盘将其改为 frac{x}{2}=sqrt{2} 的 LaTeX 形式，纸面正确显示分数和根号；真实 loadXdltDocument 读回源文一致。取消草稿不改正文；竖屏 Write/Preview 切换和整页纸面预览通过。文档名 3528CEC4-C6FE-461C-8046-977000BC6B9B，独立验收数据。

本轮未重新穷举断言/执行块、Unknown/错误/超时状态；这些逻辑未修改。公式工具目前识别独立 $$ 块，不是完整 XDLT 富文本编辑器；行内公式、代码围栏内分隔符和复杂宏的编辑尚未覆盖。
