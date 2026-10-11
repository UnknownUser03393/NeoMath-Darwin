import { readFileSync } from "node:fs";
import { fakeDom, element } from "./tests/fakeDom.mjs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const ts = require("typescript");
const src = readFileSync("lib/xdlt/patchRuntime.ts", "utf8");
const { outputText } = ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
const runtime = await import("data:text/javascript;charset=utf-8," + encodeURIComponent(outputText));
const dom = fakeDom();

const URL = "http://127.0.0.1:8811";
async function post(method, payload) {
  const r = await fetch(`${URL}/api/${method}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  return r.json();
}
const demoFile = readFileSync("lib/xdlt/demo.ts", "utf8");
const start = demoFile.indexOf("`") + 1;
const end = demoFile.lastIndexOf("`");
const demo = demoFile.slice(start, end).replaceAll("\\\\", "\\");

const created = await post("createXdltSession", { content: demo, execute: true, verify: true });
const root = element(created.result.html);

const edited = demo.replace("= 300", "= 350").replace("温度场", "温度场改");
const updated = await post("updateXdltSession", { sessionId: created.sessionId, content: edited, execute: true, verify: true });
const patches = updated.result.htmlPatches;
const fullHtml = updated.result.html;

console.log("patch ops:", patches.map(p => p.op + ":" + (p.renderId || p.parentRenderId || "")));
const result = runtime.applyXdltPatches(root, patches, {}, dom);
console.log("apply ok:", result.ok, "fallback:", result.fallback);
const patchedDom = root.innerHTML;
const fullRoot = element(fullHtml);
const eq = patchedDom === fullRoot.innerHTML;
console.log("patched DOM == full render:", eq);
if (!eq) {
  for (let i = 0; i < Math.max(patchedDom.length, fullRoot.innerHTML.length); i++) {
    if (patchedDom[i] !== fullRoot.innerHTML[i]) {
      console.log("first diff at", i);
      console.log("patched:", patchedDom.slice(Math.max(0,i-60), i+60));
      console.log("full:   ", fullRoot.innerHTML.slice(Math.max(0,i-60), i+60));
      break;
    }
  }
}
await post("destroyXdltSession", { sessionId: created.sessionId });
process.exit(eq ? 0 : 1);
