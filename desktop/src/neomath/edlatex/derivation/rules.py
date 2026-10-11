from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Rule categories decide how a step is verified:
#   equivalence  -> from and to must be identically equal expressions
#   equation_op  -> same operation applied to both sides of an equation
#   calculus     -> differentiate / integrate (checked via the derivative)
#   solve        -> from is an equation, to lists its solution(s)
EQUIVALENCE = "equivalence"
EQUATION_OP = "equation_op"
CALCULUS = "calculus"
SOLVE = "solve"


@dataclass(frozen=True)
class RuleSpec:
    id: str
    label: str
    category: str
    # Whether the transformation can change the solution set (debugger cares).
    may_add_solutions: bool = False
    may_lose_solutions: bool = False
    # Whether correctness is conditional on an operand being non-zero.
    needs_nonzero: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


RULES: dict[str, RuleSpec] = {
    "simplify": RuleSpec("simplify", "化简", EQUIVALENCE),
    "expand": RuleSpec("expand", "展开", EQUIVALENCE),
    "factor": RuleSpec("factor", "因式分解", EQUIVALENCE),
    "substitute": RuleSpec("substitute", "代入", EQUIVALENCE),
    "add-both-sides": RuleSpec("add-both-sides", "两边加", EQUATION_OP),
    "subtract-both-sides": RuleSpec("subtract-both-sides", "两边减", EQUATION_OP),
    "multiply-both-sides": RuleSpec(
        "multiply-both-sides", "两边乘", EQUATION_OP, may_add_solutions=True, needs_nonzero=True
    ),
    "divide-both-sides": RuleSpec(
        "divide-both-sides", "两边除", EQUATION_OP, may_lose_solutions=True, needs_nonzero=True
    ),
    "square-both-sides": RuleSpec(
        "square-both-sides", "两边平方", EQUATION_OP, may_add_solutions=True
    ),
    "take-square-root": RuleSpec(
        "take-square-root", "两边开方", EQUATION_OP, may_lose_solutions=True
    ),
    "differentiate": RuleSpec("differentiate", "求导", CALCULUS),
    "integrate": RuleSpec("integrate", "积分", CALCULUS),
    "solve-equation": RuleSpec("solve-equation", "解方程", SOLVE),
}


def rule_spec(rule_id: str) -> RuleSpec | None:
    return RULES.get(rule_id)


def all_rule_ids() -> list[str]:
    return list(RULES.keys())
