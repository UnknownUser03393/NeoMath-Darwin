import { createRequire } from "node:module"
import assert from "node:assert/strict"
import { unlink } from "node:fs/promises"
import path from "node:path"
const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "C:/Users/UnknownUser/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright")
const base = process.env.DARWIN_URL || "http://localhost:8443"
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
await page.addInitScript(() => localStorage.setItem("neomath-auto-check", "true"))
const created = new Set()
const writings = new Set()
const checks = []
const errors = []
page.on("pageerror", e => errors.push(e.message))
page.on("request", request => {
  const payload = request.postDataJSON()
  if (request.url().endsWith("/api/saveNotebook") && /^[a-f0-9-]{36}\.nm$/.test(payload?.name)) created.add(payload.name)
  if (request.url().endsWith("/api/saveXdltDocument") && /^[a-f0-9-]{36}\.xdlt$/.test(payload?.name)) writings.add(payload.name)
  if (/\/api\/(runTrace|replay)$/.test(request.url())) checks.push(payload)
})
const checked = () => page.getByRole("status").filter({ hasText: /Checked.*ms/ }).waitFor()
try {
  await page.goto(base)
  await page.getByText("MathCore connected", { exact: true }).waitFor()
  await page.getByRole("button", { name: "Lost roots Dividing by a variable" }).click()
  await page.getByRole("combobox", { name: "View", exact: true }).selectOption("canvas")
  await checked()
  assert.equal(checks.length, 1, "opening checks automatically")
  await page.getByText("More", { exact: true }).click()
  await page.getByRole("button", { name: "Edit", exact: true }).click()
  await page.getByRole("textbox", { name: "Equation 3", exact: true }).fill("x=2")
  await checked()
  assert.equal(checks.at(-1).changedStep, 2)
  await page.getByRole("status").filter({ hasText: /Replay.*reused 2 steps/ }).waitFor()
  const beforeMetadata = checks.length
  await page.getByRole("textbox", { name: "Title", exact: true }).fill("Incremental smoke")
  await page.waitForTimeout(400)
  assert.equal(checks.length, beforeMetadata, "title edit does not check")
  const equation = page.getByRole("textbox", { name: "Equation 3", exact: true })
  await equation.dispatchEvent("compositionstart")
  await equation.fill("x=3")
  await page.waitForTimeout(350)
  assert.equal(checks.length, beforeMetadata, "IME composition suppresses checks")
  await equation.dispatchEvent("compositionend")
  await checked()
  const beforeRapid = checks.length
  await equation.fill("x=4"); await equation.fill("x=5"); await equation.fill("x=1")
  await checked()
  assert.equal(checks.length, beforeRapid + 1, "rapid edits are coalesced")
  assert.match(checks.at(-1).document.source, /x=1$/)
  let notifyBlocked, releaseBlocked
  const blocked = new Promise(resolve => { notifyBlocked = resolve })
  const release = new Promise(resolve => { releaseBlocked = resolve })
  let holdOne = true
  await page.route("**/api/replay", async route => {
    if (!holdOne) { await route.continue(); return }
    holdOne = false
    const response = await route.fetch()
    notifyBlocked()
    await release
    await route.fulfill({ response }).catch(() => {})
  })
  await equation.fill("x=9")
  await blocked
  await equation.fill("x=1")
  await checked()
  releaseBlocked()
  await page.waitForTimeout(100)
  assert.match(checks.at(-1).document.source, /x=1$/)
  await page.getByRole("button", { name: /Step 3: x=1\./ }).waitFor()
  await page.unroute("**/api/replay")
  await page.getByRole("textbox", { name: "Equation 2", exact: true }).fill("x=")
  await page.getByRole("status").filter({ hasText: /Syntax error/ }).waitFor()
  await page.getByRole("alert").filter({ hasText: /expected a number/ }).waitFor()
  await page.getByRole("textbox", { name: "Equation 2", exact: true }).fill("x-1=0")
  await checked()
  assert.equal(await page.getByRole("alert").count(), 0)
  await page.getByRole("button", { name: "Auto check", exact: true }).click()
  const beforeManual = checks.length
  await equation.fill("x=7")
  await page.waitForTimeout(350)
  assert.equal(checks.length, beforeManual)
  await page.getByRole("button", { name: "Auto check", exact: true }).click()
  await checked()
  console.log("Automatic check, prefix replay, metadata isolation, IME, debounce, stale replies, parse errors and recovery passed")
  await page.getByRole("textbox", { name: "Equation 1", exact: true }).fill("x^2-4=0")
  await checked()
  await page.getByRole("textbox", { name: "Equation 1", exact: true }).focus()
  await page.getByRole("button", { name: "Complete · Ctrl+Space", exact: true }).click()
  await page.getByRole("button", { name: /因式分解/ }).click()
  await page.getByRole("textbox", { name: "Equation 4", exact: true }).waitFor()
  await checked()
  assert.equal(await page.getByRole("textbox", { name: "Equation 4", exact: true }).count(), 1)
  await page.getByRole("button", { name: "Explain", exact: true }).click()
  await page.getByRole("status").filter({ hasText: /\(local\)|\(qwen\)/ }).waitFor()
  await page.getByRole("button", { name: "Done", exact: true }).click()
  await page.getByRole("button", { name: "Documents", exact: true }).click()
  await page.getByRole("button", { name: "New writing document", exact: true }).click()
  await page.getByRole("status").filter({ hasText: "Compiled" }).waitFor()
  const source = page.getByRole("textbox", { name: "XDLT source", exact: true })
  const text = "# Test writing\n\nParagraph one.\n\n$\\frac{x^2-1}{x-1}$\n\n#assert:valid(using=sympy) {\nclaim x + 0 == x\n}\n"
  await source.fill(text)
  await page.getByRole("status").filter({ hasText: /Updated/ }).waitFor()
  await page.frameLocator('iframe[title="XDLT preview"]').getByText("Paragraph one.", { exact: true }).waitFor()
  await page.frameLocator('iframe[title="XDLT preview"]').locator(".katex").first().waitFor()
  assert.ok(await page.frameLocator('iframe[title="XDLT preview"]').locator(".katex mfrac").count() >= 1)
  await source.fill(text.replace("one", "two"))
  await page.getByRole("status").filter({ hasText: /preview patched.*1 checks reused/ }).waitFor()
  await page.frameLocator('iframe[title="XDLT preview"]').getByText("Paragraph two.", { exact: true }).waitFor()
  assert.ok(await page.frameLocator('iframe[title="XDLT preview"]').locator(".katex").count() >= 1)
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
  }
  const destroyed = page.waitForResponse(response => response.url().endsWith("/api/destroyXdltSession"))
  await page.getByRole("button", { name: "‹ Documents", exact: true }).click()
  assert.equal((await (await destroyed).json()).result.destroyed, true)
  assert.deepEqual(errors, [])
  console.log("Semantic completion + transformation + explanation; XDLT session compilation, verification cache, DOM patches, save and close passed")
} catch (error) {
  console.log((await page.locator("body").innerText()).slice(0, 5000))
  await page.screenshot({ path: "browser-incremental-failure.png" })
  throw error
} finally {
  await browser.close()
  const response = await fetch(`${base}/api/getSettings`, { method: "POST", body: "{}", headers: { "Content-Type": "application/json" } })
  const settings = await response.json()
  for (const name of created) await unlink(path.join(settings.result.dataDir, "notebooks", name)).catch(() => {})
  for (const name of writings) await unlink(path.join(settings.result.dataDir, "xdlt", name)).catch(() => {})
}
