# NeoMath Demo Video Pipeline

比赛演示视频自动化生产流水线。
阿里云·AI少年 Vibe Coding 创新挑战活动。

## 目录结构

```
video/
├── recording.html          ← 录制画布（PPT/解释场景）
├── recording-playwright.mjs ← 自动录制 recording.html 各场景
├── record-slides.mjs       ← 连续录制所有幻灯片场景
├── record-product.mjs      ← 录制真实 NeoMath UI 演示
├── record-ide.mjs          ← 录制 IDE/AI 协作演示
├── demo-helpers.mjs        ← Playwright 演示自动化工具库
├── storyboard.md           ← 分镜脚本
├── narration.md            ← 旁白文稿（中文，带时间码）
├── recording-scenes.md     ← 场景清单与时长
├── selectors.md            ← UI Selector 参考
├── package.json
└── output/                 ← 生成的视频和截图
    ├── 01-hook.webm
    ├── 01-hook-step0.png
    ├── ...
    ├── product-lost-root.png
    ├── product-all-demos.webm
    └── slides-all.webm
```

## 快速开始

### 1. 安装依赖

```bash
cd video
npm install
npx playwright install chromium
```

### 2. 录制幻灯片画布

```bash
# 逐场景录制（视频 + 截图）
node recording-playwright.mjs

# 仅截图
node recording-playwright.mjs --png-only

# 单个场景
node recording-playwright.mjs --scene hook

# 连续录制全部幻灯片
node record-slides.mjs
```

### 3. 录制真实产品 Demo

先启动后端：

```bash
cd ../desktop
python -m neomath --serve
```

然后录制：

```bash
node record-product.mjs                     # 全部 Demo
node record-product.mjs --demo lost-root    # 仅丢根
```

### 4. 录制 IDE 协作

```bash
# 如果 IDE 支持 CDP（VS Code / Cursor）：
code --remote-debugging-port=9222
node record-ide.mjs --cdp http://127.0.0.1:9222

# 否则查看脚本输出的替代方案
node record-ide.mjs
```

## recording.html API

```javascript
// Playwright 中控制场景
await page.evaluate(() => NeoMathRecording.goto('problem'));
await page.evaluate(() => NeoMathRecording.setStep(2));
await page.evaluate(() => NeoMathRecording.waitForIdle());
await page.evaluate(() => NeoMathRecording.getState());
// → { scene: 'problem', step: 2, animating: false, scenes: [...] }

// URL 控制
// recording.html?scene=trust-model&step=1
// recording.html?debug=1
```

## 键盘快捷键（手动预览 recording.html）

- `→` / `Space` — 下一步
- `←` — 上一步
- `R` — 重置
- `D` — 切换调试覆盖层

## 视频规格

| 属性 | 值 |
|------|-----|
| 分辨率 | 1920 × 1080 |
| 格式 | WebM (Playwright) → MP4 (ffmpeg) |
| 目标时长 | 3:30 ~ 4:20 |
| 背景 | #0f0f0f |
| 字体 | Inter / SF Pro / PingFang SC / system-ui |
