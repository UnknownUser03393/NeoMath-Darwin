/**
 * record-narrated.mjs
 *
 * Records the slide presentation canvas with each scene held for
 * its correct narration duration. Produces individual segment videos
 * ready for ffmpeg assembly with narration audio.
 */
import { chromium } from 'playwright';
import { dirname, resolve, join } from 'path';
import { fileURLToPath } from 'url';
import { existsSync, mkdirSync } from 'fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const RECORDING_HTML = resolve(__dirname, 'recording.html');
const OUTPUT_DIR = resolve(__dirname, 'output');

// Each entry: scene name, final step, hold duration in seconds
// Slide scenes (01-03, 07-10) with durations matching TTS narration
const SLIDES = [
  { idx: 1,  name: 'hook',             step: 1, dur: 8.4 },
  { idx: 2,  name: 'problem',          step: 3, dur: 27.6 },
  { idx: 3,  name: 'workflow',         step: 3, dur: 15.0 },
  { idx: 7,  name: 'trust-model',      step: 2, dur: 28.0 },
  { idx: 8,  name: 'engineering',      step: 1, dur: 19.5 },
  { idx: 9,  name: 'ai-collaboration', step: 1, dur: 27.9 },
  { idx: 10, name: 'reflection',       step: 1, dur: 10.0 },
  { idx: 10, name: 'end',              step: 0, dur: 9.4 },
];

async function main() {
  if (!existsSync(OUTPUT_DIR)) mkdirSync(OUTPUT_DIR, { recursive: true });
  const videoDir = join(OUTPUT_DIR, 'tmp-narrated');
  if (!existsSync(videoDir)) mkdirSync(videoDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const errors = [];

  for (const slide of SLIDES) {
    const prefix = String(slide.idx).padStart(2, '0');
    const context = await browser.newContext({
      viewport: { width: 1920, height: 1080 },
      deviceScaleFactor: 1,
      colorScheme: 'dark',
      recordVideo: { dir: videoDir, size: { width: 1920, height: 1080 } },
    });
    const page = await context.newPage();
    page.on('pageerror', e => errors.push(e.message));

    console.log(`  ${prefix}-${slide.name}:  goto step=${slide.step}  hold=${slide.dur.toFixed(0)}s`);

    // Navigate directly to final state
    await page.goto(`file://${RECORDING_HTML}?scene=${slide.name}&step=${slide.step}`);
    await page.evaluate(() => document.fonts?.ready);
    await page.evaluate(() => NeoMathRecording.waitForIdle());

    // Small settle time then hold for narration duration
    await page.waitForTimeout(600);
    await page.waitForTimeout(Math.round(slide.dur * 1000));
    await page.waitForTimeout(400); // buffer

    const video = page.video();
    await page.close();

    if (video) {
      const out = join(OUTPUT_DIR, `${prefix}-narrated-${slide.name}.webm`);
      await video.saveAs(out);
      console.log(`    → ${out}`);
    }
    await context.close();
  }

  await browser.close();

  if (errors.length) {
    console.warn(`\nErrors (${errors.length}):`);
    errors.forEach(e => console.warn('  ', e));
  }
  console.log('\nDone.');
}

main().catch(err => { console.error('Fatal:', err); process.exit(1); });
