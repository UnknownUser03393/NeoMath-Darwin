"""Run the real execution path and dump the image output."""
import base64
import json
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

inline = (
    "import('./lib/xdlt/demo.mjs').then(m => "
    "process.stdout.write(JSON.stringify(m.DEMO_XDLT)))"
)
node = subprocess.run(
    ["node", "-e", inline],
    cwd="../ui-mockups",
    capture_output=True,
    text=True,
    encoding="utf-8",
)
xdl = json.loads(node.stdout)

from neomath.xdlt.project import XdltProject
from neomath.xdlt.execution import ExecutionEngine

project = XdltProject.load(xdl, cards_dir=None, values=None)
import tempfile
with tempfile.TemporaryDirectory() as tmp:
    engine = ExecutionEngine(cache_dir=tmp)
    result = engine.execute_document(
        project.semantic_ir, project.graph, project.value_environment
    )
print("exec result keys:", list(result.keys()))
for out in result.get("results", []):
    print("RESULT status:", out.status, "outputs:", len(out.outputs))
    for o in out.outputs:
        print("  OUTPUT kind:", o.kind)
        if o.kind == "image":
            b64 = o.data_base64 if hasattr(o, "data_base64") else getattr(o, "base64", None)
            print("  b64:", b64)
            raw = base64.b64decode(b64)
            print("  decoded len:", len(raw), "head:", raw[:12])
