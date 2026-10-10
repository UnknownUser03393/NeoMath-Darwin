"""Recursive-descent parser for SEL.

Precedence (lowest to highest): ``or`` < ``and`` < comparison < add/sub <
mul/div < power < unary < primary. ``^`` is right-associative. Implicit
multiplication (``2x``) is accepted at the multiplicative level. Call suffix
``name(...)`` applies to identifiers; ``[...]`` applies to semantic references
(execution selectors). Malformed input degrades to error nodes with diagnostics
without aborting the document.
"""

from __future__ import annotations

from neomath.xdlt.sel.lexer import SelToken, tokenize_sel
from neomath.xdlt.sel.nodes import (
    BinaryNode,
    CallNode,
    ComparisonNode,
    ErrorNode,
    ListNode,
    LiteralNode,
    LogicalNode,
    NamedArgumentNode,
    SelDiagnostic,
    SelectorNode,
    SelNode,
    SelRange,
    SemanticReferenceNode,
    SymbolNode,
    UnaryNode,
)

_COMPARISON_OPS = {"==", "!=", "<", "<=", ">", ">="}


def parse_sel(source: str) -> SelNode:
    tokens = tokenize_sel(source)
    parser = _SelParser(source, tokens)
    return parser.parse()


class _SelParser:
    def __init__(self, source: str, tokens: list[SelToken]) -> None:
        self.source = source
        self.tokens = tokens
        self.pos = 0
        self.last_end = 0

    # --- token helpers -------------------------------------------------
    def _peek(self, offset: int = 0) -> SelToken:
        index = min(self.pos + offset, len(self.tokens) - 1)
        return self.tokens[index]

    def _advance(self) -> SelToken:
        token = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        self.last_end = token.end
        return token

    def _is_op(self, value: str, offset: int = 0) -> bool:
        token = self._peek(offset)
        return token.kind == "op" and token.value == value

    def _is_punct(self, value: str) -> bool:
        token = self._peek()
        return token.kind == "punct" and token.value == value

    def _is_keyword(self, value: str) -> bool:
        token = self._peek()
        return token.kind == "keyword" and token.value == value

    def _diag(self, code: str, message: str, start: int, end: int) -> SelDiagnostic:
        return SelDiagnostic("error", code, message, SelRange(start, end))

    def _finish(self, node: SelNode, start: int) -> None:
        node.source = self.source[start : self.last_end]
        node.range = SelRange(start, self.last_end)

    # --- grammar --------------------------------------------------------
    def parse(self) -> SelNode:
        if self._peek().kind == "eof":
            return ErrorNode("", self.source, 0, len(self.source))
        root = self._parse_or()
        token = self._peek()
        if token.kind != "eof":
            root.diagnostics.append(
                self._diag(
                    "SEL_PARSE_ERROR", f"Unexpected token '{token.value}'", token.start, token.end
                )
            )
        return root

    def _parse_or(self) -> SelNode:
        start = self._peek().start
        left = self._parse_and()
        while self._is_keyword("or"):
            self._advance()
            right = self._parse_and()
            node = LogicalNode("or", left, right)
            self._finish(node, start)
            left = node
        return left

    def _parse_and(self) -> SelNode:
        start = self._peek().start
        left = self._parse_comparison()
        while self._is_keyword("and"):
            self._advance()
            right = self._parse_comparison()
            node = LogicalNode("and", left, right)
            self._finish(node, start)
            left = node
        return left

    def _parse_comparison(self) -> SelNode:
        start = self._peek().start
        left = self._parse_additive()
        token = self._peek()
        if token.kind == "op" and token.value in _COMPARISON_OPS:
            self._advance()
            right = self._parse_additive()
            node = ComparisonNode(token.value, left, right)
            self._finish(node, start)
            return node
        return left

    def _parse_additive(self) -> SelNode:
        start = self._peek().start
        left = self._parse_multiplicative()
        while self._peek().kind == "op" and self._peek().value in ("+", "-"):
            operator = self._advance().value
            right = self._parse_multiplicative()
            node = BinaryNode(operator, left, right)
            self._finish(node, start)
            left = node
        return left

    def _parse_multiplicative(self) -> SelNode:
        start = self._peek().start
        left = self._parse_power()
        while True:
            token = self._peek()
            if token.kind == "op" and token.value in ("*", "/"):
                operator = self._advance().value
                right = self._parse_power()
                node = BinaryNode(operator, left, right)
                self._finish(node, start)
                left = node
                continue
            if self._is_implicit_factor_start(token):
                right = self._parse_power()
                node = BinaryNode("*", left, right)
                self._finish(node, start)
                left = node
                continue
            break
        return left

    def _parse_power(self) -> SelNode:
        start = self._peek().start
        left = self._parse_unary()
        if self._is_op("^"):
            self._advance()
            right = self._parse_power()
            node = BinaryNode("^", left, right)
            self._finish(node, start)
            return node
        return left

    def _parse_unary(self) -> SelNode:
        token = self._peek()
        if token.kind == "op" and token.value == "-":
            self._advance()
            operand = self._parse_unary()
            node = UnaryNode("-", operand)
            self._finish(node, token.start)
            return node
        if token.kind == "op" and token.value == "+":
            self._advance()
            return self._parse_unary()
        if self._is_keyword("not"):
            self._advance()
            operand = self._parse_unary()
            node = UnaryNode("not", operand)
            self._finish(node, token.start)
            return node
        return self._parse_postfix()

    def _parse_postfix(self) -> SelNode:
        node = self._parse_primary()
        while True:
            token = self._peek()
            if token.kind == "punct" and token.value == "(" and node.kind == "symbol":
                self._advance()
                args = self._parse_call_args()
                if self._is_punct(")"):
                    self._advance()
                else:
                    node.diagnostics.append(
                        self._diag(
                            "SEL_PARSE_ERROR", "Missing ')'", self._peek().start, self._peek().end
                        )
                    )
                call = CallNode(node.name, args)
                self._finish(call, node.range.start)
                node = call
                continue
            if (
                token.kind == "punct"
                and token.value == "["
                and isinstance(node, SemanticReferenceNode)
            ):
                self._advance()
                index_token = self._peek()
                self._advance()
                if self._is_punct("]"):
                    self._advance()
                else:
                    node.diagnostics.append(
                        self._diag(
                            "SEL_PARSE_ERROR", "Missing ']'", self._peek().start, self._peek().end
                        )
                    )
                selector = SelectorNode(node, index_token.value)
                self._finish(selector, node.range.start)
                node = selector
                continue
            break
        return node

    def _parse_call_args(self) -> list[SelNode]:
        args: list[SelNode] = []
        if self._is_punct(")"):
            return args
        while True:
            arg = self._parse_or()
            if arg.kind == "symbol" and self._is_op("="):
                self._advance()
                value = self._parse_or()
                named = NamedArgumentNode(arg.name, value)
                self._finish(named, arg.range.start)
                args.append(named)
            else:
                args.append(arg)
            if self._is_punct(","):
                self._advance()
                continue
            break
        return args

    def _parse_primary(self) -> SelNode:
        token = self._peek()
        if token.kind == "number":
            self._advance()
            if "." in token.value:
                node: SelNode = LiteralNode("real", token.value)
            else:
                node = LiteralNode("integer", token.value)
            self._finish(node, token.start)
            return node
        if token.kind == "string":
            self._advance()
            node = LiteralNode("string", token.value)
            self._finish(node, token.start)
            return node
        if token.kind == "ref":
            self._advance()
            node = SemanticReferenceNode(token.value)
            self._finish(node, token.start)
            return node
        if token.kind == "identifier":
            self._advance()
            node = SymbolNode(token.value)
            self._finish(node, token.start)
            return node
        if token.kind == "keyword":
            if token.value == "true":
                self._advance()
                node = LiteralNode("boolean", "true")
                self._finish(node, token.start)
                return node
            if token.value == "false":
                self._advance()
                node = LiteralNode("boolean", "false")
                self._finish(node, token.start)
                return node
            if token.value == "null":
                self._advance()
                node = LiteralNode("null", "null")
                self._finish(node, token.start)
                return node
        if token.kind == "punct" and token.value == "(":
            self._advance()
            inner = self._parse_or()
            if self._is_punct(")"):
                self._advance()
            else:
                inner.diagnostics.append(
                    self._diag(
                        "SEL_PARSE_ERROR", "Missing ')'", self._peek().start, self._peek().end
                    )
                )
            return inner
        if token.kind == "punct" and token.value == "[":
            self._advance()
            items: list[SelNode] = []
            if not self._is_punct("]"):
                while True:
                    items.append(self._parse_or())
                    if self._is_punct(","):
                        self._advance()
                        continue
                    break
            if self._is_punct("]"):
                self._advance()
            else:
                pass
            node = ListNode(items)
            self._finish(node, token.start)
            return node
        self._advance()
        node = ErrorNode(token.value, self.source[token.start : token.end], token.start, token.end)
        node.diagnostics.append(
            self._diag(
                "SEL_PARSE_ERROR", f"Unexpected token '{token.value}'", token.start, token.end
            )
        )
        return node

    def _is_implicit_factor_start(self, token: SelToken) -> bool:
        if token.kind in ("number", "string", "ref", "identifier"):
            return True
        if token.kind == "keyword" and token.value in ("true", "false", "null"):
            return True
        if token.kind == "punct" and token.value in ("(", "["):
            return True
        return False
