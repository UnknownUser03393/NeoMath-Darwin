/**
 * recording-playwright.mjs
 *
 * Automated scene-by-scene recorder for video/recording.html.
 * Produces per-scene .webm video files and PNG keyframe captures.
 *
 * Usage:
 *   node recording-playwright.mjs                 # record all scenes
 *   node recording-playwright.mjs --scene hook     # record one scene
 *   node recording-playwright.mjs --png-only       # keyframes only, no video
 */
import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import { dirname, resolve, join } from 'path';
import { existsSync, mkdirSync } from 'fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const RECORDING_HTML = resolve(__dirname, 'recording.html');
const OUTPUT_DIR = resolve(__dirname, 'output');

// Timing per scene: [sceneName, [[step, holdMs], ...]]
const SCENE_TIMING = [
  ['hook',             [[0, 2500], [1, 2500]]],
  ['problem',          [[0, 2200], [1, 2200], [2, 2200], [3, 3000]]],
  ['workflow',         [[0, 1800], [1, 1200], [2, 1200], [3, 2500]]],
  ['trust-model',      [[0, 2000], [1, 1800], [2, 3500]]],
  ['engineering',      [[0, 1500], [1, 3500]]],
  ['ai-collaboration', [[0, 2000], [1, 2500]]],
  ['reflection',       [[0, 3000], [1, 3000]]],
  ['end',              [[0, 3500]]],
];

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = { scene: null, pngOnly: false };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--scene' && args[i + 1]) {
      opts.scene = args[++i];
    } else if (args[i] === '--png-only') {
      opts.pngOnly = true;
    }
  }
  return opts;
}

async function main() {
  const opts = parseArgs();

  if (!existsSync(OUTPUT_DIR)) mkdirSync(OUTPUT_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    ignoreHTTPSErrors: true,
    colorScheme: 'dark',
    reducedMotion: 'no-preference',
  });

  const page = await context.newPage();

  // Collect console errors
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', err => errors.push(err.message));

  const fileUrl = `file://${RECORDING_HTML}`;
  await page.goto(fileUrl);

  // Wait for fonts
  await page.evaluate(() => document.fonts?.ready);
  await page.waitForTimeout(300);

  // Verify API exists
  const hasApi = await page.evaluate(() => typeof window.NeoMathRecording !== 'undefined');
  if (!hasApi) {
    console.error('ERROR: NeoMathRecording API not found on page');
    await browser.close();
    process.exit(1);
  }

  const scenes = opts.scene
    ? SCENE_TIMING.filter(([name]) => name === opts.scene)
    : SCENE_TIMING;

  if (scenes.length === 0) {
    console.error(`Scene "${opts.scene}" not found. Available:`, SCENE_TIMING.map(s => s[0]).join(', '));
    await browser.close();
    process.exit(1);
  }

  console.log(`Recording ${scenes.length} scene(s)...\n`);

  for (const [sceneName, steps] of scenes) {
    const idx = SCENE_TIMING.findIndex(s => s[0] === sceneName);
    const prefix = String(idx + 1).padStart(2, '0');
    const videoPath = join(OUTPUT_DIR, `${prefix}-${sceneName}.webm`);

    console.log(`  Scene: ${sceneName} (${steps.length} steps)`);

    // Reset to scene
    await page.evaluate(name => NeoMathRecording.goto(name, 0), sceneName);
    await page.evaluate(() => NeoMathRecording.waitForIdle());
    await page.waitForTimeout(200);

    // Start recording (unless png-only)
    let recorder = null;
    if (!opts.pngOnly) {
      // Use page.video() approach: need to create a new context with recordVideo
      // Instead, we use screencast approach via CDP
    }

    // For each step: set step, wait for idle, hold, capture keyframe
    for (const [step, holdMs] of steps) {
      await page.evaluate(s => NeoMathRecording.setStep(s), step);
      await page.evaluate(() => NeoMathRecording.waitForIdle());
      await page.waitForTimeout(100); // Small buffer after animation

      // Capture keyframe PNG
      const pngPath = join(OUTPUT_DIR, `${prefix}-${sceneName}-step${step}.png`);
      await page.screenshot({ path: pngPath, type: 'png' });
      console.log(`    Step ${step}: captured → ${pngPath}`);

      if (!opts.pngOnly) {
        await page.waitForTimeout(holdMs);
      }
    }

    // Check for overflow
    const hasOverflow = await page.evaluate(() => {
      const stage = document.getElementById('stage');
      return stage.scrollWidth > 1920 || stage.scrollHeight > 1080;
    });
    if (hasOverflow) {
      console.warn(`    ⚠  Overflow detected in scene "${sceneName}"`);
    }
  }

  // If not png-only, record via video context approach
  if (!opts.pngOnly) {
    console.log('\n  Recording video sequences...');

    for (const [sceneName, steps] of scenes) {
      const idx = SCENE_TIMING.findIndex(s => s[0] === sceneName);
      const prefix = String(idx + 1).padStart(2, '0');
      const videoDir = join(OUTPUT_DIR, 'tmp-video');
      if (!existsSync(videoDir)) mkdirSync(videoDir, { recursive: true });

      const videoContext = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
        deviceScaleFactor: 1,
        colorScheme: 'dark',
        recordVideo: {
          dir: videoDir,
          size: { width: 1920, height: 1080 },
        },
      });

      const videoPage = await videoContext.newPage();
      await videoPage.goto(`file://${RECORDING_HTML}?scene=${sceneName}&step=0`);
      await videoPage.evaluate(() => document.fonts?.ready);
      await videoPage.waitForTimeout(400);
      await videoPage.evaluate(() => NeoMathRecording.waitForIdle());

      for (const [step, holdMs] of steps) {
        await videoPage.evaluate(s => NeoMathRecording.setStep(s), step);
        await videoPage.evaluate(() => NeoMathRecording.waitForIdle());
        await videoPage.waitForTimeout(holdMs);
      }

      // Extra hold at end
      await videoPage.waitForTimeout(500);

      // Close page to finalize video
      const video = videoPage.video();
      await videoPage.close();

      if (video) {
        const webmPath = join(OUTPUT_DIR, `${prefix}-${sceneName}.webm`);
        try {
          await video.saveAs(webmPath);
          console.log(`    Video: ${webmPath}`);
        } catch (e) {
          console.warn(`    ⚠  Could not save video for ${sceneName}: ${e.message}`);
        }
      }

      await videoContext.close();
    }
  }

  // Report
  console.log('\n--- Report ---');
  if (errors.length) {
    console.warn(`JS Errors (${errors.length}):`);
    errors.forEach(e => console.warn('  ', e));
  } else {
    console.log('No JS errors detected.');
  }

  // Check fonts
  const fontsReady = await page.evaluate(() => document.fonts.status);
  console.log(`Fonts status: ${fontsReady}`);

  await browser.close();
  console.log('\nDone.');
}

main().catch(err => {
  console.error('Fatal:', err);
  process.exit(1);
});
