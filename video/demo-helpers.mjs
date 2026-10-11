/**
 * demo-helpers.mjs
 *
 * Presentation automation layer for Playwright.
 * Makes recordings look like a human operating the product,
 * not like an E2E test blasting through at machine speed.
 */

/**
 * Move cursor to element with smooth animation, then click.
 * @param {import('playwright').Page} page
 * @param {import('playwright').Locator|string} target - Locator or selector string
 * @param {object} [opts]
 * @param {number} [opts.prePause=300]  - ms pause before moving to target
 * @param {number} [opts.postPause=500] - ms pause after clicking
 */
export async function demoClick(page, target, opts = {}) {
  const { prePause = 300, postPause = 500 } = opts;
  const locator = typeof target === 'string' ? page.locator(target) : target;

  await locator.waitFor({ state: 'visible', timeout: 10000 });
  await page.waitForTimeout(prePause);

  // Get element center
  const box = await locator.boundingBox();
  if (!box) throw new Error(`Element not visible for demoClick`);

  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;

  // Move mouse smoothly (Playwright moves linearly which is fine for recording)
  await page.mouse.move(cx, cy, { steps: 12 });
  await page.waitForTimeout(80);
  await page.mouse.click(cx, cy);
  await page.waitForTimeout(postPause);
}

/**
 * Type text into a field with visible per-character delay.
 * @param {import('playwright').Page} page
 * @param {import('playwright').Locator|string} target
 * @param {string} text
 * @param {object} [opts]
 * @param {number} [opts.charDelay=65] - ms between characters
 * @param {number} [opts.prePause=200]
 * @param {number} [opts.postPause=400]
 */
export async function demoType(page, target, text, opts = {}) {
  const { charDelay = 65, prePause = 200, postPause = 400 } = opts;
  const locator = typeof target === 'string' ? page.locator(target) : target;

  await locator.waitFor({ state: 'visible', timeout: 10000 });
  await page.waitForTimeout(prePause);

  await locator.click();
  await page.waitForTimeout(100);

  for (const ch of text) {
    await page.keyboard.type(ch, { delay: 0 });
    await page.waitForTimeout(charDelay);
  }

  await page.waitForTimeout(postPause);
}

/**
 * Focus/highlight an element without clicking.
 * Scrolls it into view and moves cursor there.
 */
export async function focusElement(page, target, opts = {}) {
  const { holdMs = 1200 } = opts;
  const locator = typeof target === 'string' ? page.locator(target) : target;

  await locator.waitFor({ state: 'visible', timeout: 10000 });
  await locator.scrollIntoViewIfNeeded();
  await page.waitForTimeout(150);

  const box = await locator.boundingBox();
  if (box) {
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 10 });
  }

  await page.waitForTimeout(holdMs);
}

/**
 * Pause for viewing. Use instead of bare waitForTimeout for clarity.
 */
export async function hold(page, ms = 1000) {
  await page.waitForTimeout(ms);
}

/**
 * Wait for an element matching text to appear (not just exist, but be visible).
 * More robust than waitForTimeout for state transitions.
 */
export async function waitForText(page, text, opts = {}) {
  const { timeout = 15000 } = opts;
  await page.getByText(text, { exact: false }).first().waitFor({
    state: 'visible',
    timeout,
  });
}

/**
 * Wait for a CSS class to appear on an element.
 */
export async function waitForClass(page, selector, className, opts = {}) {
  const { timeout = 15000 } = opts;
  await page.waitForFunction(
    ([sel, cls]) => {
      const el = document.querySelector(sel);
      return el && el.classList.contains(cls);
    },
    [selector, className],
    { timeout }
  );
}

/**
 * Wait for NeoMath UI to be ready (backend connected, kernel idle).
 */
export async function waitForAppReady(page, opts = {}) {
  const { timeout = 30000 } = opts;
  // Wait for status bar to show "就绪" or "Idle" or the kernel status to stabilize
  try {
    await page.waitForFunction(
      () => {
        // Check if any status item shows ready state
        const items = document.querySelectorAll('.status-item');
        for (const item of items) {
          if (item.textContent.includes('就绪') || item.textContent.includes('Idle') || item.textContent.includes('Ready')) {
            return true;
          }
        }
        // Also check if the app-shell is fully loaded
        return !!document.querySelector('.app-shell');
      },
      {},
      { timeout }
    );
  } catch {
    // If timeout, check if app-shell exists at least
    const hasShell = await page.locator('.app-shell').count();
    if (!hasShell) throw new Error('App shell not loaded');
  }
  await page.waitForTimeout(500);
}

/**
 * Press keyboard shortcut.
 */
export async function demoKey(page, key, opts = {}) {
  const { prePause = 200, postPause = 600 } = opts;
  await page.waitForTimeout(prePause);
  await page.keyboard.press(key);
  await page.waitForTimeout(postPause);
}
