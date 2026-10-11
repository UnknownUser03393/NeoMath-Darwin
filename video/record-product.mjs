/**
 * record-product.mjs
 *
 * Records the real NeoMath UI performing the core demos:
 *   1. Lost Root Demo (primary — Scene 04, hero product demo)
 *   2. Semantic Completion Demo (Scene 05)
 *   3. XDLT workspace edit (Scene 06)
 *
 * All selectors use data-demo-id attributes added to the NeoMath UI components.
 * Uses the presentation automation layer (demo-helpers.mjs) for human-paced interaction.
 *
 * IMPORTANT: The NeoMath UI uses a tabbed editor where multiple panes exist
 * in the DOM simultaneously. Only the pane without `.hidden` class is visible.
 * All selectors MUST be scoped to `.editor-pane:not(.hidden)` to avoid matching
 * elements in hidden (display:none) panes.
 *
 * Usage:
 *   node record-product.mjs                     # all demos
 *   node record-product.mjs --demo lost-root    # single demo
 */
import { chromium } from 'playwright';
import { dirname, resolve, join } from 'path';
import { fileURLToPath } from 'url';
import { existsSync, mkdirSync } from 'fs';
import {
  demoClick, demoType, demoKey, focusElement, hold, waitForClass,
} from './demo-helpers.mjs';

/** Scope a data-demo-id selector to the visible editor pane. */
function visible(sel) {
  return `.editor-pane:not(.hidden) ${sel}`;
}

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUTPUT_DIR = resolve(__dirname, 'output');

const VITE_URL = 'http://127.0.0.1:5174';

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = { demo: null };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--demo' && args[i + 1]) opts.demo = args[++i];
  }
  return opts;
}

/**
 * Open a demo notebook from the sidebar by file name.
 * The app starts with an "empty" state (no open tabs).
 * We click the sidebar file item to open the demo.
 */
async function openDemo(page, fileName) {
  console.log(`  Opening demo: ${fileName}`);

  // Wait for sidebar to be loaded with files
  await hold(page, 1000);

  // The sidebar has file items. Look for the specific file.
  const fileEl = page.locator(`[data-demo-id="sidebar-file-${fileName}"]`);
  try {
    await fileEl.waitFor({ state: 'visible', timeout: 10000 });
    console.log('  Sidebar file found, clicking to open...');
    await demoClick(page, fileEl, { prePause: 300, postPause: 1500 });
  } catch {
    // Fallback: try by text
    console.log('  ID-based lookup failed, trying text lookup...');
    const sidebarNav = page.locator('nav[aria-label="工作区推导文件"]');
    const fileLink = sidebarNav.getByText(fileName, { exact: false }).first();
    if (await fileLink.count() > 0) {
      await demoClick(page, fileLink, { prePause: 300, postPause: 1500 });
    } else {
      console.error(`  Cannot find "${fileName}" in sidebar`);
      // Dump sidebar content for debugging
      const text = await page.locator('.notebook-sidebar').textContent();
      console.error(`  Sidebar text: ${text?.slice(0, 500)}`);
      return false;
    }
  }

  // Wait for the derivation program to appear in the visible (non-hidden) pane.
  // The app has multiple panes in DOM; we must target only the active one.
  try {
    await page.waitForSelector(visible('[data-demo-id="derivation-program"]'), { timeout: 15000 });
    console.log('  Notebook loaded');
  } catch {
    console.error('  Notebook did not load');
    return false;
  }

  await hold(page, 1000);
  return true;
}

/** Record the Lost Root demo — the hero product demo (Scene 04). */
async function recordLostRoot(page) {
  console.log('\n  === Lost Root Demo ===\n');

  // Step 1: Open the demo
  if (!await openDemo(page, '丢根.nm')) return;

  // Step 2: Check that the derivation has math steps
  const steps = page.locator('.debug-step');
  const stepCount = await steps.count();
  console.log(`  Found ${stepCount} derivation steps`);

  // Step 3: Click "开始调试" (Continue / F5)
  await demoClick(page, visible('[data-demo-id="toolbar-continue"]'), { prePause: 400, postPause: 500 });

  // Step 4: Wait for execution to hit root fault
  try {
    await page.waitForSelector(visible('[data-demo-id="step-break-banner"]'), { timeout: 15000 });
    console.log('  Root Fault break banner appeared');
    await hold(page, 1200);
  } catch {
    console.log('  Waiting for breakpoint class instead...');
    try {
      await page.waitForSelector('.debug-step.breakpoint', { timeout: 5000 });
      await hold(page, 1200);
    } catch {
      console.log('  Warning: No breakpoint detected — using mock runtime?');
      await hold(page, 2000);
    }
  }

  // Step 5: Focus on the break banner (diagnostic summary)
  const summary = page.locator(visible('[data-demo-id="diagnostic-summary"]'));
  if (await summary.count() > 0) {
    await focusElement(page, summary, { holdMs: 2000 });
  }

  // Step 6: Focus on debug inspector (right panel has witness)
  await focusElement(page, visible('[data-demo-id="debug-inspector"]'), { holdMs: 2000 });

  // Step 7: Click "一键代回" button
  const witnessApplyBtn = page.locator(visible('[data-demo-id="witness-apply"]'));
  if (await witnessApplyBtn.count() > 0) {
    await demoClick(page, witnessApplyBtn, { prePause: 600, postPause: 1200 });

    // Step 8: Wait for probe summary text to appear
    try {
      await page.waitForSelector(visible('[data-demo-id="witness-probe-summary"]'), { timeout: 8000 });
      await hold(page, 2000);
      console.log('  Witness probe result visible');
    } catch {
      console.log('  Probe result did not appear');
    }
  } else {
    console.log('  Witness apply button not found — already clicked or UI differs');
  }

  await hold(page, 1000);
  console.log('  Lost Root demo complete');
}

/** Record the Semantic Completion demo (Scene 05). */
async function recordSemanticCompletion(page) {
  console.log('\n  === Semantic Completion Demo ===\n');

  // Step 1: Open the semantic completion demo
  if (!await openDemo(page, '语义补全.nm')) return;

  // Step 2: Click Continue to run the analysis
  await demoClick(page, visible('[data-demo-id="toolbar-continue"]'), { prePause: 300, postPause: 800 });

  // Step 3: Wait for the completion bar or transform palette to appear
  try {
    await page.waitForSelector(
      `${visible('[data-demo-id="completion-bar"]')}, ${visible('.transform-palette')}`,
      { timeout: 10000 }
    );
    const completionBar = page.locator(visible('[data-demo-id="completion-bar"]'));
    if (await completionBar.count() > 0 && await completionBar.isVisible()) {
      console.log('  Completion bar appeared');
      await hold(page, 1000);
      const chip = completionBar.locator('.completion-chip').first();
      if (await chip.count() > 0) {
        const text = await chip.textContent();
        console.log(`  Clicking completion chip: ${text?.trim()}`);
        await demoClick(page, chip, { prePause: 400, postPause: 1500 });
      }
    } else {
      // Try TransformPalette
      const palette = page.locator(visible('.transform-palette'));
      if (await palette.count() > 0 && await palette.isVisible()) {
        console.log('  Transform palette appeared');
        await hold(page, 1000);
        // Click the "因式分解" button
        const factorBtn = palette.locator('.transform-chip').filter({ hasText: '因式分解' });
        if (await factorBtn.count() > 0) {
          await demoClick(page, factorBtn, { prePause: 400, postPause: 1500 });
        } else {
          // Just click the first chip
          const firstChip = palette.locator('.transform-chip').first();
          if (await firstChip.count() > 0) {
            await demoClick(page, firstChip, { prePause: 400, postPause: 1500 });
          }
        }
      }
    }
  } catch {
    console.log('  Neither completion bar nor transform palette appeared');
    await hold(page, 2000);
  }

  await hold(page, 1500);
  console.log('  Semantic Completion demo complete');
}

/** Record a small XDLT edit (Scene 06). */
async function recordXdlt(page) {
  console.log('\n  === XDLT Workspace Demo ===\n');

  // Step 1: The XDLT documents are in the sidebar under "XDLT 文档 (.xdlt)"
  const xdltNav = page.locator('nav[aria-label="工作区 XDLT 文档"]');
  let opened = false;

  if (await xdltNav.count() > 0) {
    const xdltFile = xdltNav.locator('button').first();
    if (await xdltFile.count() > 0) {
      await demoClick(page, xdltFile, { prePause: 300, postPause: 1500 });
      opened = true;
    }
  }

  if (!opened) {
    console.log('  Could not find XDLT file in sidebar, trying direct nav...');
    // The sidebar might list "示例.xdlt"
    const demoFile = page.locator('[data-demo-id="sidebar-file-示例.xdlt"]');
    if (await demoFile.count() > 0) {
      await demoClick(page, demoFile, { prePause: 300, postPause: 1500 });
      opened = true;
    }
  }

  if (opened) {
    // Wait for XDLT workspace
    try {
      await page.waitForSelector(visible('[data-demo-id="xdlt-workspace"]'), { timeout: 8000 });
      console.log('  XDLT workspace loaded');
      await hold(page, 1200);

      // Step 2: Make a small edit in the XDLT editor
      const editor = page.locator(visible('[data-demo-id="xdlt-editor"]'));
      if (await editor.count() > 0) {
        await demoClick(page, editor, { postPause: 400 });

        // Navigate to end and add a line
        await page.keyboard.press('Meta+ArrowDown');
        await demoType(page, editor, '\n% NeoMath 演示编辑', { charDelay: 60, postPause: 800 });
        console.log('  Edit made, waiting for recompile...');

        // Wait for the debug panel / status to update
        await hold(page, 2500);
      }
    } catch (e) {
      console.log(`  XDLT not available: ${e.message}`);
    }
  } else {
    console.log('  XDLT demo skipped — no XDLT files in workspace');
  }

  console.log('  XDLT demo complete');
}

async function main() {
  const opts = parseArgs();
  if (!existsSync(OUTPUT_DIR)) mkdirSync(OUTPUT_DIR, { recursive: true });

  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-notifications', '--disable-translate', '--no-first-run'],
  });

  const videoDir = join(OUTPUT_DIR, 'tmp-product');
  if (!existsSync(videoDir)) mkdirSync(videoDir, { recursive: true });

  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    colorScheme: 'dark',
    recordVideo: {
      dir: videoDir,
      size: { width: 1920, height: 1080 },
    },
  });

  const page = await context.newPage();

  const errors = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('pageerror', err => errors.push(err.message));

  // Navigate to the app (Vite dev server on 5174, proxies /api to :8765)
  console.log(`Navigating to ${VITE_URL}...`);
  await page.goto(VITE_URL, { timeout: 20000, waitUntil: 'networkidle' });

  // Wait for app shell to load (sidebar will seed demos automatically)
  try {
    await page.waitForSelector('.app-shell', { timeout: 15000 });
    console.log('App shell loaded');
  } catch {
    console.error('App shell did not load');
    await page.screenshot({ path: join(OUTPUT_DIR, 'product-error-startup.png') });
    await browser.close();
    process.exit(1);
  }

  // Wait for workspace seeding to complete — sidebar should show files
  // Look for either the sidebar nav or until the "loading" text disappears
  try {
    await page.waitForSelector('nav[aria-label="工作区推导文件"]', { timeout: 15000 });
    console.log('Sidebar workspace loaded');
  } catch {
    console.error('Sidebar did not load');
    await page.screenshot({ path: join(OUTPUT_DIR, 'product-error-sidebar.png') });
  }
  await hold(page, 1500);

  // Initial screenshot
  await page.screenshot({ path: join(OUTPUT_DIR, 'product-initial.png') });
  console.log('Initial screenshot captured');

  const demos = opts.demo ? [opts.demo] : ['lost-root', 'semantic-completion', 'xdlt'];

  for (const demo of demos) {
    switch (demo) {
      case 'lost-root':
        await recordLostRoot(page);
        break;
      case 'semantic-completion':
        await recordSemanticCompletion(page);
        break;
      case 'xdlt':
        await recordXdlt(page);
        break;
      default:
        console.warn(`Unknown demo: ${demo}`);
    }

    const pngPath = join(OUTPUT_DIR, `product-${demo}.png`);
    await page.screenshot({ path: pngPath });
    console.log(`  Screenshot: ${pngPath}`);
  }

  // Save video
  const video = page.video();
  await page.close();

  if (video) {
    const webmPath = join(OUTPUT_DIR, 'product-all-demos.webm');
    try {
      await video.saveAs(webmPath);
      console.log(`\nVideo saved: ${webmPath}`);
    } catch (e) {
      console.warn(`Could not save video: ${e.message}`);
    }
  }

  await context.close();
  await browser.close();

  if (errors.length) {
    console.warn(`\nJS Errors (${errors.length}):`);
    errors.forEach(e => console.warn('  ', e));
  }

  console.log('\nProduct recording done.');
}

main().catch(err => {
  console.error('Fatal:', err);
  process.exit(1);
});
