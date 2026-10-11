/**
 * record-slides.mjs
 *
 * Records presentation slide sequences from recording.html.
 * Simpler wrapper around recording-playwright.mjs that
 * produces one continuous video of all slide-type scenes.
 *
 * Usage:
 *   node record-slides.mjs
 */
import { chromium } from 'playwright';
import { dirname, resolve, join } from 'path';
import { fileURLToPath } from 'url';
import { existsSync, mkdirSync } from 'fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const RECORDING_HTML = resolve(__dirname, 'recording.html');
const OUTPUT_DIR = resolve(__dirname, 'output');

// Scene sequence with hold times per step (ms)
const SEQUENCE = [
  { scene: 'hook',             steps: [2500, 2500] },
  { scene: 'problem',         steps: [2200, 2200, 2200, 3000] },
  { scene: 'workflow',        steps: [1800, 1200, 1200, 2500] },
  { scene: 'trust-model',     steps: [2000, 1800, 3500] },
  { scene: 'engineering',     steps: [1500, 3500] },
  { scene: 'ai-collaboration',steps: [2000, 2500] },
  { scene: 'reflection',      steps: [3000, 3000] },
  { scene: 'end',             steps: [3500] },
];

async function main() {
  if (!existsSync(OUTPUT_DIR)) mkdirSync(OUTPUT_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const videoDir = join(OUTPUT_DIR, 'tmp-slides');
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
  await page.goto(`file://${RECORDING_HTML}`);
  await page.evaluate(() => document.fonts?.ready);
  await page.waitForTimeout(500);

  console.log('Recording all slide scenes continuously...\n');

  for (const { scene, steps } of SEQUENCE) {
    console.log(`  ${scene}`);
    await page.evaluate(s => NeoMathRecording.goto(s, 0), scene);
    await page.evaluate(() => NeoMathRecording.waitForIdle());

    for (let i = 0; i < steps.length; i++) {
      if (i > 0) {
        await page.evaluate(s => NeoMathRecording.setStep(s), i);
        await page.evaluate(() => NeoMathRecording.waitForIdle());
      }
      await page.waitForTimeout(steps[i]);
    }

    // Brief black between scenes
    await page.waitForTimeout(300);
  }

  // Extra hold at end
  await page.waitForTimeout(1000);

  const video = page.video();
  await page.close();

  if (video) {
    const out = join(OUTPUT_DIR, 'slides-all.webm');
    try {
      await video.saveAs(out);
      console.log(`\nSaved: ${out}`);
    } catch (e) {
      console.warn(`Could not save: ${e.message}`);
    }
  }

  await context.close();
  await browser.close();
  console.log('Done.');
}

main().catch(err => {
  console.error('Fatal:', err);
  process.exit(1);
});
