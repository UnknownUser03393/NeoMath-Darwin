import { createRequire } from "node:module"
import assert from "node:assert/strict"
import { unlink } from "node:fs/promises"
import path from "node:path"
const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "C:/Users/UnknownUser/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright")
const base = process.env.DARWIN_URL || "http://localhost:8443"
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 960 }, reducedMotion: "reduce" })
const created = new Set()
const fontErrors = []
page.on("response", r => { if (/\.(woff2?|ttf)/.test(r.url()) && !r.ok()) fontErrors.push(r.url()) })
page.on("request", request => {
  if (request.url().endsWith("/api/saveNotebook")) {
    const name = request.postDataJSON()?.name
    if (/^[a-f0-9-]{36}\.nm$/.test(name)) created.add(name)
  }
})
try {
  await page.goto(base)
  await page.getByText("MathCore connected", { exact: true }).waitFor()
  await page.getByRole("button", { name: "Domain change Keep the original domain" }).click()
  await page.getByRole("combobox", { name: "View", exact: true }).selectOption("canvas")
  await page.getByRole("main").locator(".view-content .katex mfrac").first().waitFor()
  await page.getByRole("button", { name: /Step 1: / }).click()
  await page.getByRole("tabpanel").locator(".katex").first().waitFor()
  await page.getByRole("status").filter({ hasText: /Checked/ }).waitFor()
  await page.screenshot({ path: "browser-katex-fraction.png" })
  await page.getByText("More", { exact: true }).click()
  await page.getByRole("button", { name: "Edit", exact: true }).click()
  const equation = page.getByRole("textbox", { name: "Equation 1", exact: true })
  await equation.fill("sqrt(x)=x-2")
  await page.locator('[aria-label="Equation preview 1"] .katex msqrt').waitFor()
  await equation.fill("x=")
  await page.locator('[aria-label="Equation preview 1"] [data-math-fallback]').waitFor()
  await equation.fill("sqrt(x)=x-2")
  await page.locator('[aria-label="Equation preview 1"] .katex msqrt').waitFor()
  await page.getByRole("button", { name: "Done", exact: true }).click()
  await page.getByRole("combobox", { name: "View", exact: true }).selectOption("steps")
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 960 })
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
  }
  await page.getByRole("main").locator(".view-content .katex msqrt").first().waitFor()
  await page.getByRole("status").filter({ hasText: /Checked/ }).waitFor()
  await page.screenshot({ path: "browser-katex-root.png" })
  await page.evaluate(() => document.fonts.ready)
  assert.ok(await page.evaluate(() => document.fonts.check("16px KaTeX_Main")))
  assert.deepEqual(fontErrors, [])
  console.log("KaTeX passed: real fractions, roots, MathML, editor previews, invalid input recovery, local fonts and responsive layout")
} finally {
  await browser.close()
  const response = await fetch(`${base}/api/getSettings`, { method: "POST", body: "{}", headers: { "Content-Type": "application/json" } })
  const settings = await response.json()
  for (const name of created) await unlink(path.join(settings.result.dataDir, "notebooks", name)).catch(() => {})
}
