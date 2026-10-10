"""Isolated, allowlisted mathematical input -> SymPy -> notebook protocol."""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from typing import Any

import sympy as sp
from sympy.calculus.util import continuous_domain

FUNCTIONS = {"sqrt": sp.sqrt, "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
             "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
             "exp": sp.exp, "log": sp.log, "ln": sp.log, "abs": sp.Abs,
             "Abs": sp.Abs, "diff": sp.diff, "integrate": sp.integrate}
CONSTANTS = {"pi": sp.pi, "E": sp.E, "e": sp.E}


def normalize(source: str) -> str:
    source = source.strip().strip("$")
    source = source.replace("\\left", "").replace("\\right", "")
    source = re.sub(r"\\(?:,|;|!)", "", source)
    # Recursively consume nested LaTeX groups without changing their mathematical scope.
    def group(pos: int) -> tuple[str, int]:
        while pos < len(source) and source[pos].isspace(): pos += 1
        if pos >= len(source) or source[pos] != "{": raise ValueError("LaTeX 命令缺少 {…} 参数")
        end, depth = pos + 1, 1
        while end < len(source) and depth:
            depth += (source[end] == "{") - (source[end] == "}")
            end += 1
        if depth: raise ValueError("LaTeX 参数缺少右括号")
        return normalize(source[pos + 1:end - 1]), end
    while match := re.search(r"\\(frac|sqrt)\b", source):
        arg, end = group(match.end())
        if match[1] == "frac":
            other, end = group(end)
            value = f"(({arg})/({other}))"
        else: value = f"sqrt({arg})"
        source = source[:match.start()] + " " + value + " " + source[end:]
    for name, value in {"pm": "±", "mp": "∓", "cdot": "*", "times": "*", "div": "/", "leq": "<=", "geq": ">=", "le": "<=", "ge": ">=", "neq": "!=", "pi": "pi", "sin": "sin", "cos": "cos", "tan": "tan", "log": "log", "ln": "ln", "exp": "exp"}.items():
        source = re.sub(r"\\" + name + r"(?![A-Za-z])", lambda _: value, source)
    return source.translate(str.maketrans({"−": "-", "–": "-", "×": "*", "·": "*", "⋅": "*", "÷": "/", "√": "sqrt", "≤": "<=", "≥": ">=", "≠": "!=", "{": "(", "}": ")"}))


class Parser:
    def __init__(self, source: str):
        self.tokens = re.findall(r"[A-Za-z][A-Za-z_0-9]*|(?:\d+(?:\.\d*)?|\.\d+)|\*\*|[+*/^(),-]", source)
        if "".join(self.tokens) != re.sub(r"\s+", "", source): raise ValueError("不支持此输入；请使用数学表达式和常见函数")
        if len(self.tokens) > 300: raise ValueError("表达式过长")
        self.pos = 0

    def peek(self) -> str: return self.tokens[self.pos] if self.pos < len(self.tokens) else ""
    def take(self) -> str:
        value = self.peek()
        if not value: raise ValueError("表达式未完成")
        self.pos += 1
        return value
    def expression(self):
        value = self.product()
        while self.peek() in ("+", "-"):
            op, rhs = self.take(), self.product()
            value = sp.Add(value, rhs if op == "+" else sp.Mul(-1, rhs, evaluate=False), evaluate=False)
        return value
    def product(self):
        value = self.unary()
        while self.peek() in ("*", "/") or self.peek() == "(" or re.match(r"[A-Za-z0-9.]", self.peek()):
            op = self.take() if self.peek() in ("*", "/") else "*"
            rhs = self.unary()
            value = sp.Mul(value, rhs if op == "*" else sp.Pow(rhs, -1, evaluate=False), evaluate=False)
        return value
    def unary(self):
        if self.peek() in ("+", "-"):
            sign = self.take()
            value = self.unary()
            return value if sign == "+" else sp.Mul(-1, value, evaluate=False)
        value = self.atom()
        if self.peek() in ("^", "**"):
            self.take()
            power = self.unary()
            if power.is_number and (abs(power) > 100): raise ValueError("指数超出演示计算限制")
            value = sp.Pow(value, power, evaluate=False)
        return value
    def atom(self):
        token = self.take()
        if token == "(":
            value = self.expression()
            if self.take() != ")": raise ValueError("缺少右括号")
            return value
        if re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)", token):
            if len(token) > 80: raise ValueError("数字过长")
            return sp.Rational(token)
        if token in FUNCTIONS:
            if self.peek() != "(":
                if token == "sqrt": return sp.sqrt(self.unary(), evaluate=False)
                raise ValueError(f"{token} 后请输入 (…) 参数")
            self.take()
            args = [self.expression()]
            while self.peek() == ",": self.take(); args.append(self.expression())
            if self.take() != ")": raise ValueError("缺少函数右括号")
            if len(args) > 2: raise ValueError("函数参数过多")
            if token not in ("diff", "integrate"):
                if len(args) != 1: raise ValueError("此函数需要一个参数")
                return FUNCTIONS[token](args[0], evaluate=False)
            if len(args) != 2 or not isinstance(args[1], sp.Symbol): raise ValueError("求导/积分需要指定变量，如 diff(x^2,x)")
            return FUNCTIONS[token](*args)
        if token in CONSTANTS: return CONSTANTS[token]
        if re.fullmatch(r"[A-Za-z][A-Za-z_0-9]*", token):
            if self.peek() == "(" and len(token) > 1: raise ValueError(f"暂不支持函数 {token}")
            return sp.Symbol(token, real=True)
        raise ValueError("缺少数字、变量或函数")
    def parse(self):
        value = self.expression()
        if self.peek(): raise ValueError("表达式包含多余内容")
        return value


def expression(source: str): return Parser(source).parse()


def text(value) -> str:
    return sp.sstr(value).replace("**", "^").replace("Abs(", "abs(")


@dataclass
class Line:
    source: str
    alternatives: list[tuple[Any, str, Any]]
    variable: Any
    domain: Any
    solutions: Any
    error: str = ""


def parse_line(source: str, variable=None) -> Line:
    try:
        normalized = normalize(source)
        if re.search(r"\b(?:diff|integrate)\s*\(", normalized):
            raise ValueError("Inline calculus domain obligations are not fully verified; use the operation tool")
        alternatives = []
        for branch in re.split(r"\s+or\s+", normalized):
            choices = [branch] if not re.search("[±∓]", branch) else [branch.replace("±", "+").replace("∓", "-"), branch.replace("±", "-").replace("∓", "+")]
            for choice in choices:
                parts = re.split(r"(<=|>=|!=|==|=|<|>)", choice)
                if len(parts) == 1: alternatives.append((expression(choice), "expression", None))
                elif len(parts) == 3: alternatives.append((expression(parts[0]), parts[1], expression(parts[2])))
                else: raise ValueError("每行最多一个关系符，请用 or 表示多个分支")
        symbols = set().union(*(left.free_symbols | (right.free_symbols if right is not None else set()) for left, _, right in alternatives))
        if len(symbols) > 1: raise ValueError("当前 Notebook 支持单变量；带参数或方程组请分开演示")
        chosen = next(iter(symbols)) if len(symbols) == 1 else variable
        if variable is not None and symbols and (len(symbols) == 1 and chosen != variable): raise ValueError("同一份推导请使用同一个变量")
        domains, solutions = [], []
        for left, op, right in alternatives:
            domain = sp.S.Reals
            for term in (left, right):
                if term is not None and not term.free_symbols:
                    constant = sp.simplify(term)
                    if constant.is_real is not True or constant.is_finite is not True:
                        raise ValueError("当前实数模式下表达式未定义")
            if chosen is not None:
                domain = continuous_domain(left, chosen, domain)
                if right is not None: domain = domain.intersect(continuous_domain(right, chosen, sp.S.Reals))
            domains.append(domain)
            if op == "expression": continue
            if chosen is None:
                truth = {"=": sp.Eq, "==": sp.Eq, "<": sp.Lt, ">": sp.Gt, "<=": sp.Le, ">=": sp.Ge, "!=": sp.Ne}[op](sp.simplify(left), sp.simplify(right))
                if truth not in (sp.S.true, sp.S.false):
                    raise ValueError("Constant relation could not be decided")
                solutions.append(sp.S.Reals if truth == sp.S.true else sp.S.EmptySet)
            elif op in ("=", "=="):
                solutions.append(sp.solveset(sp.Add(left, -right, evaluate=False), chosen, domain=domain))
            else:
                relation = {"<": sp.Lt, ">": sp.Gt, "<=": sp.Le, ">=": sp.Ge, "!=": sp.Ne}[op](left, right, evaluate=False)
                solutions.append(sp.solve_univariate_inequality(relation, chosen, relational=False).intersect(domain))
        return Line(source, alternatives, chosen, sp.Union(*domains), sp.Union(*solutions) if solutions else None)
    except Exception as exc:
        return Line(source, [], variable, None, None, str(exc)[:240])


def source_lines(payload):
    source = str(payload.get("document", {}).get("source", ""))
    if len(source) > 12000: raise ValueError("文档过长，请拆分推导")
    sources = [line.strip() for line in source.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if len(sources) > 100: raise ValueError("演示计算最多支持 100 步")
    lines, variable = [], None
    for source in sources:
        line = parse_line(source, variable)
        if not line.error and line.variable is not None: variable = line.variable
        lines.append(line)
    return lines


def set_data(value):
    if value is None: return {"kind": "expression"}
    if value.has(sp.ConditionSet): return {"kind": "unverified", "display": text(value), "latex": sp.latex(value)}
    if value == sp.S.EmptySet: return {"kind": "empty"}
    if value == sp.S.Reals: return {"kind": "all_real"}
    if isinstance(value, sp.FiniteSet): return {"kind": "finite", "values": [text(v) for v in sorted(value, key=sp.default_sort_key)], "latex": sp.latex(value)}
    return {"kind": "symbolic", "display": text(value), "latex": sp.latex(value)}


def canonical(line):
    return " or ".join(text(left) if op == "expression" else f"{text(left)} {op} {text(right)}" for left, op, right in line.alternatives)


def state(line):
    known = not line.error and line.domain is not None and not line.domain.has(sp.ConditionSet) and (line.solutions is None or not line.solutions.has(sp.ConditionSet))
    complete = known and line.solutions is not None
    return {"source": line.source, "canonical": canonical(line), "latex": " \\quad\\text{or}\\quad ".join(sp.latex(left) if op == "expression" else sp.latex(left) + " " + {"=": "=", "==": "=", "<": "<", ">": ">", "<=": "\\le", ">=": "\\ge", "!=": "\\ne"}[op] + " " + sp.latex(right) for left, op, right in line.alternatives), "variable": str(line.variable or "x"), "engine": "sympy", "trustLevel": "cas_verified" if complete else "cas_computed" if known else "unverified", "verification": {"status": "verified" if complete else "unknown", "target": "solution_completeness", "method": "sympy_solution_set_and_domain", "limitations": ["single_variable_real_domain", "trusted_CAS_result_not_independent_proof"]}, "solutionSet": set_data(line.solutions), "domain": set_data(line.domain), "reason": line.error or ("SymPy 符号计算" if known else "SymPy 暂时无法求出完整解集")}


def evaluate(line, value):
    if line.error: return {"predicateResult": None, "reason": line.error, "verificationStatus": "unknown"}
    if line.variable is not None:
        membership = line.domain.contains(value)
        if membership == sp.S.false: return {"defined": False, "predicateResult": None}
        if membership != sp.S.true: return {"predicateResult": None, "verificationStatus": "unknown", "reason": "Domain membership unresolved"}
    result = {"defined": True, "predicateResult": None}
    for left, op, right in line.alternatives:
        l = sp.simplify(left.subs(line.variable, value)) if line.variable is not None else sp.simplify(left)
        r = sp.simplify(right.subs(line.variable, value)) if right is not None and line.variable is not None else sp.simplify(right) if right is not None else None
        if l.has(sp.zoo, sp.nan, sp.oo, -sp.oo) or r is not None and r.has(sp.zoo, sp.nan, sp.oo, -sp.oo): continue
        truth = None if r is None else {"=": sp.Eq, "==": sp.Eq, "<": sp.Lt, ">": sp.Gt, "<=": sp.Le, ">=": sp.Ge, "!=": sp.Ne}[op](l, r)
        result = {"defined": True, "predicateResult": truth == sp.S.true if truth in (sp.S.true, sp.S.false) else None, "verificationStatus": "verified" if truth == sp.S.true else "refuted" if truth == sp.S.false else "unknown", "verificationTarget": "predicate_at_assignment", "leftValue": text(l), "rightValue": text(r) if r is not None else None}
        if result["predicateResult"]: return result
    return result


def compare(previous, current):
    relation = {"relation": "unverified", "reason": "SymPy 暂时无法判断两步关系", "lostSolutions": [], "gainedSolutions": [], "domainExpanded": False, "domainShrunk": False}
    if previous.error or current.error: return relation
    if previous.solutions is None or current.solutions is None:
        if previous.solutions is None and current.solutions is None and len(previous.alternatives) == len(current.alternatives) == 1:
            if sp.simplify(previous.alternatives[0][0] - current.alternatives[0][0]) == 0 and previous.domain == current.domain:
                relation.update(relation="equivalent", reason="SymPy 验证表达式等价且定义域保持")
        return relation
    if previous.solutions.has(sp.ConditionSet) or current.solutions.has(sp.ConditionSet): return relation
    lost = previous.solutions - current.solutions
    gained = current.solutions - previous.solutions
    expanded, shrunk = current.domain - previous.domain, previous.domain - current.domain
    if lost.has(sp.ConditionSet) or gained.has(sp.ConditionSet): return relation
    if lost == sp.S.EmptySet and gained == sp.S.EmptySet and expanded == sp.S.EmptySet and shrunk == sp.S.EmptySet:
        relation.update(relation="equivalent", reason="SymPy 验证解集和定义域保持")
    elif any(v.is_empty is False for v in (lost, gained, expanded, shrunk)):
        relation.update(relation="unrelated", reason="SymPy 检测到解集或定义域改变")
    relation.update(lostSolutions=set_data(lost).get("values", []), gainedSolutions=set_data(gained).get("values", []), domainExpanded=expanded.is_empty is False, domainShrunk=shrunk.is_empty is False)
    for candidates in (lost, gained, expanded, shrunk):
        if isinstance(candidates, sp.FiniteSet) and candidates:
            value = sorted(candidates, key=sp.default_sort_key)[0]
            before, after = evaluate(previous, value), evaluate(current, value)
            relation["probe"] = {"value": text(value), **{"previous" + key[0].upper() + key[1:]: v for key, v in before.items()}, **{"current" + key[0].upper() + key[1:]: v for key, v in after.items()}}
            break
    return relation


def trace(lines):
    states, relations, diagnostics = [state(line) for line in lines], [], []
    fault = None
    for i, line in enumerate(lines):
        if line.error or states[i]["trustLevel"] == "unverified": status, message = "unverified", states[i]["reason"]
        elif i == 0: status, message = "valid", "SymPy 已建立符号数学状态"
        else: status, message = "valid", "SymPy 已验证"
        if i:
            relation = compare(lines[i - 1], line)
            relations.append(relation)
            if relation["relation"] == "unverified": status, message = "unverified", relation["reason"]
            elif relation["relation"] != "equivalent":
                status, message = "root_fault" if fault is None else "independent_fault", relation["reason"]
                if fault is None: fault = i
            elif fault is not None: status, message = "tainted", "受前序错误影响"
        diagnostics.append({"status": status, "message": message, "title": message})
    return {"states": states, "relations": relations, "diagnostics": diagnostics, "breakpointStep": fault, "engine": "sympy"}


def transformation(line, operation, argument="2"):
    if line.error: raise ValueError(line.error)
    if len(line.alternatives) != 1 and operation != "solve": raise ValueError("多个分支请分别变形")
    left, op, right = line.alternatives[0]
    if operation == "solve":
        if not isinstance(line.solutions, sp.FiniteSet) or not line.solutions: raise ValueError("当前解集不是可插入的有限根集合，请在检查器查看完整解集")
        return " or ".join(f"{line.variable}={text(v)}" for v in sorted(line.solutions, key=sp.default_sort_key))
    if operation in ("factor", "expand", "simplify"):
        function = {"factor": sp.factor, "expand": sp.expand, "simplify": sp.simplify}[operation]
        l, r = function(left), function(right) if right is not None else None
    elif operation in ("differentiate", "integrate"):
        if op != "expression" or len(left.free_symbols) != 1: raise ValueError("求导/积分请在单变量表达式行使用")
        l, r = (sp.diff if operation == "differentiate" else sp.integrate)(left, line.variable), None
        if operation == "integrate" and l.has(sp.Integral): raise ValueError("SymPy 未求出积分闭式")
    elif operation == "move_terms" and op in ("=", "=="):
        l, r = sp.expand(left - right), sp.Integer(0)
    elif operation in ("divide", "multiply", "square_both_sides") and op in ("=", "=="):
        factor = expression(normalize(argument))
        if factor == 0 and operation == "divide": raise ValueError("不能除以零")
        if operation == "square_both_sides": l, r = left**2, right**2
        elif operation == "divide": l, r = left/factor, right/factor
        else: l, r = left*factor, right*factor
    else: raise ValueError("当前表达式不支持此变形")
    return text(l) if r is None else f"{text(l)}{op}{text(r)}"


def handle(method, payload):
    lines = source_lines(payload)
    if method == "parseDocument":
        return {"steps": [{"source": line.source, "error": {"code": "CAS_INPUT", "message": line.error} if line.error else None} for line in lines], "engine": "sympy"}
    if method in ("runTrace", "replay", "analyzeDocument"): return trace(lines)
    if method == "evaluateProbe":
        value = sp.simplify(expression(normalize(str(payload.get("probe", {}).get("value", "")))))
        if value.free_symbols or value.is_real is not True or value.is_finite is not True: raise ValueError("Probe 请输入有限实数，如 sqrt(2)")
        return {"value": text(value), "steps": [dict(step=i, **evaluate(line, value)) for i, line in enumerate(lines)], "engine": "sympy"}
    index = int(payload.get("step", 0))
    if not 0 <= index < len(lines): raise ValueError("请选择公式行")
    line = lines[index]
    if method == "getCompletions":
        result = []
        for operation, label in [("solve", "求解"), ("simplify", "化简"), ("factor", "因式分解"), ("expand", "展开"), ("move_terms", "移项"), ("differentiate", "求导"), ("integrate", "积分（一个原函数）"), ("square_both_sides", "两边平方")]:
            try:
                target = transformation(line, operation)
                relation = compare(line, parse_line(target, line.variable))
                result.append({"id": operation, "label": label, "available": True, "preview": target, "risk": "safe" if relation["relation"] == "equivalent" else "calculus" if operation in ("differentiate", "integrate") else "requires_review", "engine": "sympy"})
            except Exception: pass
        return result
    if method == "executeTransformation":
        intent = payload.get("intent", {})
        if isinstance(intent, str): intent = {"intent": intent}
        operation = intent.get("intent", "")
        target = transformation(line, operation, str(intent.get("arguments", {}).get("expression", "2")))
        relation = compare(line, parse_line(target, line.variable))
        return {"applied": True, "source": target, "engine": "sympy", "reason": "SymPy 符号变换", "certificate": {"status": "cas_verified" if relation["relation"] == "equivalent" else "unverified", "claimedRelation": relation["relation"], "engine": "sympy"}}
    raise ValueError("未知 CAS 操作")


def main():
    try:
        request = json.loads(sys.stdin.read())
        result = {"ok": True, "result": handle(request["method"], request["payload"])}
    except Exception as exc:
        result = {"ok": False, "error": {"code": "CAS_INPUT", "message": str(exc)[:240]}}
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__": main()
