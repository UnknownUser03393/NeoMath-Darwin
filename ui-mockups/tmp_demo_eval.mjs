import { DEMO_XDLT } from "./lib/xdlt/demo.mjs";

const line = DEMO_XDLT.split("\n").find((l) => l.includes("output.image"));
console.log("evaluated output.image line:", JSON.stringify(line));
console.log("backslash count in that line:", (line.match(/\\/g) || []).length);
