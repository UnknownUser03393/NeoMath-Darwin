"""Recursive-descent parser for the supported LaTeX-math subset.

Produces a Math Surface AST. Unknown commands degrade locally to
``OpaqueNode`` with an ``UNSUPPORTED_MATH_COMMAND`` diagnostic; unbalanced or
unexpected input degrades to ``MATH_PARSE_ERROR`` diagnostics without aborting
the surrounding document.
"""

from __future__ import annotations

from neomath.xdlt.math.lexer import Token, tokenize
from neomath.xdlt.math.nodes import (
    AddNode,
    DivideNode,
    EmptyNode,
    FractionNode,
    FunctionCallNode,
    GroupNode,
    IntegerNode,
    IntegralNode,
    MathDiagnostic,
    MathNode,
    MathRange,
    MultiplyNode,
    NegateNode,
    OpaqueNode,
    PartialDerivativeNode,
    PowerNode,
    ProductNode,
    RealNode,
    RelationNode,
    RootNode,
    SubscriptNode,
    SumNode,
    SymbolNode,
    TextNode,
    TupleNode,
)

_RELATION_OPS = {"=", "!=", "<", "<=", ">", ">="}
_OPERATOR_COMMANDS = {"cdot", "times", "leq", "geq", "neq"}
_RELATION_COMMANDS = {"leq": "<=", "geq": ">=", "neq": "!="}
_FUNCTIONS = {"sin", "cos", "tan", "log", "ln", "exp", "lim"}
_GREEK = {
    "alpha": "alpha",
    "beta": "beta",
    "gamma": "gamma",
    "delta": "delta",
    "epsilon": "epsilon",
    "varepsilon": "epsilon",
    "zeta": "zeta",
    "eta": "eta",
    "theta": "theta",
    "vartheta": "theta",
    "iota": "iota",
    "kappa": "kappa",
    "lambda": "lambda",
    "mu": "mu",
    "nu": "nu",
    "xi": "xi",
    "pi": "pi",
    "rho": "rho",
    "sigma": "sigma",
    "tau": "tau",
    "upsilon": "upsilon",
    "phi": "phi",
    "varphi": "phi",
    "chi": "chi",
    "psi": "psi",
    "omega": "omega",
    "Gamma": "Gamma",
    "Delta": "Delta",
    "Theta": "Theta",
    "Lambda": "Lambda",
    "Pi": "Pi",
    "Sigma": "Sigma",
    "Phi": "Phi",
    "Psi": "Psi",
    "Omega": "Omega",
    "infty": "infty",
}

_OPEN_TO_CLOSE = {"lparen": "rparen", "lbracket": "rbracket", "pipe": "pipe", "lbrace": "rbrace"}


def parse_math(source: str) -> MathNode:
    tokens = tokenize(source)
    parser = _MathParser(source, tokens)
    return parser.parse()


class _MathParser:
    def __init__(self, source: str, tokens: list[Token]) -> None:
        self.source = source
        self.tokens = tokens
        self.pos = 0
        self.last_end = 0
        self.integral_depth = 0

    # --- token helpers -------------------------------------------------
    def _peek(self, offset: int = 0) -> Token:
        index = min(self.pos + offset, len(self.tokens) - 1)
        return self.tokens[index]

    def _advance(self) -> Token:
        token = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        self.last_end = token.end
        return token

    def _at_op(self, value: str) -> bool:
        token = self._peek()
        return token.kind == "op" and token.value == value

    def _at_command(self, name: str) -> bool:
        token = self._peek()
        return token.kind == "command" and token.value == name

    def _diag(self, code: str, message: str, start: int, end: int) -> MathDiagnostic:
        return MathDiagnostic("error", code, message, MathRange(start, end))

    def _finish(self, node: MathNode, start: int) -> None:
        node.source = self.source[start : self.last_end]
        node.range = MathRange(start, self.last_end)

    # --- grammar --------------------------------------------------------
    def parse(self) -> MathNode:
        if self._peek().kind == "eof":
            return EmptyNode(self.source)
        root = self._parse_relation()
        token = self._peek()
        if token.kind != "eof":
            root.diagnostics.append(
                self._diag(
                    "MATH_PARSE_ERROR",
                    f"Unexpected token '{token.value}'",
                    token.start,
                    token.end,
                )
            )
        return root

    def _parse_relation(self) -> MathNode:
        start = self._peek().start
        operands = [self._parse_additive()]
        operators: list[str] = []
        while True:
            token = self._peek()
            operator: str | None = None
            if token.kind == "op" and token.value in _RELATION_OPS:
                operator = token.value
            elif token.kind == "command" and token.value in _RELATION_COMMANDS:
                operator = _RELATION_COMMANDS[token.value]
            if operator is None:
                break
            operators.append(operator)
            self._advance()
            operands.append(self._parse_additive())
        if not operators:
            return operands[0]
        node: MathNode = RelationNode(operators[0], operands[0], operands[1])
        for index in range(1, len(operators)):
            node = RelationNode(operators[index], node, operands[index + 1])
        self._finish(node, start)
        return node

    def _parse_additive(self) -> MathNode:
        start = self._peek().start
        terms = [self._parse_multiplicative()]
        operators: list[Token] = []
        while self._peek().kind == "op" and self._peek().value in ("+", "-"):
            operators.append(self._advance())
            terms.append(self._parse_multiplicative())
        if not operators:
            return terms[0]
        operands: list[MathNode] = [terms[0]]
        for operator, term in zip(operators, terms[1:], strict=True):
            if operator.value == "-":
                operand = NegateNode(
                    term,
                    self.source[operator.start : term.range.end],
                    operator.start,
                    term.range.end,
                )
                operands.append(operand)
            else:
                operands.append(term)
        node = AddNode(operands)
        self._finish(node, start)
        return node

    def _parse_multiplicative(self) -> MathNode:
        start = self._peek().start
        result = self._parse_unary()
        while True:
            token = self._peek()
            if self.integral_depth > 0 and self._is_differential_boundary():
                break
            if token.kind == "op" and token.value == "*":
                self._advance()
                result = self._combine_multiply(result, self._parse_unary(), start)
                continue
            if token.kind == "op" and token.value == "/":
                self._advance()
                right = self._parse_unary()
                node = DivideNode(result, right)
                self._finish(node, start)
                result = node
                continue
            if token.kind == "command" and token.value in ("cdot", "times"):
                self._advance()
                result = self._combine_multiply(result, self._parse_unary(), start)
                continue
            if self._is_factor_start(token):
                result = self._combine_multiply(result, self._parse_unary(), start)
                continue
            break
        return result

    def _combine_multiply(self, left: MathNode, right: MathNode, start: int) -> MathNode:
        # f(x) or f(x, y) is function application rather than multiplication.
        node: MathNode
        if left.kind == "symbol" and right.kind == "group":
            inner = right.inner
            args = list(inner.parts) if inner.kind == "tuple" else [inner]
            node = FunctionCallNode(left.name, args)
            node.source = self.source[start : right.range.end]
            node.range = MathRange(start, right.range.end)
            return node
        if left.kind == "multiply":
            operands = list(left.operands)
            operands.append(right)
            node = MultiplyNode(operands)
        else:
            node = MultiplyNode([left, right])
        node.source = self.source[start : right.range.end]
        node.range = MathRange(start, right.range.end)
        return node

    def _parse_unary(self) -> MathNode:
        token = self._peek()
        if token.kind == "op" and token.value == "-":
            self._advance()
            operand = self._parse_unary()
            return NegateNode(
                operand,
                self.source[token.start : operand.range.end],
                token.start,
                operand.range.end,
            )
        if token.kind == "op" and token.value == "+":
            self._advance()
            return self._parse_unary()
        return self._parse_power()

    def _parse_power(self) -> MathNode:
        base = self._parse_postfix()
        if self._at_op("^"):
            self._advance()
            exponent = self._parse_unary()
            node = PowerNode(base, exponent)
            self._finish(node, base.range.start)
            return node
        return base

    def _parse_postfix(self) -> MathNode:
        base = self._parse_primary()
        while self._at_op("_"):
            self._advance()
            subscript = self._parse_script_arg()
            node = SubscriptNode(base, subscript)
            self._finish(node, base.range.start)
            base = node
        return base

    def _parse_script_arg(self) -> MathNode:
        if self._peek().kind == "lbrace":
            return self._parse_braced_expression()
        return self._parse_primary()

    def _parse_braced_expression(self) -> MathNode:
        open_token = self._advance()
        inner = self._parse_relation()
        token = self._peek()
        if token.kind == "rbrace":
            self._advance()
        else:
            inner.diagnostics.append(
                self._diag("MATH_PARSE_ERROR", "Missing closing '}'", token.start, token.end)
            )
        node = GroupNode(inner)
        self._finish(node, open_token.start)
        return node

    def _parse_primary(self) -> MathNode:
        token = self._peek()
        if token.kind == "number":
            self._advance()
            if "." in token.value:
                node: MathNode = RealNode(token.value)
            else:
                node = IntegerNode(token.value)
            self._finish(node, token.start)
            return node
        if token.kind == "symbol":
            self._advance()
            node = SymbolNode(token.value, token.value)
            self._finish(node, token.start)
            return node
        if token.kind == "text":
            self._advance()
            node = TextNode(token.value)
            self._finish(node, token.start)
            return node
        if token.kind == "lbrace":
            return self._parse_braced_expression()
        if token.kind in ("lparen", "lbracket", "pipe"):
            return self._parse_parenthesized()
        if token.kind == "command":
            return self._parse_command(token.value)
        self._advance()
        node = OpaqueNode("", token.value)
        node.diagnostics.append(
            self._diag(
                "MATH_PARSE_ERROR", f"Unexpected token '{token.value}'", token.start, token.end
            )
        )
        self._finish(node, token.start)
        return node

    def _parse_parenthesized(self) -> MathNode:
        open_token = self._advance()
        parts = [self._parse_relation()]
        while self._peek().kind == "comma":
            self._advance()
            parts.append(self._parse_relation())
        expected = _OPEN_TO_CLOSE[open_token.kind]
        token = self._peek()
        if token.kind == expected:
            self._advance()
        else:
            parts[-1].diagnostics.append(
                self._diag("MATH_PARSE_ERROR", "Missing closing delimiter", token.start, token.end)
            )
        if len(parts) == 1:
            inner = parts[0]
        else:
            inner = TupleNode(parts)
            inner.source = self.source[open_token.start : self.last_end]
            inner.range = MathRange(open_token.start, self.last_end)
        node = GroupNode(inner)
        self._finish(node, open_token.start)
        return node

    # --- commands -------------------------------------------------------
    def _parse_command(self, name: str) -> MathNode:
        start = self._peek().start
        node: MathNode
        if name in _GREEK:
            self._advance()
            node = SymbolNode(_GREEK[name], "\\" + name)
            self._finish(node, start)
            return node
        if name == "frac":
            self._advance()
            numerator = self._parse_script_arg()
            denominator = self._parse_script_arg()
            node = FractionNode(numerator, denominator)
            self._finish(node, start)
            return node
        if name == "sqrt":
            self._advance()
            degree: MathNode | None = None
            if self._peek().kind == "lbracket":
                self._advance()
                degree = self._parse_relation()
                if self._peek().kind == "rbracket":
                    self._advance()
                else:
                    degree.diagnostics.append(
                        self._diag(
                            "MATH_PARSE_ERROR",
                            "Missing ']' after sqrt degree",
                            self._peek().start,
                            self._peek().end,
                        )
                    )
            radicand = self._parse_script_arg()
            node = RootNode(radicand, degree)
            self._finish(node, start)
            return node
        if name in _FUNCTIONS:
            self._advance()
            args: list[MathNode] = []
            if self._is_factor_start(self._peek()):
                args.append(self._parse_function_arg())
            node = FunctionCallNode(name, args)
            self._finish(node, start)
            return node
        if name == "sum":
            self._advance()
            lower, upper = self._parse_limits()
            body = self._parse_multiplicative()
            node = SumNode(body, lower, upper)
            self._finish(node, start)
            return node
        if name == "prod":
            self._advance()
            lower, upper = self._parse_limits()
            body = self._parse_multiplicative()
            node = ProductNode(body, lower, upper)
            self._finish(node, start)
            return node
        if name == "int":
            return self._parse_integral()
        if name == "partial":
            return self._parse_partial()
        if name == "left":
            return self._parse_left_right()
        return self._parse_unknown_command(name)

    def _parse_function_arg(self) -> MathNode:
        token = self._peek()
        if token.kind in ("lparen", "lbracket", "pipe"):
            return self._parse_parenthesized()
        return self._parse_postfix()

    def _parse_limits(self) -> tuple[MathNode | None, MathNode | None]:
        lower: MathNode | None = None
        upper: MathNode | None = None
        if self._at_op("_"):
            self._advance()
            lower = self._parse_script_arg()
        if self._at_op("^"):
            self._advance()
            upper = self._parse_script_arg()
        return lower, upper

    def _parse_integral(self) -> MathNode:
        start = self._peek().start
        self._advance()
        lower, upper = self._parse_limits()
        self.integral_depth += 1
        body = self._parse_multiplicative()
        self.integral_depth -= 1
        variable: str | None = None
        if self._peek().kind == "symbol" and self._peek().value == "d":
            self._advance()
            next_token = self._peek()
            if next_token.kind == "symbol":
                variable = self._advance().value
        node = IntegralNode(body, lower, upper, variable)
        self._finish(node, start)
        return node

    def _parse_partial(self) -> MathNode:
        start = self._peek().start
        self._advance()
        order: MathNode | None = None
        if self._at_op("^"):
            self._advance()
            order = self._parse_script_arg()
        expression = self._parse_postfix()
        node = PartialDerivativeNode(expression, order)
        self._finish(node, start)
        return node

    def _parse_left_right(self) -> MathNode:
        start = self._peek().start
        self._advance()  # \left
        token = self._peek()
        if token.kind in _OPEN_TO_CLOSE or (token.kind == "command" and token.value in ("{", "}")):
            self._advance()
        inner = self._parse_relation()
        token = self._peek()
        if token.kind == "command" and token.value == "right":
            self._advance()
            closing = self._peek()
            if closing.kind in ("rparen", "rbracket", "pipe", "rbrace") or (
                closing.kind == "command" and closing.value in ("{", "}")
            ):
                self._advance()
        else:
            inner.diagnostics.append(
                self._diag("MATH_PARSE_ERROR", "Missing '\\right'", token.start, token.end)
            )
        node = GroupNode(inner)
        self._finish(node, start)
        return node

    def _parse_unknown_command(self, name: str) -> MathNode:
        start = self._peek().start
        self._advance()
        args_raw = self._consume_balanced_args()
        node = OpaqueNode("\\" + name, args_raw)
        node.diagnostics.append(
            MathDiagnostic(
                "warning",
                "UNSUPPORTED_MATH_COMMAND",
                f"Unsupported math command '\\{name}'",
                MathRange(start, self.last_end),
            )
        )
        self._finish(node, start)
        return node

    def _consume_balanced_args(self) -> str:
        parts: list[str] = []
        while self._peek().kind in ("lbrace", "lbracket"):
            open_token = self._advance()
            close_kind = _OPEN_TO_CLOSE[open_token.kind]
            depth = 1
            parts.append(open_token.value)
            while depth > 0 and self._peek().kind != "eof":
                token = self._advance()
                if token.kind == open_token.kind:
                    depth += 1
                elif token.kind == close_kind:
                    depth -= 1
                parts.append(token.value)
        return "".join(parts)

    # --- lookahead ------------------------------------------------------
    def _is_differential_boundary(self) -> bool:
        token = self._peek()
        if token.kind == "symbol" and token.value == "d":
            return self._peek(1).kind == "symbol"
        return False

    def _is_factor_start(self, token: Token) -> bool:
        if token.kind in ("number", "symbol", "text", "lbrace", "lparen", "lbracket", "pipe"):
            return True
        if token.kind == "command":
            # ``\right`` closes a ``\left ... \right`` group; it must not be
            # consumed as an implicit multiplication factor.
            if token.value == "right":
                return False
            return token.value not in _OPERATOR_COMMANDS
        return False
