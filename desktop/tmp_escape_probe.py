"""Probe the exec-source escaping chain: what does the IR source actually contain?"""
import json
import subprocess
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

# Get the exact evaluated DEMO_XDLT (same as browser sends).
node = subprocess.run(
    ["node", "tmp_demo_eval.mjs", "--emit-source"],
    cwd="../ui-mockups",
    capture_output=True,
    text=True,
    encoding="utf-8",
)
# Instead, evaluate via a tiny inline node that prints the raw source.
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
if node.returncode != 0:
    print("node error:", node.stderr)
    sys.exit(1)
xdl = json.loads(node.stdout)
print("sent content chars:", len(xdl))
print("sent single backslashes:", xdl.count("\\"))

req = urllib.request.Request(
    "http://127.0.0.1:8765/api/buildXdltDocument",
    data=json.dumps({"content": xdl}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))


def walk(node):
    if isinstance(node, dict):
        src = node.get("source")
        if isinstance(src, str) and "plot.png" in src:
            print("IR exec source repr:", repr(src))
            for line in src.splitlines():
                if "output.image" in line:
                    print("output.image line repr:", repr(line))
        for v in node.values():
            walk(v)
    elif isinstance(node, list):
        for v in node:
            walk(v)


walk(data)
print("walk done")
