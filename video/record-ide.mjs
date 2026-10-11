/**
 * record-ide.mjs
 *
 * Records an AI coding collaboration sequence.
 *
 * Strategy:
 *   1. If a browser-based IDE (e.g., Qoder Web) is available, automate it directly
 *   2. If VS Code / Cursor is running with --remote-debugging-port, connect via CDP
 *   3. Fallback: record a terminal-based AI interaction (e.g., Claude Code CLI)
 *
 * Usage:
 *   node record-ide.mjs                                    # auto-detect
 *   node record-ide.mjs --cdp http://127.0.0.1:9222        # VS Code CDP
 *   node record-ide.mjs --terminal                          # terminal fallback
 */
import { chromium } from 'playwright';
import { dirname, resolve, join } from 'path';
import { fileURLToPath } from 'url';
import { existsSync, mkdirSync } from 'fs';
import { demoClick, demoType, hold, demoKey } from './demo-helpers.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUTPUT_DIR = resolve(__dirname, 'output');

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = { cdp: null, terminal: false };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--cdp' && args[i + 1]) opts.cdp = args[++i];
    if (args[i] === '--terminal') opts.terminal = true;
  }
  return opts;
}

/** Try connecting via CDP (VS Code / Cursor / Electron IDE). */
async function tryCdp(url) {
  try {
    const browser = await chromium.connectOverCDP(url, { timeout: 5000 });
    const contexts = browser.contexts();
    if (contexts.length > 0) {
      console.log(`Connected via CDP: ${url}`);
      return { browser, context: contexts[0] };
    }
    await browser.close();
  } catch {
    // Not available
  }
  return null;
}

/** Record IDE interaction via CDP. */
async function recordViaCdp(context) {
  const pages = context.pages();
  if (pages.length === 0) {
    console.error('No pages found in CDP context');
    return;
  }

  const page = pages[0]; // Main VS Code window

  // Take initial screenshot
  const pngPath = join(OUTPUT_DIR, 'ide-initial.png');
  await page.screenshot({ path: pngPath });
  console.log(`  Initial screenshot: ${pngPath}`);

  // Open command palette
  await demoKey(page, 'Meta+Shift+p', { postPause: 800 });
  await hold(page, 500);

  // Type to open a file
  await page.keyboard.type('Open File', { delay: 60 });
  await hold(page, 800);
  await page.keyboard.press('Escape');
  await hold(page, 400);

  // Open terminal
  await demoKey(page, 'Meta+`', { postPause: 800 });
  await hold(page, 1000);

  // Final screenshot
  const pngPath2 = join(OUTPUT_DIR, 'ide-terminal.png');
  await page.screenshot({ path: pngPath2 });
  console.log(`  Terminal screenshot: ${pngPath2}`);
}

/** Fallback: record a simulated terminal AI interaction in the browser. */
async function recordTerminalFallback() {
  console.log('\n  Using terminal-style recording fallback...\n');
  console.log('  NOTE: For the actual video, manually record your IDE session');
  console.log('  or start your IDE with remote debugging enabled:');
  console.log('    code --remote-debugging-port=9222');
  console.log('    cursor --remote-debugging-port=9222');
  console.log('');
  console.log('  Then re-run: node record-ide.mjs --cdp http://127.0.0.1:9222');
  console.log('');

  // Create a simple screenshot with instructions
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    colorScheme: 'dark',
  });
  const page = await context.newPage();

  // Create a minimal terminal-like page
  await page.setContent(`
    <html>
    <body style="margin:0;background:#0e0e0e;color:#e0e0e0;font-family:Menlo,Consolas,monospace;font-size:18px;padding:60px;">
      <div style="color:#666;margin-bottom:24px;">~/NeoMath $</div>
      <div style="color:#4c8dff;">IDE recording placeholder</div>
      <div style="color:#999;margin-top:16px;">
        To record the actual IDE session:<br>
        1. Start your IDE with --remote-debugging-port=9222<br>
        2. Run: node record-ide.mjs --cdp http://127.0.0.1:9222
      </div>
    </body>
    </html>
  `);

  const pngPath = join(OUTPUT_DIR, 'ide-placeholder.png');
  await page.screenshot({ path: pngPath });
  console.log(`  Placeholder: ${pngPath}`);

  await browser.close();
}

async function main() {
  const opts = parseArgs();
  if (!existsSync(OUTPUT_DIR)) mkdirSync(OUTPUT_DIR, { recursive: true });

  console.log('Recording IDE collaboration sequence...');

  // Try CDP first
  const cdpUrl = opts.cdp || 'http://127.0.0.1:9222';
  if (!opts.terminal) {
    const cdp = await tryCdp(cdpUrl);
    if (cdp) {
      await recordViaCdp(cdp.context);
      await cdp.browser.close();
      console.log('\nIDE recording done (CDP).');
      return;
    }
    console.log('  CDP not available at', cdpUrl);
  }

  // Fallback
  await recordTerminalFallback();
  console.log('\nIDE recording done (fallback).');
}

main().catch(err => {
  console.error('Fatal:', err);
  process.exit(1);
});
