"""Bounded SymPy adapter for notebook expressions and single-variable real predicates.

Input is parsed with a small mathematical grammar, never Python eval/parse_expr.
The worker subprocess bounds expensive symbolic computations.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from functools import lru_cache
from time import perf_counter
from typing import Any


@lru_cache(maxsize=32)
def _compute(method: str, serialized: str) -> dict[str, Any]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        process = subprocess.run(
            [sys.executable, "-m", "neomath.cas_worker"],
            input=json.dumps({"method": method, "payload": json.loads(serialized)}),
            capture_output=True, text=True, encoding="utf-8", env=env, timeout=6,
        )
        if process.returncode:
            return {"ok": False, "error": {"code": "CAS_FAILED", "message": "SymPy 计算失败，请检查输入。"}}
        return json.loads(process.stdout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": {"code": "CAS_TIMEOUT", "message": "SymPy 计算超时，请简化表达式。"}}


def call_cas(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    started = perf_counter()
    result = _compute(method, json.dumps(payload, sort_keys=True, ensure_ascii=True))
    if not result.get("ok"):
        result = {**result, "verification": {"status": "unknown", "target": method,
            "method": "sympy_worker", "limitations": [result.get("error", {}).get("code", "CAS_FAILED")]}}
    # Cached symbolic answers do not represent MathCore prefix replay cache hits.
    return {**result, "metrics": {"durationMs": (perf_counter() - started) * 1000, "cacheHits": 0}}


def needs_cas(result: dict[str, Any]) -> bool:
    if not result.get("ok"):
        return True
    data = result.get("result", {})
    return any(step.get("error") and step["error"].get("code") != "EXPECTED_EXPRESSION" for step in data.get("steps", [])) or any(
        state.get("trustLevel") not in ("verified", "exact_core") for state in data.get("states", [])
    )
