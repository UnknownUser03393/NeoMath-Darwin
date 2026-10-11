import assert from "node:assert/strict";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders NeoMath with an empty editor by default", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /NeoMath/);
  // Default boot opens no tabs: an empty editor, not a demo document.
  assert.match(html, /未打开任何标签页/);
  assert.doesNotMatch(html, /方程变形中的丢根/);
  assert.doesNotMatch(html, /x\(x - 1\) = 0|x\(x − 1\) = 0/);
  assert.match(html, /MathCore|离线演示|内核/);
  assert.doesNotMatch(html, /Mock Runtime/);
  assert.doesNotMatch(html, /后续版本|尚未实现/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape/);
});
