const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { chromium } = require("playwright");

async function main() {
  const root = path.resolve(__dirname, "..", "..");
  const fixture = JSON.parse(
    fs.readFileSync(path.join(root, "build", "reports", "ui_fixture.json"), "utf8"),
  );
  const browser = await chromium.launch({
    headless: true,
    executablePath:
      process.env.NEOMATH_BROWSER
      || "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  await page.addInitScript((data) => {
    window.NEOMATH_STARTUP = data.startup;
    window.pywebview = {
      api: {
        runTrace: async () => data.trace,
        analyzeDocument: async () => data.trace,
        replay: async () => data.trace,
        getCompletions: async () => data.completions,
        getCapabilities: async () => data.capabilities,
        getRecentDocuments: async () => ({ ok: true, result: [] }),
        requestAiExplanation: async () => ({
          ok: true,
          text: "在这里试入 x = 0：它在上一步成立，在这一步不再成立，所以发生了丢根。",
          source: "local",
        }),
        stop: async () => ({ ok: true }),
      },
    };
  }, fixture);
  await page.goto(pathToFileURL(path.join(root, "src", "neomath", "ui", "index.html")).href);
  await page.waitForSelector(".step-card.root_fault", { timeout: 10_000 });
  await page.waitForTimeout(350);
  const output = path.join(root, "docs", "assets", "neomath-ui.png");
  fs.mkdirSync(path.dirname(output), { recursive: true });
  await page.screenshot({ path: output, fullPage: false });
  await browser.close();
  console.log(output);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
