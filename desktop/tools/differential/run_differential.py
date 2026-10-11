from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

import neomath_core

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.oracle.sympy_oracle import solve_predicate_ast  # noqa: E402


def generated_source(randomizer: random.Random, index: int) -> str:
    family = index % 5
    nonzero = [value for value in range(-10, 11) if value]
    if family == 0:
        a = randomizer.choice(nonzero)
        b = randomizer.randint(-10, 10)
        return f"{a}x + {b} = 0"
    if family == 1:
        r1 = randomizer.randint(-10, 10)
        r2 = randomizer.randint(-10, 10)
        return f"(x - ({r1}))(x - ({r2})) = 0"
    if family == 2:
        a = randomizer.randint(-10, 10)
        b = randomizer.randint(-10, 10)
        return f"(x - ({a}))(x - ({b})) = 0"
    if family == 3:
        p = randomizer.choice(nonzero)
        q = randomizer.randint(-10, 10)
        r = randomizer.choice(nonzero)
        s = randomizer.randint(-10, 10)
        return f"({p}x + {q}) / ({r}x + {s}) = 0"
    root = randomizer.randint(0, 10)
    shift = randomizer.randint(-4, 4)
    # Construct a radical equation with the known nonnegative solution root.
    return f"sqrt(x + {root * root - root}) = x + {shift - shift}"


def core_signature(state: dict[str, Any]) -> set[str] | str:
    solution = state["solutionSet"]
    if solution["kind"] == "finite":
        return set(solution["values"])
    if solution["kind"] == "empty":
        return set()
    if solution["kind"] == "all_real":
        return "all_real"
    if solution["kind"] == "all_real_excluding_finite":
        return "all_real_excluding:" + ",".join(solution["excluded"])
    return "unverified"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260724)
    args = parser.parse_args()
    randomizer = random.Random(args.seed)
    differences: list[dict[str, Any]] = []
    checked = 0
    skipped = 0
    for index in range(args.cases):
        source = generated_source(randomizer, index)
        parsed = neomath_core.parse_document(source)
        trace = neomath_core.run_trace(parsed["result"])
        if not trace["ok"] or not trace["result"]["states"]:
            differences.append({"source": source, "reason": "core_error", "core": trace})
            continue
        state = trace["result"]["states"][0]
        oracle = solve_predicate_ast(parsed["result"]["steps"][0]["ast"])
        core = core_signature(state)
        if oracle in {"irrational", "unverified"} or core == "unverified":
            skipped += 1
            continue
        checked += 1
        if core != oracle:
            differences.append(
                {
                    "source": source,
                    "core": sorted(core) if isinstance(core, set) else core,
                    "oracle": sorted(oracle) if isinstance(oracle, set) else oracle,
                }
            )
            if len(differences) >= 25:
                break
    report = {
        "seed": args.seed,
        "requestedCases": args.cases,
        "checkedCases": checked,
        "skippedCases": skipped,
        "differenceCount": len(differences),
        "differences": differences,
    }
    report_dir = ROOT / "build" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "differential.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return 1 if differences else 0


if __name__ == "__main__":
    raise SystemExit(main())
