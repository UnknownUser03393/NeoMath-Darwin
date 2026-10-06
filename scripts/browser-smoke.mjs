import { createRequire } from "node:module"
import assert from "node:assert/strict"
import { unlink } from "node:fs/promises"
import path from "node:path"
const require = createRequire(import.meta.url)
const { chromium } = require(
  process.env.PLAYWRIGHT_MODULE ||
    "C:/Users/UnknownUser/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright",
)
const base = process.env.DARWIN_URL || "http://localhost:8443"
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
const errors = []
page.on("pageerror", (error) => errors.push(error.message))
const created = new Set()
page.on("request", (request) => {
  if (request.url().endsWith("/api/saveNotebook")) {
    const payload = request.postDataJSON()
    if (/^[a-f0-9-]{36}\.nm$/.test(payload.name)) created.add(payload.name)
  }
})
try {
  await page.goto(base)
  await page.getByText("MathCore connected", { exact: true }).waitFor()
  console.log("Workspace connected")
  await page
    .getByRole("button", { name: "Lost roots Dividing by a variable" })
    .click()
  await page.getByRole("combobox", { name: "View", exact: true }).selectOption("canvas")
  await page.getByRole("button", { name: "Check", exact: true }).click()
  await page
    .getByRole("button", {
      name: "Relation Step 1 to 2: Lost solution",
      exact: true,
    })
    .waitFor()
  await page
    .getByRole("button", {
      name: "Relation Step 1 to 2: Lost solution",
      exact: true,
    })
    .click()
  await page.getByRole("tab", { name: "evidence" }).click()
  await page.getByText("x = 0", { exact: true }).waitFor()
  await page.getByRole("button", { name: "Evaluate", exact: true }).click()
  await page.getByRole("button", { name: "Evaluate", exact: true }).waitFor()
  await page.waitForFunction(
    () => document.querySelectorAll('[role="tabpanel"] p').length >= 6,
  )
  assert.match(await page.getByRole("tabpanel").innerText(), /False/)
  console.log("Trace and probe checked")
  await page.getByText("More", { exact: true }).click()
  await page.getByRole("button", { name: "Edit", exact: true }).click()
  await page
    .getByRole("textbox", { name: "Title", exact: true })
    .fill("Darwin browser smoke")
  await page
    .getByRole("textbox", { name: "Equation 1", exact: true })
    .fill("x-1=0")
  await page.getByRole("button", { name: "Done", exact: true }).click()
  await page
    .getByRole("button", {
      name: "Relation Step 1 to 2: Not checked",
      exact: true,
    })
    .waitFor()
  await page.getByRole("button", { name: "Check", exact: true }).click()
  await page
    .getByRole("button", {
      name: "Relation Step 1 to 2: Equivalent",
      exact: true,
    })
    .waitFor()
  console.log("Edit invalidation checked")
  await page.getByRole("button", { name: "Pen", exact: true }).click()
  const canvas = await page
    .getByRole("group", {
      name: "Ink layer: draw with pen or mouse; touch to pan",
    })
    .boundingBox()
  await page.mouse.move(canvas.x + 400, canvas.y + 400)
  await page.mouse.down()
  await page.mouse.move(canvas.x + 470, canvas.y + 430, { steps: 5 })
  await page.mouse.up()
  await page
    .getByRole("img", { name: "1 ink strokes, not recognized as equations" })
    .waitFor()
  await page.getByRole("button", { name: "Undo", exact: true }).click()
  await page
    .getByRole("img", { name: "0 ink strokes, not recognized as equations" })
    .waitFor()
  await page.getByRole("button", { name: "Redo", exact: true }).click()
  await page
    .getByRole("img", { name: "1 ink strokes, not recognized as equations" })
    .waitFor()
  await page.getByRole("button", { name: "Documents", exact: true }).click()
  await page.getByRole("button", { name: /Darwin browser smoke/ }).click()
  await page.getByRole("combobox", { name: "View", exact: true }).selectOption("canvas")
  await page
    .getByRole("img", { name: "1 ink strokes, not recognized as equations" })
    .waitFor()
  assert.equal(await page.getByRole("tablist").count(), 0)
  await page.getByRole("combobox", { name: "View", exact: true }).selectOption("steps")
  console.log("Ink persistence checked")
  assert.ok(await page.getByRole("main").locator('[data-math-source="x-1=0"] .katex').count() >= 2)
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    await page.screenshot({ path: `browser-${width}.png` })
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
      `overflow at ${width}`,
    )
  }
  await page.getByRole("status").filter({ hasText: /Checked/ }).waitFor()
  await page.route("**/api/replay", (route) => route.abort())
  await page.getByRole("button", { name: "Check", exact: true }).click()
  await page.getByRole("alert").waitFor()
  assert.equal(
    await page.getByRole("button", { name: "Check", exact: true }).isEnabled(),
    true,
  )
  await page.unroute("**/api/replay")
  await page.getByRole("button", { name: "Check", exact: true }).click()
  await page
    .getByRole("button", { name: "Step 2: x-1=0. Equivalent", exact: true })
    .waitFor()
  assert.deepEqual(errors, [])
  console.log(
    "Browser passed: real check + witness + probe, edit invalidation, ink undo/redo persistence, reopen, 390/768/1440px, failed request and retry",
  )
} catch (error) {
  console.log((await page.locator("body").innerText()).slice(0, 4000))
  await page.screenshot({ path: "browser-failure.png" })
  throw error
} finally {
  await browser.close()
  const response = await fetch(`${base}/api/getSettings`, {
    method: "POST",
    body: "{}",
    headers: { "Content-Type": "application/json" },
  })
  const settings = await response.json()
  for (const name of created)
    await unlink(path.join(settings.result.dataDir, "notebooks", name)).catch(
      () => {},
    )
}
