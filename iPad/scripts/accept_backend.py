#!/usr/bin/env python3
"""Record acceptance against the real running backend, never a stub server."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base", default="http://127.0.0.1:8765/api")
parser.add_argument("--output", type=Path, default=Path("/tmp/neomath-backend-acceptance.json"))
args = parser.parse_args()
evidence = {}

def request(label, method, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(args.base + "/" + method, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as response:
        result = json.load(response)
    evidence[label] = result
    return result

def math(label, method, source, **extra):
    return request(label, method, {"engine": "auto", "document": {"source": source}, **extra})

health = request("health", "health")
assert health["ok"] and health["result"]["core"] == "C++20"
roots = math("complete_roots", "runTrace", "x^2=2\nx=±sqrt(2)")
assert roots["ok"] and roots["result"]["engine"] == "sympy"
assert roots["result"]["states"][1]["solutionSet"]["values"] == ["-sqrt(2)", "sqrt(2)"]
assert roots["result"]["relations"][0]["relation"] == "equivalent"
for method in ("parseDocument", "analyzeDocument", "replay", "getCompletions"):
    assert math(method, method, "x^2=2", step=0, changedStep=0)["ok"]
probe = math("exact_probe", "evaluateProbe", "x^2=2", probe={"value": "sqrt(2)"})
assert probe["ok"] and probe["result"]["steps"][0]["predicateResult"] is True
transformed = math("multiply_3", "executeTransformation", "x^2=2", step=0, intent={"intent": "multiply", "arguments": {"expression": "3"}})
assert transformed["ok"] and transformed["result"]["source"] == "3*x^2=6"
division = math("divide_zero", "executeTransformation", "x^2=2", step=0, intent={"intent": "divide", "arguments": {"expression": "0"}})
assert not division["ok"] and division["error"]["code"] == "CAS_INPUT"
for label, source in [("unknown", "sin(x)=x"), ("syntax_error", "x=)")]:
    reply = math(label, "runTrace", source)
    assert reply["ok"] and reply["result"]["diagnostics"][0]["status"] == "unverified"
    assert reply["result"]["states"][0]["verification"]["status"] == "unknown"
timeout = math("real_timeout", "runTrace", "x^50+x+1=0")
assert not timeout["ok"] and timeout["error"]["code"] == "CAS_TIMEOUT"
assert timeout["verification"]["status"] == "unknown"

initial = request("writing_create", "createXdltSession", {"content": "# Initial document\n", "mode": "fragment", "verify": True})
assert initial["ok"]
session = initial["sessionId"]
content = "# Updated document\n\n#context {\nx: Real\n}\n#assert:unknown {\nclaim x > 0\n}\n"
try:
    update = request("writing_add_context", "updateXdltSession", {"sessionId": session, "content": content, "verify": True})
    assert update["ok"] and "status: unknown" in update["result"]["html"]
    assert "sym:ctx.anon1/x" in update["result"]["invalidatedSemanticIds"]
finally:
    request("writing_destroy", "destroyXdltSession", {"sessionId": session})

expected = "# CAS 自动编译验收\n\n$$ #eq:roots\nx^2=3\n$$\n\n#context {\nx: Real\n}\n#assert:unknown {\nclaim x > 0\n}\n#assert:error {\nclaim x = 0\n}\n\n# Save marker 4"
saved = request("simulator_writing_readback", "loadXdltDocument", {"name": "CAS Writing Acceptance"})
assert saved["ok"] and saved["result"]["source"] == expected
evidence["writingSourceSHA256"] = hashlib.sha256(expected.encode()).hexdigest()
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
print("Real backend acceptance passed: health, CAS roots, all auto math APIs, probe, parameter transform, Unknown, syntax error, timeout, Writing incremental context and exact simulator save readback.")
print("Evidence:", args.output.resolve())
