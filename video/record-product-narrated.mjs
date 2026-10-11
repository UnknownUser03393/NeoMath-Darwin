/**
 * record-product-narrated.mjs
 *
 * Re-records each product demo with paced timing matching narration.
 * Produces 3 separate videos: product-04-lost-root, product-05-semantic,
 * product-06-xdlt — each held for the correct narration duration.
 */
import { chromium } from 'playwright';
import { dirname, resolve, join } from 'path';
import { fileURLToPath } from 'url';
import { existsSync, mkdirSync } from 'fs';
import { demoClick, demoType, hold } from './demo-helpers.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUTPUT_DIR = resolve(__dirname, 'output');
const VITE_URL = 'http://127.0.0.1:5174';

function visible(sel) { return `.editor-pane:not(.hidden) ${sel}`; }

// Narration-hold: target duration minus action overhead
const DUR = { s04: 37.1, s05: 19.0, s06: 23.4 };

async function main() {
  if (!existsSync(OUTPUT_DIR)) mkdirSync(OUTPUT_DIR, { recursive: true });
  const videoDir = join(OUTPUT_DIR, 'tmp-product-narrated');
  if (!existsSync(videoDir)) mkdirSync(videoDir, { recursive: true });

  // --- Shared browser session ---
  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-notifications', '--disable-translate'],
  });

  const page = await (await browser.newContext({ viewport: { width: 1920, height: 1080 }, colorScheme: 'dark' })).newPage();
  await page.goto(VITE_URL, { timeout: 20000, waitUntil: 'networkidle' });
  await page.waitForSelector('.app-shell', { timeout: 15000 });
  await page.waitForSelector('nav[aria-label="工作区推导文件"]', { timeout: 15000 });
  await hold(page, 1500);

  const errors = [];

  // ============================================================
  // Scene 04 — Lost Root Demo (target: 37.1s)
  // ============================================================
  console.log('\n=== Scene 04: Lost Root (37.1s) ===');
  {
    const ctx = await browser.newContext({
      viewport: { width: 1920, height: 1080 },
      deviceScaleFactor: 1,
      colorScheme: 'dark',
      recordVideo: { dir: videoDir, size: { width: 1920, height: 1080 } },
    });
    const pg = await ctx.newPage();
    pg.on('pageerror', e => errors.push(e.message));
    await pg.goto(VITE_URL, { timeout: 20000, waitUntil: 'networkidle' });
    await pg.waitForSelector('.app-shell', { timeout: 15000 });
    await pg.waitForSelector('nav[aria-label="工作区推导文件"]', { timeout: 15000 });
    await hold(pg, 1200);

    // 1. Open demo (3s)
    const fileEl = pg.locator('[data-demo-id="sidebar-file-丢根.nm"]');
    await fileEl.waitFor({ state: 'visible', timeout: 10000 });
    await demoClick(pg, fileEl, { prePause: 300, postPause: 800 });
    await pg.waitForSelector(visible('[data-demo-id="derivation-program"]'), { timeout: 15000 });
    console.log('  Demo loaded');
    await hold(pg, 1500);

    // 2. Click Continue (2s)
    await demoClick(pg, visible('[data-demo-id="toolbar-continue"]'), { prePause: 500, postPause: 500 });

    // 3. Wait for Root Fault (up to 5s)
    try {
      await pg.waitForSelector(visible('[data-demo-id="step-break-banner"]'), { timeout: 10000 });
      console.log('  Root Fault visible');
      await hold(pg, 3000);
    } catch { await hold(pg, 5000); }

    // 4. Focus on witness / diagnostic (4s)
    const summary = pg.locator(visible('[data-demo-id="diagnostic-summary"]'));
    if (await summary.count() > 0) {
      const box = await summary.boundingBox();
      if (box) await pg.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 10 });
      await hold(pg, 3000);
    } else { await hold(pg, 3000); }

    // 5. Move to inspector (2s)
    const inspector = pg.locator(visible('[data-demo-id="debug-inspector"]'));
    if (await inspector.count() > 0) {
      const box = await inspector.boundingBox();
      if (box) await pg.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 10 });
      await hold(pg, 2000);
    } else { await hold(pg, 2000); }

    // 6. Click "一键代回" (3s for click + result)
    const witnessBtn = pg.locator(visible('[data-demo-id="witness-apply"]'));
    if (await witnessBtn.count() > 0) {
      await demoClick(pg, witnessBtn, { prePause: 300, postPause: 1000 });
      try {
        await pg.waitForSelector(visible('[data-demo-id="witness-probe-summary"]'), { timeout: 8000 });
        console.log('  Probe result visible');
        await hold(pg, 5000);
      } catch { await hold(pg, 5000); }
    } else { await hold(pg, 3000); }

    // Pad remaining time to reach ~37s
    await hold(pg, 3000);

    const video = pg.video();
    await pg.close();
    if (video) { await video.saveAs(join(OUTPUT_DIR, 'product-04-lost-root.webm')); console.log('  Saved'); }
    await ctx.close();
  }

  // ============================================================
  // Scene 05 — Semantic Completion (target: 19.0s)
  // ============================================================
  console.log('\n=== Scene 05: Semantic Completion (19.0s) ===');
  {
    const ctx = await browser.newContext({
      viewport: { width: 1920, height: 1080 },
      deviceScaleFactor: 1,
      colorScheme: 'dark',
      recordVideo: { dir: videoDir, size: { width: 1920, height: 1080 } },
    });
    const pg = await ctx.newPage();
    pg.on('pageerror', e => errors.push(e.message));
    await pg.goto(VITE_URL, { timeout: 20000, waitUntil: 'networkidle' });
    await pg.waitForSelector('.app-shell', { timeout: 15000 });
    await pg.waitForSelector('nav[aria-label="工作区推导文件"]', { timeout: 15000 });
    await hold(pg, 1200);

    // 1. Open demo (2s)
    const fileEl = pg.locator('[data-demo-id="sidebar-file-语义补全.nm"]');
    await fileEl.waitFor({ state: 'visible', timeout: 10000 });
    await demoClick(pg, fileEl, { prePause: 200, postPause: 800 });
    await pg.waitForSelector(visible('[data-demo-id="derivation-program"]'), { timeout: 15000 });
    await hold(pg, 800);

    // 2. Click Continue (1s)
    await demoClick(pg, visible('[data-demo-id="toolbar-continue"]'), { prePause: 300, postPause: 500 });

    // 3. Wait for completion bar (3s)
    try {
      await pg.waitForSelector(visible('[data-demo-id="completion-bar"]'), { timeout: 8000 });
      console.log('  Completion bar visible');
      await hold(pg, 1500);

      // 4. Click 因式分解 (2s)
      const chip = pg.locator(visible('[data-demo-id="completion-bar"] .completion-chip')).first();
      if (await chip.count() > 0) {
        const text = await chip.textContent();
        console.log(`  Clicking: ${text?.trim()}`);
        await demoClick(pg, chip, { prePause: 300, postPause: 3000 });
      }
    } catch { await hold(pg, 4000); }

    // Pad
    await hold(pg, 5000);

    const video = pg.video();
    await pg.close();
    if (video) { await video.saveAs(join(OUTPUT_DIR, 'product-05-semantic.webm')); console.log('  Saved'); }
    await ctx.close();
  }

  // ============================================================
  // Scene 06 — XDLT Edit (target: 23.4s)
  // ============================================================
  console.log('\n=== Scene 06: XDLT (23.4s) ===');
  {
    const ctx = await browser.newContext({
      viewport: { width: 1920, height: 1080 },
      deviceScaleFactor: 1,
      colorScheme: 'dark',
      recordVideo: { dir: videoDir, size: { width: 1920, height: 1080 } },
    });
    const pg = await ctx.newPage();
    pg.on('pageerror', e => errors.push(e.message));
    await pg.goto(VITE_URL, { timeout: 20000, waitUntil: 'networkidle' });
    await pg.waitForSelector('.app-shell', { timeout: 15000 });
    await pg.waitForSelector('nav[aria-label="工作区推导文件"]', { timeout: 15000 });
    await hold(pg, 1200);

    // 1. Click XDLT file in sidebar (3s)
    const xdltNav = pg.locator('nav[aria-label="工作区 XDLT 文档"]');
    if (await xdltNav.count() > 0) {
      const xdltFile = xdltNav.locator('.file-item').first();
      if (await xdltFile.count() > 0) {
        await demoClick(pg, xdltFile, { prePause: 200, postPause: 1200 });
      }
    }

    // 2. Wait for XDLT workspace
    try {
      await pg.waitForSelector(visible('[data-demo-id="xdlt-workspace"]'), { timeout: 8000 });
      console.log('  XDLT loaded');
      await hold(pg, 2000);
    } catch { await hold(pg, 3000); }

    // 3. Make a small edit (6s)
    const editor = pg.locator(visible('[data-demo-id="xdlt-editor"]'));
    if (await editor.count() > 0) {
      await demoClick(pg, editor, { postPause: 300 });
      await pg.keyboard.press('Meta+End');
      await hold(pg, 300);
      await demoType(pg, editor, '\n% NeoMath 演示 — 热传导公式推导', { charDelay: 60, postPause: 500 });
      await hold(pg, 3000);
    }

    // Pad
    await hold(pg, 8000);

    const video = pg.video();
    await pg.close();
    if (video) { await video.saveAs(join(OUTPUT_DIR, 'product-06-xdlt.webm')); console.log('  Saved'); }
    await ctx.close();
  }

  await browser.close();

  if (errors.length) {
    console.warn(`\nErrors (${errors.length}):`);
    errors.forEach(e => console.warn('  ', e));
  }
  console.log('\nProduct narrated recordings done.');
}

main().catch(err => { console.error('Fatal:', err); process.exit(1); });
